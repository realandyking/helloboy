"""Spider rig clips. Keys are rotations in each bone's local space (plus a small ceph bob),
so every form that shares the Spider rig can play them. All keys are eased Bezier.

Clip settings live in spider_config.CLIPS. Loop clips end on their first pose.
"""

import math

import bpy

from spider_config import CLIPS, PAIRS, PALP_SEGMENTS, SIDES


def leg(side, pair, segment):
    return f"Leg_{side}{pair}_{segment}"


def reset_pose(rig):
    for pb in rig.pose.bones:
        pb.rotation_mode = "XYZ"
        pb.location = (0, 0, 0)
        pb.rotation_euler = (0, 0, 0)
        pb.scale = (1, 1, 1)


def key(rig, bone, frame, rot=None, loc=None):
    pb = rig.pose.bones[bone]
    if rot is not None:
        pb.rotation_euler = [math.radians(a) for a in rot]
        pb.keyframe_insert("rotation_euler", frame=frame, group=bone)
    if loc is not None:
        pb.location = loc
        pb.keyframe_insert("location", frame=frame, group=bone)


def fcurves(action):
    """F-curves of the action's first slot (layered actions, Blender 4.4+), or legacy fcurves."""
    if hasattr(action, "slots") and len(action.slots):
        from bpy_extras import anim_utils
        channelbag = anim_utils.action_get_channelbag_for_slot(action, action.slots[0])
        return channelbag.fcurves if channelbag else []
    return action.fcurves


def ease(action):
    for fc in fcurves(action):
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"
            kp.easing = "AUTO"
            kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
        fc.update()


def use_clip(rig, action):
    reset_pose(rig)
    rig.animation_data_create()
    rig.animation_data.action = action
    if hasattr(action, "slots") and len(action.slots):
        rig.animation_data.action_slot = action.slots[0]
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 0, int(action["frames"])
    scene.frame_set(0)


# ---------------------------------------------------------------- clips

def build_idle(rig, clip):
    n = clip["frames"]
    mid = n // 2
    key(rig, "Abdomen", 0, rot=(0, 0, 0))
    key(rig, "Abdomen", mid, rot=(clip["breath"], 0, 0))
    key(rig, "Abdomen", n, rot=(0, 0, 0))
    key(rig, "Cephalothorax", 0, loc=(0, 0, 0))
    key(rig, "Cephalothorax", mid, loc=(0, 0, -clip["bob"]))
    key(rig, "Cephalothorax", n, loc=(0, 0, 0))

    # Palps tap one after the other; fangs flex once.
    tap = clip["palpTap"]
    for side, start in (("L", int(n * 0.12)), ("R", int(n * 0.55))):
        upper, lower = (f"Pedipalp_{side}_{s}" for s in PALP_SEGMENTS)
        for bone, amount in ((upper, tap), (lower, -tap * 0.6)):
            key(rig, bone, 0, rot=(0, 0, 0))
            key(rig, bone, start, rot=(0, 0, 0))
            key(rig, bone, start + 6, rot=(amount, 0, 0))
            key(rig, bone, start + 12, rot=(0, 0, 0))
            key(rig, bone, n, rot=(0, 0, 0))
        fang = f"Fang_{side}"
        flex_at = int(n * 0.3)
        key(rig, fang, 0, rot=(0, 0, 0))
        key(rig, fang, flex_at, rot=(clip["fangFlex"], 0, 0))
        key(rig, fang, flex_at + 6, rot=(0, 0, 0))
        key(rig, fang, n, rot=(0, 0, 0))

    # Legs shift weight slightly, in the same two groups the walk uses.
    for side in SIDES:
        for pair in PAIRS:
            sign = 1 if f"{side}{pair}" in CLIPS["Walk"]["groupA"] else -1
            femur = leg(side, pair, "Femur")
            key(rig, femur, 0, rot=(0, 0, 0))
            key(rig, femur, mid, rot=(sign * clip["legShift"], 0, 0))
            key(rig, femur, n, rot=(0, 0, 0))


def build_walk(rig, clip):
    n = clip["frames"]
    frames = [n * k / 4 for k in range(5)]
    # A leg's own cycle at quarter points: (femur lift, swing -1 back..+1 forward, tibia tuck)
    cycle = [(0, -1, 0), (clip["lift"], 0, clip["tuck"]), (0, 1, 0), (-clip["push"], 0, 0)]
    for side, sign in SIDES.items():
        for i, pair in enumerate(PAIRS):
            offset = 0 if f"{side}{pair}" in clip["groupA"] else 2
            for k, frame in enumerate(frames):
                lift, swing, tuck = cycle[(k + offset) % 4]
                key(rig, leg(side, pair, "Femur"), frame, rot=(lift, 0, sign * swing * clip["swing"][i]))
                key(rig, leg(side, pair, "Tibia"), frame, rot=(tuck, 0, 0))
                key(rig, leg(side, pair, "Tarsus"), frame, rot=(-tuck * 0.5, 0, 0))

    # The body dips when a leg group plants (twice per cycle) and rolls toward the planted side.
    bob, sway, ab = clip["bob"], clip["sway"], clip["abdomenSway"]
    for k, frame in enumerate(frames):
        planted = k % 2 == 0
        key(rig, "Cephalothorax", frame,
            loc=(0, 0, -bob if planted else bob * 0.6),
            rot=(0, sway * (0, 1, 0, -1, 0)[k], 0))
        key(rig, "Abdomen", frame, rot=(0, 0, ab * (-1, 0, 1, 0, -1)[k]))
        for side, phase in (("L", 0), ("R", 2)):
            key(rig, f"Pedipalp_{side}_{PALP_SEGMENTS[0]}", frame, rot=((8, 0, -4, 0)[(k + phase) % 4], 0, 0))


BUILDERS = {"Idle": build_idle, "Walk": build_walk}


def build_clips(rig):
    clips = {}
    for name, clip in CLIPS.items():
        reset_pose(rig)
        action = bpy.data.actions.new(name)
        action.use_fake_user = True
        action["frames"] = clip["frames"]
        action["loop"] = clip["loop"]
        rig.animation_data_create()
        rig.animation_data.action = action
        BUILDERS[name](rig, clip)
        ease(action)
        clips[name] = action
    reset_pose(rig)
    rig.animation_data.action = None
    return clips


assert all(name in BUILDERS for name in CLIPS), "every clip in CLIPS needs a builder"
