"""Build a Spider Quest spider form: low-tri vertex-painted mesh + shared Spider rig + clips.

Headless only:
    blender -b -P blender/scripts/build_spider.py -- --form spiderling
    python blender/scripts/build_spider.py --form spiderling     (with the `bpy` module)

Writes blender/sources/<form>.blend (mesh, rig, and each clip as a named action for the asset bridge)
and blender/exports/<form>.fbx (mesh + rig, rest pose). --clip-fbx also writes one baked FBX per clip.
"""

import argparse
import math
import os
import random
import sys
import zlib

import bpy  # must come before bmesh when running as the bpy module
import bmesh  # noqa: I001
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import spider_anims  # noqa: E402
from spider_config import FORMS, LEG_SEGMENTS, PAIRS, PALP_SEGMENTS, SIDES  # noqa: E402

BLENDER_DIR = os.path.dirname(HERE)
UP = Vector((0, 0, 1))


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser()
    parser.add_argument("--form", default="spiderling", choices=sorted(FORMS))
    parser.add_argument("--no-export", action="store_true")
    parser.add_argument("--clip-fbx", action="store_true", help="also bake each clip to FBX (the bridge reads actions directly)")
    return parser.parse_args(argv)


# ---------------------------------------------------------------- skeleton

def leg_name(side, pair, segment):
    return f"Leg_{side}{pair}_{segment}"


def leg_joints(form, side, index):
    """Hip, knee, ankle, foot positions for one leg."""
    legs = form["legs"]
    center = Vector(form["ceph"]["center"])
    rx, ry, _ = form["ceph"]["radii"]
    yaw = math.radians(legs["yaw"][index])
    out = Vector((SIDES[side] * math.sin(yaw), -math.cos(yaw), 0))

    def step(start, length, pitch_deg):
        pitch = math.radians(pitch_deg)
        return start + (out * math.cos(pitch) + UP * math.sin(pitch)) * length

    hip = center + Vector((out.x * rx * legs["hipInset"], out.y * ry * legs["hipInset"], legs["hipDrop"]))
    knee = step(hip, legs["femur"][index], legs["femurPitch"])
    ankle = step(knee, legs["tibia"][index], legs["tibiaPitch"])
    foot = step(ankle, ankle.z / math.sin(math.radians(-legs["tarsusPitch"])), legs["tarsusPitch"])
    return hip, knee, ankle, foot


def mirror(point, side):
    return Vector((point[0] * SIDES[side], point[1], point[2]))


def ellipsoid_point(part, direction):
    """Point on an ellipsoid part (ceph/abdomen) along a unit-space direction, with tilt applied."""
    d = Vector(direction).normalized()
    radii = part["radii"]
    local = Vector((d.x * radii[0], d.y * radii[1], d.z * radii[2]))
    tilt = Matrix.Rotation(math.radians(part.get("tilt", 0)), 3, "X")
    return Vector(part["center"]) + tilt @ local


