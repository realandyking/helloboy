"""Spider Quest map kit: geometry builder, noise, vertex-paint bake, markers, budgets, FBX export, manifest.

Shared by build_map.py (all maps) and map_props.py (prop generators). Nothing here knows about a
specific map; maps are data in map_config.py.

Space: 1 Blender unit = 1 stud, Z up, north = +Y. Roblox (x, y, z) = (x_b, z_b, -y_b).
Colours are sRGB 0-1 tuples written straight into a corner BYTE_COLOR attribute named `Col`
(same as the spider build). All randomness is seeded with zlib.crc32, never hash().
"""

import json
import math
import os
import random
import zlib

import bpy  # must come before bmesh when running as the bpy module
import bmesh  # noqa: I001
from mathutils import Matrix, Vector
from mathutils import noise as mnoise
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.dirname(os.path.dirname(HERE))

UP = Vector((0.0, 0.0, 1.0))
IDENTITY = Matrix.Identity(4)
TAU = math.tau
PREFIXES = ("COL", "PROP", "DECO", "MARKER")
MAX_OBJECT_TRIS = 10000
DOOR_DIRS = {"N": (0, 1), "E": (1, 0), "S": (0, -1), "W": (-1, 0)}


# ---------------------------------------------------------------- small math

def clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c0, c1, t):
    return tuple(a + (b - a) * t for a, b in zip(c0, c1))


def smoothstep(e0, e1, x):
    t = clamp((x - e0) / (e1 - e0))
    return t * t * (3 - 2 * t)


def seed_of(*parts):
    return zlib.crc32(":".join(str(p) for p in parts).encode())


def rng_for(*parts):
    return random.Random(seed_of(*parts))


def to_roblox(v):
    return (round(v[0], 4), round(v[2], 4), round(-v[1], 4))


def mat(loc=(0, 0, 0), rot_z=0.0, scale=1.0, tilt=(0.0, 0.0)):
    """Placement matrix: scale, then tilt about X and Y (radians), then yaw about Z, then translate."""
    s = scale if isinstance(scale, (tuple, list)) else (scale, scale, scale)
    m_scale = Matrix.Diagonal((s[0], s[1], s[2], 1.0))
    m_tilt = Matrix.Rotation(tilt[1], 4, "Y") @ Matrix.Rotation(tilt[0], 4, "X")
    return Matrix.Translation(Vector(loc)) @ Matrix.Rotation(rot_z, 4, "Z") @ m_tilt @ m_scale


class Noise:
    """Deterministic Perlin fBm. Seeded by offsetting the lookup, so no global state is touched."""

    def __init__(self, *seed_parts):
        r = rng_for("noise", *seed_parts)
        self.off = Vector((r.uniform(-900, 900), r.uniform(-900, 900), r.uniform(-900, 900)))

    def __call__(self, p, freq=1.0, octaves=1, gain=0.5):
        p = Vector(p)
        if len(p) == 2:
            p = Vector((p[0], p[1], 0.0))
        total, amp, f, norm = 0.0, 1.0, freq, 0.0
        for _ in range(octaves):
            total += amp * mnoise.noise(p * f + self.off)
            norm += amp
            amp *= gain
            f *= 2.03
        return total / norm


def smooth_path(points, per_segment=3):
    """Catmull-Rom through control points (ends clamped)."""
    pts = [Vector(p) for p in points]
    if len(pts) < 3:
        return pts
    out = []
    for i in range(len(pts) - 1):
        p0, p1, p2 = pts[max(0, i - 1)], pts[i], pts[i + 1]
        p3 = pts[min(len(pts) - 1, i + 2)]
        for s in range(per_segment):
            t = s / per_segment
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(pts[-1])
    return out


def poisson(rng, count, sample, min_dist, accept=None, tries=40, taken=None):
    """Dart-throwing scatter. sample() -> (x, y); accept(x, y) filters; taken is a shared list of (x, y, r)."""
    taken = taken if taken is not None else []
    out = []
    for _ in range(count):
        for _ in range(tries):
            x, y = sample()
            if accept and not accept(x, y):
                continue
            if any((x - tx) ** 2 + (y - ty) ** 2 < (min_dist + tr) ** 2 for tx, ty, tr in taken):
                continue
            out.append((x, y))
            taken.append((x, y, min_dist * 0.5))
            break
    return out


