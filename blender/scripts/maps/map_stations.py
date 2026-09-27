"""Lobby (Webhollow) station props. Each builder works in station space: origin on the floor at the
station's centre, +Y faces the hub centre (where players stand), the stump wall is behind (-Y).

A builder returns {"PROP": [geo...], "DECO": [geo...], "COL": [geo...]} plus extra marker offsets.
Solid parts go in PROP (they block and are climbable); thin silk and glow bits go in DECO.
"""

import math

import bpy  # noqa: F401
from mathutils import Matrix, Vector

import map_props as MP
from map_config import PALETTE as P
from map_kit import IDENTITY, TAU, UP, Noise, clamp, lerp, mix, smoothstep


def block(g, size, color, m=IDENTITY, jitter=0.0, rng=None):
    """Closed box centred on its base (z from 0 to size.z)."""
    sx, sy, sz = size[0] * 0.5, size[1] * 0.5, size[2]
    corners = [(-sx, -sy, 0), (sx, -sy, 0), (sx, sy, 0), (-sx, sy, 0),
               (-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz)]
    vs = []
    for co in corners:
        v = Vector(co)
        if jitter and rng:
            v += Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))) * jitter
        c = color(v) if callable(color) else color
        vs.append(g.vert(m @ v, *((c,) if len(c) == 3 else c)))
    for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        g.face([vs[i] for i in f])


def post(g, rng, base, height, radius, m=IDENTITY, bend=0.06):
    """Upright twig post (bark), slightly crooked."""
    b = Vector(base)
    pts = [b + Vector((rng.uniform(-1, 1) * height * bend * (s / 3), rng.uniform(-1, 1) * height * bend * (s / 3),
                       -1.0 + (height + 1.0) * s / 3)) for s in range(4)]
    g.sweep(pts, lambda t: radius * lerp(1.1, 0.85, t), 5,
            lambda t, a, co, off: (P["bark"] if int(t * 6) % 2 else mix(P["bark"], P["bark_light"], 0.35)), m=m)
    return pts[-1]


def bar(g, a, b, radius, m=IDENTITY, sides=5):
    g.sweep([Vector(a), Vector(a).lerp(Vector(b), 0.5) + Vector((0, 0, -0.4)), Vector(b)], radius, sides,
            lambda t, ang, co, off: mix(P["bark"], P["bark_light"], 0.3 * max(0, off.z)), m=m)


def amber_drop(g, center, r, m=IDENTITY):
    def color(n, co):
        return mix(P["amber"], P["amber_glow"], smoothstep(-0.2, 0.9, n.z))
    g.ico(Vector(center) + Vector((0, 0, r * 0.7)), (r, r, r * 0.8), 2, color, m=m)


def shell_dome(g, rx, ry, rz, color, m=IDENTITY, segments=12, rings=7, back=0.18):
    """Carapace-like dome bulging along +Y with its long axis on Z; the back is flattened (closed)."""
    prof = [(math.sin(math.pi * i / rings), math.cos(math.pi * i / rings)) for i in range(rings + 1)]

    def adjust(i, t, a, co):
        y = co.y * ry if co.y > 0 else co.y * ry * back
        return Vector((co.x * rx, y, co.z * rz))

    g.lathe(prof, segments, color, m=m, adjust=adjust)


# ---------------------------------------------------------------- stations

def merchant(rng, geo):
    """Acorn-cap stall: four twig posts under a big scaly acorn-cap roof, a bark counter with amber goods."""
    prop, deco = geo("prop"), geo("deco")
    for x, y in ((-12, -6), (12, -6), (-11, 6), (11, 6)):
        post(prop, rng, (x, y, 0), 23, 1.3)
    MP.acorn_cap(prop, rng, radius=17, m=Matrix.Translation((0, 0, 18.5)) @ Matrix.Rotation(0.05, 4, "X"),
                 stalk=True, segments=14)
    block(prop, (26, 5, 7), lambda v: mix(P["wood_rot"], P["bark_light"], 0.5 if v.z > 3 else 0.0),
          m=Matrix.Translation((0, 9, 0)), jitter=0.4, rng=rng)
    block(prop, (27, 6.5, 1.4), P["wood_pale"], m=Matrix.Translation((0, 9, 7)), jitter=0.2, rng=rng)
    for x in (-9, -4, 2, 7):
        amber_drop(deco, (x + rng.uniform(-1, 1), 9 + rng.uniform(-1, 1), 8.4), rng.uniform(1.2, 1.9))
    for k in range(3):
        MP.acorn(prop, rng, length=9, m=Matrix.Translation((-16 + k * 3.5, 12 + k * 1.5, 0)) @ Matrix.Rotation(k, 4, "Z"))
    return {"PROP": [prop], "DECO": [deco]}, {}


