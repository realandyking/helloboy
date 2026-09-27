# Maps status

All three maps build, pass every check, and export.
- **Checks that raise:**
  - budgets (per object and per map or room);
  - Mossy Hollow doorways (with barriers included), footprints and room lids;
  - the lobby boundary ring and sheet web.
- **Review:** after the fix pass, each map's previews have been reviewed.

## Current totals

Totals count every instance, including `BARRIER_` parts. Markers are not counted.

| Map / room | Tris / budget | Objects | Barrier | Exports |
|---|---|---|---|---|
| `main_menu` | 19,512 / 25,000 | 119 | none (camera-only place) | `exports/maps/main_menu.fbx` + `main_menu.manifest.json` |
| `lobby` (Webhollow) | 55,334 / 60,000 | 362 | `BARRIER_Boundary_01..36` (432 tris) | `exports/maps/lobby.fbx` + `lobby.manifest.json` |
| `mossy_entry` | 5,292 / 8,000 | 35 | `BARRIER_Lid` at z 51.31 | `exports/maps/mossy_hollow/mossy_entry.fbx` |
| `mossy_hall` | 5,730 / 8,000 | 33 | lid at z 51.46 | `.../mossy_hall.fbx` |
| `mossy_turn` | 6,288 / 8,000 | 39 | lid at z 50.68 | `.../mossy_turn.fbx` |
| `mossy_arena_small` | 12,106 / 15,000 | 81 | lid at z 55.36 | `.../mossy_arena_small.fbx` |
| `mossy_arena_large` | 12,480 / 15,000 | 84 | lid at z 56.02 | `.../mossy_arena_large.fbx` |
| `mossy_treasure` | 7,456 / 8,000 | 28 | lid at z 51.80 | `.../mossy_treasure.fbx` |
| `mossy_boss` | 17,600 / 25,000 | 102 | lid at z 57.88 | `.../mossy_boss.fbx` |

- `exports/maps/mossy_hollow/manifest.json` lists, for each room:
  - the doorway measurements (every opening is 28 wide and 29 tall at the crown; the required clear passage is 24 × 20);
  - the lid (underside, top, lowest wall top, clearance);
  - anything the build lowered or shrank to fit under it.
- `lobby.manifest.json` records the boundary ring.
- Sources are in `sources/maps/<map>.blend`. In `mossy_hollow.blend`, rooms are spread out for previewing and their object names carry a `.<room>` suffix, because Blender names must be unique. The FBX files use the clean names, and each room is exported at its own origin.

## Fixed in the fix pass

- **`BARRIER_` prefix** (new): invisible collision the spider controller can't stick to. Studio makes it invisible, collides with it, and excludes it from raycasts.
  - These are convex hexahedra (12 tris each) in one flat grey vertex colour.
  - They are never baked and never act as AO occluders.
  - They are hidden in every preview render.
- **Room lids.** Every Mossy Hollow room has a `BARRIER_Lid` over its whole footprint, 1 stud under the lowest wall top.
  - Walls were raised to 52–64. Logs, ceiling roots and canopies were lowered in config so the partial ceilings still read as ceilings under the lid.
  - The build fits anything left over: the hall's canopy was lowered 1.7 studs.
  - The check raises if a climbable interior piece comes within 3 studs of the lid.
  - The doorway check now also raises if a `BARRIER_` intrudes into a passage. A negative test confirmed it fires, as do the lid and lobby-boundary checks.
- **Lobby boundary.** `BARRIER_Boundary` is a ring of 36 convex slabs, 200 tall, at r 218–222, just inside the grass and pebble ring.
  - The ring props moved out to r ≥ 242, and the outer scatter and buttress roots pulled in, so nothing climbable straddles the barrier. The check raises otherwise.
  - The entrance and all stations stay inside.
- **Mossy Hollow wall backs.** The outward face of every wall piece is now a quad grid matching the inner face's columns and rows, not one n-gon.
  - Nothing lies on the boundary plane any more, so no two faces z-fight there or bake black:
    - wall backs sit 0.05 studs inside the boundary;
    - outer wall ends sit 0.1 inside, tucked into the neighbouring wall;
    - corner boulders are clipped 0.3 inside.
  - Verified from outside in `mossy_hollow_close.jpg` (the two "outside" panels).
- **Previews:**
  - the black "entry spawn" panel now looks back at the spawns from the north doorway lane;
  - the contact sheet camera is high and steep enough to see into the 1×1 rooms;
  - the spare cell shows entry → hall → arena_small snapped at their connectors.
- **Lobby look:**
  - The interior wood and mulch are brighter, and shading is softer (lobby occlusion 0.45, bottom light 0.74). Baked medians went from 0.30 to 0.36 on the inner wall and from 0.28 to 0.32 on the floor; the darkest 10% went from 0.15 to 0.21. The streaks and moss still vary.
  - The sheet web has a dusky funnel centre (now a single pole vertex), alternating radial bands, ridge relief, and radial and concentric threads.
  - The ledges under the web were re-spaced so none pokes through it, which is now checked.

## Still open

- **Lobby preview lighting.** The station close-ups still read dim in the previews: they sit in the stump's shadow under a single preview sun. In Studio, Roblox ambient and `EnvironmentDiffuseScale` decide this.
- **Not verified in Studio:**
  - FBX import behaviour.
  - Whether linked duplicates import as shared MeshIds.
  - Vertex colours.
  - Pivots. Markers are centred on their origin, so a bounds-recentring import still gives the exact position.
  - How the map prep tool handles `BARRIER_` (invisible, `CanCollide`, excluded from spider raycasts).

## Rebuild commands

Use any Python with bpy 5.0 and Pillow. With Blender instead, run `blender -b -P <script> -- <args>`.

```
PY=python   # e.g. the session venv: /tmp/claude-0/-home-user-helloboy/e94dfa7a-7753-568e-8df6-73aff00e46b7/scratchpad/bvenv/bin/python
$PY blender/scripts/maps/build_map.py --map main_menu
$PY blender/scripts/maps/build_map.py --map lobby
$PY blender/scripts/maps/build_map.py --map mossy_hollow
$PY blender/scripts/maps/render_map.py --map main_menu      # renders/maps/main_menu_views.jpg
$PY blender/scripts/maps/render_map.py --map lobby          # lobby_views.jpg, lobby_stations.jpg
$PY blender/scripts/maps/render_map.py --map mossy_hollow   # mossy_hollow_rooms.jpg, mossy_hollow_close.jpg
```

- `--draft` reports budget overruns instead of raising and never exports. Use it only for preview iteration; all the other checks still raise.
- `--only <sheet>` renders a single sheet, and `--samples N` sets quality.

## Files

`blender/scripts/maps/`:
- `map_kit.py` holds the geometry builder, noise, vertex-paint bake, markers, barriers, budgets, FBX and manifest.
- `map_props.py` holds the prop generators.
- `map_stations.py` holds the 8 lobby stations.
- `map_config.py` holds the palette, shading, the kit, and one entry per map and room (lids, boundary, views).
- `build_map.py` builds a map and runs its checks.
- `render_map.py` renders the preview sheets.
