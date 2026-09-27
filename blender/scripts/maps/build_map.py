"""Build a Spider Quest map: geometry -> vertex-paint bake -> budget checks -> .blend + FBX + manifest.

Headless only:
    python blender/scripts/maps/build_map.py --map lobby          (with the `bpy` module)
    blender -b -P blender/scripts/maps/build_map.py -- --map lobby

Maps: main_menu, lobby, mossy_hollow (see map_config.MAPS). Writes
  blender/sources/maps/<map>.blend
  blender/exports/maps/<map>.fbx + <map>.manifest.json           (main_menu, lobby)
  blender/exports/maps/mossy_hollow/<room>.fbx + manifest.json   (one FBX per room, each at its own origin)
"""

import argparse
import math
import os
import sys

import bpy  # must come before bmesh when running as the bpy module
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import map_kit as K  # noqa: E402
import map_props as MP  # noqa: E402
import map_stations as MS  # noqa: E402
from map_config import KIT, MAPS, PALETTE as P, SHADING  # noqa: E402

TAU = math.tau


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", required=True, choices=sorted(MAPS))
    parser.add_argument("--no-export", action="store_true")
    parser.add_argument("--draft", action="store_true",
                        help="preview iteration: report budget overruns instead of raising, never export")
    return parser.parse_args(argv)


def camel(s):
    return "".join(part.capitalize() for part in s.split("_"))


def deg(a):
    return math.radians(a)


def in_triangle(p, a, b, c):
    def side(p1, p2, p3):
        return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])
    d1, d2, d3 = side(p, a, b), side(p, b, c), side(p, c, a)
    return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))


# ---------------------------------------------------------------- builder

class Builder:
    """Collects objects for one exportable unit (a map, or one dungeon room)."""

    def __init__(self, map_id, unit_id, material, kit_cache, coll):
        self.map_id, self.unit_id = map_id, unit_id
        self.material = material
        self.kit_cache = kit_cache
        self.coll = coll
        self.names = {}
        self.objects = []
        self.taken = []        # (x, y, r) footprints of solid things, so scatter keeps clear
        self.deco_taken = []
        self.exclude = []      # accept(x, y) -> bool filters for scatter
        self.height = lambda x, y: 0.0

    def geo(self, *parts):
        return K.Geo(self.map_id, self.unit_id, *parts)

    def uname(self, prefix, base, numbered=True):
        key = f"{prefix}_{base}"
        if not numbered:
            return key
        n = self.names.get(key, 0) + 1
        self.names[key] = n
        return f"{key}_{n:02d}"

    def add_geo(self, prefix, base, geo, matrix=K.IDENTITY, numbered=True, occluder=True):
        if not geo.bm.faces:
            geo.bm.free()
            return None
        name = self.uname(prefix, base, numbered)
        me = K.mesh_from_geo(geo, f"{self.unit_id}_{name}", self.material, occluder=occluder,
                             sharp_angle=SHADING["sharpAngle"])
        obj = K.place(name, me, self.coll, matrix)
        self.objects.append(obj)
        return obj

    def kit_mesh(self, kit_id, variant):
        key = (kit_id, variant)
        if key not in self.kit_cache:
            spec = KIT[kit_id]
            rng = K.rng_for("kit", kit_id, variant)
            params = MP.resolve(rng, spec["params"])
            g = K.Geo("kit", kit_id, variant)
            getattr(MP, spec["gen"])(g, rng, **params)
            self.kit_cache[key] = K.mesh_from_geo(g, f"kit_{kit_id}_{variant}", self.material, kit=True,
                                                  ground=spec.get("ground", True),
                                                  occluder=spec.get("occluder", True),
                                                  sharp_angle=SHADING["sharpAngle"])
        return self.kit_cache[key]

    def add_kit(self, prefix, kit_id, matrix, variant=0, base=None):
        obj = K.place(self.uname(prefix, base or camel(kit_id)), self.kit_mesh(kit_id, variant), self.coll, matrix)
        self.objects.append(obj)
        if getattr(self, "fit", None):
            self.keep_inside(obj)
        return obj

    def keep_inside(self, obj, margin=0.5):
        """Rooms: nudge a kit instance back inside the footprint, shrinking it if it cannot fit."""
        hx, hy = self.fit[0] / 2 - margin, self.fit[1] / 2 - margin
        for _ in range(6):
            bpy.context.view_layer.update()
            lo, hi = K.world_bounds(obj)
            dx = (-hx - lo.x if lo.x < -hx else 0.0) + (hx - hi.x if hi.x > hx else 0.0)
            dy = (-hy - lo.y if lo.y < -hy else 0.0) + (hy - hi.y if hi.y > hy else 0.0)
            if not dx and not dy:
                return
            if hi.x - lo.x < 2 * hx and hi.y - lo.y < 2 * hy:
                obj.location.x += dx
                obj.location.y += dy
            else:
                obj.scale *= 0.9

    def marker(self, name, pos):
        obj = K.add_marker(name, pos, self.coll, self.material)
        self.objects.append(obj)
        return obj

    def barrier(self, base, corners, numbered=True):
        """BARRIER_: invisible collision the spider controller cannot stick to (Studio excludes it from raycasts)."""
        name = self.uname("BARRIER", base, numbered)
        obj = K.place(name, K.barrier_mesh(f"{self.unit_id}_{name}", corners, self.material), self.coll)
        self.objects.append(obj)
        return obj

    def block(self, x, y, r, deco=False):
        (self.deco_taken if deco else self.taken).append((x, y, r))

    def accept(self, x, y):
        return all(f(x, y) for f in self.exclude)

    def add_exclusions(self, zones):
        for zone in zones:
            if zone[0] == "circle":
                _, x, y, r = zone
                self.exclude.append(lambda px, py, x=x, y=y, r=r: (px - x) ** 2 + (py - y) ** 2 > r * r)
            elif zone[0] == "rect":
                _, x0, y0, x1, y1 = zone
                self.exclude.append(lambda px, py, x0=x0, y0=y0, x1=x1, y1=y1: not (x0 <= px <= x1 and y0 <= py <= y1))
            elif zone[0] == "tri":
                self.exclude.append(lambda px, py, t=zone[1:]: not in_triangle((px, py), *t))
            else:
                raise ValueError(zone)

    def drop(self, x, y, objects, z0=500.0):
        """Highest surface point of `objects` under (x, y) (for markers sitting on props)."""
        from mathutils.bvhtree import BVHTree
        verts, polys = [], []
        for obj in objects:
            base = len(verts)
            verts.extend(obj.matrix_world @ v.co for v in obj.data.vertices)
            polys.extend([base + i for i in p.vertices] for p in obj.data.polygons)
        hit = BVHTree.FromPolygons(verts, polys).ray_cast(Vector((x, y, z0)), Vector((0, 0, -1)), 2 * z0)
        return hit[0].z if hit[0] is not None else self.height(x, y)

    # -- scatter
    def scatter(self, spec, sampler=None):
        rng = K.rng_for(self.map_id, self.unit_id, "scatter", spec.get("name", spec["kit"]))
        kits = spec["kit"] if isinstance(spec["kit"], (list, tuple)) else [spec["kit"]]
        prefix = spec.get("prefix", "PROP")
        deco = prefix == "DECO"
        area = spec["area"]
        if sampler is None:
            if area[0] == "annulus":
                r0, r1 = area[1], area[2]
                a0, a1 = deg(area[3]) if len(area) > 3 else 0.0, deg(area[4]) if len(area) > 4 else TAU

                def sampler():
                    r = math.sqrt(rng.uniform(r0 * r0, r1 * r1))
                    a = rng.uniform(a0, a1)
                    return r * math.cos(a), r * math.sin(a)
            elif area[0] == "rect":
                x0, y0, x1, y1 = area[1:]

                def sampler():
                    return rng.uniform(x0, x1), rng.uniform(y0, y1)
            else:
                raise ValueError(area)
        own = spec.get("clearOf", "self")
        taken = self.deco_taken if deco else self.taken
        if own == "none":
            taken = []
        extra = spec.get("accept")
        if spec.get("avoid"):
            saved = self.exclude
            self.exclude = []
            self.add_exclusions(spec["avoid"])
            avoid, self.exclude = self.exclude, saved
            extra0 = extra
            extra = lambda x, y: all(f(x, y) for f in avoid) and (extra0(x, y) if extra0 else True)
        accept = (lambda x, y: self.accept(x, y) and extra(x, y)) if extra else self.accept
        if spec.get("ignoreExclusions"):
            accept = extra
        pts = K.poisson(rng, spec["count"], sampler, spec.get("minDist", 8.0), accept=accept, taken=taken)
        out = []
        cluster = spec.get("cluster")
        for x, y in pts:
            members = [(x, y, 1.0)]
            if cluster:
                n = rng.randint(cluster[0], cluster[1])
                for _ in range(n - 1):
                    a, d = rng.uniform(0, TAU), rng.uniform(0.35, 1.0) * cluster[2]
                    members.append((x + d * math.cos(a), y + d * math.sin(a), rng.uniform(0.55, 0.85)))
            for mx, my, ms in members:
                kit_id = rng.choice(kits)
                variant = rng.randrange(KIT[kit_id]["variants"])
                s = rng.uniform(*spec.get("scale", (0.85, 1.15))) * ms
                tilt = spec.get("tilt", 0.0)
                tl = (deg(rng.uniform(-tilt, tilt)), deg(rng.uniform(-tilt, tilt))) if tilt else (0.0, 0.0)
                z = self.height(mx, my) - spec.get("sink", 0.3) * s
                out.append(self.add_kit(prefix, kit_id, K.mat((mx, my, z), rng.uniform(0, TAU), s, tl), variant))
        return out

    def finish(self, budget, shading, draft=False):
        K.bake_colors(self.objects, shading, P)
        try:
            return K.check_budget(self.unit_id, self.objects, budget)
        except RuntimeError as err:
            if not draft:
                raise
            print(f"[map] DRAFT, not exportable: {err}")
            return None