def outfitter(rng, geo):
    """Beetle-shell armour stand: a twig T-frame wearing a glossy elytra shell, spare shells beside it."""
    prop, deco = geo("prop"), geo("deco")
    top = post(prop, rng, (0, -2, 0), 27, 1.5, bend=0.02)
    bar(prop, (-11, -2, 21), (11, -2, 21.5), 1.1)

    def beetle(i, t, a, co):
        x = co.x
        seam = abs(x) < 0.9
        if seam:
            return P["beetle_gold"]
        sheen = smoothstep(0.35, 0.9, t) * 0.0 + (0.6 if 1 <= i <= 2 else 0.0)
        return mix(P["beetle"], P["beetle_sheen"], sheen)

    shell_dome(prop, 11, 6, 13, beetle, m=Matrix.Translation((0, -0.5, 13.5)))
    shell_dome(prop, 5.5, 4, 4.5, lambda i, t, a, co: mix(P["beetle"], P["beetle_sheen"], 0.5 if i <= 2 else 0),
               m=Matrix.Translation((0, -1.2, 27.5)))
    shell_dome(prop, 7, 4.5, 9, beetle, m=Matrix.Translation((15, 2, 5)) @ Matrix.Rotation(-0.9, 4, "X")
               @ Matrix.Rotation(0.4, 4, "Z"))
    shell_dome(prop, 5, 3.5, 6, beetle, m=Matrix.Translation((-14, 4, 3.2)) @ Matrix.Rotation(-1.2, 4, "X")
               @ Matrix.Rotation(-0.5, 4, "Z"))
    return {"PROP": [prop], "DECO": [deco]}, {}


def hatchery(rng, geo):
    """Silk nest bowl holding glowing egg sacs, anchored to the wall by silk lines."""
    prop, deco = geo("prop"), geo("deco")
    noise = Noise("nest", rng.random())
    R = 17
    prof = [(0, 1.0), (0.7 * R, 1.6), (0.95 * R, 4.5), (1.08 * R, 8.5), (1.0 * R, 9.6), (0.9 * R, 8.6),
            (0.8 * R, 5.0), (0.5 * R, 3.2), (0, 2.8)]

    def adjust(i, t, a, co):
        if a is None:
            return co
        w = 1.0 + 0.07 * noise((math.cos(a) * 2, math.sin(a) * 2, i * 0.5), 1.0)
        return Vector((co.x * w, co.y * w, co.z + (0.8 * noise((math.cos(a) * 3, math.sin(a) * 3, 9)) if i in (3, 4) else 0)))

    def color(i, t, a, co):
        if i >= 5:
            return mix(P["silk_shade"], P["amber_glow"], 0.25)
        return mix(P["silk_shade"], P["silk"], smoothstep(1, 4, i))

    prop.lathe(prof, 14, color, adjust=adjust)
    for k in range(4):  # wraps around the rim
        tilt = Matrix.Rotation(rng.uniform(-0.25, 0.25), 4, "X") @ Matrix.Rotation(rng.uniform(-0.25, 0.25), 4, "Y")
        ring = [tilt @ Vector((R * 1.05 * math.cos(TAU * s / 12), R * 1.05 * math.sin(TAU * s / 12), 6.5 + k * 0.8))
                for s in range(13)]
        deco.sweep(ring, 0.3, 3, lambda *a: P["silk"], caps=(False, False))
    spots = [(0, 0), (6, 3), (-6, 2), (3, -6), (-4, -6), (8, -3), (-9, -2)]
    for k, (x, y) in enumerate(spots):
        s = rng.uniform(6, 8)
        MP.egg_sac(prop, rng, size=s, glow=True,
                   m=Matrix.Translation((x, y, 2.5 + (2.5 if k == 0 else 0))) @ Matrix.Rotation(rng.uniform(-0.3, 0.3), 4, "X"))
    for x, zt in ((-14, 46), (-4, 58), (9, 52), (16, 40)):
        deco.strand((x * 0.9, 0, 8), (x * 1.4, -22, zt), 0.3, P["silk"], sag=0.5, segments=2)
    return {"PROP": [prop], "DECO": [deco]}, {}


