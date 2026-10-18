# Starsector modding skill

A [Claude Code](https://claude.com/claude-code) skill for building, debugging, balancing and releasing mods for
[Starsector](https://fractalsoftworks.com/) (0.98a, Java 17). Claude loads it automatically when you mention
Starsector, `mod_info.json`, `rules.csv`, `.ship`/`.wpn` files, LazyLib/MagicLib/GraphicsLib/LunaLib and so on.

Tested on Starsector 0.98a-RC7 (Windows) with JDK 17 and Python 3 + Pillow + numpy.

## Install

```
git clone https://github.com/tracesfx/starsector-modding-skill ~/.claude/skills/starsector-modding
python ~/.claude/skills/starsector-modding/scripts/selftest.py   # ~1 min, proves every tool works
```

On Windows the target is `%USERPROFILE%\.claude\skills\starsector-modding`. The scripts locate the game via
`STARSECTOR_DIR`, common install paths, or by walking up from the mod folder.

## What's inside

| Path | Purpose |
|------|---------|
| `SKILL.md` | Entry point: workflow and rules Claude follows |
| `scripts/` | `new_mod` (scaffold), `build_mod`, `validate_mod` (catches 20+ crash/softlock causes), `api_lookup` (API source search), `vanilla_baselines` (balance tables), `log_scan`, `package_mod`, `ssdata`, sprite tools (`hullgen`, `kitbash`, `weapongen`, `sprite_tools`, `contact_sheet`, `sprite_stats`), `selftest` |
| `references/` | File formats, API notes, balance, ships and combat, sprites, pitfalls, retrospective |
| `templates/` | Mod scaffold, Java class templates, smoke-test and review prompts |
| `examples/the_last_census/` | A complete worked example mod |

## Quick start

```
S=~/.claude/skills/starsector-modding/scripts
python $S/new_mod.py create --name "Iron Tithe" --deps lazylib --git
cd "<game>/mods/IronTithe" && ./build.sh
python $S/api_lookup.py class FleetParamsV3
python $S/vanilla_baselines.py peers --size DESTROYER --dp 10
```

Or just ask Claude: "make a Starsector mod that adds a new hullmod".

## Safety

The skill never launches the game and never edits vanilla files or other mods without explicit permission. It
verifies statically and hands you `templates/SMOKE_TEST.md` for the in-game check.