def shading_for(cfg):
    sh = dict(SHADING)
    sh.update(cfg.get("shading", {}))
    return sh


def new_unit(map_id, unit_id, coll, kit_cache, material):
    return Builder(map_id, unit_id, material, kit_cache, coll)


# ---------------------------------------------------------------- lobby: Webhollow

def build_lobby(map_id, cfg, material):
    coll = K.collection(map_id)
    b = new_unit(map_id, map_id, coll, {}, material)
    st, fl, gate = cfg["stump"], cfg["floor"], cfg["gate"]
    noise = K.Noise(map_id, "ground")
    gate_a = deg(gate["angle"])
    gate_c = Vector((gate["radius"] * math.cos(gate_a), gate["radius"] * math.sin(gate_a)))

    def height(x, y):
        r = math.hypot(x, y)
        n = noise((x, y), 1 / 38, 2)
        amp = K.lerp(fl["noise"], fl["outerNoise"], K.smoothstep(113, 160, r))
        fade_gate = K.smoothstep(gate["skirt"] - 2, gate["skirt"] + 18, (Vector((x, y)) - gate_c).length)
        z = amp * n * fade_gate
        z += fl["berm"] * K.smoothstep(212, 250, r) * (1 - K.smoothstep(290, 330, r))
        return z * (1 - K.smoothstep(330, 360, r))

    b.height = height

    # ---- floors (inside: rotting-wood mulch; outside: forest floor) share one height field and a seam ring
    ent_a = deg(st["entrance"]["angle"])

    def inner_color(x, y, z):
        r = math.hypot(x, y)
        n1, n2, n3 = noise((x, y), 1 / 16, 2), noise((x + 300, y), 1 / 7), noise((x, y + 500), 1 / 16)
        c = K.mix(P["mulch"], P["mulch_light"], K.smoothstep(-0.35, 0.45, n1) * 0.8)
        c = K.mix(c, P["wood_dark"], K.smoothstep(0.2, 0.55, n2) * 0.4)
        c = K.mix(c, P["leaf_orange"], K.smoothstep(0.3, 0.6, -n2) * 0.3)
        lane = K.smoothstep(26, 8, abs(x)) * K.smoothstep(-20, -60, y)
        ring = K.smoothstep(12, 2, abs(r - 58))
        c = K.mix(c, P["wood_pale"], max(lane, ring) * 0.35)
        c = K.mix(c, P["moss"], K.smoothstep(86, 108, r) * K.smoothstep(-0.1, 0.4, n3) * 0.7)
        return c

    def outer_color(x, y, z):
        r = math.hypot(x, y)
        n1, n2, n3 = noise((x, y), 1 / 28, 2), noise((x - 200, y), 1 / 13, 2), noise((x, y - 400), 1 / 6)
        c = K.mix(P["loam"], P["loam_light"], K.smoothstep(-0.4, 0.5, n3) * 0.7)
        moss = K.mix(P["moss_dark"], P["moss"], K.smoothstep(-0.3, 0.5, n3))
        c = K.mix(c, moss, K.smoothstep(-0.1, 0.25, n1) * 0.8)
        litter = K.mix(P["leaf_brown"], P["leaf_orange"], K.smoothstep(-0.2, 0.5, n3))
        c = K.mix(c, litter, K.smoothstep(0.1, 0.4, n2) * 0.55)
        return K.mix(c, P["moss_dark"], K.smoothstep(280, 420, r) * 0.6)

    def keep_floor(cx, cy):
        return (Vector((cx, cy)) - gate_c).length > gate["hole"]

    g = b.geo("floor")
    g.polar_heightfield(fl["rings"], fl["segments"], height, inner_color, -6.0, keep=keep_floor)
    b.add_geo("COL", "Floor", g, numbered=False)
    g = b.geo("forest_floor")
    g.polar_heightfield(fl["outerRings"], fl["segments"], height, outer_color, -6.0)
    b.add_geo("COL", "ForestFloor", g, numbered=False)

    # ---- stump wall: 16 closed ring segments sharing their boundary columns
    snoise = K.Noise(map_id, "stump")
    rng = K.rng_for(map_id, "stump")
    ncols = st["segments"] * st["colsPerSegment"]
    dth = TAU / ncols
    spikes = {}
    for _ in range(st["spikes"]):  # splinter clusters: a peak column with shorter neighbours
        c, h = rng.randrange(ncols), rng.uniform(*st["spikeHeight"])
        for dc, f in ((0, 1.0), (-1, rng.uniform(0.2, 0.6)), (1, rng.uniform(0.2, 0.6))):
            spikes[(c + dc) % ncols] = max(spikes.get((c + dc) % ncols, 0.0), h * f)
    for a, h in st["towers"]:
        c = int(round(deg(a) / dth)) % ncols
        for dc, f in ((0, 1.0), (1, 0.75), (-1, 0.35), (2, 0.3)):
            spikes[(c + dc) % ncols] = max(spikes.get((c + dc) % ncols, 0.0), h * f)
    ent = st["entrance"]

    def col_index(th):
        return int(round((th % TAU) / dth)) % ncols

    def ang_dist(a, b_):
        return abs((a - b_ + math.pi) % TAU - math.pi)

    def rim_out(th):
        z = st["height"] + st["rimNoise"] * snoise((math.cos(th) * 1.4, math.sin(th) * 1.4, 3.0), 1.0, 2)
        for a, depth, half in st["breaks"]:
            d = ang_dist(th, deg(a)) / deg(half)
            z -= depth * math.exp(-d * d * 2.0)
        return z + spikes.get(col_index(th), 0.0)

    def rim_in(th):
        lo, hi = st["innerDrop"]
        return rim_out(th) - spikes.get(col_index(th), 0.0) * 0.8 - K.lerp(lo, hi, 0.5 + 0.5 * snoise((math.cos(th) * 3, math.sin(th) * 3, 9.0)))

    def bottom(th):
        d = ang_dist(th, ent_a) / deg(ent["halfWidth"])
        if d >= 1.0:
            return -2.0
        return ent["height"] * math.sqrt(1 - d * d) ** 0.9

    def taper(z):
        return 1.0 - st["taper"] * K.clamp(z / st["height"])

    def lumps(th, z):
        return st["lumps"] * snoise((math.cos(th) * 1.6, math.sin(th) * 1.6, z * 0.009), 1.0, 2)

    def r_out(th, z):
        c = col_index(th)
        ridge = st["barkRidge"] * (1.0 if c % 2 else -0.45) * (1 + 0.4 * snoise((th * 4, z * 0.05, 1)))
        flare = st["flare"] * math.exp(-max(0.0, z) / st["flareHeight"])
        return st["rOut"] * taper(z) + ridge + lumps(th, z) + flare

    def r_in(th, z):
        hollow = 3.5 * snoise((math.cos(th) * 3, math.sin(th) * 3, z * 0.02 + 5), 1.0, 2)
        return st["rIn"] * taper(z) + hollow + lumps(th, z) * 0.6 - 3.0 * math.exp(-max(0.0, z) / 10.0)

    def c_out(th, z, co):
        c = col_index(th)
        base = K.mix(P["bark"], P["bark_light"], 0.35) if c % 2 else K.mix(P["bark_dark"], P["bark"], 0.3)
        streak = snoise((th * 9, z * 0.03, 2), 1.0)
        base = K.mix(base, P["bark_light"], K.smoothstep(0.25, 0.7, streak) * 0.4)
        lich = snoise((math.cos(th) * 5, math.sin(th) * 5, z * 0.035), 1.0, 2)
        base = K.mix(base, P["lichen"], K.smoothstep(0.2, 0.5, lich) * 0.5)
        base = K.mix(base, P["moss"], K.smoothstep(30, 2, z) * K.smoothstep(-0.3, 0.3, streak + 0.2) * 0.7)
        return base, 0.35

    def c_in(th, z, co):
        streak = snoise((math.cos(th) * 5, math.sin(th) * 5, z * 0.018), 1.0, 2)
        c = K.mix(P["wood_rot"], P["wood_pale"], 0.25 + K.smoothstep(-0.2, 0.5, streak) * 0.55)
        c = K.mix(c, P["wood_dark"], K.smoothstep(0.35, 0.65, -streak) * 0.35)
        c = K.mix(c, P["mulch"], K.smoothstep(40, 0, z) * 0.35)
        c = K.mix(c, P["moss"], K.smoothstep(12, 0, z) * 0.5)
        return c, 0.3

    def c_rim(th, z, co):
        return P["wood_pale"], 0.3

    def mid(th):
        zi, zo = rim_in(th), rim_out(th)
        z = max(zi, zo - spikes.get(col_index(th), 0.0)) + 2.0 + 3.0 * snoise((math.cos(th) * 4, math.sin(th) * 4, 17.0))
        r = (r_in(th, z) + r_out(th, z)) * 0.5
        return r, z, K.mix(P["wood_pale"], P["wood_rot"], 0.35), 0.45

    for s in range(st["segments"]):
        g = b.geo("stump", s)
        t0, t1 = TAU * s / st["segments"], TAU * (s + 1) / st["segments"]
        MP.ring_panel(g, t0, t1, st["colsPerSegment"], st["rows"], r_in, r_out,
                      lambda th: (bottom(th), rim_in(th)), lambda th: (bottom(th), rim_out(th)),
                      c_in, c_out, c_rim, mid=mid)
        b.add_geo("COL", "StumpWall", g)

    # ---- buttress roots outside the stump
    rng = K.rng_for(map_id, "roots")
    for i, a in enumerate(cfg["roots"]):
        th = deg(a) + rng.uniform(-0.05, 0.05)
        d = Vector((math.cos(th), math.sin(th), 0))
        side = Vector((-d.y, d.x, 0))
        bend = rng.uniform(-1, 1)
        reach = rng.uniform(70, 100)
        pts = []
        for k, (f, z) in enumerate(((0.0, 46), (0.12, 30), (0.3, 16), (0.5, 8), (0.72, 3), (1.0, -5))):
            wig = side * (bend * 18 * f * f + rng.uniform(-4, 4) * f)
            pts.append(d * (st["rOut"] - 10 + reach * f) + wig + Vector((0, 0, z + rng.uniform(-1.5, 1.5) * f)))
        g = b.geo("root", i)
        MP.root(g, rng, pts, r0=rng.uniform(13, 16), r1=3.0, sides=8, moss=0.35, squash=0.7, per_segment=2)
        b.add_geo("COL", "Root", g)

    # ---- stations (+Y of station space faces the hub centre)
    for sid, spec in cfg["stations"].items():
        a = deg(spec["angle"])
        radius = gate["radius"] if sid == "dungeon_gate" else spec["radius"]
        center = Vector((radius * math.cos(a), radius * math.sin(a), 0))
        facing = math.atan2(-center.y, -center.x) - math.pi / 2
        z = 0.0 if sid == "dungeon_gate" else height(center.x, center.y) - 0.2
        m = K.mat((center.x, center.y, z), facing)
        srng = K.rng_for(map_id, "station", sid)
        fn = MS.STATIONS[sid]
        parts, extra = fn(srng, lambda *p: b.geo("station", sid, *p), gate) if sid == "dungeon_gate" else \
            fn(srng, lambda *p: b.geo("station", sid, *p))
        for prefix, geos in parts.items():
            for k, g in enumerate(geos):
                base = f"Station_{camel(sid)}" + ("" if k == 0 else f"_{k + 1}")
                b.add_geo(prefix, base, g, matrix=m, numbered=False)
        mdist = gate["marker"] if sid == "dungeon_gate" else spec["marker"]
        mp = m @ Vector((0, mdist, 0))
        b.marker(f"MARKER_Station_{sid}", (mp.x, mp.y, height(mp.x, mp.y)))
        for mname, off in extra.items():
            p = m @ off
            b.marker(f"MARKER_{mname}", (p.x, p.y, p.z))
        b.block(center.x, center.y, spec.get("clear", 26))
        b.block(center.x, center.y, spec.get("clear", 26), deco=True)
        b.block(mp.x, mp.y, 10)
        b.block(mp.x, mp.y, 10, deco=True)

    # ---- shelf-fungus ledges (walkable climb route up the inner wall)
    rng = K.rng_for(map_id, "ledges")
    for i, (a, z, w, dpt, th_) in enumerate(cfg["ledges"]):
        th = deg(a)
        r = r_in(th, z) + 2.0
        pos = Vector((r * math.cos(th), r * math.sin(th), z))
        facing = math.atan2(-pos.y, -pos.x) - math.pi / 2
        g = b.geo("ledge", i)
        MP.shelf_fungus(g, rng, width=w, depth=dpt, thick=th_, embed=6.0)
        b.add_geo("COL", "Ledge", g, matrix=K.mat(pos, facing, 1.0, (deg(rng.uniform(2, 6)), 0)))
        for k in range(rng.randint(1, 2)):  # smaller brackets beside it
            off = rng.choice((-1, 1)) * (w * 0.5 + rng.uniform(4, 9))
            z2 = z + rng.uniform(-9, -3)
            th2 = th + off / r
            r2 = r_in(th2, z2) + 1.5
            p2 = Vector((r2 * math.cos(th2), r2 * math.sin(th2), z2))
            b.add_kit("PROP", "shelf_small", K.mat(p2, math.atan2(-p2.y, -p2.x) - math.pi / 2, rng.uniform(0.8, 1.2)),
                      variant=rng.randrange(2), base="ShelfFungus")

    # ---- silk: a walkable sheet web across part of the opening plus DECO strands
    web = cfg["web"]
    g = b.geo("sheet")
    anchors = []
    for a, z in web["anchors"]:
        th = deg(a)
        r = r_in(th, z) + 1.0
        anchors.append(Vector((r * math.cos(th), r * math.sin(th), z)))
    anchors += [Vector(p) for p in web["freeCorners"]]
    center = sum(anchors, Vector()) / len(anchors)
    center.z = sum(p.z for p in anchors) / len(anchors) - web["sag"]
    ring_t = (0.0, 0.3, 0.55, 0.8, 1.0)
    top_rings, bot_rings = [], []
    for ri, t in enumerate(ring_t):
        tr, br = [], []
        for p in anchors:
            q = center.lerp(p, t)
            q.z = K.lerp(center.z, p.z, t ** 1.6)
            c = K.mix(P["silk_shade"], P["silk"], 0.55 if ri % 2 else 0.15)
            tr.append(g.vert(q + Vector((0, 0, 0.5)), c))
            br.append(g.vert(q - Vector((0, 0, 0.5)), P["silk_shade"]))
        top_rings.append(tr)
        bot_rings.append(br)
    for ra, rb in zip(top_rings, top_rings[1:]):
        g.bridge(ra, rb)
    for ra, rb in zip(bot_rings, bot_rings[1:]):
        g.bridge(ra, rb)
    g.face(top_rings[0])
    g.face(list(reversed(bot_rings[0])))
    g.bridge(top_rings[-1], bot_rings[-1])
    sheet_lines = [(center.lerp(p, 0.05), p) for p in anchors]
    b.add_geo("COL", "SheetWeb", g, numbered=False)
    g = b.geo("strands")
    for p0, p1 in sheet_lines:  # radial threads over the sheet read as silk, not a tarp
        mids = [p0.lerp(p1, t) for t in (0.0, 0.33, 0.66, 1.0)]
        for q in mids:
            q.z = K.lerp(center.z, p1.z, (q - center).length / max(1e-3, (p1 - center).length)) + 0.75
        g.sweep(mids, 0.3, 3, lambda *a: P["silk"], caps=(False, False))
    for p in web["freeCorners"]:
        p = Vector(p)
        for a, z in web["cornerLines"]:
            th = deg(a)
            q = Vector((st["rIn"] * math.cos(th), st["rIn"] * math.sin(th), z))
            if (q - p).length < 170:
                g.strand(p, q, 0.35, P["silk"], sag=2.0, segments=3)
    for (a0, z0), (a1, z1) in web["spans"]:
        p0 = Vector((st["rIn"] * math.cos(deg(a0)), st["rIn"] * math.sin(deg(a0)), z0))
        p1 = Vector((st["rIn"] * math.cos(deg(a1)), st["rIn"] * math.sin(deg(a1)), z1))
        g.strand(p0, p1, 0.4, P["silk"], sag=9.0, segments=5)
    for x, y, z in web["dropLines"]:
        g.strand((x, y, z), (x, y, height(x, y) + 3), 0.35, P["silk"], segments=1)
        MP.dew(g, K.rng_for(map_id, "drop", x), radius=0.9, center=(x, y, height(x, y) + 1.6))
    b.add_geo("DECO", "Silk", g, numbered=False, occluder=False)

    # ---- markers: player spawns
    for i, (x, y) in enumerate(cfg["spawns"], start=1):
        b.marker(f"MARKER_PlayerSpawn_{i}", (x, y, height(x, y)))
        b.block(x, y, 6)

    # ---- scatter
    b.add_exclusions(cfg["exclude"])
    b.exclude.append(lambda px, py: not (st["rIn"] - 4 < math.hypot(px, py) < st["rOut"] + 22))

    fr = cfg["fairyRing"]
    rng = K.rng_for(map_id, "fairy")
    for k in range(fr["count"]):
        a = deg(fr["gapAngle"]) + deg(fr["gapWidth"]) / 2 + (TAU - deg(fr["gapWidth"])) * (k + 0.5) / fr["count"]
        r = fr["radius"] + rng.uniform(-2, 2)
        x, y = r * math.cos(a), r * math.sin(a)
        kit_id = rng.choice(fr["kit"])
        b.add_kit("PROP", kit_id, K.mat((x, y, height(x, y) - 0.4), rng.uniform(0, TAU), rng.uniform(*fr["scale"])),
                  variant=rng.randrange(KIT[kit_id]["variants"]))
        b.block(x, y, 5)
    for spec in cfg["scatter"]:
        b.scatter(spec)
    ring = cfg["ring"]
    rng = K.rng_for(map_id, "ring")
    for row, (r_row, spacing, kits, scale) in enumerate(ring["rows"]):
        n = int(TAU * r_row / spacing)
        for k in range(n):
            a = TAU * (k + 0.5 * row + rng.uniform(-0.3, 0.3)) / n
            r = r_row + rng.uniform(-ring["jitter"], ring["jitter"])
            x, y = r * math.cos(a), r * math.sin(a)
            kit_id = rng.choice(kits)
            tilt = ring.get("tilt", {}).get(kit_id, 0)
            b.add_kit("DECO" if kit_id.startswith(("grass", "leaf")) else "PROP", kit_id,
                      K.mat((x, y, height(x, y) - 0.5), a + math.pi / 2 + rng.uniform(-0.6, 0.6), rng.uniform(*scale),
                            (deg(rng.uniform(-tilt, tilt)), deg(rng.uniform(-tilt, tilt)))),
                      variant=rng.randrange(KIT[kit_id]["variants"]))
    g = b.geo("stalks")
    rng = K.rng_for(map_id, "stalks")
    for k in range(ring["stalks"]):
        a = TAU * (k + rng.uniform(0, 0.8)) / ring["stalks"]
        r = rng.uniform(*ring["stalkRadius"])
        x, y = r * math.cos(a), r * math.sin(a)
        MP.grass_stalk(g, rng, height=rng.uniform(*ring["stalkHeight"]), radius=rng.uniform(1.8, 2.6),
                       m=K.mat((x, y, height(x, y)), rng.uniform(0, TAU)),
                       lean=(rng.uniform(-0.15, 0.15), rng.uniform(-0.15, 0.15)))
    b.add_geo("DECO", "GrassStalks", g, numbered=False)
    yield map_id, b, coll


