#!/usr/bin/env python3
"""weapongen.py - procedural turret + hardpoint sprites for a weapon, with the matching .wpn offsets.

    python weapongen.py --id xmpl_lance --size MEDIUM --kind cannon --barrels 2 --style midline --out-dir MyMod
    python weapongen.py --id xmpl_ray --size SMALL --kind beam --style hightech --out-dir MyMod --preview prev.png
    python weapongen.py --id xmpl_rack --size MEDIUM --kind missile --tubes 4 --style lowtech --out-dir MyMod --check

kinds: cannon (ballistic), gatling (ballistic rotary), beam (energy, slim emitter), emitter (energy bolt: stacked
coils), missile (rack with visible warheads). --seed varies the details; --variant varies the layout.

What vanilla weapon sprites look like (measured on all 275 vanilla turret/hardpoint sprites, 0.98a) and what this
script therefore draws: the gun itself seen from above, not a round turret base (the hull's turret cover is drawn by the
game). A narrow, mirror-symmetric stack of small mechanical parts - banded barrels, coils, fins, struts, clamps - each
separated by a dark 1 px line, with lots of transparent space between parts (median opaque coverage: turrets 25%,
hardpoints 44%). Busy at pixel level (edge density ~0.82, high-frequency energy ~0.13), luminance p5/mean/p95
~0.11/0.41/0.82, saturation ~0.18, rim brightness ~0.8 of the interior.

Sizes follow the vanilla medians: turrets are square, SMALL 26, MEDIUM 40, LARGE 68 px; hardpoints SMALL 16x28,
MEDIUM 24x43, LARGE 36x68. Every vanilla weapon sprite has an even width. The game centres both sprites on the weapon
slot, so muzzle offsets are measured from the sprite centre: x = forward (towards the top of the sprite), y = left.
Prints the .wpn fragment (sprites, offsets, angle offsets, barrelMode) to paste.
"""
import argparse
import json
import os
import sys
import zlib

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hullgen  # noqa: E402  (tone_match, alpha_bleed)

TURRET = {"SMALL": 26, "MEDIUM": 40, "LARGE": 68}
HARDPOINT = {"SMALL": (16, 28), "MEDIUM": (24, 43), "LARGE": (36, 68)}
SCALE = {"SMALL": 0.75, "MEDIUM": 1.0, "LARGE": 1.6}   # detail size multiplier per mount size
SS = 4                                                   # supersampling factor
TARGET = dict(p5=0.11, p95=0.83, mean=0.42, sat=0.18)    # vanilla weapon medians
INK = np.array([16, 16, 19], np.float32) / 255.0
PAL = {  # metal bands measured on vanilla hulls of each tech; paint/accent from vanilla weapon bands
    "lowtech": dict(metal_l=(200, 190, 180), metal_m=(141, 134, 130), metal_d=(76, 72, 70), paint=(178, 134, 108),
                    paint_d=(104, 76, 64), accent=(222, 160, 70), glow=(255, 160, 100)),
    "midline": dict(metal_l=(214, 210, 198), metal_m=(161, 158, 148), metal_d=(80, 78, 76), paint=(196, 176, 122),
                    paint_d=(106, 96, 70), accent=(232, 150, 60), glow=(255, 205, 120)),
    "hightech": dict(metal_l=(176, 182, 188), metal_m=(104, 108, 112), metal_d=(54, 56, 60), paint=(140, 166, 196),
                     paint_d=(78, 92, 110), accent=(110, 200, 240), glow=(130, 220, 255)),
}


def even(v):
    v = int(round(v))
    return v + (v % 2)


# ===================================================================================== signed distance helpers
def sd_box(x, y, x0, y0, x1, y1, r=0.0):
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    hx, hy = max(1e-3, (x1 - x0) / 2.0 - r), max(1e-3, (y1 - y0) / 2.0 - r)
    qx, qy = np.abs(x - cx) - hx, np.abs(y - cy) - hy
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r


def sd_ellipse(x, y, cx, cy, rx, ry):
    return (np.hypot((x - cx) / rx, (y - cy) / ry) - 1.0) * min(rx, ry)


def sd_segment(x, y, ax, ay, bx, by, r):
    px, py, vx, vy = x - ax, y - ay, bx - ax, by - ay
    t = np.clip((px * vx + py * vy) / max(1e-6, vx * vx + vy * vy), 0, 1)
    return np.hypot(px - vx * t, py - vy * t) - r