def skeleton(form):
    """(name, parent, head, tail) for every bone. Order = parent before child."""
    ceph, abdomen = form["ceph"], form["abdomen"]
    c = Vector(ceph["center"])
    root_part = Vector(form["rootPart"])
    pedicel = ellipsoid_point(abdomen, (0, -1, 0.05))
    abdomen_back = ellipsoid_point(abdomen, (0, 1, 0.1))
    spin = form["spinnerets"]
    spin_base = ellipsoid_point(abdomen, spin["dir"])
    spin_dir = (Matrix.Rotation(math.radians(abdomen["tilt"]), 3, "X") @ Vector(spin["dir"])).normalized()

    bones = [
        ("Root", None, Vector((0, 0, 0)), Vector((0, 0, 0.5))),
        ("HumanoidRootPart", "Root", root_part, root_part + Vector((0, 0, 0.5))),
        ("Cephalothorax", "HumanoidRootPart", c, c + Vector((0, -ceph["radii"][1], 0))),
        ("Abdomen", "Cephalothorax", pedicel, abdomen_back),
        ("Spinnerets", "Abdomen", spin_base, spin_base + spin_dir * spin["length"]),
    ]
    chel, palps = form["chelicerae"], form["palps"]
    for side in SIDES:
        bones += [
            (f"Chelicera_{side}", "Cephalothorax", mirror(chel["base"], side), mirror(chel["tip"], side)),
            (f"Fang_{side}", f"Chelicera_{side}", mirror(chel["tip"], side), mirror(chel["fangTip"], side)),
            (f"Pedipalp_{side}_{PALP_SEGMENTS[0]}", "Cephalothorax", mirror(palps["base"], side), mirror(palps["joint"], side)),
            (f"Pedipalp_{side}_{PALP_SEGMENTS[1]}", f"Pedipalp_{side}_{PALP_SEGMENTS[0]}", mirror(palps["joint"], side), mirror(palps["tip"], side)),
        ]
        for i, pair in enumerate(PAIRS):
            joints = leg_joints(form, side, i)
            parent = "Cephalothorax"
            for s, segment in enumerate(LEG_SEGMENTS):
                name = leg_name(side, pair, segment)
                bones.append((name, parent, joints[s], joints[s + 1]))
                parent = name
    return bones


def build_armature(form, name):
    data = bpy.data.armatures.new(name)
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    for bone_name, parent, head, tail in skeleton(form):
        eb = data.edit_bones.new(bone_name)
        eb.head, eb.tail = head, tail
        # Local Z points up (or forward for the vertical root bones), so +X rotation lifts the tip.
        eb.align_roll(Vector((0, -1, 0)) if bone_name in ("Root", "HumanoidRootPart") else UP)
        if parent:
            eb.parent = data.edit_bones[parent]
            eb.use_connect = (eb.parent.tail - eb.head).length < 1e-5
    bpy.ops.object.mode_set(mode="OBJECT")
    data.display_type = "STICK"
    return obj


# ---------------------------------------------------------------- mesh

