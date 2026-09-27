"""Render preview sheets of a built map (Cycles CPU, headless). Nothing is saved back to the .blend.

    python blender/scripts/maps/render_map.py --map lobby
Writes JPEG sheets to blender/renders/maps/ (Pillow stitches them). The Spiderling from
sources/spiderling.blend is dropped on spawn / pose / station markers for scale: previews only,
never exported.
"""

import argparse
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from map_config import MAPS  # noqa: E402

BLENDER_DIR = os.path.dirname(os.path.dirname(HERE))
OUT_DIR = os.path.join(BLENDER_DIR, "renders", "maps")


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", required=True, choices=sorted(MAPS))
    parser.add_argument("--samples", type=int, default=20)
    parser.add_argument("--only", nargs="*", help="render only these sheets")
    parser.add_argument("--scale", type=float, default=1.0, help="resolution scale for quick looks")
    return parser.parse_args(argv)


# ---------------------------------------------------------------- scene

def setup(samples, look):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 4
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = look.get("look", "None")
    scene.view_settings.exposure = look.get("exposure", 0.0)

    world = bpy.data.worlds.new("PreviewWorld")
    scene.world = world
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (*look["sky"], 1.0)
    bg.inputs["Strength"].default_value = look["skyStrength"]

    sun = bpy.data.objects.new("PreviewSun", bpy.data.lights.new("PreviewSun", "SUN"))
    sun.data.energy = look["sunEnergy"]
    sun.data.color = look["sunColor"]
    sun.data.angle = math.radians(look.get("sunAngle", 6))
    elev, azim = look["sun"]
    sun.rotation_euler = (math.radians(90 - elev), 0, math.radians(azim))
    scene.collection.objects.link(sun)

    cam = bpy.data.objects.new("PreviewCam", bpy.data.cameras.new("PreviewCam"))
    cam.data.clip_end = 5000
    scene.collection.objects.link(cam)
    scene.camera = cam
    return scene, cam


def add_spiders(markers, prefixes):
    """Append the Spiderling mesh (rest pose, no rig) and drop linked copies on markers."""
    path = os.path.join(BLENDER_DIR, "sources", "spiderling.blend")
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = ["Spiderling"]
    proto = dst.objects[0]
    proto.parent = None
    proto.modifiers.clear()
    placed = []
    for m in markers:
        if not any(m.name.startswith("MARKER_" + p) for p in prefixes):
            continue
        obj = bpy.data.objects.new(f"PreviewSpider_{m.name}", proto.data)
        pos = m.matrix_world.translation
        # the Spiderling faces -Y; turn it toward the map centre
        yaw = math.atan2(-pos.x, pos.y) if pos.xy.length > 1 else 0.0
        obj.matrix_world = Matrix.Translation(pos) @ Matrix.Rotation(yaw, 4, "Z")
        bpy.context.scene.collection.objects.link(obj)
        placed.append(obj)
    return placed


def glow_previews(patterns, color, strength):
    """Preview-only emission for firefly bulbs and the like (export keeps one vertex-colour material)."""
    mat = bpy.data.materials.new("PreviewGlow")
    nodes = mat.node_tree.nodes
    em = nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1)
    em.inputs["Strength"].default_value = strength
    mat.node_tree.links.new(em.outputs["Emission"], nodes["Material Output"].inputs["Surface"])
    for obj in list(bpy.data.objects):
        if obj.type == "MESH" and any(p in obj.name for p in patterns):
            obj.material_slots[0].link = "OBJECT"
            obj.material_slots[0].material = mat
            light = bpy.data.objects.new(f"PreviewLight_{obj.name}", bpy.data.lights.new(obj.name, "POINT"))
            light.data.energy = strength * 400
            light.data.color = color
            light.data.shadow_soft_size = 1.0
            light.location = obj.matrix_world.translation + Vector((0, 0, 1.5))
            bpy.context.scene.collection.objects.link(light)


def aim(cam, loc, target, lens=None, fov=None, ortho=None):
    cam.location = Vector(loc)
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    if ortho:
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = ortho
    else:
        cam.data.type = "PERSP"
        if fov:  # vertical field of view, like Roblox's Camera.FieldOfView
            cam.data.sensor_fit = "VERTICAL"
            cam.data.angle_y = math.radians(fov)
        else:
            cam.data.sensor_fit = "AUTO"
            cam.data.lens = lens or 30


def marker_pos(name):
    obj = bpy.data.objects.get(name)
    if not obj:
        raise RuntimeError(f"missing {name}")
    return obj.matrix_world.translation.copy()


def resolve(p):
    """A view point is (x, y, z), a marker name, or (marker name, (dx, dy, dz))."""
    if isinstance(p, str):
        return marker_pos(p)
    if isinstance(p[0], str):
        return marker_pos(p[0]) + Vector(p[1])
    return Vector(p)