# ---------------------------------------------------------------- main menu: dusk diorama

def build_diorama(map_id, cfg, material):
    coll = K.collection(map_id)
    b = new_unit(map_id, map_id, coll, {}, material)
    gd = cfg["ground"]
    noise = K.Noise(map_id, "ground")
    dx0, dy0, dx1, dy1 = gd["detail"]
    by0, by1, bh = gd["bank"]

    def height(x, y):
        inside = K.smoothstep(0, 25, min(x - dx0, dx1 - x, y - dy0, dy1 - y))
        z = gd["noise"] * noise((x, y), 1 / 26, 2) * inside
        z += bh * K.smoothstep(by0, by1, y) * (1 - K.smoothstep(dx1 + 30, dx1 + 110, abs(x)))
        return z * (1 - K.smoothstep(150, 240, y))

    b.height = height

    def ground_color(x, y, z):
        n1, n2, n3 = noise((x, y), 1 / 22, 2), noise((x - 200, y), 1 / 11, 2), noise((x, y - 400), 1 / 5)
        c = K.mix(P["loam"], P["loam_light"], K.smoothstep(-0.4, 0.5, n3) * 0.6)
        c = K.mix(c, K.mix(P["moss_dark"], P["moss"], K.smoothstep(-0.3, 0.5, n3)), K.smoothstep(-0.2, 0.2, n1) * 0.85)
        c = K.mix(c, K.mix(P["leaf_brown"], P["leaf_orange"], K.smoothstep(-0.2, 0.5, n3)), K.smoothstep(0.15, 0.45, n2) * 0.6)
        far = K.smoothstep(40, 20, min(x - dx0, dx1 - x, y - dy0, dy1 - y))
        return K.mix(c, P["moss_dark"], far * 0.6)

    g = b.geo("ground")
    g.rect_heightfield(gd["xs"], gd["ys"], height, ground_color, -6.0)
    b.add_geo("COL", "Ground", g, numbered=False)

    # fallen hollow log (left, behind the menu UI): four closed quarter shells
    lg = cfg["log"]
    rng = K.rng_for(map_id, "log")
    lx, ly = lg["center"]
    m = K.mat((lx, ly, height(lx, ly) - 1.5), deg(lg["yaw"]))
    for g in MP.hollow_log(rng, lambda i: b.geo("log", i), length=lg["length"], radius=lg["radius"],
                           thickness=lg["thickness"], m=m):
        b.add_geo("COL", "Log", g)

    # root arch behind the web
    g = b.geo("root_arch")
    MP.root(g, K.rng_for(map_id, "arch"), [Vector(p) for p in cfg["rootArch"]], r0=8.0, r1=4.5, sides=8, moss=0.6)
    b.add_geo("COL", "RootArch", g, numbered=False)

    # the orb web between two grass stalks
    wb = cfg["web"]
    rng = K.rng_for(map_id, "web")
    stalk_tops = []
    for i, ((sx, sy), h, lean) in enumerate(wb["stalks"]):
        g = b.geo("stalk", i)
        MP.grass_stalk(g, rng, height=h, radius=1.9, m=K.mat((sx, sy, height(sx, sy))), lean=lean, head=True)
        b.add_geo("PROP", "WebStalk", g)
        stalk_tops.append(((sx, sy), h, lean))
        b.block(sx, sy, 4)

    def on_stalk(i, z):
        (sx, sy), h, (lx_, ly_) = stalk_tops[i]
        f = (z / h) ** 2
        return Vector((sx + lx_ * h * f, sy + ly_ * h * f, z + height(sx, sy)))

    wm = K.mat(wb["center"], deg(wb["yaw"]))
    wm_inv = wm.inverted()
    anchors = [on_stalk(i, z) for i, z in wb["anchors"]]
    gx, gy = wb["groundAnchor"]
    anchors.append(Vector((gx, gy, height(gx, gy) + 0.5)))
    local = []
    for k, p in enumerate(anchors):
        q = wm_inv @ p
        f = wb.get("frameScale", 0.64) * rng.uniform(0.9, 1.1)
        local.append((q.x * f, q.z * f, p))
    local.sort(key=lambda t: math.atan2(t[1], t[0]))
    g = b.geo("web")
    corners = MP.orb_web(g, rng, radius=wb["radius"], radials=wb["radials"], turns=wb["turns"], thread=0.17,
                         m=wm, frame=[(x, z) for x, z, _ in local], dew_count=wb["dew"])
    for c, (_, _, world) in zip(corners, local):
        g.strand(wm @ c, world, 0.2, P["silk"], sag=0.6, segments=2)
    b.add_geo("DECO", "OrbWeb", g, numbered=False, occluder=False)
    b.block(wb["center"][0], wb["center"][1], 8)

    # spider perch: a flat mossy stone right of centre
    pc = cfg["perch"]
    px, py = pc["xy"]
    g = b.geo("perch")
    MP.pebble(g, K.rng_for(map_id, "perch"), size=pc["size"], flat=pc["flat"], moss=0.8, tone="stone_warm")
    perch = b.add_geo("PROP", "SpiderPerch", g, matrix=K.mat((px, py, height(px, py)), deg(15)), numbered=False)
    b.block(px, py, pc["size"] * 0.6)

    # hero props
    for kit_id, x, y, s_, yaw in cfg["props"]:
        prefix = "DECO" if kit_id.startswith(("leaf", "grass", "clover")) else "PROP"
        b.add_kit(prefix, kit_id, K.mat((x, y, height(x, y) - 0.3 * s_), deg(yaw), s_))
        b.block(x, y, 6 * s_)

    # fireflies: perch points (Studio can hang a PointLight or particles on each). (x, y) pairs sit on
    # whatever solid is below; (x, y, z) triples are absolute.
    solids = [o for o in b.objects if not o.name.startswith(("MARKER", "DECO_OrbWeb"))]
    g_ff = []
    for i, pos in enumerate(cfg["fireflies"], start=1):
        x, y = pos[0], pos[1]
        z = pos[2] if len(pos) == 3 else b.drop(x, y, solids) + 0.5
        g = b.geo("firefly", i)
        g.ico((0, 0, 0), (0.7, 0.7, 0.55), 2, lambda n, co: K.mix(P["firefly"], P["amber"], 0.3 * max(0.0, -n.z)))
        g_ff.append(b.add_geo("DECO", "Firefly", g, matrix=K.mat((x, y, z)), occluder=False))

    # filler scatter
    b.add_exclusions(cfg["exclude"])
    for spec in cfg["scatter"]:
        b.scatter(spec)

    # backdrop: tall grass rows, stalks and a few giant mushrooms in the distance
    bd = cfg["backdrop"]
    rng = K.rng_for(map_id, "backdrop")
    for y_row, (x0, x1), spacing, kits, scale in bd["rows"]:
        x = x0
        while x <= x1:
            y = y_row + rng.uniform(-6, 6)
            kit_id = rng.choice(kits)
            b.add_kit("DECO", kit_id, K.mat((x, y, height(x, y) - 0.5), rng.uniform(0, TAU), rng.uniform(*scale)),
                      variant=rng.randrange(KIT[kit_id]["variants"]))
            x += spacing * rng.uniform(0.75, 1.25)
    g = b.geo("stalks")
    for k in range(bd["stalks"]):
        x, y = rng.uniform(*bd["stalkX"]), rng.uniform(*bd["stalkY"])
        MP.grass_stalk(g, rng, height=rng.uniform(*bd["stalkHeight"]), radius=rng.uniform(2.2, 3.2),
                       m=K.mat((x, y, height(x, y))), lean=(rng.uniform(-0.12, 0.12), rng.uniform(-0.1, 0.05)))
    b.add_geo("DECO", "GrassStalks", g, numbered=False)
    for kit_id, x, y, s_ in bd["giants"]:
        b.add_kit("DECO", kit_id, K.mat((x, y, height(x, y) - 1), rng.uniform(0, TAU), s_), base="Giant" + camel(kit_id))

    # markers
    cam = cfg["camera"]
    b.marker("MARKER_MenuCamera", cam["pos"])
    b.marker("MARKER_MenuFocus", cam["focus"])
    b.marker("MARKER_SpiderPose", (px, py, b.drop(px, py, [perch])))
    yield map_id, b, coll


