"""Data for the Spider Quest map builds: palette, shading, kit props, and one entry per map.

Tune here, not in code. A new room or map is a new entry. Units are studs (1 Blender unit = 1 stud),
Z is up and north is +Y. Colours are sRGB 0-1.

Scale guide (1 real cm ~ 4 studs): Spiderling ~3.6 wide x 4.3 long x 1.9 tall; grass blades 25-45;
mushrooms 10-35; pebbles 4-15; acorns ~10; oak leaves ~40 long; the hub stump ~260 across.
"""

PALETTE = {
    # moss and greens
    "moss": (0.29, 0.40, 0.17),
    "moss_light": (0.50, 0.58, 0.26),
    "moss_dark": (0.15, 0.23, 0.11),
    "lichen": (0.56, 0.60, 0.47),
    "grass": (0.33, 0.47, 0.19),
    "grass_dark": (0.16, 0.27, 0.11),
    "grass_tip": (0.66, 0.62, 0.34),
    "clover": (0.27, 0.46, 0.21),
    "clover_mark": (0.55, 0.66, 0.42),
    # wood and earth
    "bark": (0.29, 0.20, 0.14),
    "bark_dark": (0.15, 0.10, 0.08),
    "bark_light": (0.45, 0.34, 0.24),
    "wood_rot": (0.52, 0.33, 0.18),
    "wood_pale": (0.72, 0.57, 0.39),
    "wood_dark": (0.30, 0.18, 0.10),
    "loam": (0.23, 0.16, 0.11),
    "loam_light": (0.37, 0.27, 0.18),
    "mulch": (0.42, 0.26, 0.14),
    "mulch_light": (0.60, 0.42, 0.24),
    "tunnel": (0.035, 0.025, 0.025),
    # leaves
    "leaf_brown": (0.47, 0.29, 0.14),
    "leaf_orange": (0.66, 0.36, 0.13),
    "leaf_dry": (0.66, 0.50, 0.27),
    "leaf_red": (0.52, 0.20, 0.11),
    "leaf_green": (0.36, 0.40, 0.17),
    # stone
    "stone": (0.43, 0.41, 0.37),
    "stone_warm": (0.50, 0.45, 0.37),
    "stone_cool": (0.37, 0.37, 0.36),
    "stone_dark": (0.24, 0.23, 0.22),
    # fungi
    "mush_stem": (0.84, 0.78, 0.64),
    "mush_cream": (0.88, 0.80, 0.63),
    "mush_red": (0.62, 0.19, 0.11),
    "mush_rust": (0.66, 0.35, 0.15),
    "mush_tan": (0.68, 0.53, 0.34),
    "mush_brown": (0.40, 0.26, 0.15),
    "gill": (0.73, 0.63, 0.50),
    "gill_dark": (0.52, 0.42, 0.32),
    "shelf_band": ((0.55, 0.30, 0.14), (0.70, 0.50, 0.27), (0.40, 0.23, 0.13), (0.82, 0.70, 0.50)),
    "shelf_edge": (0.90, 0.84, 0.68),
    "shelf_under": (0.80, 0.72, 0.57),
    # silk, dew, amber, critters
    "silk": (0.84, 0.83, 0.78),
    "silk_shade": (0.64, 0.63, 0.61),
    "dew": (0.70, 0.84, 0.88),
    "dew_hi": (0.95, 0.98, 1.0),
    "amber": (0.93, 0.60, 0.15),
    "amber_glow": (1.0, 0.82, 0.38),
    "firefly": (1.0, 0.86, 0.36),
    "acorn": (0.56, 0.36, 0.16),
    "acorn_dark": (0.36, 0.22, 0.11),
    "acorn_cap": (0.45, 0.36, 0.24),
    "acorn_cap_dark": (0.30, 0.23, 0.15),
    "beetle": (0.08, 0.17, 0.16),
    "beetle_sheen": (0.22, 0.42, 0.36),
    "beetle_gold": (0.62, 0.50, 0.20),
    "exo": (0.74, 0.60, 0.40),
    "exo_dark": (0.48, 0.36, 0.23),
    "thorn": (0.50, 0.30, 0.20),
    "nut": (0.58, 0.40, 0.21),
    "nut_dark": (0.35, 0.22, 0.11),
    "nut_inner": (0.80, 0.68, 0.48),
    "ant_earth": (0.40, 0.28, 0.18),
    "ant_earth_light": (0.56, 0.42, 0.28),
}

# Baked lighting. value = light(normal.z) * (1 - occlusion * ao); lit areas lean warm, shade leans cool purple.
SHADING = {
    "light": (0.66, 1.06),        # bottom-facing .. top-facing
    "occlusion": 0.58,            # how dark full occlusion gets
    "aoRays": 14,
    "aoDistance": 30.0,           # studs; maps can override
    "aoFalloff": 0.8,
    "kitAoScale": 0.7,            # kit props: occlusion distance = size * this
    "shadowTint": (0.84, 0.80, 1.04),
    "litTint": (1.05, 1.0, 0.90),
    "jitter": 0.065,              # hand-painted value noise per vertex
    "sharpAngle": 50,             # edges sharper than this are split (faceted look)
}

