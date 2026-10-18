# File formats (Starsector 0.98a)

Read this when you write or debug a data file. Facts come from the vanilla files of 0.98a-RC7, the API source, the
installed library mods, and the wiki (marked **(wiki)**; several wiki pages say they were last verified for 0.95 or
older). Never type a CSV header from memory: copy it from vanilla (`ssdata.py header <file>`) or clone a vanilla row
(`ssdata.py clone ...`). `validate_mod.py` checks nearly everything below.

## 1. Mod layout and loading

```
mods/MyMod/
  mod_info.json                    required
  mymod.version                    Version Checker (see 3)
  jars/MyMod.jar                   compiled code, listed in mod_info.json "jars"
  data/...                         same relative paths as starsector-core/data
  graphics/... sounds/...          assets, referenced by path relative to the mod root
  src/ tools/ build.sh             your sources and tooling (not needed at runtime; leave out of releases)
```

* The game merges each data file over vanilla at the same relative path. CSV rows are added; a row with an existing
  id replaces it (community-known, not tested here). JSON objects such as `data/config/settings.json` are merged
  key by key: GraphicsLib, MagicLib and others ship a settings.json with only their own keys. List core files in
  `"replace"` (mod_info.json) to stop them loading (total conversions).
* Spec files (`.ship .skin .variant .wpn .proj .system .faction`) are indexed by the id **inside** the file, not
  the file name. Vanilla has warhound.ship (hullId cerberus), kite_Stock.variant (variantId kite_original_Stock),
  locust_srm.proj (id locust). Matching names is still clearer.
* Variants can sit in subfolders of data/variants (vanilla uses data/variants/<hull>/ and fighters/, drones/, ...).
* Loose `.java` anywhere under `data/` is compiled at startup by the game's embedded Janino compiler (log:
  `ScriptStore`). Vanilla's own hullmods load this way (`data.hullmods.HeavyArmor`). The class name is its path,
  e.g. `data/hullmods/Foo.java` = `data.hullmods.Foo`. Janino supports less of Java than javac and slows startup,
  so ship a jar.
* Paths in data files use `/` and must match the file's case exactly (Linux/macOS are case-sensitive). Files must
  be UTF-8 **without BOM** **(wiki)**. A BOM breaks the first CSV column or the JSON parse.
* The JSON parser is lenient: `#` and `//` comments, trailing commas, unquoted keys and values, `;` as a separator
  and `0.5f` numbers all parse, and anything after the first complete value is ignored. Vanilla uses all of these
  (505 of 1131 vanilla JSON-family files are not strict JSON). Write strict JSON yourself so tools can read it, and test with
  `sslib.loose_json` for the game's behaviour. Wiki: commented-out code inside JSON has quirks, so do not "comment
  out" entries to debug.
* CSVs: the header must contain the vanilla columns. Rows whose first cell starts with `#` are comments. Quote any
  cell containing commas, quotes or newlines (rules.csv text is often multi-line). Excel can re-encode files and
  change number formats **(wiki)**: edit with a text editor or generate them.

## 2. mod_info.json

```json
{
    "id": "my_mod",                     unique across all mods (the launcher hides duplicates)
    "name": "My Mod",
    "author": "You",
    "version": "1.2.0",                 string, or {"major": 1, "minor": 2, "patch": 0}
    "description": "Shown in the launcher.",
    "gameVersion": "0.98a-RC7",
    "jars": ["jars/MyMod.jar"],
    "modPlugin": "mym.MymModPlugin",    class extending BaseModPlugin
    "dependencies": [{"id": "lw_lazylib", "name": "LazyLib"}],   optional "version": {"major": 3}
    "utility": false,                   utility mods can be removed from saves; may load with total conversions
    "totalConversion": false,
    "replace": []                       core files NOT to load (total conversions)
}
```

Installed library ids: `lw_lazylib` (LazyLib), `MagicLib`, `shaderLib` (GraphicsLib), `lunalib`, `lw_console`
(Console Commands). Check `sslib.installed_mods()` for the actual ids. The game version string is in
`com/fs/starfarer/Version.class` inside starfarer_obf.jar (`sslib.game_version`).

## 3. Version Checker (every installed library mod has it)

