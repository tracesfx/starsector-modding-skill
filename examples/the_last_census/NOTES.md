# Examples from "The Last Census" (TLC)

Copied from `mods/TheLastCensus` at commit 865ebe6: a Starsector 0.98a faction-and-questline mod built in one
session. It has 29 Java classes, 5 hulls, 5 weapons, 2 ship systems, 1 hullmod and 63 rules. It builds with 0 javac
warnings, its own validator and the skill's `validate_mod.py` report 0 errors, and an independent review plus a
re-review found and fixed 10 bugs. **It was never run in game**, so treat every behaviour below as statically
verified, not play-tested.

Paths below are relative to this folder. The originals compile in the full mod: these copies are reference
material, not a buildable mod.

## Data

| File | What it shows | Why it is right |
|---|---|---|
| `mod_info.json` | Dependencies (LazyLib, LunaLib), jar, modPlugin | ids taken from the installed mods' own mod_info.json |
| `data/hulls/ship_data.csv`, `tlc_assessor.ship`, `data/variants/tlc_assessor_Standard.variant` | A hull row, its geometry, a legal variant | Generated from Python with vanilla's exact header; .ship written from the same spec as the sprite; OP checked by the validator |
| `data/weapons/weapon_data.csv`, `tlc_writ.wpn` (beam), `tlc_foreclosure.wpn` + `proj/tlc_foreclosure_shot.proj` (projectile + onHitEffect), `tlc_subpoena.wpn` + `proj/tlc_subpoena_srm.proj` (missile) | One weapon of each kind | Same fields as vanilla .wpn/.proj files; stats tuned against generated vanilla band tables |
| `data/hullmods/hull_mods.csv` | A built-in hullmod (hidden, cost 0) with `%s` description params | Script class resolved by the validator |
| `data/shipsystems/ship_systems.csv`, `tlc_surcharge.system` | Custom system with custom AI (`aiType: CUSTOM`) | statsScript/aiScript classes exist in the jar |
| `data/world/factions/tlc_bureau.faction`, `factions.csv`, `default_ship_roles.json` | A complete new faction, listed in factions.csv, whose role variants use only gear it knows | The validator caught the faction not knowing rare_bp weapons its variants used |
| `data/campaign/rules.csv` | Reusing vanilla's **hassle framework**: `tlc_auditBegin` triggers on `BeginFleetEncounter` with `$hassleType == tlc_audit` and `$pursuePlayer_hassle score:50`, sets `$hassle_didAlready`/`$hassleComplete`, then `HailPlayer`; the comm flow runs on `OpenCommLink` with `score:100`, and every exit restores `MakeOtherFleetPreventDisengage hassle false` | Copied from vanilla's own hassle rules; every option has a handler (validator) |
| `data/strings/descriptions.csv` | SHIP/WEAPON/SHIP_SYSTEM/FACTION/CUSTOM descriptions | (id, type) keys checked |
| `data/config/settings.json` | `ruleCommandPackages`, a combat plugin under `plugins`, `graphics` entries for intel icons and portraits, `designTypeColors` | Same mechanisms vanilla and the big libraries use |
| `data/config/LunaSettings.csv` | LunaLib settings (Header/Boolean/Int) | Field types from LunaLib's loader |
| `data/config/custom_entities.json` | A station and two custom entities with descriptions | Sprites and description ids checked |
| `data/lights/tlc_light_data.csv` | GraphicsLib projectile/beam lights | Header copied from GraphicsLib's core_light_data.csv |
| `graphics/ships/tlc_assessor.png`, `graphics/weapons/tlc_writ_*.png`, `tlc_foreclosure_*.png` | Last session's procedural art | Valid sprites, but **below vanilla quality**: use the skill's newer hullgen/kitbash/weapongen instead |

## Java (src/tlc)

| File | Pattern |
|---|---|
| `TLCModPlugin.java` | Lifecycle: onApplicationLoad (guarded GraphicsLib integration), onNewGame + idempotent onGameLoad, `addScript` only if missing, `configureXStream` aliases for every class stored in the save |
| `TLCIds.java` | Every data id in one class. The validator resolves constants named HULL_/WEAPON_/FACTION_/... |
| `TLCSettings.java` | Reading LunaLib settings with defaults and try/catch (LunaLib is a hard dependency here) |
| `world/TLCWorldGen.java` | Star systems, planets, station market (survey level, submarkets, industries), hyperspace clearing, story-critical + no-decivilization protection with a release method, important people. Basis of `templates/java/WorldGen.java` |
| `combat/TLCLedgerPlugin.java` | Allocation-free every-frame combat plugin: preallocated maps of `float[]`, swap-remove iteration, `IntervalUtil`, per-battle instance in `engine.getCustomData()`, a `DamageListener`, capped debuff stacking |
| `combat/TLCForeclosureOnHit.java` | `OnHitEffectPlugin` with no per-shot state in fields |
| `hullmods/TLCProtocols.java` | Built-in hullmod that hands work to the combat plugin and fills `%s` description params |
| `systems/TLCSurchargeStats.java`, `TLCSurchargeAI.java` | System stats script with a one-shot pulse and status data; custom system AI on an interval |
| `rulecmd/TLCAuditCMD.java` | Rule command with sub-actions, memory access, dialog text, and quest stage changes |
| `campaign/TLCQuest.java` | Quest state machine in sector memory: stages as strings, re-checked every tick, release of protections at the end |
| `campaign/TLCInspectorGeneral.java` | Boss fleet: hostility/pursuit flags set with `Misc.setFlagWithReason` and cleared on every exit path; parks at a planet, not the star; `FLEET_INTERACTION_DIALOG_CONFIG_OVERRIDE_GEN` |
| `campaign/TLCHearingConfigGen.java` | `FIDConfigGen` that stops stations, allies and enemies joining a set-piece battle |
| `campaign/TLCHearingIntel.java` | `BaseIntelPlugin` with icon, tags, faction colours and bullet points |
| `compat/TLCGraphicsLibCompat.java` | Optional-library integration isolated in its own class, only called after `isModEnabled("shaderLib")` |

## Build and tools

* `build.sh`: last session's bash build (classpath loop, cygpath on Windows, `javac --release 17 -Xlint:all`, jar,
  validate). Superseded by `scripts/build_mod.py`, which reads dependencies from mod_info.json and works without
  bash.
* `tools/gen_rules.py`: generating rules.csv from Python data, which avoids quoting errors in multi-line cells.
  The distilled, tested version of the whole data-generation approach is `templates/tools/gen_content.py`.

## Known gaps in this example (do better next time)

* No Version Checker files (`validate_mod.py` warns). Scaffold with `new_mod.py` to get them.
* `TLCWorldGen` sets the tariff with `modifyFlat("generator", 0.3f)`. Vanilla uses
  `modifyFlat("default_tariff", faction.getTariffFraction())` (Galatia.java); the template does it vanilla's way.
* The old TLC validator asserted faction doctrine sums of 7. That is false for several vanilla factions, and
  `validate_mod.py` no longer checks it.
* Art: below vanilla (see references/sprites.md). Audio: vanilla sound ids only.
