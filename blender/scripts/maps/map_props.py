"""Procedural, seeded, low-tri prop generators for Spider Quest maps.

Every generator writes into a map_kit.Geo in local space (origin at the prop's base, Z up) and takes
a placement matrix `m`. Base colours come from map_config.PALETTE; light, occlusion, moss and jitter
are baked later by map_kit.bake_colors. Every solid is closed so Roblox can build collision from it.
"""

import math

import bpy  # noqa: F401  (import order: bpy before bmesh/mathutils users)
from mathutils import Matrix, Vector

from map_config import PALETTE as P
from map_kit import IDENTITY, TAU, UP, Noise, clamp, lerp, mix, smooth_path, smoothstep


def _pick(rng, value):
    """(lo, hi) -> seeded float in range; anything else passes through."""
    if isinstance(value, tuple) and len(value) == 2 and all(isinstance(x, (int, float)) for x in value):
        return rng.uniform(*value)
    return value


def resolve(rng, params):
    return {k: _pick(rng, v) for k, v in params.items()}


def _align_z(direction):
    """Rotation matrix taking +Z to direction."""
    return Vector(direction).normalized().to_track_quat("Z", "Y").to_matrix().to_4x4()


# ---------------------------------------------------------------- small shared pieces

def wart(g, center, normal, radius, height, color, m=IDENTITY, sides=5):
    """Low closed pyramid sitting on a surface (mushroom spots, bumps)."""
    n = Vector(normal).normalized()
    rot = _align_z(n)
    base = []
    for k in range(sides):
        a = TAU * k / sides
        co = Vector(center) + rot @ Vector((radius * math.cos(a), radius * math.sin(a), -height * 0.4))
        base.append(g.vert(m @ co, color))
    tip = g.vert(m @ (Vector(center) + n * height), color)
    for k in range(sides):
        g.face((base[k], base[(k + 1) % sides], tip))
    g.face(list(reversed(base)))


def dew(g, rng, radius=1.2, center=(0, 0, 0), m=IDENTITY, subdiv=2):
    """Dew drop: squat low ico, bright top highlight, pale body."""
    def color(n, co):
        if n.z > 0.55:
            return P["dew_hi"]
        return mix(P["dew"], P["dew_hi"], clamp(-n.z) * 0.45)
    c = Vector(center) + Vector((0, 0, radius * 0.8))
    g.ico(c, (radius, radius, radius * 0.85), subdiv, color, m=m)


# ---------------------------------------------------------------- fungi

CAP_PROFILES = {  # (r, z) in cap units: r * cap radius, z * cap thickness. Top pole -> rim -> underside pole.
    "dome": ((0, 1.0), (0.42, 0.94), (0.74, 0.70), (0.94, 0.34), (1.0, 0.08), (0.88, -0.03), (0.56, 0.07), (0.2, 0.05), (0, 0.06)),
    "flat": ((0, 0.72), (0.48, 0.76), (0.82, 0.62), (1.0, 0.44), (1.03, 0.28), (0.9, 0.16), (0.52, 0.05), (0.2, 0.0), (0, 0.02)),
    "bell": ((0, 1.0), (0.26, 0.96), (0.56, 0.78), (0.82, 0.42), (1.0, 0.02), (0.9, -0.02), (0.52, 0.18), (0.2, 0.12), (0, 0.12)),
}
CAP_THICKNESS = {"dome": 0.62, "flat": 0.34, "bell": 1.05}
CAP_TONES = {  # centre, body, rim
    "rust": ("mush_brown", "mush_rust", "mush_tan"),
    "red": ("mush_red", "mush_red", "mush_rust"),
    "tan": ("mush_brown", "mush_tan", "mush_cream"),
    "brown": ("bark_dark", "mush_brown", "mush_tan"),
    "cream": ("mush_tan", "mush_cream", "mush_cream"),
}


