#!/usr/bin/env python3
"""kitbash.py - build a hull sprite from pieces of existing sprites (vanilla or your own), plus its .ship file.

Kitbashing vanilla sprites is standard practice for Starsector mods. The official wiki tutorial recommends it, and
the forum's "Kitbash Database" notes vanilla art is to be used "only in the context of Starsector's modding as per the
game's license". Credit the source hulls in your CREDITS/README.

    python kitbash.py list --size DESTROYER --tech Midline            # candidate source hulls with sizes
    python kitbash.py show vanilla:hammerhead --grid 10 --out hh.png  # 4x view with a pixel grid: read boxes off it
    python kitbash.py build my_kit.json --out-dir path/to/MyMod --preview
    python kitbash.py --example > my_kit.json

Spec (design units = final pixels; x from the centre line, + = right; y from the top):
  "size": [W, H]
  "pieces": [{"src": "vanilla:<hullId>" | "path/to.png", "box": [x0, y0, x1, y1] (source pixels, x1/y1 exclusive),
              "at": [x, y] (design position of the piece's top-left corner), "sym": true (also place the mirror),
              "flip": "h" | "v", "rot": 90 | 180 | 270 (applied before placing), "recolor": false (skip global recolor)}]
  "recolor": {"target": [r, g, b] | "paint", "min_sat": 0.18, "keep_value": true}   # repaint saturated pixels only
  "rim": 0.55                     # darken the silhouette rim where a piece was cut out of a larger sprite
  "tone_match": true              # match luminance p5/p95/mean to vanilla for "style" (harmonises mixed sources)
  "slots", "engines", "ship", "hullSize", "style", "id", "name": exactly as in hullgen.py
Later pieces are drawn on top of earlier ones. Build the silhouette from big pieces first, then add details.
"""
import argparse
import colorsys
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sslib  # noqa: E402
import hullgen  # noqa: E402


def load_src(src, game):
    if src.startswith("vanilla:"):
        hid = src.split(":", 1)[1]
        hulls = sslib.vanilla_hulls(game)
        if hid not in hulls:
            raise SystemExit("unknown vanilla hull %r (try: kitbash.py list)" % hid)
        d, _ = hulls[hid]
        return Image.open(os.path.join(sslib.core_dir(game), d["spriteName"])).convert("RGBA")
    return Image.open(src).convert("RGBA")


def cmd_list(a, game):
    core = sslib.core_dir(game)
    tech = {r["id"]: (r.get("tech/manufacturer") or "").strip()
            for r in sslib.read_csv(os.path.join(core, "data", "hulls", "ship_data.csv"))}
    rows = []
    for hid, (d, _) in sorted(sslib.vanilla_hulls(game).items()):
        if a.size and d.get("hullSize") != a.size:
            continue
        if a.tech and a.tech.lower() not in tech.get(hid, "").lower():
            continue
        rows.append((d.get("hullSize", "?"), tech.get(hid, ""), hid, d.get("width"), d.get("height"), d.get("spriteName")))
    for r in rows:
        print("%-13s %-12s %-28s %4sx%-4s %s" % r)
    print("%d hulls" % len(rows))


def cmd_show(a, game):
    im = load_src(a.src, game)
    s = a.scale
    W, H = im.size
    pad = 28
    bg = Image.new("RGBA", (W * s + pad * 2, H * s + pad * 2), (20, 22, 28, 255))
    chk = np.indices((H * s, W * s)).sum(0) // (2 * s) % 2
    g = (chk * 18 + 34).astype(np.uint8)
    bg.paste(Image.fromarray(np.stack([g, g, g + 6, np.full_like(g, 255)], 2), "RGBA"), (pad, pad))
    bg.alpha_composite(im.resize((W * s, H * s), Image.NEAREST), (pad, pad))
    d = ImageDraw.Draw(bg)
    try:
        font = ImageFont.truetype("arial.ttf", 11)
    except Exception:
        font = ImageFont.load_default()
    for x in range(0, W + 1, a.grid):
        X = pad + x * s
        d.line([(X, pad), (X, pad + H * s)], fill=(255, 255, 255, 70))
        d.text((X + 1, 4), str(x), fill=(255, 220, 120), font=font)
    for y in range(0, H + 1, a.grid):
        Y = pad + y * s
        d.line([(pad, Y), (pad + W * s, Y)], fill=(255, 255, 255, 70))
        d.text((2, Y + 1), str(y), fill=(255, 220, 120), font=font)
    cx = pad + W * s / 2
    d.line([(cx, pad), (cx, pad + H * s)], fill=(80, 200, 255, 140))
    out = a.out or "kitbash_show.png"
    bg.convert("RGB").save(out)
    print("wrote %s  (source %dx%d; grid every %d px; blue line = centre)" % (out, W, H, a.grid))


