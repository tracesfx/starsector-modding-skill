#!/usr/bin/env python3
"""selftest.py - prove that every script in this skill runs on this machine, end to end, and that the validator
catches real faults. Run it after changing any script, or first thing on a new machine / game version.

    python selftest.py                    # full run in a temp folder (removed afterwards unless --keep)
    python selftest.py --workdir D:/tmp/ss --keep
    python selftest.py --skip-sprites     # faster: no image generation

What it does: scaffolds a mod with new_mod.py (every `add` template, so all Java templates are compiled against the
real API), generates a content slice with templates/tools/gen_content.py, builds it with build_mod.py, validates it
(expects 0 errors), injects ~20 faults into copies and checks each one is reported, packages a release, and runs
api_lookup, vanilla_baselines, log_scan, hullgen, kitbash, weapongen, sprite_tools, sprite_stats and contact_sheet.
It also runs validate_mod.py on every installed mod (it must not crash). Exit code 1 if anything failed.
"""
import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import zipfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import sslib  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

RESULTS = []


def run(args, cwd=None, timeout=600):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", SS_SKILL_SCRIPTS=HERE)
    p = subprocess.run([sys.executable] + args, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print("%s  %s%s" % ("PASS" if ok else "FAIL", name, ("   -- " + detail) if (detail and not ok) else ""))
    return ok


def script(name):
    return os.path.join(HERE, name)


def step_env(game):
    try:
        import numpy  # noqa: F401
        from PIL import Image  # noqa: F401
        check("python libs: numpy + Pillow", True)
    except ImportError as e:
        check("python libs: numpy + Pillow", False, str(e))
    javac = shutil.which("javac")
    out = subprocess.run([javac, "-version"], capture_output=True, text=True).stdout + \
        subprocess.run([javac, "-version"], capture_output=True, text=True).stderr if javac else ""
    m = re.search(r"javac (\d+)", out)
    check("JDK on PATH (javac >= 17)", bool(m and int(m.group(1)) >= 17), out.strip() or "javac not found")
    check("game found + version", bool(game and sslib.game_version(game)), "%s %s" % (game, sslib.game_version(game)))


def step_sslib(game):
    core = sslib.core_dir(game)
    bad = []
    n = 0
    for root, _, fs in os.walk(os.path.join(core, "data")):
        for f in fs:
            if f.endswith((".json", ".ship", ".variant", ".wpn", ".proj", ".system", ".faction", ".skin")):
                n += 1
                try:
                    sslib.load_loose_json(os.path.join(root, f))
                except Exception as e:
                    bad.append("%s: %s" % (f, e))
    check("sslib.loose_json parses every vanilla JSON-family file (%d)" % n, not bad, "; ".join(bad[:3]))
    t = sslib.loose_json("{ # c\n id: x, 'q': 'it\\'s', n: .5f, l: [1,2,], s: 1; t: true, }")
    check("sslib.loose_json dialect", t == {"id": "x", "q": "it's", "n": 0.5, "l": [1, 2], "s": 1, "t": True}, repr(t))
    w, h, c = 52, 96, [26, 42]
    pts = [(10, 20), (0, 0), (51, 95)]
    check("sslib ship<->image round trip", all(sslib.image_to_ship(*sslib.ship_to_image(*sslib.image_to_ship(px, py, c, h), c, h), c, h)
                                              == sslib.image_to_ship(px, py, c, h) for px, py in pts))


def step_api_lookup():
    cases = [
        (["class", "FleetParamsV3"], "combatPts"),
        (["method", "Misc", "makeStoryCritical"], "STORY_CRITICAL"),
        (["const", "MemFlags", "MEMORY_KEY_NO_JUMP"], "$cfai_noJump"),
        (["rulecmd", "AddRemoveCommodity"], "<commodity id>"),
        (["uses", "$hassleType"], "rules.csv"),
        (["grep", "class HasslePlayerScript", "--impl"], "HasslePlayerScript.java"),
        (["data", "hammerhead_Balanced", "--ext", "json"], "default_ship_roles.json"),
        (["sources"], "API source"),
    ]
    if shutil.which("javap"):
        cases.append((["javap", "com.fs.starfarer.api.combat.ShipAPI"], "getFluxTracker"))
    for args, want in cases:
        rc, out = run([script("api_lookup.py")] + args)
        check("api_lookup %s" % " ".join(args[:2]), rc == 0 and want in out, out[-300:])
    rc, out = run([script("api_lookup.py"), "grep", "(unclosed"])
    check("api_lookup rejects a bad regex cleanly", rc != 0 and "Traceback" not in out, out[-200:])


def step_baselines(mod=None):
    for args, want in ((["hulls", "--size", "FRIGATE"], "flux diss"), (["peers", "--size", "CRUISER", "--dp", "20"], "Eagle"),
                       (["weapons", "--size", "MEDIUM", "--type", "ENERGY"], "DPS/OP"), (["wings"], "BOMBER"),
                       (["hullmods"], "capital OP")):
        rc, out = run([script("vanilla_baselines.py")] + args)
        check("vanilla_baselines %s" % args[0], rc == 0 and want in out, out[-300:])
    if mod:
        rc, out = run([script("vanilla_baselines.py"), "check", "--mod", mod, "--markdown"])
        check("vanilla_baselines check --mod", rc == 0 and "HULL" in out and "WEAPON" in out, out[-300:])


def png16(path, w=8, h=8):
    """Write a 16-bit RGBA PNG (the format that crashes the game's TextureLoader)."""
    raw = b"".join(b"\x00" + b"\x12\x34" * 4 * w for _ in range(h))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 16, 6, 0, 0, 0)) +
                 chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def edit(path, fn):
    with open(path, encoding="utf-8") as fh:
        s = fh.read()
    s2 = fn(s)
    if s2 == s:
        raise RuntimeError("edit had no effect on %s" % path)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(s2)


