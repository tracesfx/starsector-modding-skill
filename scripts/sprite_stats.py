#!/usr/bin/env python3
"""sprite_stats.py - measure sprites and compare them with vanilla hulls of the same tech style.

    python sprite_stats.py my_ship.png other.png --tech midline
    python sprite_stats.py --mod path/to/MyMod          # every hull sprite in the mod, each vs its .ship style's tech
    python sprite_stats.py --vanilla-table              # print the vanilla reference table

Metrics (opaque pixels, measured at 1x):
  lum_mean / lum_p5 / lum_p95   tonal range. Vanilla p5~0.10-0.13, p95~0.75-0.83
  sat_mean                      saturation. Vanilla low tech 0.30, midline 0.18, high tech 0.13
  edge_density                  share of interior pixels with a luminance step > 0.08. Vanilla ~0.6 (dense detail)
  hf_energy                     mean |pixel - 3x3 mean| luminance. Vanilla ~0.085-0.095
  rim_ratio                     silhouette-rim luminance / interior luminance. Vanilla ~0.58-0.64 (dark rim)
A row is flagged when it is outside the vanilla band (p10-p90 over that tech's hulls).
Weapon sprites have their own targets (weapongen.py --check prints them).
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sslib  # noqa: E402

TECH_NAMES = {"lowtech": "Low Tech", "midline": "Midline", "hightech": "High Tech"}
KEYS = ["lum_mean", "lum_p5", "lum_p95", "sat_mean", "edge_density", "hf_energy", "rim_ratio"]


def measure(img):
    a = np.asarray(img.convert("RGBA")).astype(np.float32) / 255.0
    alpha = a[..., 3]
    m = alpha > 0.9
    if m.sum() < 50:
        return None
    rgb = a[..., :3]
    lum = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    mx, mn = rgb.max(axis=2), rgb.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    interior = m.copy()
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (2, 0), (-2, 0), (0, 2), (0, -2)):
        interior &= np.roll(np.roll(m, dy, 0), dx, 1)
    rim = m & ~interior
    gy, gx = np.gradient(lum)
    grad = np.hypot(gx, gy)
    pad = np.pad(lum, 1, mode="edge")
    blur = sum(pad[i:i + lum.shape[0], j:j + lum.shape[1]] for i in range(3) for j in range(3)) / 9.0
    hf = np.abs(lum - blur)
    out = dict(
        lum_mean=float(lum[m].mean()),
        lum_p5=float(np.percentile(lum[m], 5)),
        lum_p95=float(np.percentile(lum[m], 95)),
        sat_mean=float(sat[m].mean()),
        edge_density=float((grad[interior] > 0.08).mean()) if interior.any() else 0.0,
        hf_energy=float(hf[interior].mean()) if interior.any() else 0.0,
        rim_ratio=float(lum[rim].mean() / max(1e-6, lum[interior].mean())) if interior.any() and rim.any() else 1.0,
    )
    return out


def vanilla_table(game, cache=None):
    """{tech: {metric: (p10, median, p90)}} over vanilla non-fighter hulls, cached per game version in
    ~/.cache/starsector-modding/<version>/ (SS_CACHE overrides the base folder)."""
    base = os.environ.get("SS_CACHE") or os.path.join(os.path.expanduser("~"), ".cache", "starsector-modding")
    cache = cache or os.path.join(base, sslib.game_version(game) or "unknown", "vanilla_sprite_stats.json")
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    if os.path.exists(cache):
        try:
            return json.load(open(cache))
        except Exception:
            pass
    core = sslib.core_dir(game)
    tech = {r["id"]: (r.get("tech/manufacturer") or "").strip()
            for r in sslib.read_csv(os.path.join(core, "data", "hulls", "ship_data.csv"))}
    groups = {}
    for hid, (d, _p) in sslib.vanilla_hulls(game).items():
        if d.get("hullSize") in (None, "FIGHTER") or "module" in hid or "station" in hid:
            continue
        t = tech.get(hid, "")
        if t not in TECH_NAMES.values():
            continue
        p = os.path.join(core, d.get("spriteName", ""))
        if not os.path.isfile(p):
            continue
        s = measure(Image.open(p))
        if s:
            groups.setdefault(t, []).append(s)
    table = {}
    for t, L in groups.items():
        table[t] = {k: [float(np.percentile([x[k] for x in L], q)) for q in (10, 50, 90)] for k in KEYS}
        table[t]["n"] = len(L)
    try:
        json.dump(table, open(cache, "w"), indent=1)
    except OSError:
        pass
    return table


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sprites", nargs="*")
    ap.add_argument("--mod", help="measure every hull sprite referenced by the mod's .ship files")
    ap.add_argument("--tech", choices=sorted(TECH_NAMES),
                    help="vanilla band to compare with (default: midline; with --mod, each hull's .ship style)")
    ap.add_argument("--vanilla-table", action="store_true")
    ap.add_argument("--game")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    a = ap.parse_args()
    game = sslib.require_game_dir(a.game)
    table = vanilla_table(game)
    if a.vanilla_table:
        for t, row in table.items():
            print("%s (n=%d)" % (t, row["n"]))
            for k in KEYS:
                print("   %-13s p10 %.3f  median %.3f  p90 %.3f" % (k, *row[k]))
        return
    paths = list(a.sprites)
    tech_of = {}
    style_tech = {"LOW_TECH": "lowtech", "MIDLINE": "midline", "HIGH_TECH": "hightech"}
    if a.mod:
        for root, _, files in os.walk(os.path.join(a.mod, "data", "hulls")):
            for f in files:
                if f.endswith(".ship"):
                    d = sslib.load_loose_json(os.path.join(root, f))
                    sp = os.path.join(a.mod, d.get("spriteName", ""))
                    if os.path.isfile(sp):
                        paths.append(sp)
                        tech_of[sp] = style_tech.get(d.get("style"), "midline")
    results = {}
    flagged = 0
    for p in paths:
        tech = a.tech or tech_of.get(p, "midline")
        ref = table.get(TECH_NAMES[tech])
        s = measure(Image.open(p))
        if not s:
            print("%s: too few opaque pixels" % p)
            continue
        results[p] = s
        if a.json:
            continue
        print("%s  (vs vanilla %s)" % (os.path.basename(p), tech))
        for k in KEYS:
            lo, med, hi = ref[k]
            bad = not (lo <= s[k] <= hi)
            flagged += bad
            hint = ""
            if bad:
                hint = {"edge_density": "  <- %s surface detail" % ("add more" if s[k] < lo else "too much/noisy"),
                        "hf_energy": "  <- %s fine detail" % ("add" if s[k] < lo else "reduce"),
                        "rim_ratio": "  <- %s the silhouette rim" % ("darken" if s[k] > hi else "lighten"),
                        "sat_mean": "  <- %s saturation" % ("raise" if s[k] < lo else "lower"),
                        "lum_p5": "  <- shadows too %s" % ("light" if s[k] > hi else "dark"),
                        "lum_p95": "  <- highlights too %s" % ("dim" if s[k] < lo else "bright"),
                        "lum_mean": "  <- overall too %s" % ("dark" if s[k] < lo else "bright")}.get(k, "")
            print("   %-13s %.3f   vanilla %s p10-p90 %.3f-%.3f%s" % (k, s[k], tech, lo, hi, ("  OUT" if bad else "") + hint))
    if a.json:
        print(json.dumps({"vanilla": {t: table.get(n) for t, n in TECH_NAMES.items()}, "sprites": results}, indent=1))
    elif paths:
        print("\n%d metric(s) outside the vanilla band" % flagged)


if __name__ == "__main__":
    main()
