# Retrospective: building "The Last Census" (Starsector 0.98a)

This covers one autonomous session: a faction mod with a questline, written from nothing in about 2 hours 10
minutes of active work. It ended with 28 Java files (~3,400 lines), 5 hulls, 5 weapons, 2 ship systems, 1 hullmod,
63 rules, and procedural art. The build and validator were both clean at 0 errors and 0 warnings. **The game was
never launched** (the user asked me not to take over the PC), so everything below about "working" means statically
verified, not play-tested.

Sources: the session transcript (timestamps, tool calls, failures), the mod's git history, and its
VERIFICATION_REPORT.md. The numbers are approximate.

## 1. Timeline (where the time went)

| Phase | Wall clock | Notes |
|---|---|---|
| Recon (install, toolchain, vanilla data, API source) | 19 min | ~45 shell calls. Most of them were one-off greps into the extracted API source |
| Design docs (concept, lore, scope, risks) | 3 min | One long thinking turn chose the concept before this (~20K output tokens) |
| Foundation + procedural art | 15 min | 6 render-and-look cycles on the *first* hull alone |
| API verification + data generator + validator | 21 min | gen_data.py (49 KB) and validate.py (40 KB) were each written in one shot after long deliberation (~24K and ~21K output tokens) |
| Rules-engine semantics (FireAll/option clearing) | 7 min | One ~35K-token reasoning turn. The semantics are undocumented and had to be read from the API impl |
| Java (28 files) + rules + first green build | 20 min | Compiled clean on the first full build because every signature had been checked first |
| Independent reviewer agent | 39 min (parallel) | 112 tool calls; found 9 real issues |
| Balance, docs, polish, 2nd art pass, GraphicsLib lights | ~27 min (parallel with review) | |
| Fixing the 9 review findings | 4 min | Done right before the usage limit hit |
| Final re-review (after limit reset) | 2 min | Found 1 more real bug |

Total output was about 1.95M tokens including thinking. The session hit the plan's usage limit before the final
re-review, which had to wait for the reset.

## 2. What worked (keep doing these)

1. **Verify against primary sources before writing code.** The game ships its API *with implementation source*
   (`starsector-core/starfarer.api.zip`). Every API call was checked there first, so the first full compile
   of 28 files had no API errors. Reading the impl showed behaviour no doc states: FireAll clears and replaces
   options, recovery replaces non-AI captains, and the vanilla hassle framework can be reused.
2. **Generate every data file from Python, using vanilla's exact CSV headers.** gen_data.py and gen_rules.py produced
   all the CSV/JSON. There were zero quoting or column-count errors, and balance changes were one-line edits.
3. **Give art and data one source of truth.** gen_ships.py wrote the sprite *and* the `.ship` (bounds, slots,
   engines) from one hull spec, so slots could never drift off the art.
4. **Write a project validator early and gate the build on it.** It was written before any Java existed and run on
   every build. A fault-injection test (7 deliberate faults, all caught) proved it works. It caught a real bug: the
   faction didn't know weapons its own variants used.
5. **Use an independent adversarial reviewer.** A fresh agent with a pointed checklist found 9 real defects that my
   own review missed, including a quest softlock and a boss fleet that could never hail the player. A re-review of
   the fixes found another.
6. **Reuse vanilla frameworks instead of inventing.** The audit encounters reuse the hassle framework
   (`$willHasslePlayer`, `HailPlayer`). The hearing reuses FIDConfigGen, the Remnant pattern. Recovery uses
   `Tags.VARIANT_ALWAYS_RECOVERABLE`. Less custom code meant less risk.
7. **Make balance numbers come from tables.** A script printed vanilla peers next to every mod hull and weapon.
   Every "too strong/too weak" call was made against those tables.
8. **Commit at every milestone.** This made diffs and rollbacks cheap.

## 3. What cost the most time and tokens, and why

1. **API spelunking with ad-hoc greps (~50 calls, ~25 min total).** There was no cheat sheet, so every question
   ("what does FleetParamsV3 take?", "how is a combat plugin registered?") needed a fresh extract-grep-read cycle.
   → Fixed by `scripts/api_lookup.py` and `references/api-notes.md`.
