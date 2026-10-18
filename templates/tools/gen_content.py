#!/usr/bin/env python3
"""gen_content.py - example content generator: one complete, validating slice of mod content from code.

Copy it into your mod's tools/ folder and adapt it. Re-run it after every change: it overwrites exactly what it
generates and nothing else. It writes:
  * a procedural frigate sprite + its .ship (hullgen), a ship_data.csv row cloned from a vanilla peer, a variant
    that fits the generated slots and stays inside the OP budget, and a SHIP description
  * a small ballistic weapon: procedural turret/hardpoint sprites (weapongen), a .wpn cloned from vanilla lightac with
    the new sprites and muzzle offsets, a weapon_data.csv row, and a WEAPON description
  * default_ship_roles.json so factions can field the variant
  * a new faction (cloned from vanilla independent, listed in factions.csv) that knows the hull and weapon
  * a patch making the vanilla independents know them too (the partial-faction-file pattern)
  * a market menu option for the faction's markets, with handlers that return to the market menu (rules.csv)

    python gen_content.py --mod path/to/MyMod          (default: the mod at/above the current folder)
Needs the skill's scripts (ssdata, hullgen, weapongen): set SS_SKILL_SCRIPTS if they are not in
~/.claude/skills/starsector-modding/scripts.
"""
import argparse
import os
import sys

SCRIPTS = os.environ.get("SS_SKILL_SCRIPTS") or os.path.join(os.path.expanduser("~"), ".claude", "skills",
                                                             "starsector-modding", "scripts")
sys.path.insert(0, SCRIPTS)
import hullgen  # noqa: E402
import ssdata  # noqa: E402
import sslib  # noqa: E402
import weapongen  # noqa: E402

