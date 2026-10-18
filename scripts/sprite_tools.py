#!/usr/bin/env python3
"""sprite_tools.py - clean up external/AI/hand-made images into Starsector sprites, recolour, estimate maps, check.

  clean    python sprite_tools.py clean in.png out.png --length 160 --rotate 0 --straighten --symmetrize left --style midline
           background removal (alpha, or flood fill from the border colour) -> crop -> rotate/straighten so the ship
           faces UP -> optional mirror symmetry -> premultiplied-alpha downscale to the target length -> even width ->
           tone match to vanilla -> dark rim -> alpha bleed. Also works for weapons (--length = sprite height).
  recolor  python sprite_tools.py recolor in.png out.png --target 96,150,128     (faction skins: repaints saturated
           pixels only, so grey machinery stays grey)
  maps     python sprite_tools.py maps in.png --out-prefix graphics/shaders/{normal,material,surface}/ships/my_ship
           estimated GraphicsLib normal/material/surface maps for any sprite (see references/sprites.md for accuracy)
  check    python sprite_tools.py check graphics/ships/*.png --kind ship|weapon|icon
           8-bit RGBA, even width, transparent border, size and pixel mass against vanilla hulls of that class

Palette quantisation (--quantize N) exists but is off by default: Starsector sprites are "tiny paintings, not pixel
art" (wiki), and quantising usually hurts them.
"""
import argparse
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sslib  # noqa: E402
import hullgen  # noqa: E402


# ------------------------------------------------------------------ background removal
def remove_background(im, tol=0.12, soft=0.08):
    """Return RGBA with the background made transparent.

    If the image already has transparency, keep it. Otherwise the background colour is the median of the border
    pixels; everything connected to the border and within `tol` (0..1 colour distance) of it becomes transparent,
    with a soft alpha ramp over the next `soft` of distance (anti-aliased edges).
    """
    im = im.convert("RGBA")
    a = np.asarray(im).astype(np.float32) / 255.0
    if (a[..., 3] < 0.98).mean() > 0.02:  # already has meaningful alpha
        return im
    rgb = a[..., :3]
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    bg = np.median(border, axis=0)
    dist = np.sqrt(((rgb - bg) ** 2).sum(axis=2)) / math.sqrt(3)
    near = (dist < tol + soft).astype(np.uint8) * 255
    # flood fill from a 1-px frame so every border-connected background region is found in one C-speed fill
    H, W = near.shape
    framed = Image.new("L", (W + 2, H + 2), 255)
    framed.paste(Image.fromarray(near, "L"), (1, 1))
    ImageDraw.floodfill(framed, (0, 0), 128, thresh=0)
    conn = (np.asarray(framed)[1:-1, 1:-1] == 128)
    alpha = np.ones((H, W), np.float32)
    ramp = np.clip((dist - tol) / max(1e-6, soft), 0, 1)
    alpha[conn] = ramp[conn]
    # un-mix the background colour from semi-transparent edge pixels
    al = alpha[..., None]
    un = np.where(al > 0.05, (rgb - bg * (1 - al)) / np.maximum(al, 0.05), rgb)
    out = np.concatenate([np.clip(un, 0, 1), alpha[..., None]], axis=2)
    return Image.fromarray((out * 255 + 0.5).astype(np.uint8), "RGBA")


def crop_to_content(im, margin=1, thresh=8):
    a = np.asarray(im)[..., 3]
    ys, xs = np.nonzero(a > thresh)
    if len(xs) == 0:
        return im
    x0, x1 = max(0, xs.min() - margin), min(im.width, xs.max() + 1 + margin)
    y0, y1 = max(0, ys.min() - margin), min(im.height, ys.max() + 1 + margin)
    return im.crop((x0, y0, x1, y1))


def principal_angle(im):
    """Angle (degrees) of the alpha mask's long axis from vertical, in (-90, 90]."""
    a = np.asarray(im)[..., 3] > 127
    ys, xs = np.nonzero(a)
    if len(xs) < 10:
        return 0.0
    x = xs - xs.mean()
    y = ys - ys.mean()
    cov = np.cov(np.stack([x, y]))
    w, v = np.linalg.eigh(cov)
    vx, vy = v[:, np.argmax(w)]
    ang = math.degrees(math.atan2(vx, vy))  # 0 = vertical axis
    if ang > 90:
        ang -= 180
    if ang <= -90:
        ang += 180
    return ang