class MeshBuilder:
    """One bmesh for the whole spider. Every vertex is rigidly bound to one bone (exoskeleton segments)."""

    def __init__(self, bone_names, palette, seed):
        self.bm = bmesh.new()
        self.deform = self.bm.verts.layers.deform.verify()
        self.paint = self.bm.verts.layers.float_color.new("paint")  # per-vertex, copied to corners in finish()
        self.group_index = {name: i for i, name in enumerate(bone_names)}
        self.palette = palette
        self.rng = random.Random(seed)

    def bind(self, verts, bone, color_fn):
        for v, param in verts:
            v[self.deform][self.group_index[bone]] = 1.0
            jitter = 1 + self.rng.uniform(-1, 1) * self.palette["jitter"]
            v[self.paint] = (*(min(1.0, max(0.0, ch * jitter)) for ch in color_fn(param)), 1.0)

    def new_verts(self, op, **kwargs):
        """Run a bmesh create op in a scratch bmesh, copy it in, and return exactly the new vertices.
        (The ops merge and recycle vertices, so their own return value is not reliable.)"""
        scratch = bmesh.new()
        op(scratch, **kwargs)
        scratch.verts.index_update()
        verts = [self.bm.verts.new(v.co) for v in scratch.verts]
        for f in scratch.faces:
            self.bm.faces.new([verts[v.index] for v in f.verts])
        scratch.free()
        return verts

    def tube(self, p0, p1, radii, bone, color_fn, sides=6, overlap=0.03, band=None):
        """Tapered prism from p0 to p1. radii = (start, middle, end). color_fn gets t along the tube 0..1.
        band adds an extra ring at that t so a colour change there stays crisp."""
        d = (p1 - p0).normalized()
        a, b = p0 - d * overlap, p1 + d * overlap
        side = d.cross(UP)
        if side.length < 1e-4:
            side = d.cross(Vector((1, 0, 0)))
        side.normalize()
        up = side.cross(d).normalized()
        stations = [(0.0, radii[0]), (0.5, radii[1]), (1.0, radii[2])]
        if band:
            stations.insert(2, (band, radii[1] + (radii[2] - radii[1]) * (band - 0.5) / 0.5))
        rings = []
        for t, r in stations:
            center = a.lerp(b, t)
            ring = []
            for k in range(sides):
                ang = (k + 0.5) / sides * math.tau
                ring.append(self.bm.verts.new(center + (side * math.cos(ang) + up * math.sin(ang)) * max(r, 0.004)))
            rings.append((t, ring))
        for (_, r0), (_, r1) in zip(rings, rings[1:]):
            for k in range(sides):
                self.bm.faces.new((r0[k], r0[(k + 1) % sides], r1[(k + 1) % sides], r1[k]))
        self.bm.faces.new(list(reversed(rings[0][1])))
        self.bm.faces.new(rings[-1][1])
        self.bind([(v, t) for t, ring in rings for v in ring], bone, color_fn)

    def ball(self, center, radius, bone, color, subdivisions=1):
        verts = self.new_verts(bmesh.ops.create_icosphere, subdivisions=subdivisions, radius=radius,
                               matrix=Matrix.Translation(center))
        self.bind([(v, None) for v in verts], bone, lambda _: color)

    def ellipsoid(self, part, bone, color_fn):
        u, v = part["segments"]
        verts = self.new_verts(bmesh.ops.create_uvsphere, u_segments=u, v_segments=v, radius=1.0)
        tilt = Matrix.Rotation(math.radians(part.get("tilt", 0)), 3, "X")
        center, radii, egg = Vector(part["center"]), part["radii"], part.get("egg", 0)
        bound = []
        for vert in verts:
            n = vert.co.copy()
            if part.get("poleAxis") == "Y":
                n = Vector((n.x, -n.z, n.y))
            widen = 1 + egg * n.y
            vert.co = center + tilt @ Vector((n.x * radii[0] * widen, n.y * radii[1], n.z * radii[2] * widen))
            bound.append((vert, n))
        self.bind(bound, bone, color_fn)

    def finish(self, mesh, sharp_angle=50):
        bm = self.bm
        col = bm.loops.layers.color.new("Col")
        for f in bm.faces:
            f.smooth = True
            for loop in f.loops:
                loop[col] = loop.vert[self.paint]
        for e in bm.edges:
            if len(e.link_faces) == 2 and e.calc_face_angle(0) > math.radians(sharp_angle):
                e.smooth = False
        bm.verts.layers.float_color.remove(self.paint)
        bm.normal_update()
        bm.to_mesh(mesh)
        bm.free()