PEER_HULL = {"lowtech": "lasher", "midline": "vigilance", "hightech": "wolf"}  # vanilla frigate peers by style


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mod")
    ap.add_argument("--style", choices=sorted(PEER_HULL), default="midline")
    a = ap.parse_args()
    mod = sslib.find_mod_root(a.mod or os.getcwd())
    if not mod:
        sys.exit("no mod_info.json at or above %s" % (a.mod or os.getcwd()))
    cfg_p = os.path.join(mod, "tools", "validate_config.json")
    prefix = sslib.load_loose_json(cfg_p).get("prefix") if os.path.isfile(cfg_p) else None
    if not prefix:
        sys.exit("set \"prefix\" in tools/validate_config.json first")
    v = ssdata.Vanilla()
    P = prefix
    faction_id = P + "faction"
    hull_id = P + "warden"
    variant_id = hull_id + "_Standard"
    weapon_id = P + "lancet"
    bp_tag = P + "bp"

    # ---------------------------------------------------------------- hull: sprite + .ship from one spec
    spec = hullgen.example_spec("frigate")
    spec.update(id=hull_id, name="Warden", style=a.style)
    hullgen.generate(spec, out_dir=mod, quiet=True)
    ship = sslib.load_loose_json(os.path.join(mod, "data", "hulls", hull_id + ".ship"))
    peer = PEER_HULL[a.style]
    row = v.clone_row("ship_data.csv", peer, id=hull_id, name="Warden", designation="Frigate",
                      **{"tech/manufacturer": "Warden Yards", "codex variant id": variant_id, "tags": bp_tag,
                         "number": ""})
    ssdata.upsert_csv(mod, "ship_data.csv", [row])
    ssdata.upsert_description(mod, hull_id, "SHIP",
                              text1="A picket frigate built from salvage-yard tooling. It is slow to turn and hard "
                                    "to kill, and its crews treat it with more affection than it deserves.")

    # ---------------------------------------------------------------- weapon: sprites + .wpn + csv row
    out = {}
    for mount, key in (("TURRET", "turret"), ("HARDPOINT", "hardpoint")):
        kit, muzzles = weapongen.compose("cannon", "SMALL", mount, 1, 0, a.style, seed=3, variant=1)
        im = kit.finish()
        rel = "graphics/weapons/%s_%s.png" % (weapon_id, key)
        os.makedirs(os.path.join(mod, "graphics", "weapons"), exist_ok=True)
        im.save(os.path.join(mod, rel))
        offs, angs = weapongen.offsets(muzzles, im.height)
        out[key] = (rel, offs, angs)
    wpn = v.spec("wpn", "lightac")
    for k in ("turretGunSprite", "hardpointGunSprite", "turretGlowSprite", "hardpointGlowSprite",
              "turretUnderSprite", "hardpointUnderSprite"):
        wpn.pop(k, None)  # vanilla extra layers would draw lightac's barrel over the new art
    wpn["visualRecoil"] = 0
    wpn["id"] = weapon_id
    for key in ("turret", "hardpoint"):
        rel, offs, angs = out[key]
        wpn[key + "Sprite"] = rel
        wpn[key + "Offsets"] = offs
        wpn[key + "AngleOffsets"] = angs
    ssdata.write_json(os.path.join(mod, "data", "weapons", weapon_id + ".wpn"), wpn)
    wrow = v.clone_row("weapon_data.csv", "lightac", id=weapon_id, name="Lancet Autocannon",
                       tags="kinetic6, " + bp_tag, number="")
    ssdata.upsert_csv(mod, "weapon_data.csv", [wrow])
    ssdata.upsert_description(mod, weapon_id, "WEAPON",
                              text1="A short-barrelled autocannon that trades range for a fast, steady rate of fire.")

    # ---------------------------------------------------------------- variant: fill the generated slots
    hull_op = float(row["ordnance points"])
    fill = {("BALLISTIC", "SMALL"): weapon_id, ("ENERGY", "SMALL"): "pdlaser", ("MISSILE", "SMALL"): "harpoon",
            ("HYBRID", "SMALL"): weapon_id, ("COMPOSITE", "SMALL"): weapon_id, ("SYNERGY", "SMALL"): "pdlaser",
            ("UNIVERSAL", "SMALL"): weapon_id}
    groups, op = {}, 0.0
    for s in ship.get("weaponSlots", []):
        wid = fill.get((s["type"], s["size"]))
        if not wid or s.get("mount") == "HIDDEN":
            continue
        cost = float((wrow if wid == weapon_id else v.row("weapon_data.csv", wid))["OPs"])
        if op + cost > hull_op:
            continue
        op += cost
        groups.setdefault(wid, {})[s["id"]] = wid
    vents = int(min(10, hull_op - op))              # 1 OP each, max 10 on a frigate (CoreAutofitPlugin.getBaseMax)
    caps = int(min(10, hull_op - op - vents))
    op += vents + caps
    variant = {"variantId": variant_id, "hullId": hull_id, "displayName": "Standard", "goalVariant": True,
               "quality": 0.5, "fluxVents": vents, "fluxCapacitors": caps, "hullMods": [], "permaMods": [], "sMods": [],
               "wings": [],
               "weaponGroups": [{"mode": "LINKED", "autofire": i > 0, "weapons": ws} for i, ws in enumerate(groups.values())]}
    ssdata.write_json(os.path.join(mod, "data", "variants", variant_id + ".variant"), variant)
    ssdata.merge_json(os.path.join(mod, "data", "world", "factions", "default_ship_roles.json"),
                      {"combatSmall": {variant_id: 10}})

    # ---------------------------------------------------------------- faction: new one + patch of a vanilla one
    fac = v.spec("faction", "independent")
    fac.update(id=faction_id, displayName="Warden Yards", displayNameWithArticle="the Warden Yards",
               displayNameLong="Warden Yards", displayNameLongWithArticle="the Warden Yards",
               color=[150, 190, 120, 255])
    fac["knownShips"] = {"tags": ["base_bp", bp_tag], "hulls": [hull_id]}
    fac["knownWeapons"] = {"tags": ["base_bp", bp_tag, "midline_bp"], "weapons": [weapon_id]}
    for k in ("priorityShips", "priorityWeapons", "shipSellFrequency", "weaponSellFrequency", "fighterSellFrequency",
              "hullmodSellFrequency", "variantOverrides"):
        fac.pop(k, None)  # independent-specific tuning; add your own deliberately
    ssdata.write_json(os.path.join(mod, "data", "world", "factions", faction_id + ".faction"), fac)
    ssdata.upsert_csv(mod, "factions.csv", [{"faction": "data/world/factions/%s.faction" % faction_id}], key="faction")
    ssdata.upsert_description(mod, faction_id, "FACTION",
                              text1="A guild of salvage yards that builds pickets out of whatever the Collapse left behind.")
    ssdata.merge_json(os.path.join(mod, "data", "world", "factions", "independent.faction"),
                      {"knownShips": {"hulls": [hull_id]}, "knownWeapons": {"weapons": [weapon_id]}})

    # ---------------------------------------------------------------- rules: a market menu option and its handlers
    rules = [
        {"id": P + "office_option", "trigger": "PopulateOptions",
         "conditions": "$hasMarket\n$menuState == main\n$faction.id == " + faction_id,
         "script": "", "text": "", "options": "50:%soffice_visit:Visit the yard office" % P, "notes": ""},
        {"id": P + "office_visit", "trigger": "DialogOptionSelected", "conditions": "$option == %soffice_visit" % P,
         "script": "", "text": "A clerk looks up from a stack of hull certificates. \"Pickets are booked through the "
                               "end of the cycle,\" she says, without asking what you came for.",
         "options": "%soffice_back:Back" % P, "notes": ""},
        {"id": P + "office_back", "trigger": "DialogOptionSelected", "conditions": "$option == %soffice_back" % P,
         "script": "FireAll PopulateOptions", "text": "", "options": "", "notes": ""},
    ]
    ssdata.upsert_csv(mod, "rules.csv", rules)
    print("generated: hull %s, variant %s (%.0f/%.0f OP incl. %d vents, %d caps), weapon %s, faction %s, 3 rules" % (
        hull_id, variant_id, op, hull_op, vents, caps, weapon_id, faction_id))


if __name__ == "__main__":
    main()
