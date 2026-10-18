# Sprites: requirements, what vanilla looks like, and what works

Everything below was measured on the Starsector 0.98a-RC7 install (202 vanilla hull files, 275 weapon sprites, all
of `graphics/`) or read from the game's and GraphicsLib's own code, unless marked **(wiki)** or **unverified**. The
scripts named here live in `scripts/` and were run on this install.

## 1. Hard requirements

| Rule | Evidence |
|---|---|
| PNG, **8 bits per channel**. A 16-bit PNG crashes the TextureLoader (ArrayIndexOutOfBounds) | wiki "Modding troubleshooting"; `validate_mod.py` reads the PNG header and errors on 16-bit |
| RGBA for anything with transparency. RGB is fine for opaque images | vanilla: 2129 RGBA PNGs, 914 RGB PNGs, 0 palette/grey PNGs |
| JPG only for big opaque art (illustrations 480x300, backgrounds) | vanilla: 156 JPGs, all illustrations/backgrounds |
| Ships and weapons **face up** (forward = top of the image) | every vanilla hull/weapon |
| Weapon sprites: **even width** ("odd-width weapon sprites blur" **(wiki)**) | all 275 vanilla weapon sprites have even widths |
| Hull sprites may have odd widths, but prefer even | 7 of 127 vanilla hulls are odd |
| Paths use `/`, match the file's case exactly, and are relative to the mod root (or to starsector-core for vanilla files) | wiki; Linux/macOS are case-sensitive; `validate_mod.py` checks case |
| No black outlines on hulls; shade the edges darker instead. "Starsector sprites are tiny paintings, not pixel art" **(wiki, Intro to Modding)** | measured: hull rim/interior luminance about 0.6 |
| Match vanilla pixel mass (total opaque pixels) for the hull class **(wiki)** | see the size table; `sprite_tools.py check` compares |

Fully transparent pixels: vanilla stores light RGB there (mean 207). The colour of transparent pixels bleeds in with
linear filtering, so the generators run `alpha_bleed` (copy edge colours outward).

## 2. Sizes (vanilla medians and p10-p90)

**Hulls** (width x height, px):

| Class | Width p10/50/90 | Height p10/50/90 | Pixel mass (opaque px) p10 / median / p90 |
|---|---|---|---|
| Frigate | 52 / 81 / 127 | 52 / 92 / 120 | 2,841 / 4,312 / 6,838 |
| Destroyer | 102 / 134 / 168 | 137 / 160 / 216 | 10,866 / 13,784 / 17,228 |
| Cruiser | 140 / 184 / 242 | 179 / 224 / 280 | 20,832 / 26,545 / 32,734 |
| Capital | 199 / 288 / 366 | 319 / 367 / 414 | 46,798 / 59,281 / 103,132 |

(Pixel mass over combat hulls, excluding stations, modules and hidden hulls. `sprite_tools.py check --size X`
compares a sprite with its class.)

Examples: wolf 52x96, lasher 68x96, hammerhead 108x164, eagle 168x218, onslaught 288x384, conquest 190x400.

**Weapons** (all even widths):

| Mount | SMALL | MEDIUM | LARGE |
|---|---|---|---|
| Turret (square) p10/50/90 | 24 / 26 / 37 | 34 / 40 / 48 | 64 / 68 / 72 |
| Hardpoint W x H medians | 16 x 28 | 24 x 43 | 36 x 68 |

The game centres BOTH sprites on the weapon slot. Muzzle offsets (`turretOffsets` / `hardpointOffsets`) are measured
from the sprite centre in the ship convention (x = forward/up, y = left). Vanilla muzzle x = 0.62 x (H/2) for turrets
and 0.90 x (H/2) for hardpoints (medians). Every barrel needs a matching angle offset, or the game crashes with
"Index: 1, Size: 1".

**Other images** (count with that size / total in the folder):

| Kind | Size | Where |
|---|---|---|
| Hullmod icon | 32x32 (127/127) | graphics/hullmods |
| Ship system icon | 64x64 (53/53) | graphics/icons/hullsys |
| Market condition icon | 40x40 (136/151) | graphics/icons/markets |
| Intel icon | 40x40 (95/107) | graphics/icons/intel |
| Mission icon | 64x64 (54/54) | graphics/icons/missions |
| Ability icon | 48x48 (16/16) | graphics/icons/abilities |
| Skill icon | 64x64 (76/93) | graphics/icons/skills |
| Cargo icon (commodity, item) | 80x80 (81/103) | graphics/icons/cargo |
| Industry image | 190x95 (42/53) | graphics/icons/industry |
| Portrait | 128x128 (152/153) | graphics/portraits |
| Faction crest | 256x256 | graphics/factions |
| Faction flag/logo | 410x256 (28), one 640x400 | graphics/factions |
| Illustration | 480x300 JPG (96/99) | graphics/illustrations |
| Planet texture | 1024x512 or 512x256 | graphics/planets |
| Background | 2048x2048 JPG | graphics/backgrounds |

