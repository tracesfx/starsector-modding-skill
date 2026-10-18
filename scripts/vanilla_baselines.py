#!/usr/bin/env python3
"""vanilla_baselines.py - vanilla stat bands for balancing new content, and a checker that compares a mod against them.

Run this BEFORE choosing any stat, and `check` after every balance change:

  python vanilla_baselines.py hulls --size DESTROYER            # p10/median/p90 of every hull stat, + example hulls
  python vanilla_baselines.py hulls --size CRUISER --tech "High Tech" --list   # one row per vanilla hull
  python vanilla_baselines.py peers --size DESTROYER --dp 12    # the vanilla hulls nearest to 12 DP
  python vanilla_baselines.py weapons --size MEDIUM --type ENERGY [--list]
  python vanilla_baselines.py wings | hullmods
  python vanilla_baselines.py check --mod path/to/MyMod [--markdown]
        every hull / weapon / wing / hullmod of the mod next to its vanilla band; OUT marks a stat outside p10-p90.
        An OUT is not automatically wrong, but each one needs a reason in BALANCE.md (a trade-off it pays for).

Notes on the columns (from ship_data.csv / weapon_data.csv; see references/balance.md):
  DP = "supplies/rec" (deployment points AND recovery cost). "fleet pts" is a separate number used by fleet
  generation. "8/6/5/4%" is unused by the engine. Weapon DPS here is sustained and approximate: damage x burst / cycle,
  where cycle = chargeup + chargedown + (burst-1) x burst delay; ammo and reload are ignored. Beams use damage/second.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sslib  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SIZES = ("FRIGATE", "DESTROYER", "CRUISER", "CAPITAL_SHIP")
HULL_STATS = [  # (key, label, csv column or callable)
    ("dp", "DP", "supplies/rec"),
    ("fp", "fleetpts", "fleet pts"),
    ("hp", "hull", "hitpoints"),
    ("armor", "armor", "armor rating"),
    ("flux", "flux cap", "max flux"),
    ("diss", "flux diss", "flux dissipation"),
    ("op", "OP", "ordnance points"),
    ("bays", "bays", "fighter bays"),
    ("speed", "speed", "max speed"),
    ("accel", "accel", "acceleration"),
    ("turn", "turn", "max turn rate"),
    ("mass", "mass", "mass"),
    ("arc", "shield arc", "shield arc"),
    ("upkeep", "shield upk", "shield upkeep"),
    ("eff", "shield eff", "shield efficiency"),
    ("peak", "peak CR s", "peak CR sec"),
    ("crday", "CR%/day", "cr %/day"),
    ("supmo", "supplies/mo", "supplies/mo"),
    ("cargo", "cargo", "cargo"),
    ("fuel", "fuel", "fuel"),
    ("fuelly", "fuel/ly", "fuel/ly"),
    ("crew", "min crew", "min crew"),
    ("burn", "burn", "max burn"),
    ("value", "base value", "base value"),
]
DERIVED = [("diss_dp", "diss/DP"), ("op_dp", "OP/DP"), ("ehp_dp", "(hull+10*armor)/DP")]
WEAPON_STATS = [("op", "OP"), ("range", "range"), ("dmg", "dmg/shot"), ("dps", "~DPS"), ("fps", "~flux/s"),
                ("fpd", "flux/dmg"), ("dps_op", "DPS/OP"), ("emp", "emp"), ("speed", "proj speed")]


def num(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def pct(vals, p):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return None
    k = (len(vals) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (k - lo)


def fmt(v):
    if v is None:
        return "-"
    if abs(v) >= 100 or float(v).is_integer():
        return "%d" % round(v)
    return "%.2f" % v if abs(v) < 10 else "%.1f" % v


def tags_of(row):
    return {t.strip() for t in (row.get("tags") or "").split(",") if t.strip()}


def hints_of(row):
    return {t.strip() for t in (row.get("hints") or "").split(",") if t.strip()}


# ----------------------------------------------------------------------------------------------------- loading
def load_hulls(data_dir, ship_files):
    """[(id, name, size, tech, stats dict)] for ship_data rows that have a .ship file with a combat hull size."""
    rows = sslib.read_csv(os.path.join(data_dir, "hulls", "ship_data.csv"))
    out = []
    for r in rows:
        hid = r["id"].strip()
        sh = ship_files.get(hid)
        if not sh or sh.get("hullSize") not in SIZES:
            continue
        st = {k: num(r.get(col)) for k, _, col in HULL_STATS}
        if r.get("shield type", "").strip() in ("NONE", "PHASE"):
            st["arc"] = st["upkeep"] = st["eff"] = None
        dp = st.get("dp") or 0
        if dp > 0:
            st["diss_dp"] = (st["diss"] or 0) / dp
            st["op_dp"] = (st["op"] or 0) / dp
            st["ehp_dp"] = ((st["hp"] or 0) + 10 * (st["armor"] or 0)) / dp
        out.append({"id": hid, "name": (r.get("name") or "").strip() or hid, "size": sh["hullSize"],
                    "tech": (r.get("tech/manufacturer") or "").strip(), "shield": r.get("shield type", "").strip(),
                    "system": r.get("system id", "").strip(), "tags": tags_of(r), "hints": hints_of(r), "st": st})
    return out


def ship_files_in(data_dir):
    out = {}
    for root, _, fs in os.walk(os.path.join(data_dir, "hulls")):
        for f in fs:
            if f.endswith(".ship"):
                try:
                    d = sslib.load_loose_json(os.path.join(root, f))
                except Exception:
                    continue
                if isinstance(d, dict) and d.get("hullId"):
                    out[d["hullId"]] = d
    return out


def is_regular_hull(h):
    """A normal combat/civilian hull a player can field: not a station/module/unboardable special, not hidden."""
    bad_hints = {"STATION", "MODULE", "HIDE_IN_CODEX", "UNBOARDABLE"}
    if h["hints"] & bad_hints:
        return False
    if h["st"].get("dp") in (None, 0):
        return False
    return True


def load_weapons(data_dir):
    rows = sslib.read_csv(os.path.join(data_dir, "weapons", "weapon_data.csv"))
    specs = {}
    for root, _, fs in os.walk(os.path.join(data_dir, "weapons")):
        for f in fs:
            if f.endswith(".wpn"):
                try:
                    d = sslib.load_loose_json(os.path.join(root, f))
                except Exception:
                    continue
                if isinstance(d, dict) and d.get("id"):
                    specs[d["id"]] = d
    out = []
    for r in rows:
        wid = r["id"].strip()
        sp = specs.get(wid)
        if not sp or sp.get("size") not in ("SMALL", "MEDIUM", "LARGE"):
            continue
        if sp.get("type") not in ("BALLISTIC", "ENERGY", "MISSILE", "HYBRID", "SYNERGY", "COMPOSITE", "UNIVERSAL"):
            continue
        op = num(r.get("OPs"))
        if op is None:
            continue
        dmg = num(r.get("damage/shot"))
        dsec = num(r.get("damage/second"))
        burst = num(r.get("burst size")) or 1
        cyc = (num(r.get("chargeup")) or 0) + (num(r.get("chargedown")) or 0) + max(0, burst - 1) * (num(r.get("burst delay")) or 0)
        beam = sp.get("specClass") == "beam"
        if beam:
            dps = dsec
            fps = num(r.get("energy/second"))
            bsz = num(r.get("burst size"))
            if bsz and dsec:  # burst beam: fires for `burst size` s, then cools down for `burst delay` s (wiki)
                bcyc = (num(r.get("chargeup")) or 0) + bsz + (num(r.get("chargedown")) or 0) + (num(r.get("burst delay")) or 0)
                if bcyc > 0:
                    dps = dsec * bsz / bcyc
                    fps = (fps or 0) * bsz / bcyc
        else:
            dps = (dmg or 0) * burst / cyc if cyc > 0 and dmg else None
            fps = (num(r.get("energy/shot")) or 0) * burst / cyc if cyc > 0 else None
        st = {"op": op, "range": num(r.get("range")), "dmg": dmg if not beam else None, "dps": dps, "fps": fps,
              "emp": num(r.get("emp")), "speed": num(r.get("proj speed"))}
        st["fpd"] = (fps / dps) if (dps and fps is not None and dps > 0) else None
        st["dps_op"] = (dps / op) if (dps and op) else None
        out.append({"id": wid, "name": (r.get("name") or "").strip() or wid, "size": sp["size"], "type": sp["type"],
                    "dtype": (r.get("type") or "").strip(), "beam": beam, "tech": (r.get("tech/manufacturer") or "").strip(),
                    "tags": tags_of(r), "hints": hints_of(r), "st": st})
    return out


def is_regular_weapon(w):
    if w["hints"] & {"SYSTEM"} or "restricted" in w["tags"] or "no_drop" in w["tags"] and "omega" in w["tags"]:
        return False
    return w["st"]["op"] is not None and w["st"]["op"] > 0


# ----------------------------------------------------------------------------------------------------- output
def band_table(items, stats, md=False):
    lines = []
    head = ["stat", "p10", "median", "p90", "min (who)", "max (who)"]
    lines.append(_row(head, md, header=True, widths=BAND_W))
    for key, label in stats:
        vals = [(it["st"].get(key), it) for it in items if it["st"].get(key) is not None]
        if not vals:
            continue
        v = [x[0] for x in vals]
        lo = min(vals, key=lambda x: x[0])
        hi = max(vals, key=lambda x: x[0])
        lines.append(_row([label, fmt(pct(v, 10)), fmt(pct(v, 50)), fmt(pct(v, 90)),
                           "%s (%s)" % (fmt(lo[0]), lo[1]["name"]), "%s (%s)" % (fmt(hi[0]), hi[1]["name"])], md,
                          widths=BAND_W))
    return lines


def _row(cells, md, header=False, widths=None):
    if md:
        s = "| " + " | ".join(str(c) for c in cells) + " |"
        if header:
            s += "\n|" + "---|" * len(cells)
        return s
    widths = widths or [20] + [9] * (len(cells) - 1)
    return " ".join(str(c).ljust(widths[i] if i < len(widths) else 9) for i, c in enumerate(cells)).rstrip()


BAND_W = [20, 8, 8, 8, 26, 26]


def list_table(items, cols, md=False):
    lines = [_row(["name"] + [c[1] for c in cols], md, header=True)]
    for it in items:
        lines.append(_row([it["name"]] + [fmt(it["st"].get(c[0])) for c in cols], md))
    return lines


def compare(item, band_items, stats, md=False, lo_p=10, hi_p=90):
    lines = []
    outs = 0
    lines.append(_row(["stat", "value", "p10", "median", "p90", "flag"], md, header=True))
    for key, label in stats:
        v = item["st"].get(key)
        vals = [it["st"].get(key) for it in band_items if it["st"].get(key) is not None]
        if v is None or not vals:
            continue
        lo, med, hi = pct(vals, lo_p), pct(vals, 50), pct(vals, hi_p)
        flag = ""
        if v < lo - 1e-9:
            flag = "OUT low"
        elif v > hi + 1e-9:
            flag = "OUT high"
        outs += bool(flag)
        lines.append(_row([label, fmt(v), fmt(lo), fmt(med), fmt(hi), flag], md))
    return lines, outs


# ----------------------------------------------------------------------------------------------------- commands
def vanilla(game):
    core = sslib.core_dir(game)
    data = os.path.join(core, "data")
    hulls = [h for h in load_hulls(data, ship_files_in(data)) if is_regular_hull(h)]
    weapons = [w for w in load_weapons(data) if is_regular_weapon(w)]
    return data, hulls, weapons


def same_role(items, hull):
    """Civilian hulls (hint CIVILIAN) are compared with civilian hulls, warships with warships."""
    civ = "CIVILIAN" in hull["hints"]
    return [i for i in items if ("CIVILIAN" in i["hints"]) == civ]


def tech_filter(items, tech):
    if not tech:
        return items
    t = tech.lower()
    return [i for i in items if t in i["tech"].lower()]


def cmd_hulls(game, a):
    _, hulls, _ = vanilla(game)
    for size in ([a.size] if a.size else SIZES):
        sel = tech_filter([h for h in hulls if h["size"] == size and ("CIVILIAN" in h["hints"]) == a.civilian], a.tech)
        if not sel:
            continue
        print("\n## %s%s %s (n=%d vanilla hulls)" % (size, " / " + a.tech if a.tech else "",
                                                   "civilian" if a.civilian else "warships", len(sel)))
        stats = [(k, l) for k, l, _ in HULL_STATS] + DERIVED
        if a.list:
            cols = [("dp", "DP"), ("hp", "hull"), ("armor", "armor"), ("flux", "flux"), ("diss", "diss"), ("op", "OP"),
                    ("speed", "speed"), ("arc", "arc"), ("eff", "eff"), ("peak", "peak CR")]
            for ln in list_table(sorted(sel, key=lambda h: h["st"]["dp"] or 0), cols, a.markdown):
                print(ln)
        else:
            for ln in band_table(sel, stats, a.markdown):
                print(ln)


def cmd_peers(game, a):
    _, hulls, _ = vanilla(game)
    sel = tech_filter([h for h in hulls if h["size"] == a.size and ("CIVILIAN" in h["hints"]) == a.civilian], a.tech)
    sel.sort(key=lambda h: (abs((h["st"]["dp"] or 0) - a.dp), h["name"]))
    cols = [("dp", "DP"), ("fp", "fleetpts"), ("hp", "hull"), ("armor", "armor"), ("flux", "flux"), ("diss", "diss"),
            ("op", "OP"), ("speed", "speed"), ("arc", "arc"), ("eff", "eff"), ("peak", "peak CR")]
    print("vanilla %s hulls nearest to %s DP:" % (a.size, fmt(a.dp)))
    for ln in list_table(sel[: a.n], cols, a.markdown):
        print(ln)
    for h in sel[: a.n]:
        print("  %-22s %-10s shield %-5s system %-18s tech %s" % (h["name"], h["id"], h["shield"], h["system"], h["tech"]))


def cmd_weapons(game, a):
    _, _, weapons = vanilla(game)
    groups = {}
    for w in weapons:
        if a.size and w["size"] != a.size:
            continue
        if a.type and w["type"] != a.type:
            continue
        groups.setdefault((w["size"], w["type"]), []).append(w)
    for (size, typ), ws in sorted(groups.items()):
        ws = tech_filter(ws, a.tech)
        if not ws:
            continue
        print("\n## %s %s  (n=%d)" % (size, typ, len(ws)))
        if a.list:
            for ln in list_table(sorted(ws, key=lambda w: w["st"]["op"]), WEAPON_STATS, a.markdown):
                print(ln)
        else:
            for ln in band_table(ws, WEAPON_STATS, a.markdown):
                print(ln)


def load_wings(data_dir, hull_rows=None):
    out = []
    for r in sslib.read_csv(os.path.join(data_dir, "hulls", "wing_data.csv")):
        st = {"op": num(r.get("op cost")), "num": num(r.get("num")), "refit": num(r.get("refit")),
              "range": num(r.get("range")), "fp": num(r.get("fleet pts"))}
        out.append({"id": r["id"].strip(), "name": r["id"].strip(), "role": (r.get("role") or "").strip(),
                    "tags": tags_of(r), "st": st})
    return out


WING_STATS = [("op", "OP"), ("num", "craft"), ("refit", "refit s"), ("range", "range"), ("fp", "fleet pts")]


def cmd_wings(game, a):
    data = os.path.join(sslib.core_dir(game), "data")
    wings = [w for w in load_wings(data) if w["st"]["op"]]
    roles = sorted({w["role"] for w in wings})
    for role in roles:
        sel = [w for w in wings if w["role"] == role]
        print("\n## role %s  (n=%d)" % (role, len(sel)))
        for ln in (list_table(sorted(sel, key=lambda w: w["st"]["op"]), WING_STATS, a.markdown) if a.list
                   else band_table(sel, WING_STATS, a.markdown)):
            print(ln)


HMOD_STATS = [("f", "frigate OP"), ("d", "destroyer OP"), ("c", "cruiser OP"), ("k", "capital OP")]


def load_hullmods(data_dir):
    out = []
    for r in sslib.read_csv(os.path.join(data_dir, "hullmods", "hull_mods.csv")):
        if (r.get("hidden") or "").strip().upper() == "TRUE":
            continue
        st = {"f": num(r.get("cost_frigate")), "d": num(r.get("cost_dest")), "c": num(r.get("cost_cruiser")),
              "k": num(r.get("cost_capital"))}
        out.append({"id": r["id"].strip(), "name": (r.get("name") or r["id"]).strip(), "tags": tags_of(r), "st": st})
    return out


def cmd_hullmods(game, a):
    data = os.path.join(sslib.core_dir(game), "data")
    hm = [h for h in load_hullmods(data) if h["st"]["k"] is not None]
    print("\n## visible vanilla hullmods (n=%d)" % len(hm))
    for ln in (list_table(sorted(hm, key=lambda h: h["st"]["k"]), HMOD_STATS, a.markdown) if a.list
               else band_table(hm, HMOD_STATS, a.markdown)):
        print(ln)


def cmd_check(game, a):
    data, hulls, weapons = vanilla(game)
    mod = os.path.abspath(a.mod)
    mdata = os.path.join(mod, "data")
    total_out = 0
    mh = []
    if os.path.isfile(os.path.join(mdata, "hulls", "ship_data.csv")):
        mships = ship_files_in(mdata)
        allships = dict(ship_files_in(data))
        allships.update(mships)
        mh = load_hulls(mdata, allships)
    for h in mh:
        band = tech_filter(same_role([v for v in hulls if v["size"] == h["size"]], h), a.tech)
        civ = "CIVILIAN" in h["hints"]
        print("\n" + "=" * 90)
        print("HULL %s (%s) %s%s  DP %s  (vs %d vanilla %s)" % (h["name"], h["id"], h["size"], " civilian" if civ else "",
                                                             fmt(h["st"]["dp"]), len(band), "civilian hulls" if civ else "warships"))
        lines, outs = compare(h, band, [(k, l) for k, l, _ in HULL_STATS if k not in ("value",)] + DERIVED, a.markdown)
        total_out += outs
        for ln in lines:
            print(ln)
        peers = sorted(band, key=lambda v: abs((v["st"]["dp"] or 0) - (h["st"]["dp"] or 0)))[:4]
        cols = [("dp", "DP"), ("hp", "hull"), ("armor", "armor"), ("flux", "flux"), ("diss", "diss"), ("op", "OP"),
                ("speed", "speed"), ("arc", "arc"), ("eff", "eff")]
        print("  nearest vanilla peers by DP:")
        for ln in list_table([h] + peers, cols, a.markdown):
            print("  " + ln)
        fp, dp = h["st"].get("fp"), h["st"].get("dp")
        if fp and dp and not (0.5 <= fp / dp <= 2.0):
            print("  note: fleet pts %s vs DP %s - vanilla keeps these close; fleet pts drive fleet generation" % (fmt(fp), fmt(dp)))
    if os.path.isfile(os.path.join(mdata, "weapons", "weapon_data.csv")):
        mw = load_weapons(mdata)
        for w in mw:
            band = [v for v in weapons if v["size"] == w["size"] and v["type"] == w["type"]]
            if len(band) < 3:
                band = [v for v in weapons if v["size"] == w["size"]]
            print("\n" + "=" * 90)
            print("WEAPON %s (%s) %s %s %s%s" % (w["name"], w["id"], w["size"], w["type"], w["dtype"], " beam" if w["beam"] else ""))
            lines, outs = compare(w, band, WEAPON_STATS, a.markdown)
            total_out += outs
            for ln in lines:
                print(ln)
            peers = sorted(band, key=lambda v: abs((v["st"]["op"] or 0) - (w["st"]["op"] or 0)))[:4]
            print("  nearest vanilla peers by OP:")
            for ln in list_table([w] + peers, WEAPON_STATS, a.markdown):
                print("  " + ln)
    if os.path.isfile(os.path.join(mdata, "hulls", "wing_data.csv")):
        vw = [w for w in load_wings(data) if w["st"]["op"]]
        for w in load_wings(mdata):
            band = [v for v in vw if v["role"] == w["role"]] or vw
            print("\n" + "=" * 90)
            print("WING %s role %s" % (w["id"], w["role"]))
            lines, outs = compare(w, band, WING_STATS, a.markdown)
            total_out += outs
            for ln in lines:
                print(ln)
    if os.path.isfile(os.path.join(mdata, "hullmods", "hull_mods.csv")):
        vh = [h for h in load_hullmods(data) if h["st"]["k"] is not None]
        for h in load_hullmods(mdata):
            print("\n" + "=" * 90)
            print("HULLMOD %s (%s)" % (h["name"], h["id"]))
            lines, outs = compare(h, vh, HMOD_STATS, a.markdown)
            total_out += outs
            for ln in lines:
                print(ln)
    print("\n%d stat(s) outside the vanilla p10-p90 band. Justify each in BALANCE.md or bring it in." % total_out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("hulls")
    p.add_argument("--size", choices=SIZES)
    p.add_argument("--tech", help='substring of tech/manufacturer, e.g. "Low Tech", "Midline", "High Tech"')
    p.add_argument("--list", action="store_true", help="one row per hull instead of bands")
    p.add_argument("--civilian", action="store_true", help="civilian hulls (hint CIVILIAN) instead of warships")
    p.set_defaults(fn=cmd_hulls)
    p = sub.add_parser("peers")
    p.add_argument("--size", choices=SIZES, required=True)
    p.add_argument("--dp", type=float, required=True)
    p.add_argument("--tech")
    p.add_argument("-n", type=int, default=6)
    p.add_argument("--civilian", action="store_true")
    p.set_defaults(fn=cmd_peers)
    p = sub.add_parser("weapons")
    p.add_argument("--size", choices=("SMALL", "MEDIUM", "LARGE"))
    p.add_argument("--type", choices=("BALLISTIC", "ENERGY", "MISSILE"))
    p.add_argument("--tech")
    p.add_argument("--list", action="store_true")
    p.set_defaults(fn=cmd_weapons)
    p = sub.add_parser("wings")
    p.add_argument("--list", action="store_true")
    p.set_defaults(fn=cmd_wings)
    p = sub.add_parser("hullmods")
    p.add_argument("--list", action="store_true")
    p.set_defaults(fn=cmd_hullmods)
    p = sub.add_parser("check")
    p.add_argument("--mod", required=True)
    p.add_argument("--tech", help="compare hulls only against this tech")
    p.set_defaults(fn=cmd_check)
    for sp in sub.choices.values():
        sp.add_argument("--markdown", action="store_true", help="markdown tables (paste into BALANCE.md)")
    a = ap.parse_args()
    a.fn(sslib.require_game_dir(a.game), a)


if __name__ == "__main__":
    main()
