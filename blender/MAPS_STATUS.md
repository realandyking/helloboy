# Maps status (paused mid-polish)

All three maps build, pass their budget checks, and export. Mossy Hollow rooms also pass their doorway and footprint checks. The visual polish is part-done: the lobby had about three look-and-fix passes, the menu about two, and Mossy Hollow only one render, which may not be reviewed yet.

## Done

| Map / room | Tris / budget | Objects | Exports |
|---|---|---|---|
| `main_menu` | 19,512 / 25,000 | 119 | `exports/maps/main_menu.fbx` + `main_menu.manifest.json` |
| `lobby` (Webhollow) | 55,728 / 60,000 | 328 | `exports/maps/lobby.fbx` + `lobby.manifest.json` |
| `mossy_entry` | 4,650 / 8,000 | 34 | `exports/maps/mossy_hollow/mossy_entry.fbx` |
| `mossy_hall` | 5,018 / 8,000 | 32 | `.../mossy_hall.fbx` |
| `mossy_turn` | 5,576 / 8,000 | 38 | `.../mossy_turn.fbx` |
| `mossy_arena_small` | 10,834 / 15,000 | 80 | `.../mossy_arena_small.fbx` |
| `mossy_arena_large` | 11,138 / 15,000 | 83 | `.../mossy_arena_large.fbx` |
| `mossy_treasure` | 6,814 / 8,000 | 27 | `.../mossy_treasure.fbx` |
| `mossy_boss` | 15,810 / 25,000 | 101 | `.../mossy_boss.fbx` |

- Mossy Hollow has one `exports/maps/mossy_hollow/manifest.json` for all rooms. For each room it records the doorway measurements: every opening is 28 wide and 29 tall at the crown, and the required clear passage is 24 × 20.
- Sources are in `sources/maps/<map>.blend`. In `mossy_hollow.blend`, rooms are spread out for previewing and their object names carry a `.<room>` suffix, because Blender names must be unique. The FBX files use the clean names, and each room is exported at its own origin.
- Tri totals count every instance, including linked duplicates. Markers are not counted.

## Partial / not yet done

- **Mossy Hollow visual review.** Only one render pass. Known issues from `renders/maps/mossy_hollow_rooms.jpg`:
  - **Dark shards on the wall backs.** The outer, boundary-side face of each wall piece is one n-gon (`thick_panel(simple_b=True)` in `map_kit.py`). Its triangulation fans into dark shards. That face is hidden when rooms are adjacent, but it shows from outside and from above. Fix: fill the back with `triangle_fill` or a quad grid.
  - **Contact-sheet framing.** The camera is too low and close for 1×1 rooms (it shows their outsides). Raise it or pull it back in `render_map.py` (the `rooms` sheet).
  - **Rooms still to look at.** `mossy_hollow_close.jpg` hasn't been reviewed yet. Then tune wall colour, prop density and the ceiling pieces.
- **Lobby polish.** The interior is dark in the previews and the sheet web still reads a little flat. The ground colour is blotchy from far away.
- **Main menu.** The last tweaks (tighter web frame, fireflies dropped onto caps) are built and exported, but their render may not be reviewed yet.
- **`blender/README.md` Maps section.** Not written yet. This file stands in for it.
- **Not verified in Studio:**
  - FBX import behaviour.
  - Whether linked duplicates import as shared MeshIds.
  - Vertex colours.
  - Pivots. Markers are centred on their origin so a bounds-recentring import still gives the exact position.

## Rebuild commands

Use the bpy venv. With Blender instead, run `blender -b -P <script> -- <args>`.

```
PY=/tmp/claude-0/-home-user-helloboy/e94dfa7a-7753-568e-8df6-73aff00e46b7/scratchpad/bvenv/bin/python   # or any python with bpy 5.0 + Pillow
$PY blender/scripts/maps/build_map.py --map main_menu
$PY blender/scripts/maps/build_map.py --map lobby
$PY blender/scripts/maps/build_map.py --map mossy_hollow
$PY blender/scripts/maps/render_map.py --map main_menu      # renders/maps/main_menu_views.jpg
$PY blender/scripts/maps/render_map.py --map lobby          # lobby_views.jpg, lobby_stations.jpg
$PY blender/scripts/maps/render_map.py --map mossy_hollow   # mossy_hollow_rooms.jpg, mossy_hollow_close.jpg
```

- `--draft` reports budget overruns instead of raising and never exports. Use it only for preview iteration.
- `--only <sheet>` renders a single sheet, and `--samples N` sets quality.

## Files

`blender/scripts/maps/`:
- `map_kit.py` holds the geometry builder, noise, vertex-paint bake (light, AO, moss, hue shift, jitter), markers, budgets, FBX and manifest.
- `map_props.py` holds the prop generators.
- `map_stations.py` holds the 8 lobby stations.
- `map_config.py` holds the palette, shading, the kit, and one entry per map and room.
- `build_map.py` builds a map.
- `render_map.py` renders the preview sheets.


## Review notes (main session)
- The Main Menu and Lobby renders read well. The Lobby interior is on the dark side, which is a lighting/Studio question more than a mesh one.
- The `entry spawn` panel of `renders/maps/mossy_hollow_close.jpg` renders solid black. The preview camera is probably inside geometry, so fix the view in `render_map.py` before judging the entry room.
