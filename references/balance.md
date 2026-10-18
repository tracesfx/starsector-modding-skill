# Balance: fitting new content into vanilla's power curve

All numbers below come from `scripts/vanilla_baselines.py` on 0.98a-RC7. Warships exclude civilian hulls (hint
CIVILIAN), stations, modules and hidden hulls. Weapons exclude fighter, system and special-faction weapons (Omega,
Threat, Dweller): 87 regular weapons. Re-run the script rather than trusting this page after a game update.

## Workflow (do this, in this order)

1. **Before choosing any stat:** `vanilla_baselines.py hulls --size DESTROYER` (bands) and
   `vanilla_baselines.py peers --size DESTROYER --dp 12` (the closest vanilla hulls). Start each new hull as a clone of
   its nearest peer's row (`ssdata.py clone ship_data.csv <peer> ...`) and change only what the design calls for.
2. **Give every ship and weapon one trade-off**, not just bigger numbers: if something is above the band, something
   else must be below it.
3. **After every balance change:** `vanilla_baselines.py check --mod MyMod --markdown`. Each `OUT` needs a
   one-line justification in BALANCE.md (the trade-off it pays for), or bring it into the band. Paste the
   peer tables into BALANCE.md.
4. Balance on paper is not balance in play: list sim matchups for the human tester (`templates/SMOKE_TEST.md`).

Last session's first pass, done from memory, underpriced a capital (32 instead of 36 DP), undertuned two weapons
and gave a frigate too little OP. The tables caught all of it.

## What the columns mean (and common misreadings)

* **DP is `supplies/rec`**: deployment points, recovery cost, and (usually equal) `supplies/mo`. **`fleet pts`** is
  a separate strength value used to build AI fleets. Vanilla cruisers have about 20 DP but about 14 fleet points,
  so do not set them equal by habit. `vanilla_baselines.py check` notes a fleet pts/DP ratio outside 0.5-2.
* **`8/6/5/4%` is unused** by the engine **(wiki)**. Fill it consistently, but do not reason from it.
* **Shield efficiency** is flux per point of damage blocked: **lower is better** (0.6 is excellent, 1.2 poor).
  Upkeep is a fraction of dissipation spent while shields are up.
* **Flux economy:** sustained firing costs weapon flux/s. A ship can fire everything indefinitely only if the
  weapons' total flux/s is at most its dissipation. Vanilla destroyers dissipate about 24 per DP, capitals about 15.
* **Weapon flux/damage** (flux per point of damage): ballistic and energy weapons sit around 0.7-1.0; beams are
  cheaper; missiles cost no flux but are ammo-limited. **DPS here is sustained and approximate:**
  damage x burst / (chargeup + chargedown + (burst - 1) x burst delay). Burst beams fire for `burst size` seconds,
  then cool down for `burst delay`. Ammo and reload are ignored.
* **OP budget**: hull OP covers weapons, non-built-in hullmods (`cost_frigate/dest/cruiser/capital`), wings,
  vents and capacitors (1 OP each, max 10/20/30/50 by size). Built-in hullmods and s-mods cost nothing.
  Vanilla gives about 9 OP per DP on frigates and destroyers and about 7 on cruisers and capitals.

## Vanilla warship bands: median (p10-p90)

| Size (n) | DP | fleet pts | hull | armor | flux cap | diss | OP | speed | shield eff | peak CR s | diss/DP | OP/DP |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Frigate (19) | 5 (3-8.8) | 6 (3.8-10.8) | 1750 (1140-2500) | 250 (150-460) | 2250 (1240-3200) | 160 (100-320) | 50 (29-56) | 120 (90-168) | 0.80 (0.60-0.96) | 240 (180-300) | 33.3 (24.8-40.8) | 9 (4.9-12.9) |
| Destroyer (12) | 10 (7.1-12) | 10 (9-12) | 4375 (2820-5450) | 450 (250-740) | 4100 (2295-5940) | 238 (114-490) | 87.5 (71-104) | 80 (60-100) | 0.90 (0.69-1.20) | 360 (300-420) | 23.6 (18.8-42.7) | 9.5 (5.4-12.1) |
| Cruiser (17) | 20 (12-27) | 14 (9.6-16.4) | 8000 (6000-10400) | 800 (600-1250) | 9000 (3700-11400) | 500 (192-740) | 140 (82-167) | 60 (43-80) | 0.80 (0.64-1.0) | 480 (420-540) | 22.5 (13-35) | 6.9 (5.3-8.6) |
| Capital (13) | 45 (31-60) | 28 (20-34) | 15000 (10000-28000) | 1500 (820-1730) | 15000 (10800-24000) | 600 (460-1200) | 300 (240-364) | 35 (26-66) | 1.0 (0.69-1.22) | 720 (600-720) | 15 (10-21.9) | 7.3 (4.3-8.9) |