# ---------------------------------------------------------------- Mossy Hollow: room kit

def edge_matrix(edge, W, D):
    """Edge-local (u along the edge, v = 0 on the boundary, room toward -v) -> room space."""
    return {
        "N": K.mat((0, D / 2, 0), 0.0),
        "S": K.mat((0, -D / 2, 0), math.pi),
        "E": K.mat((W / 2, 0, 0), -math.pi / 2),
        "W": K.mat((-W / 2, 0, 0), math.pi / 2),
    }[edge]


def door_arch(door, u):
    """Bottom of the lintel over a doorway (z of the opening's top edge at u)."""
    hw = door["halfWidth"]
    f = K.clamp(abs(u) / hw)
    return door["spring"] + (door["crown"] - door["spring"]) * math.sqrt(max(0.0, 1 - f * f))


def door_frame_geo(map_id, door):
    """Root tracing the doorway on the room side (edge-local, wall face at v = 0). Shared by every doorway."""
    g = K.Geo(map_id, "door_frame")
    rng = K.rng_for(map_id, "door_frame")
    r = door["frameRadius"]
    off = r + 1.2
    hw, sp, cr = door["halfWidth"] + off, door["spring"], door["crown"] + off - door["spring"]
    pts = [Vector((-hw - 1.5, -r * 0.35, -1.5)), Vector((-hw, -r * 0.4, sp * 0.5))]
    for k in range(9):
        phi = math.pi * (1 - k / 8)
        pts.append(Vector((hw * math.cos(phi), -r * 0.4, sp + cr * math.sin(phi))))
    pts += [Vector((hw, -r * 0.4, sp * 0.5)), Vector((hw + 2.5, -r * 0.35, -1.5))]
    MP.root(g, rng, pts, r0=r * 1.25, r1=r * 0.9, sides=7, moss=0.55, per_segment=1, wobble=0.08, squash=0.9)
    for side in (-1, 1):  # small tendrils creeping out from the jambs
        base = Vector((side * (hw + 1), -r * 0.4, sp + 2))
        MP.root(g, rng, [base, base + Vector((side * 5, -0.6, 4)), base + Vector((side * 9, 0.0, 3))], r0=1.2, r1=0.4,
                sides=5, per_segment=2, moss=0.3)
    return g