2. **Writing huge one-off generators and a validator from scratch.** About 90 KB of Python was written mid-session,
   with long deliberation before each file. → Fixed by the generic `scripts/validate_mod.py`, `scripts/new_mod.py`
   and `templates/`.
3. **Art iterated by eye with no target.** 6 cycles on one hull plus two later passes (~25 min), and the result was
   still visibly below vanilla. Root cause: I never measured what vanilla sprites actually look like (palette, light
   direction, detail density) before starting. → Fixed by `scripts/sprite_stats.py` (measure),
   `scripts/hullgen.py` presets tuned to the measurements, and `scripts/contact_sheet.py` (compare at 1x).
4. **Reviewer latency and late fixes.** The review started after the content slice and took 39 minutes. Its fixes
   landed in the last 4 minutes before the usage limit, which pushed the final re-review to after the reset.
   → Start the review right after the first green build, give it `references/pitfalls.md` as the checklist, and
   reserve budget for fix plus re-review.
5. **Shell heredoc failures (3 times, same mistake).** Long Bash commands that held several heredocs, or
   triple-quoted Python, failed with `unexpected EOF while looking for matching '`. I retried the same pattern twice
   before switching tools. → Write files with the Write tool. Use heredocs only for short throwaway scripts, one
   per command.
6. **Line-ending churn.** Rewriting files from Python on Windows flipped LF/CRLF, giving 300–500-line diffs for
   small changes (DESIGN.md, rules.csv, several Java files). That made review harder.
   → Always `open(..., "w", newline="\n", encoding="utf-8")`, and add `.gitattributes` (`* text=auto eol=lf`).

## 4. Mistakes and wrong assumptions

| # | Mistake | Root cause | Caught by | Rule now |
|---|---|---|---|---|
| 1 | The faction's role variants used `rare_bp` weapons (Heavy Mauler, Heavy Blaster) the faction didn't know | Assumed variant weapons are available to the faction automatically | Self-review, then a new validator check | Validator: every weapon/wing/hullmod on a faction's role variants must be in its known lists |
| 2 | Boss fleet had `MEMORY_KEY_NO_JUMP`, so it would be stranded in the player's system | Copied a bundle of fleet flags without checking each one | Self-review | Before setting any MemFlag, grep its vanilla uses and state its effect in a comment |
| 3 | Boss pursuit set `FLEET_IGNORES_OTHER_FLEETS`, which likely ignores the player too, so it would never hail | Same cargo-culting of flags | Reviewer agent | Pursue with exactly the flags vanilla `HasslePlayerScript` sets, and no extras |
| 4 | The hearing battle next to the faction station would pull the station in | Didn't think about who joins battles | Reviewer agent | Give set-piece fights an FIDConfigGen with `pullInStations/Allies/Enemies=false`, and keep them ≥2500 su from stations |
| 5 | Missing `unset $ignorePlayerCommRequests`, so vanilla's greetingNoComms could pre-empt the hearing | Didn't trace which vanilla rules compete for the same trigger | Reviewer agent | For each custom OpenCommLink flow, list the vanilla rules on that trigger and check their scores |
| 6 | The quest-critical market could be saturation-bombed or decivilized, which softlocks the quest | No lifecycle analysis for quest-critical entities | Reviewer agent | For every quest-critical entity, check destroyed/captured/decivilized/player-hostile/save-load. Use `Misc.makeStoryCritical` and `NO_DECIV_KEY` |
| 7 | Liens could re-settle on wrecks; an in-progress hassle could still fire after certification | Event listeners didn't filter hulks or check state at fire time | Reviewer agent | Re-check state when an effect fires, not only when it's scheduled |
| 8 | Per-frame allocations in a combat plugin (lists and maps per frame) | Wrote the obvious code first | Reviewer agent | Combat plugins: preallocate, use index arrays and swap-remove, no lambdas or iterators in `advance` |
| 9 | Market never set its survey level | Missed a step from the vanilla market-creation pattern | Reviewer agent | Copy the full vanilla station-market recipe (see `references/api-notes.md`) |
| 10 | The boss "waits" at the system's star, which parks its fleet in the corona | Didn't consider campaign geometry | Final re-review | Park fleets at planets or stations clear of coronas, never the star |
| 11 | Seized ships kept `VARIANT_ALWAYS_RECOVERABLE` forever | Forgot cleanup after the effect | Self-review | Every tag or flag you add needs a documented removal point |
| 12 | Balance first pass: a capital underpriced (32 → 36 DP), two weapons undertuned, frigate OP low | Set numbers from memory before generating vanilla tables | Balance tables | Run `vanilla_baselines.py` *before* choosing any stat |
| 13 | Treated `8/6/5/4%` as meaningful | The wiki says the engine doesn't use it | Wiki (later) | Fill it for consistency but don't reason from it |
| 14 | Docs overclaimed ("tested"), described a respawn that didn't exist, and named the wrong LunaLib key (F2 vs F3) | Docs written from the plan, not from the code | Self-review | Write docs last and grep the code for every factual claim |
| 15 | Mixed British and American spelling in player text | No style rule set up front | Self-review | Starsector uses American English. Run a spelling grep before release |
| 16 | Invalid validator fault test: `git stash` stashed the new check along with the bug | Careless test design | Noticed in output | Fault-inject by editing only the data file, then restore it with `git checkout -- <file>` |
| 17 | The wiki says compile with JDK 7 | Wiki is outdated for 0.98 | Checked the API class file version (major 61) | Compile with `javac --release 17` |
| 18 | No Version Checker support (`.version` + `version_files.csv`) | Not on my checklist; every other installed mod has it | This retrospective | `new_mod.py` scaffolds it; the preflight checks it |

