#!/usr/bin/env python3
"""hullgen.py - procedural Starsector hull sprite + matching .ship geometry (+ optional GraphicsLib maps).

    python hullgen.py --example frigate > my_ship.json      # starter specs: frigate|destroyer|cruiser|capital
    python hullgen.py my_ship.json --out-dir path/to/MyMod   # writes graphics/ships/<id>.png + data/hulls/<id>.ship
    python hullgen.py my_ship.json --out-dir MyMod --maps    # + GraphicsLib normal/material/surface maps
    python hullgen.py my_ship.json --out-dir MyMod --preview # + <spec>_preview.png (2x, with slot overlay)

Why it looks the way it does (measured on the 0.98a vanilla hulls; see references/sprites.md):
  * Two materials: smooth painted PLATES on top of dense grey MACHINERY (pipes, tanks, vents, boxes).
  * No baked directional light: shading is overhead (slopes darken symmetrically) plus crevice AO,
    convex-edge highlights and a dark silhouette rim (vanilla rim/interior luminance ~0.6).
  * Near-perfect left/right symmetry: the right half is a mirror of the left ("symmetric": false to opt out).
  * Final tonal range matched to vanilla per tech style (luminance p5/p95 and mean saturation).

Spec coordinates are DESIGN units, which are final pixels: x = lateral offset from the centre line (+ = image right),
y = distance from the TOP edge. Ships face up. Slot angles use the .ship convention (0 = forward, +90 = left).
Minimal spec: "size", "style", hull "parts" (the silhouette), "auto_plates", "slots", "engines".
Print an example (--example cruiser) to see every key.
"""
import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sslib  # noqa: E402

SS = 4  # supersampling factor

# Palettes sampled from vanilla sprites (albedo a little brighter than the measured shaded mid-tones).
# target = vanilla median luminance p5/p95 and mean saturation per tech at 1x (opaque pixels).
STYLES = {
    "lowtech": dict(paint=(168, 122, 98), paint2=(150, 120, 92), accent=(206, 168, 76), metal=(168, 160, 154),
                    dark=(58, 54, 52), glow=(240, 150, 100), engine=(255, 170, 110), glass=(90, 120, 130),
                    ship_style="LOW_TECH", target=dict(p5=0.109, p95=0.763, mean=0.408, sat=0.299)),
    "midline": dict(paint=(186, 168, 120), paint2=(150, 156, 156), accent=(96, 150, 176), metal=(186, 182, 172),
                    dark=(62, 60, 58), glow=(236, 200, 110), engine=(255, 205, 130), glass=(80, 130, 150),
                    ship_style="MIDLINE", target=dict(p5=0.125, p95=0.835, mean=0.470, sat=0.187)),
    "hightech": dict(paint=(140, 156, 176), paint2=(108, 118, 134), accent=(120, 210, 240), metal=(122, 125, 126),
                     dark=(40, 42, 46), glow=(120, 215, 255), engine=(140, 205, 255), glass=(70, 140, 170),
                     ship_style="HIGH_TECH", target=dict(p5=0.105, p95=0.760, mean=0.421, sat=0.126)),
}
SOCKET_R = {"SMALL": 5.0, "MEDIUM": 8.0, "LARGE": 12.0}
ENGINE_DEFAULTS = {"FRIGATE": (8, 24), "DESTROYER": (12, 48), "CRUISER": (16, 56), "CAPITAL_SHIP": (16, 48)}
DETAIL_SCALE = {"FRIGATE": 1.0, "DESTROYER": 1.1, "CRUISER": 1.25, "CAPITAL_SHIP": 1.4}
CLS_NONE, CLS_MACH, CLS_PLATE, CLS_TRIM, CLS_GLASS, CLS_SOCKET = 0, 1, 2, 3, 4, 5


# ------------------------------------------------------------------ numeric helpers
def box_blur(a, r):
    """Separable box blur via cumulative sums (fast, float-exact)."""
    r = int(max(1, round(r)))
    out = a.astype(np.float32)
    for axis in (0, 1):
        pad = [(0, 0), (0, 0)]
        pad[axis] = (r + 1, r)
        p = np.pad(out, pad, mode="edge")
        c = np.cumsum(p, axis=axis, dtype=np.float64)
        if axis == 0:
            out = ((c[2 * r + 1:, :] - c[:-2 * r - 1, :]) / (2 * r + 1)).astype(np.float32)
        else:
            out = ((c[:, 2 * r + 1:] - c[:, :-2 * r - 1]) / (2 * r + 1)).astype(np.float32)
    return out


def blur(a, sigma):
    """Approximate Gaussian: three box passes."""
    if sigma < 0.5:
        return a.astype(np.float32)
    r = max(1, int(round(sigma * 0.85)))
    return box_blur(box_blur(box_blur(a, r), r), r)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0 + 1e-9), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def value_noise(h, w, cell, rng):
    gh, gw = max(2, int(h / cell) + 2), max(2, int(w / cell) + 2)
    g = (rng.random((gh, gw)) * 255).astype(np.uint8)
    return np.asarray(Image.fromarray(g, "L").resize((w, h), Image.BICUBIC), np.float32) / 255.0


def erode(mask_bool, r):
    if r < 1:
        return mask_bool.copy()
    im = Image.fromarray((mask_bool * 255).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.MinFilter(2 * int(r) + 1))) > 127