def build_room(b, cfg, rc, room_id, frame_mesh):
    grid, door, wall, fl = cfg["grid"], cfg["door"], cfg["wall"], cfg["floor"]
    W, D = rc["cells"][0] * grid, rc["cells"][1] * grid
    T = rc.get("thickness", wall["thickness"])
    b.footprint = (W, D)
    b.fit = (W, D)
    b.thickness = T
    noise = K.Noise(b.map_id, room_id, "floor")
    hw = door["halfWidth"]

    def height(x, y):
        edge_d = min(W / 2 - abs(x), D / 2 - abs(y))
        return fl["noise"] * noise((x, y), 1 / 18, 2) * K.smoothstep(fl["flat"], fl["fade"], edge_d)

    b.height = height

    def floor_color(x, y, z):
        n1, n2, n3 = noise((x, y), 1 / 20, 2), noise((x - 200, y), 1 / 9, 2), noise((x, y - 400), 1 / 5)
        c = K.mix(P["loam"], P["loam_light"], K.smoothstep(-0.4, 0.5, n3) * 0.7)
        c = K.mix(c, K.mix(P["moss_dark"], P["moss"], K.smoothstep(-0.3, 0.5, n3)), K.smoothstep(-0.15, 0.25, n1) * 0.8)
        return K.mix(c, K.mix(P["leaf_brown"], P["leaf_orange"], K.smoothstep(-0.2, 0.5, n3)), K.smoothstep(0.15, 0.45, n2) * 0.55)

    nx, ny = int(round(W / fl["step"])), int(round(D / fl["step"]))
    xs = [K.lerp(-W / 2, W / 2, i / nx) for i in range(nx + 1)]
    ys = [K.lerp(-D / 2, D / 2, j / ny) for j in range(ny + 1)]
    g = b.geo("floor")
    g.rect_heightfield(xs, ys, height, floor_color, -6.0)
    b.floor = b.add_geo("COL", "Floor", g, numbered=False)

    # ---- walls: per edge, jamb pieces + an arched lintel where there is a doorway
    b.wall_depth = {}
    b.wall_tops = []
    H0, H1 = rc["height"]
    for edge in "NESW":
        L = W if edge in "NS" else D
        m = edge_matrix(edge, W, D)
        has_door = edge in rc["doors"]
        en = K.Noise(b.map_id, room_id, "wall", edge)

        def top(u, en=en):
            return K.lerp(H0, H1, 0.5 + 0.5 * en((u * 0.018, 0, 3), 1.0)) + 2.5 * en((u * 0.09, 0, 7), 1.0)

        def depth(u, z, en=en, has_door=has_door, top=top):
            fade = K.smoothstep(hw, hw + 10, abs(u)) if has_door else 1.0
            n = en((u * 0.045, z * 0.05, 0), 1.0, 2)
            base = wall["noise"] * (0.5 + 0.5 * n)
            flare = wall["flare"] * math.exp(-max(z, 0.0) / 7.0)
            lip = wall["lip"] * K.smoothstep(top(u) - 10, top(u), z)
            return (base + flare + lip) * fade

        b.wall_depth[edge] = (lambda u, z, depth=depth: T + depth(u, z))

        def col_front(u, z, co, en=en, top=top):
            n = en((u * 0.03, z * 0.13, 11), 1.0)
            c = K.mix(P["loam"], P["loam_light"], K.smoothstep(-0.35, 0.4, n))
            c = K.mix(c, P["ant_earth_light"], K.smoothstep(0.3, 0.6, en((u * 0.06, z * 0.22, 20), 1.0)) * 0.45)
            c = K.mix(c, P["stone"], K.smoothstep(0.45, 0.7, en((u * 0.1, z * 0.1, 30), 1.0)) * 0.5)
            c = K.mix(c, P["moss_dark"], K.smoothstep(12, 0, z) * 0.45)
            c = K.mix(c, P["moss"], K.smoothstep(top(u) - 9, top(u) - 1, z) * 0.85)
            return c, 0.5

        def col_back(u, z, co):
            return P["loam"]

        def mid(u, en=en, top=top, depth=depth, m=m):
            z = top(u) + 2.0 + 1.5 * en((u * 0.12, 0, 40), 1.0)
            return m @ Vector((u, -T * 0.5 - depth(u, top(u)) * 0.4, z)), K.mix(P["moss"], P["moss_light"], 0.4), 0.8

        pieces = []
        if has_door:
            left = (-L / 2, -hw)
            right = (hw, L / 2)
            for a, b_ in (left, right):
                n = max(1, int(math.ceil((b_ - a) / wall["maxPiece"])))
                pieces += [(K.lerp(a, b_, k / n), K.lerp(a, b_, (k + 1) / n), "wall") for k in range(n)]
            pieces.append((-hw, hw, "lintel"))
        else:
            n = max(1, int(math.ceil(L / wall["maxPiece"])))
            pieces = [(K.lerp(-L / 2, L / 2, k / n), K.lerp(-L / 2, L / 2, (k + 1) / n), "wall") for k in range(n)]
        for u0, u1, kind in pieces:
            ncols = door["lintelColumns"] if kind == "lintel" else max(2, int(round((u1 - u0) / wall["colStep"])))
            us = [K.lerp(u0, u1, c / ncols) for c in range(ncols + 1)]
            bot = (lambda u: door_arch(door, u)) if kind == "lintel" else (lambda u: -2.0)
            g = b.geo("wall", edge, u0)
            g.thick_panel(us, wall["rows"],
                          lambda u, z, m=m, depth=depth: m @ Vector((u, -(T + depth(u, z)), z)),
                          lambda u, z, m=m: m @ Vector((u, 0.0, z)),
                          lambda u, bot=bot, top=top: (bot(u), top(u)),
                          lambda u, bot=bot, top=top: (bot(u), top(u)),
                          col_front, col_back, col_back, top_mid=mid)
            b.add_geo("COL", f"Wall{edge}", g)
            b.wall_tops += [top(u) for u in us]
        if has_door:
            obj = K.place(b.uname("COL", f"DoorFrame{edge}", False), frame_mesh, b.coll,
                          m @ Matrix.Translation((0, -T, 0)))
            b.objects.append(obj)
            dm = m @ Vector((0, 0, 0))
            b.marker(f"MARKER_Connector_{edge}", (round(dm.x, 6), round(dm.y, 6), 0.0))

    # ---- lid: BARRIER_Lid sits 1 stud under the lowest wall top, so nobody climbs over a wall and out
    lid = cfg["lid"]
    b.lid_z = min(b.wall_tops) - lid["gap"]
    b.interior_max = b.lid_z - lid["clearance"]  # climbable interior tops stay this far under the lid

    # ---- corner boulders (clipped to the footprint and kept under the lid)
    rng = K.rng_for(b.map_id, room_id, "corners")
    for k, (sx, sy) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1))):
        r = T + rng.uniform(6, 9)
        c = Vector((sx * (W / 2 - T * 0.5), sy * (D / 2 - T * 0.5), 0))
        g = b.geo("corner", k)
        cn = K.Noise(b.map_id, room_id, "corner", k)
        hz = rng.uniform(H0 * 0.55, H0 * 0.8)

        def clip(n, co, c=c, hz=hz):
            p = co + c
            p.x = max(-W / 2, min(W / 2, p.x))
            p.y = max(-D / 2, min(D / 2, p.y))
            p.z = min(max(-2.0, p.z), b.interior_max)
            return p - c

        g.ico(c + Vector((0, 0, hz * 0.5)), (r, r, hz * 0.75), 2,
              lambda n, co: (K.mix(P["stone"], P["stone_warm"], 0.5 + 0.5 * n.x), 0.8),
              displace=lambda n, cn=cn: 0.14 * cn(n, 1.5, 2), adjust=clip)
        b.add_geo("COL", "Corner", g)

    # ---- lanes: doorway -> centre capsules kept clear of solid props
    lanes = [((0.0, 0.0), tuple((edge_matrix(e, W, D) @ Vector((0, 0, 0))).xy)) for e in rc["doors"]]
    lanes += [tuple(l) for l in rc.get("lanes", ())]
    b.lanes = lanes
    lane_r = cfg["lane"]

    def off_lanes(x, y):
        for (x0, y0), (x1, y1) in lanes:
            dx, dy = x1 - x0, y1 - y0
            t = K.clamp(((x - x0) * dx + (y - y0) * dy) / max(1e-6, dx * dx + dy * dy))
            if (x - x0 - dx * t) ** 2 + (y - y0 - dy * t) ** 2 < lane_r * lane_r:
                return False
        return True

    b.off_lanes = off_lanes

    # ---- markers
    for i, (x, y) in enumerate(rc.get("spawns", ()), start=1):
        b.marker(f"MARKER_PlayerSpawn_{i}", (x, y, height(x, y)))
        b.block(x, y, 7)
        b.block(x, y, 5, deco=True)
    for i, (x, y) in enumerate(rc.get("enemies", ()), start=1):
        b.marker(f"MARKER_EnemySpawn_{i}", (x, y, height(x, y)))
        b.block(x, y, 7)
        b.block(x, y, 4, deco=True)
    if "boss" in rc:
        x, y = rc["boss"]
        b.marker("MARKER_BossSpawn", (x, y, height(x, y)))
        b.block(x, y, 24)
        b.block(x, y, 16, deco=True)
    if "extraction" in rc:
        x, y = rc["extraction"]
        b.marker("MARKER_Extraction", (x, y, height(x, y)))
        b.block(x, y, 12)
        b.block(x, y, 8, deco=True)

    # ---- features
    enemy_n = len(rc.get("enemies", ()))
    frng = K.rng_for(b.map_id, room_id, "features")
    for fi, f in enumerate(rc.get("features", ())):
        t = f["type"]
        if t == "ceilingRoot":
            g = b.geo("ceiling", fi)
            MP.root(g, frng, [Vector(p) for p in f["points"]], r0=f["r"][0], r1=f["r"][1], sides=7, moss=0.6)
            b.add_geo("COL", "CeilingRoot", g)
        elif t == "rootArch":
            (x0, y0), (x1, y1) = f["from"], f["to"]
            h = f["height"]
            a, c_ = Vector((x0, y0, -3)), Vector((x1, y1, -3))
            mid_ = (a + c_) * 0.5
            pts = [a, a.lerp(mid_, 0.35) + Vector((0, 0, h * 0.7)), mid_ + Vector((0, 0, h)),
                   c_.lerp(mid_, 0.35) + Vector((0, 0, h * 0.7)), c_]
            g = b.geo("arch", fi)
            MP.root(g, frng, pts, r0=f["r"][0], r1=f["r"][1], sides=7, moss=0.6)
            b.add_geo("COL", "RootArch", g)
            for x, y in ((x0, y0), (x1, y1)):
                b.block(x, y, f["r"][0] + 4)
        elif t == "pillar":
            x, y = f["at"]
            b.add_kit("PROP", "mushroom_pillar", K.mat((x, y, height(x, y) - 0.4), frng.uniform(0, TAU), f["scale"]),
                      variant=frng.randrange(KIT["mushroom_pillar"]["variants"]), base="MushroomPillar")
            b.block(x, y, 16 * f["scale"])
            b.block(x, y, 6, deco=True)
        elif t == "mushrooms":
            x, y = f["at"]
            for k in range(f["n"]):
                a, d = frng.uniform(0, TAU), (0 if k == 0 else frng.uniform(0.4, 1.0) * f["radius"])
                px, py = x + d * math.cos(a), y + d * math.sin(a)
                kit_id = frng.choice(f["kit"])
                s_ = frng.uniform(0.85, 1.15) * (1.0 if k == 0 else frng.uniform(0.55, 0.8))
                b.add_kit("PROP", kit_id, K.mat((px, py, height(px, py) - 0.3), frng.uniform(0, TAU), s_),
                          variant=frng.randrange(KIT[kit_id]["variants"]))
            b.block(x, y, f["radius"] + 5)
            b.block(x, y, f["radius"] + 2, deco=True)
        elif t == "stack":
            x, y = f["at"]
            z = height(x, y) - 1.0
            for k, s_ in enumerate(f["scales"]):
                kit_id = "pebble_big"
                var = frng.randrange(KIT[kit_id]["variants"])
                me = b.kit_mesh(kit_id, var)
                top_z = max(v.co.z for v in me.vertices) * s_
                jx, jy = (frng.uniform(-2, 2), frng.uniform(-2, 2)) if k else (0, 0)
                b.add_kit("PROP", kit_id, K.mat((x + jx, y + jy, z), frng.uniform(0, TAU), s_,
                                                (math.radians(frng.uniform(-8, 8)), math.radians(frng.uniform(-8, 8)))),
                          variant=var, base="PebbleStack")
                z += top_z * 0.78
            b.block(x, y, 14 * f["scales"][0])
            b.block(x, y, 10, deco=True)
        elif t == "ledge":
            e, u, z = f["edge"], f["u"], f["z"]
            w, dp, th = f["size"]
            m = edge_matrix(e, W, D)
            v = -b.wall_depth[e](u, z) + 2.0
            g = b.geo("ledge", fi)
            MP.shelf_fungus(g, frng, width=w, depth=dp, thick=th, embed=5.0)
            b.add_geo("COL", "Ledge", g, matrix=m @ K.mat((u, v, z), math.pi, 1.0, (math.radians(4), 0)))
        elif t == "log":
            x, y = f["center"]
            m = K.mat((x, y, f["z"]), math.radians(f["yaw"]))
            for g in MP.hollow_log(frng, lambda i, fi=fi: b.geo("log", fi, i), length=f["length"], radius=f["radius"],
                                   thickness=max(2.5, f["radius"] * 0.28), m=m):
                b.add_geo("COL", "Log", g)
        elif t == "leafCanopy":
            x, y, z = f["at"]
            g = b.geo("canopy", fi)
            L = f["length"]
            MP.leaf(g, frng, length=L, kind="oak", curl=f["curl"], thickness=1.6, tone="leaf_brown",
                    m=K.mat((x, y, z), math.radians(f["yaw"])) @ Matrix.Translation((0, -0.42 * L, 0)))
            b.add_geo("COL", "LeafCanopy", g)
        elif t == "silkDrop":
            x, y = f["at"]
            g = b.geo("drop", fi)
            g.strand((x, y, f["top"]), (x, y, height(x, y) + 3.2), 0.3, P["silk"])
            MP.dew(g, frng, radius=1.0, center=(x, y, height(x, y) + 1.4))
            b.add_geo("DECO", "SilkDrop", g, occluder=False)
        elif t == "tunnel":
            e, u, z, r = f["edge"], f["u"], f["z"], f["r"]
            m = edge_matrix(e, W, D)
            v = -b.wall_depth[e](u, z) + 1.0
            dpt = -v - 1.5
            g = b.geo("tunnel", fi)
            MP.tunnel_mouth(g, frng, radius=r, depth=dpt, collar=4.0,
                            m=m @ Matrix.Translation((u, v, z)) @ Matrix.Rotation(math.pi / 2, 4, "X"))
            b.add_geo("COL", "Tunnel", g)
            p = m @ Vector((u, v - 10, 0))
            enemy_n += 1
            b.marker(f"MARKER_EnemySpawn_{enemy_n}", (p.x, p.y, height(p.x, p.y)))
            b.block(p.x, p.y, r + 6)
        elif t == "eggs":
            x, y = f["at"]
            g = b.geo("eggs", fi)
            for k in range(f["n"]):
                a, d = frng.uniform(0, TAU), (0 if k == 0 else frng.uniform(0.4, 1.0) * f["radius"])
                MP.egg_sac(g, frng, size=frng.uniform(5, 7.5), glow=True,
                           m=K.mat((x + d * math.cos(a), y + d * math.sin(a), height(x, y) - 0.5), frng.uniform(0, TAU)))
            b.add_geo("PROP", "EggSacs", g)
            b.block(x, y, f["radius"] + 5)
        elif t == "amber":
            x, y = f["at"]
            g = b.geo("amber", fi)
            for k in range(f["n"]):
                a = TAU * k / f["n"] + frng.uniform(-0.3, 0.3)
                px, py = x + f["radius"] * math.cos(a), y + f["radius"] * math.sin(a)
                MS.amber_drop(g, (px, py, height(px, py) - 0.4), frng.uniform(1.0, 1.8))
            b.add_geo("DECO", "Amber", g, occluder=False)
        elif t == "glowBells":
            x, y = f["at"]
            g = b.geo("bells", fi)
            for k in range(f["n"]):
                a = TAU * (k + 0.5) / f["n"]
                px, py = x + f["radius"] * math.cos(a), y + f["radius"] * math.sin(a)
                MP.mushroom(g, frng, height=frng.uniform(7, 10), cap=frng.uniform(2.5, 3.2), shape="bell", tone="cream",
                            m=K.mat((px, py, height(px, py) - 0.3)))
            b.add_geo("DECO", "GlowBells", g)
        elif t == "web":
            x, y, z = f["at"]
            g = b.geo("web", fi)
            MP.orb_web(g, frng, radius=f["radius"], radials=12, turns=7, thread=0.16,
                       m=K.mat((x, y, z), math.radians(f["yaw"])), dew_count=6)
            b.add_geo("DECO", "OrbWeb", g, occluder=False)
        else:
            raise ValueError(f"unknown feature type {t}")

    if "chest" in rc:
        ch = rc["chest"]
        x, y = ch["at"]
        g = b.geo("dais")
        MP.stump_dais(g, frng, radius=ch["radius"], height=ch["height"])
        b.add_geo("COL", "ChestDais", g, matrix=K.mat((x, y, height(x, y))), numbered=False)
        b.marker("MARKER_Chest_1", (x, y, height(x, y) + ch["height"]))
        b.block(x, y, ch["radius"] + 6)
        b.block(x, y, ch["radius"] + 2, deco=True)

    if "nest" in rc:
        nc = rc["nest"]
        x, y = nc["at"]
        g = b.geo("nest")
        nm = K.mat((x, y, height(x, y) - 0.5))
        surface = MP.ant_nest(g, frng, radius=nc["radius"], height=nc["height"], crater=nc["crater"], m=nm)
        for a, z, r in nc["mouths"]:
            p, n = surface(math.radians(a), z)
            MP.tunnel_mouth(g, frng, radius=r, depth=12.0, collar=3.0,
                            m=nm @ Matrix.Translation(p - n * 1.0) @ MP._align_z(n))
        b.add_geo("COL", "AntNest", g, numbered=False)
        b.block(x, y, nc["radius"] + 6)
        b.block(x, y, nc["radius"] + 2, deco=True)

    # ---- keep every climbable interior piece under the lid: ceiling pieces drop, standing props shrink
    b.fitted = []
    for obj in list(b.objects):
        if not obj.name.startswith(("COL_", "PROP_")) or obj.name.startswith(("COL_Wall", "COL_Floor")):
            continue
        bpy.context.view_layer.update()
        lo, hi = K.world_bounds(obj)
        if hi.z <= b.interior_max:
            continue
        if lo.z > 8.0:  # hanging / spanning piece: lower it (its ends stay buried in the walls)
            obj.location.z -= hi.z - b.interior_max
            b.fitted.append((obj.name, "lowered", round(hi.z - b.interior_max, 2)))
        elif obj.data.get("kit"):  # standing kit prop: shrink uniformly about its base (its origin)
            base = obj.location.z
            f = (b.interior_max - base) / (hi.z - base)
            obj.scale *= f
            b.fitted.append((obj.name, "scaled", round(f, 3)))
        else:           # standing unique piece (origin at the room origin): squash its height only
            f = b.interior_max / hi.z
            obj.scale.z *= f
            b.fitted.append((obj.name, "squashed", round(f, 3)))
    if b.fitted:
        print(f"[map] {room_id}: fitted under the lid (z {b.interior_max:.1f}): {b.fitted}")
    b.barrier("Lid", K.box_corners((-W / 2, -D / 2, b.lid_z), (W / 2, D / 2, b.lid_z + lid["thickness"])),
              numbered=False)

    # ---- filler scatter inside the walls
    inset = T + 7
    area = ("rect", -W / 2 + inset, -D / 2 + inset, W / 2 - inset, D / 2 - inset)
    for spec in cfg["scatter"]:
        sp = dict(spec)
        sp["count"] = int(round(spec["count"] * rc.get("scatterScale", 1.0)))
        sp["area"] = area
        sp["name"] = f"{room_id}_{spec['name']}"
        if spec.get("lanes"):
            sp["accept"] = off_lanes
        if sp["count"] > 0:
            b.scatter(sp)


