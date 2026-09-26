# Spider Quest

A Roblox co-op dungeon crawler. Players are spiders: they gear up in a lobby hub, dive into dungeons built from room templates for loot, and molt into new forms along spider **paths**. Each path changes how the spider plays.

> This file is both the project brief and the working rules for this folder. Every name, number and odds value below is a starting point. They live in config, so tune them there, not in code.

## Preferences
- Keep everything modular and scalable: config tables and registries, not hardcoded values.
- You have standing permission to playtest and take screenshots to check your own work.
### Project scope
- The game being built is **Spider Quest**.
- **Game code lives in Studio**, not in this repo. This repo holds only **docs and Blender files** (see "Repo layout" below).
- **Pursuit of Immortality** (the user's other game, often open in Studio) is **read-only**. Never edit it in any way.
  - You may take its assets and code when they fit Spider Quest. Copy them into Spider Quest and adapt them there.
  - You are encouraged to reuse its modular setup (registries, config and service patterns). Look at how Pursuit of Immortality does something before building it fresh.
- **Data uses ProfileStore** (see §14.4).
- **Delivering scripts:** with Studio MCP access, work in Studio directly. Without it, hand scripts over as a **Command Bar installer** the user pastes and runs. Installers must be idempotent and a single undo step, must refuse to run during a playtest or in Pursuit of Immortality, and must never overwrite a script they didn't create.
### Repo layout
```
CLAUDE.md            this brief + rules
blender/             headless Blender pipeline (see blender/README.md)
  scripts/           config-driven build scripts; spider_config.py holds forms and clips
  sources/           generated .blend files (rebuild, don't hand-edit)
  exports/           mesh + rig FBX for Studio import (clips go through the asset bridge)
  renders/           preview sheets for review
```
### Networking rules
- **One RemoteEvent (`ReplicatedStorage.Net`) carries everything.** A new message is a new channel in `NetConfig`, never a new remote. Don't use RemoteFunctions: request/response runs over the same remote (`Net.request`).
- Packets are batched and fired once per frame. The server checks every client packet's channel, direction, rate limit and argument types before a handler sees it.
- Send small payloads: ids and numbers, not names or instances the other side can look up. Replicate deltas, not whole tables, and send only to the players who need them.
- Replicated tables are pure arrays or string-keyed dictionaries, never mixed or sparse (remotes drop those).
### Platform rules
- **PC, console and mobile are all first-class.** Every action has a keyboard/mouse binding, a gamepad binding and a touch button in `InputConfig`. Gameplay code listens for named actions and never checks devices.
- Every panel works with a gamepad: a default selected button, sensible selection order, and B/back to close. Button prompts swap with the current input mode (`PlatformController`).
- Console players sit far from the screen, so keep text large and HUD elements inside the safe area.
### UI rules
- All UI is authored in Studio as real instances. Scripts only clone and fill templates; they never build UI with `Instance.new`. Dynamic lists clone a Studio-authored template row.
- House style is the fantasy stylized.
- Phones: fit tall panels with `UIFit`, and keep tap targets at least ~42 px.
### Art rules
- 3D assets are made in Blender: low-tri, stylized in both modelling and texturing, Deepwoken-like, vertex-painted.
- Assets models that require more detail can be above the quality of rite models, but not for bigger builds/models. Optimization is still the most important.
- For VFX, 2000 triangles is the max. Rely on Textures and Alpha Blending.
- Uploads through the asset bridge publish to the group, so **ask me before every upload batch**.
- Run Blender headless. The live Blender belongs to other sessions.
### Animations
- Clips are made in headless Blender, with easing. **Player spiders use the custom Spider rig** (`blender/`). **Human-shaped NPCs use the R6 rig.**
- Before reusing a borrowed clip, check its length and `Loop`. A skill fades out every track it starts.
- Every spider form shares the Spider rig's bone names and hierarchy, and only the proportions change. Spider clips key **rotations only** (apart from small body bobs), so one clip plays on every form.
- **The asset bridge converts Blender actions directly.** Keep each clip as a named action (with a fake user) in the form's `.blend`.
### Code rules (proposed with the plan; confirm or edit)
- **Server-authoritative.** The client sends intents ("use ability `venom_bite` toward X"). The server checks ownership, range, cooldown and cost, then applies the result. Damage, prices, drops and rewards are never taken from the client.
- **Content is data.** Every form, ability, item, affix, enemy, room, dungeon, banner, shop and panel is an entry in a registry, keyed by a stable snake_case id (`venom_t2`). Code refers to ids, never to display names or inline asset ids.
- **Registries validate at boot**: unique ids, required fields, and cross-references that resolve (for example, a form's ability ids must exist). In Studio, a bad entry fails loudly.
- **Saved data holds only ids and numbers.** No instances and no display strings. It carries a schema version plus a migration list. Change it only through `DataService`, so the client receives deltas.
- **Networking** follows the Networking rules above.

---

## 1. Vision
- **Fantasy:** you start as a tiny spider in a giant world and molt into a monster.
- **Scale:** the world is made of human-sized things seen from spider height. A grass blade is a tree, a mug is a tower, a cellar is a canyon.
- **Pillars**
  1. **Spider movement feels special.** You can walk on any wall or ceiling, swing or zip on silk, and ambush from above.
  2. **Evolution is the progression.** Each path changes how you play, not just your numbers.
  3. **Short co-op runs with big loot moments.** Runs take 10–20 min with 1–4 players, and you bring the loot back to sell or equip.
- **Focus:** PvE dungeons come first. A PvP arena comes later as its own registry-driven mode.
  4. **Readable on phones.** Telegraphs, UI and controls work on a small screen first.

## 2. Core loop
```
Lobby (Webhollow) ──► pick dungeon + difficulty + party ──► Dungeon run
      ▲                                                       │ rooms → mini-boss → boss
      │                                                       ▼
      └── sell loot · buy gear · hatch eggs · evolve ◄── extract with loot, XP, Molt Shards
```
- **Per session:** do a run, then bank the loot, sell the junk, equip upgrades, and queue again.
- **Long term:** level up, unlock evolution tiers and harder dungeons, collect paths and Broodlings, and chase rare gear.

## 3. Lobby: "Webhollow" (working name)
The hub is a giant hollow tree stump that you can climb inside and out. Each station opens a Studio-authored panel through a `ProximityPrompt`.

| Station | What it does | Notes |
|---|---|---|
| **Merchant** (sell) | Sell loot for Amber | Bulk-sell by rarity filter. Locked items are never sold. |
| **Outfitter** (buy gear) | Buy gear | Fixed starter stock plus rotating stock. The rotation schedule and pools live in `ShopRegistry`. |
| **Hatchery** (summon) | Open Egg Sacs to hatch Broodlings | Banners, odds and pity are covered in §8. |
| **Molting Shrine** (evolve) | Evolve, unlock paths, switch active path | Shows the path tree (§4). |
| **Stash** | Storage beyond the inventory cap | Size is config-driven and can be raised with a gamepass. |
| **Dungeon Gate / Party Board** | Create or join a party, pick dungeon and difficulty, teleport | Solo is allowed. |
| **Silk Tailor** (cosmetics) | Carapace dyes, silk colours, eye glow | Cosmetic only. |
| **Quest Board** | Dailies and weeklies | Entries live in `QuestRegistry`. |

## 4. Spiders and evolution

### 4.1 Universal kit (every form)
- **Movement:** walk on any surface (walls and ceilings), jump or leap off walls, **Silk Line** (grapple or zip to an aimed point), and **Silk Drop** (lower yourself from a ceiling on a thread).
- **Combat:** **Bite** as the M1 combo, plus up to three ability slots (Q / E / R) and one passive. Slots unlock by tier.
- **Resources:** **Health**, and **Silk**, the ability resource that regenerates. Web abilities spend it.
- **Downed state:** you are **Cocooned** instead of dying. A teammate holds interact to cut you free before a timer runs out.

### 4.2 Evolution structure
```
Spiderling (T0) ──Lv 10──► Path T1 ──Lv 25──► Path T2 ──Lv 45──► Apex T3 (pick 1 of 2)
 Bite + Silk Line          + Q, passive        + E                + R (ultimate), apex tweaks
```
- An evolution costs **Molt Shards** (dungeon drops) plus **Amber**. Levels and costs live in `ProgressionConfig` and each form's `requirements`.
- **Collect-and-switch (decided):** player level is account-wide and gates tiers. Each path has its own **Mastery** track. Unlocking another path costs Molt Shards. You switch your active path at the Molting Shrine, and only in the lobby. This keeps every path worth trying and lets new paths drop in as content.

### 4.3 Launch paths (4)
| Path | Role | T1 → T2 → T3 apex options | Q (T1) | E (T2) | Passive | R ultimate (by apex) |
|---|---|---|---|---|---|---|
| **Weaver** | Control / support | Web Spinner → Orb-Weaver → **Golden Orb-Weaver** \| **Net-Caster** | *Web Trap*: a snare zone that slows, then roots | *Mending Cocoon*: shields an ally | *Silk Affinity*: regen Silk while standing on your own webs | Golden: *Great Orb*, a huge web zone that heals allies and slows enemies. Net-Caster: *Casting Net*, which roots a group and drags it in. |
| **Hunter** | Melee DPS / mobility | Wolf Spider → Brood Wolf → **Huntsman** \| **Jumping Spider** | *Pounce*: a gap-closer, stronger when launched from a wall or ceiling | *Brood Scatter*: spiderlings leap off your back and nip enemies | *The Hunt*: bonus damage to targets you pounced | Huntsman: *Sidewinder Rush*, multi-dashes through enemies. Jumping Spider: *Skyfall*, a long leap into an AoE slam that chains off walls. |
| **Venom** | DoT / assassin | Cobweb Spider → Widow → **Black Widow** \| **Brown Recluse** | *Venom Bite*: applies venom stacks | *Hourglass Mark*: the marked target takes more damage from the whole party | *Venom Stacks*: poison ticks scale with stacks | Black Widow: *Neurotoxin*, which detonates all stacks for single-target burst. Recluse: *Necrotic Bloom*, an AoE rot that cuts healing and spreads. |
| **Brute** | Tank | Young Tarantula → Tarantula → **Goliath Birdeater** \| **Trapdoor Spider** | *Urticating Hairs*: AoE flick that deals damage and taunts | *Hunker*: damage reduction and knockback immunity | *Thick Carapace*: damage reduction above 50% HP | Goliath: *Titan Stance*, a big taunt with a party damage-reduction aura. Trapdoor: *Ambush Lair*, burrow in and your next hit stuns and executes. |

- Apex forms can also modify core abilities through `abilityOverrides`. For example, Recluse's *Venom Bite* spreads to nearby enemies.
- **Future paths** (drop-in registry entries): Spitting Spider (ranged), Peacock Spider (bard-style buffs from dances), Crab Spider (camouflage / stealth), Bolas Spider (lasso pulls), Diving Bell Spider (water biome).
- **Colour and silhouette language:** Weaver is gold and cream with a round abdomen. Hunter is brown with grey stripes and long legs. Venom is glossy black with red marks. Brute is dusty brown and blue-black, hairy and bulky.

### 4.4 Form entry (example shape)
```lua
-- ReplicatedStorage/Shared/Registries/Forms/venom_t2.lua
return {
    id = "venom_t2",
    path = "venom",
    tier = 2,
    displayName = "Widow",
    evolvesFrom = "venom_t1",          -- the tree is built from these links at boot
    requirements = { level = 25, amber = 5000, items = { molt_shard = 40 } },
    baseStats = { health = 420, attack = 38, defense = 12, moveSpeed = 18, silk = 100, silkRegen = 6 },
    abilities = { q = "venom_bite", e = "hourglass_mark" },
    passive = "venom_stacks",
    model = "spider_widow",            -- key into ModelRegistry, never a raw asset id
    animSet = "spider_medium",         -- key into AnimSetRegistry
}
```

## 5. Combat
- Action combat. Bite combos on M1, and abilities have cooldowns and Silk costs, all defined in `AbilityRegistry`. Each ability entry points at a handler module (projectile, zone, dash, buff, summon, and so on), so a new ability is usually data only.
- **Hit detection:** the server uses spatial queries with a small latency tolerance. The client plays animations and VFX right away for feel, and the server has the final say.
- **Status effects** (`StatusEffectRegistry`): Poisoned (stacks), Webbed (slow), Rooted, Stunned, Necrosis (heal reduction), Shielded, Taunted, Burrowed.
- **Damage formula** lives in `CombatConfig`. Example: `atk × abilityScalar × 100/(100+def) × crit × modifiers`.
- **Enemy telegraphs:** ground decals and alpha-textured VFX, readable on phones and within the VFX triangle cap.
- Friendly fire is off.

## 6. Gear and items
- **Gear slots:** **Fangs** (scales Bite and physical damage), **Carapace** (armor), **Spinnerets** (modify Silk and web abilities), and **Charm ×2** (utility).
- **Rarities** (`RarityRegistry`): Common, Uncommon, Rare, Epic, Legendary, Mythic. Each rarity sets its colour, affix count and sell multiplier.
- **An item** is a base (`ItemRegistry`) plus rolled affixes (`AffixRegistry`) plus an item level. It is saved as `{ id, lvl, affixes = { {id, value} }, locked, uid }`.
- **Other item types:** materials (Molt Shards, Silk Thread, biome materials), consumables (a Dew Drop heal, for example), Egg Sacs, and cosmetics.
- **Stretch:** a Silk Loom that upgrades and rerolls affixes, which also works as an Amber sink.

## 7. Economy
| Currency | Source | Spent on |
|---|---|---|
| **Amber** (soft) | Selling loot, run rewards, quests | Gear, evolution, rerolls, path unlock fees |
| **Molt Shards** (progression) | Dungeon drops, boss chests | Evolution, path unlocks |
| **Moonstones** (premium) | Robux dev products, plus a trickle from dailies and achievements | Egg Sacs, cosmetics, stash space |

- Entries live in `CurrencyRegistry`, and sources and sinks are tuned in `EconomyConfig` per dungeon tier.
- Every source and sink logs through `AnalyticsService` economy events so balance can be tuned from real data.

## 8. Summoning: Hatchery
- Players open **Egg Sacs** to hatch **Broodlings**. A Broodling is a companion spiderling that follows you, grants a passive bonus, and has one small active (for example, it swarms your target).
- **Banners** (`BannerRegistry`): pool, rarity weights, featured Broodling, start and end time, cost, and pity family.
- **Pity:** a guaranteed Epic every N hatches and a Legendary at M (config). Counters are saved per pity family.
- **Duplicates** star up the Broodling or convert into Brood Essence.
- You can equip 1 Broodling, or 2 with a gamepass.
- **Compliance:** show the odds in the Hatchery panel before any purchase. Check `PolicyService:GetPolicyInfoForPlayerAsync().ArePaidRandomItemsRestricted`, and where paid random items are restricted, only allow Egg Sacs bought with earned currency.

## 9. Dungeons

### 9.1 Run structure
- A party of 1–4 picks a **dungeon** and a **difficulty** (Normal / Hard / Nightmare). Difficulty scales enemy HP and damage, and those multipliers also scale with party size (`DungeonConfig`).
- **Room flow:** entry → combat, event and treasure rooms → mini-boss → boss → extraction chest.
- **Generator:** assembles Studio-built **room templates** by snapping together connector attachments. The room pool, counts and weights come from `DungeonRegistry` and `RoomRegistry`. RNG is seeded, so a run can be reproduced for debugging.
- **Vertical design:** spiders climb, so rooms use walls and ceilings: ceiling routes, hidden nooks, drop ambushes and falling hazards.

### 9.2 Biomes
| Dungeon | Theme | Enemies | Boss |
|---|---|---|---|
| **Mossy Hollow** (launch) | Forest floor, moss, mushrooms | Ants, pill bugs, ground beetles, mites | **Ant Queen** (spawns adds) |
| **The Cellar** (launch) | Damp basement, jars, pipes | Centipedes, silverfish, cockroaches | **Great Centipede** |
| The Wasp Nest | Paper hive, honeycomb | Wasps, larvae | **Tarantula Hawk** (the spider-hunting wasp and the series nemesis) |
| The Garden | Flowers, pond edge | Mantises, dragonflies, frogs | **Mantis Matriarch** |
| The House (endgame) | Giant human rooms | Mixed | **The Housecat** |

### 9.3 Enemies
- Each `EnemyRegistry` entry holds stats, an AI archetype, abilities, a loot table, a model, an anim set, a spawn weight and a tier scaling curve.
- **AI archetypes** are reusable modules: Swarmer, Bruiser, Ranged, Flier, Burrower and Summoner. They are simple server-side state machines, updated in batches, with a per-room enemy cap for performance.

### 9.4 Loot
- `LootTableRegistry` holds weighted entries and nested tables. Difficulty and luck modify the rarity roll.
- **Personal loot:** each player rolls their own drops, so nobody fights over loot.
- A run's loot is banked on a successful extraction. **A wipe keeps no loot**, only a small Amber payout (`DungeonConfig.wipeAmber`).

## 10. Progression summary
- **Player Level**, from run XP, gates evolution tiers and difficulties.
- **Path Mastery** unlocks cosmetics and small path-specific bonuses.
- **Gear power**, **Broodlings**, and **dungeon unlocks** (beating a boss unlocks the next dungeon).
- **Dailies, weeklies and achievements** come from `QuestRegistry`.

## 11. Controls (defaults live in `InputConfig`)
| Action | PC | Gamepad | Mobile |
|---|---|---|---|
| Move | WASD | Left stick | Thumbstick |
| Bite | M1 | RT | Attack button |
| Abilities | Q / E / R | X / Y / RB | Ability buttons |
| Silk Line | F | LB | Silk button (aims with the camera) |
| Jump / leap off wall | Space | A | Jump |
| Interact / revive | G | B | Prompt button |

- On mobile, keep every button at least ~42 px and cluster them around the right thumb.
- Movement, jump and camera stay on Roblox's default controls until the spider movement controller replaces them.
- Menus follow the Platform rules: gamepad navigation, and prompts that swap with the input mode.

## 12. UI screens
All screens are Studio-authored under `StarterGui`, and every list clones a row from its `Templates` folder.
- **HUD:** health, Silk, ability bar with cooldowns, party frames, Broodling, and the run loot counter.
- **Inventory and equip:** gear slots, stat compare, lock toggle.
- **Merchant, Outfitter and Stash.**
- **Hatchery:** banner, odds table, pity counter, hatch reveal.
- **Molting Shrine:** path tree, requirements, evolve and switch.
- **Party / Dungeon select, Run results, Quests, Settings.**
- **Pattern:** `UIController` opens panels by id from `PanelRegistry`. Each panel module binds to its Studio instance, clones template rows, and applies `UIFit` on phones.

## 13. Art and audio direction
- The look follows the Art rules above: Deepwoken-like, stylized, low-tri and vertex-painted, with painterly lighting and strong silhouettes.
- **Selling the scale:** oversized props, depth fog, and big soft light shafts.
- **Proposed triangle budgets** (starting points to tune, with the Art rules taking precedence): a player spider is about 3k at T1 and about 6k at an apex. Small enemies are about 1.5k, bosses about 8k, room-kit pieces 0.5–2k. VFX stay at 2k or less, per the rules.
- **Spider rig (built; see `blender/README.md`):**
  - One shared 37-bone skeleton for every player form: `Root → HumanoidRootPart → Cephalothorax`, then the abdomen, chelicerae and fangs, pedipalps, and 8 legs × Femur/Tibia/Tarsus.
  - Skinning is rigid, one bone per vertex.
  - `Spinnerets` and `Fang_L/R` double as VFX anchors.
  - The Spiderling base form (2.3k tris) comes with Idle and Walk clips.
  - It has not yet been checked in Studio. The import checklist is in the README.
- **Other creatures:** insect enemies (ants, centipedes, wasps) get their own rig per body plan, built with the same config-driven pipeline.
- **VFX:** alpha-textured particles and beams. Silk lines are `Beam`s, and web decals, venom drips and pollen puffs are particles.
- **Audio:** skittering footsteps sized per form, a silk "thwip", chitters and hisses, and a music bed per biome.

## 14. Technical architecture

### 14.1 Places
- There are two places: a **Lobby place** and a **Dungeon place**. Dungeon runs use reserved servers through `TeleportService:TeleportAsync` with `TeleportOptions.ReservedServerAccessCode`.
- Teleport data passes through the client and can be spoofed. So the lobby writes a **run record** (party, dungeon id, difficulty, seed) to `MemoryStoreService`, keyed by run id, and the dungeon server reads that record instead of trusting teleport data.

### 14.2 Studio layout (installed by the core installer)
```
ReplicatedStorage/
  Net                  the one RemoteEvent
  Shared/
    Config/            NetConfig (channels), InputConfig (bindings per platform)
    Registries/        Currencies (more registries join here)
    Modules/           Net, NetCodec, Registry, Signal, TableUtil, Boot
ServerScriptService/
  Packages/            ProfileStore (inserted by hand)
  Server/
    Main               boots Net, then every Service
    Config/            DataConfig (template, schemaVersion, migrations)
    Modules/           ProfileUtil
    Services/          DataService
StarterPlayerScripts/
  Client/
    Main               boots every Controller; pings the server in Studio
    Controllers/       PlatformController, InputController, DataController
```
- **Planned additions** go in the same folders:
  - Configs: Combat, Economy, Progression, Dungeon.
  - Registries: Forms, Abilities, StatusEffects, Items, Affixes, Rarities, Enemies, Dungeons, Rooms, LootTables, Banners, Broods, Shops, Quests, Panels, Models, AnimSets.
  - Services: Inventory, Economy, Shop, Hatchery, Evolution, Combat, Ability, Status, Enemy, Dungeon, Loot, Party, Travel, Quest.
  - Controllers: UI, Ability, Movement (climb + silk), Camera, VFX, Audio.
  - Elsewhere: `ServerStorage` (RoomTemplates, EnemyModels) and `StarterGui` (panels + Templates).
- Each service or controller is a ModuleScript with optional `priority`, `init()` and `start()`.
- `Boot` runs every `init` (highest priority first), then every `start`.
- Where Pursuit of Immortality has a better pattern for something, adapt it into this layout.

### 14.3 Registry pattern
- Each registry is a folder of ModuleScripts (or one table for small sets). At boot it is loaded, frozen and validated.
- The API is `get(id)`, `all()` and `where(predicate)`. Nothing outside the registry and config files should hold content data.

### 14.4 Data
- **ProfileStore** (`ServerScriptService.Packages.ProfileStore`) with session locking, through `DataService`.
- `DataConfig` holds the store name, the template, `schemaVersion` and the ordered `migrations`. Data newer than the server's schema is never loaded, and the player is sent to a fresh server.
- Currencies are filled in from the Currencies registry, so adding a currency needs no data change.
- The owner gets a snapshot on load (`DataInit`), then one `DataSet` delta per change. `DataConfig.private` keys never leave the server.
- **Saved:** currencies, inventory, equipped gear, unlocked forms with mastery, Broodlings, pity counters, stats and settings.
- **Studio:** turn on Game Settings > Security > Studio Access to API Services to test real saves. Otherwise ProfileStore runs on its mock store (or set `mockInStudio`).

### 14.5 Movement tech (biggest risk, so prototype it first)
- **Wall and ceiling walking:** `ControllerManager` + `GroundController`, with `UpDirection` driven by raycasts that read the surface normal. The fallback is a custom controller built on `AlignOrientation` and `LinearVelocity`.
- **Silk Line:** a raycast picks the anchor point. Swinging uses a `RopeConstraint` or a spring, zipping uses a velocity pull, and a `Beam` draws the thread.
- The camera must handle ceilings (up-vector aware) without making players motion-sick. Add a settings toggle.

### 14.6 Networking and performance
- Networking follows the Networking rules above. The client predicts cosmetics; the server decides outcomes.
- Turn on `StreamingEnabled` in dungeons. Pool VFX and projectiles, cap enemies per room, and reuse kit meshes.
- Test on a low-end phone at every milestone.

## 15. Monetization (fair, no raw power for Robux)
- **Gamepasses:** second Broodling slot, bigger Stash, auto-sell Commons, VIP cosmetic set.
- **Dev products:** Moonstone packs and cosmetic bundles.
- **Private servers.**
- Paid random items follow the compliance rules in §8.

## 16. Roadmap
| Milestone | Scope | Done when |
|---|---|---|
| **M0 Foundations** | **Core installer delivered:** Net (one remote), Registry, ProfileStore DataService, Platform/Input/Data controllers, Boot. **Still to do:** UI panel framework (template cloning, `UIFit`, gamepad navigation), lobby greybox | You can join, data saves, and a panel opens and closes on PC, console and phone. |
| **M1 Spider feel** | Wall and ceiling walking, Silk Line, jump and leap, camera, Spiderling model and anim set (rig, mesh, Idle and Walk are built in `blender/`, import pending), Bite on a dummy | Crossing a room over its walls and ceiling feels good on PC and phone. |
| **M2 Combat core** | Ability framework, status effects, 2 enemy archetypes, damage numbers, cocoon and revive | 2 players clear a test room. |
| **M3 Dungeon run** | Room generator, Mossy Hollow kit, mini-boss and Ant Queen, loot drops, results screen, lobby↔dungeon travel with the MemoryStore run record | A full run works end to end and the loot banks. **This is the vertical slice.** |
| **M4 Lobby economy** | Inventory and equip, gear and affixes, Merchant, Outfitter, Stash, currencies | You can sell, buy, equip and store. |
| **M5 Evolution and Hatchery** | Molting Shrine and tree UI, 4 paths at T1–T2, Hatchery with odds and pity, Broodlings | You can evolve, switch paths, and hatch and equip a Broodling. |
| **M6 Content and polish** | T3 apexes, The Cellar, more bosses, VFX and audio pass, mobile and performance pass | The launch content set is complete. |
| **M7 Launch prep** | Onboarding, dailies, analytics funnels, economy tuning, monetization | Soft launch. |

## 17. Decisions
- **Rig:** players use a custom Spider rig; human-shaped NPCs use R6.
- **Paths:** collect-and-switch.
- **Summoning:** hatching Egg Sacs into Broodlings.
- **Where things live:** code in Studio; this repo holds docs and Blender files only.
- **Clips:** the asset bridge converts Blender actions.
- **Modes:** PvE dungeons first, PvP arena later.
- **Wipes:** no loot, only a small Amber payout.
- **Runs:** 10–20 min, 1–4 players.
- **Data:** ProfileStore.
- **Networking:** one RemoteEvent.
- **Platforms:** PC, console and mobile.

No open questions right now.
