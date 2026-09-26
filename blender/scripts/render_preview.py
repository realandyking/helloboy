"""Render preview sheets of a built spider form (Cycles CPU, headless). Nothing is saved back to the .blend.

    python blender/scripts/render_preview.py --form spiderling
Writes blender/renders/<form>_views.jpg and <form>_walk.jpg (Pillow needed to stitch sheets).
"""

import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.dirname(HERE)

VIEWS = {  # name: (camera location, look-at target, orthographic scale or None)
    "three_quarter": ((5.2, -6.4, 4.4), (0, 0.5, 0.7), None),
    "front": ((0, -9.0, 1.4), (0, 0, 1.0), None),
    "top": ((0, 0.6, 12.0), (0, 0.6, 0), 6.5),
    "side": ((9.5, 0.4, 1.8), (0, 0.4, 0.9), None),
}


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser()
    parser.add_argument("--form", default="spiderling")
    parser.add_argument("--samples", type=int, default=24)
    return parser.parse_args(argv)


def setup_scene(samples):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 800, 600
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "AgX"

    world = bpy.data.worlds.new("PreviewWorld")
    scene.world = world
    world.color = (0.35, 0.40, 0.45)
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.32, 0.38, 0.45, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.8

    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 3.5
    sun.data.color = (1.0, 0.93, 0.82)
    sun.data.angle = math.radians(8)
    sun.rotation_euler = (math.radians(50), 0, math.radians(35))
    scene.collection.objects.link(sun)

    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
    ground = bpy.context.active_object
    mat = bpy.data.materials.new("Ground")
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.16, 0.19, 0.12, 1)
    mat.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 1.0
    ground.data.materials.append(mat)

    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    cam.data.lens = 50
    scene.collection.objects.link(cam)
    scene.camera = cam
    return scene, cam


def aim(cam, view):
    location, target, ortho = VIEWS[view]
    cam.location = location
    cam.rotation_euler = (Vector(target) - Vector(location)).to_track_quat("-Z", "Y").to_euler()
    cam.data.type = "ORTHO" if ortho else "PERSP"
    if ortho:
        cam.data.ortho_scale = ortho


def render(scene, path):
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path


def stitch(paths, out, labels):
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("[preview] Pillow not installed; leaving individual frames")
        return
    images = [Image.open(p) for p in paths]
    w, h = images[0].size
    sheet = Image.new("RGB", (w * len(images), h))
    draw = ImageDraw.Draw(sheet)
    for i, (img, label) in enumerate(zip(images, labels)):
        sheet.paste(img, (i * w, 0))
        draw.text((i * w + 12, 10), label, fill=(240, 235, 220))
    sheet.save(out, quality=88)
    for p in paths:
        os.remove(p)
    print(f"[preview] wrote {os.path.relpath(out, BLENDER_DIR)}")


def main():
    args = parse_args()
    bpy.ops.wm.open_mainfile(filepath=os.path.join(BLENDER_DIR, "sources", f"{args.form}.blend"))
    scene, cam = setup_scene(args.samples)
    rig = bpy.data.objects["SpiderRig"]
    out_dir = os.path.join(BLENDER_DIR, "renders")
    os.makedirs(out_dir, exist_ok=True)

    rig.animation_data.action = None
    for pb in rig.pose.bones:
        pb.location, pb.rotation_euler = (0, 0, 0), (0, 0, 0)
    views = ["three_quarter", "front", "top"]
    paths = []
    for view in views:
        aim(cam, view)
        paths.append(render(scene, os.path.join(out_dir, f"_{view}.png")))
    stitch(paths, os.path.join(out_dir, f"{args.form}_views.jpg"), views)

    walk = bpy.data.actions["Walk"]
    rig.animation_data.action = walk
    if hasattr(walk, "slots") and len(walk.slots):
        rig.animation_data.action_slot = walk.slots[0]
    frames = [0, 6, 12, 18]
    aim(cam, "three_quarter")
    paths = []
    for frame in frames:
        scene.frame_set(frame)
        paths.append(render(scene, os.path.join(out_dir, f"_walk{frame}.png")))
    stitch(paths, os.path.join(out_dir, f"{args.form}_walk.jpg"), [f"Walk f{f}" for f in frames])


if __name__ == "__main__":
    main()