def edit_json(path, fn):
    d = sslib.load_loose_json(path)
    fn(d)
    sslib.write_json(path, d)


def step_mod(work, game):
    installed = sslib.installed_mods(game)
    deps = [d for d, mid in (("lazylib", "lw_lazylib"), ("lunalib", "lunalib")) if mid in installed]
    rc, out = run([script("new_mod.py"), "create", "--name", "Selftest Yards", "--prefix", "sty_", "--author", "selftest",
                   "--description", "Selftest mod.", "--dest", work] + (["--deps", ",".join(deps)] if deps else []))
    mod = os.path.join(work, "SelftestYards")
    if not check("new_mod create", rc == 0 and os.path.isfile(os.path.join(mod, "mod_info.json")), out[-400:]):
        return None
    kinds = [("hullmod", "Ablative Plating"), ("system", "Overcharge"), ("combat-plugin", "Ledger"), ("onhit", "Static Lash"),
             ("weapon-effect", "Heat Sink"), ("rulecmd", "Tithe"), ("intel", "Notice"), ("script", "Collector"),
             ("worldgen", "Reach"), ("fleet", "Collectors")]
    if "lunalib" in installed:
        kinds.append(("luna", "Settings"))
    for kind, name in kinds:
        args = [script("new_mod.py"), "add", kind, "--mod", mod, "--name", name] + (["--ai"] if kind == "system" else [])
        rc, out = run(args)
        check("new_mod add %s" % kind, rc == 0 and "wrote" in out, out[-300:])
    rc, out = run([os.path.join(SKILL, "templates", "tools", "gen_content.py"), "--mod", mod])
    check("templates/tools/gen_content.py", rc == 0 and "generated" in out, out[-400:])
    rc, out = run([os.path.join(mod, "tools", "build_mod.py"), "--mod", mod, "--game", game])
    n_java = len([f for f in os.listdir(os.path.join(SKILL, "templates", "java")) if f.endswith(".java")])
    m = re.search(r"wrote jars/\S+ \((\d+) classes\)", out)
    check("build_mod (vendored copy) compiles scaffold + %d Java templates" % (len(kinds) + 1),
          rc == 0 and m and int(m.group(1)) >= len(kinds) + 2, out[-800:])
    rc, out = run([script("validate_mod.py"), "--mod", mod, "--game", game])
    errs = re.search(r"(\d+) error\(s\)", out)
    check("validate_mod: scaffold + content has 0 errors", rc == 0 and errs and errs.group(1) == "0", out[-1200:])
    check("validate_mod flags scaffold placeholders as warnings", "unfinished placeholder" in out, out[-300:])
    return mod