# Shared kit meshes. Each is built once per variant and placed as linked duplicates.
# gen: generator in map_props.py; params: its keyword arguments (tuples of two numbers = seeded range).
KIT = {
    "mushroom_dome": {"gen": "mushroom", "variants": 3,
                      "params": {"height": (14, 22), "cap": (7, 10), "shape": "dome", "tone": "rust"}},
    "mushroom_red": {"gen": "mushroom", "variants": 2,
                     "params": {"height": (18, 28), "cap": (8, 12), "shape": "dome", "tone": "red", "spots": True}},
    "mushroom_flat": {"gen": "mushroom", "variants": 2,
                      "params": {"height": (20, 32), "cap": (10, 14), "shape": "flat", "tone": "tan"}},
    "mushroom_bell": {"gen": "mushroom", "variants": 2,
                      "params": {"height": (10, 16), "cap": (4, 6), "shape": "bell", "tone": "brown", "segments": 8,
                                 "stem_sides": 5}},
    "mushroom_pillar": {"gen": "mushroom", "variants": 2,
                        "params": {"height": (38, 48), "cap": (13, 16), "shape": "flat", "tone": "rust"}},
    "pebble": {"gen": "pebble", "variants": 4, "params": {"size": (6, 11), "flat": (0.5, 0.75)}},
    "pebble_big": {"gen": "pebble", "variants": 3, "params": {"size": (14, 20), "flat": (0.55, 0.8)}},
    "pebble_small": {"gen": "pebble", "variants": 2, "params": {"size": (3.5, 5.0), "flat": (0.5, 0.7), "subdiv": 1}},
    "acorn": {"gen": "acorn", "variants": 2, "params": {"length": (9, 11)}},
    "acorn_cap": {"gen": "acorn_cap", "variants": 2, "params": {"radius": (4.2, 5.0)}},
    "twig": {"gen": "twig", "variants": 3, "params": {"length": (34, 52), "radius": (1.3, 1.9)}},
    "leaf_oak": {"gen": "leaf", "variants": 4, "params": {"length": (34, 44), "kind": "oak", "curl": (0.15, 0.4)}},
    "leaf_round": {"gen": "leaf", "variants": 2, "params": {"length": (24, 32), "kind": "round", "curl": (0.2, 0.45)}},
    "grass_clump": {"gen": "grass_clump", "variants": 3, "params": {"height": (26, 40), "blades": 8, "spread": 3.5}},
    "grass_tall": {"gen": "grass_clump", "variants": 3, "params": {"height": (46, 64), "blades": 8, "spread": 5.0}},
    "moss_mound": {"gen": "moss_mound", "variants": 3, "params": {"radius": (7, 13), "height": (3, 6)}},
    "clover": {"gen": "clover", "variants": 3, "params": {"height": (10, 18), "leaf": (4.0, 5.5)}},
    "dew": {"gen": "dew", "variants": 1, "params": {"radius": 1.2}},
    "egg_sac": {"gen": "egg_sac", "variants": 2, "params": {"size": (6, 8)}},
    "egg_sac_glow": {"gen": "egg_sac", "variants": 2, "params": {"size": (6, 8), "glow": True}},
    "shelf_small": {"gen": "shelf_fungus", "variants": 2, "ground": False,
                    "params": {"width": (14, 20), "depth": (9, 12), "thick": (4, 5)}},
}

MAPS = {}