def symmetry_score(mask):
    """Best left/right mirror overlap of a boolean mask over candidate axes near the centre (0..1)."""
    a = mask.astype(np.float32)
    W = a.shape[1]
    tot = max(1.0, a.sum())
    best = 0.0
    for off in range(-int(W * 0.08) - 1, int(W * 0.08) + 2):
        c = W / 2.0 + off / 2.0
        xs = np.arange(W)
        mx = np.round(2 * c - xs - 1).astype(int)
        ok = (mx >= 0) & (mx < W)
        best = max(best, float((a[:, xs[ok]] * a[:, mx[ok]]).sum() / tot))
    return best


def symmetry_angle(im, span=20.0, step=0.5):
    """Rotation (deg, counter-clockwise) within +-span that makes the silhouette most mirror-symmetric.

    Works for any aspect ratio (PCA does not: near-square hulls have no dominant axis). Ships are almost perfectly
    symmetric (vanilla median silhouette asymmetry 0.7%), so symmetry is a reliable signal.
    """
    small = im.copy()
    small.thumbnail((160, 160))
    best, best_a = -1.0, 0.0
    for ang in np.arange(-span, span + 1e-6, step):
        r = small.rotate(float(ang), resample=Image.BILINEAR, expand=True)
        s = symmetry_score(np.asarray(r)[..., 3] > 127)
        if s > best + 1e-4:
            best, best_a = s, float(ang)
    return best_a, best