## 5. Verified vs guessed

**Verified (and how):**
* Every API signature used: by compiling against `starfarer.api.jar`, with the semantics read in the API source.
* The rules engine: FireAll/FireBest/option clearing in `RuleBasedInteractionDialogPluginImpl` and the rule
  commands. Memory scopes from vanilla rules.csv.
* Data formats: the exact vanilla CSV headers, copied programmatically. `.ship`/`.variant`/`.wpn` fields come from
  vanilla files.
* `.ship` coordinate convention and weapon sprite centring: measured on vanilla sprites and files.
* GraphicsLib light-data API: `javap` on Graphics.jar plus GraphicsLib's own CSVs.
* Ship recovery captain handling, hassle framework flags, story-critical and decivilization keys: read in the API impl.
* Java target: the API's class major version 61, which means Java 17.

**Guessed or unverified, and how to verify next time:**
| Item | How to verify |
|---|---|
| Whether the game loads the mod without errors | Launch with the mod enabled, then grep `starsector-core/starsector.log` for `ERROR`/`Exception` (see `scripts/log_scan.py`) |
| Fleet AI behaviour (routes, pursuit timing, when a hassler hails) | In-game smoke test with Console Commands (`spawnfleet`, `goto`), devMode on |
| Ship system AI timing, weapon feel, visual effects | Simulator battles against vanilla peers |
| Combat balance | Sim battles: mod hull against same-DP vanilla hull, both AI-controlled, 5 runs each |
| How the procedural sprites read at in-game zoom | Screenshot in combat at 1x and zoomed out |
| GraphicsLib light appearance | In-game with GraphicsLib enabled |
| Nexerelin random-sector compatibility | Start a Nexerelin random-sector game |
| LunaLib settings UI | Open the LunaLib menu in game |

If the user forbids launching the game, give them `templates/SMOKE_TEST.md` (a 10-minute checklist) so they can
run it themselves.

## 6. Rules for next time

1. **Before choosing any stat, run `scripts/vanilla_baselines.py`** and pick numbers inside the vanilla band for
   that hull size or weapon class. Justify each outlier in BALANCE.md.
2. **Before calling any API method, look it up** with `scripts/api_lookup.py`. If the behaviour matters, read the
   impl. Never write a signature from memory.
3. **Before setting a memory flag or tag, look up its vanilla uses** (`api_lookup.py uses MEMORY_KEY_X`,
   `api_lookup.py const MemFlags X`) and write its effect in a comment. Every added flag or tag needs a removal point.
