# Pitfalls: every error met so far, with the fix (use as the review checklist)

Sources: the session that built "The Last Census" (TLC, 0.98a), this skill's own development, the starsector.log
files in this install, and the wiki's troubleshooting pages **(wiki)**. "Caught by" says what finds it now:
**V** = `validate_mod.py`, **L** = `log_scan.py`, **R** = human/agent review (no tool can).

Hand this file to the independent reviewer as their checklist, and ask for the 20 most likely causes of a crash,
broken save, blocked quest or unusable ship in *this* mod, each checked against the code.

## Build and tooling

| Symptom | Cause | Fix | Caught by |
|---|---|---|---|
| `Fatal: Index: 0, Size: 0` or class version errors at startup | Classes compiled for the wrong Java | `javac --release 17` (0.98a runs Java 17; the wiki's "JDK 7" is outdated) | build_mod.py sets it |
| `NoClassDefFoundError` / `ClassNotFoundException` in the log | Jar not listed in mod_info.json `jars`, dependency missing or outdated, or optional-mod classes touched without a guard | List jars; declare dependencies; put optional integrations in a separate class behind `isModEnabled("id")` | V (jar, imports), L |
| Mod missing from the launcher | Malformed mod_info.json or duplicate mod id **(wiki)** | Strict JSON, unique id | V |
| `Fatal: null` right after a battle; log: `ConcurrentModificationException` in `CampaignEngine.reportBattleOccurred` | A `FleetEventListener` called `fleet.removeEventListener(this)` or `despawn()` (directly or through a helper) inside `reportBattleOccurred` / `reportFleetDespawnedToListener`, while the engine iterates that fleet's listeners | Queue the fleet; unhook/despawn it in the intel's `advanceImpl` (vanilla removes listeners only from advance/end paths) | V (java) |
| Quest timers run twice as fast, intel updates fire twice | The intel was added with `addIntel` AND `sector.addScript(intel)`: the intel manager already advances intel | Only `addIntel` (vanilla SystemBountyIntel); add a separate script only for work that is not the intel's | review |
| A quest fleet parked in the abyss drifts away or flees | AI fleets flee abyssal depth above 0.5 (`HyperspaceAbyssPluginImpl.DEPTH_THRESHOLD_FOR_FLEETS_FLEEING`) | Place quest sites at `Misc.getAbyssalDepth` 0.3-0.45 | review |
| A quest step can never be completed after the player jettisoned or sold a quest item | The step checks for the item in cargo | Tag the item `mission_item, no_drop` and gate the step on the quest stage, consuming the item only if present | review |
| Jar older than the sources: changes "do nothing" | Forgot to rebuild | `./build.sh` always rebuilds; package_mod.py refuses stale jars | V (warning), package_mod |
| `unexpected EOF while looking for matching '` from Bash | Long heredocs with apostrophes or nested `'''` (3 failures last session) | Write files with the Write tool; heredocs only for short throwaway scripts | R |
| A Python patch script "silently" fails to match | Escape sequences (`\\n`) mangled through shell + Python string layers | Use the Edit tool for exact replacements | R |
| 300-500 line diffs for one-line changes | Python on Windows wrote CRLF | `open(..., "w", newline="\n")`; `.gitattributes` `* text=auto eol=lf` (scaffolded) | R |
| `TypeError: Object of type int64 is not JSON serializable` | numpy scalars in data written as JSON | `sslib.write_json` converts numpy values | tooling |
| `UnicodeEncodeError` printing to the Windows console | cp1252 console | `sys.stdout.reconfigure(encoding="utf-8")` (all scripts do) or `PYTHONIOENCODING=utf-8` | tooling |
| `python3` opens the Microsoft Store instead of running | Windows store alias | Call `python` first (build.sh does) | tooling |
| Same seed, different sprite in another run | `hash(str)` is randomised per Python process | Use `zlib.crc32` for stable seeds | tooling |

## Data files

| Symptom | Cause | Fix | Caught by |
|---|---|---|---|
| CSV first column unreadable, "invalid characters" **(wiki)** | UTF-8 **with BOM** | Save UTF-8 without BOM | V |
| `NumberFormatException` at load | Text in a numeric column, often from shifted columns (unquoted comma) | Quote cells with commas; generate CSVs with `ssdata.py` | V (column counts, numerics), L |
| Hull "not found in store", ship missing **(wiki)** | ship_data id does not match the .ship hullId (case-sensitive) | Same id everywhere | V |
| `Ship hull spec [x] not found in ship_data.csv` (ERROR) | .ship without a csv row | Add the row (vanilla logs this for 2 decorative hulls; ignore those) | V, L |
| `RuntimeException: Weapon spec [x] not found!` | Variant/faction/code references a weapon without row + .wpn | Fix the id | V, L |
| `Weapon [x] from weapon_data.csv not found in store` (WARN) | csv row without a .wpn | Add the .wpn | V, L |
| `Fatal: Index: 1, Size: 1` **(wiki)** | `turretOffsets` holds more barrels than `turretAngleOffsets` (or a similar array mismatch) | One angle offset per barrel | V |
| Crash or glitches with fighters | 7 fighter bays glitch, 8+ break **(wiki)** | 6 or fewer | V |
| Works on Windows, crashes on Linux/macOS **(wiki)** | Path case differs from the file, or `\` in paths | Exact case, `/` only | V |
| `Error loading [path] resource, not found in [mods...]` | A referenced file does not exist (the list shows every mod folder searched) | Fix the path or add the file | V (data refs), L |
| A commented-out JSON entry still breaks things **(wiki)** | Comment quirks in the lenient parser | Delete instead of commenting out | R |
| Variant spawns with a different loadout | Fleet inflater refits from the faction's known weapons/hullmods (DefaultFleetInflater); last session's role variants used rare_bp weapons the faction did not know | Faction must know every weapon/hullmod on its role variants | V (warning) |
| Fleet spawn throws `Weapon with spec id [x] not found` | Faction known/priority lists name a missing weapon or wing | Fix the id | V, L |
| Ships never appear in fleets or markets **(wiki)** | Hull not known by the faction, or no variant in default_ship_roles.json | knownShips + roles | V (note) |
| Autofit ignores the weapon **(wiki)** | No autofit tag (`kinetic#`, `energy#`, `pd#`, ...) | Add tags | V |
| Validator rule "doctrine must sum to 7" | Wrong assumption: vanilla sindrian_diktat (5), persean (6), remnant (quality 9) break it | Removed; do not reintroduce | (lesson) |
| Validator demanded `data/hulls/<id>.ship` file names | Wrong assumption: the game indexes specs by the id inside (vanilla has 5 hull and 6 variant mismatches) | Files are found by id; a name mismatch is only a note | (lesson) |
| "Class not found" for a vanilla hullmod script | Vanilla compiles loose `data/**/*.java` at startup (Janino): `data.hullmods.HeavyArmor` is not in any jar | The validator indexes `data/**/*.java` from every source | V |
| Mission screen crash `Error loading [data.missions.x.MissionDefinition]` ... `Thrown exception of type "java.lang.CloneNotSupportedException" is neither caught ...` | Loose `data/**/*.java` is compiled by Janino, which resolves `getVariant().clone()` (any interface clone()) against `Object.clone()` and its checked exception; javac/the jar build is fine with it | Move the code into a jar helper (e.g. `rsl.campaign.EncoreFleets.missionDiesIrae(member)`) or wrap it in `try { } catch (Exception e) { }` | V |
| Refit/codex crash `IllegalFormatConversionException: e != java.lang.String` | Bare `%` in hull_mods.csv `desc`/`short`/`sModDesc` (passed through String.format), e.g. "100% extends" | Write `%%` or use a `%s` param | V |
| `masterVersionFile` placeholder shipped | Scaffold left a TODO | Host the .version file and point at its raw URL | V (warning) |
| Launch crash `NumberFormatException: For input string: " 255"` in `MagicSettings.toColor3` | MagicLib `magicTrail_data.csv` colour written as `"[210, 255, 250]"` (Python `json.dumps` default adds spaces); MagicLib `parseInt`s each item untrimmed | Write colours as `[210,255,250]` (`json.dumps(c, separators=(",", ":"))`); same for any MagicLib CSV colour | (lesson) |
| Fighter hull flagged "ordnance points must be positive" | Wrong assumption: vanilla fighters have 0 OP and 0 supplies | The validator skips those checks for `.ship` hullSize FIGHTER | (lesson) |

## Sprites

| Symptom | Cause | Fix | Caught by |
|---|---|---|---|
| `ArrayIndexOutOfBoundsException` in TextureLoader **(wiki)** | 16-bit PNG | Save as 8-bit RGBA | V |
| Blurry weapon in inventory **(wiki)** | Odd sprite width | Even widths | V |
| Weapons float off the hull, engines in mid-air | Slot/engine coordinates not derived from the art | Generate art and .ship together (hullgen/kitbash); `contact_sheet.py --overlay` | V (slots over transparent pixels) |
| Flat, toy-like sprites; procedural art "looks off" next to vanilla | Generated by eye with no target; round turret bases; directional light | Measure vanilla first (`sprite_stats.py`, `weapongen.py --check`), compare on a contact sheet at 1x, follow references/sprites.md | R + stats |
| Halo around sprites when scaled | Transparent pixels hold junk colour | `alpha_bleed` (generators do it) | tooling |

## Rules and dialogs

| Symptom | Cause | Fix | Caught by |
|---|---|---|---|
| Dead dialog button | Option id without a `DialogOptionSelected` / `$option == id` rule (also options added from Java rule commands) | Add the handler | V |
| Rule command "does nothing" | Package not in `ruleCommandPackages`, or class name typo | Add the package; the validator checks every command name | V |
| Your OpenCommLink flow never shows; vanilla text appears instead | A vanilla rule on the same trigger scores higher or blocks (`$ignorePlayerCommRequests` blocked TLC's boss) | List vanilla rules on the trigger (`api_lookup.py data ",OpenCommLink," --files rules.csv`), add `score:`, unset blockers | R |
| Options vanish or duplicate | FireAll clears the panel only when the new set has options; FireBest replaces | See api-notes section 4 | R |
| Your rule silently replaced by another mod's | Unprefixed rule id collided | Prefix every rule id | V |

## Campaign code

| Symptom | Cause | Fix | Caught by |
|---|---|---|---|
| Boss fleet stranded in one system | `MemFlags.MEMORY_KEY_NO_JUMP` copied in a bundle of flags | Look up each flag's vanilla use before setting it | R (`api_lookup.py uses`) |
| Pursuing fleet never hails the player | `FLEET_IGNORES_OTHER_FLEETS` also ignores the player | Use exactly the hassle framework's flags | R |
| Set-piece battle pulls in the nearby station and fleets | Default FIDConfig pulls everyone in | FIDConfigGen with `pullInStations/Allies/Enemies = false`; fight 2500+ units from stations | R |
| Quest softlocks after the quest market is bombed or decivilized | No lifecycle analysis | `Misc.makeStoryCritical` + `DecivTracker.NO_DECIV_KEY`, released at quest end; write the lifecycle table | R |
| Station market shows "?" data | Missed `market.setSurveyLevel(SurveyLevel.FULL)` | Use the WorldGen template recipe | R (template) |
| Fleet parked in the star's corona | Assignment targeted the star | Target a planet or station | R |
| Effects fire after their reason ended (hassles after certification, liens on wrecks) | State checked when scheduled, not when firing; listeners did not filter hulks | Re-check state at fire time; filter `isHulk()` | R |
| Ships stay "always recoverable" forever | Tag added without a removal point (on a shared stock variant) | Clone the variant, remove the tag afterwards | R |
| Content missing in existing saves | World generation only in onNewGame | Also generate from onGameLoad behind a sector memory flag (idempotent) | R (template) |
| `null` from getVariant/getFaction/getMarket at runtime | Typo in an id string in Java | Ids in one Ids class; validator resolves constants and lookup literals | V |
| NullPointerException deep in a script | Unchecked lookup (`createFleet` can return null) | Null-check every lookup | L, R |

## Combat code

| Symptom | Cause | Fix | Caught by |
|---|---|---|---|
| Stuttering in big battles | Per-frame allocations (new lists/maps, lambdas, iterators) | Preallocate, `IntervalUtil`, index loops (CombatPlugin template) | R |
| Effects scale with frame rate **(wiki)** | Per-frame maths without `amount` | Multiply by `amount`; skip when paused | R |
| Bonus never goes away | `apply` without matching `unmodify(id)` in `unapply` | Same id in both | R |
| Weird shared behaviour between ships **(wiki)** | `static` fields shared by all instances | Instance fields or engine custom data | V (statics holding game objects) |
| One exception kills the battle | Unguarded plugin code | try/catch in advance, disable the plugin after the first error, log it | R (template) |
| Built-in weapon shows as a removable 0-OP item | Slot in `builtInWeapons` kept its normal type | Slot `"type": "BUILT_IN"` (vanilla Onslaught) | R |
| Moving deco part floats a quarter length off its mount | Deco weapon on a HARDPOINT mount (hardpoint sprites are drawn forward of the slot) | TURRET mount for centre-pivot parts | R |
| Hull overlay/glow never visible | Layered plugin drawn in the ship's own layer (under the hull) | Draw in `BELOW_PHASED_SHIPS_LAYER` | R |
| Second status bar appears | MagicUI keyless `drawInterfaceStatusBar` keys by label; label changed | Keyed overload | R |
| Piercing shot flies past its range | Continuation spawned with `spawnProjectile` gets a fresh range | Carry origin + `weapon.getRange()`, remove when exceeded | R |
| ConcurrentModification / skipped entities | `removeEntity` inside a loop over `engine.getProjectiles()` | Collect, remove after the loop | R |
| Custom sounds "out of place" | Synthesised tonal sounds next to vanilla's | Process vanilla samples (pitch, layer, flanger/phaser) with ffmpeg | R |

## Save compatibility

| Symptom | Cause | Fix | Caught by |
|---|---|---|---|
| Save will not load: `CannotResolveClassException: <class>` (seen in this install's log) | A class stored in the save was removed, renamed or moved (or its mod removed) | Never rename saved classes after release; `configureXStream` aliases; mark mods `"utility": true` only if they can really be removed | L |
| Memory grows after loading several saves **(wiki)** | Static fields holding sector objects | Persistent data, memory, transient fields | V (warning) |

## Docs, scope and process

| Mistake | Fix |
|---|---|
| Docs claimed "tested", described a respawn that did not exist, named the wrong LunaLib key | Write docs last; grep the code for every factual claim; never say "tested" unless it ran |
| Mixed British/American spelling | Starsector uses American English: grep before release |
| Balance numbers from memory (capital underpriced, weapons undertuned, frigate OP low) | `vanilla_baselines.py` before choosing stats, `check --mod` after |
| No Version Checker, no changelog | Scaffolded by new_mod.py |
| Fault test invalidated by `git stash` (it stashed the new check too) | Fault-inject by editing only data in a copy (selftest.py does this) |
| Reviewer started late; fixes landed just before the usage limit | Start the independent review right after the first green build; reserve budget for fix + re-review |
| Validator written against one mod raised 1800 false errors on other mods | Test validators on mods you did not write, and on both positive and negative cases (selftest runs all installed mods) |
| A dictionary keyed by tuples was stringified, so every description lookup failed | Add a regression check for every checker |
| LunaLib settings header shows blank | A `Header` row's title is its `defaultValue`, not `fieldName` (validator warns) |
| Regenerating sounds (ffmpeg libvorbis) or re-finishing a sprite rewrote every file: huge noisy git diff | Re-encoding is not byte-stable; `git checkout` the outputs you did not mean to change |
| Mission list shows a stretched logo / unknown difficulty | Icons are 256x256 JPGs; difficulty EASY/MEDIUM/HARD/IMPOSSIBLE/VARIABLE (validator `missions` group) |