def check_room(b, cfg, rc, room_id):
    """Numerical checks that make rooms snap: connectors on the boundary, floor at z = 0 in every doorway,
    a clear 24 x 20 passage through every doorway, and nothing outside the footprint. Raises on failure."""
    from mathutils.bvhtree import BVHTree
    W, D = b.footprint
    door = cfg["door"]
    cw, ch = door["clear"]
    eps = 1e-3
    markers = {o.name: o.matrix_world.translation for o in b.objects if o.name.startswith("MARKER_")}
    # doorway passages must be clear of every solid, including invisible BARRIER_ collision
    solids = [o for o in b.objects if o.name.startswith(("COL_", "PROP_", "BARRIER_")) and o is not b.floor]
    verts, polys = [], []
    for obj in solids:
        base = len(verts)
        verts.extend(obj.matrix_world @ v.co for v in obj.data.vertices)
        polys.extend([base + i for i in p.vertices] for p in obj.data.polygons)
    bvh = BVHTree.FromPolygons(verts, polys)
    fverts = [b.floor.matrix_world @ v.co for v in b.floor.data.vertices]
    floor_bvh = BVHTree.FromPolygons(fverts, [list(p.vertices) for p in b.floor.data.polygons])
    report = {}
    for e in "NESW":
        name = f"MARKER_Connector_{e}"
        if e not in rc["doors"]:
            if name in markers:
                raise RuntimeError(f"[{room_id}] {name} without a doorway")
            continue
        pos = markers.get(name)
        want = {"N": (0, D / 2), "S": (0, -D / 2), "E": (W / 2, 0), "W": (-W / 2, 0)}[e]
        if pos is None or abs(pos.x - want[0]) > eps or abs(pos.y - want[1]) > eps or abs(pos.z) > eps:
            raise RuntimeError(f"[{room_id}] {name} at {pos}, expected {want} on the boundary at z = 0")
        m = edge_matrix(e, W, D)
        depth = b.thickness + 12.0
        # floor under the doorway is at z = 0 across the opening
        for u in (-cw / 2, 0.0, cw / 2):
            for v in (-0.5, -b.thickness * 0.5, -b.thickness):
                p = m @ Vector((u, v, 5.0))
                hit = floor_bvh.ray_cast(p, Vector((0, 0, -1)), 20.0)
                if hit[0] is None or abs(hit[0].z) > 0.05:
                    raise RuntimeError(f"[{room_id}] floor under doorway {e} at u={u} v={v} is {hit[0]}")
        # horizontal rays through the passage and vertical rays down through it
        blocked = []
        for iu in range(13):
            u = -cw / 2 + cw * iu / 12
            for iz in range(9):
                z = 0.3 + (ch - 0.3) * iz / 8
                o = m @ Vector((u, 0.5, z))
                d = (m.to_3x3() @ Vector((0, -1, 0))).normalized()
                hit = bvh.ray_cast(o, d, depth + 0.5)
                if hit[0] is not None:
                    blocked.append(("h", round(u, 1), round(z, 1), round(hit[3], 2)))
            for iv in range(8):
                v = -depth * iv / 7
                o = m @ Vector((u, v, ch))
                hit = bvh.ray_cast(o, Vector((0, 0, -1)), ch - 0.3)
                if hit[0] is not None:
                    blocked.append(("v", round(u, 1), round(v, 1), round(hit[3], 2)))
        # any vertex inside the clear box
        inv = m.inverted()
        inside = 0
        for p in verts:
            q = inv @ p
            if abs(q.x) < cw / 2 and 0.3 < q.z < ch and -depth < q.y < 0.0:
                inside += 1
        if blocked or inside:
            raise RuntimeError(f"[{room_id}] doorway {e} not clear: {len(blocked)} rays blocked {blocked[:4]}, "
                               f"{inside} vertices inside the {cw}x{ch} box")
        # measured opening: widest clear half-width at floor and clear height at centre
        o = m @ Vector((0, -b.thickness * 0.5, 1.0))
        side = (m.to_3x3() @ Vector((1, 0, 0))).normalized()
        wr = bvh.ray_cast(o, side, 100)[3] or 0
        wl = bvh.ray_cast(o, -side, 100)[3] or 0
        hh = bvh.ray_cast(m @ Vector((0, -b.thickness * 0.5, 0.3)), Vector((0, 0, 1)), 200)[3] or 0
        report[e] = {"connector": [round(pos.x, 4), round(pos.y, 4), round(pos.z, 4)],
                     "openingWidth": round(wl + wr, 2), "openingHeight": round(hh + 0.3, 2)}
    for obj in b.objects:
        if obj.name.startswith("MARKER_"):
            q = obj.matrix_world.translation
            if abs(q.x) > W / 2 + eps or abs(q.y) > D / 2 + eps:
                raise RuntimeError(f"[{room_id}] {obj.name} outside the footprint")
            continue
        lo, hi = K.world_bounds(obj)
        if lo.x < -W / 2 - eps or hi.x > W / 2 + eps or lo.y < -D / 2 - eps or hi.y > D / 2 + eps:
            raise RuntimeError(f"[{room_id}] {obj.name} leaves the {W}x{D} footprint: {tuple(lo)} {tuple(hi)}")
    # the lid covers the whole footprint 1 stud under the lowest wall top, and nothing climbable pokes above it
    lid = [o for o in b.objects if o.name == "BARRIER_Lid"]
    if len(lid) != 1:
        raise RuntimeError(f"[{room_id}] needs exactly one BARRIER_Lid")
    lo, hi = K.world_bounds(lid[0])
    if abs(lo.x + W / 2) > eps or abs(hi.x - W / 2) > eps or abs(lo.y + D / 2) > eps or abs(hi.y - D / 2) > eps:
        raise RuntimeError(f"[{room_id}] BARRIER_Lid does not cover the {W}x{D} footprint")
    if abs(lo.z - (min(b.wall_tops) - cfg["lid"]["gap"])) > eps:
        raise RuntimeError(f"[{room_id}] BARRIER_Lid underside {lo.z} is not {cfg['lid']['gap']} under the lowest wall top")
    for obj in b.objects:
        if obj.name.startswith(("COL_", "PROP_")) and not obj.name.startswith(("COL_Wall", "COL_Floor")):
            top_z = K.world_bounds(obj)[1].z
            if top_z > lo.z - cfg["lid"]["clearance"] + eps:
                raise RuntimeError(f"[{room_id}] {obj.name} reaches z {top_z:.2f}, above the lid clearance "
                                   f"({lo.z - cfg['lid']['clearance']:.2f})")
    print(f"[map] {room_id}: doorways OK {report}; lid at z {lo.z:.2f}")
    return {"doorways": report,
            "lid": {"underside": round(lo.z, 3), "top": round(hi.z, 3), "clearance": cfg["lid"]["clearance"],
                    "lowestWallTop": round(min(b.wall_tops), 3), "fitted": [list(f) for f in b.fitted]}}