# ===================================================================================== the parts kit
class Kit:
    """Paints mechanical parts on a supersampled canvas in design units (final pixels): x from the centre line
    (+ = right), y from the top. Every part gets a dark ink outline first, so overlapping parts stay separated."""

    def __init__(self, W, H, style, rng, scale):
        self.W, self.H, self.rng, self.s = W, H, rng, scale
        self.pal = {k: np.array(v, np.float32) / 255.0 for k, v in PAL[style].items()}
        ny, nx = H * SS, W * SS
        xs = (np.arange(nx) + 0.5) / SS - W / 2.0
        ys = (np.arange(ny) + 0.5) / SS
        self.x, self.y = np.meshgrid(xs, ys)
        self.rgb = np.zeros((ny, nx, 3), np.float32)
        self.a = np.zeros((ny, nx), np.float32)
        self.emi = np.zeros((ny, nx), np.float32)
        cells = rng.random((H + 2, W + 2)).astype(np.float32) * 2 - 1    # 1 px value noise ("paint texture")
        self.noise = np.kron(cells, np.ones((SS, SS), np.float32))[:ny, :nx]

    def c(self, name):
        return self.pal[name] if isinstance(name, str) else np.array(name, np.float32)

    def _fill(self, d, shade, color, ink=0.6, emissive=False, noise=0.05):
        if ink > 0:
            m = d < ink
            self.rgb[m] = INK
            self.a[m] = 1.0
            self.emi[m] = 0.0
        m = d < 0
        col = self.c(color)[None, None, :] * (shade * (1.0 + noise * self.noise))[..., None]
        self.rgb[m] = np.clip(col[m], 0, 1)
        self.a[m] = 1.0
        self.emi[m] = 1.0 if emissive else 0.0

    # --- primitives (mirror=True also draws the part mirrored across the centre line)
    def cyl(self, x0, y0, x1, y1, color, mirror=False, ink=0.6, r=None, ribs=0):
        """Vertical cylinder seen from above: bright along its axis, dark at both sides; `ribs` dark rings across."""
        for (a, b) in self._mir(x0, x1, mirror):
            rr = (b - a) * 0.3 if r is None else r
            d = sd_box(self.x, self.y, a, y0, b, y1, rr)
            t = np.clip((self.x - (a + b) / 2.0) / max(0.5, (b - a) / 2.0), -1, 1)
            shade = 0.34 + 0.62 * np.sqrt(np.clip(1 - t * t, 0, 1)) + 0.22 * np.exp(-((t + 0.12) / 0.22) ** 2)
            if ribs:
                ph = (self.y - y0) / max(1e-3, (y1 - y0)) * ribs
                shade = shade * np.where((ph % 1.0) < 0.28, 0.62, 1.0)
            self._fill(d, shade, color, ink)

    def cluster(self, half_w, y0, y1, variant, accent=True):
        """A mechanism body made of rounded parts (what vanilla gun bodies look like), never one flat slab."""
        hw, h = half_w, y1 - y0
        s = self.s
        if variant % 3 == 0:  # twin tanks around a ribbed core
            self.cyl(hw * 0.45, y0 + h * 0.10, hw, y1 - h * 0.12, "metal_m", mirror=True, ribs=int(2 + 2 * s))
            self.cyl(-hw * 0.55, y0, hw * 0.55, y1, "metal_l", ribs=int(3 + 2 * s))
            if accent:
                self.box(-hw * 0.42, y0 + h * 0.30, hw * 0.42, y0 + h * 0.30 + 1.2 * s + 0.4, "accent", r=0.3, bevel=False)
        elif variant % 3 == 1:  # stepped housing: wide rear, narrower front, side clamps
            self.cyl(-hw, y0 + h * 0.45, hw, y1, "metal_m", ribs=int(1 + s))
            self.cyl(-hw * 0.70, y0, hw * 0.70, y0 + h * 0.55, "metal_l", ribs=int(2 + s))
            self.box(hw * 0.62, y0 + h * 0.15, hw * 0.95, y0 + h * 0.42, "paint", mirror=True, r=0.4, bevel=False)
            if accent:
                self.box(-hw * 0.5, y0 + h * 0.48, hw * 0.5, y0 + h * 0.48 + 1.1 * s + 0.4, "accent", r=0.3, bevel=False)
        else:  # four small cylinders in a block with a capped centre
            for fx in (0.25, 0.75):
                self.cyl(hw * (fx - 0.24), y0 + h * 0.05, hw * (fx + 0.24), y1, "metal_m", mirror=True, ribs=int(2 + s))
            self.cyl(-hw * 0.28, y0 - h * 0.05, hw * 0.28, y1 - h * 0.15, "metal_l")
            if accent:
                self.dot(0, y0 + h * 0.45, max(0.8, hw * 0.16), "accent")
        self.dot(hw * 0.78, y1 - 1.2, 0.45 * s + 0.15, "metal_l", mirror=True)

    def box(self, x0, y0, x1, y1, color, mirror=False, ink=0.6, r=0.5, bevel=True):
        """Flat plate: 1 px highlight just inside the edge, a darker groove, then the face."""
        for (a, b) in self._mir(x0, x1, mirror):
            d = sd_box(self.x, self.y, a, y0, b, y1, r)
            e = -d
            shade = np.full(d.shape, 0.80, np.float32)
            if bevel and min(b - a, y1 - y0) > 2.5:
                shade = np.where(e < 0.7, 1.02, np.where(e < 1.5, 0.66, 0.80))
            self._fill(d, shade, color, ink)

    def bands(self, x0, y0, x1, y1, n, color_a, color_b, mirror=False):
        """A stack of n coils/rings between y0 and y1, alternating colours, inked between."""
        h = (y1 - y0) / float(n)
        for i in range(n):
            self.cyl(x0, y0 + i * h, x1, y0 + (i + 1) * h - 0.25, color_a if i % 2 == 0 else color_b, mirror,
                     ink=0.45, r=0.4)

    def taper(self, y0, y1, w0, w1, n, color_a, color_b):
        """Coils whose width goes from w0 (at y0) to w1 (at y1): the stacked look of vanilla pulse weapons."""
        h = (y1 - y0) / float(n)
        for i in range(n):
            w = w0 + (w1 - w0) * (i + 0.5) / n
            self.cyl(-w / 2, y0 + i * h, w / 2, y0 + (i + 1) * h - 0.3, color_a if i % 2 == 0 else color_b,
                     ink=0.5, r=min(1.2, w * 0.25))

    def leg(self, ax, ay, bx, by, w, color, mirror=True):
        for sgn in ((1, -1) if mirror else (1,)):
            d = sd_segment(self.x, self.y, ax * sgn, ay, bx * sgn, by, w / 2.0)
            vx, vy = bx * sgn - ax * sgn, by - ay
            ln = max(1e-6, np.hypot(vx, vy))
            t = np.clip(((self.x - ax * sgn) * (-vy) + (self.y - ay) * vx) / ln / (w / 2.0), -1, 1)
            shade = 0.38 + 0.58 * np.sqrt(np.clip(1 - t * t, 0, 1))
            self._fill(d, shade, color, 0.5)

    def dome(self, cx, cy, rx, ry, color, emissive=False, mirror=False, ink=0.5):
        for sx in ((cx, -cx) if mirror and abs(cx) > 1e-3 else (cx,)):
            d = sd_ellipse(self.x, self.y, sx, cy, rx, ry)
            rr = np.clip(np.hypot((self.x - sx) / rx, (self.y - cy) / ry), 0, 1)
            shade = (1.15 - 0.45 * rr) if emissive else (0.40 + 0.62 * np.sqrt(np.clip(1 - rr * rr, 0, 1)))
            self._fill(d, shade, color, ink, emissive=emissive, noise=0.0 if emissive else 0.05)

    def slits(self, x0, y0, x1, y1, n, color="metal_d", horizontal=True, mirror=False):
        """Thin dark vents (no ink): n lines across a part."""
        for (a, b) in self._mir(x0, x1, mirror):
            for i in range(n):
                if horizontal:
                    yy = y0 + (i + 0.5) * (y1 - y0) / n
                    d = sd_box(self.x, self.y, a + 0.6, yy - 0.28, b - 0.6, yy + 0.28, 0)
                else:
                    xx = a + (i + 0.5) * (b - a) / n
                    d = sd_box(self.x, self.y, xx - 0.28, y0 + 0.6, xx + 0.28, y1 - 0.6, 0)
                self._fill(d, np.full(d.shape, 0.55, np.float32), color, ink=0)

    def dot(self, x, y, r, color, emissive=False, mirror=False):
        self.dome(x, y, r, r, color, emissive, mirror, ink=0.35 if not emissive else 0.3)

    @staticmethod
    def _mir(x0, x1, mirror):
        out = [(x0, x1)]
        if mirror and abs(x0 + x1) > 1e-3:
            out.append((-x1, -x0))
        return out

    # --- output
    def finish(self, target=TARGET):
        H, W = self.H, self.W
        A = self.a.reshape(H, SS, W, SS).mean(axis=(1, 3))
        pre = (self.rgb * self.a[..., None]).reshape(H, SS, W, SS, 3).mean(axis=(1, 3))
        rgb = pre / np.maximum(A, 1e-4)[..., None]
        emi = self.emi.reshape(H, SS, W, SS).mean(axis=(1, 3))
        lum = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
        pad = np.pad(lum, 1, mode="edge")
        blur = sum(pad[i:i + H, j:j + W] for i in range(3) for j in range(3)) / 9.0
        rgb = np.clip(rgb + 0.55 * (lum - blur)[..., None], 0, 1)          # unsharp: crisp 1 px detail
        opaque = A > 0.5
        inner = opaque.copy()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            inner &= np.roll(np.roll(opaque, dy, 0), dx, 1)
        rgb[opaque & ~inner] *= 0.86                                         # vanilla rim ~0.8 of interior
        rgb = hullgen.tone_match(rgb, A, emi, target)
        A = np.where(A < 0.1, 0.0, np.where(A > 0.9, 1.0, A))
        out = np.concatenate([rgb, A[..., None]], axis=2)
        im = Image.fromarray(np.clip(out * 255 + 0.5, 0, 255).astype(np.uint8), "RGBA")
        return hullgen.alpha_bleed(im)


