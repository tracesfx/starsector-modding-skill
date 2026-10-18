# Ships, weapons and combat feel: lessons from a full ship-faction build

Source: building **Resonance Lattice** (`mods/ResonanceLattice`, 0.98a-RC7, 2026-10): 9 hulls + a unique capital
with an "Unsung" lesser version, a 7-part station, 3 fighter wings, 12 faction weapons, 10 ship systems, 10 hullmods,
custom FX and sounds, all generated from code and iterated with the user over ~15 feedback rounds in the game.
Everything marked **(in game)** was confirmed by the user playing; **(static)** was verified by build/validator/API
source only. Read this before making ships, weapons, ship systems or hullmods.

## 1. Workflow that worked

* **Everything generated, nothing hand-edited.** One `tools/gen_data.py` writes every csv/json/.wpn/.proj/.system/
  .variant/faction/settings/sounds/trails file and post-processes the `.ship` files the art step writes. Change the
  generator, re-run, rebuild. Every tuning request then becomes a one-line diff.
* **Patch big edits with a script file written by the Write tool**, not a shell heredoc: the Bash tool turned
  `"\\n"` into real newlines and broke Python string literals twice, and quotes/apostrophes inside heredocs broke
  the shell parse ("unexpected EOF while looking for matching"). Use `assert old in s` on every replacement.
* **The game locks the mod jar while it runs.** `build_mod.py` then fails with `PermissionError ... ResonanceLattice.jar`.
  Check `Get-Process java` and ask the user to close the game; data-only changes do not need a new jar.
* **Read starsector.log first** on any "Fatal:" dialog: `grep -n "ERROR\|Exception" -A12` near the end. The two
  crashes of this build were one-line data bugs found in seconds that way (see section 8).
* **Ask before guessing on taste and balance.** Short multiple-choice questions with a recommended option worked
  well (power level, how range is paid for, Virtuoso toughness). Visual iterations: always a review sheet next to
  vanilla peers at 1x, then change exactly what the user named.

## 2. Hulls (`.ship`, ship_data.csv)

* **DP is `supplies/rec`** (deployment cost shown in game); keep `supplies/mo` equal, as vanilla does.
* **Built-in weapons:** a slot listed in `builtInWeapons` must have `"type": "BUILT_IN"` (vanilla Onslaught TPCs).
  With a normal slot type the weapon shows as a removable 0-OP item in refit **(in game)**. Put built-ins in the
  default weapon groups too.
* **Shield radius:** the user wanted the bubble 10% beyond the sprite. Compute it: farthest opaque pixel from
  `shieldCenter` (include decorative parts at their rest angle) x 1.1; keep `collisionRadius >= shieldRadius`.
  hullgen's default (bounds + 2 px) looked too small in game **(in game)**.
* **Unique ship with a lesser version:** a full second hull (own `.ship`, derived from the main one by the
  generator) was simpler than a `.skin` once the two needed different slots, systems and built-ins. Show the locked
  feature as its own built-in hullmod ("Bravura (Silent)": struck-through icon, red INACTIVE heading via
  `addPostDescriptionSection`) so the player sees what the upgrade unlocks.
* **Stations:** size them by the *whole footprint* (core + modules on their slots), not the core sprite: vanilla
  `station2` reaches ~563 px from its centre. Balance against the matching vanilla station: clone the core from
  `station3_hightech` etc. and each module from the vanilla module of the same role (citadel / shield / hangar);
  vanilla modules carry 1,000 OP and 0.6-efficiency fortress shields. `vanilla_baselines.py check` compares
  stations and modules to warships, so their OUT flags are expected.
* **Fighters:** vanilla fighter hulls have 0 OP and 0 supplies (the validator now knows); weapons go in `HIDDEN`
  slots; the variant needs `"hullMods": ["no_weapon_flux"]` like vanilla; `wing_data.csv` rows cloned from a peer
  wing (`thunder_wing` interceptor, `broadsword_wing` heavy fighter, `dagger_wing` bomber). Fighter-only guns use
  their own weapon ids (tag them hidden), borrowing an existing sprite.
