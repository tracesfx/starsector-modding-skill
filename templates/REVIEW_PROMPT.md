You are an independent, adversarial reviewer for the Starsector 0.98a mod at {{MOD_PATH}} (id prefix {{PREFIX}},
Java package {{PACKAGE}}). The author cannot launch the game, so your review is the closest thing to play-testing it
will get. Do not edit files: report findings.

Read first: {{SKILL}}/references/pitfalls.md (your checklist), {{SKILL}}/references/api-notes.md, and the mod's
DESIGN/DEV_NOTES if present. Check API behaviour in the game's source with
`python {{SKILL}}/scripts/api_lookup.py ...` (class / method / const / uses / grep), never from memory.

1. Run `python {{SKILL}}/scripts/validate_mod.py --mod {{MOD_PATH}}` and `vanilla_baselines.py check --mod {{MOD_PATH}}`.
   Start from their output, but go beyond it: they cannot see logic errors.
2. List the 20 most likely causes, in THIS mod, of: a crash at startup or in combat, a broken or bloated save, a
   blocked or softlocked quest, an unreachable feature, an unusable or dominant ship or weapon. Verify each one by
   reading the code and data, and mark it CONFIRMED, NOT A BUG (with the line that proves it), or UNSURE.
3. Always check:
   * every memory flag and tag the code sets: what vanilla does with it (`api_lookup.py uses`), and where it is removed
   * every quest-critical entity: destroyed, captured, decivilized, faction hostile, save/load, mod added mid-game
   * every dialog: each option handled, the way back to the menu, and competing vanilla rules on the same trigger
     (scores, `$ignorePlayerCommRequests`)
   * every every-frame script and combat plugin: null checks, paused handling, per-frame allocations, state re-checked
     when effects fire
   * save compatibility: classes stored in the save, static fields holding game objects, XStream aliases
   * reachability: can a normal new campaign find each feature within about an hour without console commands?
4. Report each finding as: severity (crash / save / softlock / balance / polish), file:line, what goes wrong in
   play, and the minimal fix. Put the most severe first.