## 3. How sprites map to the .ship file

* `center` = [x from the sprite's LEFT edge, y from its BOTTOM edge] in pixels. All other positions are relative to
  it in **ship coordinates: +x = forward (towards the top of the image), +y = left**.
* Image pixel (px from left, py from top) to ship coordinates: `x = (H - py) - cy`, `y = cx - px`.
  Ship to image: `px = cx - y`, `py = H - cy - x`. (`sslib.ship_to_image` / `image_to_ship`.)
* Angles (slot `angle`, engine `angle`) are degrees counter-clockwise from forward: 0 = forward, 90 = left,
  -90 = right, 180 = backwards. Engines normally use 180. (The wiki tidbit "0 degrees is to the right" is about combat
  world angles, not .ship slot angles.)
* `bounds` = collision polygon as a flat [x1, y1, x2, y2, ...] list in ship coordinates. Vanilla uses 5-32 points
  (median 13.5). `collisionRadius` must cover the polygon: vanilla ratio radius/extent is 1.09 / 1.31 / 1.71
  (p10/50/90).
* `shieldRadius` / `collisionRadius` = 0.82 / 0.95 / 1.0. `shieldCenter` is non-zero on 76% of hulls (usually a few
  px forward).
* Slots: `id` ("WS 001"), `mount` TURRET/HARDPOINT/HIDDEN, `size`, `type`, `angle`, `arc`, `locations` (x, y
  pairs; launch bays list several). Median slot count: frigate 3, destroyer 7, cruiser 10, capital 16.
* Engines: `location`, `width`, `length`, `angle`, `contrailSize`, `style` (or CUSTOM + `styleSpec`). Medians
  width/length: frigate 8/24, destroyer 12/48, cruiser 16/56, capital 16/48. contrailSize is 64 almost everywhere
  ("128 is a special magic number" for maneuvering jets **(wiki)**).
* The game indexes .ship files by `hullId`, not by file name (5 vanilla files differ, e.g. warhound.ship holds
  hullId cerberus).

`hullgen.py` and `kitbash.py` write the .ship geometry from the same spec as the sprite, so slots cannot drift off
the art. `contact_sheet.py --overlay` draws bounds, centre, slots (arc wedges) and engines on top of the sprite.

## 4. What vanilla art looks like (style targets)

Measured per tech (opaque pixels):

| Tech | lum p5 / mean / p95 | Saturation | Edge density | Rim / interior | Paint share | Metal share | Dominant paint hue |
|---|---|---|---|---|---|---|---|
| Low Tech (n=28) | 0.11 / 0.41 / 0.75 | 0.30 | 0.61 | 0.63 | 42% | 16% | red-orange (15 deg) |
| Midline (n=23) | 0.13 / 0.48 / 0.83 | 0.18 | 0.65 | 0.62 | 19% | 35% | yellow-orange (30-45 deg) |
| High Tech (n=23) | 0.10 / 0.41 / 0.77 | 0.13 | 0.62 | 0.58 | 10% | 56% | azure (210 deg) |

Sampled colours (dark / mid / light, RGB):

* Low tech paint (100,74,64) / (135,101,86) / (175,132,111); metal (74,70,69) / (141,134,130) / (198,189,182); glow (229,132,100)
* Midline paint (104,94,69) / (151,136,99) / (194,175,122); metal (79,77,75) / (161,158,148) / (212,208,195); glow (226,191,107)
* High tech paint (79,92,108) / (108,128,149) / (139,166,195); metal (53,54,54) / (92,94,92) / (165,170,174); glow (207,167,120)

Findings that shaped the generators:

1. **No baked directional light.** Regressing luminance on the surface normals from GraphicsLib's authored normal
   maps (185 hulls) gives coefficients near 0 (R^2 = 0.04). Vanilla shading is "overhead": slopes darken
   symmetrically, crevices get ambient occlusion, convex edges get highlights, and the silhouette rim is dark.
   Do not light from the top-left.
2. **Near-perfect mirror symmetry.** Mean |lum - mirrored lum| = 0.07, silhouette asymmetry 0.7%, 57% of hulls
   under 2%. Generate the left half and mirror it.
3. **Two materials.** Smooth painted plates sit on top of dense grey machinery (pipes, tanks, vents, boxes).
4. **Dense detail.** About 60% of interior pixels have a luminance step > 0.08 (high-frequency energy about 0.09).
5. 16% of hulls touch the image border (median margin 1 px), so tight cropping is normal.

**Weapons** (all 275 vanilla turret/hardpoint sprites) look different from hulls: the gun itself seen from above,
not a round turret base (the hull's turret cover is drawn by the game). Each is a narrow, symmetric stack of small
mechanical parts (banded barrels, coils, fins, struts, clamps) separated by dark 1 px lines, with a lot of
transparent space between parts. Median opaque coverage is 25% for turrets and 44% for hardpoints. lum p5/mean/p95
is 0.11/0.41/0.82, saturation 0.18, edge density 0.82, high-frequency energy 0.13 (busier than hulls), and the rim is
lighter than on hulls (0.80).

Measure your own art against these numbers: `sprite_stats.py --mod MyMod` for hulls (each compared with its .ship
style's tech) and `weapongen.py ... --check` for weapons.

## 5. Approaches, tested, ranked by result

### A. Kitbash vanilla pieces (`kitbash.py`): most vanilla-consistent

Cut boxes out of vanilla (or your own) sprites, place/mirror them, recolour the saturated paint only, darken cut
edges, and tone-match to the vanilla band. `kitbash.py show vanilla:<hull> --grid 10` renders a 4x view with a
pixel grid to read box coordinates from. The test destroyer (hammerhead + enforcer pieces) landed inside every
vanilla midline band (0 of 7 metrics out) after tone matching.

Kitbashing vanilla art is long-standing community practice. The official tutorial says to "copy or kitbash bits of
existing sprites", and the forum's "Kitbash Database" notes the sprites are "to be used only in the context of
Starsector's modding as per the game's license". **Credit the source hulls** in CREDITS/README. Visible seams still
need a manual touch-up for top quality.

### B. Procedural hulls (`hullgen.py`): original art, consistent, below vanilla

A JSON spec (silhouette parts, plate bands, slots, engines) becomes a sprite plus the .ship file, and optionally
GraphicsLib maps. It renders a supersampled height/material model (plates over machinery, overhead lighting, AO,
convex highlights, dark rim), mirrors it, and tone-matches to the vanilla band for the style.
`hullgen.py --example frigate|destroyer|cruiser|capital` prints starter specs. Result: the four examples measure
inside the vanilla bands except 2 of 28 metrics. Visually they are readable, consistent and clearly better than
flat shapes, but they look more regular and blocky than vanilla, with less organic curvature, no weathering
story, and turret rings that look applied. Good for a faction with a deliberately industrial look, or as a base
to paint over.

### C. Procedural weapons (`weapongen.py`): good for most weapons

A kit of parts (banded barrels, coils, tanks, struts, warheads, lenses) is drawn on a 4x canvas with dark ink
separation. Composition recipes cover cannon, gatling, beam, emitter and missile, and the output is tone-matched to
the vanilla weapon medians. Turret and hardpoint sprites come with their .wpn offsets. Tone, saturation, rim and
coverage land in or near the vanilla ranges (`--check`). They read as vanilla-adjacent; the pulse/emitter recipe is
the closest. They are less intricate and less irregular than vanilla. An earlier version (round bases, smooth
shading) looked like toys, which is why the composition rules above matter.

### D. External or AI images to a sprite (`sprite_tools.py clean`)

Pipeline: background removal (alpha, or flood fill from the border colour), crop, rotate/straighten so the ship
faces up (mirror-symmetry search), optional mirror symmetry, premultiplied-alpha downscale to the target length, even
width, tone match to vanilla, dark rim, alpha bleed. Round-trip test: vanilla sprites with simulated AI artefacts
(scaled up 3x, rotated 6 degrees, JPEG-compressed, on a coloured background) came back with silhouette IoU
0.92-0.98 and luminance correlation 0.62-0.89, and the 6 degree tilt was recovered. Also: `recolor` (repaint
saturated pixels only, for faction skins) and `--quantize N` (off by default; quantising hurts painted sprites).

**AI image generation: not tested.** This machine has an RTX 3060 (12 GB) and PyPI is reachable (torch, diffusers
and rembg wheels exist), but nothing was installed or run: multi-GB downloads plus GPU load would take over the
user's PC, which was ruled out, and no image-generation API key is configured. The cleanup pipeline above is ready
for images made elsewhere. Whether a diffusion model can produce usable top-down ship art is **unverified**.

## 6. GraphicsLib normal/material/surface maps

Read from GraphicsLib's shaders (`data/shaders/lights/*.frag`) and Java (`LightShader`, `ShaderLib`, `TextureData`):

* **normal** map: RGB = normal x 0.5 + 0.5 with **R = +image right, G = +image down, B = +z** (measured on
  GraphicsLib's own vanilla maps: per-pixel correlation +0.84 / -0.84 against outward edge directions). Same size
  as the sprite; alpha = sprite alpha.
* **material** map: the colour that dynamic lights illuminate. In vanilla maps it is a darker copy of the sprite
  (median material/sprite luminance ratio 0.57-0.85).
* **surface** map: R unused (0), **G = specular intensity, B = specular hardness** (shader: `surface.g` scales
  specular, `5 x surface.b` sets hardness; any non-zero channel switches surface mode on).
* Register maps in `data/lights/<mod>_texture_data.csv` with GraphicsLib's header
  `id,type,frame,magnitude,map,path` (id = hull/weapon/projectile id, or `hullid_STYLEID`; type = ship, turret,
  hardpoint, turretbarrel, missile, ...; magnitude = normal depth, default 1). Load it from the ModPlugin only when
  GraphicsLib is enabled:
  `if (Global.getSettings().getModManager().isModEnabled("shaderLib")) TextureData.readTextureDataCSV("data/lights/<mod>_texture_data.csv");`
  (put the call in a separate class so the mod loads without GraphicsLib). Light data (projectile/beam glow) uses
  `LightData.readLightDataCSV(path)` and the 18-column header of `core_light_data.csv`.
* `sprite_tools.py maps` / `hullgen.py --maps` estimate the three maps from any sprite. Accuracy against
  GraphicsLib's hand-made normal maps for 24 vanilla hulls: mean per-pixel cosine **0.90** (flat normals score 0.70;
  worst hull 0.57). That is good enough for convincing dynamic lighting; it is not hand-authored quality.
* The in-game look was **not verified** (the game was never launched).

## 7. Workflow that keeps art on target

1. Before drawing: `sprite_stats.py --vanilla-table`, and look at 3-5 vanilla peers of the same size and tech
   (`contact_sheet.py --vanilla wolf,lasher,... --scale 3`).
2. Pick the approach: kitbash for vanilla consistency, hullgen/weapongen for original art, sprite_tools clean for
   external art.
3. After every pass: `contact_sheet.py --mod MyMod --peers 2 --scale 1,2 --overlay` and LOOK at it at 1x first
   (that is how players see ships), then `sprite_stats.py --mod MyMod`.
4. Before release: `sprite_tools.py check graphics/ships/*.png --kind ship` and `validate_mod.py` (8-bit, case,
   dimensions match .ship, slots on opaque pixels, even weapon widths, unused assets).

## 7b. Blender-scripted hulls (Resonance Lattice, 2026-10: the best original-art result so far)

Pipeline (lives in that mod's `art_src/`, see its CLAUDE.md): a JSON spec per hull (layered plate outlines, cuts,
greebles, details, livery, slots, engines) -> headless Blender 4.2 Cycles GPU render at 4x (colour, emit, normal,
height, material-id passes; 4-10 s per hull) -> `finish.py` (livery paint at 4x, ink lines, tone match to vanilla,
rim, glow sprite with halo, GraphicsLib maps, the `.ship` via hullgen). Complex hulls get a Python generator that
writes the spec. The user approved the art direction and called the result good after many review rounds.

Art-direction lessons that generalise (each came from a rejected version):
* No geometric primitives as silhouettes (parallel rails = rectangle, straight diagonals = triangle, one smooth
  envelope = egg, vertical midship = rocket). Several masses with different edge angles, notches, protrusions and
  sharp swept tips. When a silhouette does not converge in ~2 tries, sketch 2-3 flat options and let the user pick.
* Never a flat single-colour hull: a livery per ship that fits its silhouette, varied technique per ship
  (gradients at the extremities, crisp painted shapes, "dipped tips"); gradients over whole plates read as foil.
* Big hulls are built from many distinct structural parts (segmented prongs, clamps, housings, exposed machinery
  gaps), not one broad envelope; tiny dots never substitute for detail. Connecting parts must look load-bearing.
* Glowing seams as the faction signature work well when they follow rules (straight conduit runs with 45/90 deg
  bends from the core to something functional, no branching, nodes at the ends).
* Check mirror symmetry by pixel diff after every render; per-object random tints and boolean cuts broke it.
* Every review sheet shows the new hull next to the faction's approved hulls and ONE vanilla reference at 1x.
* Hullmod icons in vanilla style can be made from close-up crops of these 4x renders (see ships-and-combat.md 8).

## 8. Still not done well (be honest about these)

* Hand-painted micro-detail, weathering and organic curvature: procedural hulls stay visibly more regular than
  vanilla. Kitbashing closes the gap but needs seam cleanup by hand.
* Portraits, illustrations and faction crests: no tested generator (hullmod icons: see 7b). Last session's procedural portraits and
  icons were weak, and nothing better was built. Use simple, clean glyph icons in vanilla's style and sizes, reuse
  vanilla portraits, or commission art.
* Animated sprites (weapon charge/glow frames, `numFrames`): not attempted.
* How any generated sprite reads in motion and at combat zoom, and how the estimated GraphicsLib maps light in game:
  unverified without launching the game.