# ------------------------------------------------------------------ the hull canvas
class Hull:
    def __init__(self, spec):
        self.spec = spec
        self.W, self.H = int(spec["size"][0]), int(spec["size"][1])
        if self.W % 2:
            print("warning: odd sprite width %d; even widths keep the centre line on a pixel edge" % self.W)
        self.w, self.h = self.W * SS, self.H * SS
        style = spec.get("style", "midline")
        self.pal = dict(STYLES.get(style, STYLES["midline"]))
        for k, v in (spec.get("palette") or {}).items():
            self.pal[k] = tuple(v) if isinstance(v, (list, tuple)) else v
        self.rng = np.random.default_rng(int(spec.get("seed", 1)))
        self.ds = float(spec.get("detail_scale", DETAIL_SCALE.get(spec.get("hullSize", "FRIGATE"), 1.0)))
        shp = (self.h, self.w)
        self.M = np.zeros(shp, np.float32)           # coverage
        self.Hh = np.zeros(shp, np.float32)          # height
        self.ALB = np.zeros(shp + (3,), np.float32)  # albedo 0..1
        self.MET = np.zeros(shp, np.float32)         # metalness (edge highlight colour, surface map)
        self.GLS = np.zeros(shp, np.float32)         # gloss
        self.EMI = np.zeros(shp + (3,), np.float32)  # emissive
        self.GRV = np.zeros(shp, np.float32)         # engraved line darkening
        self.CLS = np.zeros(shp, np.int8)
        self.PIL = np.zeros(shp, np.float32)         # plate curvature profile (0 edge .. 1 centre)
        self.plate_count = 0

    def P(self, x, y):
        return ((self.W / 2.0 + x) * SS, y * SS)

    def col(self, c):
        if isinstance(c, str):
            c = self.pal[c]
        return np.array(c, np.float32) / 255.0

    # ---- rasterise one spec shape (with optional mirror copy) to a float mask at SS resolution
    def raster(self, part):
        im = Image.new("L", (self.w, self.h), 0)
        d = ImageDraw.Draw(im)
        for mir in ([False, True] if part.get("sym") else [False]):
            sx = -1 if mir else 1
            s = part["shape"]
            if s == "poly":
                d.polygon([self.P(sx * x, y) for x, y in part["pts"]], fill=255)
            elif s in ("rect", "rrect"):
                x0, y0, x1, y1 = part["box"]
                if mir:
                    x0, x1 = -x1, -x0
                a, b = self.P(min(x0, x1), min(y0, y1)), self.P(max(x0, x1), max(y0, y1))
                box = [a[0], a[1], b[0] - 1, b[1] - 1]
                if s == "rect":
                    d.rectangle(box, fill=255)
                else:
                    d.rounded_rectangle(box, radius=part.get("r", 2) * SS, fill=255)
            elif s == "ellipse":
                cx, cy = part["c"]
                rx, ry = part["r"] if isinstance(part["r"], (list, tuple)) else (part["r"], part["r"])
                c = self.P(sx * cx, cy)
                d.ellipse([c[0] - rx * SS, c[1] - ry * SS, c[0] + rx * SS, c[1] + ry * SS], fill=255)
            elif s == "capsule":
                (ax, ay), (bx, by) = part["a"], part["b"]
                r = part["r"]
                pa, pb = self.P(sx * ax, ay), self.P(sx * bx, by)
                d.line([pa, pb], fill=255, width=int(2 * r * SS))
                for p in (pa, pb):
                    d.ellipse([p[0] - r * SS, p[1] - r * SS, p[0] + r * SS, p[1] + r * SS], fill=255)
            else:
                raise ValueError("unknown shape %r" % s)
        return np.asarray(im, np.float32) / 255.0

    # ---- layers
    def add_part(self, part):
        layer = part.get("layer", "plate")
        m = self.raster(part)
        sel = m > 0.5
        if layer == "cut":
            self.M[sel] = 0
            self.CLS[sel] = CLS_NONE
            self.Hh[sel] = 0
            return
        if layer in ("hull", "machinery"):
            self.M = np.maximum(self.M, m)
            if layer == "hull":
                sel = sel & (self.CLS == CLS_NONE)
            self.set_machinery(sel, part.get("z", 0.22), part.get("paint", "metal"))
            return
        if layer in ("plate", "trim", "glass"):
            self.M = np.maximum(self.M, m)
            self.plate_from_mask(sel, layer, part)
            return
        if layer == "stripe":  # recolour existing plate pixels, no height change
            s2 = sel & (self.CLS == CLS_PLATE)
            self.ALB[s2] = self.col(part.get("paint", "accent"))
            return
        raise ValueError("unknown layer %r" % layer)

    def set_machinery(self, sel, z=0.22, paint="metal"):
        self.CLS[sel] = CLS_MACH
        self.Hh[sel] = z
        self.ALB[sel] = self.col(paint) * 0.85
        self.MET[sel] = 0.8
        self.GLS[sel] = 0.0

    def plate_from_mask(self, sel, layer="plate", opts=None):
        opts = opts or {}
        ys, xs = np.nonzero(sel)
        if len(xs) == 0:
            return
        self.plate_count += 1
        k = self.plate_count
        m = sel.astype(np.float32)
        base_z = opts.get("z", {"plate": 0.55, "trim": 0.62, "glass": 0.60}[layer] + 0.012 * (k % 8))
        bevel = float(opts.get("bevel", 1.6 if layer != "trim" else 0.6))
        edge = smoothstep(0.5, 1.0, blur(m, bevel * SS * 0.8))
        extent = min(xs.max() - xs.min(), ys.max() - ys.min()) / SS
        dome = float(opts.get("dome", 0.25 if layer == "glass" else 0.20))
        pillow = smoothstep(0.42, 1.0, blur(m, max(2.0, min(extent * 0.28, 12)) * SS))
        hz = base_z + 0.10 * edge + dome * pillow
        self.PIL[sel] = (0.35 * edge + 0.65 * pillow)[sel]
        self.Hh[sel] = hz[sel]
        if layer == "plate":
            c = self.col(opts.get("paint", "paint"))
            self.CLS[sel] = CLS_PLATE
            self.MET[sel] = 0.15
            self.GLS[sel] = float(opts.get("gloss", 0.15))
            self.ALB[sel] = c * (1.0 + float(self.rng.uniform(-0.05, 0.05)))
            dens = float(opts.get("panels", self.spec.get("panels", 1.0)))
            if dens > 0:
                self.panel_lines(sel, dens)
        elif layer == "trim":
            self.CLS[sel] = CLS_TRIM
            self.ALB[sel] = self.col(opts.get("paint", "metal"))
            self.MET[sel] = 0.9
            self.GLS[sel] = 0.3
        else:
            self.CLS[sel] = CLS_GLASS
            self.ALB[sel] = self.col(opts.get("paint", "glass"))
            self.MET[sel] = 0.2
            self.GLS[sel] = 1.0

    # ---- automatic plating: inset the machinery silhouette, cut it into bands (+ optional spine), plate each band
    def auto_plates(self, cfg):
        """Plate part of the machinery silhouette automatically.

        The inset silhouette is cut into `bands` along chevron-shaped seams. Each band then gets a random pattern:
        full, inner (near the spine), outer (the flanks), split (two islands) or none (machinery stays exposed).
        The patterns are weighted so roughly `coverage` of the hull ends up plated. Corners are rounded.
        """
        hull = self.CLS == CLS_MACH
        region = erode(hull, float(cfg.get("inset", 2.5)) * SS)
        ys, xs = np.nonzero(region)
        if len(xs) == 0:
            return
        rng = self.rng
        cx = self.w / 2.0
        n = max(1, int(cfg.get("bands", 4)))
        gap = float(cfg.get("gap", 1.6)) * SS
        cov = float(cfg.get("coverage", 0.62))
        yy, xx = np.mgrid[0:self.h, 0:self.w]
        ax = np.abs(xx - cx + 0.5)
        maxhalf = float(ax[region].max()) if region.any() else 1.0
        slope = float(cfg.get("chevron", rng.uniform(-0.35, 0.35)))
        t = yy - slope * ax  # band coordinate: chevron seams
        t0, t1 = float(t[region].min()), float(t[region].max())
        cuts = [t0 - 1]
        for e in np.linspace(t0, t1, n + 1)[1:-1]:
            cuts.append(e + rng.uniform(-0.2, 0.2) * (t1 - t0) / n)
        cuts.append(t1 + 1)
        spine = float(cfg.get("spine", 0)) * SS
        skip = set(cfg.get("skip_bands", []))
        forced = {int(k): v for k, v in (cfg.get("patterns") or {}).items()}
        two = set(cfg.get("paint2_bands", []))
        pats = ["full", "inner", "outer", "split", "none"]
        w = np.array([0.45 * cov, 0.2, 0.2, 0.15, max(0.02, 0.45 * (1 - cov))])
        w = w / w.sum()
        round_r = float(cfg.get("round", 2.0)) * SS
        for i in range(n):
            if i in skip:
                continue
            band = region & (t > cuts[i] + gap / 2) & (t < cuts[i + 1] - gap / 2)
            if spine > 0:
                band &= ax > spine / 2
            pat = forced.get(i) or rng.choice(pats, p=w)
            f = rng.uniform(0.35, 0.65) * maxhalf
            if pat == "inner":
                band &= ax < f
            elif pat == "outer":
                band &= ax > f
            elif pat == "split":
                band &= (ax < f - gap / 2) | (ax > f + gap / 2)
            elif pat == "none":
                continue
            if round_r >= 1:
                band = (blur(band.astype(np.float32), round_r) > 0.5) & region
            if band.sum() < (3 * SS) ** 2:
                continue
            self.plate_from_mask(band, "plate", {"paint": "paint2" if i in two else cfg.get("paint", "paint"),
                                                 "panels": cfg.get("panels", self.spec.get("panels", 1.0))})

    # ---- small protrusions along the silhouette (vents, blisters, antennae) so the outline isn't a clean polygon
    def edge_greebles(self, n):
        inside = self.M > 0.5
        if n <= 0 or not inside.any():
            return
        b = blur(inside.astype(np.float32), 1.5 * SS)
        gy, gx = np.gradient(b)
        edge = inside & ~erode(inside, 1)
        edge[:, self.w // 2:] = False  # left half only; the mirror pass copies it
        ys, xs = np.nonzero(edge)
        if len(xs) == 0:
            return
        rng = self.rng
        for _ in range(int(n)):
            i = rng.integers(len(xs))
            x, y = xs[i], ys[i]
            ox, oy = -gx[y, x], -gy[y, x]
            L = math.hypot(ox, oy)
            if L < 1e-6:
                continue
            ox, oy = ox / L, oy / L
            if abs(oy) > 0.85:  # skip nose and tail tips
                continue
            ln = rng.uniform(1.5, 4.0) * SS * self.ds
            wd = rng.uniform(3.0, 7.0) * SS * self.ds
            cx, cy = x + ox * ln * 0.5, y + oy * ln * 0.5
            if abs(ox) >= abs(oy):
                box = (cx - ln * 0.75, cy - wd / 2, cx + ln * 0.75, cy + wd / 2)
            else:
                box = (cx - wd / 2, cy - ln * 0.75, cx + wd / 2, cy + ln * 0.75)
            x0, y0, x1, y1 = [int(v) for v in box]
            x0, y0, x1, y1 = max(0, x0), max(0, y0), min(self.w, x1), min(self.h, y1)
            if x1 <= x0 or y1 <= y0:
                continue
            sel = np.zeros_like(inside)
            yy, xx = np.mgrid[y0:y1, x0:x1]
            ex, ey = (x1 - x0) / 2.0, (y1 - y0) / 2.0
            if rng.random() < 0.5:  # rounded blister
                sel[y0:y1, x0:x1] = ((xx - x0 - ex) / ex) ** 2 + ((yy - y0 - ey) / ey) ** 2 <= 1.0
            else:  # squared vent block with softened corners
                sel[y0:y1, x0:x1] = ((np.abs(xx - x0 - ex) / ex) ** 4 + (np.abs(yy - y0 - ey) / ey) ** 4) <= 1.0
            sel &= (self.CLS == CLS_NONE) | (self.CLS == CLS_MACH)
            self.M[sel] = 1.0
            self.set_machinery(sel)

    # ---- engraved panel lines (minor) and seams (major), per-panel tone, hatches
    def panel_lines(self, sel, density):
        inner = erode(sel, 1.5 * SS)
        ys, xs = np.nonzero(inner)
        if len(xs) < 50:
            return
        y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
        minor = Image.new("L", (self.w, self.h), 0)
        major = Image.new("L", (self.w, self.h), 0)
        dmi, dma = ImageDraw.Draw(minor), ImageDraw.Draw(major)
        rng = self.rng
        cx = self.w / 2.0
        hs, vs = [], []
        y = y0 + rng.uniform(5, 12) * SS / density
        while y < y1:
            hs.append(y)
            big = rng.random() < 0.35
            dd, lw = (dma, SS) if big else (dmi, max(1, SS // 2))
            sx_ = x0
            while sx_ < x1:
                seg = rng.uniform(6, 20) * SS
                if big or rng.random() > 0.45:
                    dd.line([(sx_, y), (min(x1, sx_ + seg), y)], fill=255, width=lw)
                sx_ += seg
            y += rng.uniform(10, 22) * SS / density
        step = rng.uniform(9, 16) * SS / density
        for k in range(1, 40):
            off = k * step
            if cx - off < x0 and cx + off > x1:
                break
            big = rng.random() < 0.3
            dd, lw = (dma, SS) if big else (dmi, max(1, SS // 2))
            for xv in (cx - off, cx + off):
                if x0 < xv < x1:
                    vs.append(xv)
                    sy = y0
                    while sy < y1:
                        seg = rng.uniform(6, 22) * SS
                        if big or rng.random() > 0.3:
                            dd.line([(xv, sy), (xv, min(y1, sy + seg))], fill=255, width=lw)
                        sy += seg
        n_hatch = int((x1 - x0) * (y1 - y0) / (SS * SS) / 400 * density)
        for _ in range(n_hatch):
            hx, hy = rng.uniform(x0, x1), rng.uniform(y0, y1)
            hw, hh = rng.uniform(2, 4.5) * SS, rng.uniform(2, 5) * SS
            dmi.rectangle([hx, hy, hx + hw, hy + hh], outline=220, width=max(1, SS // 3))
        mi = np.asarray(minor, np.float32) / 255.0 * inner
        ma = np.asarray(major, np.float32) / 255.0 * inner
        self.GRV = np.maximum(self.GRV, np.maximum(mi * 0.55, ma))
        self.Hh[ma > 0.5] -= 0.07  # seams are real grooves: they catch AO and break the pillow
        if hs or vs:
            yb = np.searchsorted(np.array(sorted(hs)), np.arange(self.h))
            xb = np.searchsorted(np.array(sorted(vs)), np.abs(np.arange(self.w) - cx) + cx)
            cell = (yb[:, None] * 131 + xb[None, :] * 977 + self.plate_count * 31) % 1009
            tone = 0.93 + 0.14 * ((np.sin(cell * 12.9898) * 43758.5453) % 1.0)
            self.ALB[sel] *= tone[sel][:, None]

    # ---- machinery greebles (clipped to machinery pixels)
    def machinery(self, density):
        mach = self.CLS == CLS_MACH
        ys, xs = np.nonzero(mach)
        if len(xs) == 0:
            return
        self.ALB[mach] *= 0.62  # darker base: plates stand out and greebles read as depth
        area = mach.sum() / (SS * SS)
        rng = self.rng
        metal, paint, accent, dark = self.col("metal"), self.col("paint"), self.col("accent"), self.col("dark")
        ds2 = self.ds * self.ds
        # detail hierarchy (big shapes first, then medium, then small) reads far better at 1x than uniform noise
        tiers = [
            (area / (150.0 * ds2), ["longcyl", "bigtank", "ventbank"], [0.45, 0.30, 0.25], 1.0),
            (area / (7.0 * ds2), ["box", "cyl", "vent", "disc", "pipe", "tank"], [0.26, 0.28, 0.08, 0.12, 0.16, 0.10], 1.0),
            (area / (26.0 * ds2), ["bolt", "pipe", "box"], [0.5, 0.3, 0.2], 0.6),
        ]
        for _ in range(int(area / (230.0 * ds2) * density)):
            i = rng.integers(len(xs))
            kind = rng.choice(["cyl", "vent", "disc", "box", "tank"], p=[0.35, 0.2, 0.2, 0.15, 0.1])
            S = SS * self.ds
            if kind in ("disc", "tank"):
                w = h = int(rng.uniform(2.5, 5.5) * S)
            elif kind == "cyl":
                w, h = int(rng.uniform(1.6, 3.2) * S), int(rng.uniform(5, 11) * S)
            else:
                w, h = int(rng.uniform(2.5, 5) * S), int(rng.uniform(2.5, 6) * S)
            horiz = rng.random() < 0.6
            if kind == "cyl" and not horiz:
                w, h = h, w
            count = int(rng.integers(3, 7))
            step = (w if horiz else h) + int(rng.uniform(0.6, 1.5) * SS)
            c = metal * rng.uniform(0.65, 1.05) if kind != "vent" else dark * 1.4
            amp = rng.uniform(0.04, 0.1)
            for j in range(count):
                qx = xs[i] + (j * step if horiz else 0)
                qy = ys[i] + (0 if horiz else j * step)
                self.greeble(kind, qx, qy, c, mach, size=(w, h), amp=amp)
        for count, kinds, probs, scale in tiers:
            for _ in range(int(count * density)):
                i = rng.integers(len(xs))
                kind = rng.choice(kinds, p=probs)
                t = rng.random()
                if t < 0.10:
                    c = paint * 0.65 + metal * 0.35
                elif t < 0.14:
                    c = accent * 0.7 + metal * 0.3
                elif kind in ("vent", "ventbank"):
                    c = dark * 1.4
                else:
                    c = metal * rng.uniform(0.6, 1.12)
                self.greeble(kind, xs[i], ys[i], c, mach, scale=scale)

    # ---- details on plates: small raised boxes, discs, recessed vents and bolt heads
    def plate_details(self, density):
        plate = self.CLS == CLS_PLATE
        inner = erode(plate, 1.5 * SS)
        ys, xs = np.nonzero(inner)
        if len(xs) == 0 or density <= 0:
            return
        area = inner.sum() / (SS * SS)
        n = int(area / (60.0 * self.ds * self.ds) * density)
        rng = self.rng
        for _ in range(n):
            i = rng.integers(len(xs))
            px, py = xs[i], ys[i]
            kind = rng.choice(["box", "disc", "vent", "bolt", "cyl"], p=[0.35, 0.2, 0.15, 0.15, 0.15])
            base = self.ALB[py, px].copy()
            c = base * rng.uniform(0.75, 1.1) if kind != "vent" else self.col("dark") * 1.3
            if kind == "cyl":
                c = self.col("metal") * rng.uniform(0.7, 1.0)
            self.greeble(kind, px, py, c, inner, base_h=float(self.Hh[py, px]), scale=0.75)

    def greeble(self, kind, px, py, c, clip, base_h=None, scale=1.0, size=None, amp=None):
        rng = self.rng
        S = SS * self.ds * scale
        if kind == "longcyl":
            w, h = rng.uniform(3, 6) * S, rng.uniform(14, 40) * S
            kind = "cyl"
        elif kind == "bigtank":
            w = h = rng.uniform(9, 20) * S
            kind = "tank"
        elif kind == "ventbank":
            w, h = rng.uniform(6, 14) * S, rng.uniform(8, 18) * S
            kind = "vent"
        elif kind == "box":
            w, h = rng.uniform(1.5, 6) * S, rng.uniform(1.5, 6) * S
        elif kind == "tank":
            w = h = rng.uniform(4, 10) * S
        elif kind == "cyl":
            if rng.random() < 0.55:
                w, h = rng.uniform(1.4, 3.4) * S, rng.uniform(3, 12) * S
            else:
                w, h = rng.uniform(3, 12) * S, rng.uniform(1.4, 3.4) * S
        elif kind == "vent":
            w, h = rng.uniform(3, 8) * S, rng.uniform(3, 8) * S
        elif kind == "disc":
            w = h = rng.uniform(2, 6) * S
        elif kind == "pipe":
            if rng.random() < 0.5:
                w, h = rng.uniform(0.9, 1.5) * S, rng.uniform(5, 16) * S
            else:
                w, h = rng.uniform(5, 16) * S, rng.uniform(0.9, 1.5) * S
        else:  # bolt
            w = h = rng.uniform(0.8, 1.3) * SS
        if size:
            w, h = size
        w, h = max(2, int(w)), max(2, int(h))
        x0, y0 = int(px - w / 2), int(py - h / 2)
        x1, y1 = x0 + w, y0 + h
        if x0 < 0 or y0 < 0 or x1 > self.w or y1 > self.h:
            return
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        u = (xx + 0.5) / w * 2 - 1
        v = (yy + 0.5) / h * 2 - 1
        amp = rng.uniform(0.03, 0.11) if amp is None else amp
        mask = np.ones_like(u, bool)
        if kind == "box":
            e = np.minimum(1 - np.abs(u), 1 - np.abs(v)) * min(w, h) / (1.2 * SS)
            prof = 0.55 + 0.45 * np.clip(e, 0, 1)
            if rng.random() < 0.4:
                prof = prof * np.where(np.abs(v) < 0.08, 0.8, 1.0)
        elif kind == "tank":
            r2 = u * u + v * v
            mask = r2 <= 1
            prof = np.sqrt(np.clip(1 - r2, 0, 1)) * 0.9 + 0.1
            prof *= np.where(np.abs(np.sqrt(r2) - 0.62) < 0.06, 0.85, 1.0)
            amp *= 1.6
        elif kind in ("cyl", "pipe"):
            across, along = (u, v) if w < h else (v, u)
            prof = np.sqrt(np.clip(1 - across * across, 0, 1))
            if kind == "cyl":
                L = max(w, h) / SS
                prof = prof * np.where(np.cos(along * L * 1.6) > 0.82, 0.82, 1.0)
                prof *= np.clip((1 - np.abs(along)) * L * 0.5, 0.4, 1.0)
        elif kind == "vent":
            frame = (np.abs(u) > 0.8) | (np.abs(v) > 0.8)
            ribs = 0.5 + 0.5 * np.cos((v if w > h else u) * max(w, h) / SS * 2.4)
            prof = np.where(frame, 1.0, 0.25 + 0.35 * ribs)
        elif kind == "disc":
            r = np.sqrt(u * u + v * v)
            mask = r <= 1
            prof = np.where(r < 0.35, 1.0, np.where(np.abs(r - 0.7) < 0.12, 0.55, 0.8))
        else:  # bolt
            r2 = u * u + v * v
            mask = r2 <= 1
            prof = np.sqrt(np.clip(1 - r2, 0, 1))
            amp = 0.04
        cl = clip[y0:y1, x0:x1] & mask
        if not cl.any():
            return
        cur = self.Hh[y0:y1, x0:x1]
        if base_h is None:  # machinery
            newh = 0.22 + amp * prof + (0.02 if kind in ("pipe", "bolt") else 0.0)
            win = cl if kind == "vent" else cl & (newh > cur - 0.004)
        elif kind == "vent":  # recessed into a plate
            newh = base_h - 0.06 + 0.04 * prof
            win = cl
        else:  # raised detail on a plate
            newh = base_h + 0.6 * amp * prof
            win = cl
        cur[win] = newh[win]
        self.ALB[y0:y1, x0:x1][win] = c
        self.MET[y0:y1, x0:x1][win] = 0.85 if base_h is None or kind == "cyl" else 0.3

    # ---- weapon sockets
    def socket(self, slot):
        x, y = slot["pos"]
        mount = slot.get("mount", "TURRET")
        if mount == "HIDDEN":
            return
        r = float(slot.get("socket_r", SOCKET_R.get(slot.get("size", "SMALL"), 5.0)))
        for sx in ([1, -1] if slot.get("sym") else [1]):
            cx, cy = self.P(sx * x, y)
            R = r * SS
            x0, x1 = int(max(0, cx - R - 2 * SS)), int(min(self.w, cx + R + 2 * SS))
            y0, y1 = int(max(0, cy - R * 1.6 - 2 * SS)), int(min(self.h, cy + R + 2 * SS))
            yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
            dx, dy = (xx - cx) / R, (yy - cy) / R
            sl = (slice(y0, y1), slice(x0, x1))
            local = float(self.Hh[sl].max()) if self.Hh[sl].size else 0.5
            if mount == "TURRET":
                rr = np.sqrt(dx * dx + dy * dy)
                collar = (rr <= 1.18) & (rr > 0.92)
                well = rr <= 0.92
                ring = np.abs(rr - 0.58) < 0.09
                hub = rr < 0.26
                hz = np.where(collar, local + 0.04 + 0.03 * (1 - np.abs(rr - 1.05) / 0.13),
                              np.where(hub, local - 0.04, np.where(ring, local - 0.06, local - 0.11)))
                m = collar | well
                alb = np.where(collar[..., None], self.col("metal") * 0.95,
                               np.where((ring | hub)[..., None], self.col("metal") * 0.55, self.col("dark") * 0.8))
            else:  # HARDPOINT: rounded rectangular recess extending forward
                ax, ay = np.abs(dx), np.where(dy < 0, -dy / 1.5, dy)
                m = (ax <= 1.0) & (ay <= 1.0)
                frame = m & ((ax > 0.78) | (ay > 0.82))
                hz = np.where(frame, local + 0.04, local - 0.10)
                alb = np.where(frame[..., None], self.col("metal") * 0.95, self.col("dark") * 0.85)
            self.Hh[sl][m] = hz[m]
            self.ALB[sl][m] = alb[m]
            self.MET[sl][m] = 0.9
            self.CLS[sl][m] = CLS_SOCKET
            self.M[sl][m] = 1.0

    # ---- engine nozzles (visual only; the flame comes from the .ship engine slot)
    def nozzle(self, eng):
        x, y = eng["pos"]
        nw = float(eng.get("nozzle", max(3.0, float(eng.get("width", 8)) * 0.5)))
        nl = float(eng.get("nozzle_length", nw * 0.9))
        for sx in ([1, -1] if eng.get("sym") else [1]):
            m = self.raster(dict(shape="rrect", box=[sx * x - nw / 2, y - nl, sx * x + nw / 2, y],
                                 r=min(nw, nl) * 0.3)) > 0.5
            inner = self.raster(dict(shape="rrect", box=[sx * x - nw * 0.32, y - nl * 0.75, sx * x + nw * 0.32, y - 0.3],
                                     r=nw * 0.2)) > 0.5
            self.Hh[m] = 0.43
            self.ALB[m] = self.col("metal") * 0.8
            self.Hh[inner] = 0.30
            self.ALB[inner] = self.col("dark") * 0.7
            self.MET[m] = 0.9
            self.CLS[m] = CLS_TRIM
            self.M[m] = 1.0
            self.light_at(sx * x, y - 0.8, "engine", r=nw * 0.22, strength=0.45)

    def light_at(self, x, y, color, r=0.9, strength=1.0):
        cx, cy = self.P(x, y)
        R = max(0.5, r) * SS
        x0, x1 = int(max(0, cx - 4 * R)), int(min(self.w, cx + 4 * R))
        y0, y1 = int(max(0, cy - 4 * R)), int(min(self.h, cy + 4 * R))
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        a = np.maximum(np.clip(1 - dist / R, 0, 1), np.clip(1 - dist / (R * 3.5), 0, 1) ** 2 * 0.4) * strength
        self.EMI[y0:y1, x0:x1] = np.maximum(self.EMI[y0:y1, x0:x1], a[..., None] * self.col(color)[None, None, :])

    # ---- build everything
    def build(self):
        sp = self.spec
        for part in sp.get("parts", []):
            self.add_part(part)
        if sp.get("auto_plates"):
            self.auto_plates(sp["auto_plates"])
        self.edge_greebles(float(sp.get("edge_greebles", 0.05 * self.H / self.ds)))
        self.machinery(float(sp.get("machinery", 1.0)))
        self.plate_details(float(sp.get("plate_detail", 1.0)))
        for s in sp.get("slots", []):
            self.socket(s)
        for e in sp.get("engines", []):
            self.nozzle(e)
        for lt in sp.get("lights", []):
            for sx in ([1, -1] if lt.get("sym") else [1]):
                self.light_at(sx * lt["pos"][0], lt["pos"][1], lt.get("color", "glow"), lt.get("r", 0.8),
                              lt.get("strength", 1.0))
        if sp.get("symmetric", True):
            half = self.w // 2
            for arr in (self.M, self.Hh, self.ALB, self.MET, self.GLS, self.EMI, self.GRV, self.CLS, self.PIL):
                arr[:, self.w - half:] = arr[:, :half][:, ::-1]

    # ---- shading
    def render(self):
        sp = self.spec
        inside = self.M > 0.5
        h = blur(self.Hh, 0.35 * SS) * inside + self.Hh * (~inside)
        h = h - 0.035 * self.GRV
        gy, gx = np.gradient(h)
        k = 7.0 * SS
        nx, ny = -gx * k, -gy * k
        nl = np.sqrt(nx * nx + ny * ny + 1.0)
        nz = 1.0 / nl
        ld = sp.get("light_dir", [0.0, 0.0])  # optional weak key light in image axes; vanilla uses none
        key = np.clip((nx * ld[0] + ny * ld[1]) / nl, -1, 1)
        diffuse = 0.30 + 0.78 * nz ** 1.4 + 0.25 * key
        cav = h - blur(h, 1.0 * SS)
        convex = np.clip(cav * 22.0, 0, 1)
        concave = np.clip(-cav * 18.0, 0, 1)
        ao = np.clip((blur(h, 3.5 * SS) - h) * 3.2, 0, 1)
        shade = diffuse * (1 - 0.55 * ao) * (1 - 0.45 * concave)
        # plate curvature: the dome slope is too shallow for the normal-based term, so shade it directly
        plate_px = self.CLS == CLS_PLATE
        curv = float(sp.get("plate_curvature", 0.32))
        shade = np.where(plate_px, shade * (1 - curv + curv * np.sqrt(np.clip(self.PIL, 0, 1)) * 1.08), shade)
        rng = np.random.default_rng(int(sp.get("seed", 1)) + 99)
        wear_amt = float(sp.get("weathering", 0.3))
        n1 = value_noise(self.h, self.w, 22 * SS, rng)
        n2 = value_noise(self.h, self.w, 2.5 * SS, rng)
        wear = 1.0 - wear_amt * (0.55 * smoothstep(0.5, 0.95, n1) + 0.15 * (n2 - 0.5))
        alb = self.ALB * wear[..., None] * (1 - 0.72 * self.GRV)[..., None]
        hi_col = alb * (0.6 + 0.8 * self.MET[..., None]) + (1 - self.MET[..., None]) * 0.25
        spec_glass = (nz ** 30) * self.GLS * 0.35
        col = alb * shade[..., None] + (convex * (0.35 + 0.25 * self.GLS))[..., None] * hi_col + spec_glass[..., None]
        col = col + self.EMI
        # graded dark rim: vanilla's outer two or three opaque pixels are ~40% darker than the interior
        e1, e2, e3 = erode(inside, SS), erode(inside, 2 * SS), erode(inside, 3 * SS)
        e4 = erode(inside, 4 * SS)
        col[inside & ~e1] *= float(sp.get("rim", 0.45))
        col[e1 & ~e2] *= 0.55
        col[e2 & ~e3] *= 0.70
        col[e3 & ~e4] *= 0.86
        self.final_h = h
        return np.clip(col, 0, 1)

    # ---- downsample (premultiplied), sharpen, tone-match to vanilla, alpha-bleed
    def finish(self, col):
        a = np.clip(self.M, 0, 1)
        pm = np.concatenate([col * a[..., None], a[..., None]], axis=2)
        im = Image.fromarray((pm * 255 + 0.5).astype(np.uint8), "RGBA").resize((self.W, self.H), Image.LANCZOS)
        out = np.asarray(im, np.float32) / 255.0
        A = out[..., 3]
        rgb = np.clip(np.where(A[..., None] > 1e-3, out[..., :3] / np.maximum(A[..., None], 1e-3), 0), 0, 1)
        if self.spec.get("sharpen", 0.4) > 0:
            s = Image.fromarray((rgb * 255).astype(np.uint8), "RGB").filter(
                ImageFilter.UnsharpMask(radius=1, percent=int(100 * self.spec.get("sharpen", 0.4)), threshold=2))
            rgb = np.asarray(s, np.float32) / 255.0
        emi = np.asarray(Image.fromarray((np.clip(self.EMI.max(axis=2), 0, 1) * 255).astype(np.uint8)).resize(
            (self.W, self.H), Image.BOX), np.float32) / 255.0
        t = self.pal.get("target")
        if t and self.spec.get("tone_match", True):
            rgb = tone_match(rgb, A, emi, t, self.spec.get("match_saturation", False))
        A = np.where(A < 8 / 255.0, 0, A)
        rgba = np.concatenate([rgb, A[..., None]], axis=2)
        return alpha_bleed(Image.fromarray((rgba * 255 + 0.5).astype(np.uint8), "RGBA"))

    def maps(self, sprite):
        """GraphicsLib maps at 1x. normal: R=+right, G=+down (as GraphicsLib's own maps), B=+z, alpha = sprite."""
        import sprite_tools  # the estimator validated against GraphicsLib's authored maps (cosine ~0.90)
        a = np.asarray(sprite, np.float32)[..., 3] / 255.0
        normal = np.asarray(sprite_tools.estimate_maps(sprite)[0], np.float32) / 255.0
        spr = np.asarray(sprite, np.float32) / 255.0
        emi = np.asarray(Image.fromarray((np.clip(self.EMI.max(axis=2), 0, 1) * 255).astype(np.uint8)).resize(
            (self.W, self.H), Image.BOX), np.float32) / 255.0
        material = spr.copy()
        material[..., :3] = spr[..., :3] * 0.72 * (1 - np.clip(emi * 2, 0, 1))[..., None]

        def down(x):
            return np.asarray(Image.fromarray((np.clip(x, 0, 1) * 255).astype(np.uint8)).resize(
                (self.W, self.H), Image.BOX), np.float32) / 255.0
        met, gls = down(self.MET), down(self.GLS)
        surface = np.stack([np.zeros_like(a), 0.18 + 0.35 * met + 0.4 * gls, 0.18 + 0.2 * met + 0.4 * gls, a], axis=2)

        def to(x):
            return Image.fromarray((np.clip(x, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA")
        return to(normal), to(material), to(surface)


def tone_match(rgb, A, emi, t, match_sat=False):
    """Remap luminance so p5/p95 match vanilla; optionally scale chroma to the vanilla mean saturation.

    Saturation matching is off by default: vanilla's mean saturation mixes saturated paint with grey machinery,
    so forcing a mostly-plated hull to that mean washes its paint out.
    """
    lum = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    m = (A > 0.9) & (emi < 0.2)
    if m.sum() < 30:
        return rgb
    p5, p95 = np.percentile(lum[m], 5), np.percentile(lum[m], 95)
    norm = np.clip((lum - p5) / max(1e-3, p95 - p5), -0.2, 1.4)
    g = 1.0
    if "mean" in t:  # gamma on the normalised range moves the mean without moving p5/p95
        target = (t["mean"] - t["p5"]) / (t["p95"] - t["p5"])
        lo, hi = 0.5, 2.0
        for _ in range(20):
            g = (lo + hi) / 2
            cur_mean = np.mean(np.sign(norm[m]) * np.abs(norm[m]) ** g)
            if cur_mean > target:
                lo = g
            else:
                hi = g
    new_l = np.clip(t["p5"] + np.sign(norm) * np.abs(norm) ** g * (t["p95"] - t["p5"]), 0, 1)
    ratio = np.where(lum > 1e-3, new_l / np.maximum(lum, 1e-3), 1.0)
    out = np.where(m[..., None], np.clip(rgb * ratio[..., None], 0, 1), rgb)
    mx, mn = out.max(axis=2), out.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-3), 0)
    cur = sat[m].mean()
    if match_sat and cur > 1e-3:
        kk = np.clip(t["sat"] / cur, 0.4, 2.5)
        l2 = out @ np.array([0.299, 0.587, 0.114], np.float32)
        adj = np.clip(l2[..., None] + (out - l2[..., None]) * kk, 0, 1)
        out = np.where(m[..., None], adj, out)
    return out


def alpha_bleed(im, passes=4):
    """Copy edge colours into fully transparent pixels so linear filtering never pulls in a halo."""
    a = np.asarray(im).astype(np.float32)
    rgb, al = a[..., :3].copy(), a[..., 3]
    known = al > 0
    for _ in range(passes):
        acc = np.zeros_like(rgb)
        cnt = np.zeros(al.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sk = np.roll(np.roll(known, dy, 0), dx, 1)
            acc += np.roll(np.roll(rgb, dy, 0), dx, 1) * sk[..., None]
            cnt += sk
        grow = (~known) & (cnt > 0)
        rgb[grow] = acc[grow] / cnt[grow][:, None]
        known = known | grow
    return Image.fromarray(np.clip(np.concatenate([rgb, al[..., None]], axis=2) + 0.5, 0, 255).astype(np.uint8), "RGBA")


# ------------------------------------------------------------------ geometry for the .ship file
def trace_outline(mask):
    """Outer boundary (pixel corners, clockwise in image space) of the topmost component."""
    Hh, Ww = mask.shape
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return []
    j0 = int(ys.min())
    i0 = int(xs[ys == j0].min())

    def filled(i, j):
        return 0 <= i < Ww and 0 <= j < Hh and mask[j, i]

    def quad(x, y, sx, sy):
        return filled(x if sx > 0 else x - 1, y if sy > 0 else y - 1)

    x, y, dx, dy = i0, j0, 1, 0
    start = (x, y, dx, dy)
    pts = []
    for _ in range(4 * (Hh + Ww) * 8):
        pts.append((x, y))
        x += dx
        y += dy
        ar = quad(x, y, dx - dy, dy + dx)
        al = quad(x, y, dx + dy, dy - dx)
        if not ar:
            dx, dy = -dy, dx
        elif al:
            dx, dy = dy, -dx
        if (x, y, dx, dy) == start:
            break
    return pts


def rdp(points, eps):
    if len(points) < 3:
        return points
    a, b = np.array(points[0], float), np.array(points[-1], float)
    ab = b - a
    nrm = float(np.hypot(*ab))
    best, idx = 0.0, 0
    for i in range(1, len(points) - 1):
        p = np.array(points[i], float)
        d = abs(ab[0] * (a[1] - p[1]) - ab[1] * (a[0] - p[0])) / nrm if nrm > 0 else float(np.hypot(*(p - a)))
        if d > best:
            best, idx = d, i
    if best > eps:
        return rdp(points[:idx + 1], eps)[:-1] + rdp(points[idx:], eps)
    return [points[0], points[-1]]


def simplify_closed(pts, eps):
    if len(pts) < 4:
        return pts
    P = np.array(pts, float)
    c = P.mean(axis=0)
    i = int(np.argmax(np.hypot(*(P - c).T)))
    j = int(np.argmax(np.hypot(*(P - P[i]).T)))
    i, j = sorted((i, j))
    a = rdp(pts[i:j + 1], eps)
    b = rdp(pts[j:] + pts[:i + 1], eps)
    return a[:-1] + b[:-1]


def ship_json(spec, sprite):
    W, H = sprite.size
    alpha = np.asarray(sprite)[..., 3] > 127
    ys, xs = np.nonzero(alpha)
    if spec.get("center"):
        center = [float(spec["center"][0]), float(spec["center"][1])]
    else:  # on the centre line, at the alpha centroid (measured from the bottom, as .ship expects)
        center = [W / 2.0, float(round(H - (ys.mean() + 0.5)))]
    outline = trace_outline(alpha)
    eps, simp = 1.0, outline
    while True:
        simp = simplify_closed(outline, eps)
        if len(simp) <= 32 or eps > 6:
            break
        eps += 0.5
    bounds = []
    for px, py in simp:
        sx, sy = sslib.image_to_ship(px, py, center, H)
        bounds += [round(float(sx), 1), round(float(sy), 1)]
    pts = np.array(bounds).reshape(-1, 2)
    ext_px = float(np.max(np.hypot(xs + 0.5 - center[0], (H - ys - 0.5) - center[1])))
    collision = int(math.ceil(ext_px * 1.2 + 4))
    shield_cx = round(float((pts[:, 0].max() + pts[:, 0].min()) / 2), 1)
    shield_r = min(collision, int(math.ceil(float(np.max(np.hypot(pts[:, 0] - shield_cx, pts[:, 1]))) + 2)))
    shp = spec.get("ship", {})
    hs = spec.get("hullSize", "FRIGATE")
    ew, el = ENGINE_DEFAULTS.get(hs, (10, 32))
    style = shp.get("style") or STYLES.get(spec.get("style", "midline"), STYLES["midline"])["ship_style"]

    def to_ship(x, y):
        sx, sy = sslib.image_to_ship(W / 2.0 + x, y, center, H)
        return [round(float(sx), 1), round(float(sy), 1)]

    slots, n = [], 0
    for s in spec.get("slots", []):
        variants = [(1, 1)] + ([(-1, -1)] if s.get("sym") else [])
        for sx, sa in variants:
            n += 1
            if s.get("id"):
                sid = s["id"] if sx > 0 else s["id"] + "R"
            else:
                sid = "WS %03d" % n
            slots.append({
                "angle": float(s.get("angle", 0)) * sa, "arc": float(s.get("arc", 180)), "id": sid,
                "locations": to_ship(sx * s["pos"][0], s["pos"][1]),
                "mount": s.get("mount", "TURRET"), "size": s.get("size", "SMALL"), "type": s.get("type", "BALLISTIC"),
            })
    engines = []
    for e in spec.get("engines", []):
        for sx in ([1, -1] if e.get("sym") else [1]):
            engines.append({
                "angle": float(e.get("angle", 180)), "contrailSize": float(e.get("contrailSize", 64)),
                "length": float(e.get("length", el)), "location": to_ship(sx * e["pos"][0], e["pos"][1]),
                "style": e.get("style", style), "width": float(e.get("width", ew)),
            })
    return {
        "bounds": bounds, "builtInMods": shp.get("builtInMods", []), "center": center,
        "collisionRadius": collision, "coversColor": "", "engineSlots": engines, "height": H,
        "hullId": spec["id"], "hullName": spec.get("name", spec["id"]), "hullSize": hs,
        "shieldCenter": [shield_cx, 0], "shieldRadius": shield_r,
        "spriteName": spec.get("sprite_path", "graphics/ships/%s.png" % spec["id"]),
        "style": style, "viewOffset": shp.get("viewOffset", 0), "weaponSlots": slots, "width": W,
    }


def check(spec, sprite, ship):
    """Sanity checks an agent would otherwise forget. Returns warnings."""
    warn = []
    a = np.asarray(sprite)[..., 3]
    W, H = sprite.size
    for s in ship["weaponSlots"]:
        px, py = sslib.ship_to_image(s["locations"][0], s["locations"][1], ship["center"], H)
        if not (0 <= int(px) < W and 0 <= int(py) < H) or a[int(py), int(px)] < 128:
            warn.append("slot %s at %s is not on opaque hull pixels" % (s["id"], s["locations"]))
    for e in ship["engineSlots"]:
        px, py = sslib.ship_to_image(e["location"][0], e["location"][1], ship["center"], H)
        col = a[min(H - 1, int(py) + 3):, int(min(W - 1, max(0, px)))]
        if (col > 128).sum() > 4:
            warn.append("engine at %s is not at the rear edge (hull continues behind it)" % (e["location"],))
    ids = [s["id"] for s in ship["weaponSlots"]]
    if len(ids) != len(set(ids)):
        warn.append("duplicate weapon slot ids")
    if W % 2:
        warn.append("odd width %d" % W)
    return warn


# ------------------------------------------------------------------ starter specs
EXAMPLES = {
    "frigate": {
        "id": "xmpl_kestrel", "name": "Kestrel", "hullSize": "FRIGATE", "size": [56, 88], "style": "midline",
        "seed": 4, "machinery": 1.0, "panels": 1.0, "plate_detail": 1.0, "weathering": 0.3,
        "parts": [
            {"layer": "hull", "shape": "poly", "sym": True,
             "pts": [[0, 3], [7, 12], [10, 30], [18, 44], [19, 62], [12, 70], [11, 86], [0, 86]]},
            {"layer": "plate", "shape": "poly", "sym": True, "pts": [[0, 4], [6, 12], [8, 30], [3, 36], [0, 36]]},
            {"layer": "plate", "shape": "poly", "sym": True, "pts": [[10, 34], [17, 45], [18, 60], [12, 64]]},
            {"layer": "plate", "shape": "rrect", "box": [-7, 48, 7, 66], "r": 3, "paint": "paint2"},
            {"layer": "stripe", "shape": "rect", "box": [-7, 54, 7, 56], "paint": "accent"},
            {"layer": "glass", "shape": "ellipse", "c": [0, 22], "r": [2.5, 4]},
            {"layer": "trim", "shape": "rect", "box": [-1, 37, 1, 47]}
        ],
        "slots": [
            {"id": "WS0001", "pos": [0, 14], "size": "SMALL", "type": "BALLISTIC", "mount": "HARDPOINT",
             "angle": 0, "arc": 5},
            {"id": "WS0002", "pos": [-12, 50], "size": "SMALL", "type": "ENERGY", "mount": "TURRET",
             "angle": 45, "arc": 180, "sym": True}
        ],
        "engines": [{"pos": [6, 87], "width": 8, "length": 24, "sym": True}],
        "lights": [{"pos": [9, 30], "color": "glow", "sym": True, "r": 0.6}],
        "ship": {"builtInMods": []}
    },
    "destroyer": {
        "id": "xmpl_harrier", "name": "Harrier", "hullSize": "DESTROYER", "size": [110, 168], "style": "lowtech",
        "seed": 11, "weathering": 0.4,
        "parts": [
            {"layer": "hull", "shape": "poly", "sym": True,
             "pts": [[0, 6], [14, 12], [22, 36], [22, 64], [30, 76], [33, 100], [28, 118], [21, 126], [20, 150],
                     [13, 166], [0, 166]]},
            {"layer": "hull", "shape": "rrect", "box": [22, 62, 50, 116], "r": 7, "sym": True},
            {"layer": "hull", "shape": "ellipse", "c": [0, 26], "r": [17, 21]}
        ],
        "auto_plates": {"inset": 2.5, "bands": 5, "gap": 1.8, "spine": 4, "paint2_bands": [2]},
        "slots": [
            {"id": "WS0001", "pos": [9, 16], "size": "SMALL", "type": "BALLISTIC", "mount": "HARDPOINT",
             "angle": 0, "arc": 10, "sym": True},
            {"id": "WS0002", "pos": [0, 52], "size": "MEDIUM", "type": "BALLISTIC", "mount": "TURRET",
             "angle": 0, "arc": 270},
            {"id": "WS0003", "pos": [37, 76], "size": "MEDIUM", "type": "HYBRID", "mount": "TURRET",
             "angle": -60, "arc": 210, "sym": True},
            {"id": "WS0004", "pos": [38, 102], "size": "SMALL", "type": "MISSILE", "mount": "TURRET",
             "angle": -90, "arc": 180, "sym": True}
        ],
        "engines": [{"pos": [9, 166], "sym": True}, {"pos": [0, 166], "width": 10}],
        "lights": [{"pos": [16, 40], "color": "glow", "sym": True, "r": 0.7}],
        "ship": {"builtInMods": []}
    },
    "cruiser": {
        "id": "xmpl_osprey", "name": "Osprey", "hullSize": "CRUISER", "size": [150, 230], "style": "hightech",
        "seed": 21, "weathering": 0.2,
        "parts": [
            {"layer": "hull", "shape": "poly", "sym": True,
             "pts": [[0, 4], [10, 20], [16, 60], [30, 90], [62, 122], [68, 150], [54, 160], [40, 150], [30, 170],
                     [24, 210], [14, 226], [0, 226]]},
            {"layer": "glass", "shape": "ellipse", "c": [0, 48], "r": [5, 9]}
        ],
        "auto_plates": {"inset": 2.2, "bands": 6, "gap": 1.5, "spine": 0, "paint2_bands": [1, 4]},
        "slots": [
            {"id": "WS0001", "pos": [0, 92], "size": "LARGE", "type": "ENERGY", "mount": "TURRET",
             "angle": 0, "arc": 300},
            {"id": "WS0002", "pos": [26, 112], "size": "MEDIUM", "type": "ENERGY", "mount": "TURRET",
             "angle": -45, "arc": 220, "sym": True},
            {"id": "WS0003", "pos": [48, 136], "size": "MEDIUM", "type": "SYNERGY", "mount": "TURRET",
             "angle": -90, "arc": 200, "sym": True},
            {"id": "WS0004", "pos": [9, 32], "size": "SMALL", "type": "ENERGY", "mount": "HARDPOINT",
             "angle": 0, "arc": 10, "sym": True}
        ],
        "engines": [{"pos": [8, 226], "sym": True}, {"pos": [22, 214], "sym": True}],
        "lights": [{"pos": [36, 108], "color": "glow", "sym": True, "r": 0.8},
                   {"pos": [58, 140], "color": "glow", "sym": True, "r": 0.7}],
        "ship": {"builtInMods": []}
    },
    "capital": {
        "id": "xmpl_condor", "name": "Condor", "hullSize": "CAPITAL_SHIP", "size": [220, 340], "style": "midline",
        "seed": 31, "weathering": 0.3,
        "parts": [
            {"layer": "hull", "shape": "poly", "sym": True,
             "pts": [[0, 8], [22, 20], [30, 60], [34, 100], [58, 118], [64, 180], [60, 240], [44, 262], [40, 300],
                     [30, 336], [0, 336]]},
            {"layer": "hull", "shape": "rrect", "box": [44, 128, 100, 232], "r": 10, "sym": True},
            {"layer": "machinery", "shape": "rect", "box": [-5, 120, 5, 300]}
        ],
        "auto_plates": {"inset": 3.0, "bands": 7, "gap": 2.0, "spine": 7, "paint2_bands": [3]},
        "slots": [
            {"id": "WS0001", "pos": [0, 70], "size": "LARGE", "type": "BALLISTIC", "mount": "TURRET",
             "angle": 0, "arc": 270},
            {"id": "WS0002", "pos": [0, 110], "size": "LARGE", "type": "BALLISTIC", "mount": "TURRET",
             "angle": 0, "arc": 270},
            {"id": "WS0003", "pos": [76, 160], "size": "LARGE", "type": "COMPOSITE", "mount": "TURRET",
             "angle": -90, "arc": 180, "sym": True},
            {"id": "WS0004", "pos": [76, 206], "size": "MEDIUM", "type": "MISSILE", "mount": "TURRET",
             "angle": -90, "arc": 180, "sym": True},
            {"id": "WS0005", "pos": [24, 36], "size": "MEDIUM", "type": "BALLISTIC", "mount": "TURRET",
             "angle": 30, "arc": 200, "sym": True},
            {"id": "WS0006", "pos": [46, 254], "size": "MEDIUM", "type": "ENERGY", "mount": "TURRET",
             "angle": -120, "arc": 180, "sym": True}
        ],
        "engines": [{"pos": [8, 336], "sym": True}, {"pos": [22, 336], "sym": True}],
        "lights": [{"pos": [52, 124], "color": "glow", "sym": True, "r": 0.9}],
        "ship": {"builtInMods": []}
    },
}


def example_spec(name):
    """Deep copy of a starter spec (frigate, destroyer, cruiser, capital) to modify in code."""
    return json.loads(json.dumps(EXAMPLES[name]))


def generate(spec, out_dir=None, maps=False, preview=None, quiet=False):
    hull = Hull(spec)
    hull.build()
    sprite = hull.finish(hull.render())
    ship = ship_json(spec, sprite)
    warns = check(spec, sprite, ship)
    written = []
    if out_dir:
        p = os.path.join(out_dir, ship["spriteName"])
        os.makedirs(os.path.dirname(p), exist_ok=True)
        sprite.save(p)
        written.append(p)
        sh = os.path.join(out_dir, "data", "hulls", spec["id"] + ".ship")
        sslib.write_json(sh, ship)
        written.append(sh)
        if maps:
            rows = []
            for kind, im in zip(("normal", "material", "surface"), hull.maps(sprite)):
                rel = "graphics/shaders/%s/ships/%s_%s.png" % (kind, spec["id"], kind)
                q = os.path.join(out_dir, rel)
                os.makedirs(os.path.dirname(q), exist_ok=True)
                im.save(q)
                written.append(q)
                rows.append("%s,ship,,%s,%s,%s" % (spec["id"], "1" if kind == "normal" else "", kind, rel))
            if not quiet:
                print("GraphicsLib texture rows (data/lights/<mod>_texture_data.csv, header id,type,frame,magnitude,map,path):")
                print("\n".join(rows))
    if preview:
        import contact_sheet
        big = sprite.resize((sprite.width * 2, sprite.height * 2), Image.NEAREST)
        ov = contact_sheet.overlay(big.copy(), ship, 2)
        tile_w, tile_h = big.width + 24, big.height + 24
        sheet = contact_sheet.starfield(tile_w * 2, tile_h).convert("RGBA")
        sheet.alpha_composite(big, (12, 12))
        sheet.alpha_composite(ov, (tile_w + 12, 12))
        sheet.convert("RGB").save(preview)
        written.append(preview)
    if not quiet:
        for w in written:
            print("wrote", w)
        for w in warns:
            print("WARNING:", w)
    return sprite, ship, warns


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", nargs="?", help="hull spec JSON")
    ap.add_argument("--example", choices=sorted(EXAMPLES), help="print a starter spec")
    ap.add_argument("--out-dir", help="mod root (default: the spec's folder)")
    ap.add_argument("--maps", action="store_true", help="also write GraphicsLib normal/material/surface maps")
    ap.add_argument("--preview", action="store_true", help="write <spec>_preview.png (2x + overlay)")
    a = ap.parse_args()
    if a.example:
        print(json.dumps(EXAMPLES[a.example], indent=2))
        return
    if not a.spec:
        ap.error("spec required (or --example)")
    spec = sslib.load_loose_json(a.spec)
    out_dir = a.out_dir or os.path.dirname(os.path.abspath(a.spec))
    prev = os.path.splitext(a.spec)[0] + "_preview.png" if a.preview else None
    generate(spec, out_dir, a.maps, prev)


if __name__ == "__main__":
    main()