Civilian hulls have their own bands: `vanilla_baselines.py hulls --civilian`. By tech: add `--tech "High Tech"`.

## Vanilla weapon bands: median (p10-p90)

| Weapon (n) | OP | range | ~DPS | ~flux/s | flux/dmg | DPS/OP |
|---|---|---|---|---|---|---|
| Small Ballistic (10) | 4.5 (2.9-7.1) | 650 (295-830) | 158 (98-510) | 65 (17-151) | 0.73 (0.04-0.91) | 34.8 (23.3-127) |
| Small Energy (8) | 4.5 (2.4-6.9) | 500 (470-860) | 75 (44-158) | 60 (24-128) | 0.70 (0.47-1.11) | 21.9 (11.2-30) |
| Small Missile (15) | 3 (1.4-4) | 1200 (1200-2300) | ammo-limited | 0 | 0 | - |
| Medium Ballistic (11) | 10 (7-13) | 700 (450-1000) | 220 (138-500) | 175 (120-333) | 0.80 (0.25-1.0) | 25 (10.6-50) |
| Medium Energy (10) | 10 (8.9-12) | 600 (500-1000) | 275 (95-910) | 201 (133-1050) | 0.96 (0.63-1.65) | 28.5 (10.4-83.6) |
| Medium Missile (12) | 10 (6.1-10) | 1500 (1200-2450) | ammo-limited | 0 | 0 | - |
| Large Ballistic (7) | 20 (17.2-26.2) | 900 (820-1020) | 480 (309-748) | 440 (274-680) | 1.0 (0.62-1.44) | 22.2 (15-31.7) |
| Large Energy (6) | 22.5 (19-27.5) | 725 (700-1000) | 583 (240-1125) | 354 (192-1038) | 0.82 (0.47-1.22) | 25 (9.6-56) |
| Large Missile (8) | 20 (15.4-25.3) | 2250 (1200-2950) | ammo-limited | 0 | 0 | - |

Damage type changes value (from the `DamageType` enum): kinetic 200% vs shields and 50% vs armour, high explosive
the reverse, fragmentation 25% vs shields and armour but 100% vs hull, energy 100% everywhere. Compare a new weapon
with peers of the same damage type and role (PD, strike, anti-shield, anti-armour).

**Hullmod costs** (62 visible vanilla hullmods), frigate / destroyer / cruiser / capital: 4 / 8 / 12 / 20 medians
(p10-p90: 3-8 / 5-15 / 8-20 / 10-30). Price a new hullmod by its closest vanilla counterpart's costs.

**Wings:** `vanilla_baselines.py wings` gives OP cost, craft count, refit time and range per role (bomber OP median
12, refit about 18 s).

## Making things distinct without breaking them

* A ship system or built-in hullmod is the usual place for identity. Price strong systems through DP, flux
  dissipation or a slot penalty, not by ignoring them.
* Debuffs that stack (several ships applying the same effect) must cap or refresh, not multiply. Last session's
  combat ledger capped stacking. Check the stacked case explicitly.
* Range is the most dangerous stat: a weapon outranging its peers by more than about 20% changes how the AI fights.
  Pay for range with DPS or flux.
* Fighters and missiles: watch DPS per OP and ammo; low-OP strike weapons that out-damage vanilla dominate quickly.

## Economy guardrails

* Generated markets: copy the vanilla recipe (`templates/java/WorldGen.java`). Set the tariff with
  `modifyFlat("default_tariff", faction.getTariffFraction())` as vanilla's Galatia.java does.
* New commodities and items: compare `base price` with vanilla's `commodities.csv` and `special_items.csv`. Check
  that nothing can be bought below what another market (or a quest reward) pays for it, so there is no money loop.
* Quest rewards: in the range of vanilla mission and bounty rewards at the same stage of a run. Do not let a
  repeatable action pay out without a cooldown (use expiring memory flags).
* Industries: compare `income`/`upkeep` columns with vanilla's `industries.csv`; custom production must not create
  a commodity from nothing at a profit.