FAULTS = [  # (name, mutation(mod), expected message regex)
    ("variant uses an unknown weapon", lambda m: edit(V(m), lambda s: s.replace('"sty_lancet"', '"sty_lancett"', 1)), r"unknown weapon 'sty_lancett'"),
    ("energy weapon in a ballistic slot", lambda m: edit(V(m), lambda s: s.replace('"WS0001": "sty_lancet"', '"WS0001": "pdlaser"')), r"cannot mount in BALLISTIC"),
    ("OP over budget", lambda m: edit(CSV(m, "hulls/ship_data.csv"), lambda s: re.sub(r"(sty_warden,[^\n]*?)(,45,)", r"\1,5,", s, count=1)), r"uses \d+ OP but sty_warden has 5"),
    ("non-numeric hitpoints", lambda m: edit(CSV(m, "hulls/ship_data.csv"), lambda s: re.sub(r"(sty_warden,(?:[^,]*,){4})(\d+)", r"\1lots", s, count=1)), r"'hitpoints' is not a number"),
    ("sprite path case mismatch", lambda m: edit(SHIP(m), lambda s: s.replace("graphics/ships/sty_warden.png", "graphics/ships/STY_warden.png")), r"case differs"),
    (".ship size differs from sprite", lambda m: edit_json(SHIP(m), lambda d: d.update(width=d["width"] + 4)), r"sprite is \d+x\d+ but \.ship"),
    ("barrel/angle-offset mismatch", lambda m: edit_json(WPN(m), lambda d: d.update(turretAngleOffsets=[])), r"AngleOffsets has 0"),
    ("faction knows a missing weapon", lambda m: edit_json(FAC(m), lambda d: d["knownWeapons"]["weapons"].append("sty_ghost")), r"knownWeapons: unknown weapon 'sty_ghost'"),
    ("dialog option without handler", lambda m: edit(CSV(m, "campaign/rules.csv"), lambda s: s.replace("sty_office_back:Back", "sty_office_nowhere:Back")), r"option 'sty_office_nowhere' has no DialogOptionSelected"),
    ("unknown rule command", lambda m: edit(CSV(m, "campaign/rules.csv"), lambda s: s.replace("FireAll PopulateOptions", "FireAlll PopulateOptions")), r"'FireAlll' is not a rule command"),
    ("duplicate description", lambda m: edit(CSV(m, "strings/descriptions.csv"), lambda s: s + s.splitlines()[1] + "\n"), r"duplicate \("),
    ("hullmod script class typo", lambda m: edit(CSV(m, "hullmods/hull_mods.csv"), lambda s: s.replace("StyAblativePlating", "StyAblativePlatin")), r"hullmod script not found"),
    ("UTF-8 BOM in a CSV", lambda m: bom(CSV(m, "hulls/ship_data.csv")), r"BOM"),
    ("16-bit PNG", lambda m: png16(os.path.join(m, "graphics", "ships", "sty_extra.png")), r"16-bit PNG"),
    ("jar missing", lambda m: os.remove(os.path.join(m, "jars", "SelftestYards.jar")), r"jar listed in mod_info.json does not exist"),
    ("faction not in factions.csv", lambda m: edit(CSV(m, "world/factions/factions.csv"), lambda s: s.splitlines()[0] + "\n"), r"not listed in data/world/factions/factions.csv"),
    ("Java lookup of a missing variant", lambda m: edit(PLUGIN(m), lambda s: s.replace("log.info(", "Global.getSettings().getVariant(\"sty_nothing_Standard\");\n        log.info(", 1)), r"unknown variant id"),
    ("role lists a missing variant", lambda m: edit_json(ROLES(m), lambda d: d["combatSmall"].update({"sty_missing_V": 3})), r"unknown variant 'sty_missing_V'"),
    ("weapon slot outside the sprite", lambda m: edit_json(SHIP(m), lambda d: d["weaponSlots"][0].update(locations=[400, 0])), r"lies outside the sprite"),
    ("unbalanced quote in a CSV", lambda m: edit(CSV(m, "weapons/weapon_data.csv"), lambda s: s.replace("Lancet Autocannon", "\"Lancet, Autocannon")), r"columns|line \d+"),
    ("backslash in a path", lambda m: edit(SHIP(m), lambda s: s.replace("graphics/ships/sty_warden.png", "graphics\\\\ships\\\\sty_warden.png")), r"backslashes"),
    ("fleet listener removed inside its callback", lambda m: write(os.path.join(m, "src", "sty", "StyBadListener.java"), BAD_LISTENER), r"ConcurrentModificationException"),
    (".version out of sync", lambda m: edit_json(os.path.join(m, "selftest_yards.version"), lambda d: d["modVersion"].update(minor=9)), r"does not match mod_info.json version"),
]