def render_view(scene, cam, view, path, scale):
    size = view.get("size", (800, 600))
    scene.render.resolution_x, scene.render.resolution_y = int(size[0] * scale), int(size[1] * scale)
    if view.get("station"):  # stand behind the station marker (hub side) and look at the station
        m = marker_pos("MARKER_Station_" + view["station"])
        d = Vector((-m.x, -m.y, 0)).normalized()
        side = Vector((-d.y, d.x, 0)) * view.get("side", 8)
        loc, target = m + d * view.get("back", 26) + side + Vector((0, 0, view.get("up", 12))), m - d * 22 + Vector((0, 0, 9))
    else:
        loc, target = resolve(view["loc"]), resolve(view["target"])
        if view.get("room"):  # room-local view; rooms are spread out by their layout offset in the .blend
            off = Vector((*bpy.data.collections[view["room"]]["layoutOffset"], 0))
            loc, target = loc + off, target + off
    aim(cam, loc, target, view.get("lens"), view.get("fov"), view.get("ortho"))
    hidden = []
    if view.get("only"):
        for obj in bpy.data.objects:
            if obj.type == "MESH" and not obj.name.startswith("Preview"):
                keep = any(obj.name in c.all_objects for c in (bpy.data.collections[n] for n in view["only"]))
                if not keep and not obj.hide_render:
                    obj.hide_render = True
                    hidden.append(obj)
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    for obj in hidden:
        obj.hide_render = False
    return path


def stitch(paths, labels, out, cols, overlays):
    from PIL import Image, ImageDraw
    images = [Image.open(p).convert("RGB") for p in paths]
    w = max(i.size[0] for i in images)
    h = max(i.size[1] for i in images)
    rows = (len(images) + cols - 1) // cols
    sheet = Image.new("RGB", (w * cols, h * rows), (20, 18, 16))
    for k, (img, label, overlay) in enumerate(zip(images, labels, overlays)):
        x, y = (k % cols) * w, (k // cols) * h
        if overlay == "menu_ui":  # menu UI covers the left third
            shade = Image.new("RGB", (img.size[0] // 3, img.size[1]), (10, 10, 18))
            img.paste(Image.blend(img.crop((0, 0, img.size[0] // 3, img.size[1])), shade, 0.55), (0, 0))
            d = ImageDraw.Draw(img)
            d.line((img.size[0] // 3, 0, img.size[0] // 3, img.size[1]), fill=(200, 190, 160), width=2)
            d.text((16, img.size[1] // 2), "menu UI (left third)", fill=(220, 210, 190))
        sheet.paste(img, (x, y))
        ImageDraw.Draw(sheet).text((x + 12, y + 10), label, fill=(245, 238, 220))
    sheet.save(out, quality=88)
    for p in paths:
        os.remove(p)
    print(f"[render] wrote {os.path.relpath(out, BLENDER_DIR)}")


def main():
    args = parse_args()
    cfg = MAPS[args.map]
    rcfg = cfg["render"]
    bpy.ops.wm.open_mainfile(filepath=os.path.join(BLENDER_DIR, "sources", "maps", f"{args.map}.blend"))
    scene, cam = setup(args.samples, rcfg["look"])
    markers = [o for o in bpy.data.objects if o.name.startswith("MARKER_")]
    for m in markers:
        m.hide_render = True
    add_spiders(markers, rcfg.get("spiders", ("PlayerSpawn", "SpiderPose")))
    if rcfg.get("glow"):
        glow_previews(*rcfg["glow"])
    os.makedirs(OUT_DIR, exist_ok=True)
    for sheet in rcfg["sheets"]:
        if args.only and sheet["name"] not in args.only:
            continue
        paths, labels, overlays = [], [], []
        if sheet.get("rooms"):
            views = []
            for rid, rc in cfg["rooms"].items():
                W, D = rc["cells"][0] * cfg["grid"], rc["cells"][1] * cfg["grid"]
                views.append({"label": rid, "size": sheet.get("size", (640, 480)), "room": rid, "only": (rid,),
                              "loc": (W * 0.55, -D * 1.05, max(W, D) * 0.95), "target": (0, 0, 6), "lens": 24})
        else:
            views = sheet["views"]
        for k, view in enumerate(views):
            paths.append(render_view(scene, cam, view, os.path.join(OUT_DIR, f"_{sheet['name']}_{k}.png"), args.scale))
            labels.append(view["label"])
            overlays.append(view.get("overlay"))
        stitch(paths, labels, os.path.join(OUT_DIR, f"{sheet['name']}.jpg"), sheet.get("cols", 2), overlays)


if __name__ == "__main__":
    main()
