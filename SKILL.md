---
name: starsector-modding
description: Build, extend, debug, balance and release mods for the game Starsector (0.98a, Java 17), including factions, ships, weapons, hullmods, ship systems, star systems, markets, rules.csv dialogs, quests/intel, ship and weapon sprites, and GraphicsLib maps. Use this skill whenever the user mentions Starsector or Fractal Softworks, a Starsector mod or mod_info.json, .ship/.variant/.wpn/.proj/.faction/.system files, ship_data.csv, weapon_data.csv, rules.csv, starsector.log, or LazyLib/MagicLib/GraphicsLib/LunaLib, or asks to create, fix, balance, test or package Starsector content, even if they never say "skill". It ships tested tools (a mod scaffold, a one-command build, a validator that catches 20+ crash and softlock causes, vanilla balance tables, an API source lookup, a log analyser, sprite generators and release packaging).
---

# Starsector modding

Tested on Starsector 0.98a-RC7 (Windows) with JDK 17 and Python 3 + Pillow + numpy. Everything here was checked
against the game's own files and API source; anything that was not is marked **unverified** in the references.

```
S=~/.claude/skills/starsector-modding/scripts        # Windows: %USERPROFILE%\.claude\skills\starsector-modding\scripts
python $S/selftest.py                                 # once per machine / game update: proves every tool works (~1 min)
python $S/new_mod.py create --name "Iron Tithe" --deps lazylib --git    # scaffold in <game>/mods/IronTithe
cd "<game>/mods/IronTithe" && ./build.sh              # compile + validate (build.bat on Windows cmd)
python $S/api_lookup.py class FleetParamsV3           # before using ANY API
python $S/vanilla_baselines.py peers --size DESTROYER --dp 10           # before choosing ANY stat
```

The scripts find the game by itself (env `STARSECTOR_DIR`, common install paths, or walking up from the mod).

**Never launch the game, and never edit vanilla files or other mods, without the user's explicit OK.** Launching
takes over their PC. Verify statically, and hand the user `templates/SMOKE_TEST.md` for the in-game part.

## Workflow

1. **Recon (minutes, not an hour).** Run `selftest.py`. Read `sslib.installed_mods()` output and the game version.
   Answer API questions with `api_lookup.py` (`class`, `method`, `const`, `uses`, `grep`, `rulecmd`, `javap`) instead
   of extracting and grepping the API zip by hand: that cost about 25 minutes last time.
2. **Design.** One strong idea expressed through mechanics, art, writing and quests. Write DESIGN.md with a scope
   budget (MUST/SHOULD/STRETCH), the id prefix (e.g. `itx_`), dependencies and a risk list. Cut early.
3. **Scaffold.** `new_mod.py create ...` gives mod_info.json, Version Checker files, ModPlugin + Ids classes, a
   build that vendors `tools/` (build/validate/log_scan/package), .gitattributes (LF) and a README/CHANGELOG. Build at
   once. Only placeholder warnings should appear. Commit.
4. **Numbers before content.** `vanilla_baselines.py hulls|peers|weapons|wings|hullmods`. Clone the nearest
   vanilla row (`ssdata.py clone ship_data.csv <peer> ...`) and change only what the design needs
   (references/balance.md).
5. **Art.** Read references/sprites.md first. Hulls: `kitbash.py` (most vanilla-like) or `hullgen.py` (original
   art). Weapons: `weapongen.py`. External or AI images: `sprite_tools.py clean`. Both generators write the .ship
   or .wpn geometry from the same spec as the art. After every pass, LOOK at
   `contact_sheet.py --mod M --peers 2 --scale 1,2 --overlay` (judge at 1x) and run `sprite_stats.py --mod M`.
6. **Data.** Generate it from Python and re-run the generator after every change. Copy
   `templates/tools/gen_content.py` (a hull, variant, weapon, faction, roles and dialog in one tested script) and
   adapt it. `ssdata.py` gives vanilla's exact headers, cloned rows/specs and safe upserts. Never hand-type a CSV
   header (references/file-formats.md).
7. **Code.** `new_mod.py add hullmod|system [--ai]|combat-plugin|onhit|weapon-effect|rulecmd|intel|script|worldgen|fleet|luna`
   writes a compile-checked class and the data wiring that never changes. Look up every API call; keep ids in the
   Ids class; guard optional libraries; make world generation idempotent; mind save compatibility
   (references/api-notes.md).
8. **Vertical slices.** Faction + ships, then the questline, then events, then polish. After each slice:
   `./build.sh` (must report 0 errors), commit, and fix everything before moving on.
9. **Independent review.** Right after the first green build, if subagents are available (and the user allows
   them), start a reviewer with `templates/REVIEW_PROMPT.md`. Its checklist is references/pitfalls.md. Keep
   building, then fix and run a re-review. Last time this found 10 real bugs that self-review missed.
10. **Release.** Bump the version in mod_info.json, the .version file and CHANGELOG. Fill README/CREDITS. Then
    `python tools/package_mod.py --strict` (blocks on errors, placeholders, a stale jar or version mismatch).
11. **Test in game** (user, or you if allowed): `templates/SMOKE_TEST.md`, then `python tools/log_scan.py --mod .`
    and fix what it shows.

## Which reference to read, and when