* **Variant generator order:** a function that `rmtree`s `data/variants/<mod>` must run before anything else
  writes variants there (the fighter variants vanished once).

## 3. Decorative moving parts

* A deco weapon on a **HARDPOINT** mount is drawn a quarter of its sprite length *forward* of the slot; vanes
  designed to pivot on their centre looked detached in refit and in combat **(in game)**. Use **TURRET** mounts
  for parts that pivot on the sprite centre.
* Animate with an `EveryFrameWeaponEffectPlugin` that sets `weapon.setCurrAngle(ship.getFacing() + angle)`; give
  the slot `arc` 360 so nothing clamps it. The game never mirrors deco sprites: asymmetric L/R parts need two
  sprites.

## 4. Glow, overlays and afterimages

* **A `CombatLayeredRenderingPlugin` drawn in a ship's own layer (CAPITAL_SHIPS_LAYER...) did not show** - it is
  most likely drawn before the hull sprite **(in game)**. Draw hull overlays in `BELOW_PHASED_SHIPS_LAYER` (after
  every hull layer; side effect: the glow draws over overlapping ships). Register sprites in settings.json
  `"graphics": {"<category>": {key: path}}` so they load, fetch with `getSpriteName(category, key)`.
* Give glow a visible floor (40% at zero Resonance); 15% was invisible.
* **`ShipAPI.addAfterimage` did not behave as expected** (images flew off with a compensating velocity, vanished with
  none). A small renderer of our own is reliable: store (x, y, facing, time) snapshots, draw the hull sprite
  (`getSprite(hullSpec.getSpriteName())`, centre from `ship.getSpriteAPI().getCenterX/Y()`) additively in
  `UNDER_SHIPS_LAYER`, tinted, alpha fading.
* Shield colour per state: `ShieldAPI.setInnerColor/setRingColor`; capture the originals once and lerp.
* **A state change the player must feel** (user wanted "the gleams glowing very vibrantly for a bit then cooling off,
  paired with a noise"): keep a 0..1 flare value per ship, set it to 1 on the transition and decay it over ~2.5 s in
  the renderer's `advance`; draw the seam sprite additively up to 3 extra times with alpha `k*k` (stacked passes
  saturate the seams to solid light, which one pass at alpha 1 cannot), plus a shockwave ring of `addHitParticle`
  motes, a callout (`addFloatingText`) and a sound. Leaving the state gets its own, cooler flare.
  **`ShipAPI.setJitter/setJitterUnder` last one frame**: call them every frame while the effect runs (a single call
  from the transition does nothing visible). Skip the fanfare when the ship merely deploys in that state
  (`ship.getFullTimeDeployed() < 1`).

## 5. Weapons, projectiles, pierce

