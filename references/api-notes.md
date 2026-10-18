# API notes (Starsector 0.98a, Java 17)

Verified by reading the API source shipped with the game (`starsector-core/starfarer.api.zip`, which includes
`com.fs.starfarer.api.impl.*`, vanilla's own campaign/combat/rules code) or by compiling the skill's templates
against `starfarer.api.jar`. Items marked **(wiki)** come from starsector.wiki.gg; **unverified** means nobody ran it.

**Rule zero: never write an API call from memory.** `scripts/api_lookup.py` answers in one command:
`class X` (members + supertypes), `method X m` (full source), `const MemFlags NO_JUMP` (value, doc, vanilla use
count), `uses SYMBOL` (every vanilla use in code and data), `grep`, `rulecmd [Name]`, `javap fqcn` (library jars).
If behaviour matters, read the impl (`method`) and copy what vanilla does.

## 1. Toolchain

* The game runs the bundled **Java 17** (jre/release: Zulu 17.0.10; the API classes are major version 61).
  Compile with `javac --release 17` (`build_mod.py` reads the bundled JRE and sets this). The wiki's "compile for
  JDK 7" advice is outdated.
* Compile against the core jars (starfarer.api.jar, json, log4j, lwjgl, lwjgl_util, xstream, ...) plus each
  dependency's jars. Do not compile against the obfuscated jars.
* The game JVM runs with `-noverify` (vmparams), so classes are resolved lazily. That is what makes "optional
  integration in a separate class guarded by isModEnabled" work (standard practice; not exercised here).
* Restricted APIs **(wiki)**: the script classloader rejects file I/O (`java.io.File`, streams) and reflection. Use
  `Global.getSettings()`: `loadText/loadJSON/loadCSV(path[, modId])`, `getMergedSpreadsheetDataForMod(idCol, path,
  masterMod)`, `getMergedJSONForMod(path, masterMod)`, and for files outside the mod
  `readTextFileFromCommon/writeTextFileToCommon/fileExistsInCommon/deleteTextFileFromCommon`.
* Logging: `private static final Logger log = Global.getLogger(MyClass.class);` (log4j). Keep loggers static: the
  wiki lists non-static loggers among classloader errors.

## 2. ModPlugin lifecycle (`BaseModPlugin`)

Hooks: `onApplicationLoad()` (once at startup, may throw), `onNewGame()`, `onNewGameAfterProcGen()`,
`onNewGameAfterEconomyLoad()`, `onEnabled(boolean wasEnabledBefore)`, `onNewGameAfterTimePass()`,
`onGameLoad(boolean newGame)`, `beforeGameSave()`, `afterGameSave()`, `onGameSaveFailed()`,
`configureXStream(XStream x)`, `pickShipAI/pickWeaponAutofireAI/pickDroneAI/pickMissileAI(...)`,
`onDevModeF8Reload()`, codex hooks (`onAboutToStartGeneratingCodex`, `onAboutToLinkCodexEntries`,
`onCodexDataGenerated`).

New-campaign order **(wiki)**: onNewGame, onNewGameAfterProcGen, onNewGameAfterEconomyLoad, onEnabled,
onNewGameAfterTimePass, onGameLoad. onGameLoad also runs on every load.

* **Generate world content in onNewGame** (before the economy loads), and **again from onGameLoad guarded by a
  sector memory flag** so saves that predate the mod get it once. Every generator must be idempotent: check
  `sector.getStarSystem(id) != null` and the flag. (Templates: the scaffold's `<Prefix>ModPlugin.java` from
  `templates/mod/src/`, plus `templates/java/WorldGen.java`.)
* **Save compatibility.** Everything reachable from the sector (scripts added with `addScript`, intel, listeners
  added as permanent, objects in memory/persistent data) is serialized by XStream. Removing or renaming such a class
  later breaks saves (`CannotResolveClassException`, seen in this install's log after a mod was removed). Register
  short aliases in `configureXStream(x)` with `x.alias("Mym_Intel", MymIntel.class)`, and never rename or move a
  saved class after release. Add per-session things with `addTransientScript` / transient listeners and re-add them
  in onGameLoad. Use `transient` fields for caches and UI references.
* Shared state: `Global.getSector().getPersistentData()` (saved), memory (`getMemoryWithoutUpdate()`), or
  `CombatEngineAPI.getCustomData()` (per battle). Never static fields holding game objects: they survive loading
  another save and leak it **(wiki: "the worst memory leak" was a static that was never cleared)**.

## 3. Combat code

* **Every-frame combat plugins**: `extends BaseEveryFrameCombatPlugin`, registered in `data/config/settings.json`
  `"plugins": {"anyKey": "fqcn"}`. Vanilla registers its own combat plugins there (genericCombatPlugin,
  coordinatedManeuversPlugin, ...), and so do MagicLib, GraphicsLib, LunaLib, Console Commands and SpeedUp. The
  engine creates one instance per battle and calls `init(engine)`, then `advance(amount, events)` each frame. Return
  early when `engine.isPaused()`. Frame-rate-independent maths uses `amount` **(wiki)**.
* **Performance**: no allocations in per-frame code (preallocate lists and `clear()` them; avoid lambdas, iterators
  and String building), do periodic work through `IntervalUtil(min, max)` (`advance(amount)` then
  `intervalElapsed()`), and cache lookups. Last session's reviewer found per-frame list/map allocations in a combat
  plugin; the template shows the allocation-free pattern.
* **Hullmods** (`BaseHullMod`): `applyEffectsBeforeShipCreation(HullSize, MutableShipStatsAPI, id)` is the only
  place where stat changes reach the campaign layer and the codex/refit stat cards;
  `applyEffectsAfterShipCreation(ShipAPI, id)` for weapons/wings/listeners; `advanceInCombat(ShipAPI, amount)` every
  frame; `advanceInCampaign(FleetMemberAPI, amount)`; `getDescriptionParam(index, HullSize)` fills `%s` in the csv
  `desc`; `isApplicableToShip` / `getUnapplicableReason`; `isSMod`, `isBuiltIn`. Changing hullmods during creation
  restarts creation; adding a random hullmod each call can loop forever **(wiki)**.
* **Stat modifiers**: `stat.modifyPercent(id, v)` bonuses with the same stat add together, `modifyMult` multiply,
  `modifyFlat` adds. Result = (base + base x percent/100 + flat) x mult, floored at zero **(wiki)**. Always
  `unmodify(id)` with the same id.
* **Ship systems**: `.system` `statsScript` extends `BaseShipSystemScript`: `apply(stats, id, state, effectLevel)`
  runs every frame while not idle; `unapply(stats, id)` once at the end; `getStatusData(index, state, level)` for the
  HUD. States IDLE, IN (level 0 to 1), ACTIVE (1), OUT (1 to 0), COOLDOWN **(wiki)**. Custom AI: `aiType: "CUSTOM"`
  and `aiScript` implementing `ShipSystemAIScript` (`init(ship, system, flags, engine)`,
  `advance(amount, missileDangerDir, collisionDangerDir, target)`; call `ship.useSystem()`).
* **Weapon/projectile effects**: `.wpn` `everyFrameEffect` (`EveryFrameWeaponEffectPlugin.advance(amount, engine,
  weapon)`; one instance per weapon) and `onFireEffect` (`OnFireEffectPlugin.onFire(proj, weapon, engine)`);
  `.proj` `onHitEffect` (`OnHitEffectPlugin.onHit(proj, target, point, shieldHit, damageResult, engine)`; keep no
  per-shot state in fields). `engine.spawnEmpArc(...)` and `addHitParticle(...)` for effects.
* One in-game day = 10 seconds **(wiki)**. Ship explosion radius = collision radius + 200 **(wiki)**.

## 4. rules.csv and dialogs

Columns `id,trigger,conditions,script,text,options,notes`. Every rule id is global: prefix yours.

* **FireAll** (verified in `rulecmd/FireAll.java`): first gives `FireAllIntercept` rules a chance; then collects
  **all** rules matching the trigger, gathers their options (and option-adding commands), sorts them by order,
  **clears the option panel only if there are options**, adds them, and then applies every matching rule's text
  and script. **FireBest** applies only the single best-scoring match (`getBestMatching`), clearing and adding
  options if it has any. Consequence: your options for a trigger appear alongside vanilla's unless your rule
  outscores or blocks them, and an empty-options rule does not clear the panel.
* Triggers by vanilla use: `DialogOptionSelected` (6034 rules; condition `$option == myOptionId`),
  `PopulateOptions` (333; adds market/entity menu options; return to a market's main menu with
  `FireAll PopulateOptions`), `PickGreeting` (199), `OpenCommLink` (183; hailing/being hailed),
  `OpenInteractionDialog` (121), `BeginFleetEncounter` (61), `MarketPostDock`, `MarketPostOpen`.
* Options: one per line, `id:text` or `order:id:text` (order is a number, lower first). Each option id needs a
  `DialogOptionSelected` rule with `$option == id`, or the button does nothing. `validate_mod.py` checks this,
  including options added from Java rule commands.
* Conditions and script lines start with `$variable` comparisons/assignments or a command (a class in a
  `ruleCommandPackages` package; `api_lookup.py rulecmd` lists the 231 vanilla ones, `rulecmd Name` prints a
  command's documented syntax, e.g. `AddRemoveCommodity <commodity id> <quantity> <withText>`). Prefix a condition
  command with `!` to negate it. Append `score:N` to a condition line to raise the rule's score for FireBest
  (vanilla: `$customType == abyssal_light score:1000`; 802 vanilla condition lines use it).
* Memory scopes (`MemKeys`): `$foo` = local (the entity/person being talked to), `$global.foo`, `$player.foo`,
  `$market.foo`, `$faction.foo`, `$entity.foo`, `$sourceMarket.foo`, `$personFaction.foo`, `$mission.foo`.
  `$foo = value N` sets with an N-day expiry (`MemoryAPI.set(key, value, expire)`). Vanilla writes `= true 0` about
  800 times for dialog-scoped flags; what 0 means exactly is not documented (**unverified**: it behaves as "until
  the memory next advances").
* Custom commands: `extends BaseCommandPlugin`, `execute(ruleId, dialog, List<Misc.Token> params,
  Map<String, MemoryAPI> memoryMap)`, and list the package in settings.json `ruleCommandPackages`. Read params with
  `params.get(i).getString/getFloat/getBoolean(memoryMap)` (these resolve `$variables`).
* **Competing with vanilla**: before adding an `OpenCommLink` or `OpenInteractionDialog` flow, list vanilla's
  rules on that trigger (`api_lookup.py data ",OpenCommLink," --files rules.csv`) and check their conditions and
  scores. Last session's boss could not talk to the player until `$ignorePlayerCommRequests`
  (`MemFlags.MEMORY_KEY_IGNORE_PLAYER_COMMS`) was unset, because vanilla's greetingNoComms rule won.
* **Hassle framework** (reuse instead of writing pursuit code): give a fleet `MemFlags.WILL_HASSLE_PLAYER` (true)
  and `MemFlags.HASSLE_TYPE` ("myType"). Vanilla's `HasslePlayerScript` periodically picks such a fleet and makes it
  pursue and hail the player (setting `MEMORY_KEY_PURSUE_PLAYER`, `FLEET_BUSY` and `FLEET_SPECIAL_ACTION` with reason
  "hassle"), and your rules then react to `$hassleType == myType` on OpenCommLink. Do not add extra pursuit flags.
* **Faction greetings** (OpenCommLink, copy vanilla `greetingTT*`): conditions `$faction.id == x` plus one of
  `$faction.friendlyToPlayer` / `$faction.neutralToPlayer` / `$entity.isHostile` + `$entity.relativeStrength < 0` or
  `>= 0`; non-hostile scripts `$menuState = fleetConvMain 0` + `FireAll PopulateOptions`, hostile ones
  `$entity.ignorePlayerCommRequests = true 1` and option `cutCommLink:Cut the comm link`. Texts use `OR` lines and
  `$personRank`, `$heOrShe`, `$himOrHer`. A variant with one more condition (e.g. `$player.myFlag`, the player
  fleet's memory) outscores the plain one.
* **A market-menu entry** (e.g. a shop): PopulateOptions rule with `$hasMarket`, `$menuState == main`,
  `$market.id == x`, `$faction.id == y`, `$tradeMode != NONE`, `!$faction.isHostile`; option `6:myOpen:Text`
  (vanilla bar = 5, trade = 10).
* **A dialog shop / sub-menu in Java** without one rule per button: copy vanilla `PaginatedOptions` — a
  `BaseCommandPlugin` that also `implements InteractionDialogPlugin`, saves `dialog.getPlugin()`, calls
  `dialog.setPlugin(this)` and handles `optionSelected` itself. Give options **object** data (enums, small
  classes), not strings: no rules involved, and the validator's dead-option check does not apply. Leave with
  `dialog.setPlugin(originalPlugin); FireAll.fire(null, dialog, memoryMap, "PopulateOptions")`. Resonance Lattice's
  `rsl.rulecmd.RslWorkshop` is a full example (buy with confirmation, turn-ins, tooltips on disabled options).

## 5. Campaign

* **World generation** (`templates/java/WorldGen.java`, the recipe from a finished mod): `sector.createStarSystem(id)`,
  set the location (find free hyperspace, keep 2600+ units from other systems), `initStar`, `addPlanet`,
  `addCustomEntity(id, name, type, faction)`, orbits, `autogenerateHyperspaceJumpPoints(true, true)`, clear
  hyperspace storms with `NebulaEditor`, then markets.
* **Where the core is**: vanilla places its systems from `data/campaign/starmap.json`; they span about x -19100..11000,
  y -14500..3200. A faction home "on the fringe" goes outside that box (Resonance Lattice: (14500, -13000)), then the
  free-spot search keeps 2600+ from every system.
* **Pulsar (neutron star) by hand**, as `StarSystemGenerator.setPulsarIfNeutron`: `initStar(id,
  StarTypes.NEUTRON_STAR, r, corona)`, remove the default corona (`Misc.getCoronaFor(star).getEntity()`),
  `addCorona(star, 300, 3, 0, 3)`, then `addTerrain(Terrain.PULSAR_BEAM, new StarCoronaTerrainPlugin.CoronaParams(
  r + band, (r + band) / 2, star, wind, flare, crLoss))` with `band = max(r * coronaMult, coronaMin)` from
  `(StarGenDataSpec) getSpec(StarGenDataSpec.class, "star_neutron", true)`; orbit it on the star (0, 0, 100).
* **A custom defence station (incl. a modular one)** needs no Java beyond an optional subclass: an industries.csv row
  cloned from `starfortress_high` with `plugin` = `OrbitalStation` (or a subclass), tags `station, starfortress,
  unraidable, structure` (the tag sets the size/defence tier) and `data` `{radius, variant: <station variant>,
  fleetName}`. The station fleet spawns in `advance()`, on the first connected entity tagged `station`; to give it a
  name and the station sprite, pre-create `addCustomEntity(id, "Name", Entities.STATION_BUILT_FROM_INDUSTRY,
  faction)`, `addTag(Tags.USE_STATION_VISUAL)`, add it to `market.getConnectedEntities()` and `setMarket(market)`.
  Hide it from the player's build menu with a subclass: `isAvailableToBuild()` false, `showWhenUnavailable()` false.
  Alias the subclass in configureXStream (industries are saved).
* **Nexerelin random sector**: skip your hand-made system when `SectorManager.getManager().isCorvusMode()` is false
  (Tahlan, DA, UAF, LoA do this). In onNewGame the manager can still be null if your plugin runs before Nex's: fall
  back to `ExerelinSetupData.getInstance().corvusMode`. Call Nex **directly** (add `"nexerelin"` to validate_config
  `optional_mods` so the build compiles against ExerelinCore.jar) from a nested class reached only after
  `isModEnabled("nexerelin")`; no reflection (the script classloader restricts it; the validator warns).
* **Markets**: `Global.getFactory().createMarket(id, name, size)`, set faction and primary entity, conditions
  (`Conditions.POPULATION_4`), industries (`Industries.POPULATION`, `SPACEPORT`, `BATTLESTATION`, ...), submarkets
  (`Submarkets.SUBMARKET_OPEN`, `GENERIC_MILITARY`, `SUBMARKET_STORAGE`), **`setSurveyLevel(SurveyLevel.FULL)`**
  (missed last time), `entity.setMarket(market)`, then `Global.getSector().getEconomy().addMarket(market, true)`.
* **Quest-critical entities**: `Misc.makeStoryCritical(market, reason)` (sets `$story_critical` with a reason, so
  saturation bombardment cannot destroy it) and `market.getMemoryWithoutUpdate().set(DecivTracker.NO_DECIV_KEY,
  true)`. Release both when the quest ends (`Misc.makeNonStoryCritical`, `unset`). For every quest-critical entity
  write the lifecycle table: destroyed, captured, decivilized, faction turns hostile, save/load, mod added
  mid-game.
* **People**: `Global.getFactory().createPerson()`, `setId`, faction, `FullName`, portrait (settings.json graphics
  "characters" key), rank/post (`Ranks`), `sector.getImportantPeople().addPerson(p)`, market `setAdmin`,
  `getCommDirectory().addPerson(p)`, `market.addPerson(p)`. Make it idempotent (look the person up first).
* **Fleets**: `FleetFactoryV3.createFleet(new FleetParamsV3(...))` can return null or an empty fleet: check it.
  Then `location.addEntity(fleet)`, `setLocation`, assignments (`FleetAssignment.PATROL_SYSTEM`, `ORBIT_PASSIVE`,
  `GO_TO_LOCATION_AND_DESPAWN`, `INTERCEPT`, `HOLD`, ...). End with a despawn assignment.
* **MemFlags are not decoration.** Before setting one, run `api_lookup.py const MemFlags <NAME>` and
  `uses <NAME>`, and copy a vanilla use. Mistakes from last session: `MEMORY_KEY_NO_JUMP` (`$cfai_noJump`) stranded
  a boss fleet in the player's system; `FLEET_IGNORES_OTHER_FLEETS` (`$cfai_ignoreOtherFleets`) would also have it
  ignore the player, so it never hailed. Set flags with `Misc.setFlagWithReason(mem, flag, reason, value, days)` so
  they can be cleared per reason, and give every flag a removal point. `Misc.makeHostile(fleet)` sets
  `MEMORY_KEY_MAKE_HOSTILE`.
* **Set-piece battles**: give the fleet a `FleetInteractionDialogPluginImpl.FIDConfigGen` under
  `MemFlags.FLEET_INTERACTION_DIALOG_CONFIG_OVERRIDE_GEN`
  (the constant's value is the misspelt `"$fidConifgGen"`, so always use the constant) that returns an `FIDConfig`
  with `pullInStations = false`, `pullInAllies = false`, `pullInEnemies = false` when nearby stations or fleets must
  not join. Also keep the fight 2500+ units from stations. Other fields: `leaveAlwaysAvailable`, `withSalvage`,
  `lootCredits`, `dismissOnLeave`, `showTransponderStatus`, `delegate`.
* **Recovery**: `variant.addTag(Tags.VARIANT_ALWAYS_RECOVERABLE)` skips the random "not recoverable" roll for an
  enemy ship (`FleetEncounterContext`). Clone a stock variant before tagging it, or every fleet using that variant
  is affected, and remove the tag afterwards. Recovered ships get new captains (AI-core captains have their own
  handling).
* **Fleet geometry**: park fleets at planets or stations, never at the star: the star's corona damages them.
* **Intel** (`BaseIntelPlugin`, template `Intel.java`): `getName()`, `getIcon()` (settings.json graphics "intel"
  key, 40x40), `getIntelTags(map)` (`Tags.INTEL_STORY`, faction id, ...), `addBulletPoints(...)`,
  `createSmallDescription(info, width, height)`, `getMapLocation(map)`. Add with
  `Global.getSector().getIntelManager().addIntel(intel)`; find again with `getFirstIntel(MyIntel.class)`;
  `sendUpdateIfPlayerHasIntel(param, onlyIfImportant)` for updates; `endImmediately()` to finish.
* **Campaign scripts** (`EveryFrameScript`): `advance(amount)`, `isDone()`, `runWhilePaused()`. Convert time with
  `Global.getSector().getClock().convertToDays(amount)`. Re-check state when an effect fires, not only when it was
  scheduled: last session, a hassle already under way still fired after the player had been certified.
* **Mod checks**: `Global.getSettings().getModManager().isModEnabled("id")`.
* **Extra loot after a won battle**: a `BaseCampaignEventListener(false)` added with
  `sector.addTransientListener(...)` in onGameLoad (transient: re-add on every load). `reportEncounterLootGenerated(
  plugin, loot)` runs right before the loot screen and `loot` is mutable. Enemy losses: for each fleet in
  `plugin.getBattle().getNonPlayerSideSnapshot()`, `plugin.getDataFor(fleet).getOwnCasualties()` with status
  `DISABLED`/`DESTROYED`. `reportEconomyMonthEnd()` in the same listener gives a monthly hook.
* **A colony item with a custom effect**: special_items.csv row cloned from `fullerene_spool`
  (`GenericSpecialItemPlugin`); its `plugin params` column is the comma list of industry ids that accept it
  (`BaseIndustry.wantsToUseSpecialItem`). The effect is a `BaseInstallableItemEffect` (`apply/unapply(Industry)`,
  `addItemDescriptionImpl`) put into the static `ItemEffectsRepo.ITEM_EFFECTS` in onApplicationLoad (nothing is
  saved). Waystation takes no vanilla item, so an item there competes with nothing.
* **A repeatable "hunt this fleet" job** (vanilla `PersonBountyIntel` rule): spawn with `FleetFactoryV3`, keep the
  commander, `fleet.addEventListener(intel)`; in `reportBattleOccurred` succeed when
  `battle.isPlayerInvolved() && battle.isInvolved(fleet) && !battle.onPlayerSide(fleet)` and the flagship's captain
  is no longer the commander; reward with `adjustPlayerReputation(new RepActionEnvelope(PERSON_BOUNTY_REWARD, ...))`.
  Remove the listener in `notifyEnded()`; alias the intel class.
* **A multi-beat questline** (Resonance Lattice `rsl.campaign.LacrimosaIntel`, statically verified only): keep the
  whole state machine in ONE saved intel item (stage enum + entity/fleet references + timers in `advanceImpl`), and
  mirror only the facts other content needs afterwards (path chosen, upgraded, ...) into global memory so the intel
  can end. The intel manager advances intel by itself (vanilla `SystemBountyIntel`/`PersonBountyIntel` never
  `addScript` themselves and still expire), so do not also add it as a sector script. The intel implements
  `FleetEventListener` and is added to every quest fleet (`fleet.addEventListener(intel)`): a boss that despawns
  undefeated is respawned, a hunter that is lost lets the quest continue; remove the listeners in `notifyEnded`. **Never** `removeEventListener` or `despawn()` inside `reportBattleOccurred`/`reportFleetDespawnedToListener` (also not through a helper): the engine is iterating that list, `ConcurrentModificationException` = Fatal: null after the battle (seen in game). Queue the fleet and handle it in `advanceImpl`.
  Add a console hook (`runcode my.Quest.debug("stage")`) that plays the beats forward without fights.
* **Quest dialogs without hundreds of rules**: one `BaseCommandPlugin` + `InteractionDialogPlugin` (the
  PaginatedOptions takeover, section 4) with a scene argument; rules.csv keeps only entry points. The same command in
  a rule's *conditions* (`MyQuest can council`) acts as a predicate: `execute` returns the answer, so keep that branch
  free of side effects. For a dialog that opens by itself (a rival hails you), give the class a constructor that
  takes the scene and call `Global.getSector().getCampaignUI().showInteractionDialog(new MyDialog("offer"),
  playerFleet)` from the intel's advance when `!ui.isShowingDialog() && !ui.isShowingMenu()` and the player is not in
  a hyperspace transition; `init(dialog)` runs, so start the scene there, and return a non-null map from
  `getMemoryMap()`. Leave with `dialog.dismiss()` (entities, hails) or restore the plugin + `FireAll PopulateOptions`
  (markets; `saveCurrentVisual()` / `restoreSavedVisual()` around person portraits).
* **Quest sites**: custom entities in hyperspace are `getHyperspace().addCustomEntity(null, name, type, faction)` +
  `setFixedLocation(x, y)` + `setDiscoverable(false)` + `Misc.makeImportant(e, reason)` (quest marker); in a system,
  `setCircularOrbitPointingDown` around the outermost planet (not the star). Their dialog: rule on
  `OpenInteractionDialog` with `$customType == my_type score:1000` and script `ShowDefaultVisual` + your command. A
  custom_entities.json entry may use any vanilla sprite or one of your ship sprites (`spriteWidth/Height` scale it).
* **Abyssal hyperspace**: `Misc.getAbyssalDepth(loc)` is > 0 in the Orion-Perseus Abyss (lower-left corner,
  `HyperspaceAbyssPluginImpl.getAbyssalDepth`: sqrt((x+w/2)/100000) + sqrt((y+h/2)/50000) < 0.95, w/h = settings
  `sectorWidth`/`sectorHeight` 164000/104000) and outside the map (distance/2000). AI fleets flee deeper than
  `DEPTH_THRESHOLD_FOR_FLEETS_FLEEING` = 0.5, so park a quest fleet at depth 0.3-0.45 (sample a grid, take the point
  nearest the quest's previous site).
* **Boss fleets** (vanilla Ziggurat `TTBlackSite.addFleet` is the model): `FleetFactoryV3.createEmptyFleet(faction,
  type, null)`, `addFleetMember(variantId)` per ship, then `member.setVariant(variant.clone(), false, false)` +
  `setSource(VariantSource.REFIT)` before changing anything (else every fleet using the stock variant changes);
  S-mods with `variant.addPermaMod(id, true)` (as `ShipRecoverySpecial`: skip hidden, D-mod and `no_build_in`
  hullmods); officers beyond the normal cap with `OfficerManagerEvent.createOfficer(faction, 7, SkillPickPreference.ANY,
  false, fleet, true /*allowAnyLevel*/, true, 7 /*elite skills: all*/, random)`; commander fleet skills with
  `person.getStats().setSkillLevel(Skills.X, 1)`; flags `MAKE_HOSTILE`, `NO_REP_IMPACT`, `LOW_REP_IMPACT`,
  `NO_SHIP_RECOVERY`, plus `MAKE_ALWAYS_PURSUE`/`PURSUE_PLAYER` and `FleetAssignment.INTERCEPT, playerFleet, 1000f`
  for a hunter (vanilla `DeliveryFailureConsequences` spawns hunters in hyperspace 500 units from the player). A
  hunter left in another location for days can be moved: `removeEntity` / `addEntity` near the player.
* **Swapping a fleet member's hull** (Unsung -> Virtuoso, different built-in weapons/hullmods/deco slots): vanilla
  only swaps between a hull and its D-hull (`variant.setHullSpecAPI`, DModManager/FieldRepairsScript). For a different
  hull, build `Global.getSettings().createEmptyVariant(uniqueId, newSpec)` (it carries the new hull's built-ins),
  copy fitted weapons into non-built-in slots, `getNonBuiltInHullmods`, `getSMods` (addMod + addPermaMod(id, true)),
  vents/capacitors and tags, `autoGenerateWeaponGroups()`, then `member.setVariant(v, false, true)` on the SAME
  member: name, captain, id and flagship status stay (**unverified in game**). `Tags.VARIANT_ALWAYS_RECOVERABLE` on a
  unique quest ship's variant.
* **Quest items**: special_items.csv row cloned from `planetkiller` (`BaseSpecialItemPlugin`) with tags
  `mission_item, no_drop`. Never let a quest step require holding the item if the stage already proves it was won:
  a jettisoned item would softlock the quest.
* **Allied escorts for a quest beat**: there is no vanilla "allied fleet follows the player" pattern
  (`ORBIT_PASSIVE, playerFleet` has no uses). Adding the ships (with officers, `fleetData.addOfficer`) to the
  player's fleet, tagged on the variant, and removing ships and officers when the beat ends is the reliable route.

* **Exploration secrets** (Resonance Lattice `rsl.world.SecretsGen`, statically verified): place them from
  `onNewGameAfterProcGen` (procgen systems exist then; `onNewGame` is too early) and once more from `onGameLoad` behind
  a sector flag for old saves. Pick "wild" systems: no markets (`Misc.getMarketsInLocation(s).isEmpty()`), not
  `THEME_HIDDEN`/`THEME_CORE`, abyssal depth 0; orbit a planet, never the star. A discoverable custom entity needs
  `"discoverable": true, "discoveryXP", "detectionRange"` in custom_entities.json plus `setDiscoverable(true)`.
  Recoverable derelict ships: vanilla `TTBlackSite.addDerelict` (`DerelictShipData` + `BaseThemeGenerator
  .addSalvageEntity(system, Entities.WRECK, ...)` + `ShipRecoverySpecialCreator` via `Misc.setSalvageSpecial`). To
  put a mod commodity into salvage, add a row to `data/campaign/procgen/drop_groups.csv` (`commodity,group,freq`) and
  call `entity.addDropValue(group, creditValue)` (quantity = value / base price; **unverified** for `nonecon`
  commodities). A derelict/automated station fleet: copy `RemnantThemeGenerator.addBattlestations`
  (`FleetTypes.BATTLESTATION`, `setStationMode(true)`, `setAI(null)`, `setCircularOrbitWithSpin`, transponder on,
  `MEMORY_KEY_NO_JUMP`, `MAKE_ALLOW_DISENGAGE`, an AI-core commander from `Misc.getAICoreOfficerPlugin(id)
  .createPerson(...)`); it works with a modular station variant. Lazily create a hidden system (e.g. when the last
  clue is found) with `createStarSystem` + the free-spot search + `autogenerateHyperspaceJumpPoints`.
* **A unique officer skill**: a `skill_data.csv` row (tier 0, `combat officer` TRUE, tag `npc_only` so no one can
  pick it; vanilla `omega_ecm`/`hypercognition` are npc_only) + `<id>.skill` JSON (`scope` CUSTOM + `scopeStr`,
  `effectGroups` -> `{"type":"SHIP","script":"pkg.Class$Level1"}`) + a `ShipSkillEffect` class. Give it with
  `person.getStats().setSkillLevel(id, 1)`. A SHIP effect only reaches the officer's own ship, and fleet-type effects
  only apply for the fleet commander, so a battle-wide officer aura must be done in a combat plugin (scan for a
  captain with `getStats().getSkillLevel(id) > 0`, apply/unapply mods on every allied ship); the skill class then
  only supplies the description lines. Skill icons are 64x64. An officer above the normal cap:
  `OfficerManagerEvent.createOfficer(playerFaction, 7, ANY, false, playerFleet, true, true, 7, random)`, then
  `setId`, name, portrait, personality, and `playerFleet.getFleetData().addOfficer(p)`.

### Set-piece encounters: duels, "one ship each", optional mega-fights (Resonance Lattice Stage 7, unverified in game)

* **Your own dialog first, then vanilla's fleet battle**: a transient `BaseCampaignPlugin` registered every load
  (`sector.registerPlugin`, `isTransient() = true`) returns `new PluginPick<>(myPlugin, PickPriority.MOD_SPECIFIC)` from
  `pickInteractionDialogPlugin(target)` when the fleet's memory carries your role key. On "engage":
  `FleetInteractionDialogPluginImpl p = new FleetInteractionDialogPluginImpl(config); dialog.setInteractionTarget(fleet);
  dialog.setPlugin(p); p.init(dialog);` (vanilla's SalvageDefenderInteraction does the same).
* **FIDConfig for a set piece**: `pullInAllies/Enemies/Stations = false`, `leaveAlwaysAvailable`, `alwaysLetGo`
  (the enemy never pursues), `impactsEnemyReputation = false`, `firstTimeEngageOptionText`; a `FIDDelegate`:
  `battleContextCreated(dialog, bcc)` sets `bcc.aiRetreatAllowed = false; bcc.fightToTheLast = true;
  bcc.objectivesAllowed = false`; `notifyLeave(dialog)` is your "encounter over" hook (also keep a next-tick fallback:
  the delegate is transient).
* **BattleCreationContext cannot restrict the player's deployment.** For "one ship each": take every other member out
  of the player fleet (`removeFleetMember`, remember each captain), run the encounter, put them back (re-add, re-assign
  captains) in `notifyLeave` — never mid-encounter (e.g. from a `reportBattleOccurred` callback while the dialog is
  still open). Require the duelling ship to be the flagship, so the player's own ship is never removed. Safety net in
  combat: `engine.getFleetManager(0).removeFromReserves(member)` for anything else.
* **Make losing non-fatal** as vanilla's Phase Anchor does: a `HullDamageAboutToBeTakenListener` returns true (damage
  negated) when `damageAmount >= ship.getHitpoints()`, sets hitpoints to 1, then an `AdvanceableListener` blocks
  commands, `setRetreating(true, false)`, fades the ship (`setExtraAlphaMult2`) and finally moves it to
  `(0, -1000000)`: the engine counts it as retreated. Several such listeners on one ship are all asked; coordinate
  them (only one should claim the blow).
* **A fleet that waits**: `MemFlags.MEMORY_KEY_MAKE_NON_AGGRESSIVE`, `FLEET_IGNORES_OTHER_FLEETS`,
  `FLEET_IGNORED_BY_OTHER_FLEETS`, `MEMORY_KEY_NO_JUMP`, `ORBIT_PASSIVE` assignment; set `MEMORY_KEY_MAKE_HOSTILE`
  only when the player accepts. "Beat it in one go": on leave with survivors, despawn it on the next tick (outside any
  fleet callback) and spawn a fresh one.
* **Officers beyond the cap**: `PersonAPI.getStats().setSkillLevel(id, 2)` for each of vanilla's 14 combat skills
  (Skills.HELMSMANSHIP ... POLARIZED_ARMOR, ORDNANCE_EXPERTISE = "ordnance_expert") + an npc_only custom skill, then
  `setLevel(15)`. AI-core captains: `Misc.getAICoreOfficerPlugin(Commodities.OMEGA_CORE / ALPHA_CORE).createPerson(...)`.
* **Missions**: `descriptor.json` difficulty is one of EASY, MEDIUM, HARD, IMPOSSIBLE, VARIABLE; the icon is a
  256x256 JPG illustration (a close-up, not a logo); `mission_text.txt` opens with `Location:` / `Date:`, then the
  story, `***`, then how to play it. `api.addToFleet` returns the FleetMemberAPI, so a mission can clone its variant,
  add S-mods and give it a `Global.getFactory().createPerson()` captain with skills.

## 6. Libraries (installed versions: LazyLib 3.0.0, MagicLib 1.5.6, GraphicsLib 1.10.2, LunaLib 2.0.4)

| Library | id | Use it for | Depend? |
|---|---|---|---|
| LazyLib | `lw_lazylib` | Maths, collision and combat utilities (`org.lazywizard.lazylib.*`); Kotlin runtime for Kotlin mods | Most mods already require it; cheap hard dependency |
| MagicLib | `MagicLib` | Trails, render helpers (`org.magiclib.util.MagicRender`), bounties, subsystems, paintjobs, achievements, incompatible-hullmod handling | Only if you use a feature; check with `api_lookup.py javap org.magiclib...` |
| GraphicsLib | `shaderLib` | Dynamic lights, normal/material/surface maps, distortions | Usually optional: guard with isModEnabled and keep its classes in a separate compat class |
| LunaLib | `lunalib` | In-game mod settings (LunaSettings.csv), version checking UI | Hard dependency if settings matter, else optional with defaults (`LunaSettingsBridge` template) |
| Console Commands | `lw_console` | Testing only: `spawnfleet <faction> <combatFP> [name]`, `addship <variantID> [amount]`, `goto [location]`, `addcredits`, `reveal`, `god`, `infiniteammo`, `nocooldown`, `devmode [on/off]`, `runcode <code>` (94 commands; names checked against its commands.csv) | Never a dependency |

Sources you can search: `api_lookup.py ... --libs` covers MagicLib/src, LunaLib/src, GraphicsLib/org and
Console Commands/src. LazyLib ships only a javadoc zip, so use `javap`.

## 7. Testing hooks

* Dev mode: `"devMode": false` in `starsector-core/data/config/settings.json` (vanilla's value; editing core files
  is the user's call), or the `devmode` console command. Dev mode adds debug dialog options (FireAll adds
  `DevMenuOptions`).
* `starsector.log` in starsector-core: `scripts/log_scan.py` splits it by launch, groups and explains errors, and
  puts entries mentioning your mod first.
* There is no headless or test runner: anything about AI behaviour, visuals or balance needs a human session.
  `templates/SMOKE_TEST.md` is the 10-minute checklist to hand over.