def transform(piece, p):
    if p.get("flip") == "h":
        piece = piece.transpose(Image.FLIP_LEFT_RIGHT)
    elif p.get("flip") == "v":
        piece = piece.transpose(Image.FLIP_TOP_BOTTOM)
    rot = int(p.get("rot", 0)) % 360
    if rot:
        piece = piece.rotate(-rot, expand=True)  # positive = clockwise on screen
    return piece


def recolor_array(rgba, target, min_sat=0.18, keep_value=True, mask=None, sat_scale=0.7):
    """Repaint saturated pixels to the target hue/saturation, leaving greys (machinery) alone."""
    a = rgba.astype(np.float32) / 255.0
    rgb = a[..., :3]
    mx, mn = rgb.max(axis=2), rgb.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    th, ts, tv = colorsys.rgb_to_hsv(*[c / 255.0 for c in target])
    sel = (sat > min_sat) & (a[..., 3] > 0)
    if mask is not None:
        sel &= mask
    ys, xs = np.nonzero(sel)
    if len(xs):
        px = rgb[ys, xs]
        hsv = np.array([colorsys.rgb_to_hsv(*c) for c in px])
        s_old = hsv[:, 1]
        # keep each pixel's relative saturation so painted shading survives
        s_new = np.clip(s_old / max(1e-3, np.median(s_old)) * ts * sat_scale, 0, 1)
        v_new = hsv[:, 2] if keep_value else np.clip(hsv[:, 2] / max(1e-3, np.median(hsv[:, 2])) * tv, 0, 1)
        out = np.array([colorsys.hsv_to_rgb(th, s, v) for s, v in zip(s_new, v_new)])
        rgb[ys, xs] = out
    a[..., :3] = rgb
    return (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)


def rim_darken(img, strength=0.55, only=None):
    """Darken the outer two pixels of the silhouette (optionally only where `only` is True: the cut edges)."""
    a = np.asarray(img).astype(np.float32)
    inside = a[..., 3] > 127
    e1 = hullgen.erode(inside, 1)
    e2 = hullgen.erode(inside, 2)
    k = np.ones(inside.shape, np.float32)
    r1, r2 = inside & ~e1, e1 & ~e2
    if only is not None:
        r1, r2 = r1 & only, r2 & only
    k[r1] = strength
    k[r2] = 0.5 + 0.5 * strength + 0.1
    a[..., :3] *= np.clip(k, 0, 1)[..., None]
    return Image.fromarray(np.clip(a + 0.5, 0, 255).astype(np.uint8), "RGBA")