def build_rooms(map_id, cfg, material):
    kit_cache = {}
    frame_geo = door_frame_geo(map_id, cfg["door"])
    frame_mesh = K.mesh_from_geo(frame_geo, "mossy_door_frame", material, sharp_angle=SHADING["sharpAngle"])
    parent = K.collection(map_id)
    for room_id, rc in cfg["rooms"].items():  # one room at a time: names are reused across rooms
        coll = K.collection(room_id, parent)
        b = new_unit(map_id, room_id, coll, kit_cache, material)
        build_room(b, cfg, rc, room_id, frame_mesh)
        b.checks = [lambda b=b, rc=rc, room_id=room_id: check_room(b, cfg, rc, room_id)]
        b.layout = rc["layout"]
        yield room_id, b, coll


BUILDERS = {"hub": build_lobby, "diorama": build_diorama, "rooms": build_rooms}


# ---------------------------------------------------------------- main

def main():
    args = parse_args()
    cfg = MAPS[args.map]
    K.reset_scene()
    material = K.vertex_color_material(f"{args.map}_VertexColor")
    units = BUILDERS[cfg["kind"]](args.map, cfg, material)
    shading = shading_for(cfg)
    exports = os.path.join(K.BLENDER_DIR, "exports", "maps")
    sources = os.path.join(K.BLENDER_DIR, "sources", "maps")
    os.makedirs(sources, exist_ok=True)
    reports = {}
    done = []
    for unit_id, b, coll in units:
        budget = cfg["budget"] if cfg["kind"] != "rooms" else cfg["rooms"][unit_id]["budget"]
        total = b.finish(budget, shading, args.draft)
        checks = {}
        for check in getattr(b, "checks", ()):
            checks = check()
        if cfg["kind"] != "rooms":
            fbx = os.path.join(exports, f"{args.map}.fbx")
            man = os.path.join(exports, f"{args.map}.manifest.json")
        else:
            fbx = os.path.join(exports, args.map, f"{unit_id}.fbx")
            man = None
        if not (args.no_export or args.draft):
            K.export_fbx(fbx, b.objects)
        reports[unit_id] = K.manifest(unit_id, b.objects, budget, fbx)
        if cfg["kind"] == "rooms":
            W, D = b.footprint
            reports[unit_id].update({"cells": list(cfg["rooms"][unit_id]["cells"]), "footprint": [W, D],
                                     "doors": list(cfg["rooms"][unit_id]["doors"]), **checks})
        if cfg["kind"] == "diorama":
            reports[unit_id]["menuCamera"] = {"fieldOfView": cfg["camera"]["fov"],
                                              "note": "CFrame.lookAt(MenuCamera, MenuFocus); UI covers the left third"}
        if man and not args.draft:
            K.write_json(man, dict(reports[unit_id], map=args.map))
        print(f"[map] {unit_id}: {total} tris")
        if cfg["kind"] == "rooms":  # free the clean names for the next room (the FBX is already written)
            for obj in b.objects:
                obj.name = f"{obj.name}.{unit_id}"
        done.append((unit_id, b, coll))
    if cfg["kind"] == "rooms":
        if not args.draft:
            door = cfg["door"]
            K.write_json(os.path.join(exports, args.map, "manifest.json"), {
                "map": args.map, "grid": cfg["grid"],
                "door": {"clearWidth": door["clear"][0], "clearHeight": door["clear"][1],
                         "openingWidth": 2 * door["halfWidth"], "springHeight": door["spring"],
                         "crownHeight": door["crown"],
                         "rule": "connector = doorway centre on the floor, exactly on the room boundary"},
                "rooms": reports})
        for unit_id, b, coll in done:  # spread rooms out for previewing (exports are at the origin)
            off = Vector((*b.layout, 0))
            for obj in b.objects:
                obj.location += off
            coll["layoutOffset"] = list(b.layout)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(sources, f"{args.map}.blend"), compress=True)
    print(f"[map] saved sources/maps/{args.map}.blend")


if __name__ == "__main__":
    main()
