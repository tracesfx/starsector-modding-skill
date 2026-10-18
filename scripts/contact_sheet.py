#!/usr/bin/env python3
"""Contact sheet / preview for Starsector sprites, with optional vanilla peers and .ship overlays.

Typical uses
  # every hull of a mod, at 1x and 2x, each next to 2 vanilla hulls of the same size class, with slot overlays
  python contact_sheet.py --mod path/to/MyMod --peers 2 --scale 1,2 --overlay --out sheet.png

  # a few loose sprites against named vanilla hulls
  python contact_sheet.py my_ship.png other.png --vanilla wolf,lasher,tempest --scale 2 --out cmp.png

Then LOOK at the PNG (an agent can open it with its image-reading tool). Judge at 1x first: that is how players
see ships. The overlay draws the bounds polygon (green), center (white cross), weapon slots (yellow=turret,
orange=hardpoint, cyan=hidden/built-in; arc wedge + facing line, radius by size) and engines (blue).
"""
import argparse
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sslib  # noqa: E402

SLOT_R = {"SMALL": 5, "MEDIUM": 8, "LARGE": 12}


def starfield(w, h, seed=7):
    rng = np.random.default_rng(seed)
    base = np.zeros((h, w, 3), np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    base[..., 0] = 8 + 6 * (yy / max(1, h))
    base[..., 1] = 10 + 4 * (xx / max(1, w))
    base[..., 2] = 18 + 8 * (yy / max(1, h))
    n = max(1, w * h // 900)
    ys = rng.integers(0, h, n); xs = rng.integers(0, w, n); b = rng.uniform(60, 220, n)
    base[ys, xs] = np.stack([b, b, b * 1.05], 1)
    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB")


def background(kind, w, h):
    if kind == "space":
        return starfield(w, h)
    if kind == "checker":
        a = np.indices((h, w)).sum(0) // 8 % 2
        g = (a * 40 + 90).astype(np.uint8)
        return Image.fromarray(np.stack([g, g, g], 2), "RGB")
    col = {"dark": (14, 16, 22), "grey": (96, 96, 96), "white": (235, 235, 235)}.get(kind, (14, 16, 22))
    return Image.new("RGB", (w, h), col)


def find_ship_json_for_sprite(sprite_path, search_roots):
    """Find a .ship whose spriteName ends with this sprite's relative path."""
    sp = sprite_path.replace("\\", "/").lower()
    for root in search_roots:
        for r, _, files in os.walk(root):
            for f in files:
                if f.endswith(".ship"):
                    try:
                        d = sslib.load_loose_json(os.path.join(r, f))
                    except Exception:
                        continue
                    name = (d.get("spriteName") or "").replace("\\", "/").lower()
                    if name and sp.endswith(name):
                        return d
    return None


def overlay(img, ship, scale):
    """Draw .ship geometry onto an RGBA image already scaled by `scale`."""
    d = ImageDraw.Draw(img, "RGBA")
    H = float(ship.get("height", img.height / scale))
    c = ship.get("center", [img.width / scale / 2, H / 2])

    def P(x, y):
        px, py = sslib.ship_to_image(x, y, c, H)
        return (px * scale, py * scale)

    b = ship.get("bounds") or []
    pts = [P(b[i], b[i + 1]) for i in range(0, len(b) - 1, 2)]
    if len(pts) >= 3:
        d.line(pts + [pts[0]], fill=(60, 255, 120, 200), width=1)
    cx, cy = P(0, 0)
    d.line([(cx - 4, cy), (cx + 4, cy)], fill=(255, 255, 255, 230))
    d.line([(cx, cy - 4), (cx, cy + 4)], fill=(255, 255, 255, 230))
    cr = ship.get("collisionRadius")
    if cr:
        d.ellipse([cx - cr * scale, cy - cr * scale, cx + cr * scale, cy + cr * scale], outline=(255, 255, 255, 50))
    for s in ship.get("weaponSlots") or []:
        if not s.get("locations"):
            continue
        mount = s.get("mount", "TURRET")
        typ = s.get("type", "")
        col = (255, 220, 60, 230) if mount == "TURRET" else (255, 140, 40, 230)
        if mount == "HIDDEN" or typ in ("BUILT_IN", "DECORATIVE", "SYSTEM", "LAUNCH_BAY", "STATION_MODULE"):
            col = (80, 230, 255, 230)
        r = SLOT_R.get(s.get("size", "SMALL"), 5) * scale / 2 + 2
        ang = float(s.get("angle", 0)); arc = float(s.get("arc", 0))
        locs = s["locations"]
        for i in range(0, len(locs) - 1, 2):
            x, y = P(locs[i], locs[i + 1])
            # screen angle: ship forward = up (-90 deg in PIL's clockwise-from-+x convention); ship CCW -> screen CCW
            face = -90 - ang
            if arc > 0:
                d.pieslice([x - r * 2.2, y - r * 2.2, x + r * 2.2, y + r * 2.2], face - arc / 2, face + arc / 2,
                           fill=col[:3] + (40,))
            d.ellipse([x - r, y - r, x + r, y + r], outline=col)
            fx = x + math.cos(math.radians(face)) * r * 2.4
            fy = y + math.sin(math.radians(face)) * r * 2.4
            d.line([(x, y), (fx, fy)], fill=col)
    for e in ship.get("engineSlots") or []:
        loc = e.get("location") or [0, 0]
        x, y = P(loc[0], loc[1])
        w = float(e.get("width", 6)) * scale / 2
        ln = float(e.get("length", 10)) * scale
        ang = float(e.get("angle", 180))
        face = -90 - ang
        ex = x + math.cos(math.radians(face)) * ln
        ey = y + math.sin(math.radians(face)) * ln
        d.line([(x, y), (ex, ey)], fill=(90, 160, 255, 160), width=max(1, int(w)))
        d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(150, 200, 255, 255))
    return img


def collect_mod(mod):
    items = []
    for root, _, files in os.walk(os.path.join(mod, "data", "hulls")):
        for f in sorted(files):
            if f.endswith(".ship"):
                try:
                    d = sslib.load_loose_json(os.path.join(root, f))
                except Exception as e:
                    print("skip", f, e)
                    continue
                sp = d.get("spriteName")
                if sp and os.path.exists(os.path.join(mod, sp)):
                    items.append((d.get("hullId", f), os.path.join(mod, sp), d, False))
    return items


def vanilla_peers(game, ship, n, exclude=()):
    hs = ship.get("hullSize")
    area = float(ship.get("width", 1)) * float(ship.get("height", 1))
    cands = []
    for hid, (d, _p) in sslib.vanilla_hulls(game).items():
        if d.get("hullSize") != hs or hid in exclude or "_" in hid and hid.split("_")[-1] in ("d", "default"):
            continue
        if any(t in hid for t in ("module", "station", "_lg", "_xiv", "_tt", "_pirates", "_luddic", "_hegemony")):
            continue
        a = float(d.get("width", 1)) * float(d.get("height", 1))
        cands.append((abs(math.log(max(a, 1) / max(area, 1))), hid, d))
    cands.sort(key=lambda t: t[0])
    core = sslib.core_dir(game)
    out = []
    for _, hid, d in cands[:n]:
        p = os.path.join(core, d["spriteName"])
        if os.path.exists(p):
            out.append(("vanilla:" + hid, p, d, True))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sprites", nargs="*", help="sprite PNGs (a matching .ship is looked up under --mod if given)")
    ap.add_argument("--mod", help="mod folder: include every hull sprite from data/hulls/*.ship")
    ap.add_argument("--vanilla", default="", help="comma-separated vanilla hull ids to include")
    ap.add_argument("--peers", type=int, default=0, help="add N closest-size vanilla hulls of the same hull size per mod hull")
    ap.add_argument("--scale", default="1,2", help="comma-separated scales, e.g. 1,2 or 3")
    ap.add_argument("--bg", default="space", choices=["space", "dark", "grey", "checker", "white"])
    ap.add_argument("--overlay", action="store_true", help="draw bounds/slots/engines from .ship data")
    ap.add_argument("--max-width", type=int, default=2400)
    ap.add_argument("--game", help="Starsector install dir (auto-detected)")
    ap.add_argument("--out", default="contact_sheet.png")
    a = ap.parse_args()

    scales = [float(s) for s in a.scale.split(",") if s.strip()]
    game = sslib.find_game_dir(a.game)
    items = []
    if a.mod:
        mod_items = collect_mod(a.mod)
        for it in mod_items:
            items.append(it)
            if a.peers and game:
                items += vanilla_peers(game, it[2], a.peers)
    for sp in a.sprites:
        d = find_ship_json_for_sprite(os.path.abspath(sp), [os.path.join(a.mod, "data")] if a.mod else [])
        items.append((os.path.basename(sp), sp, d, False))
    if a.vanilla:
        if not game:
            sys.exit("--vanilla needs the game dir (--game)")
        vh = sslib.vanilla_hulls(game)
        core = sslib.core_dir(game)
        for hid in [h.strip() for h in a.vanilla.split(",") if h.strip()]:
            if hid not in vh:
                print("unknown vanilla hull", hid)
                continue
            d, _ = vh[hid]
            items.append(("vanilla:" + hid, os.path.join(core, d["spriteName"]), d, True))
    if not items:
        sys.exit("nothing to show")

    try:
        font = ImageFont.truetype("arial.ttf", 12)
    except Exception:
        font = ImageFont.load_default()

    tiles = []
    for name, path, ship, is_vanilla in items:
        im = Image.open(path).convert("RGBA")
        for s in scales:
            w, h = max(1, int(im.width * s)), max(1, int(im.height * s))
            t = im.resize((w, h), Image.NEAREST if s >= 1 else Image.LANCZOS)
            if a.overlay and ship:
                t = overlay(t, ship, s)
            label = "%s %dx%d @%gx" % (name, im.width, im.height, s)
            tiles.append((t, label, is_vanilla))

    pad, lab = 12, 16
    rows, row, x, maxw = [], [], pad, 0
    for t in tiles:
        tw = max(t[0].width, int(font.getlength(t[1])) if hasattr(font, "getlength") else t[0].width)
        if row and x + tw + pad > a.max_width:
            rows.append(row); row, x = [], pad
        row.append((t, x)); x += tw + pad
        maxw = max(maxw, x)
    if row:
        rows.append(row)
    heights = [max(t[0].height for t, _ in r) + lab + pad for r in rows]
    W, Hh = min(a.max_width, maxw), sum(heights) + pad
    sheet = background(a.bg, W, Hh).convert("RGBA")
    d = ImageDraw.Draw(sheet)
    y = pad
    for r, rh in zip(rows, heights):
        for (t, label, is_v), x in r:
            sheet.alpha_composite(t, (x, y + lab))
            d.text((x, y), label, fill=(150, 170, 200) if is_v else (255, 230, 150), font=font)
        y += rh
    sheet.convert("RGB").save(a.out)
    print("wrote %s (%dx%d, %d tiles)" % (a.out, W, Hh, len(tiles)))


if __name__ == "__main__":
    main()