* **Rail look:** `BALLISTIC_AS_BEAM` projectiles (long `length`, thin `width`, white `coreColor`, coloured
  `fringeColor`, `glowRadius` + alpha for the head glow, `hitGlowRadius` for the engine's impact glow). The user
  tuned these in small steps ("width 10", "head glow -20%"): expose each as a generator parameter.
* **Pierce through a hull** (no projectile can ignore a hull it hits): in `onHit`, spawn a continuation with
  `engine.spawnProjectile(source, weapon, weaponId, point + 4 px forward, facing, null)`, copy the damage,
  `addDamagedAlready(target)`, tag it. Spawning at the *exit* point looked like a teleport; spawn at the impact
  point so it visibly bores through. Damage inside the hull: a small plugin follows the slug while
  `target.isPointInBounds(loc)` and applies a fixed budget split over steps (the user balanced it as +40% of the
  shot for destroyers, +80% for capitals). Cap the chain (the user chose 12 ships).
* **A spawned continuation gets a fresh full range** **(in game)**: store the original firing point and
  `weapon.getRange()` in custom data, pass them on, remove the projectile once it has travelled that far.
* **The slug head rendered inside the shield** after a shield hit: `engine.removeEntity(proj)` in `onHit` when
  `shieldHit`.
* Never call `engine.removeEntity` while iterating `engine.getProjectiles()`: collect, remove after the loop.
* **Projectile colours per ship state** (e.g. teal normally, white in an overdrive): colours live in the shared
  `.proj` spec, so make an identical twin weapon (`tags: SYSTEM`, own `.proj` with the other colours and its own trail
  rows) and give the real weapon an `onFireEffect` that, in that state, spawns the twin
  (`engine.spawnProjectile(ship, weapon, twinId, proj.getLocation(), proj.getFacing(), ship.getVelocity())`: passing
  the real `weapon` keeps `getWeapon()` = the real lance for on-hit logic), copies `getDamageAmount()`, holds it to
  the real weapon's `getRange()` (the twin's own range is only an upper bound) and removes the original. Pierce
  continuations must re-spawn as the twin too (pick the id from `getProjectileSpecId()`). **Unverified in game.**
* `"barrelMode": "LINKED"` with several barrels is rare in vanilla (one weapon) and DPS tools count it as one shot;
  use explicit `burst size` instead when the numbers must be predictable.
* **Faction-wide range bonus** for "our weapons only": a `WeaponBaseRangeModifier` listener added in
  `applyEffectsAfterShipCreation` that returns a flat bonus for weapon ids with the mod prefix (works in refit too).

## 6. Trails (MagicLib) and impact effects

* `data/config/modFiles/magicTrail_data.csv` gives trails with no code. Copy MagicLib's own header exactly; sprites
  are ids from MagicLib's `fx` graphics category (`base_trail_smooth`, `_fuzzy`, `_smoke`, ...).
* **Colours must be written `[210,255,250]` with no spaces** - MagicLib parses each item with `Integer.parseInt`
  and the game crashed at launch with `For input string: " 255"` (validator now errors on it).
* Trails render in `BELOW_INDICATORS_LAYER` (above ships) unless `renderBelowExplosions`. The `distance` column
  (offset behind the head) left a visible gap where a piercing slug was replaced: use 0 for pierce weapons.
* Fast slugs lay ~40 px segments per frame and the haze looks angular; noise hides it: `dispersion`,
  `velocityOut`, `randomVelocity` ~0.9, `randomRotation` with `rotationIn/Out`, a scrolling smoke texture.
* Impact effects: the user found big hit flashes overpowering ("the entire thing is just a large circle of light");
  the final values were roughly a third of the first attempt. Scale particles with sqrt(damage) and keep the hit
  flash small for piercing guns so the pierce stays readable.

## 7. Sounds

