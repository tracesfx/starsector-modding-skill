#!/usr/bin/env python3
"""new_mod.py - scaffold a Starsector mod that builds and validates on the first try, then add code from templates.

  python new_mod.py create --name "Iron Tithe" [--prefix itx_] [--deps lazylib,lunalib] [--author "You"] [--git]
      -> <game>/mods/IronTithe/ with mod_info.json, Version Checker files, a ModPlugin + Ids class, build.sh/.bat,
         tools/ (vendored build_mod.py, validate_mod.py, sslib.py, validate_config.json), README, CHANGELOG,
         .gitignore/.gitattributes. Then run: cd <mod> && ./build.sh   (or build.bat)
  python new_mod.py add hullmod --mod <mod> --id itx_plating --name "Ablative Plating"
  python new_mod.py add list

`add` kinds (Java from templates/java, plus the data wiring that is always the same):
  hullmod        class + hull_mods.csv row (cloned from vanilla heavyarmor: costs, tags, icon)
  system         stats class + .system (cloned from highenergyfocus) + ship_systems.csv row + SHIP_SYSTEM description;
                 --ai also adds a custom AI class and sets aiType CUSTOM
  combat-plugin  every-frame combat plugin + settings.json "plugins" entry
  rulecmd        rules.csv command + settings.json "ruleCommandPackages" entry
  intel          BaseIntelPlugin + settings.json graphics.intel icon entry (a vanilla icon until you draw one)
  onhit | weapon-effect | script | worldgen | fleet | luna     class only; prints where to hook it up
Identifiers: --id is the data id (gets the prefix if missing); the Java class name defaults to ClassPrefix + Name.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sslib  # noqa: E402
import ssdata  # noqa: E402

SKILL = os.path.dirname(HERE)
TEMPLATES = os.path.join(SKILL, "templates")
VENDORED = ["sslib.py", "validate_mod.py", "build_mod.py", "log_scan.py", "package_mod.py"]
DEP_ALIASES = {"lazylib": "lw_lazylib", "magiclib": "MagicLib", "lunalib": "lunalib", "graphicslib": "shaderLib",
               "shaderlib": "shaderLib", "console": "lw_console", "consolecommands": "lw_console"}
ADD_KINDS = {  # kind: (template, sub-package, class suffix)
    "hullmod": ("HullMod.java", "hullmods", ""),
    "system": ("ShipSystemStats.java", "systems", "Stats"),
    "combat-plugin": ("CombatPlugin.java", "combat", "Plugin"),
    "onhit": ("OnHitEffect.java", "combat", "OnHit"),
    "weapon-effect": ("WeaponEffect.java", "combat", "Effect"),
    "rulecmd": ("RuleCommand.java", "rulecmd", ""),
    "intel": ("Intel.java", "campaign", "Intel"),
    "script": ("CampaignScript.java", "campaign", "Script"),
    "worldgen": ("WorldGen.java", "world", "WorldGen"),
    "fleet": ("FleetSpawner.java", "campaign", "FleetSpawner"),
    "luna": ("LunaSettingsBridge.java", "", "Settings"),
}
VANILLA_INTEL_ICON = "graphics/icons/intel/investigation.png"


def words(name):
    return re.findall(r"[A-Za-z0-9]+", name)


def derive(name):
    ws = words(name) or ["mod"]
    mod_id = "_".join(w.lower() for w in ws)
    folder = "".join(w[:1].upper() + w[1:] for w in ws)
    initials = "".join(w[0] for w in ws if w.lower() not in ("the", "of", "a", "an") or len(ws) == 1).lower()
    if len(initials) < 3:
        initials = (initials + ws[0][1:]).lower()[:3]
    return mod_id, folder, initials[:4] + "_"


def subst(text, ctx):
    return re.sub(r"\{\{(\w+)\}\}", lambda m: str(ctx.get(m.group(1), m.group(0))), text)


def render_tree(src, dst, ctx):
    for root, _, files in os.walk(src):
        rel = os.path.relpath(root, src)
        rel = "" if rel == "." else rel
        rel = rel.replace("__PACKAGE_PATH__", ctx["PACKAGE_PATH"])
        for f in files:
            name = f.replace("__MOD_ID__", ctx["MOD_ID"]).replace("__CLASS_PREFIX__", ctx["CLASS_PREFIX"])
            name = re.sub(r"^__(gitignore|gitattributes)$", r".\1", name)
            out = os.path.join(dst, rel, name)
            with open(os.path.join(root, f), encoding="utf-8") as fh:
                text = subst(fh.read(), ctx)
            sslib.write_text(out, text)
            if name.endswith(".sh"):
                os.chmod(out, 0o755)


def cmd_create(a):
    game = sslib.require_game_dir(a.game)
    mod_id, folder, prefix = derive(a.name)
    mod_id = a.id or mod_id
    folder = a.folder or folder
    prefix = (a.prefix or prefix).lower()
    if not prefix.endswith("_"):
        prefix += "_"
    package = a.package or re.sub(r"[^a-z0-9_]", "", prefix.rstrip("_"))
    if not re.match(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$", package):
        package = "m" + package
    class_prefix = "".join(p[:1].upper() + p[1:] for p in re.split(r"[._]", package.split(".")[-1]) if p)
    dest = os.path.join(a.dest or sslib.mods_dir(game), folder)
    if os.path.exists(dest) and not a.force:
        sys.exit("refusing to overwrite %s (pass --force)" % dest)
    installed = sslib.installed_mods(game)
    if mod_id in installed:
        sys.exit("mod id %r is already used by %s; pick another --id" % (mod_id, installed[mod_id][0]))
    deps = []
    for d in [x.strip() for x in (a.deps or "").split(",") if x.strip()]:
        did = DEP_ALIASES.get(d.lower(), d)
        if did not in installed:
            sys.exit("dependency %r (%s) is not installed in %s" % (d, did, sslib.mods_dir(game)))
        deps.append({"id": did, "name": installed[did][1].get("name", did)})
    gv = a.game_version or sslib.game_version(game)
    if not gv:
        sys.exit("could not read the game version; pass --game-version (e.g. 0.98a-RC8)")
    ctx = {
        "MOD_ID": mod_id, "MOD_NAME": a.name, "MOD_FOLDER": folder, "AUTHOR": a.author,
        "DESCRIPTION": a.description or "TODO(scaffold): one or two sentences shown in the launcher.",
        "GAME_VERSION": gv, "JAR_NAME": folder, "PACKAGE": package, "PACKAGE_PATH": package.replace(".", "/"),
        "CLASS_PREFIX": class_prefix, "PREFIX": prefix, "DATE": datetime.date.today().isoformat(),
        "DEPENDENCIES_JSON": json.dumps(deps),
        "DEPENDENCY_LINES": "\n".join("- %s" % d["name"] for d in deps) or "- (no other mods)",
    }
    render_tree(os.path.join(TEMPLATES, "mod"), dest, ctx)
    for f in VENDORED:
        shutil.copy2(os.path.join(HERE, f), os.path.join(dest, "tools", f))
    # mod_info.json: pretty-print the dependency list the template inserted as one line
    mi = os.path.join(dest, "mod_info.json")
    sslib.write_json(mi, json.load(open(mi, encoding="utf-8")))
    print("created %s" % dest)
    print("  id %s, prefix %s, package %s, classes %sModPlugin / %sIds, game %s" % (mod_id, prefix, package, class_prefix,
                                                                                 class_prefix, gv))
    if a.git and shutil.which("git"):
        subprocess.run(["git", "init", "-q"], cwd=dest)
        subprocess.run(["git", "add", "-A"], cwd=dest)
        subprocess.run(["git", "commit", "-q", "-m", "Scaffold %s" % a.name], cwd=dest)
        print("  git repository initialised with a first commit")
    print("next: cd \"%s\" && ./build.sh   (Windows: build.bat). Then `new_mod.py add ...` for code." % dest)
    return dest


def mod_context(mod):
    info = sslib.read_mod_info(mod)
    plugin = info.get("modPlugin") or ""
    if "." not in plugin:
        sys.exit("mod_info.json has no modPlugin; cannot infer the Java package")
    package, cls = plugin.rsplit(".", 1)
    class_prefix = cls[:-len("ModPlugin")] if cls.endswith("ModPlugin") else cls
    cfg, _ = (None, None)
    prefix = None
    for p in (os.path.join(mod, "tools", "validate_config.json"), os.path.join(mod, "validate_config.json")):
        if os.path.isfile(p):
            prefix = sslib.load_loose_json(p).get("prefix")
            break
    prefix = prefix or class_prefix.lower() + "_"
    return {"MOD_ID": info.get("id"), "MOD_NAME": info.get("name"), "PACKAGE_BASE": package,
            "CLASS_PREFIX": class_prefix, "PREFIX": prefix}


def cmd_add(a):
    if a.kind == "list":
        for k, (t, sub, _) in ADD_KINDS.items():
            print("%-14s %-26s -> <package>%s" % (k, t, "." + sub if sub else ""))
        return
    mod = sslib.find_mod_root(a.mod or os.getcwd())
    if not mod:
        sys.exit("no mod_info.json at or above %s" % (a.mod or os.getcwd()))
    ctx = mod_context(mod)
    tpl, sub, suffix = ADD_KINDS[a.kind]
    prefix = ctx["PREFIX"]
    name = a.name or a.kind.replace("-", " ").title()
    did = a.id or (prefix + re.sub(r"\W+", "_", name.lower()).strip("_"))
    if not did.startswith(prefix):
        did = prefix + did
    base = ctx["CLASS_PREFIX"] + "".join(w[:1].upper() + w[1:] for w in words(name))
    cls = a.cls or (base if base.endswith(suffix) else base + suffix)
    package = ctx["PACKAGE_BASE"] + ("." + sub if sub else "")
    tctx = dict(ctx, PACKAGE=package, CLASS=cls, ID=did, NAME=name)
    java = os.path.join(mod, "src", *package.split("."), cls + ".java")
    if os.path.exists(java) and not a.force:
        sys.exit("refusing to overwrite %s (pass --force)" % java)
    with open(os.path.join(TEMPLATES, "java", tpl), encoding="utf-8") as fh:
        sslib.write_text(java, subst(fh.read(), tctx))
    print("wrote %s" % os.path.relpath(java, mod))
    fq = package + "." + cls
    game = sslib.find_game_dir(os.path.dirname(os.path.dirname(mod))) or sslib.require_game_dir(a.game)
    v = ssdata.Vanilla(game)
    if a.kind == "hullmod":
        row = v.clone_row("hull_mods.csv", "heavyarmor", id=did, name=name, script=fq,
                          desc="Increases armor by %s and reduces top speed by %s.",
                          short="More armor, less speed.", sModDesc="")
        ssdata.upsert_csv(mod, "hull_mods.csv", [row], game=game)
        print("upserted data/hullmods/hull_mods.csv row %s (costs/tags/icon cloned from vanilla heavyarmor: edit them)" % did)
    elif a.kind == "system":
        spec = v.spec("system", "highenergyfocus")
        spec["id"] = did
        spec["statsScript"] = fq
        if a.ai:
            ai_cls = cls[:-len("Stats")] + "AI" if cls.endswith("Stats") else cls + "AI"
            with open(os.path.join(TEMPLATES, "java", "ShipSystemAI.java"), encoding="utf-8") as fh:
                ai_path = os.path.join(mod, "src", *package.split("."), ai_cls + ".java")
                sslib.write_text(ai_path, subst(fh.read(), dict(tctx, CLASS=ai_cls)))
            spec["aiType"] = "CUSTOM"
            spec["aiScript"] = package + "." + ai_cls
            print("wrote %s" % os.path.relpath(ai_path, mod))
        ssdata.write_json(os.path.join(mod, "data", "shipsystems", did + ".system"), spec)
        row = v.clone_row("ship_systems.csv", "highenergyfocus", id=did, name=name)
        ssdata.upsert_csv(mod, "ship_systems.csv", [row], game=game)
        ssdata.upsert_description(mod, did, "SHIP_SYSTEM", text1="TODO(scaffold): what %s does." % name, game=game)
        print("wrote data/shipsystems/%s.system, ship_systems.csv row, SHIP_SYSTEM description (cloned from "
              "highenergyfocus: edit timings, flux, icon)" % did)
    elif a.kind == "combat-plugin":
        ssdata.merge_json(os.path.join(mod, "data", "config", "settings.json"), {"plugins": {prefix + cls: fq}})
        print("registered in data/config/settings.json \"plugins\"")
    elif a.kind == "rulecmd":
        ssdata.merge_json(os.path.join(mod, "data", "config", "settings.json"), {"ruleCommandPackages": [package]})
        print("added %s to data/config/settings.json \"ruleCommandPackages\"; use `%s ...` in rules.csv" % (package, cls))
    elif a.kind == "intel":
        ssdata.merge_json(os.path.join(mod, "data", "config", "settings.json"),
                          {"graphics": {"intel": {prefix + "intel": VANILLA_INTEL_ICON}}})
        print("settings.json graphics.intel.%sintel -> %s (vanilla icon; replace with your own 40x40)" % (prefix, VANILLA_INTEL_ICON))
    else:
        hints = {
            "onhit": "set \"onHitEffect\": \"%s\" in a .proj file" % fq,
            "weapon-effect": "set \"everyFrameEffect\" (and/or \"onFireEffect\"): \"%s\" in a .wpn file" % fq,
            "script": "add it in your ModPlugin.onGameLoad: if (!Global.getSector().hasScript(%s.class)) "
                      "Global.getSector().addScript(new %s());" % (cls, cls),
            "worldgen": "call %s.generate(sector) from your ModPlugin's generateIfNeeded" % fq,
            "fleet": "call %s.spawn(factionId, entity, points, hostile) from a script or rule command" % fq,
            "luna": "add lunalib as a dependency (or keep it optional) and a data/config/LunaSettings.csv",
        }
        print("next: " + hints[a.kind])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("create")
    p.add_argument("--name", required=True)
    p.add_argument("--id")
    p.add_argument("--prefix", help="id prefix incl. trailing underscore, e.g. itx_ (default: initials of the name)")
    p.add_argument("--package", help="Java package (default: the prefix without '_')")
    p.add_argument("--folder")
    p.add_argument("--author", default="Unknown")
    p.add_argument("--description")
    p.add_argument("--deps", help="comma list: lazylib, magiclib, lunalib, graphicslib, console, or mod ids")
    p.add_argument("--dest", help="parent folder (default: <game>/mods)")
    p.add_argument("--game-version")
    p.add_argument("--git", action="store_true")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_create)
    p = sub.add_parser("add")
    p.add_argument("kind", choices=sorted(ADD_KINDS) + ["list"])
    p.add_argument("--mod")
    p.add_argument("--id")
    p.add_argument("--name")
    p.add_argument("--class", dest="cls")
    p.add_argument("--ai", action="store_true", help="system: also add a custom AI class")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_add)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