# ---------------------------------------------------------------- main menu backdrop (its own place)
# A dusk diorama about 150 x 100 studs. The menu camera looks north (+Y). Menu UI covers the left third
# of a 16:9 frame, so the web and the spider pose sit right of centre. Studio: CFrame.lookAt(MenuCamera,
# MenuFocus) with FieldOfView = camera.fov; the showcase spider stands on SpiderPose facing the camera.
MAPS["main_menu"] = {
    "kind": "diorama",
    "title": "Main menu backdrop",
    "budget": 25000,
    "shading": {"aoDistance": 22.0},
    "camera": {"pos": (-4, -36, 10), "focus": (10, 16, 16), "fov": 50},
    "ground": {
        "xs": (-420, -240, -150, -110) + tuple(range(-96, 97, 8)) + (110, 150, 240, 420),
        "ys": (-200, -110, -80) + tuple(range(-64, 97, 8)) + (120, 170, 260, 520),
        "noise": 1.6, "detail": (-100, -70, 100, 100),     # rect with bumpy, painted ground
        "bank": (48, 96, 9.0),                              # ground rises behind the scene: y from, y to, height
    },
    "log": {"center": (-52, 30), "yaw": 24, "length": 96, "radius": 13, "thickness": 3.5},
    "rootArch": ((-26, 52, -6), (-18, 50, 14), (-4, 48, 34), (14, 52, 40), (34, 58, 30), (46, 64, 10), (52, 66, -6)),
    "web": {
        "center": (25, 24, 24), "yaw": 8, "radius": 15, "radials": 18, "turns": 10, "dew": 16,
        "stalks": (((4, 28), 64, (0.02, 0.0)), ((48, 24), 72, (-0.03, 0.01))),   # (xy, height, lean)
        "anchors": ((0, 42), (1, 46), (0, 9), (1, 12)),                         # (stalk index, height)
        "groundAnchor": (30, 20),
    },
    "perch": {"xy": (17, 3), "size": 12, "flat": 0.45},
    "fireflies": ((43.5, 2.5), (51, 10), (31, -2), (60, -2), (-21, 3), (5.2, 28.2, 60)),
    "props": (   # (kit, x, y, scale, yaw degrees): hand-composed hero props
        ("mushroom_red", 43, 2, 1.0, 20), ("mushroom_red", 51, 10, 0.7, 80), ("mushroom_flat", 60, -2, 0.9, 140),
        ("mushroom_dome", 37, -6, 0.55, 10), ("mushroom_bell", 31, -2, 0.8, 0), ("mushroom_bell", 29, -9, 0.6, 50),
        ("mushroom_flat", -30, 12, 1.1, 200), ("mushroom_dome", -21, 3, 0.8, 30),
        ("leaf_oak", -30, -22, 1.0, 60), ("leaf_round", 42, -20, 0.9, 120), ("leaf_oak", 70, 14, 1.0, 250),
        ("pebble_big", -8, 42, 1.0, 10), ("pebble", 60, 26, 1.2, 70), ("acorn", -12, -8, 1.0, 30),
        ("acorn_cap", -6, -14, 1.0, 0), ("twig", -34, -8, 1.0, 12),
    ),
    # the camera's view wedge stays clear of tall things; the spider perch and web base stay clear of all
    "exclude": (("circle", 17, 3, 11), ("circle", 25, 24, 9)),
    "scatter": (
        {"name": "clover", "kit": "clover", "prefix": "DECO", "count": 9, "area": ("rect", -70, -60, 70, 30),
         "minDist": 10, "cluster": (1, 3, 5), "scale": (0.7, 1.0), "avoid": (("tri", (-4, -40), (-10, 20), (40, 20)),)},
        {"name": "grass", "kit": "grass_clump", "prefix": "DECO", "count": 14, "area": ("rect", -90, -40, 90, 45),
         "minDist": 14, "scale": (0.7, 1.1), "avoid": (("tri", (-4, -60), (-40, 45), (75, 45)),)},
        {"name": "moss", "kit": "moss_mound", "prefix": "DECO", "count": 8, "area": ("rect", -85, -55, 85, 40),
         "minDist": 14},
        {"name": "pebbles", "kit": ("pebble", "pebble_small"), "count": 10, "area": ("rect", -85, -60, 85, 40),
         "minDist": 10, "scale": (0.6, 1.0), "avoid": (("tri", (-4, -40), (-6, 10), (30, 10)),)},
        {"name": "leaves", "kit": ("leaf_round", "leaf_oak"), "prefix": "DECO", "count": 6,
         "area": ("rect", -85, -60, 85, 40), "minDist": 20, "scale": (0.6, 0.9), "sink": 0.2},
    ),
    "backdrop": {  # rows of tall grass and stalks that close the horizon behind the diorama
        "rows": ((68, (-170, 170), 20, ("grass_tall",), (1.1, 1.6)), (92, (-230, 230), 26, ("grass_tall",), (1.4, 2.0))),
        "stalks": 12, "stalkY": (74, 120), "stalkX": (-200, 200), "stalkHeight": (90, 150),
        "giants": (("mushroom_flat", -120, 150, 3.2), ("mushroom_dome", 140, 170, 3.6), ("mushroom_flat", 60, 210, 4.0)),
    },
    "render": {
        "look": {"sky": (0.06, 0.07, 0.16), "skyStrength": 1.6, "sun": (24, 150), "sunEnergy": 2.2,
                 "sunColor": (0.70, 0.78, 1.0), "exposure": 0.2},
        "spiders": ("SpiderPose",),
        "glow": (("Firefly",), (1.0, 0.78, 0.35), 12.0),
        "sheets": (
            {"name": "main_menu_views", "cols": 1, "views": (
                {"label": "menu camera (16:9, FOV 50)", "size": (1280, 720), "loc": "MARKER_MenuCamera",
                 "target": "MARKER_MenuFocus", "fov": 50, "overlay": "menu_ui"},
                {"label": "overview", "size": (1280, 720), "loc": (150, -190, 150), "target": (0, 10, 5), "lens": 32},
                {"label": "player height beside the web", "size": (1280, 720), "loc": (2, -14, 5),
                 "target": (40, 30, 18), "lens": 20},
            )},
        ),
    },
}