# ===================================================================================== compositions
def compose(kind, size, mount, barrels, tubes, style, seed, variant):
    rng = np.random.default_rng(seed * 7919 + {"TURRET": 0, "HARDPOINT": 1}[mount])
    lay = np.random.default_rng(variant * 104729 + zlib.crc32(kind.encode()))  # layout shared by both mounts
    if mount == "TURRET":
        W = H = even(TURRET[size])
    else:
        W, H = HARDPOINT[size]
        W = even(W)
    s = SCALE[size]
    k = Kit(W, H, style, rng, s)
    hp = mount == "HARDPOINT"
    body_variant = int(lay.integers(0, 3))
    muzzles = []
    tip = 1.0
    xm = W / 2.0 - 1.0          # keep 1 px clear of the sprite edge so every part keeps its dark outline
    ym = H - 1.0
    if kind in ("cannon", "gatling"):
        n = max(1, barrels)
        if kind == "gatling":
            n = max(3, n)
        rb = (1.15 if kind == "cannon" else 0.75) * s + (0.4 if n == 1 and kind == "cannon" else 0)
        gap = 2 * rb + (0.9 if kind == "gatling" else 1.6 * s)
        span = (n - 1) * gap / 2.0
        breech = H * (0.54 if hp else 0.48)
        body_bot = min(ym, H * (0.97 if hp else 0.82))
        half = min(xm, max(span + rb * 2.6, W * (0.40 if hp else 0.24)))
        if not hp:  # short, thick mount struts tucked under the body
            k.leg(half * 0.55, body_bot - 2.0 * s, min(xm - 1, half * 1.25), min(ym, body_bot + 3.0 * s), 1.8 * s, "metal_d")
            k.dot(min(xm - 1, half * 1.25), min(ym - 0.8, body_bot + 3.0 * s), 0.8 * s, "metal_m", mirror=True)
        if kind == "cannon" and (not hp or W >= 24):  # ammo feed / cooling packs on the sides
            fw = max(1.8, 1.6 * s)
            k.cyl(half - 0.2, breech + H * 0.05, min(xm, half - 0.2 + fw), body_bot - H * 0.10, "metal_d", mirror=True,
                  ribs=int(3 + 2 * s))
        k.cluster(half, breech - 0.5, body_bot, body_variant)
        for i in range(n):
            x = -span + i * gap
            k.cyl(x - rb, tip + 1.5, x + rb, breech + 0.5, "metal_l", ribs=int(2 + 3 * s) if kind == "cannon" else 0)
            muzzles.append((x, tip))
        if kind == "cannon":
            for i in range(n):  # muzzle brakes and heat shrouds
                x = -span + i * gap
                k.box(x - rb * 1.45, tip, x + rb * 1.45, tip + 1.8 * s + 0.6, "metal_m", r=0.3, bevel=False)
                sh0 = tip + (breech - tip) * (0.46 if not hp else 0.50)
                k.cyl(x - rb * 1.35, sh0, x + rb * 1.35, breech, "metal_m", ribs=int(2 + 2 * s))
            k.box(-span - rb * 1.9, breech - 1.4 * s, span + rb * 1.9, breech + 1.0 * s, "accent", r=0.4, bevel=False)
        else:
            for f in (0.06, 0.40, 0.72):  # clamp rings across the barrel cluster
                y = tip + (breech - tip) * f
                k.box(-span - rb * 1.6, y, span + rb * 1.6, y + 1.2 * s + 0.4, "accent" if f > 0.3 else "metal_m",
                      r=0.3, bevel=False)
    elif kind == "beam":
        rod = 0.9 * s
        breech = H * (0.58 if hp else 0.50)
        body_bot = min(ym, H * (0.97 if hp else 0.80))
        half = min(xm, W * (0.40 if hp else 0.22))
        if not hp:
            k.leg(half * 0.55, body_bot - 2.0 * s, min(xm - 1, half * 1.4), min(ym, body_bot + 3.0 * s), 1.6 * s, "metal_d")
        cap = max(1.6, 1.4 * s)
        k.cyl(half - 0.4, breech - H * 0.06, min(xm, half - 0.4 + cap), body_bot - H * 0.12, "metal_m", mirror=True, ribs=3)
        k.dot(half - 0.4 + cap / 2, breech - H * 0.03, 0.45 * s, "glow", emissive=True, mirror=True)
        k.cluster(half, breech, body_bot, body_variant, accent=False)
        k.cyl(-rod, tip + 2.2 * s, rod, breech + 0.5, "metal_l")
        k.bands(-rod * 2.0, tip + (breech - tip) * 0.30, rod * 2.0, breech - 0.5, int(3 + 2 * s), "accent", "metal_d")
        k.box(-rod * 1.8, tip + 0.6 * s, rod * 1.8, tip + 2.6 * s, "metal_d", r=0.5, bevel=False)
        k.dome(0, tip + 1.2 * s, rod * 1.15, 1.0 * s, "glow", emissive=True)
        muzzles.append((0.0, tip))
    elif kind == "emitter":
        breech = H * (0.62 if hp else 0.58)
        body_bot = min(ym, H * (0.97 if hp else 0.82))
        w_base = min(2 * xm, W * (0.72 if hp else 0.38))
        w_tip = W * (0.34 if hp else 0.16)
        if not hp:
            k.leg(w_base * 0.30, body_bot - 2.0 * s, min(xm - 1, w_base * 0.62), min(ym, body_bot + 3.0 * s), 1.7 * s, "metal_d")
            for fy in np.linspace(breech + 1.5, body_bot - 2.5, int(2 + s)):  # side cooling fins
                k.box(w_base * 0.46, fy, min(xm, w_base * 0.46 + W * 0.09), fy + 0.9 * s, "metal_m", mirror=True,
                      r=0.2, bevel=False)
        k.cluster(w_base / 2, breech - 1.0, body_bot, body_variant, accent=False)
        k.dot(0, (breech + body_bot) / 2, 0.9 * s, "glow", emissive=True)
        k.taper(tip + 1.6 * s, breech, w_tip, w_base * 0.80, int(4 + 2 * s), "accent", "metal_m")
        k.dome(0, tip + 1.2 * s, w_tip * 0.42, 1.1 * s, "glow", emissive=True)
        muzzles.append((0.0, tip))
    elif kind == "missile":
        n = max(1, tubes)
        cols = 1 if n == 1 else (2 if n <= 4 or hp else 3)
        rows = (n + cols - 1) // cols
        frame_w = min(2 * xm, W * (0.74 if hp else 0.64))
        top = H * (0.06 if hp else 0.16)
        bot = min(ym, H * (0.80 if hp else 0.78))
        if not hp:
            k.leg(frame_w * 0.20, bot - 1.0, min(xm - 1, frame_w * 0.42), min(ym, bot + 3.0 * s), 1.7 * s, "metal_d")
        cw = frame_w / cols
        gapw = max(1.5, 1.4 * s)
        for c in range(cols):  # one pod per column, with a gap between pods
            x0 = -frame_w / 2 + c * cw + gapw / 2
            k.box(x0, top, x0 + cw - gapw, bot, "metal_m", r=0.8)
        k.box(-frame_w / 2 - 0.4, (top + bot) / 2 - 1.0 * s, frame_w / 2 + 0.4, (top + bot) / 2 + 1.0 * s, "accent",
              r=0.3, bevel=False)  # strap across the pods
        rh = (bot - top) / rows
        for i in range(n):
            c, rr = i % cols, i // cols
            cx = -frame_w / 2 + (c + 0.5) * cw
            y0, y1 = top + rr * rh + 0.8, top + (rr + 1) * rh - 0.8
            tw = min((cw - gapw) * 0.66, 3.2 * s + 1.0)
            k.box(cx - tw / 2, y0, cx + tw / 2, y1, (0.10, 0.10, 0.11), r=tw * 0.3, bevel=False)   # tube mouth
            mh = min(y1 - y0 - 1.0, tw * 1.6)
            k.cyl(cx - tw * 0.32, y0 + 0.6, cx + tw * 0.32, y0 + 0.6 + mh, "metal_l")             # warhead
            k.dome(cx, y0 + 0.9, tw * 0.26, min(1.2 * s, mh * 0.3), "accent")                    # nose cap
            muzzles.append((cx, y0 + 0.5))
    else:
        raise SystemExit("unknown kind %r" % kind)
    return k, muzzles