1. `<anything>.version` in the mod root (lenient JSON):
   ```json
   {"masterVersionFile": "https://raw.githubusercontent.com/<you>/<repo>/main/mymod.version",
    "modName": "My Mod", "modThreadId": 12345, "modVersion": {"major": 1, "minor": 2, "patch": 0},
    "directDownloadURL": "...", "changelogURL": "..."}
   ```
   Required: `masterVersionFile`, `modName`, `modVersion`. `modThreadId` is the forum topic number. Patch may be a
   string ("0a"). LunaLib's own file has `#` comments and trailing commas, which is fine.
2. `data/config/version/version_files.csv` with the exact header `version file` and one row per .version path.
3. Host the master .version file at `masterVersionFile` and keep its `modVersion` equal to mod_info.json's version.
   (`validate_mod.py` and `package_mod.py` compare them.)

## 4. Hulls

**ship_data.csv** (`data/hulls/`): 55 columns, copy the vanilla header. Key columns:
`id`, `name`, `designation`, `tech/manufacturer` (shown in the codex; also used for designTypeColors), `system id`,
`defense id` (shield/phase system), `fleet pts` (fleet generation strength, not DP), `hitpoints`, `armor rating`,
`max flux`, `flux dissipation`, `ordnance points`, `fighter bays` (6 safe; 7 glitches, 8+ breaks **(wiki)**),
`max speed`, `acceleration`, `deceleration`, `max turn rate`, `turn acceleration`, `mass`, `shield type`
(NONE/FRONT/OMNI/PHASE), `shield arc`, `shield upkeep`, `shield efficiency`, `phase cost`, `phase upkeep`, crew,
cargo, fuel, `fuel/ly`, `max burn`, `base value`, `cr %/day`, `CR to deploy`, `peak CR sec`, `CR loss/sec`,
**`supplies/rec` (= deployment points AND recovery cost)**, `supplies/mo`, `hints`, `tags`, `logistics n/a reason`
(any text hides the codex's logistics block), `codex variant id`, `rarity`, `breakProb`, `minPieces`, `maxPieces`,
`travel drive`, `number`. `8/6/5/4%` is unused by the engine **(wiki)**.

* `hints` must be `ShipHullSpecAPI.ShipTypeHints` values (FREIGHTER, TANKER, LINER, TRANSPORT, CIVILIAN, CARRIER,
  COMBAT, NO_AUTO_ESCORT, UNBOARDABLE, STATION, SHIP_WITH_MODULES, MODULE, HIDE_IN_CODEX, UNDER_PARENT, ...).
* `tags`: blueprint packages (`base_bp`, `lowtech_bp`, `midline_bp`, `hightech_bp`, `rare_bp`, or your own `mym_bp`)
  decide which factions know the hull and what blueprints contain it.
* A .ship whose hullId has no row logs `ERROR ... Ship hull spec [x] not found in ship_data.csv` (vanilla itself does
  this for 2 decorative hulls).

**.ship** (`data/hulls/*.ship`): `hullId`, `hullName`, `hullSize` (FIGHTER/FRIGATE/DESTROYER/CRUISER/CAPITAL_SHIP),
`spriteName`, `width`, `height`, `center`, `bounds`, `collisionRadius`, `shieldCenter`, `shieldRadius`, `viewOffset`,
`style` (a hull_styles.json id: LOW_TECH, MIDLINE, HIGH_TECH, ...), `weaponSlots`, `engineSlots`, `builtInMods`,
`builtInWeapons` ({slotId: weaponId}), `builtInWings`, `coversColor`, `moduleAnchor` (modules). Coordinate
conventions and measured defaults: `references/sprites.md` section 3. Write .ship files with `hullgen.py`/`kitbash.py`
(geometry from the art), or clone a vanilla .ship when reusing a vanilla sprite.

**.skin** (`data/hulls/skins/`): `baseHullId`, `skinHullId`, `hullName`, `spriteName`, `descriptionId`,
`descriptionPrefix`, `tech`, `tags`, `baseValueMult`, and changes: `removeWeaponSlots`, `weaponSlotChanges`
({slot: partial slot}), `removeBuiltInWeapons`, `builtInWeapons`, `removeBuiltInMods`, `builtInMods`,
`removeEngineSlots`, `engineSlotChanges`, `ordnancePoints`, `fleetPoints`, `suppliesToRecover`, `suppliesPerMonth`,
`systemId`, `fighterBays`, `builtInWings`, `addHints`/`removeHints`. A skin's skinHullId works as a hull id in
variants and factions. Skins are the cheapest way to add a faction variant of a hull: none of vanilla's 66 skins has
a ship_data.csv row.

**.variant** (`data/variants/**`): `variantId`, `hullId`, `displayName`, `fluxVents`, `fluxCapacitors`
(each max 10/20/30/50 by hull size: `CoreAutofitPlugin.getBaseMax`), `hullMods`, `permaMods`, `sMods`
(`maxPermanentHullmods` is 2 in settings.json; vanilla variants use up to 3), `weaponGroups`
([{`mode`: LINKED|ALTERNATING, `autofire`: bool, `weapons`: {slotId: weaponId}}], one slot per group at most),
`wings`, `goalVariant`, `quality`, `modules` ([{slotId: variantId}] for ships with modules).
OP used = weapon OPs + non-built-in hullmod costs (cost_frigate/dest/cruiser/capital) + wing `op cost` + vents +
capacitors, and must not exceed `ordnance points`. A weapon fits a slot of the same size or one size larger, and of
a compatible type: HYBRID = ballistic or energy, SYNERGY = energy or missile, COMPOSITE = ballistic or missile,
UNIVERSAL = all three.

**default_ship_roles.json** (`data/world/factions/`): `{role: {variantId: weight}}`. Factions only spawn your variants
through these roles (plus knowing the hull), so a variant that is in no role never appears in random fleets
**(wiki)**. Vanilla roles: combatSmall/Medium/Large/Capital, combatSmallForSmallFleet, escortSmall/Medium,
fastAttack, carrierSmall/Medium/Large, phaseSmall/Medium/Large/Capital, freighterSmall/Medium/Large,
combatFreighterSmall/Medium/Large, tankerSmall/Medium/Large, linerSmall/Medium/Large, personnelSmall/Medium/Large,
civilianRandom, utility, tug, crig, and station roles.

## 5. Weapons

**weapon_data.csv** (`data/weapons/`): `name`, `id`, `tier`, `rarity`, `base value`, `range`, `damage/second`
(beams), `damage/shot`, `emp`, `impact`, `turn rate`, `OPs`, `ammo`, `ammo/sec`, `reload size`, `type` (damage type:
KINETIC, HIGH_EXPLOSIVE, FRAGMENTATION, ENERGY, OTHER), `energy/shot`, `energy/second` (beams), `chargeup`,
`chargedown`, `burst size` (beams: seconds of fire), `burst delay` (beams: cooldown between bursts), spread columns,
`beam speed`, `proj speed`, `launch speed`, `flight time`, `proj hitpoints`, `autofireAccBonus`, `extraArcForAI`,
`hints` (WeaponAPI.AIHints: PD, PD_ONLY, STRIKE, ANTI_FTR, DO_NOT_AIM, ...), `tags`, `groupTag`,
`tech/manufacturer`, tooltip columns (`primaryRoleStr`, `speedStr`, ... `noDPSInTooltip`), `number`.

* **Autofit tags:** without one of `kinetic#`, `he#`, `energy#`, `pd#`, `beam#`, `strike#`, `missile#`, `rocket#`,
  `utility#` (number = tier) autofit ignores the weapon, and so does the fleet inflater that equips AI fleets
  **(wiki; validator checks)**. Blueprint tags (`base_bp`, `rare_bp`, ...) and `merc` work as for hulls.
* A row without a .wpn logs `WARN ... Weapon [x] from weapon_data.csv not found in store`. A variant or faction
  naming a missing weapon throws `RuntimeException: Weapon spec [x] not found!`.

**.wpn**: `id`, `specClass` (projectile | beam; missiles are `projectile` weapons whose .proj has
`specClass: missile`), `type` (slot type: BALLISTIC/ENERGY/MISSILE/...), `size`, `turretSprite`, `hardpointSprite`,
optional `turretGunSprite`/`hardpointGunSprite` (recoil, used if visualRecoil > 0), `*UnderSprite`, `*GlowSprite`,
`turretOffsets`/`hardpointOffsets` (x, y pairs from the sprite centre), `turretAngleOffsets`/`hardpointAngleOffsets`
(**one per barrel**; a mismatch crashes with "Index: 1, Size: 1"), `barrelMode` (ALTERNATING|LINKED),
`animationType` (GLOW, MUZZLE_FLASH, SMOKE), `renderHints`, `muzzleFlashSpec`, `smokeSpec`, `projectileSpecId`,
sounds `fireSoundOne`/`fireSoundTwo` (sounds.json ids), beam fields (`fringeColor`, `coreColor`, `width`,
`textureType`, `textureScrollSpeed`, `pixelsPerTexel`, `darkCore`, `beamEffect`), effect classes `everyFrameEffect`,
`onFireEffect` (one instance per weapon), `onHitEffect` (beams). `weapongen.py` prints the sprite and offset fields.

**.proj** (`data/weapons/proj/`): `id`, `specClass` (projectile | missile), `spawnType` (BALLISTIC,
BALLISTIC_AS_BEAM, PLASMA), `collisionClass` (RAY, PROJECTILE_FF, PROJECTILE_FIGHTER, MISSILE_FF, MISSILE_NO_FF,
NONE, ...), `collisionClassByFighter`, size/colour fields (`width`, `length`, `fringeColor`, `coreColor`,
`textureScrollSpeed`, `pixelsPerTexel`, `bulletSprite`, `fadeTime`), `onHitEffect` (class; one shared instance).
Missiles add `missileType` (MISSILE, ROCKET, MIRV, BOMB, ...), `sprite`, `size`, `center`, `collisionRadius`,
`explosionColor`, `explosionRadius`, `engineSpec`, `engineSlots`, `flameoutTime`, `armingTime`, `behaviorSpec`.

## 6. Ship systems, hullmods, wings

**ship_systems.csv** + **.system** (`data/shipsystems/`): the csv holds name, flux/use costs, `max uses`, `regen`,
`charge up`, `active`, `down`, `cooldown`, `toggle`, the flags (noFiring, noShield, isPhaseCloak, ...) and `icon`
(64x64). The .system holds `id`, `type` (STAT_MOD, ENGINE_MOD, DRONE_LAUNCHER, WEAPON, DISPLACER, PHASE_CLOAK, ...),
`aiType` (a built-in AI such as WEAPON_BOOST or MANEUVERING_JETS, or CUSTOM + `aiScript`), `statsScript` (class),
sounds, and visual fields. Description type `SHIP_SYSTEM`.

**hull_mods.csv** (`data/hullmods/`): `name`, `id`, `tier`, `rarity`, `tech/manufacturer`, `tags`, `uiTags`,
`base value`, `unlocked`, `hidden`, `hiddenEverywhere`, `cost_frigate`, `cost_dest`, `cost_cruiser`, `cost_capital`,
`script` (class), `desc` (`%s` placeholders filled by getDescriptionParam(index)), `short`, `sModDesc`, `sprite`
(32x32 icon). A hullmod built into a hull costs 0 OP; s-mods cost 0 OP.

**wing_data.csv** (`data/hulls/`): `id` (by convention `<name>_wing`), `variant` (a variant on a FIGHTER hull),
`tags`, `tier`, `rarity`, `fleet pts`, `op cost`, `formation`, `range`, `attackRunRange`, `attackPositionOffset`,
`num`, `role` (FIGHTER, BOMBER, INTERCEPTOR, SUPPORT), `role desc`, `refit`, `base value`. Wings without autofit
tags never show in the mission refit **(wiki)**.

## 7. Factions

**factions.csv** (`data/world/factions/`, header `faction`): one row per .faction **path**
(`data/world/factions/mym_bureau.faction`). A new faction not listed here does not load.

**.faction**: required in practice (present in all 21 vanilla factions): `id`, `displayName`,
`displayNameWithArticle`, `logo`, `names` ({person_names.csv category: weight}), `portraits` ({"standard_male": [...],
"standard_female": [...]}). Usually also: `color`, `crest`, `displayNameLong(WithArticle)`, `entityNamePrefix`,
`personNamePrefix`, `shipNamePrefix`, `shipNameSources` ({ship_names.json key: weight}), `description`, `music`
({key: sounds.json music id}), `knownShips`/`knownWeapons`/`knownFighters`/`knownHullMods` ({"tags": [...],
"hulls"/"weapons"/"fighters"/"hullMods": [...]}), `priorityShips`/`priorityWeapons`, `factionDoctrine`,
`illegalCommodities`, `shipSellFrequency`/`weaponSellFrequency`/... , `variantOverrides`, `ranks`, `custom`,
`internalComms`. The validator's old "doctrine must sum to 7" rule was wrong: vanilla sindrian_diktat
(composition 5), persean (6) and remnant (quality 9) break it.

* To add your ships to a **vanilla** faction, ship a partial file at the same path
  (`data/world/factions/hegemony.faction` containing only `{"knownShips": {"hulls": ["mym_x"]}}`). It merges and
  needs no factions.csv row.
* Fleet spawning throws `RuntimeException: Weapon with spec id [x] not found` if a faction's known lists name a
  missing id (`DefaultFleetInflater`). The inflater refits AI ships from the faction's known weapons and hullmods,
  so role variants carrying gear the faction does not know will not keep their loadout.

* **Cloning a vanilla .faction** (e.g. `tritachyon`) drags in `internalComms` (a `channels.json` entry with that
  faction's logo and reports), `custom.AICoreValueMult`, `punitiveExpeditionData` and its ranks ("CEO"): pop or
  replace them. `ranks` = {"ranks": {rankId: {"name"}}, "posts": {postId: {"name"}}} with ids from `Ranks`
  (spaceAdmiral, spaceCommander, ..., posts factionLeader, administrator, stationCommander, patrolCommander, ...).
  `fleetTypeNames` keys: trade, tradeLiner, tradeSmuggler, smallTrader, patrolSmall/Medium/Large, inspectionFleet,
  taskForce, foodReliefFleet, mercBountyHunter, mercPrivateer. `voices` = {LOW/MEDIUM/HIGH: {voice: weight}}.
* **ship_names.json** merges across mods: ship your own key (`{"MYM_NAMES": [...]}`) and weight it in
  `shipNameSources`. Diable Avionics, UAF and SotF do the same.
* **Nexerelin** (optional, no dependency needed): `data/config/exerelinFactionConfig/mod_factions.csv` (header
  `faction`, one row per faction id) + `<faction id>.json` with `playableFaction`, `corvusCompatible`,
  `startRelationships` {faction: -1..1} (Nex applies them in a new Nex game), `alignments` (corporate, technocratic,
  militarist, diplomatic, ideological, hierarchical: -1..1), `diplomacyTraits` (ids in
  `Nexerelin/data/config/exerelin/factionTraits.json`: paranoid, predatory, pacifist, helps_allies, rebel,
  irredentist, stalwart, foreverwar, selfrighteous, temperamental, dislikes_ai, hates_ai, likes_ai, envious,
  submissive, neutralist, monopolist, law_and_order, anarchist, lowprofile, devious, monstrous), `startShipsSolo` /
  `CombatSmall` / `CombatLarge` / `TradeSmall` / `TradeLarge` / `CarrierSmall` / `CarrierLarge` / `Super` (lists of
  variant-id lists), `startSpecialItems` ([[[itemId, data]]]), `defenceStations` ([{"ids": [3 station industry
  ids]}]), `industrySeeds`, `bonusSeeds`, vengeance names. Copy a shipped config (Nex's persean.json, DA's).
  Mod-added-mid-save: Nex does not re-apply startRelationships, so set them yourself once behind a memory flag.

## 8. Campaign data

* **descriptions.csv** (`data/strings/`): `id,type,text1..text5,notes`, keyed by **(id, type)**. Types used by vanilla:
  SHIP, WEAPON, SHIP_SYSTEM, FACTION, CUSTOM (entities, planets via setCustomDescriptionId), RESOURCE, PLANET,
  TERRAIN, ACTION_TOOLTIP, GALLERY, ASTEROID. text1 is the main body (the codex/refit text for SHIP and WEAPON);
  vanilla SHIP rows such as hammerhead leave text2-text5 empty.
* **rules.csv** (`data/campaign/`): `id,trigger,conditions,script,text,options,notes`. Details in
  `references/api-notes.md` section 4. Rule ids are global: prefix them.
* **custom_entities.json** (`data/config/`): {id: {defaultName, sprite, spriteWidth/Height, icon, iconWidth/Height,
  layers, tags, defaultRadius, customDescriptionId, interactionImage, showInCampaign, showIconOnMap, pluginClass,
  baseId (inherit), ...}}. Use `baseId` to inherit from a vanilla entity.
* **market_conditions.csv**, **industries.csv**, **submarkets.csv**, **commodities.csv**, **special_items.csv**,
  **abilities.csv**: copy vanilla headers. Plugin/script columns name classes; icon columns name images (sizes in
  sprites.md).
* **ship_names.json**: {source key: [names]}, referenced by a faction's `shipNameSources`.
* **Blueprint packages** (special_items.csv, plugin `MultiBlueprintItemPlugin`): `plugin params` is a comma list of
  tags and an item must carry **all** of them (`!tag` excludes). One package per kind (hulls / weapons / wings) needs
  a per-kind tag on the rows (`mym_bp_hulls` ...) besides the faction's `mym_bp`. Add `no_drop` to keep a package
  out of salvage drops.
* **A mod currency as a commodity**: tags `nonecon, no_loss_from_combat` keep markets from stocking it, but **any
  open market still buys it** (`BaseSubmarketPlugin.isIllegalOnSubmarket` only checks `market.isIllegal`). There is
  no data-only way to forbid the sale: give it a tiny base price (and say so in its description), or make it illegal
  per faction. Clone `gamma_core`'s row; set `demand class` = its own id. Console: `additem <commodity> 100`;
  special items: `addspecial <item id>`.
* **A hullmod that never drops as a modspec** (taught by a quest or shop instead): tags `no_drop, no_drop_salvage`
  and an empty `rarity`, like vanilla `neural_interface`; teach it with `playerFaction.addKnownHullMod(id)`.
* **MagicLib bounties**: `data/config/modFiles/magicBounty_data.json`, {bountyId: {...}}; every key is documented in
  `MagicLib/data/config/modFiles/magicBounty_data_example.json` (MagicLib ignores unknown keys silently; the
  validator now flags them with a "did you mean"). `job_item_reward` accepts commodity ids too (MagicLib checks
  `getCommoditySpec` first), so a mod currency can be a bounty reward. `fleet_faction: "ML_bounty"` (MagicLib's
  utility faction, neutral to everyone but the player) + `fleet_composition_faction` makes "rogue" fleets whose
  defeat costs no reputation with the faction they came from. Gate a bounty on quest progress with
  `trigger_memKeys_all: {"$myFlag": true}` (sector memory). The validator checks variants, factions, item rewards and
  portrait paths.

## 9. Config

* **settings.json** (`data/config/`, merged): `"plugins": {"anyKey": "class"}` registers every-frame combat plugins
  and other plugins. Vanilla registers its own combat plugins there (genericCombatPlugin, ...), and so do MagicLib,
  GraphicsLib, LunaLib, Console Commands and SpeedUp. `"ruleCommandPackages": ["mym.rulecmd"]` makes every class in
  that package a rules.csv command (vanilla's five packages are always active). `"graphics": {"category": {"key":
  "graphics/...png"}}` names sprites for `Global.getSettings().getSprite(category, key)` / `getSpriteName`.
  `"designTypeColors": {"Manufacturer": [r,g,b,a]}` colours a tech/manufacturer name in the UI.
* **sounds.json** (`data/config/`): {sound id: {"group": ..., "sounds": [{"file": "sounds/....ogg", ...}]}} plus a
  "music" block. Use .ogg (macOS cannot play .wav **(wiki)**).
* **hull_styles.json** / **engine_styles.json**: new styles need every key vanilla's have (hull styles hold ~30 keys:
  shield colours, flux vent textures, sound sets, slot cover sprites; engine styles hold `engineColor`, contrail
  fields and `type`). Clone a vanilla entry, then change values.
* **LunaSettings.csv** (`data/config/`, needs lunalib): header
  `fieldID,fieldName,fieldType,defaultValue,secondaryValue,fieldDescription,minValue,maxValue,tab`; fieldType one of
  Header, Text, Int, Double, String, Boolean, Enum, Keycode, Color, Radio (from LunaLib's loader source). Read
  with `lunalib.lunaSettings.LunaSettings.getBoolean/getInt/getDouble/getFloat/getString(modId, fieldId)`, which
  return boxed values that can be null.

## 10. GraphicsLib data (optional integration)

* Light data `data/lights/<mod>_light_data.csv`, header copied from `GraphicsLib/data/lights/core_light_data.csv`:
  `id,type,size,intensity,fadeout,color,offset,hit size,hit intensity,hit fadeout,hit color,flash size,flash intensity,flash fadeout,flash color,flash offset,chance,fighter dim`
  (type projectile = .proj id, beam = weapon id). Load with `org.dark.shaders.light.LightData.readLightDataCSV(path)`.
* Texture maps `data/lights/<mod>_texture_data.csv`: `id,type,frame,magnitude,map,path`. Load with
  `org.dark.shaders.util.TextureData.readTextureDataCSV(path)`. Map conventions: `references/sprites.md` section 6.
* Call both from onApplicationLoad, only when `isModEnabled("shaderLib")`, from a separate class so the mod still
  loads without GraphicsLib (compile with `build_mod.py --with-mod shaderLib`).