4. **Before writing Java, scaffold with `scripts/new_mod.py` and get `scripts/validate_mod.py` to 0 errors** on
   the data alone.
5. **Before drawing any sprite, measure vanilla** (`sprite_stats.py` on 3–5 peers of the same size and tech) and
   choose a hullgen preset. Compare at 1x on a contact sheet with vanilla peers after every pass.
6. **Right after the first green build, start an independent review** with `references/pitfalls.md` as the
   checklist. Keep building while it runs, and reserve time to fix and re-review.
7. **For every quest-critical entity, write a lifecycle table** (destroyed, captured, decivilized, player hostile,
   save/load, mod added mid-game) before marking the quest done.
8. **For every custom dialog entry point, list the vanilla rules on the same trigger** and check their scores and
   conditions so yours wins. Unset vanilla blockers such as `$ignorePlayerCommRequests`.
9. **Write files with the Write tool,** never with long multi-heredoc shell commands. Write text from Python with
   `newline="\n"`.
10. **Write docs last and grep the code for every claim.** Never call anything "tested" unless it ran.
11. **Add Version Checker files and a CHANGELOG from day one.** `new_mod.py` does this.
12. **Watch the budget.** Long single-shot generators and 30K-token deliberations are the expensive part. Start from
    templates, and keep design deliberation for the concept, not the plumbing.

## 7. Quality gaps (critical)

* **Zero runtime verification.** Nobody ran the mod. A single typo in a JSON field the validator doesn't know about
  could still crash startup. The validator only covers fields it was taught.
* **The art is below vanilla.** The sprites were readable and consistent but flat next to vanilla's hand-painted
  hulls: less micro detail, no weathering, uniform plating, and no normal or material maps for GraphicsLib. The
  icons were simple glyphs.
* **No audio.** All sounds and music were vanilla ids.
* **Balance only on paper.** The tables put stats in vanilla bands, but synergies (debuff stacking, the system plus
  weapon interplay) were never observed.
* **Prose quality only self-reviewed.** It read well, but nobody checked it in context (dialog panel width, line
  breaks, highlight colours).
* **The tooling was mod-specific.** The validator hard-coded the `tlc_` prefix and the mod's own id classes. This
  skill's `validate_mod.py` is the generalised version.
* **No Version Checker, no changelog, no release zip process.** Now covered by the templates and
  `scripts/package_mod.py`.

## 8. Addendum: what generalising the tools exposed (skill-building session)

Turning the mod's tooling into general tools and testing it on every installed mod showed that some "verified"
rules were assumptions. All are fixed in this skill:

* **Faction doctrine sums.** The old validator demanded doctrine values summing to 7. Vanilla sindrian_diktat
  (composition 5), persean (6) and remnant (quality 9) break that rule. It was never checked against vanilla.
* **File names.** It required `data/hulls/<hullId>.ship`. The game indexes specs by the id inside the file: vanilla
  warhound.ship holds hullId cerberus, and 5 hulls and 6 variants differ from their file names.
* **Loose Java.** The game compiles `.java` under `data/` at startup, which is how vanilla's own hullmods load
  (`data.hullmods.HeavyArmor`). A validator that only knows jar classes reports false "class not found" errors.
* **Tariff.** TLC set `getTariff().modifyFlat("generator", 0.3f)`. Vanilla uses
  `modifyFlat("default_tariff", faction.getTariffFraction())`.
* **LunaLib field types.** The list lacked `Enum` (read from LunaLib's loader source now).
* **First run of the generic validator** on 7 mods it did not know: about 1,800 false errors (comment rows,
  per-map texture rows, string concatenation, libraries "depending on themselves"), plus one real bug in itself:
  tuple keys turned into strings, so every description lookup failed. Lesson: test a checker on code you did not
  write, with both clean and deliberately broken input. `selftest.py` now injects 22 faults and runs the validator
  on every installed mod.
* **Weapon art.** The first weapon generator drew round turret bases with smooth shading. Measuring all 275 vanilla
  weapon sprites showed the target: narrow mechanical stacks with 25-44% opaque coverage and very high pixel-level
  detail. The rewrite follows those numbers (references/sprites.md).