def mix(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def shade(color, n_z):
    """Top-lit painterly gradient: darker underneath."""
    return tuple(ch * (0.72 + 0.38 * (n_z + 1) / 2) for ch in color)


def build_mesh(form, bone_names, name):
    pal = form["palette"]
    mb = MeshBuilder(bone_names, pal, seed=zlib.crc32(name.encode()))

    # Cephalothorax: pale midline stripe on top, belly underneath.
    def ceph_color(n):
        top = mix(pal["base"], pal["accent"], 0.45 * max(0.0, 1 - abs(n.x) * 4) * max(0.0, n.z))
        return shade(mix(top, pal["belly"], max(0.0, -n.z)), n.z)

    mb.ellipsoid(form["ceph"], "Cephalothorax", ceph_color)

    # Abdomen: pale folium (leaf mark) down the back, notched into bands, darker tip.
    def abdomen_color(n):
        leaf = max(0.0, 1 - abs(n.x) / 0.5) * max(0.0, n.z) * (0.55 + 0.45 * math.cos(n.y * math.pi * 2.5))
        color = mix(pal["base"], pal["accent"], min(1.0, leaf * 1.3))
        color = mix(color, pal["dark"], max(0.0, n.y - 0.65) * 1.6)
        return shade(mix(color, pal["belly"], max(0.0, -n.z) * 0.8), n.z)

    mb.ellipsoid(form["abdomen"], "Abdomen", abdomen_color)

    # Eyes, mirrored, on the ceph surface.
    for eye in form["eyes"]:
        for side in SIDES:
            d = Vector(eye["dir"])
            d.x *= SIDES[side]
            normal = d.normalized()
            pos = ellipsoid_point(form["ceph"], normal) + normal * eye["r"] * 0.35
            mb.ball(pos, eye["r"], "Cephalothorax", pal["eye"], eye["sub"])

    # Spinnerets.
    spin = form["spinnerets"]
    base = ellipsoid_point(form["abdomen"], spin["dir"])
    tip = base + (Matrix.Rotation(math.radians(form["abdomen"]["tilt"]), 3, "X") @ Vector(spin["dir"])).normalized() * spin["length"]
    mb.tube(base, tip, (spin["radius"], spin["radius"] * 0.8, spin["radius"] * 0.3), "Spinnerets",
            lambda t: pal["dark"], sides=5)

    chel, palps, legs = form["chelicerae"], form["palps"], form["legs"]
    for side in SIDES:
        # Chelicerae and fangs.
        r = chel["radius"]
        mb.tube(mirror(chel["base"], side), mirror(chel["tip"], side), (r, r, r * 0.7), f"Chelicera_{side}",
                lambda t: shade(pal["base"], 0.2 - t))
        mb.tube(mirror(chel["tip"], side), mirror(chel["fangTip"], side), (r * 0.45, r * 0.3, 0.004), f"Fang_{side}",
                lambda t: mix(pal["fang"], pal["fangTip"], t), sides=5, overlap=0.0)

        # Pedipalps.
        r = palps["radius"]
        upper, lower = (f"Pedipalp_{side}_{s}" for s in PALP_SEGMENTS)
        mb.tube(mirror(palps["base"], side), mirror(palps["joint"], side), (r, r * 1.1, r * 0.9), upper,
                lambda t: shade(pal["base"], 0.3))
        mb.ball(mirror(palps["joint"], side), r * 1.15, lower, pal["accent"])
        mb.tube(mirror(palps["joint"], side), mirror(palps["tip"], side), (r * 0.9, r * 1.2, r * 0.7), lower,
                lambda t: mix(pal["base"], pal["dark"], t))

        # Legs: bulging segments, pale band at each joint, dark tips.
        rh, rk, ra, rf = legs["radius"]
        for i, pair in enumerate(PAIRS):
            hip, knee, ankle, foot = leg_joints(form, side, i)
            femur, tibia, tarsus = (leg_name(side, pair, s) for s in LEG_SEGMENTS)

            def banded(t):
                return shade(pal["accent"] if t > legs["band"] + 0.01 else pal["base"], 0.4 - t * 0.4)

            mb.ball(hip, rh * 1.15, femur, pal["dark"])
            mb.tube(hip, knee, (rh, rh * 1.2, rk), femur, banded, sides=legs["sides"], band=legs["band"])
            mb.ball(knee, rk * 1.3, tibia, pal["accent"])
            mb.tube(knee, ankle, (rk, rk * 1.1, ra), tibia, banded, sides=legs["sides"], band=legs["band"])
            mb.ball(ankle, ra * 1.3, tarsus, pal["accent"])
            mb.tube(ankle, foot, (ra, ra * 0.9, rf), tarsus,
                    lambda t: shade(mix(pal["base"], pal["dark"], t), -0.3), sides=legs["sides"], overlap=0.0)

    mesh = bpy.data.meshes.new(name)
    mb.finish(mesh)
    return mesh


# ---------------------------------------------------------------- scene

def build(form_id):
    form = FORMS[form_id]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.render.fps = 30

    rig = build_armature(form, "SpiderRig")
    bone_names = [b.name for b in rig.data.bones]

    mesh = build_mesh(form, bone_names, form["displayName"])
    body = bpy.data.objects.new(form["displayName"], mesh)
    scene.collection.objects.link(body)
    for bone_name in bone_names:
        body.vertex_groups.new(name=bone_name)
    body.parent = rig
    body.modifiers.new("Armature", "ARMATURE").object = rig

    mat = bpy.data.materials.new(f"{form['displayName']}_VertexColor")
    nodes = mat.node_tree.nodes
    attr = nodes.new("ShaderNodeVertexColor")
    attr.layer_name = "Col"
    bsdf = nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.75
    mat.node_tree.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    mesh.materials.append(mat)

    if form["scale"] != 1.0:
        rig.scale = (form["scale"],) * 3
        for obj in (rig, body):
            obj.select_set(True)
        bpy.context.view_layer.objects.active = rig
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    clips = spider_anims.build_clips(rig)
    return form, rig, body, clips


def report(form, rig, body):
    tris = sum(len(p.vertices) - 2 for p in body.data.polygons)
    print(f"[spider] {form['displayName']}: {tris} tris (budget {form['triBudget']}), "
          f"{len(body.data.vertices)} verts, {len(rig.data.bones)} bones")
    unbound = [v.index for v in body.data.vertices if len(v.groups) != 1]
    if unbound:
        raise RuntimeError(f"{len(unbound)} vertices are not bound to exactly one bone")
    if tris > form["triBudget"]:
        raise RuntimeError("over triangle budget")
    feet = [rig.data.bones[leg_name(s, p, "Tarsus")].tail_local.z for s in SIDES for p in PAIRS]
    print(f"[spider] foot heights: min {min(feet):.3f} max {max(feet):.3f}")
    xs = [rig.data.bones[leg_name(s, p, "Tarsus")].tail_local.x for s in SIDES for p in PAIRS]
    ys = [v.co.y for v in body.data.vertices]
    print(f"[spider] leg span {max(xs) - min(xs):.2f} studs, body length {max(ys) - min(ys):.2f} studs")


def export_fbx(path, rig, body, bake):
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    body.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.export_scene.fbx(
        filepath=path,
        use_selection=True,
        object_types={"ARMATURE", "MESH"},
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_NONE",
        axis_forward="-Z",
        axis_up="Y",
        use_mesh_modifiers=True,
        use_triangles=True,
        mesh_smooth_type="FACE",
        colors_type="SRGB",
        add_leaf_bones=False,
        primary_bone_axis="Y",
        secondary_bone_axis="X",
        armature_nodetype="NULL",
        bake_anim=bake,
        bake_anim_use_all_actions=False,
        bake_anim_use_nla_strips=False,
        bake_anim_force_startend_keying=True,
        bake_anim_step=1.0,
        bake_anim_simplify_factor=0.0,
    )
    print(f"[spider] exported {os.path.relpath(path, BLENDER_DIR)}")


def main():
    args = parse_args()
    form, rig, body, clips = build(args.form)
    report(form, rig, body)

    os.makedirs(os.path.join(BLENDER_DIR, "sources"), exist_ok=True)
    os.makedirs(os.path.join(BLENDER_DIR, "exports"), exist_ok=True)

    if not args.no_export:
        rig.animation_data.action = None
        rig.data.pose_position = "REST"
        export_fbx(os.path.join(BLENDER_DIR, "exports", f"{args.form}.fbx"), rig, body, bake=False)
        rig.data.pose_position = "POSE"
        for clip_name, action in clips.items() if args.clip_fbx else ():
            spider_anims.use_clip(rig, action)
            export_fbx(os.path.join(BLENDER_DIR, "exports", f"{args.form}_{clip_name}.fbx"), rig, body, bake=True)

    spider_anims.use_clip(rig, clips["Idle"])
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BLENDER_DIR, "sources", f"{args.form}.blend"), compress=True)
    print(f"[spider] saved sources/{args.form}.blend")


if __name__ == "__main__":
    main()