BAD_LISTENER = """package sty;

import com.fs.starfarer.api.campaign.BattleAPI;
import com.fs.starfarer.api.campaign.CampaignFleetAPI;

public class StyBadListener {
    private CampaignFleetAPI target;

    public void reportBattleOccurred(CampaignFleetAPI fleet, CampaignFleetAPI winner, BattleAPI battle) {
        if (fleet == target) finish();
    }

    private void finish() {
        target.removeEventListener(null);
    }
}
"""


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def V(m):
    return os.path.join(m, "data", "variants", "sty_warden_Standard.variant")


def CSV(m, rel):
    return os.path.join(m, "data", *rel.split("/"))


def SHIP(m):
    return os.path.join(m, "data", "hulls", "sty_warden.ship")


def WPN(m):
    return os.path.join(m, "data", "weapons", "sty_lancet.wpn")


def FAC(m):
    return os.path.join(m, "data", "world", "factions", "sty_faction.faction")


def ROLES(m):
    return os.path.join(m, "data", "world", "factions", "default_ship_roles.json")


def PLUGIN(m):
    return os.path.join(m, "src", "sty", "StyModPlugin.java")


def bom(path):
    raw = open(path, "rb").read()
    with open(path, "wb") as fh:
        fh.write(b"\xef\xbb\xbf" + raw)


def step_faults(mod, work, game):
    for name, mutate, want in FAULTS:
        dst = os.path.join(work, "fault")
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        shutil.copytree(mod, dst)
        try:
            mutate(dst)
        except Exception as e:
            check("fault caught: " + name, False, "mutation failed: %s" % e)
            continue
        rc, out = run([script("validate_mod.py"), "--mod", dst, "--game", game])
        hit = re.search(want, out)
        check("fault caught: " + name, rc == 1 and hit, "exit %d; expected /%s/; got:\n%s" % (rc, want, out[-700:]))
    if os.path.isdir(os.path.join(work, "fault")):
        shutil.rmtree(os.path.join(work, "fault"))


def step_package(mod, game):
    rc, out = run([script("package_mod.py"), "--mod", mod, "--game", game])
    z = os.path.join(mod, "dist", "SelftestYards-0.1.0.zip")
    ok = rc == 0 and os.path.isfile(z)
    if ok:
        with zipfile.ZipFile(z) as zf:
            names = zf.namelist()
        ok = "SelftestYards/mod_info.json" in names and "SelftestYards/jars/SelftestYards.jar" in names and \
            not any(n.startswith("SelftestYards/src/") or n.startswith("SelftestYards/tools/") for n in names)
    check("package_mod builds a release zip (mod folder at top, no src/tools)", ok, out[-500:])
    rc, out = run([script("package_mod.py"), "--mod", mod, "--game", game, "--strict"])
    check("package_mod --strict refuses while placeholders remain", rc == 1 and "RELEASE BLOCKED" in out, out[-300:])