def offsets(muzzles, H):
    offs, angs = [], []
    for x, y in muzzles:
        offs += [round(H / 2.0 - y, 1) + 0.0, round(-x, 1) + 0.0]   # x = forward (up from the centre), y = left
        angs.append(0)
    return offs, angs


def stats_line(im):
    import sprite_stats
    m = sprite_stats.measure(im)
    if not m:
        return "too small to measure"
    cov = (np.asarray(im)[..., 3] > 128).mean()
    return ("lum %.2f/%.2f/%.2f (vanilla .11/.41/.82)  sat %.2f (.18)  edges %.2f (.82)  hf %.3f (.13)  rim %.2f (.80)"
            "  coverage %.2f (turret .25 / hardpoint .44)" % (m["lum_p5"], m["lum_mean"], m["lum_p95"], m["sat_mean"],
                                                             m["edge_density"], m["hf_energy"], m["rim_ratio"], cov))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--id", required=True)
    ap.add_argument("--size", choices=["SMALL", "MEDIUM", "LARGE"], default="SMALL")
    ap.add_argument("--kind", choices=["cannon", "gatling", "beam", "emitter", "missile"], default="cannon")
    ap.add_argument("--barrels", type=int, default=1)
    ap.add_argument("--tubes", type=int, default=2)
    ap.add_argument("--style", choices=sorted(PAL), default="midline")
    ap.add_argument("--seed", type=int, default=1, help="varies small details")
    ap.add_argument("--variant", type=int, default=1, help="varies layout choices")
    ap.add_argument("--out-dir", default=".")
    ap.add_argument("--subdir", default="graphics/weapons", help="sprite folder inside the mod")
    ap.add_argument("--preview", help="write a 4x preview PNG of both sprites")
    ap.add_argument("--check", action="store_true", help="print each sprite's stats next to the vanilla medians")
    a = ap.parse_args()
    frag, previews = {}, []
    for mount, key in (("TURRET", "turret"), ("HARDPOINT", "hardpoint")):
        kit, muzzles = compose(a.kind, a.size, mount, a.barrels, a.tubes, a.style, a.seed, a.variant)
        im = kit.finish()
        rel = "%s/%s_%s.png" % (a.subdir, a.id, key)
        p = os.path.join(a.out_dir, rel)
        os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
        im.save(p)
        previews.append(im)
        offs, angs = offsets(muzzles, im.height)
        frag[key + "Sprite"] = rel
        frag[key + "Offsets"] = offs
        frag[key + "AngleOffsets"] = angs
        print("wrote %s (%dx%d)" % (p, im.width, im.height))
        if a.check:
            print("   " + stats_line(im))
    if a.preview:
        s = 4
        tot_w = sum(im.width * s + 16 for im in previews) + 16
        tot_h = max(im.height * s for im in previews) + 32
        import contact_sheet
        sheet = contact_sheet.starfield(tot_w, tot_h).convert("RGBA")
        x = 16
        for im in previews:
            sheet.alpha_composite(im.resize((im.width * s, im.height * s), Image.NEAREST), (x, 16))
            x += im.width * s + 16
        sheet.convert("RGB").save(a.preview)
        print("wrote", a.preview)
    frag["barrelMode"] = "ALTERNATING" if len(frag["turretAngleOffsets"]) > 1 else "LINKED"
    print("Paste into %s.wpn:" % a.id)
    print(json.dumps(frag, indent=4))


if __name__ == "__main__":
    main()
