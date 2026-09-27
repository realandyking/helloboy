# Spider Quest: Studio setup

The game is three kinds of place in one experience: the **Main Menu** (start place), the **Lobby**, and one **Dungeon** place per dungeon (Mossy Hollow first). Every place runs the same scripts, and its role decides what boots.

## 1. Install the scripts (do this in every place)
1. Open the place and make sure you are **not** in a playtest.
2. Paste each file into the Command Bar (View > Command Bar) and press Enter:
   - `SpiderQuest_Install_1.lua`, then `_2`, `_3` and `_4`, in any order.
   - `SpiderQuest_Install_Templates.lua` (UI panels, placeholder spider, silk beam).
   - Each file is one undo step. It refuses to run in Pursuit of Immortality and never overwrites a script it didn't make.
   - Re-run newer files to update. A script you have edited in Studio (for example PlaceConfig) is kept, and the Output names it. To take the new version, delete that script and re-run.
3. Put the **ProfileStore** ModuleScript in `ServerScriptService.Packages`. Get it from the Creator Store, from GitHub (MadStudioRoblox/ProfileStore), or copy it from Pursuit of Immortality, which is read-only: copy, never edit.
4. Tell the place its role by running one line in the Command Bar:
   - `workspace:SetAttribute("PlaceRole", "MainMenu")` in the Main Menu
   - `workspace:SetAttribute("PlaceRole", "Lobby")` in the Lobby
   - `workspace:SetAttribute("PlaceRole", "Dungeon")` and `workspace:SetAttribute("DungeonId", "mossy_hollow")` in Mossy Hollow
5. To test real saves in Studio, turn on Game Settings > Security > **Enable Studio Access to API Services**. Otherwise ProfileStore uses its mock store.

## 2. Import the maps
The maps are FBX files built in Blender: `blender/exports/maps/`.
1. Import the place's map with the 3D Importer (or the asset bridge; **ask before uploading**, since uploads publish to the group):
   - Main Menu: `main_menu.fbx`
   - Lobby: `lobby.fbx`
   - Mossy Hollow: the 7 rooms in `mossy_hollow/`. Name each model after its file (`mossy_entry`, `mossy_hall`, ...), run map prep on each, then put them in `ServerStorage.RoomTemplates`. **Leave nothing in Workspace:** the dungeon is built there at runtime, with the entry room at the origin.
2. Check the size on the first import: the spider is about 4 studs across, and the manifest next to each FBX lists expected bounds.
3. Select the imported model(s) and run `SpiderQuest_MapPrep.lua` in the Command Bar. It anchors everything, sets collision by prefix (`COL_` precise, `PROP_` hull, `DECO_` none, `BARRIER_` invisible and unclimbable), turns `MARKER_*` into invisible marker parts, and adds the station prompts in the Lobby.
4. Main Menu only: set `Workspace.StreamingEnabled = false` (the scene is small and the menu camera needs it all).

## 3. Play-test
**Lobby:** press Play. The Output should show:
```
[Server:Lobby] started DataService, SettingsService, SilkService, SpawnService, TravelService
[Client:Lobby] started PlatformController, DataController, NoticeController, UIController, InputController, MovementController
[Data] profile loaded, schema v1, amber 0
[Net] ping ok in N ms
```
- Walk into a wall and keep pushing forward to climb it; walk over edges; climb onto ceilings.
- Jump (Space / A / touch jump) pushes off a surface; from a ceiling it drops.
- Aim the crosshair and press **F / LB / Silk** to zip on a Silk Line.
- **M / D-pad up / Menu** opens Settings. Toggle a setting, rejoin, and it's kept.
- Walk to the Dungeon Gate station and press **G / B** to open the Dungeon Gate panel. In Studio, "Enter" says teleports only work in the published game.
- Test phones and consoles with Studio's device emulator. Touch buttons appear only in touch mode, and key hints swap to gamepad glyphs when you use a controller.

**Main Menu:** the camera frames the menu scene, and Play says teleports only work in the published game.

**Mossy Hollow:** press Play. The server builds a test run from seed 1, and the Output shows `[DungeonService] built mossy_hollow: N rooms (seed 1)`. You spawn in the entry room and can walk the whole dungeon to the boss chamber. To see another layout, run `workspace:SetAttribute("DungeonSeed", 42)` (any number) and play again. Live runs get a random seed from the lobby.

## 4. Publish and connect the places
1. Publish each place into the same experience (the Main Menu is the start place).
2. Put each place id into `ReplicatedStorage.Shared.Config.PlaceConfig` (`main_menu`, `lobby`, `dungeon_mossy_hollow`) in **every** place. Later installer runs keep your edited PlaceConfig. Tell Claude the ids to have them built into the installers.
3. Travel now works: Main Menu → Lobby → Dungeon Gate → a fresh Mossy Hollow server → Return to Lobby (Settings, in the dungeon).

## Tuning
All tuning lives in config modules: `MovementConfig` (speeds, probes, silk), `InputConfig` (bindings per platform), `PlaceConfig`, `NoticeConfig`, `NetConfig` (channels and rate limits), `DataConfig`, and the registries. Code never needs editing to tune.