def step_log_scan(work, mod):
    log = os.path.join(work, "fake_starsector.log")
    lines = [
        "0    [main] INFO  com.fs.starfarer.StarfarerLauncher  - Starting Starsector 0.98a-RC7 launcher",
        "11   [main] INFO  com.fs.starfarer.StarfarerLauncher  - Java version: 17.0.10 (64-bit)",
        "500 [Thread-2] ERROR com.fs.starfarer.loading.ShipHullSpreadsheetLoader  - Ship hull spec [flare] not found in ship_data.csv",
        "900 [Thread-2] ERROR com.fs.starfarer.combat.CombatMain  - java.lang.NullPointerException",
        "java.lang.NullPointerException",
        "\tat sty.combat.StyLedgerPlugin.advance(StyLedgerPlugin.java:42)",
        "\tat com.fs.starfarer.combat.CombatEngine.advance(Unknown Source)",
        "950 [Thread-2] ERROR com.fs.starfarer.loading.SpecStore  - java.lang.RuntimeException: Weapon spec [sty_lancett] not found!",
        "960 [Thread-2] ERROR com.fs.starfarer.campaign.save.CampaignGameManager  - ",
        "---- Debugging information ----",
        "cause-exception     : com.thoughtworks.xstream.mapper.CannotResolveClassException",
        "cause-message       : sty.campaign.StyNoticeIntel",
    ]
    with open(log, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    rc, out = run([script("log_scan.py"), "--log", log, "--mod", mod])
    ok = rc == 1 and "[MOD]" in out and "first frame in your code" in out and "sty_lancett" in out and \
        "StyNoticeIntel" in out and "1 known vanilla-noise" in out
    check("log_scan classifies errors and finds the mod's frames", ok, out[-900:])


def step_sprites(work, game):
    d = os.path.join(work, "sprites")
    os.makedirs(d, exist_ok=True)
    spec = os.path.join(d, "frigate.json")
    rc, out = run([script("hullgen.py"), "--example", "frigate"])
    open(spec, "w", encoding="utf-8").write(out)
    rc, out = run([script("hullgen.py"), spec, "--out-dir", os.path.join(d, "mod"), "--maps", "--preview"], cwd=d)
    sp = os.path.join(d, "mod", "graphics", "ships", "xmpl_kestrel.png")
    check("hullgen: sprite + .ship + GraphicsLib maps + preview", rc == 0 and os.path.isfile(sp) and
          os.path.isfile(os.path.join(d, "mod", "data", "hulls", "xmpl_kestrel.ship")) and
          os.path.isfile(os.path.join(d, "mod", "graphics", "shaders", "normal", "ships", "xmpl_kestrel_normal.png")), out[-400:])
    kit = os.path.join(d, "kit.json")
    rc, out = run([script("kitbash.py"), "--example"])
    open(kit, "w", encoding="utf-8").write(out)
    rc, out = run([script("kitbash.py"), "build", kit, "--out-dir", os.path.join(d, "kb"), "--preview"], cwd=d)
    pngs = [os.path.join(r, f) for r, _, fs in os.walk(os.path.join(d, "kb")) for f in fs if f.endswith(".png")]
    check("kitbash build from vanilla pieces", rc == 0 and pngs, out[-400:])
    from PIL import Image
    widths_even = True
    for kind in ("cannon", "gatling", "beam", "emitter", "missile"):
        rc, out = run([script("weapongen.py"), "--id", "t_" + kind, "--size", "MEDIUM", "--kind", kind, "--barrels", "2",
                       "--tubes", "4", "--out-dir", os.path.join(d, "w"), "--check"])
        ok = rc == 0 and "turretOffsets" in out
        for m in ("turret", "hardpoint"):
            p = os.path.join(d, "w", "graphics", "weapons", "t_%s_%s.png" % (kind, m))
            ok = ok and os.path.isfile(p)
            if os.path.isfile(p):
                widths_even &= Image.open(p).width % 2 == 0
        check("weapongen %s" % kind, ok, out[-300:])
    check("weapongen widths are even", widths_even)
    src = sslib.vanilla_hulls(game)["eagle"][0]["spriteName"]
    vimg = Image.open(os.path.join(sslib.core_dir(game), src)).convert("RGBA")
    fake = Image.new("RGB", (vimg.width * 3 + 80, vimg.height * 3 + 80), (40, 120, 60))
    big = vimg.resize((vimg.width * 3, vimg.height * 3), Image.BICUBIC).rotate(6, expand=False)
    fake.paste(big, (40, 40), big)
    fp = os.path.join(d, "fake_ai.jpg")
    fake.save(fp, quality=85)
    out_clean = os.path.join(d, "clean.png")
    rc, out = run([script("sprite_tools.py"), "clean", fp, out_clean, "--length", str(vimg.height), "--straighten",
                   "--style", "midline"])
    ok = rc == 0 and os.path.isfile(out_clean)
    if ok:
        im = Image.open(out_clean)
        ok = im.mode == "RGBA" and abs(im.height - vimg.height) <= 2 and im.width % 2 == 0
    check("sprite_tools clean (AI/external image to sprite)", ok, out[-400:])
    rc, out = run([script("sprite_tools.py"), "recolor", out_clean, os.path.join(d, "recolor.png"), "--target", "96,150,128"])
    check("sprite_tools recolor", rc == 0 and os.path.isfile(os.path.join(d, "recolor.png")), out[-300:])
    rc, out = run([script("sprite_tools.py"), "maps", out_clean, "--out-prefix", os.path.join(d, "maps", "{kind}", "clean")])
    check("sprite_tools maps", rc == 0 and os.path.isfile(os.path.join(d, "maps", "normal", "clean.png")), out[-300:])
    rc, out = run([script("sprite_tools.py"), "check", sp, "--kind", "ship", "--size", "FRIGATE"])
    check("sprite_tools check", rc in (0, 1) and "pixel mass" in out, out[-300:])
    rc, out = run([script("sprite_stats.py"), "--json", sp])
    try:
        ok = rc == 0 and "lum_mean" in json.loads(out[out.index("{"):])["sprites"][sp]
    except Exception:
        ok = False
    check("sprite_stats --json", ok, out[-300:])
    rc, out = run([script("contact_sheet.py"), "--mod", os.path.join(d, "mod"), "--peers", "1", "--scale", "1,2",
                   "--overlay", "--out", os.path.join(d, "sheet.png")])
    check("contact_sheet with vanilla peers + overlay", rc == 0 and os.path.isfile(os.path.join(d, "sheet.png")), out[-300:])


def step_installed(game):
    for mid, (folder, info) in sorted(sslib.installed_mods(game).items()):
        rc, out = run([script("validate_mod.py"), "--mod", folder, "--game", game, "--quiet"])
        check("validate_mod runs on installed mod %s (exit %d)" % (mid, rc), "Traceback" not in out and rc in (0, 1), out[-500:])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game")
    ap.add_argument("--workdir")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--skip-sprites", action="store_true")
    ap.add_argument("--skip-installed", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    game = sslib.require_game_dir(a.game)
    work = a.workdir or tempfile.mkdtemp(prefix="ss_selftest_")
    os.makedirs(work, exist_ok=True)
    print("selftest: skill %s\n          game %s\n          work %s\n" % (SKILL, game, work))
    step_env(game)
    step_sslib(game)
    step_api_lookup()
    mod = step_mod(work, game)
    step_baselines(mod)
    if mod:
        step_faults(mod, work, game)
        step_package(mod, game)
        step_log_scan(work, mod)
    if not a.skip_sprites:
        step_sprites(work, game)
    if not a.skip_installed:
        step_installed(game)
    fails = [r for r in RESULTS if not r[1]]
    print("\nselftest: %d passed, %d failed in %.0fs" % (len(RESULTS) - len(fails), len(fails), time.time() - t0))
    for name, _, detail in fails:
        print("  FAILED: %s\n%s" % (name, "\n".join("      " + ln for ln in detail.splitlines()[-12:])))
    if not a.keep and not a.workdir:
        shutil.rmtree(work, ignore_errors=True)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