def mushroom(g, rng, height=18.0, cap=8.0, shape="dome", tone="rust", spots=False, lean=0.12, m=IDENTITY,
             segments=9, stem_sides=6):
    th = cap * CAP_THICKNESS[shape]
    stem_r = cap * rng.uniform(0.17, 0.23)
    heading = rng.uniform(0, TAU)
    lean_v = Vector((math.cos(heading), math.sin(heading), 0)) * (lean * height * rng.uniform(0.5, 1.0))
    cap_base = Vector((0, 0, height - th * 0.85)) + lean_v
    pts = []
    for s in range(5):
        t = s / 4
        pts.append(Vector((0, 0, lerp(-1.5, cap_base.z, t))) + lean_v * (t * t))
    tangent = (pts[-1] - pts[-2]).normalized()
    pts.append(pts[-1] + tangent * th * 0.45)  # into the cap so no gap shows

    def stem_color(t, a, co, off):
        c = mix(P["mush_stem"], P["loam_light"], (1 - t) ** 4 * 0.9)
        return mix(c, P["gill_dark"], 0.25 * (1 - off.z) * 0.5)

    g.sweep(pts, [stem_r * 1.45, stem_r * 1.08, stem_r * 0.98, stem_r * 0.92, stem_r * 0.88, stem_r * 0.85],
            stem_sides, stem_color, m=m)

    prof = [(r * cap, z * th) for r, z in CAP_PROFILES[shape]]
    rim_index = 4
    c_center, c_body, c_rim = (P[k] for k in CAP_TONES[tone])
    wav_phase = rng.uniform(0, TAU)
    wav_n = rng.choice((3, 4, 5))
    cap_m = m @ Matrix.Translation(cap_base) @ _align_z(Vector((0, 0, 1)).lerp(tangent, 0.6))

    def cap_color(i, t, a, co):
        if i > rim_index:  # gills: alternate light and dark by segment for radial lines
            k = int(round((a % TAU) / TAU * segments)) % segments
            return P["gill"] if k % 2 == 0 else P["gill_dark"]
        f = i / rim_index
        c = mix(c_center, c_body, smoothstep(0.0, 0.6, f))
        return mix(c, c_rim, smoothstep(0.65, 1.0, f) * 0.85)

    def cap_adjust(i, t, a, co):
        if a is None:
            return co
        w = 1.0 + 0.05 * math.sin(wav_n * a + wav_phase) + rng.uniform(-0.025, 0.025)
        dz = 0.05 * th * math.sin(wav_n * a + wav_phase + 1.0) if i >= 3 else 0.0
        return Vector((co.x * w, co.y * w, co.z + dz))

    g.lathe(prof, segments, cap_color, m=cap_m, adjust=cap_adjust, phase=rng.uniform(0, 1))

    if spots:
        for _ in range(rng.randint(6, 9)):
            seg = rng.uniform(0.6, 3.2)
            i = int(seg)
            f = seg - i
            (r0, z0), (r1, z1) = prof[i], prof[i + 1]
            r, z = lerp(r0, r1, f), lerp(z0, z1, f)
            a = rng.uniform(0, TAU)
            dr, dz = r1 - r0, z1 - z0
            nr, nz = dz, -dr  # outward normal in the (r, z) plane for a top-down profile
            if nz < 0:
                nr, nz = -nr, -nz
            ln = math.hypot(nr, nz) or 1.0
            normal = Vector((nr / ln * math.cos(a), nr / ln * math.sin(a), nz / ln))
            pos = Vector((r * math.cos(a), r * math.sin(a), z)) + normal * 0.1
            wart(g, pos, normal, cap * rng.uniform(0.07, 0.11), cap * 0.05, P["mush_cream"], m=cap_m)


def shelf_fungus(g, rng, width=40.0, depth=26.0, thick=9.0, m=IDENTITY, segments=12, rings=8, embed=4.0):
    """Bracket fungus: protrudes along +Y from a wall plane at y = 0, back embedded into the wall."""
    bands = P["shelf_band"]
    noise = Noise("shelf", rng.random())
    band_shift = rng.uniform(0, 3)

    prof = []
    for i in range(rings + 1):
        phi = math.pi * i / rings
        prof.append((math.sin(phi), math.cos(phi)))

    def adjust(i, t, a, co):
        x, y, z = co.x, co.y, co.z
        fy = max(y, 0.0)
        wob = 1.0 + 0.08 * noise((x * 2, y * 2, 0), 1.3)
        px = x * width * 0.5 * wob
        py = (y * depth * wob) if y >= 0 else (y * embed)
        taper = 1.0 - 0.62 * fy * fy
        pz = z * thick * 0.5 * taper * (0.55 if z < 0 else 1.0)
        pz -= thick * 0.25 * fy * fy  # front droops a little
        return Vector((px, py, pz))

    equator = rings // 2
    start = rng.randrange(len(bands))

    def color(i, t, a, co):
        if i > equator:
            return P["shelf_under"]
        if i == equator:
            return P["shelf_edge"]
        c = bands[(start + i) % len(bands)]
        return mix(c, P["bark_dark"], 0.35 if i == 0 else 0.0), 0.3 if i <= 1 else 0.0

    g.lathe(prof, segments, color, m=m, adjust=adjust, phase=0.5 * TAU / segments)


# ---------------------------------------------------------------- stones, nuts, sticks

STONE_TONES = ("stone", "stone_warm", "stone_cool", "stone")


