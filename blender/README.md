# Spider Quest: Blender pipeline

Everything here is built **headless** from scripts, so a rebuild is repeatable and the live Blender is never touched.

```
blender/
  scripts/
    spider_config.py    forms (proportions, palette, tri budget) and clip settings: edit this first
    build_spider.py     mesh + Spider rig + clips -> sources/<form>.blend, exports/<form>.fbx
    spider_anims.py     clip builders (Idle, Walk); all keys eased Bezier
    render_preview.py   Cycles CPU preview sheets -> renders/
  sources/              .blend files (generated; rebuild instead of hand-editing)
  exports/              mesh + rig FBX for Studio import
  renders/              preview sheets for review
```

## Build

With Blender installed:
```
blender -b -P blender/scripts/build_spider.py -- --form spiderling
blender -b -P blender/scripts/render_preview.py -- --form spiderling
```
Or with the `bpy` wheel (`pip install bpy pillow`, Python 3.11) run the same scripts with `python`.

The build fails loudly if the form goes over its `triBudget` or any vertex isn't bound to exactly one bone.

## The Spider rig

All player spiders share this skeleton. Only the proportions change per form, so every clip plays on every form. Human-shaped NPCs use R6 instead.

```
Root                                   ground, origin
└─ HumanoidRootPart                    body centre
   └─ Cephalothorax
      ├─ Abdomen
      │  └─ Spinnerets                 Silk Line / web VFX origin
      ├─ Chelicera_L ─ Fang_L          bite VFX (same for _R)
      ├─ Pedipalp_L_Upper ─ Pedipalp_L_Lower   (same for _R)
      └─ Leg_L1_Femur ─ Leg_L1_Tibia ─ Leg_L1_Tarsus
         ... L1–L4 and R1–R4, where 1 is the front pair
```
- There are 37 bones. Skinning is **rigid**: each vertex follows exactly one bone, like real exoskeleton segments. That keeps it cheap and makes joints hinge cleanly.
- Roblox Bones are Attachments, so `Spinnerets` and `Fang_L/R` work directly as VFX and hitbox anchors.
- **Axes:** on every leg, palp, ceph and abdomen bone, **+X rotation lifts the bone's tip**. **+Z swings a left leg forward and a right leg back.** Clips key rotations only (plus a small ceph bob), so they retarget across forms.
- **Space:** 1 Blender unit = 1 stud, the spider faces -Y, and its left is +X. The FBX export uses -Z forward and Y up, with no leaf bones.

## Forms

| Form | Tris | Size (studs) | Clips |
|---|---|---|---|
| `spiderling` | 2,318 / 3,000 | 3.6 wide × 4.3 long × 1.9 tall | Idle (2.0 s, loop), Walk (0.8 s cycle, loop) |

To add a form, add an entry to `FORMS` in `spider_config.py` (proportions, palette, budget), then build it. Keep the bone names as they are.

## Clips

- **Idle:** breathing abdomen, palp taps, a fang flex, and a small weight shift. It loops.
- **Walk:** an alternating tetrapod gait (L1, R2, L3, R4 against the other four), with a body bob and roll. It loops. In game, scale its speed to walk speed. Foot sliding is expected until procedural foot placement (`IKControl`) lands with the wall-walk controller.
- Loop clips end on their first pose. After import set `Loop = true`, with priority Idle for Idle and Movement for Walk.
- **The asset bridge converts Blender actions directly.** Each clip is a named action (`Idle`, `Walk`) with a fake user in `sources/<form>.blend`. The custom properties `frames` and `loop` on each action carry its length and loop flag. Pass `--clip-fbx` only if you need a baked FBX per clip.

## Studio import checklist (do this on the first import; not yet verified in Studio)

1. Import `exports/spiderling.fbx` as a rig. Check the size against the table above. If it's off, change the importer's scale unit, not the source.
2. Check that the spider faces the model's forward (LookVector). If it faces backwards, fix the export axis in `build_spider.py` and re-export.
3. Check that the vertex colours show, and that the bones sit under the MeshPart with the names above.
4. Convert the `Idle` and `Walk` actions from `sources/spiderling.blend` with the asset bridge, then set Loop and Priority.
5. **Ask before uploading.** Asset-bridge uploads publish to the group.

Write anything you learn here back into this checklist and into `build_spider.py`.