* **Synthesised "musical" sounds were rejected** ("feel like a musical instrument, not an energy weapon", "out of
  place compared to Starsector's native sounds"). What the user accepted: **processed derivatives of the vanilla
  weapon sounds** the guns used before - ffmpeg `asetrate=44100*p,aresample=44100` (game-style pitch), `amix` of two
  vanilla shots (railgun crack + ion/pulse zap = "energy rail"), a quiet octave-up copy for shimmer, `flanger` /
  `aphaser` / `chorus`, a short `aecho` slap-back; two-pass peak normalisation (`volumedetect`, then `volume`).
  Then set each `sounds.json` volume near the vanilla source's. Pushing pitch/effects further was requested later:
  start bolder than you think.
* `sounds.json`: `"id": [{"file": "sounds/<mod>/x.ogg", "pitch": 1, "volume": 0.6}, ...]`; several entries = random
  variation (same file at 0.97/1.0/1.03 pitch works). Mono 44.1 kHz Vorbis. The engine already plays hit sounds
  per damage type; custom impact sounds were redundant.

## 8. Hullmods, S-mods and tooltips

* **`hull_mods.csv` `desc`, `short` and `sModDesc` go through `String.format`.** A bare `%` ("at 100% extends")
  crashed the refit screen and the codex with `IllegalFormatConversionException: e != java.lang.String`
  **(in game)**. Write `%%`, or put the number in a `%s` param (validator now errors on it).
* **Readable tooltips (user request):** keep the csv `desc` to one or two plain sentences and build the details in
  `addPostDescriptionSection`: `addSectionHeading(title, Alignment.MID, 10f)`, `setBulletedListMode("  - ")`,
  `addPara(format, 3f, Misc.getHighlightColor(), params...)`, negative colour for costs, `setBulletedListMode(null)`
  at the end.
* **S-mods follow vanilla's rule:** cheap hullmods get a bonus when built in with a story point, expensive ones a
  penalty (`isSModEffectAPenalty()`), and *enhancing a hull's own built-in* (nearly free) should give the strongest
  bonus. Text = `sModDesc` column + `getSModDescriptionParam`; the game draws the "S-mod bonus/penalty" section.
  In code: `variant.getSMods()` (installed then story-pointed) vs `variant.getSModdedBuiltIns()` (enhanced
  built-ins); `BaseHullMod.isSMod()` is true for both. Effects that live in other classes check the variant sets.
* **MagicUI status bars:** the keyless `drawInterfaceStatusBar(ship, fill, ...)` keys the bar by its *label*:
  changing the label ("RESONANCE" -> "OVERTONE") drew a second bar **(in game)**. Use the overload with an explicit
  key.
* Hullmod icons: vanilla's are full-bleed 32x32 paintings (close-up machinery or an effect, side light, glow,
  dark vignette, no frame). Flat framed glyphs looked out of place; crops of the mod's own 4x hull renders,
  darkened, tinted, lit and with the mechanic painted on as light, matched well.

## 9. Descriptions (descriptions.csv)

* Real newlines inside a quoted field make paragraphs; vanilla ship texts use two or three short paragraphs.
* `SHIP_SYSTEM`: `text1` = description, `text2` = category ("Movement", "Defensive", "Offensive", "Special"),
  `text3` = one-line summary. Systems without text2/text3 look unfinished next to vanilla.
* A good ship text: one lore paragraph, then "In battle:" (role, system, built-ins in plain words).

## 10. Ship systems and per-ship mechanics

* **Dash/blink** (`STAT_MOD` + custom script): move by adding to `ship.getLocation()` each frame on top of the
  ship's own velocity (so the pilot keeps control), invulnerable via `get*DamageTakenMult().modifyMult(id, 0)`,
  `setCollisionClass(NONE)` while dashing. To let the player change direction mid-dash, steer the dash heading
  towards the velocity direction at a capped rate and multiply acceleration/turn rates during the dash.
* **Charges that change with a state** (3 in a buff state, 2 otherwise): give the `.system` the maximum and hold the
  last one back (`setAmmo` clamp + `setAmmoReloadProgress(0)`) outside the state.
* **CR as a resource** (CR cost per use, CR stolen from targets, refund on kills): `ship.setCurrentCR()`; detect a
  kill in a `DamageListener` (`target.getHitpoints() <= 0 || isHulk()`, once per target via custom data).
* Hull regeneration: `ship.setHitpoints(min(max, hp + max * rate * amount))` in `advanceInCombat`.

## 11. Balance, as the user judged it

* Target "slightly above vanilla per DP". Long range is the faction edge, paid for with ~15% less sustained DPS and
  slightly worse flux efficiency than vanilla peers; point defence stays short-ranged so it still works.
* A unique capital's power should come from its kit, not raw stats (the Ziggurat model): the user kept armor light,
  raised hull moderately and added regeneration instead of toughness.
* Re-run `vanilla_baselines.py check --mod .` after every balance pass and write the before/after table into
  BALANCE.md.