def pebble(g, rng, size=8.0, flat=0.6, m=IDENTITY, subdiv=2, moss=0.45, tone=None):
    rx = size * 0.5 * rng.uniform(0.9, 1.15)
    ry = size * 0.5 * rng.uniform(0.72, 0.95)
    rz = size * 0.5 * flat
    noise = Noise("pebble", rng.random())
    base = P[tone or rng.choice(STONE_TONES)]
    sink = rz * 0.3

    def displace(n):
        return 0.16 * noise(n, 1.4, 2)

    def adjust(n, co):
        return Vector((co.x, co.y, max(co.z, -rz * 0.45) + rz * 0.45 - sink))

    def color(n, co):
        c = mix(base, P["stone_dark"], clamp(-n.z) * 0.5)
        lich = noise(n * 3.0, 1.0)
        if lich > 0.25:
            c = mix(c, P["lichen"], 0.55)
        return c, moss

    g.ico((0, 0, 0), (rx, ry, rz), subdiv, color, m=m, displace=displace, adjust=adjust)


def acorn(g, rng, length=10.0, m=IDENTITY, lying=True):
    R = length * 0.34
    L = length
    if lying:
        m = m @ Matrix.Translation((0, 0, R * 0.92)) @ Matrix.Rotation(math.radians(rng.uniform(80, 100)), 4, "Y") \
            @ Matrix.Translation((0, 0, -L * 0.55))
    nut = [(0, 0), (0.22 * R, 0.05 * L), (0.62 * R, 0.19 * L), (0.9 * R, 0.38 * L), (R, 0.56 * L),
           (0.96 * R, 0.7 * L), (0.7 * R, 0.8 * L), (0, 0.82 * L)]

    def nut_color(i, t, a, co):
        stripe = 0.1 if int((a % TAU) / TAU * 16) % 2 else 0.0
        c = mix(P["acorn"], P["acorn_dark"], 0.35 if i <= 1 else stripe)
        return mix(c, P["acorn_dark"], 0.6) if i == 0 else c

    g.lathe(nut, 7, nut_color, m=m)
    acorn_cap(g, rng, radius=R * 1.1, m=m @ Matrix.Translation((0, 0, 0.64 * L)), stalk=True, segments=8)


def acorn_cap(g, rng, radius=4.6, m=IDENTITY, stalk=True, upside_down=False, segments=10):
    """Scaly cup. Upright: cup opens downward (on a nut). upside_down: lying on the ground as a bowl."""
    R = radius
    if upside_down:
        m = m @ Matrix.Translation((0, 0, R * 0.95)) @ Matrix.Rotation(math.pi, 4, "X")
    prof = []
    if stalk:
        prof += [(0, 1.25 * R), (0.14 * R, 1.22 * R), (0.16 * R, 0.95 * R)]
    else:
        prof += [(0, 0.95 * R)]
    prof += [(0.55 * R, 0.86 * R), (0.88 * R, 0.62 * R), (1.02 * R, 0.3 * R), (1.0 * R, 0.0),
             (0.86 * R, 0.02 * R), (0.7 * R, 0.3 * R), (0, 0.55 * R)]
    lip = len(prof) - 4

    def color(i, t, a, co):
        if i > lip:
            return P["acorn_cap_dark"]
        k = int((a % TAU) / TAU * segments)
        return P["acorn_cap"] if (k + i) % 2 else mix(P["acorn_cap"], P["acorn_cap_dark"], 0.6)

    def adjust(i, t, a, co):
        if a is None or i > lip:
            return co
        k = int(round((a % TAU) / TAU * segments))
        bump = 1.06 if (k + i) % 2 else 0.97
        return Vector((co.x * bump, co.y * bump, co.z))

    g.lathe(prof, segments, color, m=m, adjust=adjust)


def twig(g, rng, length=40.0, radius=1.6, m=IDENTITY, branches=2):
    noise = Noise("twig", rng.random())
    ctrl = []
    for s in range(6):
        t = s / 5
        x = lerp(-length / 2, length / 2, t)
        ctrl.append(Vector((x, noise((t * 3, 0, 0)) * length * 0.08, radius * 0.75 + max(0, noise((t * 2, 5, 0))) * 1.5)))
    pts = smooth_path(ctrl, 2)

    def color(t, a, co, off):
        c = P["bark"] if int(t * 9) % 2 else mix(P["bark"], P["bark_light"], 0.4)
        return c, 0.35

    g.sweep(pts, lambda t: radius * lerp(1.0, 0.65, t), 5, color, m=m)
    for b in range(branches):
        t0 = rng.uniform(0.25, 0.7)
        i = int(t0 * (len(pts) - 1))
        start = pts[i]
        side = rng.choice((-1, 1))
        ang = math.radians(rng.uniform(25, 50)) * side
        d = Vector((math.cos(ang), math.sin(ang), 0.05))
        blen = length * rng.uniform(0.2, 0.35)
        bp = [start, start + d * blen * 0.5 + Vector((0, 0, 0.3)), start + d * blen]
        g.sweep(bp, lambda t: radius * lerp(0.6, 0.3, t), 4, color, m=m, caps=(False, True))