def premult_resize(im, size):
    """Downscale with premultiplied alpha (no dark/bright fringes); big reductions go in halving steps."""
    a = np.asarray(im.convert("RGBA")).astype(np.float32) / 255.0
    pm = a.copy()
    pm[..., :3] *= pm[..., 3:4]
    cur = Image.fromarray((pm * 255 + 0.5).astype(np.uint8), "RGBA")
    while cur.width >= size[0] * 2 and cur.height >= size[1] * 2:
        cur = cur.resize((cur.width // 2, cur.height // 2), Image.BOX)
    cur = cur.resize(size, Image.LANCZOS)
    o = np.asarray(cur).astype(np.float32) / 255.0
    A = o[..., 3:4]
    rgb = np.where(A > 1e-3, o[..., :3] / np.maximum(A, 1e-3), 0)
    return Image.fromarray((np.clip(np.concatenate([rgb, A], axis=2), 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA")


def best_symmetry_axis(im, search=0.08):
    a = (np.asarray(im)[..., 3] > 127).astype(np.float32)
    W = a.shape[1]
    best, bx = -1, W / 2.0
    for off in range(-int(W * search), int(W * search) + 1):
        c = W / 2.0 + off / 2.0
        # compare columns mirrored around c
        xs = np.arange(W)
        mx = np.round(2 * c - xs - 1).astype(int)
        ok = (mx >= 0) & (mx < W)
        score = (a[:, xs[ok]] * a[:, mx[ok]]).sum() / max(1, a.sum())
        if score > best:
            best, bx = score, c
    return bx


def symmetrize(im, keep="left"):
    c = best_symmetry_axis(im)
    W, H = im.size
    half = int(round(min(c, W - c)))
    left = im.crop((int(round(c - half)), 0, int(round(c)), H))
    right = im.crop((int(round(c)), 0, int(round(c + half)), H))
    src = left if keep == "left" else right.transpose(Image.FLIP_LEFT_RIGHT)
    out = Image.new("RGBA", (2 * half, H), (0, 0, 0, 0))
    out.paste(src, (0, 0))
    out.paste(src.transpose(Image.FLIP_LEFT_RIGHT), (half, 0))
    return out


def cmd_clean(a):
    im = Image.open(a.input)
    im = remove_background(im, a.tol, a.soft)
    im = crop_to_content(im, margin=2)
    if a.rotate:
        im = im.rotate(a.rotate, resample=Image.BICUBIC, expand=True)  # counter-clockwise degrees
    if a.straighten:
        ang, score = symmetry_angle(im)
        if ang:
            im = im.rotate(ang, resample=Image.BICUBIC, expand=True)
        print("straightened by %.1f deg (mirror symmetry %.3f)" % (ang, score))
    im = crop_to_content(im, margin=2)
    if a.symmetrize != "none":
        im = symmetrize(im, a.symmetrize)
        im = crop_to_content(im, margin=1)
    if a.length:
        h = a.length
        w = max(2, int(round(im.width * h / im.height)))
        if a.even and w % 2:
            w += 1
        im = premult_resize(im, (w, h))
    elif a.even and im.width % 2:
        im = premult_resize(im, (im.width + 1, im.height))
    arr = np.asarray(im).astype(np.float32) / 255.0
    rgb, A = arr[..., :3], arr[..., 3]
    if a.quantize:
        q = Image.fromarray((rgb * 255).astype(np.uint8), "RGB").quantize(colors=a.quantize, method=Image.MEDIANCUT)
        rgb = np.asarray(q.convert("RGB")).astype(np.float32) / 255.0
    if a.sharpen > 0:
        s = Image.fromarray((rgb * 255).astype(np.uint8), "RGB").filter(
            ImageFilter.UnsharpMask(radius=1, percent=int(a.sharpen * 100), threshold=2))
        rgb = np.asarray(s).astype(np.float32) / 255.0
    if a.style != "none":
        t = hullgen.STYLES[a.style]["target"]
        rgb = hullgen.tone_match(rgb, A, np.zeros_like(A), t, False)
    out = Image.fromarray((np.concatenate([rgb, A[..., None]], axis=2) * 255 + 0.5).astype(np.uint8), "RGBA")
    if a.rim < 1:
        import kitbash
        out = kitbash.rim_darken(out, a.rim)
    o = np.asarray(out).copy()
    o[o[..., 3] < 8] = 0
    out = hullgen.alpha_bleed(Image.fromarray(o, "RGBA"))
    os.makedirs(os.path.dirname(os.path.abspath(a.output)), exist_ok=True)
    out.save(a.output)
    print("wrote %s (%dx%d RGBA)" % (a.output, out.width, out.height))


def cmd_recolor(a):
    import kitbash
    im = Image.open(a.input).convert("RGBA")
    tgt = [int(v) for v in a.target.split(",")]
    arr = kitbash.recolor_array(np.asarray(im), tgt, a.min_sat, True, None, a.sat_scale)
    Image.fromarray(arr, "RGBA").save(a.output)
    print("wrote", a.output)


# ------------------------------------------------------------------ GraphicsLib map estimation
def estimate_maps(im, depth=16.0, detail=1.0, pillow=1.5):
    """Estimate GraphicsLib maps from a finished sprite.

    height = pillow(silhouette distance) + detail * blurred luminance. normal: R=+right, G=+down, B=+z (the
    convention measured on GraphicsLib's own vanilla maps). Defaults were grid-searched against GraphicsLib's authored
    normal maps for 24 vanilla hulls: mean per-pixel cosine 0.90 (a flat normal scores 0.70). material = sprite * 0.72 with glow pixels black.
    surface = (0, specular, hardness): metal-like low-saturation bright pixels get more specular.
    """
    a = np.asarray(im.convert("RGBA")).astype(np.float32) / 255.0
    rgb, A = a[..., :3], a[..., 3]
    inside = (A > 0.5).astype(np.float32)
    lum = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    pil = hullgen.smoothstep(0.3, 1.0, hullgen.blur(inside, pillow))
    h = 0.5 * pil + detail * hullgen.blur(lum, 0.6)
    gy, gx = np.gradient(h)
    nr, nd = -gx * depth, -gy * depth
    nl = np.sqrt(nr * nr + nd * nd + 1)
    normal = np.stack([0.5 + 0.5 * nr / nl, 0.5 + 0.5 * nd / nl, 0.5 + 0.5 / nl, A], axis=2)
    mx, mn = rgb.max(axis=2), rgb.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    glow = (mx > 0.85) & (sat > 0.45)
    material = np.concatenate([rgb * 0.72 * (~glow)[..., None], A[..., None]], axis=2)
    spec = np.clip(0.15 + 0.5 * lum * (1 - sat), 0, 1)
    hard = np.clip(0.15 + 0.3 * (1 - sat), 0, 1)
    surface = np.stack([np.zeros_like(A), spec, hard, A], axis=2)

    def to(x):
        return Image.fromarray((np.clip(x, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA")
    return to(normal), to(material), to(surface)


def cmd_maps(a):
    im = Image.open(a.input)
    n, m, s = estimate_maps(im, a.depth, a.detail, a.pillow)
    pre = a.out_prefix
    base = os.path.basename(pre)
    for kind, img in (("normal", n), ("material", m), ("surface", s)):
        p = pre.replace("{kind}", kind) if "{kind}" in pre else pre + "_" + kind
        p = p if p.endswith(".png") else p + ".png"
        os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
        img.save(p)
        print("wrote", p)
    print("Register each map in data/lights/<mod>_texture_data.csv (id,type,frame,magnitude,map,path) and load it from "
          "your ModPlugin with org.dark.shaders.util.TextureData.readTextureDataCSV(path) when shaderLib is enabled. (%s)" % base)


# ------------------------------------------------------------------ checks
def cmd_check(a):
    game = sslib.find_game_dir(a.game)
    medians = {}
    if game and a.kind == "ship":
        import collections
        bucket = collections.defaultdict(list)
        core = sslib.core_dir(game)
        for hid, (d, _) in sslib.vanilla_hulls(game).items():
            p = os.path.join(core, d.get("spriteName", ""))
            if os.path.isfile(p) and d.get("hullSize") in hullgen.ENGINE_DEFAULTS:
                im = Image.open(p)
                mass = int((np.asarray(im.convert("RGBA"))[..., 3] > 127).sum())
                bucket[d["hullSize"]].append((im.width, im.height, mass))
        for k, L in bucket.items():
            arr = np.array(L)
            medians[k] = (np.percentile(arr, 10, axis=0), np.median(arr, axis=0), np.percentile(arr, 90, axis=0))
    bad = 0
    for p in a.files:
        im = Image.open(p)
        issues = []
        if im.mode not in ("RGBA",):
            issues.append("mode %s (save as 8-bit RGBA; palette/16-bit PNGs can crash the texture loader)" % im.mode)
        if im.info.get("icc_profile"):
            issues.append("embedded ICC profile (harmless, but strip it to keep colours predictable)")
        rgba = np.asarray(im.convert("RGBA"))
        notes = []
        if im.width % 2:
            if a.kind == "weapon":
                issues.append("odd width %d (wiki: odd-width weapon sprites blur; keep widths even)" % im.width)
            elif a.kind == "ship":
                notes.append("odd width %d (allowed; 7 of 127 vanilla hulls are odd, but even is safer)" % im.width)
        edge = np.concatenate([rgba[0, :, 3], rgba[-1, :, 3], rgba[:, 0, 3], rgba[:, -1, 3]])
        if (edge > 8).any() and a.kind == "ship":
            notes.append("touches the image border (fine: 16% of vanilla hulls do; median margin is 1 px)")
        mass = int((rgba[..., 3] > 127).sum())
        info = "%dx%d, pixel mass %d" % (im.width, im.height, mass)
        if a.kind == "ship" and a.size and a.size in medians:
            lo, med, hi = medians[a.size]
            info += " | vanilla %s median %dx%d mass %d (p10-p90 mass %d-%d)" % (a.size, med[0], med[1], med[2], lo[2], hi[2])
            if not (lo[2] * 0.8 <= mass <= hi[2] * 1.2):
                issues.append("pixel mass outside the vanilla %s range (wiki: match existing ships' pixel mass)" % a.size)
        print("%s: %s" % (p, info))
        for i in issues:
            print("   ISSUE:", i)
        for n_ in notes:
            print("   note:", n_)
        bad += bool(issues)
    print("%d file(s) with issues" % bad)
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("clean")
    c.add_argument("input")
    c.add_argument("output")
    c.add_argument("--length", type=int, help="final height in px (ships face up)")
    c.add_argument("--rotate", type=float, default=0, help="counter-clockwise degrees to rotate first")
    c.add_argument("--straighten", action="store_true", help="auto-align the long axis to vertical (|angle| <= 45)")
    c.add_argument("--symmetrize", choices=["none", "left", "right"], default="none")
    c.add_argument("--style", choices=["none"] + sorted(hullgen.STYLES), default="none")
    c.add_argument("--tol", type=float, default=0.12, help="background colour tolerance 0..1")
    c.add_argument("--soft", type=float, default=0.08)
    c.add_argument("--sharpen", type=float, default=0.3)
    c.add_argument("--rim", type=float, default=0.6, help="rim darkening factor (1 = off)")
    c.add_argument("--quantize", type=int, default=0)
    c.add_argument("--even", action="store_true", default=True)
    r = sub.add_parser("recolor")
    r.add_argument("input")
    r.add_argument("output")
    r.add_argument("--target", required=True, help="r,g,b")
    r.add_argument("--min-sat", type=float, default=0.16)
    r.add_argument("--sat-scale", type=float, default=0.7)
    m = sub.add_parser("maps")
    m.add_argument("input")
    m.add_argument("--out-prefix", required=True, help="path prefix; '{kind}' is replaced by normal/material/surface")
    m.add_argument("--depth", type=float, default=16.0)
    m.add_argument("--detail", type=float, default=1.0)
    m.add_argument("--pillow", type=float, default=1.5)
    k = sub.add_parser("check")
    k.add_argument("files", nargs="+")
    k.add_argument("--kind", choices=["ship", "weapon", "icon", "other"], default="ship")
    k.add_argument("--size", choices=list(hullgen.ENGINE_DEFAULTS), help="hull size for the pixel-mass comparison")
    k.add_argument("--game")
    a = ap.parse_args()
    if a.cmd == "clean":
        cmd_clean(a)
    elif a.cmd == "recolor":
        cmd_recolor(a)
    elif a.cmd == "maps":
        cmd_maps(a)
    elif a.cmd == "check":
        sys.exit(1 if cmd_check(a) else 0)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