# ---------------------------------------------------------------- geometry builder

def _cm(value):
    """Colour callbacks return rgb or (rgb, moss). Normalise to (rgb, moss)."""
    if len(value) == 2 and isinstance(value[0], (tuple, list)):
        return tuple(value[0]), float(value[1])
    return tuple(value), 0.0


class Geo:
    """One bmesh. Each vertex carries a base colour (`paint`) and a moss weight (`moss`); the lighting,
    occlusion, moss and jitter are baked into the corner `Col` attribute later by bake_colors()."""

    def __init__(self, *seed_parts):
        self.bm = bmesh.new()
        self._paint = self.bm.verts.layers.float_color.new("paint")
        self._moss = self.bm.verts.layers.float.new("moss")
        self.rng = rng_for(*seed_parts)

    # -- basics
    def vert(self, co, color, moss=0.0):
        v = self.bm.verts.new(Vector(co))
        v[self._paint] = (color[0], color[1], color[2], 1.0)
        v[self._moss] = moss
        return v

    def face(self, verts):
        vs = []
        for v in verts:
            if v not in vs:
                vs.append(v)
        if len(vs) < 3:
            return None
        try:
            return self.bm.faces.new(vs)
        except ValueError:
            return None

    def bridge(self, a, b, closed=True):
        if len(a) == 1 and len(b) == 1:
            return
        if len(a) == 1 or len(b) == 1:
            pole, ring = (a[0], b) if len(a) == 1 else (b[0], a)
            n = len(ring) if closed else len(ring) - 1
            for k in range(n):
                self.face((pole, ring[k], ring[(k + 1) % len(ring)]))
            return
        assert len(a) == len(b), (len(a), len(b))
        n = len(a) if closed else len(a) - 1
        for k in range(n):
            k2 = (k + 1) % len(a)
            self.face((a[k], a[k2], b[k2], b[k]))

    # -- surfaces of revolution
    def lathe(self, profile, segments, color, m=IDENTITY, adjust=None, phase=0.0, close=True):
        """profile: [(r, z)] in order; r <= 0 makes a pole. color(i, t, angle, co) -> rgb | (rgb, moss).
        adjust(i, t, angle, co) -> co lets callers bend, wobble or shear rings (angle is None on poles)."""
        rings = []
        n = len(profile)
        for i, (r, z) in enumerate(profile):
            t = i / (n - 1)
            if r <= 1e-6:
                co = Vector((0.0, 0.0, z))
                if adjust:
                    co = adjust(i, t, None, co)
                rings.append([self.vert(m @ co, *_cm(color(i, t, 0.0, co)))])
                continue
            ring = []
            for k in range(segments):
                a = phase + TAU * k / segments
                co = Vector((r * math.cos(a), r * math.sin(a), z))
                if adjust:
                    co = adjust(i, t, a, co)
                ring.append(self.vert(m @ co, *_cm(color(i, t, a, co))))
            rings.append(ring)
        for ra, rb in zip(rings, rings[1:]):
            self.bridge(ra, rb)
        if close:
            for ring in (rings[0], rings[-1]):
                if len(ring) > 2:
                    self.face(ring)
        return rings

    def sweep(self, points, radius, sides, color, m=IDENTITY, caps=(True, True), wobble=None,
              phase=0.0, squash=1.0, up_hint=None):
        """Tube along a polyline with rotation-minimising frames. radius: number, list per point, or f(t).
        color(t, angle, co, offset_dir) -> rgb | (rgb, moss). A radius of 0 at an end makes a pointed tip."""
        pts = [Vector(p) for p in points]
        n = len(pts)
        if callable(radius):
            radii = [radius(i / (n - 1)) for i in range(n)]
        elif isinstance(radius, (list, tuple)):
            radii = list(radius)
        else:
            radii = [radius] * n
        tangents = []
        for i in range(n):
            a, b = pts[max(0, i - 1)], pts[min(n - 1, i + 1)]
            tangents.append((b - a).normalized())
        ref = Vector(up_hint) if up_hint else UP
        if abs(tangents[0].dot(ref)) > 0.95:
            ref = Vector((1, 0, 0)) if abs(tangents[0].x) < 0.9 else Vector((0, 1, 0))
        nrm = (ref - tangents[0] * ref.dot(tangents[0])).normalized()
        rings = []
        for i, p in enumerate(pts):
            t_vec = tangents[i]
            nrm = (nrm - t_vec * nrm.dot(t_vec)).normalized()
            binorm = t_vec.cross(nrm)
            t = i / (n - 1)
            r = radii[i]
            if r <= 1e-5:
                rings.append([self.vert(m @ p, *_cm(color(t, 0.0, p, t_vec)))])
                continue
            ring = []
            for k in range(sides):
                a = phase + TAU * k / sides
                off = nrm * (math.cos(a) * squash) + binorm * math.sin(a)
                rr = r * (wobble(i, k) if wobble else 1.0)
                co = p + off * rr
                ring.append(self.vert(m @ co, *_cm(color(t, a, co, off))))
            rings.append(ring)
        for ra, rb in zip(rings, rings[1:]):
            self.bridge(ra, rb)
        if caps[0] and len(rings[0]) > 2:
            self.face(list(reversed(rings[0])))
        if caps[1] and len(rings[-1]) > 2:
            self.face(rings[-1])
        return rings

    def ico(self, center, radii, subdiv, color, m=IDENTITY, displace=None, adjust=None):
        """Displaced icosphere. color(n, co) with n the unit direction. adjust(n, co) -> co."""
        scratch = bmesh.new()
        bmesh.ops.create_icosphere(scratch, subdivisions=subdiv, radius=1.0)
        scratch.verts.index_update()
        c = Vector(center)
        verts = []
        for sv in scratch.verts:
            n = sv.co.normalized()
            d = displace(n) if displace else 0.0
            co = Vector((n.x * radii[0], n.y * radii[1], n.z * radii[2])) * (1.0 + d)
            if adjust:
                co = adjust(n, co)
            verts.append(self.vert(m @ (co + c), *_cm(color(n, co))))
        for f in scratch.faces:
            self.face([verts[v.index] for v in f.verts])
        scratch.free()
        return verts

    def strand(self, p0, p1, radius, color, sag=0.0, segments=1, m=IDENTITY, sides=3):
        """Silk thread: thin open prism along a sagging line."""
        p0, p1 = Vector(p0), Vector(p1)
        pts = []
        for s in range(segments + 1):
            t = s / segments
            pts.append(p0.lerp(p1, t) - UP * (sag * 4 * t * (1 - t)))
        self.sweep(pts, radius, sides, lambda *a: color, m=m, caps=(False, False))

    # -- slabs
    def thick_panel(self, us, rows, pos_a, pos_b, z_a, z_b, color_a, color_b, color_rim,
                    top_mid=None, simple_b=False):
        """A closed slab between surface A and surface B, sampled on columns `us`.
        z_a(u) / z_b(u) -> (bottom, top). rows: fractions 0..1 up each column.
        pos_a(u, z) / pos_b(u, z) -> Vector. color_*(u, z, co) -> rgb | (rgb, moss).
        top_mid(u) -> (co, rgb, moss) adds a ridge vertex between the two top edges (e.g. a jagged rim).
        simple_b: surface B is flat, so it becomes one n-gon of its boundary (hidden backs of walls)."""
        nc, nr = len(us), len(rows)
        cols_a, cols_b = [], []
        for ci, u in enumerate(us):
            zb, zt = z_a(u)
            col = []
            for s in rows:
                z = lerp(zb, zt, s)
                co = pos_a(u, z)
                col.append(self.vert(co, *_cm(color_a(u, z, co))))
            cols_a.append(col)
            zb, zt = z_b(u)
            col = []
            for ri, s in enumerate(rows):
                if simple_b and 0 < ci < nc - 1 and 0 < ri < nr - 1:
                    col.append(None)
                    continue
                z = lerp(zb, zt, s)
                co = pos_b(u, z)
                col.append(self.vert(co, *_cm(color_b(u, z, co))))
            cols_b.append(col)
        mids = []
        if top_mid:
            for u in us:
                co, c, mo = top_mid(u)
                mids.append(self.vert(co, c, mo))
        # surface A
        for ci in range(nc - 1):
            for ri in range(nr - 1):
                self.face((cols_a[ci][ri], cols_a[ci + 1][ri], cols_a[ci + 1][ri + 1], cols_a[ci][ri + 1]))
        # surface B
        if simple_b:
            loop = [cols_b[ci][0] for ci in range(nc)]
            loop += [cols_b[nc - 1][ri] for ri in range(1, nr)]
            loop += [cols_b[ci][nr - 1] for ci in range(nc - 2, -1, -1)]
            loop += [cols_b[0][ri] for ri in range(nr - 2, 0, -1)]
            self.face(loop)
        else:
            for ci in range(nc - 1):
                for ri in range(nr - 1):
                    self.face((cols_b[ci][ri], cols_b[ci][ri + 1], cols_b[ci + 1][ri + 1], cols_b[ci + 1][ri]))
        # top and bottom strips
        for ci in range(nc - 1):
            at, at2 = cols_a[ci][-1], cols_a[ci + 1][-1]
            bt, bt2 = cols_b[ci][-1], cols_b[ci + 1][-1]
            if mids:
                self.face((at, mids[ci], mids[ci + 1], at2))
                self.face((mids[ci], bt, bt2, mids[ci + 1]))
            else:
                self.face((at, bt, bt2, at2))
            self.face((cols_a[ci][0], cols_a[ci + 1][0], cols_b[ci + 1][0], cols_b[ci][0]))
        # end caps
        for ci in (0, nc - 1):
            ca, cb = cols_a[ci], cols_b[ci]
            for ri in range(nr - 1):
                self.face((ca[ri], ca[ri + 1], cb[ri + 1], cb[ri]))
            if mids:
                self.face((ca[-1], mids[ci], cb[-1]))
        return cols_a, cols_b

    def solidify(self, faces, bottom_z, color):
        """Close a top surface into a slab: side walls down to bottom_z and a filled bottom (holes allowed)."""
        region = set(faces)
        boundary = []
        for f in faces:
            for loop in f.loops:
                others = [x for x in loop.edge.link_faces if x is not f and x in region]
                if not others:
                    boundary.append((loop.vert, loop.link_loop_next.vert))
        low = {}

        def lower(v):
            if v not in low:
                low[v] = self.vert((v.co.x, v.co.y, bottom_z), color)
            return low[v]

        for a, b in boundary:
            self.face((b, a, lower(a), lower(b)))
        edges = []
        for a, b in boundary:
            e = self.bm.edges.get((lower(a), lower(b)))
            if e:
                edges.append(e)
        bmesh.ops.triangle_fill(self.bm, use_beauty=True, use_dissolve=False, edges=edges,
                                normal=Vector((0, 0, -1)))

    def rect_heightfield(self, xs, ys, height, color, bottom_z, keep=None):
        """Grid slab. height(x, y); color(x, y, z) -> rgb | (rgb, moss); keep(cx, cy) drops cells (holes)."""
        grid = []
        for x in xs:
            col = []
            for y in ys:
                z = height(x, y)
                col.append(self.vert((x, y, z), *_cm(color(x, y, z))))
            grid.append(col)
        faces = []
        for i in range(len(xs) - 1):
            for j in range(len(ys) - 1):
                cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
                if keep and not keep(cx, cy):
                    continue
                f = self.face((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
                if f:
                    faces.append(f)
        self.solidify(faces, bottom_z, _cm(color(xs[0], ys[0], bottom_z))[0])
        return grid

    def polar_heightfield(self, radii, segments, height, color, bottom_z, center=(0, 0), keep=None, phase=0.0):
        """Disc (radii[0] == 0) or annulus slab on rings x segments. Same callbacks as rect_heightfield."""
        cx0, cy0 = center
        rings = []
        for r in radii:
            if r <= 1e-6:
                z = height(cx0, cy0)
                rings.append([self.vert((cx0, cy0, z), *_cm(color(cx0, cy0, z)))])
                continue
            ring = []
            for k in range(segments):
                a = phase + TAU * k / segments
                x, y = cx0 + r * math.cos(a), cy0 + r * math.sin(a)
                z = height(x, y)
                ring.append(self.vert((x, y, z), *_cm(color(x, y, z))))
            rings.append(ring)
        faces = []
        for ra, rb in zip(rings, rings[1:]):
            for k in range(segments):
                k2 = (k + 1) % segments
                quad = (ra[0], rb[k], rb[k2]) if len(ra) == 1 else (ra[k], rb[k], rb[k2], ra[k2])
                cx = sum(v.co.x for v in quad) / len(quad)
                cy = sum(v.co.y for v in quad) / len(quad)
                if keep and not keep(cx, cy):
                    continue
                f = self.face(quad)
                if f:
                    faces.append(f)
        base = _cm(color(cx0, cy0, bottom_z))[0]
        self.solidify(faces, bottom_z, base)
        return rings

    # -- output
    def finish(self, mesh, sharp_angle=50.0):
        bm = self.bm
        loose = [v for v in bm.verts if not v.link_faces]
        if loose:
            bmesh.ops.delete(bm, geom=loose, context="VERTS")
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        limit = math.radians(sharp_angle)
        for f in bm.faces:
            f.smooth = True
        for e in bm.edges:
            if len(e.link_faces) != 2 or e.calc_face_angle(0.0) > limit:
                e.smooth = False
        bm.normal_update()
        bm.to_mesh(mesh)
        bm.free()
        return mesh

    def tris(self):
        return sum(len(f.verts) - 2 for f in self.bm.faces)


# ---------------------------------------------------------------- scene helpers

def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    return scene


def vertex_color_material(name):
    """One vertex-colour material per map, like the spider's."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    nodes = m.node_tree.nodes
    attr = nodes.new("ShaderNodeVertexColor")
    attr.layer_name = "Col"
    bsdf = nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.85
    m.node_tree.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    return m


def collection(name, parent=None):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    parent = parent or bpy.context.scene.collection
    if c.name not in parent.children:
        parent.children.link(c)
    return c


def mesh_from_geo(geo, name, material, kit=False, ground=True, occluder=True, sharp_angle=50.0):
    """kit=True: shared prop mesh, baked in its own space (self-occlusion plus a ground plane at z=0)."""
    me = bpy.data.meshes.new(name)
    geo.finish(me, sharp_angle)
    me.materials.append(material)
    me["kit"] = kit
    me["ground"] = ground
    me["occluder"] = occluder
    return me


def place(name, mesh, coll, matrix=IDENTITY):
    if bpy.data.objects.get(name):
        raise RuntimeError(f"duplicate object name {name}")
    prefix = name.split("_")[0]
    if prefix not in PREFIXES:
        raise RuntimeError(f"object {name} has no valid prefix {PREFIXES}")
    obj = bpy.data.objects.new(name, mesh)
    obj.matrix_world = matrix
    coll.objects.link(obj)
    return obj


_TETRA = ((0.5, 0.5, 0.5), (0.5, -0.5, -0.5), (-0.5, 0.5, -0.5), (-0.5, -0.5, 0.5))


def marker_mesh(material):
    """Tiny tetrahedron whose bounding-box centre is the object origin, so a Studio import that
    recentres parts on their bounds still reports the exact marker position."""
    me = bpy.data.meshes.get("marker_tetra")
    if me:
        return me
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in _TETRA]
    for tri in ((0, 1, 2), (0, 3, 1), (0, 2, 3), (1, 3, 2)):
        bm.faces.new([vs[i] for i in tri])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    col = bm.loops.layers.color.new("Col")
    for f in bm.faces:
        for loop in f.loops:
            loop[col] = (1.0, 0.1, 0.8, 1.0)
    me = bpy.data.meshes.new("marker_tetra")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(material)
    me["marker"] = True
    return me


def add_marker(name, pos, coll, material):
    if not name.startswith("MARKER_"):
        raise RuntimeError(f"marker {name} must start with MARKER_")
    obj = place(name, marker_mesh(material), coll, Matrix.Translation(Vector(pos)))
    obj.show_in_front = True
    return obj


# ---------------------------------------------------------------- vertex-paint bake

def _hemisphere(k):
    """Cosine-weighted directions around +Z (Fibonacci spiral on the unit disc, lifted)."""
    golden = math.pi * (3 - math.sqrt(5))
    dirs = []
    for i in range(k):
        r = math.sqrt((i + 0.5) / k)
        phi = i * golden
        dirs.append(Vector((r * math.cos(phi), r * math.sin(phi), math.sqrt(max(0.0, 1 - r * r)))))
    return dirs


def _bvh_for(objects):
    verts, polys = [], []
    for obj in objects:
        me = obj.data
        if me.get("marker") or not me.get("occluder", True):
            continue
        mw = obj.matrix_world
        base = len(verts)
        verts.extend(mw @ v.co for v in me.vertices)
        polys.extend([base + i for i in p.vertices] for p in me.polygons)
    return BVHTree.FromPolygons(verts, polys) if polys else None


def bake_colors(objects, shading, palette):
    """Bake light + occlusion + moss + hue shift + jitter into `Col` for every mesh once.
    Unique meshes see the whole object list; kit meshes see only themselves plus a ground plane."""
    world_bvh = _bvh_for(objects)
    dirs = _hemisphere(shading["aoRays"])
    moss_noise = Noise("moss")
    for obj in objects:
        me = obj.data
        if me.get("marker") or me.get("baked"):
            continue
        if me.get("kit"):
            bvh = BVHTree.FromPolygons([v.co for v in me.vertices], [list(p.vertices) for p in me.polygons])
            size = max(obj.dimensions) / max(1e-6, max(obj.scale)) if obj.dimensions else 10.0
            dist = min(shading["aoDistance"], max(2.0, size * shading["kitAoScale"]))
            _bake_mesh(me, IDENTITY, bvh, dist, me.get("ground", True), shading, palette, moss_noise)
        else:
            _bake_mesh(me, obj.matrix_world, world_bvh, shading["aoDistance"], False, shading, palette, moss_noise)
        me["baked"] = True


def _bake_mesh(me, mw, bvh, dist, ground, sh, pal, moss_noise):
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.normal_update()
    paint = bm.verts.layers.float_color.get("paint")
    moss = bm.verts.layers.float.get("moss")
    col = bm.loops.layers.color.get("Col") or bm.loops.layers.color.new("Col")
    nmat = mw.to_3x3().inverted_safe().transposed()
    dirs = _hemisphere(sh["aoRays"])
    rng = rng_for("jitter", me.name)
    lo, hi = sh["light"]
    shadow_tint, lit_tint = sh["shadowTint"], sh["litTint"]
    moss_a, moss_b = pal["moss"], pal["moss_light"]
    eps = 0.05
    colors = {}
    for v in bm.verts:
        p = mw @ v.co
        n = (nmat @ v.normal)
        n = n.normalized() if n.length > 1e-8 else UP.copy()
        q = n.to_track_quat("Z", "Y")
        occ = 0.0
        for d in dirs:
            dw = q @ d
            t_hit = None
            if bvh:
                hit = bvh.ray_cast(p + n * eps, dw, dist)
                if hit[0] is not None:
                    t_hit = hit[3]
            if ground and dw.z < -1e-3 and p.z > -1.0:
                tg = (p.z + 0.3) / -dw.z
                if tg < dist and (t_hit is None or tg < t_hit):
                    t_hit = tg
            if t_hit is not None:
                occ += (1.0 - t_hit / dist) ** sh["aoFalloff"]
        occ /= len(dirs)
        base = tuple(v[paint])[:3] if paint else (0.5, 0.5, 0.5)
        mw_ = v[moss] if moss else 0.0
        if mw_ > 0:
            wobble = moss_noise(p, 0.07, 2)
            amount = mw_ * smoothstep(0.35, 0.8, n.z + wobble * 0.45)
            mc = mix(moss_a, moss_b, clamp(0.5 + wobble * 1.4))
            base = mix(base, mc, amount)
        light = lerp(lo, hi, ((n.z * 0.5 + 0.5) ** 1.3))
        value = light * (1.0 - sh["occlusion"] * occ)
        tint = mix(shadow_tint, lit_tint, smoothstep(0.55, 1.0, value))
        jitter = 1.0 + rng.uniform(-1, 1) * sh["jitter"]
        colors[v] = tuple(clamp(base[i] * value * tint[i] * jitter) for i in range(3))
    for f in bm.faces:
        for loop in f.loops:
            loop[col] = (*colors[loop.vert], 1.0)
    if paint:
        bm.verts.layers.float_color.remove(paint)
    if moss:
        bm.verts.layers.float.remove(moss)
    bm.to_mesh(me)
    bm.free()
    me.color_attributes.active_color_name = "Col"
    me.color_attributes.default_color_name = "Col"


# ---------------------------------------------------------------- budgets, export, manifest

def tri_count(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def category(name):
    prefix = name.split("_")[0]
    if prefix not in PREFIXES:
        raise RuntimeError(f"{name}: exported names must start with one of {PREFIXES}")
    return prefix


def check_budget(label, objects, budget):
    """Raise if any object is over MAX_OBJECT_TRIS or the (non-marker) total is over budget."""
    total = 0
    for obj in objects:
        cat = category(obj.name)
        t = tri_count(obj)
        if t > MAX_OBJECT_TRIS:
            raise RuntimeError(f"[{label}] {obj.name} has {t} tris (max {MAX_OBJECT_TRIS} per object)")
        if cat != "MARKER":
            total += t
    print(f"[map] {label}: {total} tris / budget {budget}, {len(objects)} objects")
    groups = {}
    for obj in objects:
        if category(obj.name) != "MARKER":
            key = obj.name.rsplit("_", 1)[0] if obj.name.rsplit("_", 1)[-1].isdigit() else obj.name
            n, t = groups.get(key, (0, 0))
            groups[key] = (n + 1, t + tri_count(obj))
    for key, (n, t) in sorted(groups.items(), key=lambda kv: -kv[1][1])[:40]:
        print(f"[map]   {key:32s} x{n:<4d} {t:7d}")
    if total > budget:
        raise RuntimeError(f"[{label}] over budget: {total} tris > {budget}")
    return total


def world_bounds(obj):
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def manifest(label, objects, budget, fbx_path, extra=None):
    entries, markers, counts = [], [], {p: 0 for p in PREFIXES}
    total = 0
    meshes = {}
    for obj in sorted(objects, key=lambda o: o.name):
        cat = category(obj.name)
        counts[cat] += 1
        if cat == "MARKER":
            pos = obj.matrix_world.translation
            parts = obj.name.split("_")
            markers.append({
                "name": obj.name,
                "type": parts[1],
                "id": "_".join(parts[2:]) or None,
                "blender": [round(pos.x, 4), round(pos.y, 4), round(pos.z, 4)],
                "roblox": list(to_roblox(pos)),
            })
            continue
        t = tri_count(obj)
        total += t
        meshes[obj.data.name] = t
        lo, hi = world_bounds(obj)
        entries.append({
            "name": obj.name,
            "category": cat,
            "tris": t,
            "mesh": obj.data.name,
            "sharedMesh": obj.data.users > 1,
            "boundsBlender": {"min": [round(x, 3) for x in lo], "max": [round(x, 3) for x in hi]},
            "boundsRoblox": {"min": [round(lo.x, 3), round(lo.z, 3), round(-hi.y, 3)],
                             "max": [round(hi.x, 3), round(hi.z, 3), round(-lo.y, 3)]},
        })
    data = {
        "name": label,
        "fbx": os.path.relpath(fbx_path, BLENDER_DIR) if fbx_path else None,
        "units": "1 Blender unit = 1 stud",
        "axes": "Blender Z up, north = +Y. Roblox (x, y, z) = (x_b, z_b, -y_b).",
        "budget": budget,
        "totalTris": total,
        "uniqueMeshTris": sum(meshes.values()),
        "objectCounts": counts,
        "objects": entries,
        "markers": markers,
    }
    if extra:
        data.update(extra)
    return data


def export_fbx(path, objects):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.hide_set(False)
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.fbx(
        filepath=path,
        use_selection=True,
        object_types={"MESH"},
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_NONE",
        axis_forward="-Z",
        axis_up="Y",
        use_mesh_modifiers=True,
        use_triangles=True,
        mesh_smooth_type="FACE",
        colors_type="SRGB",
        add_leaf_bones=False,
        bake_anim=False,
    )
    bpy.ops.object.select_all(action="DESELECT")
    print(f"[map] exported {os.path.relpath(path, BLENDER_DIR)}")


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(data, fh, indent=1)
    print(f"[map] wrote {os.path.relpath(path, BLENDER_DIR)}")