def leaf(g, rng, length=40.0, kind="oak", curl=0.25, m=IDENTITY, stations=None, thickness=0.7, tone=None):
    """Fallen leaf lying along +Y, lens-shaped cross-section (closed), lobed outline for oak."""
    W = length * (0.34 if kind == "oak" else 0.3)
    stations = stations or (15 if kind == "oak" else 10)
    lobes = rng.choice((4, 5))
    phase = rng.uniform(-0.3, 0.3)
    base_c = P[tone or rng.choice(("leaf_brown", "leaf_orange", "leaf_dry", "leaf_brown", "leaf_red", "leaf_green"))]
    twist = rng.uniform(-0.15, 0.15)
    lift = rng.uniform(0.6, 2.5)

    def half_width(t):
        w = W * math.sin(math.pi * clamp(t * 0.96 + 0.02)) ** 0.75
        if kind == "oak":  # rounded lobes with sharp sinuses
            lobe = abs(math.cos(math.pi * (lobes * t + phase))) ** 0.6
            w *= lerp(1.0, 0.62 + 0.38 * lobe, smoothstep(0.08, 0.3, t))
        return max(w, W * 0.06)

    rows = []
    for s in range(stations):
        t = s / stations
        y = t * length
        w = half_width(t)
        cz = curl * w * 0.9
        droop = lift * math.sin(math.pi * t) + (0.0 if t < 0.8 else -(t - 0.8) * 4)
        tw = twist * (t - 0.5)
        rib = 0.35 * (1 - t)
        left = Vector((-w, y, cz + tw * w + droop))
        right = Vector((w, y, cz - tw * w + droop))
        top = Vector((0, y, droop + thickness * 0.5 + rib))
        bot = Vector((0, y, droop - thickness * 0.5))
        edge_c = mix(base_c, P["leaf_dry"], 0.35)
        rows.append((g.vert(m @ left, mix(edge_c, P["bark_dark"], 0.15)), g.vert(m @ top, mix(base_c, P["leaf_dry"], 0.25)),
                     g.vert(m @ right, edge_c), g.vert(m @ bot, mix(base_c, P["leaf_dry"], 0.4))))
    tip = g.vert(m @ Vector((0, length, -0.6)), mix(base_c, P["bark_dark"], 0.3))
    for (l0, t0, r0, b0), (l1, t1, r1, b1) in zip(rows, rows[1:]):
        g.face((l0, l1, t1, t0))
        g.face((t0, t1, r1, r0))
        g.face((r0, r1, b1, b0))
        g.face((b0, b1, l1, l0))
    l, t, r, b = rows[-1]
    for a, c in ((l, t), (t, r), (r, b), (b, l)):
        g.face((a, tip, c))
    l, t, r, b = rows[0]
    g.face((l, t, r, b))
    stem = [Vector((0, 0, 0.3 + lift * 0)), Vector((0, -length * 0.1, 0.4)), Vector((0.3, -length * 0.16, 0.2))]
    g.sweep(stem, [0.45, 0.4, 0.3], 4, lambda *a: P["bark"], m=m)


def grass_clump(g, rng, height=35.0, blades=8, spread=3.5, m=IDENTITY, tone=None):
    for b in range(int(blades)):
        a = TAU * b / blades + rng.uniform(-0.3, 0.3)
        out = Vector((math.cos(a), math.sin(a), 0))
        base = out * rng.uniform(0.2, 1.0) * spread
        h = height * rng.uniform(0.6, 1.0)
        lean = rng.uniform(0.15, 0.45)
        w = max(0.9, h * rng.uniform(0.04, 0.055))
        pts = []
        for s in range(4):
            t = s / 3
            pts.append(base + out * (lean * h * t * t) + UP * (h * t * (1 - 0.12 * t * t)) - UP * 1.0 * (1 - t))
        tip_dry = rng.uniform(0.3, 0.9)

        def color(t, ang, co, off, tip_dry=tip_dry):
            c = mix(P["grass_dark"], P["grass"], smoothstep(0.0, 0.5, t))
            return mix(c, P["grass_tip"], smoothstep(0.55, 1.0, t) * tip_dry)

        g.sweep(pts, [w, w * 0.92, w * 0.6, 0.0], 3, color, m=m, squash=0.32, up_hint=out, caps=(True, False))


