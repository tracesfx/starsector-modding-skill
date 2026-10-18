#!/usr/bin/env python3
"""ssdata.py - author mod data from vanilla: exact CSV headers, cloned rows/specs, safe upserts. Import it or use the CLI.

Why: hand-typed CSV rows drift from vanilla's columns and quoting; starting every hull/weapon/system from a vanilla
peer's row keeps all ~55 columns valid and puts the stats in a balanced band from the first build.

CLI
  python ssdata.py header ship_data.csv                      # vanilla header (short names resolve to data/...)
  python ssdata.py row ship_data.csv hammerhead              # one vanilla row as JSON
  python ssdata.py spec variant hammerhead_Balanced          # a vanilla .variant/.ship/.wpn/.proj/.system/.skin by id
  python ssdata.py clone ship_data.csv hammerhead --mod MyMod --set id=mym_mallet "name=Mallet" "ordnance points=90"
  python ssdata.py merge-json MyMod data/config/settings.json '{"plugins": {"mymPlugin": "mym.combat.MymPlugin"}}'

Library (in a mod's tools/gen_data.py):
  import ssdata
  v = ssdata.Vanilla()
  row = v.clone_row("ship_data.csv", "hammerhead", id="mym_mallet", name="Mallet", **{"ordnance points": 90})
  ssdata.upsert_csv(MOD, "ship_data.csv", [row])
  var = v.spec("variant", "hammerhead_Balanced"); var.update(variantId="mym_mallet_Standard", hullId="mym_mallet")
  ssdata.write_json(os.path.join(MOD, "data/variants/mym_mallet_Standard.variant"), var)
Everything is written UTF-8 without BOM, LF line endings, minimal CSV quoting, strict JSON (4-space indent).
"""
import argparse
import copy
import csv
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sslib  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CSV_PATHS = {
    "ship_data.csv": "data/hulls/ship_data.csv",
    "wing_data.csv": "data/hulls/wing_data.csv",
    "weapon_data.csv": "data/weapons/weapon_data.csv",
    "hull_mods.csv": "data/hullmods/hull_mods.csv",
    "ship_systems.csv": "data/shipsystems/ship_systems.csv",
    "descriptions.csv": "data/strings/descriptions.csv",
    "rules.csv": "data/campaign/rules.csv",
    "commodities.csv": "data/campaign/commodities.csv",
    "market_conditions.csv": "data/campaign/market_conditions.csv",
    "industries.csv": "data/campaign/industries.csv",
    "submarkets.csv": "data/campaign/submarkets.csv",
    "special_items.csv": "data/campaign/special_items.csv",
    "abilities.csv": "data/campaign/abilities.csv",
    "factions.csv": "data/world/factions/factions.csv",
    "person_names.csv": "data/characters/person_names.csv",
}
SPEC_EXT = {"ship": (".ship", "hullId", "data/hulls"), "skin": (".skin", "skinHullId", "data/hulls"),
            "variant": (".variant", "variantId", "data/variants"), "wpn": (".wpn", "id", "data/weapons"),
            "proj": (".proj", "id", "data/weapons"), "system": (".system", "id", "data/shipsystems"),
            "faction": (".faction", "id", "data/world/factions")}


def resolve(rel):
    rel = rel.replace("\\", "/")
    return CSV_PATHS.get(rel, rel if rel.startswith("data/") else "data/" + rel)


class Vanilla:
    def __init__(self, game=None):
        self.game = sslib.require_game_dir(game)
        self.core = sslib.core_dir(self.game)
        self._rows = {}
        self._specs = {}

    def header(self, rel):
        return sslib.csv_header(os.path.join(self.core, resolve(rel)))

    def rows(self, rel, key="id"):
        rel = resolve(rel)
        if rel not in self._rows:
            self._rows[rel] = sslib.read_csv(os.path.join(self.core, rel), key=key)
        return self._rows[rel]

    def row(self, rel, rid, key="id"):
        for r in self.rows(rel, key):
            if (r.get(key) or "").strip() == rid:
                return dict(r)
        raise KeyError("no vanilla row %r in %s" % (rid, resolve(rel)))

    def clone_row(self, rel, src_id, key="id", **changes):
        """A vanilla row with changes applied. Column names with spaces/slashes: pass **{"fleet pts": 5}."""
        r = self.row(rel, src_id, key)
        hdr = self.header(rel)
        for k, v in changes.items():
            if k not in hdr:
                raise KeyError("column %r is not in %s (columns: %s)" % (k, resolve(rel), ", ".join(hdr)))
            r[k] = "" if v is None else str(v)
        return r

    def spec(self, kind, sid):
        """Deep copy of a vanilla spec JSON (.ship/.skin/.variant/.wpn/.proj/.system/.faction) found by its id."""
        ext, key, folder = SPEC_EXT[kind]
        if kind not in self._specs:
            idx = {}
            for root, _, fs in os.walk(os.path.join(self.core, folder)):
                for f in fs:
                    if f.endswith(ext):
                        p = os.path.join(root, f)
                        try:
                            d = sslib.load_loose_json(p)
                        except Exception:
                            continue
                        if isinstance(d, dict) and d.get(key):
                            idx[d[key]] = d
            self._specs[kind] = idx
        if sid not in self._specs[kind]:
            raise KeyError("no vanilla %s with %s %r" % (kind, key, sid))
        return copy.deepcopy(self._specs[kind][sid])