def molting_shrine(rng, geo):
    """A shed spider exoskeleton, twice player size, posed on a mossy stone pedestal, amber lamps either side."""
    prop, deco = geo("prop"), geo("deco")
    noise = Noise("plinth", rng.random())
    prof = [(0, 13), (12.5, 13), (13.5, 11.5), (12.6, 7), (13.8, 1.5), (15.5, -1), (0, -1)]

    def adj(i, t, a, co):
        if a is None:
            return co
        w = 1 + 0.06 * noise((math.cos(a) * 2, math.sin(a) * 2, i), 1)
        return Vector((co.x * w, co.y * w, co.z))

    prop.lathe(prof, 10, lambda i, t, a, co: (mix(P["stone"], P["stone_warm"], 0.5), 0.9 if i <= 1 else 0.5), adjust=adj)
    # exoskeleton (pale, hollow-looking): ceph, split abdomen, 8 raised legs; about 2.5x the Spiderling
    exo, dark = P["exo"], P["exo_dark"]
    S = 1.7
    base = Vector((0, 0, 13))
    ceph_c, abd_c = base + Vector((0, 2.6, 2.4)) * S, base + Vector((0, -3.4, 3.4)) * S
    prop.ico(ceph_c, (2.8 * S, 3.2 * S, 1.9 * S), 2, lambda n, co: mix(exo, dark, 0.3 * clamp(-n.z + 0.3)))
    prop.ico(abd_c, (3.6 * S, 4.6 * S, 3.1 * S), 2,
             lambda n, co: mix(exo, dark, 0.3 * clamp(-n.z + 0.4)) if abs(n.x) > 0.14 else dark)
    for side in (-1, 1):
        for k, yaw in enumerate((35, 70, 110, 145)):
            a = math.radians(yaw)
            out = Vector((side * math.sin(a), math.cos(a), 0))
            hip = ceph_c + out * 1.8 * S + Vector((0, 0, -0.3))
            knee = hip + out * 4.4 * S + Vector((0, 0, 3.4 * S))
            foot = knee + out * 4.0 * S + Vector((0, 0, -(knee.z - base.z) + 0.2))
            prop.sweep([hip, knee, foot], [0.55 * S, 0.45 * S, 0.18 * S], 5,
                       lambda t, ang, co, off: exo if t < 0.55 else mix(exo, dark, 0.5), caps=(True, True))
    for x in (-18, 18):
        post(prop, rng, (x, 4, 0), 16, 1.0, bend=0.02)
        amber_drop(deco, (x, 4, 15.8), 2.0)
    return {"PROP": [prop], "DECO": [deco]}, {}


def stash(rng, geo):
    """Hollowed hazelnut: a thick open cup with a jagged bitten rim, its lid leaning beside it."""
    prop = geo("prop")
    noise = Noise("nut", rng.random())
    R, H = 13.0, 21.0
    rim = [H * 0.86]
    prof = [(0, -1), (0.55 * R, -0.5), (0.92 * R, 3.5), (R, 9), (0.96 * R, 15), (0.84 * R, H * 0.86),
            (0.72 * R, H * 0.86), (0.8 * R, 14), (0.84 * R, 8), (0.6 * R, 3.2), (0, 2.2)]

    def adjust(i, t, a, co):
        if a is None:
            return co
        dz = 0.0
        if i in (5, 6):
            dz = 2.2 * noise((math.cos(a) * 2.5, math.sin(a) * 2.5, 3), 1.0) + (1.5 if int(a * 7) % 2 else -0.5)
        return Vector((co.x, co.y, co.z + dz))

    def color(i, t, a, co):
        if i >= 6:
            return P["nut_inner"] if i == 6 else mix(P["nut_inner"], P["nut_dark"], 0.5)
        stripe = int((a % TAU) / TAU * 28) % 2
        c = mix(P["nut"], P["nut_dark"], 0.35 * stripe)
        return mix(c, P["nut_dark"], 0.6) if i <= 1 else c

    prop.lathe(prof, 14, color, adjust=adjust)
    lid = [(0, 12.5), (1.0, 12), (2.2, 9.5), (0.55 * R, 6), (0.86 * R, 2.2), (0.84 * R, 0), (0.7 * R, 0.4), (0, 3)]
    prop.lathe(lid, 12, lambda i, t, a, co: P["nut_dark"] if i <= 2 else (P["nut"] if i < 5 else P["nut_inner"]),
               m=Matrix.Translation((R * 1.35, 3, 7)) @ Matrix.Rotation(-1.25, 4, "Y") @ Matrix.Rotation(0.3, 4, "X"))
    for k in range(2):
        MP.acorn(prop, rng, length=8, m=Matrix.Translation((-R - 2 + k * 3, 6 + k * 4, 0)) @ Matrix.Rotation(k * 1.7, 4, "Z"))
    return {"PROP": [prop]}, {}