def grass_stalk(g, rng, height=60.0, radius=1.4, m=IDENTITY, lean=(0.0, 0.0), head=True):
    """Single tall grass stem with an optional seed head (web anchor, background silhouette)."""
    lx, ly = lean
    pts = [Vector((lx * height * (s / 5) ** 2, ly * height * (s / 5) ** 2, -1.0 + (height + 1.0) * s / 5)) for s in range(6)]

    def color(t, a, co, off):
        return mix(P["grass_dark"], mix(P["grass"], P["grass_tip"], 0.5), t)

    g.sweep(pts, lambda t: radius * lerp(1.0, 0.55, t), 5, color, m=m)
    for k in range(2):  # a pair of long leaves from the base
        a = rng.uniform(0, TAU)
        out = Vector((math.cos(a), math.sin(a), 0))
        h = height * rng.uniform(0.35, 0.55)
        lp = [out * 0.5 + UP * (-1 + (h + 1) * s / 3) + out * (0.4 * h * (s / 3) ** 2) for s in range(4)]
        g.sweep(lp, [radius * 1.6, radius * 1.4, radius * 0.8, 0.0], 3,
                lambda t, a_, co, off: mix(P["grass_dark"], P["grass"], t), m=m, squash=0.3, up_hint=out,
                caps=(True, False))
    if head:
        top = pts[-1]
        d = (pts[-1] - pts[-2]).normalized()
        hp = [top - d * 1.0, top + d * height * 0.05, top + d * height * 0.11, top + d * height * 0.15]
        g.sweep(hp, [radius * 0.9, radius * 2.2, radius * 1.8, 0.0], 6,
                lambda t, a, co, off: mix(P["grass_tip"], P["leaf_dry"], t), m=m, caps=(True, False))


def moss_mound(g, rng, radius=10.0, height=4.0, m=IDENTITY, segments=9):
    noise = Noise("mound", rng.random())
    prof = [(0, height), (0.45, height * 0.92), (0.8, height * 0.58), (1.0, height * 0.18), (1.05, -0.6), (0, -0.6)]
    prof = [(r * radius, z) for r, z in prof]

    def adjust(i, t, a, co):
        if a is None:
            return co
        w = 1.0 + 0.18 * noise((math.cos(a) * 1.5, math.sin(a) * 1.5, i * 0.3), 1.0)
        return Vector((co.x * w, co.y * w, co.z * (1 + 0.25 * noise((co.x * 0.3, co.y * 0.3, 2), 1.0)) if co.z > 0 else co.z))

    def color(i, t, a, co):
        v = noise((co.x * 0.4, co.y * 0.4, 7), 1.0)
        c = mix(P["moss_dark"], P["moss"], smoothstep(-0.5, 0.2, v))
        return mix(c, P["moss_light"], smoothstep(0.15, 0.6, v))

    g.lathe(prof, segments, color, m=m, adjust=adjust, phase=rng.uniform(0, 1))


def root(g, rng, points, r0=5.0, r1=2.0, m=IDENTITY, sides=7, moss=0.45, per_segment=3, tone="bark", wobble=0.12,
         squash=0.8):
    """Tapered bent tube through control points (ends usually buried)."""
    noise = Noise("root", rng.random())
    pts = smooth_path(points, per_segment)
    base_c = P[tone]

    def color(t, a, co, off):
        k = int(round((a % TAU) / TAU * sides))
        c = base_c if k % 2 else mix(base_c, P["bark_dark"], 0.5)
        c = mix(c, P["bark_light"], 0.3 * max(0, off.z))
        return mix(c, P["lichen"], 0.35 * smoothstep(0.35, 0.6, noise(co * 0.08, 1.0))), moss

    def wob(i, k):
        return 1.0 + wobble * noise((i * 0.7, k * 1.3, 0), 1.0) + (0.08 if k % 2 else -0.04)

    g.sweep(pts, lambda t: lerp(r0, r1, t ** 0.8), sides, color, m=m, wobble=wob, phase=rng.uniform(0, 1), squash=squash)
    return pts