# ---------------------------------------------------------------- lobby: "Webhollow" hub (its own place)
# Angles are degrees counter-clockwise from +X (east); 90 = north (+Y), 270 = south (the entrance).
MAPS["lobby"] = {
    "kind": "hub",
    "title": "Webhollow",
    "budget": 60000,
    "shading": {"aoDistance": 40.0},
    "stump": {
        "rIn": 105.0, "rOut": 130.0, "height": 150.0,
        "segments": 16, "colsPerSegment": 6,           # 16 closed wall segments (COL_StumpWall_01..16)
        "rows": (0.0, 0.035, 0.09, 0.18, 0.3, 0.43, 0.56, 0.68, 0.79, 0.89, 1.0),
        "rimNoise": 14.0,
        "breaks": ((30, 34, 14), (158, 26, 12), (212, 18, 9)),  # (angle, depth, half-width) broken-away rim
        "spikes": 14, "spikeHeight": (8, 30),          # splinter clusters on the bark rim
        "towers": ((120, 42), (250, 30), (330, 36)),    # (angle, extra height) tall broken splinters
        "taper": 0.07, "lumps": 7.0,
        "innerDrop": (5, 15),                          # rotten inner wood sits lower than the bark rim
        "barkRidge": 2.4, "flare": 16.0, "flareHeight": 14.0,
        "entrance": {"angle": 270.0, "halfWidth": 16.0, "height": 70.0},
    },
    "floor": {
        "rings": (0, 10, 22, 34, 46, 58, 70, 82, 94, 104, 113), "segments": 64, "noise": 1.2,
        "outerRings": (113, 124, 138, 154, 172, 192, 214, 238, 262, 300, 420, 700), "outerNoise": 2.2,
        "berm": 7.0,                                    # the ground rises toward the boundary ring
    },
    "gate": {"angle": 90, "radius": 76, "skirt": 34, "lip": 17, "mouth": 12, "depth": 34, "slant": 16,
             "lipBack": 13, "lipFront": 0, "hole": 21, "marker": 36},
    "stations": {  # centre angle / radius, marker = distance in front (toward the hub centre)
        "dungeon_gate": {"angle": 90, "clear": 40},
        "molting_shrine": {"angle": 54, "radius": 84, "marker": 22},
        "hatchery": {"angle": 126, "radius": 84, "marker": 26},
        "outfitter": {"angle": 18, "radius": 84, "marker": 22},
        "merchant": {"angle": 162, "radius": 82, "marker": 24},
        "stash": {"angle": 198, "radius": 84, "marker": 24},
        "silk_tailor": {"angle": 342, "radius": 86, "marker": 22},
        "quest_board": {"angle": 306, "radius": 88, "marker": 20},
    },
    "spawns": ((-7, -7), (7, -7), (-7, 7), (7, 7)),
    # (angle, height, width, depth, thickness): a spiral of shelf-fungus ledges up the inner wall
    "ledges": (
        (325, 36, 36, 22, 11), (352, 48, 30, 19, 10), (20, 60, 40, 24, 12), (48, 72, 32, 20, 11),
        (78, 84, 42, 26, 12), (108, 96, 34, 21, 11), (138, 106, 40, 24, 12), (166, 114, 30, 19, 10),
        (194, 121, 44, 26, 13), (222, 130, 34, 21, 11), (250, 128, 38, 22, 11),
    ),
    "web": {  # a sheet web hammock (walkable COL) slung between the wall and two held-up corners
        "anchors": ((132, 124), (152, 121), (174, 126), (196, 123), (214, 128)),  # (angle, height) on the wall
        "freeCorners": ((-44, -14, 122), (-38, 40, 125)),                         # held up by strands
        "sag": 9.0,
        "cornerLines": ((300, 140), (60, 146), (100, 138)),
        "spans": (((20, 136), (200, 140)), ((320, 132), (110, 146))),
        "dropLines": ((-46, 34, 120), (-48, -6, 118)),
    },
    "roots": (8, 50, 100, 140, 188, 228, 318, 350),
    "fairyRing": {"radius": 30, "count": 11, "gapAngle": 270, "gapWidth": 40,
                  "kit": ("mushroom_bell", "mushroom_dome"), "scale": (0.45, 0.65)},
    "exclude": (("circle", 0, 0, 44), ("rect", -26, -140, 26, -36)),     # plaza + entrance lane
    "scatter": (
        {"name": "in_mush", "kit": ("mushroom_dome", "mushroom_bell", "mushroom_red"), "count": 7,
         "area": ("annulus", 62, 98), "minDist": 20, "scale": (0.55, 0.8), "cluster": (2, 4, 7)},
        {"name": "in_pebble", "kit": ("pebble", "pebble_small"), "count": 12, "area": ("annulus", 48, 100),
         "minDist": 10, "scale": (0.7, 1.1)},
        {"name": "in_leaf", "kit": ("leaf_round", "leaf_oak"), "prefix": "DECO", "count": 8,
         "area": ("annulus", 46, 100), "minDist": 16, "scale": (0.6, 0.9), "sink": 0.2},
        {"name": "in_moss", "kit": "moss_mound", "count": 6, "area": ("annulus", 70, 102), "minDist": 16,
         "scale": (0.8, 1.2), "prefix": "DECO"},
        {"name": "in_clover", "kit": "clover", "prefix": "DECO", "count": 3, "area": ("annulus", 46, 96),
         "minDist": 12, "cluster": (2, 3, 5)},
        {"name": "out_pebble", "kit": ("pebble", "pebble_big"), "count": 22, "area": ("annulus", 152, 226),
         "minDist": 16, "scale": (0.8, 1.3)},
        {"name": "out_mush", "kit": ("mushroom_dome", "mushroom_red", "mushroom_flat", "mushroom_bell"), "count": 7,
         "area": ("annulus", 150, 222), "minDist": 26, "scale": (0.8, 1.25), "cluster": (2, 4, 10)},
        {"name": "out_grass", "kit": "grass_clump", "prefix": "DECO", "count": 16, "area": ("annulus", 150, 228),
         "minDist": 16, "scale": (0.8, 1.2)},
        {"name": "out_leaf", "kit": ("leaf_oak", "leaf_round"), "prefix": "DECO", "count": 13,
         "area": ("annulus", 148, 226), "minDist": 18, "scale": (0.85, 1.15), "sink": 0.2},
        {"name": "out_twig", "kit": "twig", "prefix": "DECO", "count": 8, "area": ("annulus", 150, 222),
         "minDist": 24},
        {"name": "out_moss", "kit": "moss_mound", "prefix": "DECO", "count": 12, "area": ("annulus", 150, 226),
         "minDist": 18, "scale": (0.9, 1.5)},
        {"name": "out_acorn", "kit": ("acorn", "acorn_cap"), "count": 8, "area": ("annulus", 150, 222),
         "minDist": 14},
        {"name": "out_clover", "kit": "clover", "prefix": "DECO", "count": 5, "area": ("annulus", 150, 222),
         "minDist": 14, "cluster": (2, 3, 6)},
    ),
    "ring": {  # boundary: rows of (radius, spacing, kits, scale); visual only, Studio adds the invisible wall
        "rows": ((238, 26, ("grass_tall", "grass_tall", "pebble_big"), (1.0, 1.4)),
                 (256, 36, ("grass_tall", "leaf_oak", "pebble_big"), (1.1, 1.5))),
        "jitter": 5.0,
        "tilt": {"leaf_oak": 50},
        "stalks": 10, "stalkRadius": (246, 272), "stalkHeight": (80, 120),
    },
    "render": {
        "look": {"sky": (0.46, 0.53, 0.64), "skyStrength": 1.6, "sun": (66, 150), "sunEnergy": 3.6,
                 "sunColor": (1.0, 0.9, 0.76)},
        "spiders": ("PlayerSpawn", "Station"),
        "sheets": (
            {"name": "lobby_views", "cols": 2, "views": (
                {"label": "overview", "loc": (300, -390, 330), "target": (0, -10, 30), "lens": 30},
                {"label": "interior (from the entrance, spider height)", "loc": (0, -100, 14), "target": (0, 30, 34),
                 "lens": 16},
                {"label": "interior from the rim: ledges, sheet web", "loc": (80, -70, 170), "target": (-10, 20, 30),
                 "lens": 18},
                {"label": "outside, player height: entrance arch", "loc": (40, -236, 9), "target": (0, -120, 34),
                 "lens": 20},
            )},
            {"name": "lobby_stations", "cols": 4, "views": tuple(
                {"label": sid, "size": (480, 400), "station": sid, "lens": 18}
                for sid in ("dungeon_gate", "molting_shrine", "hatchery", "outfitter", "merchant", "stash",
                            "silk_tailor", "quest_board"))},
        ),
    },
}

