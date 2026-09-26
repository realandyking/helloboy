"""Data for the Spider rig pipeline: forms (proportions, palette) and animation clips.

Every form shares one skeleton (same bone names and hierarchy), so a clip made on one
form plays on all of them. A new form is a new FORMS entry, not new code.

Space: 1 Blender unit = 1 stud. The spider faces -Y, so its left side is +X.
"""

# Leg pairs front to back. The bone name pattern is Leg_<Side><Pair>_<Segment>.
PAIRS = ("1", "2", "3", "4")
SIDES = {"L": 1, "R": -1}  # sign of X for each side
LEG_SEGMENTS = ("Femur", "Tibia", "Tarsus")
PALP_SEGMENTS = ("Upper", "Lower")

FORMS = {
    "spiderling": {
        "displayName": "Spiderling",
        "scale": 1.0,
        "triBudget": 3000,
        "rootPart": (0.0, 0.0, 1.0),  # HumanoidRootPart bone: body centre, over the leg footprint
        "ceph": {"center": (0.0, -0.25, 1.0), "radii": (0.55, 0.68, 0.36), "segments": (10, 7)},
        "abdomen": {
            "center": (0.0, 1.3, 1.15),
            "radii": (0.75, 0.95, 0.70),
            "segments": (12, 8),
            "poleAxis": "Y",  # poles front/back, so rings run across the body and markings stay clean
            "tilt": 8,     # degrees, back end up
            "egg": 0.12,   # how much wider the back half is
        },
        "legs": {
            "yaw": (40, 75, 110, 145),        # degrees from forward, per pair
            "femur": (1.10, 1.00, 0.90, 1.05),  # lengths per pair
            "tibia": (1.00, 0.90, 0.80, 0.95),
            "femurPitch": 40,                 # degrees above horizontal
            "tibiaPitch": -55,
            "tarsusPitch": -75,               # the tarsus always reaches the ground
            "hipInset": 0.62,                 # hip position as a fraction of ceph radius
            "hipDrop": -0.06,
            "radius": (0.10, 0.08, 0.055, 0.02),  # hip, knee, ankle, foot
            "sides": 6,
            "band": 0.86,                     # where the pale joint band starts on femur and tibia
        },
        "chelicerae": {"base": (0.14, -0.84, 0.90), "tip": (0.13, -1.02, 0.64), "fangTip": (0.05, -1.06, 0.50), "radius": 0.10},
        "palps": {"base": (0.30, -0.80, 0.86), "joint": (0.40, -1.12, 0.95), "tip": (0.36, -1.34, 0.62), "radius": 0.055},
        # Eyes sit on the ceph surface. dir is in the ellipsoid's unit space. r is radius, sub is ico subdivisions.
        "eyes": (
            {"dir": (0.22, -0.90, 0.40), "r": 0.10, "sub": 2},
            {"dir": (0.45, -0.78, 0.45), "r": 0.06, "sub": 1},
            {"dir": (0.20, -0.62, 0.78), "r": 0.055, "sub": 1},
            {"dir": (0.70, -0.55, 0.45), "r": 0.045, "sub": 1},
        ),
        "spinnerets": {"dir": (0.0, 0.93, -0.36), "length": 0.22, "radius": 0.09},
        "palette": {  # sRGB 0-1
            "base": (0.22, 0.14, 0.09),
            "dark": (0.08, 0.055, 0.045),
            "accent": (0.74, 0.56, 0.34),
            "belly": (0.33, 0.24, 0.17),
            "eye": (0.03, 0.03, 0.05),
            "fang": (0.10, 0.06, 0.05),
            "fangTip": (0.55, 0.16, 0.10),
            "jitter": 0.07,  # hand-painted value noise per vertex
        },
    },
}

# Clips are rotations in degrees in each bone's local space. For every leg, palp, ceph
# and abdomen bone, +X lifts the bone's tip. On legs, +Z swings a left leg forward and a
# right leg back, so leg keys use swing * side sign.
CLIPS = {
    "Idle": {
        "frames": 60,
        "loop": True,
        "breath": 3.0,        # abdomen pitch
        "bob": 0.015,         # ceph drop in studs
        "palpTap": 12.0,
        "fangFlex": 8.0,
        "legShift": 1.5,
    },
    "Walk": {
        "frames": 24,         # one full cycle; speed it up in game to match walk speed
        "loop": True,
        "swing": (18, 15, 15, 16),  # per pair, degrees each side of neutral
        "lift": 18,           # femur lift at mid-swing
        "tuck": 12,           # tibia tuck at mid-swing
        "push": 3,            # femur press at mid-stance
        "bob": 0.03,
        "sway": 2.0,          # ceph roll
        "abdomenSway": 3.0,
        # Alternating tetrapod gait. These legs move together, and the rest move half a cycle later.
        "groupA": ("L1", "R2", "L3", "R4"),
    },
}