def clover(g, rng, height=14.0, leaf=5.0, m=IDENTITY):
    lean = Vector((rng.uniform(-0.1, 0.1), rng.uniform(-0.1, 0.1), 0)) * height
    pts = [Vector((0, 0, -0.8)), Vector((0, 0, height * 0.5)) + lean * 0.25, Vector((0, 0, height)) + lean]
    g.sweep(pts, [0.45, 0.4, 0.35], 4, lambda t, a, co, off: mix(P["grass_dark"], P["clover"], t), m=m)
    top = pts[-1]
    outline = [(0, 0), (0.45, 0.32), (0.58, 0.72), (0.36, 1.0), (0.0, 0.84), (-0.36, 1.0), (-0.58, 0.72), (-0.45, 0.32)]
    rot0 = rng.uniform(0, TAU)
    for k in range(3):
        a = rot0 + TAU * k / 3 + rng.uniform(-0.15, 0.15)
        tilt = math.radians(rng.uniform(8, 22))
        lm = m @ Matrix.Translation(top) @ Matrix.Rotation(a - math.pi / 2, 4, "Z") @ Matrix.Rotation(tilt, 4, "X")
        center_t = g.vert(lm @ Vector((0, leaf * 0.52, 0.35)), P["clover_mark"])
        center_b = g.vert(lm @ Vector((0, leaf * 0.52, -0.1)), mix(P["clover"], P["grass_dark"], 0.4))
        top_ring, bot_ring = [], []
        for ox, oy in outline:
            droop = -0.5 * (ox * ox + max(0, oy - 0.5)) * leaf * 0.15
            c = mix(P["clover"], P["clover_mark"], 0.45 if 0.35 < oy < 0.8 and abs(ox) < 0.35 else 0.0)
            top_ring.append(g.vert(lm @ Vector((ox * leaf, oy * leaf, droop + 0.12)), c))
            bot_ring.append(g.vert(lm @ Vector((ox * leaf, oy * leaf, droop - 0.12)), mix(P["clover"], P["grass_dark"], 0.3)))
        n = len(outline)
        for i in range(n):
            j = (i + 1) % n
            g.face((center_t, top_ring[i], top_ring[j]))
            g.face((center_b, bot_ring[j], bot_ring[i]))
            g.face((top_ring[i], bot_ring[i], bot_ring[j], top_ring[j]))


# ---------------------------------------------------------------- silk

def orb_web(g, rng, radius=22.0, radials=16, turns=9, thread=0.22, m=IDENTITY, frame=None, dew_count=14):
    """Orb web in the local XZ plane (normal = Y). frame: [(x, z)] polygon around the hub, else generated.
    Returns the frame corners in local space (for anchor threads)."""
    if frame is None:
        corners = []
        n = 6
        for k in range(n):
            a = TAU * k / n + rng.uniform(-0.2, 0.2)
            r = radius * rng.uniform(1.0, 1.2)
            corners.append((r * math.cos(a), r * math.sin(a)))
    else:
        corners = list(frame)
    silk, shade = P["silk"], P["silk_shade"]

    def frame_hit(ang):
        d = Vector((math.cos(ang), math.sin(ang)))
        best = None
        for i in range(len(corners)):
            a = Vector(corners[i])
            b = Vector(corners[(i + 1) % len(corners)])
            e = b - a
            den = d.x * e.y - d.y * e.x
            if abs(den) < 1e-9:
                continue
            t = (a.x * e.y - a.y * e.x) / den
            s = (a.x * d.y - a.y * d.x) / den
            if t > 0 and -1e-6 <= s <= 1 + 1e-6 and (best is None or t < best):
                best = t
        return best or radius

    def p3(x, z):
        return Vector((x, 0.0, z))

    angles = [TAU * k / radials + rng.uniform(-0.08, 0.08) for k in range(radials)]
    reach = [frame_hit(a) for a in angles]
    for i in range(len(corners)):
        a, b = corners[i], corners[(i + 1) % len(corners)]
        g.strand(p3(*a), p3(*b), thread * 1.3, silk, m=m)
    for a, r in zip(angles, reach):
        g.strand(p3(0, 0), p3(r * math.cos(a), r * math.sin(a)), thread, shade, m=m)
    r_in = radius * 0.14
    spiral = []
    steps = int(turns * radials)
    for s in range(steps + 1):
        k = s % radials
        f = s / steps
        r_out = min(reach[k] * 0.92, radius * (1.0 + 0.06 * math.sin(3 * angles[k])))
        rr = r_in + (r_out - r_in) * f
        spiral.append(p3(rr * math.cos(angles[k]), rr * math.sin(angles[k])))
    for a, b in zip(spiral, spiral[1:]):
        g.strand(a, b, thread * 0.7, silk, m=m)
    hub = [p3(r_in * 0.5 * math.cos(a), r_in * 0.5 * math.sin(a)) for a in angles[::2]]
    for a, b in zip(hub, hub[1:] + hub[:1]):
        g.strand(a, b, thread, silk, m=m)
    for _ in range(dew_count):
        p = spiral[rng.randint(radials, len(spiral) - 1)]
        r = rng.uniform(0.35, 0.8)
        dew(g, rng, radius=r, center=p - Vector((0, 0, r * 1.6)), m=m, subdiv=1 if r < 0.6 else 2)
    return [p3(*c) for c in corners]