def silk_tailor(rng, geo):
    """Twig loom: two uprights and crossbars, silk warp threads, a woven dyed panel, spools of dyed silk."""
    prop, deco = geo("prop"), geo("deco")
    post(prop, rng, (-12, 0, 0), 32, 1.4, bend=0.02)
    post(prop, rng, (12, 0, 0), 31, 1.4, bend=0.02)
    bar(prop, (-14, 0, 29), (14, 0, 28.5), 1.1)
    bar(prop, (-14, 0.3, 5), (14, 0.3, 5.2), 1.0)
    for k in range(11):
        x = -10 + k * 2
        deco.strand((x, 0, 5.8), (x, 0, 28), 0.22, P["silk"])
    dyes = (P["silk"], P["amber"], P["silk"], P["mush_red"], P["silk"], P["moss_light"], P["silk"])
    band_h = 12.0 / len(dyes)
    for k, c in enumerate(dyes):
        block(prop, (21, 0.9 + 0.05 * (k % 2), band_h), c, m=Matrix.Translation((0, 0.2, 6.2 + k * band_h)))
    for k, (x, y, c) in enumerate(((-17, 7, P["mush_red"]), (-12, 10, P["amber"]), (16, 8, P["moss_light"]))):
        r = rng.uniform(2.4, 3.2)
        prop.ico((x, y, r * 0.9), (r, r, r * 0.95), 2, lambda n, co, c=c: mix(c, P["silk"], 0.25 * max(0, n.z)))
    return {"PROP": [prop], "DECO": [deco]}, {}


def quest_board(rng, geo):
    """Bark board on twig legs with a big oak leaf pinned by rose thorns, and two small note-leaves."""
    prop = geo("prop")
    post(prop, rng, (-11, -1, 0), 30, 1.3, bend=0.02)
    post(prop, rng, (11, -1, 0), 30, 1.3, bend=0.02)
    noise = Noise("board", rng.random())
    block(prop, (26, 2.0, 22), lambda v: mix(P["bark"], P["bark_light"], 0.5 + 0.5 * noise((v.x * 0.2, v.z * 0.05, 0), 1)),
          m=Matrix.Translation((0, 0, 7)), jitter=0.5, rng=rng)
    upright = Matrix.Translation((0, 1.4, 0)) @ Matrix.Rotation(math.pi / 2, 4, "X")
    MP.leaf(prop, rng, length=19, kind="oak", curl=0.08, tone="leaf_orange",
            m=Matrix.Translation((-1, 0, 9)) @ upright @ Matrix.Rotation(0.1, 4, "Z"))
    MP.leaf(prop, rng, length=9, kind="round", curl=0.1, tone="leaf_dry",
            m=Matrix.Translation((8, 0.3, 17)) @ upright @ Matrix.Rotation(-0.4, 4, "Z"))
    MP.leaf(prop, rng, length=8, kind="round", curl=0.1, tone="leaf_green",
            m=Matrix.Translation((-8.5, 0.3, 19)) @ upright @ Matrix.Rotation(0.5, 4, "Z"))
    for x, z in ((-1, 27.5), (-4.5, 13), (3.5, 14), (8, 25), (-8.5, 26.5)):
        base = Vector((x, 1.6, z))
        prop.sweep([base, base + Vector((0.2, 1.4, 0.4)), base + Vector((0.3, 2.6, 1.3))], [0.9, 0.5, 0.0], 4,
                   lambda t, a, co, off: mix(P["thorn"], P["mush_red"], t))
    return {"PROP": [prop]}, {}