# ---------------------------------------------------------------- Mossy Hollow: dungeon room kit (dungeon place)
# Rooms are prefabs the generator snaps together at doorways. Room space: origin at the footprint centre on
# the floor (z = 0); footprints are whole 80-stud cells; every doorway is centred on its edge with the same
# frame, so any N meets any S after 90-degree rotations. Everything stays inside the footprint.
# Edge-local space (walls, ledges, tunnels): u runs along the edge, v = 0 on the boundary, the room is -v.
MAPS["mossy_hollow"] = {
    "kind": "rooms",
    "title": "Mossy Hollow",
    "grid": 80.0,
    "door": {
        "halfWidth": 14.0,      # opening is 28 wide at the floor ...
        "spring": 17.0,         # ... with vertical jambs up to here ...
        "crown": 29.0,          # ... and an elliptical arch up to here
        "clear": (24.0, 20.0),  # required clear width x height (checked by ray grid + vertex test)
        "lintelColumns": 10,
        "frameRadius": 3.0,     # root that traces the opening on the room side
    },
    "wall": {"thickness": 10.0, "rows": (0.0, 0.06, 0.15, 0.3, 0.48, 0.66, 0.82, 0.93, 1.0), "colStep": 7.0,
             "noise": 5.0, "flare": 5.0, "lip": 3.5, "maxPiece": 80.0},
    "floor": {"step": 10.0, "noise": 1.4, "flat": 12.0, "fade": 30.0},   # no bumps within `flat` of an edge
    "lane": 13.0,               # doorway-to-centre lanes kept clear of solid props (capsule radius)
    # BARRIER_Lid: a flat invisible box over the whole footprint, its underside `gap` under the lowest wall top,
    # so spiders cannot climb over a wall and out along its back. Climbable interior pieces stay `clearance`
    # under it (the build lowers hanging pieces / shrinks standing ones that poke above, and the check raises).
    "lid": {"gap": 1.0, "thickness": 2.0, "clearance": 3.0},
    "shading": {"aoDistance": 26.0},
    # default filler per room; counts are multiplied by the room's scatterScale
    "scatter": (
        {"name": "moss", "kit": "moss_mound", "prefix": "DECO", "count": 3, "minDist": 12, "scale": (0.7, 1.2)},
        {"name": "clover", "kit": "clover", "prefix": "DECO", "count": 2, "minDist": 12, "cluster": (2, 3, 5),
         "scale": (0.7, 1.0), "lanes": True},
        {"name": "leaves", "kit": ("leaf_oak", "leaf_round"), "prefix": "DECO", "count": 2, "minDist": 16,
         "scale": (0.5, 0.8), "sink": 0.2},
        {"name": "pebbles", "kit": ("pebble_small", "pebble"), "count": 3, "minDist": 9, "scale": (0.6, 1.0),
         "lanes": True},
        {"name": "grass", "kit": "grass_clump", "prefix": "DECO", "count": 1.5, "minDist": 14, "scale": (0.6, 0.9),
         "lanes": True},
        {"name": "twig", "kit": "twig", "prefix": "DECO", "count": 1, "minDist": 20, "scale": (0.6, 0.9),
         "lanes": True},
    ),
    "rooms": {
        "mossy_entry": {
            "cells": (1, 1), "doors": ("N",), "budget": 8000, "height": (52, 58), "layout": (0, 0),
            "scatterScale": 1.0,
            "spawns": ((-8, -20), (8, -20), (-8, -8), (8, -8)),
            "features": (
                {"type": "ceilingRoot", "points": ((-37, -14, 44), (-15, -9, 38), (10, -16, 39), (37, -12, 43)), "r": (5.0, 3.5)},
                {"type": "ceilingRoot", "points": ((-22, -37, 43), (-12, -12, 41), (-3, 18, 40), (5, 37, 44)), "r": (4.5, 3.0)},
                {"type": "silkDrop", "at": (1, -13), "top": 38},
                {"type": "mushrooms", "at": (-21, -22), "kit": ("mushroom_dome", "mushroom_red", "mushroom_bell"), "n": 4, "radius": 7},
                {"type": "stack", "at": (21, -22), "scales": (1.2, 0.9, 0.6)},
                {"type": "mushrooms", "at": (20, 18), "kit": ("mushroom_flat", "mushroom_bell"), "n": 3, "radius": 6},
                {"type": "ledge", "edge": "W", "u": 12, "z": 24, "size": (24, 15, 8)},
                {"type": "ledge", "edge": "E", "u": 6, "z": 32, "size": (20, 13, 7)},
            ),
        },
        "mossy_hall": {
            "cells": (1, 1), "doors": ("N", "S"), "budget": 8000, "height": (52, 58), "layout": (320, 0),
            "scatterScale": 1.0,
            "features": (
                {"type": "leafCanopy", "at": (0, 6, 42), "yaw": 90, "length": 66, "curl": 0.3},
                {"type": "rootArch", "from": (-24, -22), "to": (-22, 20), "height": 30, "r": (5.0, 3.5)},
                {"type": "pillar", "at": (23, -18), "scale": 1.0},
                {"type": "pillar", "at": (22, 18), "scale": 0.75},
                {"type": "mushrooms", "at": (-22, 0), "kit": ("mushroom_bell", "mushroom_dome"), "n": 3, "radius": 5},
                {"type": "ledge", "edge": "W", "u": -18, "z": 22, "size": (22, 14, 8)},
                {"type": "ledge", "edge": "E", "u": 4, "z": 30, "size": (22, 14, 8)},
            ),
        },
        "mossy_turn": {
            "cells": (1, 1), "doors": ("S", "E"), "budget": 8000, "height": (52, 58), "layout": (640, 0),
            "scatterScale": 1.0,
            "features": (
                {"type": "log", "center": (-12, 12), "z": 29, "yaw": 45, "length": 60, "radius": 8},
                {"type": "pillar", "at": (-22, -20), "scale": 0.85},
                {"type": "mushrooms", "at": (-22, 22), "kit": ("mushroom_dome", "mushroom_bell"), "n": 3, "radius": 6},
                {"type": "stack", "at": (22, 22), "scales": (1.3, 1.0, 0.65)},
                {"type": "rootArch", "from": (-30, -2), "to": (-19, -29), "height": 24, "r": (4.5, 3.2)},
                {"type": "ledge", "edge": "N", "u": -8, "z": 26, "size": (22, 14, 8)},
                {"type": "ledge", "edge": "W", "u": -16, "z": 20, "size": (18, 12, 7)},
            ),
        },
        "mossy_arena_small": {
            "cells": (2, 2), "doors": ("S", "N"), "budget": 15000, "height": (56, 62), "layout": (0, 400),
            "scatterScale": 2.5,
            "enemies": ((-32, 22), (32, 22), (-42, -18), (42, -18), (0, 34), (0, -30)),
            "features": (
                {"type": "pillar", "at": (-46, 42), "scale": 1.0},
                {"type": "pillar", "at": (47, -45), "scale": 0.9},
                {"type": "pillar", "at": (50, 46), "scale": 0.7},
                {"type": "stack", "at": (-52, -48), "scales": (1.4, 1.0, 0.7)},
                {"type": "stack", "at": (24, 52), "scales": (1.1, 0.8)},
                {"type": "rootArch", "from": (-62, -8), "to": (-32, -40), "height": 28, "r": (5.5, 3.5)},
                {"type": "rootArch", "from": (60, 10), "to": (38, 36), "height": 24, "r": (5.0, 3.5)},
                {"type": "mushrooms", "at": (-24, -50), "kit": ("mushroom_red", "mushroom_dome"), "n": 4, "radius": 7},
                {"type": "mushrooms", "at": (28, -4), "kit": ("mushroom_bell", "mushroom_dome"), "n": 3, "radius": 5},
                {"type": "ceilingRoot", "points": ((-76, 46, 48), (-44, 60, 42), (-8, 64, 45), (20, 76, 49)), "r": (5.5, 3.5)},
                {"type": "ceilingRoot", "points": ((76, -48, 48), (44, -60, 41), (12, -64, 44), (-18, -76, 49)), "r": (5.5, 3.5)},
                {"type": "ledge", "edge": "W", "u": 22, "z": 24, "size": (26, 16, 8)},
                {"type": "ledge", "edge": "E", "u": 30, "z": 28, "size": (24, 15, 8)},
                {"type": "ledge", "edge": "N", "u": 40, "z": 32, "size": (22, 14, 8)},
                {"type": "ledge", "edge": "S", "u": -40, "z": 22, "size": (26, 16, 8)},
            ),
        },
        "mossy_arena_large": {
            "cells": (2, 2), "doors": ("S", "E", "W"), "budget": 15000, "height": (56, 62), "layout": (400, 400),
            "scatterScale": 2.5,
            "enemies": ((-30, 30), (30, 30), (0, 44), (-45, -30), (45, -30), (-22, -8), (22, 6)),
            "features": (
                {"type": "log", "center": (0, 50), "z": 28, "yaw": 0, "length": 150, "radius": 11},
                {"type": "pillar", "at": (-50, -48), "scale": 1.0},
                {"type": "pillar", "at": (52, -46), "scale": 0.85},
                {"type": "stack", "at": (-56, 28), "scales": (1.3, 0.9)},
                {"type": "stack", "at": (56, 24), "scales": (1.2, 0.9, 0.6)},
                {"type": "rootArch", "from": (-62, -30), "to": (-34, -58), "height": 26, "r": (5.0, 3.5)},
                {"type": "mushrooms", "at": (30, -22), "kit": ("mushroom_red", "mushroom_dome", "mushroom_bell"), "n": 4, "radius": 7},
                {"type": "mushrooms", "at": (-28, 50), "kit": ("mushroom_flat", "mushroom_bell"), "n": 3, "radius": 6},
                {"type": "ceilingRoot", "points": ((76, -40, 48), (50, -58, 41), (30, -76, 47)), "r": (5.0, 3.5)},
                {"type": "ledge", "edge": "N", "u": -40, "z": 22, "size": (24, 15, 8)},
                {"type": "ledge", "edge": "S", "u": 40, "z": 26, "size": (24, 15, 8)},
                {"type": "ledge", "edge": "E", "u": 40, "z": 30, "size": (22, 14, 8)},
            ),
        },
        "mossy_treasure": {
            "cells": (1, 1), "doors": ("S",), "budget": 8000, "height": (52, 58), "layout": (960, 0),
            "scatterScale": 0.8,
            "chest": {"at": (0, 12), "radius": 12, "height": 5},
            "features": (
                {"type": "leafCanopy", "at": (0, 16, 42), "yaw": 90, "length": 54, "curl": 0.35},
                {"type": "eggs", "at": (-22, 20), "n": 5, "radius": 6},
                {"type": "amber", "at": (0, 12), "n": 6, "radius": 15},
                {"type": "web", "at": (21, 21, 20), "yaw": -45, "radius": 10},
                {"type": "mushrooms", "at": (25, -24), "kit": ("mushroom_bell", "mushroom_dome"), "n": 3, "radius": 4},
                {"type": "mushrooms", "at": (-25, -22), "kit": ("mushroom_red", "mushroom_bell"), "n": 2, "radius": 4},
                {"type": "glowBells", "at": (0, 12), "radius": 16, "n": 4},
            ),
        },
        "mossy_boss": {
            "cells": (3, 3), "doors": ("S",), "budget": 25000, "height": (58, 64), "thickness": 14, "layout": (840, 400),
            "scatterScale": 3.0,
            "lanes": (((0, -120), (0, 20)),),
            "boss": (0, 6), "extraction": (0, -44),
            "nest": {"at": (0, 60), "radius": 40, "height": 26, "crater": 9,
                     "mouths": ((248, 7, 6.5), (292, 8, 6.5), (205, 6, 5.5), (335, 6, 5.5))},  # (angle, z, radius)
            "features": (
                {"type": "tunnel", "edge": "W", "u": 40, "z": 10, "r": 9},
                {"type": "tunnel", "edge": "W", "u": -52, "z": 12, "r": 8},
                {"type": "tunnel", "edge": "E", "u": 30, "z": 10, "r": 9},
                {"type": "tunnel", "edge": "E", "u": -64, "z": 30, "r": 8},
                {"type": "tunnel", "edge": "N", "u": -72, "z": 12, "r": 9},
                {"type": "tunnel", "edge": "N", "u": 64, "z": 14, "r": 8},
                {"type": "ceilingRoot", "points": ((-112, 56, 50), (-80, 82, 42), (-54, 112, 50)), "r": (7.0, 4.5)},
                {"type": "ceilingRoot", "points": ((112, 48, 49), (82, 80, 41), (48, 112, 50)), "r": (7.0, 4.5)},
                {"type": "ceilingRoot", "points": ((112, -64, 48), (84, -86, 41), (62, -112, 49)), "r": (6.0, 4.0)},
                {"type": "leafCanopy", "at": (-70, -72, 46), "yaw": -40, "length": 64, "curl": 0.3},
                {"type": "pillar", "at": (-82, -40), "scale": 1.1},
                {"type": "pillar", "at": (86, -34), "scale": 1.0},
                {"type": "pillar", "at": (-88, 30), "scale": 0.8},
                {"type": "stack", "at": (74, 20), "scales": (1.5, 1.1, 0.8)},
                {"type": "stack", "at": (-60, -86), "scales": (1.3, 0.9)},
                {"type": "rootArch", "from": (40, -96), "to": (92, -56), "height": 32, "r": (6.0, 4.0)},
                {"type": "mushrooms", "at": (-56, 76), "kit": ("mushroom_red", "mushroom_dome"), "n": 4, "radius": 8},
                {"type": "mushrooms", "at": (62, 84), "kit": ("mushroom_bell", "mushroom_flat"), "n": 3, "radius": 7},
                {"type": "ledge", "edge": "W", "u": -10, "z": 30, "size": (28, 16, 9)},
                {"type": "ledge", "edge": "E", "u": 70, "z": 26, "size": (26, 16, 9)},
                {"type": "ledge", "edge": "S", "u": 60, "z": 28, "size": (28, 16, 9)},
                {"type": "ledge", "edge": "S", "u": -64, "z": 34, "size": (24, 15, 8)},
            ),
        },
    },
    "render": {
        "look": {"sky": (0.46, 0.53, 0.64), "skyStrength": 1.5, "sun": (58, 125), "sunEnergy": 3.4,
                 "sunColor": (1.0, 0.9, 0.76)},
        "spiders": ("PlayerSpawn", "EnemySpawn", "Chest", "BossSpawn"),
        "sheets": (
            {"name": "mossy_hollow_rooms", "cols": 4, "rooms": True, "size": (640, 480)},
            {"name": "mossy_hollow_close", "cols": 3, "views": (
                {"label": "arena_large, player height (log bridge overhead)", "room": "mossy_arena_large",
                 "loc": (8, -64, 6), "target": (0, 30, 26), "lens": 18},
                {"label": "boss, player height (ant nest, wall tunnels)", "room": "mossy_boss",
                 "loc": (10, -80, 8), "target": (0, 50, 22), "lens": 18},
                {"label": "hall, doorway (S) looking north", "room": "mossy_hall",
                 "loc": (0, -46, 8), "target": (0, 20, 16), "lens": 18},
                {"label": "entry, looking back at the spawns (from the N doorway lane)", "room": "mossy_entry",
                 "loc": (-4, 24, 16), "target": (4, -18, 8), "lens": 18},
                {"label": "outside: arena_small wall backs from above (lid hidden)", "room": "mossy_arena_small",
                 "loc": (150, -135, 95), "target": (0, 0, 22), "lens": 26, "only": ("mossy_arena_small",)},
                {"label": "outside: turn wall backs (lid hidden)", "room": "mossy_turn",
                 "loc": (-95, 95, 45), "target": (0, 0, 22), "lens": 24, "only": ("mossy_turn",)},
            )},
        ),
    },
}