def egg_sac(g, rng, size=7.0, glow=False, m=IDENTITY, segments=9):
    noise = Noise("egg", rng.random())
    R, H = size * 0.5, size * 0.62
    prof = [(0, H * 2 + 0.8), (0.15 * R, H * 1.95), (0.55 * R, H * 1.8), (0.9 * R, H * 1.4), (R, H), (0.92 * R, H * 0.55),
            (0.55 * R, H * 0.15), (0, 0)]

    def adjust(i, t, a, co):
        if a is None:
            return co
        w = 1.0 + 0.1 * noise((math.cos(a) * 2, math.sin(a) * 2, i * 0.6), 1.0)
        return Vector((co.x * w, co.y * w, co.z))

    def color(i, t, a, co):
        if glow:
            core = smoothstep(0.2, 0.9, 1 - abs(t - 0.5) * 2)
            return mix(P["silk"], P["amber_glow"], 0.55 * core)
        return mix(P["silk"], P["silk_shade"], 0.4 * t)

    g.lathe(prof, segments, color, m=m, adjust=adjust, phase=rng.uniform(0, 1))
    for k in range(2):
        tilt = Matrix.Rotation(rng.uniform(0.3, 0.7), 4, "X") @ Matrix.Rotation(rng.uniform(0, TAU), 4, "Z")
        ring = [tilt @ Vector((R * 1.02 * math.cos(TAU * s / 8), R * 1.02 * math.sin(TAU * s / 8), 0)) + Vector((0, 0, H))
                for s in range(9)]
        g.sweep(ring, 0.18 * size / 7, 3, lambda *a: P["silk_shade"], m=m, caps=(False, False))


# ---------------------------------------------------------------- shells (hollow log, stump walls)

def ring_panel(g, theta0, theta1, cols, rows, r_in, r_out, z_in, z_out, c_in, c_out, c_rim, m=IDENTITY, mid=None):
    """One closed segment of a thick ring (stump wall, log quarter). Angles in radians; z is the ring axis.
    r_in/r_out(theta, z); z_in/z_out(theta) -> (bottom, top); colours (theta, z, co) -> rgb | (rgb, moss);
    mid(theta) -> (r, z, rgb, moss) ridge vertex on the top rim."""
    us = [lerp(theta0, theta1, c / cols) for c in range(cols + 1)]

    def pos(rf):
        return lambda th, z: m @ Vector((rf(th, z) * math.cos(th), rf(th, z) * math.sin(th), z))

    top_mid = None
    if mid:
        def top_mid(th):
            r, z, c, mo = mid(th)
            return m @ Vector((r * math.cos(th), r * math.sin(th), z)), c, mo
    return g.thick_panel(us, rows, pos(r_in), pos(r_out), z_in, z_out, c_in, c_out, c_rim, top_mid=top_mid)


def hollow_log(rng, make_geo, length=90.0, radius=16.0, thickness=4.0, pieces=4, m=IDENTITY, cols_per_piece=4,
               moss=0.8):
    """Hollow log along local X, resting on z = 0, split into `pieces` closed shell segments (roughly convex).
    make_geo(i) -> Geo for piece i. Returns the Geos."""
    noise = Noise("log", rng.random())
    rows = [s / 6 for s in range(7)]
    frame = m @ Matrix.Translation((0, 0, radius * 0.92)) @ Matrix.Rotation(math.pi / 2, 4, "Y")
    # local ring space: z runs along the log (-L/2..L/2) and maps to world -X..+X via the frame

    def ridge(th):
        return 0.07 * radius * (1 if int(round(th / TAU * cols_per_piece * pieces * 2)) % 2 else -0.4)

    def r_out(th, z):
        return radius * (1 + 0.05 * noise((math.cos(th), math.sin(th), z * 0.02), 1.0)) + ridge(th)

    def r_in(th, z):
        return radius - thickness + 0.8 * noise((math.cos(th) * 2, math.sin(th) * 2, z * 0.05 + 4), 1.0)

    def ends(th):
        a = length * 0.5
        j1 = 3.0 * noise((math.cos(th) * 1.7, math.sin(th) * 1.7, 11), 1.0) + 2.0 * math.sin(th * 5)
        j2 = 3.0 * noise((math.cos(th) * 1.7, math.sin(th) * 1.7, 23), 1.0)
        return (-a + j1, a + j2)

    def c_out(th, z, co):
        k = int(round(th / TAU * cols_per_piece * pieces * 2))
        return (P["bark"] if k % 2 else P["bark_dark"]), moss

    def c_in(th, z, co):
        return mix(P["wood_rot"], P["wood_dark"], 0.3 + 0.3 * noise((z * 0.1, th, 0), 1.0))

    def c_rim(th, z, co):
        return P["wood_pale"]

    geos = []
    for i in range(pieces):
        g = make_geo(i)
        t0, t1 = TAU * i / pieces, TAU * (i + 1) / pieces
        ring_panel(g, t0, t1, cols_per_piece, rows, r_in, r_out, ends, ends, c_in, c_out, c_rim, m=frame)
        geos.append(g)
    return geos


# ---------------------------------------------------------------- dungeon pieces