def dungeon_gate(rng, geo, gate):
    """Root tunnel into the ground: an earthen mound whose mouth faces the hub and slants down under the wall,
    fading to black, framed by arching roots. Returns an extra marker at the mouth (MARKER_DungeonGate)."""
    col, deco = geo("col"), geo("deco")
    noise = Noise("gate", rng.random())
    r_skirt, r_lip, r_mouth, depth, lip_back, lip_front = (gate[k] for k in
                                                          ("skirt", "lip", "mouth", "depth", "lipBack", "lipFront"))
    slant = gate["slant"]
    prof = [(0, -depth - 14), (r_skirt, -depth - 14), (r_skirt, -1.5), (r_skirt * 0.76, 2.2), (r_lip + 2.5, 1.0),
            (r_lip, 0.2), (r_mouth + 1.5, -0.5), (r_mouth, -3.0), (r_mouth * 0.92, -depth * 0.3),
            (r_mouth * 0.8, -depth * 0.6), (r_mouth * 0.6, -depth * 0.85), (0, -depth)]
    lip_share = {3: 0.5, 4: 1.0, 5: 0.85, 6: 0.3}
    inner_start = 6

    def adjust(i, t, a, co):
        a_ = 0.0 if a is None else a
        back = 0.5 - 0.5 * math.sin(a_)  # 1 at -Y (toward the wall), 0 at +Y (toward the hub)
        z = co.z
        if i in lip_share:
            z += lip_share[i] * (lerp(lip_front, lip_back, back ** 1.5)
                                 + 1.2 * noise((math.cos(a_) * 2, math.sin(a_) * 2, i), 1) * back)
        x, y = co.x, co.y
        if i >= inner_start:  # the tunnel slants down toward the wall (-Y)
            y -= slant * clamp(-co.z / depth)
        if a is not None and i in (2, 3, 4):
            w = 1 + 0.07 * noise((math.cos(a) * 1.5, math.sin(a) * 1.5, i * 2), 1)
            x, y = x * w, y * w
        return Vector((x, y, z))

    def color(i, t, a, co):
        if i < inner_start:
            return mix(P["ant_earth"], P["loam_light"], 0.6 if i in (4, 5) else 0.1), 0.25
        f = clamp((i - inner_start) / 4)
        return mix(P["loam"], P["tunnel"], smoothstep(0.0, 0.7, f))

    col.lathe(prof, 16, color, adjust=adjust)
    roots = geo("roots")
    for k, (ax, lift, span) in enumerate(((-0.6, 18, 1.0), (0.5, 22, 1.1), (0.05, 28, 0.9))):
        a0 = -math.pi / 2 + ax
        p0 = Vector((math.cos(a0 - 0.9) * r_skirt * 0.9 * span, math.sin(a0 - 0.9) * r_skirt * 0.6, -3))
        p3 = Vector((math.cos(a0 + 0.9) * r_skirt * 0.9 * span, math.sin(a0 + 0.9) * r_skirt * 0.5 - 6, -4))
        mid = (p0 + p3) * 0.5 + Vector((0, 6, lift))
        MP.root(roots, rng, [p0, p0.lerp(mid, 0.6) + Vector((0, 0, lift * 0.3)), mid, p3.lerp(mid, 0.6) + Vector((0, 0, lift * 0.3)), p3],
                r0=3.6 - k * 0.5, r1=2.0, sides=6)
    for side in (-1, 1):  # roots that dive into the tunnel mouth
        p0 = Vector((side * (r_lip + 6), -r_lip * 0.6, 8))
        MP.root(roots, rng, [p0 + Vector((side * 6, -8, 10)), p0, Vector((side * r_mouth * 0.7, -4, -2)),
                             Vector((side * r_mouth * 0.4, -slant * 0.5, -depth * 0.5))], r0=3.0, r1=1.2, sides=6)
    for side in (-1, 1):  # glowing bell mushrooms flank the mouth
        for k in range(2):
            MP.mushroom(deco, rng, height=8 + k * 3, cap=3 + k * 0.6, shape="bell", tone="cream",
                        m=Matrix.Translation((side * (r_lip + 3 + k * 4), r_lip * 0.3 + k * 3, 1.5)))
    return {"COL": [col, roots], "DECO": [deco]}, {"DungeonGate": Vector((0, 0, 0))}


STATIONS = {
    "merchant": merchant,
    "outfitter": outfitter,
    "hatchery": hatchery,
    "molting_shrine": molting_shrine,
    "stash": stash,
    "dungeon_gate": dungeon_gate,
    "silk_tailor": silk_tailor,
    "quest_board": quest_board,
}