def _read_csv_records(path):
    """(header, records) where records are raw lists, comment rows included, to rewrite a file without losing them."""
    with open(path, encoding="utf-8-sig", newline="") as fh:
        recs = list(csv.reader(fh))
    return (recs[0], recs[1:]) if recs else ([], [])


def upsert_csv(mod_dir, rel, rows, key="id", game=None, header=None):
    """Insert or replace `rows` (dicts) in <mod_dir>/<rel>. New files get vanilla's exact header (or `header`).
    Existing rows with other ids, comment rows and extra columns are kept in place; replaced rows keep their position."""
    rel = resolve(rel)
    path = os.path.join(mod_dir, rel)
    if os.path.isfile(path):
        hdr, recs = _read_csv_records(path)
    else:
        hdr = header or Vanilla(game).header(rel)
        recs = []
    if key not in hdr:
        raise KeyError("%s has no key column %r" % (rel, key))
    ki = hdr.index(key)
    pending = {str(r[key]).strip(): r for r in rows}
    out = []
    for rec in recs:
        rid = rec[ki].strip() if ki < len(rec) else ""
        if rid in pending:
            out.append(_to_record(pending.pop(rid), hdr))
        else:
            out.append(rec)
    for r in rows:
        rid = str(r[key]).strip()
        if rid in pending:
            out.append(_to_record(pending.pop(rid), hdr))
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(hdr)
    w.writerows(out)
    sslib.write_text(path, buf.getvalue())
    return path


def _to_record(row, hdr):
    unknown = [k for k in row if k not in hdr and not k.startswith("_")]
    if unknown:
        raise KeyError("columns %s are not in the header %s" % (unknown, hdr))
    return ["" if row.get(c) is None else str(row.get(c)) for c in hdr]


def upsert_description(mod_dir, did, dtype, text1="", text2="", text3="", text4="", text5="", game=None):
    """descriptions.csv is keyed by (id, type); replace the matching row or append."""
    rel = resolve("descriptions.csv")
    path = os.path.join(mod_dir, rel)
    hdr, recs = _read_csv_records(path) if os.path.isfile(path) else (Vanilla(game).header(rel), [])
    row = {"id": did, "type": dtype, "text1": text1, "text2": text2, "text3": text3, "text4": text4, "text5": text5}
    rec = _to_record({k: v for k, v in row.items() if k in hdr}, hdr)
    ii, ti = hdr.index("id"), hdr.index("type")
    for i, r in enumerate(recs):
        if len(r) > ti and r[ii].strip() == did and r[ti].strip() == dtype:
            recs[i] = rec
            break
    else:
        recs.append(rec)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(hdr)
    w.writerows(recs)
    sslib.write_text(path, buf.getvalue())
    return path


def write_json(path, obj):
    sslib.write_json(path, obj)


def read_json(path):
    return sslib.load_loose_json(path)


def merge_json(path, patch):
    """Deep-merge `patch` into the JSON file at `path` (created if missing). Lists are extended without duplicates."""
    base = read_json(path) if os.path.isfile(path) else {}

    def merge(a, b):
        for k, v in b.items():
            if isinstance(v, dict) and isinstance(a.get(k), dict):
                merge(a[k], v)
            elif isinstance(v, list) and isinstance(a.get(k), list):
                a[k] += [x for x in v if x not in a[k]]
            else:
                a[k] = v
        return a

    write_json(path, merge(base, patch))
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("header")
    p.add_argument("csv")
    p = sub.add_parser("row")
    p.add_argument("csv")
    p.add_argument("id")
    p.add_argument("--key", default="id")
    p = sub.add_parser("spec")
    p.add_argument("kind", choices=sorted(SPEC_EXT))
    p.add_argument("id")
    p = sub.add_parser("clone")
    p.add_argument("csv")
    p.add_argument("src_id")
    p.add_argument("--mod", required=True)
    p.add_argument("--key", default="id")
    p.add_argument("--set", nargs="+", default=[], metavar="COLUMN=VALUE")
    p = sub.add_parser("merge-json")
    p.add_argument("mod")
    p.add_argument("rel")
    p.add_argument("patch", help="JSON object to deep-merge")
    a = ap.parse_args()
    if a.cmd == "merge-json":
        print("wrote", merge_json(os.path.join(a.mod, a.rel), json.loads(a.patch)))
        return
    v = Vanilla(a.game)
    if a.cmd == "header":
        print(",".join(v.header(a.csv)))
    elif a.cmd == "row":
        print(json.dumps(v.row(a.csv, a.id, a.key), indent=2))
    elif a.cmd == "spec":
        print(json.dumps(v.spec(a.kind, a.id), indent=4))
    elif a.cmd == "clone":
        changes = dict(s.split("=", 1) for s in a.set)
        row = v.clone_row(a.csv, a.src_id, a.key, **changes)
        print("wrote", upsert_csv(os.path.abspath(a.mod), a.csv, [row], key=a.key, game=a.game))


if __name__ == "__main__":
    main()
