# {{MOD_NAME}}: 10-minute in-game smoke test

Static checks (build, validate_mod.py) cannot see AI behaviour, visuals or balance. Please run this once, then send
back the output of `python tools/log_scan.py --mod .` (or the last ~200 lines of `starsector-core/starsector.log`).

**Setup:** enable only {{MOD_NAME}} and its requirements in the launcher. Console Commands helps (open the console with
Ctrl+Backspace) but is optional.

1. **Launch.** The launcher lists {{MOD_NAME}} {{VERSION}} with no compatibility warning. The game reaches the
   main menu. If it crashes, stop here and send the log.
2. **Codex.** Open the codex and find each new ship and weapon: the sprite shows, the text is right, and stats are
   readable. Ships: {{SHIP_LIST}}. Weapons: {{WEAPON_LIST}}.
3. **New game.** Start a campaign (any settings). Advance a few days and check that nothing errors.
4. **Refit** (`addship <variantId>` for {{VARIANT_LIST}}; `addcredits 1000000` if buying): open each in the refit
   screen. Weapon mounts sit on the hull art, the OP total is right, built-in hullmods show, and the descriptions read
   well.
5. **Simulator.** Fight each new hull against a vanilla ship of the same DP ({{SIM_MATCHUPS}}). Watch for: engine
   flames at the engines, projectiles leaving the muzzles, the ship system used sensibly by the AI, shields at the
   right size, no instant deaths or invulnerability.
6. **Fleets.** `spawnfleet {{FACTION_ID}} 100` near you. The fleet has the expected ships and loadouts, and hailing
   or fighting it works.
7. **Campaign content.** `goto {{LOCATION}}` (or fly there). Dock at each new market and try every new dialog option:
   each one leads somewhere and Back returns to the menu. Start the first quest step: {{QUEST_START}}.
8. **Save and load.** Save, quit to the menu, load the save, and check the new content is still there (intel,
   fleets, markets).
9. **Existing save** (optional): load a save made before installing the mod. The new content appears once, and
   loading again does not duplicate it.
10. **Report:** run `python tools/log_scan.py --mod .` from the mod folder (or send the log), plus anything that
    looked wrong.