def build(spec, game, out_dir=None, preview=None):
    W, H = int(spec["size"][0]), int(spec["size"][1])
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    no_recolor = np.zeros((H, W), bool)
    cut = np.zeros((H, W), bool)  # piece edges that were interior in the source (they need a rim)
    pal = dict(hullgen.STYLES.get(spec.get("style", "midline"), hullgen.STYLES["midline"]))
    cache = {}
    for p in spec.get("pieces", []):
        src = cache.setdefault(p["src"], load_src(p["src"], game))
        x0, y0, x1, y1 = p.get("box", [0, 0, src.width, src.height])
        piece = transform(src.crop((x0, y0, x1, y1)), p)
        sa = np.asarray(src)[..., 3] > 0
        cm = np.zeros((y1 - y0, x1 - x0), bool)  # crop-border pixels whose source continues past the border
        if y0 > 0:
            cm[0:2, :] |= sa[y0 - 1, x0:x1][None, :]
        if y1 < src.height:
            cm[-2:, :] |= sa[y1, x0:x1][None, :]
        if x0 > 0:
            cm[:, 0:2] |= sa[y0:y1, x0 - 1][:, None]
        if x1 < src.width:
            cm[:, -2:] |= sa[y0:y1, x1][:, None]
        cut_piece = transform(Image.fromarray((cm * 255).astype(np.uint8)), p)
        ax, ay = p.get("at", [-piece.width / 2.0, 0])
        places = [(int(round(W / 2.0 + ax)), int(round(ay)), piece, cut_piece)]
        if p.get("sym"):
            places.append((int(round(W / 2.0 - ax - piece.width)), int(round(ay)),
                           piece.transpose(Image.FLIP_LEFT_RIGHT), cut_piece.transpose(Image.FLIP_LEFT_RIGHT)))
        for px, py, pc, cc in places:
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            layer.paste(pc, (px, py))
            canvas.alpha_composite(layer)
            cl = Image.new("L", (W, H), 0)
            cl.paste(cc, (px, py))
            cut |= np.asarray(cl) > 127
            if p.get("recolor") is False:
                no_recolor |= np.asarray(layer)[..., 3] > 0
    arr = np.asarray(canvas).copy()
    rc = spec.get("recolor")
    if rc:
        tgt = rc.get("target", "paint")
        tgt = pal[tgt] if isinstance(tgt, str) else tgt
        arr = recolor_array(arr, tgt, rc.get("min_sat", 0.18), rc.get("keep_value", True), mask=~no_recolor,
                            sat_scale=rc.get("sat_scale", 0.7))
    if spec.get("tone_match", True) and pal.get("target"):
        rgb = arr[..., :3].astype(np.float32) / 255.0
        A = arr[..., 3].astype(np.float32) / 255.0
        rgb = hullgen.tone_match(rgb, A, np.zeros_like(A), pal["target"], False)
        arr[..., :3] = (np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8)
    sprite = Image.fromarray(arr, "RGBA")
    if spec.get("rim", 0.55):
        grow = np.asarray(Image.fromarray((cut * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))) > 127
        sprite = rim_darken(sprite, float(spec.get("rim", 0.55)), only=grow)
    sprite = hullgen.alpha_bleed(sprite)
    ship = hullgen.ship_json(spec, sprite)
    warns = hullgen.check(spec, sprite, ship)
    written = []
    if out_dir:
        p = os.path.join(out_dir, ship["spriteName"])
        os.makedirs(os.path.dirname(p), exist_ok=True)
        sprite.save(p)
        sh = os.path.join(out_dir, "data", "hulls", spec["id"] + ".ship")
        sslib.write_json(sh, ship)
        written += [p, sh]
    if preview:
        import contact_sheet
        big = sprite.resize((W * 2, H * 2), Image.NEAREST)
        ov = contact_sheet.overlay(big.copy(), ship, 2)
        sheet = contact_sheet.starfield(big.width * 2 + 48, big.height + 24).convert("RGBA")
        sheet.alpha_composite(big, (12, 12))
        sheet.alpha_composite(ov, (big.width + 36, 12))
        sheet.convert("RGB").save(preview)
        written.append(preview)
    for w in written:
        print("wrote", w)
    for w in warns:
        print("WARNING:", w)
    return sprite, ship, warns


EXAMPLE = {
    "id": "xmpl_bulwark", "name": "Bulwark", "hullSize": "DESTROYER", "size": [120, 164], "style": "lowtech",
    "pieces": [
        {"src": "vanilla:hammerhead", "box": [0, 0, 54, 164], "at": [-54, 0], "sym": True},
        {"src": "vanilla:enforcer", "box": [0, 40, 40, 110], "at": [-60, 50], "sym": True}
    ],
    "recolor": {"target": "paint", "min_sat": 0.18},
    "rim": 0.55,
    "slots": [
        {"id": "WS0001", "pos": [-30, 60], "size": "MEDIUM", "type": "BALLISTIC", "mount": "TURRET", "angle": 30,
         "arc": 200, "sym": True}
    ],
    "engines": [{"pos": [-14, 162], "sym": True}],
    "ship": {"builtInMods": []}
}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--example", action="store_true", help="print an example kit spec")
    ap.add_argument("--game")
    sub = ap.add_subparsers(dest="cmd")
    s1 = sub.add_parser("list")
    s1.add_argument("--size", choices=sslib.HULL_SIZES)
    s1.add_argument("--tech", help="substring of tech/manufacturer, e.g. 'Low Tech', 'Midline', 'High Tech'")
    s2 = sub.add_parser("show")
    s2.add_argument("src")
    s2.add_argument("--grid", type=int, default=10)
    s2.add_argument("--scale", type=int, default=4)
    s2.add_argument("--out")
    s3 = sub.add_parser("build")
    s3.add_argument("spec")
    s3.add_argument("--out-dir")
    s3.add_argument("--preview", action="store_true")
    a = ap.parse_args()
    if a.example:
        print(json.dumps(EXAMPLE, indent=2))
        return
    game = sslib.require_game_dir(a.game)
    if a.cmd == "list":
        cmd_list(a, game)
    elif a.cmd == "show":
        cmd_show(a, game)
    elif a.cmd == "build":
        spec = sslib.load_loose_json(a.spec)
        out_dir = a.out_dir or os.path.dirname(os.path.abspath(a.spec))
        prev = os.path.splitext(a.spec)[0] + "_preview.png" if a.preview else None
        build(spec, game, out_dir, prev)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