| File | Read it when |
|---|---|
| references/file-formats.md | Writing or debugging any data file: layout, loading rules, every CSV/JSON/spec format and its gotchas, Version Checker, LunaLib, GraphicsLib data |
| references/api-notes.md | Writing Java: lifecycle, save compatibility, combat plugins, hullmods, systems, rules.csv engine semantics, world gen, markets, fleets, MemFlags, intel, libraries |
| references/sprites.md | Before making any art: hard requirements, measured vanilla sizes and style targets, the four art approaches and their tested results, GraphicsLib maps |
| references/balance.md | Before choosing stats: vanilla bands for hulls/weapons/hullmods, how to read the columns, economy guardrails |
| references/ships-and-combat.md | Making ships, weapons, systems, hullmods, stations, fighters, FX or sounds: the lessons of a full ship-faction build (BUILT_IN slots, deco mounts, pierce, trails, sounds, S-mods, tooltips, glow layers) |
| references/pitfalls.md | Before review and before release (it is the reviewer's checklist), and when something breaks |
| references/retrospective.md | Planning a large autonomous build: where the time went last time and why |
| examples/the_last_census/NOTES.md | You want a real, working example of a pattern (hassle-framework rules, boss fleet, allocation-free combat plugin, FIDConfigGen, quest state machine) |

## Scripts

| Script | Purpose |
|---|---|
| `selftest.py` | End-to-end proof that every tool works here (scaffold, build, 22 injected faults, sprites, packaging) |
| `new_mod.py` | `create` a mod skeleton; `add <kind>` a Java class from templates/java plus its data wiring |
| `build_mod.py` | javac (--release = the game's JRE) against core + dependency jars, write the jar, then validate |
| `validate_mod.py` | Static QA: JSON/CSV shape, ids and cross-references, sprites vs .ship, variants (OP, mounts), factions, rules, Java id lookups, encoding, path case, Version Checker. `--strict` before release |
| `ssdata.py` | Vanilla headers, rows and specs; clone + upsert CSV rows; merge JSON |
| `api_lookup.py` | Search the API + vanilla implementation source, data files and library jars |
| `vanilla_baselines.py` | Stat bands, nearest peers, and `check --mod` (every OUT stat needs a justification) |
| `log_scan.py` | starsector.log by launch: errors grouped, explained, and your mod's stack frames first |
| `package_mod.py` | Release zip (single top folder, no dev files) after the release checks |
| `hullgen.py` / `kitbash.py` / `weapongen.py` | Hull sprite + .ship from a spec / from vanilla pieces; weapon sprites + .wpn offsets |
| `sprite_tools.py` | clean (external/AI image to sprite), recolor, maps (GraphicsLib), check |
| `sprite_stats.py` / `contact_sheet.py` | Measure against vanilla; side-by-side sheets with slot overlays |

## Rules that prevent the expensive mistakes

1. Look up every API call and every MemFlags flag before using it (`api_lookup.py const|uses`). Copy what vanilla
   does, and give every flag or tag you add a removal point. A copied bundle of flags stranded a boss fleet and
   stopped it hailing the player.
2. Choose no stat without `vanilla_baselines.py`. Re-check with `check --mod` after every balance change.
3. Measure vanilla art before drawing (`sprite_stats.py --vanilla-table`, `weapongen.py --check`), and compare on a
   contact sheet at 1x after every pass. Vanilla has no baked directional light; weapons are guns, not turret discs.
4. Generate data and art from code with vanilla's exact headers. Re-run the generators; never hand-edit generated
   files.
5. Keep `./build.sh` at 0 errors after every slice, and commit each time.
6. For every quest-critical entity, write the lifecycle table (destroyed, captured, decivilized, hostile, save/load,
   added mid-game) and protect it (`Misc.makeStoryCritical`, `DecivTracker.NO_DECIV_KEY`) until the quest ends.
7. For every custom dialog entry point, list vanilla's rules on the same trigger and make sure yours wins
   (`score:`, unset `$ignorePlayerCommRequests`), and give every option a handler and a way back.
8. Create world content in onNewGame and, behind a memory flag, in onGameLoad. Never rename a saved class after
   release; alias them in `configureXStream`.
9. Per-frame code: no allocations, `IntervalUtil`, null and pause checks, try/catch that disables the plugin rather
   than crashing the battle.
10. Write files with the Write/Edit tools, not long heredocs or patch scripts (escapes get mangled). Write text with
    `newline="\n"`.
11. Write the docs last and grep the code for every claim. Never call anything "tested" unless it ran in game.
12. Watch the budget: start from templates and spend long deliberation on the concept, not the plumbing. Leave room
    for review fixes and a re-review.

## Pre-release checklist

- [ ] `./build.sh --strict` and `package_mod.py --strict` pass: 0 errors, 0 warnings, no placeholders, jar fresh
- [ ] `vanilla_baselines.py check --mod .`: every OUT stat justified in BALANCE.md
- [ ] Contact sheet at 1x next to vanilla peers looks right; slots, engines and bounds line up (overlay)
- [ ] Every new hull and weapon has a description; every faction appears in factions.csv; role variants use only
      gear the faction knows
- [ ] Every dialog option has a handler and a way back; quest-critical entities protected and released
- [ ] New game AND an existing save both get the content exactly once (idempotent generation)
- [ ] No static fields holding game objects; XStream aliases for saved classes; optional libraries guarded
- [ ] Version identical in mod_info.json, the .version file (masterVersionFile hosted) and CHANGELOG
- [ ] README (spoiler-free, requirements, save compatibility), CREDITS (kitbash sources, libraries)
- [ ] Independent review and re-review done; findings fixed
- [ ] In-game smoke test (`templates/SMOKE_TEST.md`) run, and `log_scan.py --mod .` clean; or the report says
      plainly that it was not run

## Limits (say these plainly to the user)

* No tool here can play the game. AI behaviour, visuals in motion, sounds and real balance need a human session.
* Procedural art is consistent and measurably in vanilla's tonal range but still below hand-painted vanilla
  (references/sprites.md section 8). Kitbashing is the closest match. Portraits, icons and illustrations have no
  good generator.
* AI image generation was not tested: the cleanup pipeline is ready for externally made images.