def tunnel_mouth(g, rng, radius=8.0, depth=14.0, collar=4.0, m=IDENTITY, segments=12):
    """Dug tunnel mouth facing local +Z: an earthen collar around a funnel that fades to black.
    Everything sits at z <= 2, so it can be pushed into a wall or mound face (closed solid)."""
    noise = Noise("tunnel", rng.random())
    r = radius
    prof = [(0, -depth), (0.45 * r, -depth * 0.8), (0.8 * r, -depth * 0.45), (0.96 * r, -1.5), (r + 0.8, 1.2),
            (r + collar * 0.55, 1.9), (r + collar, 0.2), (r + collar * 1.1, -2.5), (r + collar * 0.8, -depth - 1.5),
            (0, -depth - 1.5)]

    def adjust(i, t, a, co):
        if a is None or i < 3:
            return co
        w = 1 + 0.09 * noise((math.cos(a) * 2, math.sin(a) * 2, i), 1)
        return Vector((co.x * w, co.y * w * 0.92, co.z + (0.6 * noise((math.cos(a) * 3, math.sin(a) * 3, 5)) if i in (4, 5) else 0)))

    def color(i, t, a, co):
        if i <= 3:
            return mix(P["tunnel"], P["ant_earth"], smoothstep(0, 3, i) * 0.8)
        return mix(P["ant_earth"], P["ant_earth_light"], 0.6 if i in (4, 5) else 0.1), 0.3

    g.lathe(prof, segments, color, m=m, adjust=adjust, phase=rng.uniform(0, 1))


def ant_nest(g, rng, radius=40.0, height=26.0, crater=10.0, m=IDENTITY, segments=16):
    """Ant-nest mound: bumpy earthen dome with a dark crater on top (closed)."""
    noise = Noise("nest", rng.random())
    R, H = radius, height
    prof = [(0, -2), (R * 1.02, -2), (R, 2.5), (R * 0.86, H * 0.38), (R * 0.62, H * 0.72), (crater * 1.6, H * 0.98),
            (crater * 1.15, H), (crater, H * 0.93), (crater * 0.7, H * 0.7), (crater * 0.35, H * 0.52), (0, H * 0.48)]

    def adjust(i, t, a, co):
        if a is None:
            return co
        n = noise((math.cos(a) * 2.2, math.sin(a) * 2.2, i * 0.4), 1.0, 2)
        w = 1 + (0.1 if 1 <= i <= 5 else 0.05) * n
        dz = 1.8 * n if 3 <= i <= 6 else 0.0
        return Vector((co.x * w, co.y * w, co.z + dz))

    def color(i, t, a, co):
        if i >= 7:
            return mix(P["ant_earth"], P["tunnel"], smoothstep(7, 10, i))
        k = int(round((a % TAU) / TAU * segments))
        c = mix(P["ant_earth"], P["ant_earth_light"], 0.55 if (k + i) % 3 == 0 else 0.15)
        return c, 0.15

    g.lathe(prof, segments, color, m=m, adjust=adjust, phase=rng.uniform(0, 1))

    def surface(a, z):
        """Point and outward normal on the mound at angle a, height z (for placing side tunnels)."""
        pts = [(r_, z_) for r_, z_ in prof[1:6]]
        for (r0, z0), (r1, z1) in zip(pts, pts[1:]):
            if z0 <= z <= z1:
                f = (z - z0) / (z1 - z0)
                r_ = lerp(r0, r1, f)
                nr, nz = (z1 - z0), -(r1 - r0)
                ln = math.hypot(nr, nz)
                n = Vector((nr / ln * math.cos(a), nr / ln * math.sin(a), nz / ln))
                return Vector((r_ * math.cos(a), r_ * math.sin(a), z)), n
        return Vector((R * math.cos(a), R * math.sin(a), z)), Vector((math.cos(a), math.sin(a), 0))

    return surface


def stump_dais(g, rng, radius=12.0, height=6.0, m=IDENTITY, segments=12):
    """Low sawn-off stump slice: bark sides, pale growth rings on top (closed)."""
    prof = [(0, height), (radius * 0.35, height), (radius * 0.7, height), (radius * 0.92, height - 0.2),
            (radius, height - 1.0), (radius * 1.06, height * 0.4), (radius * 1.2, -0.8), (0, -0.8)]
    noise = Noise("dais", rng.random())

    def adjust(i, t, a, co):
        if a is None:
            return co
        w = 1 + 0.05 * noise((math.cos(a) * 2, math.sin(a) * 2, i), 1) + (0.03 if i >= 4 and int(a * 5) % 2 else 0)
        return Vector((co.x * w, co.y * w, co.z))

    def color(i, t, a, co):
        if i <= 3:
            return (P["wood_pale"], P["wood_rot"], P["wood_pale"], P["bark_light"])[i]
        return (P["bark"] if int((a % TAU) / TAU * segments) % 2 else P["bark_dark"]), 0.5

    g.lathe(prof, segments, color, m=m, adjust=adjust)
