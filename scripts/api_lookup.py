#!/usr/bin/env python3
"""api_lookup.py - answer Starsector API questions from the game's own source, one command per question.

The game ships its API WITH implementation source: starsector-core/starfarer.api.zip (~1950 .java files: the
interfaces plus com.fs.starfarer.api.impl.*, i.e. vanilla's own campaign, combat, rules and mission code). This tool
extracts it once to a cache and answers the questions that otherwise cost an extract-grep-read cycle each.

  python api_lookup.py class FleetParamsV3             # declaration, supertypes, constructors, methods, constants
  python api_lookup.py class CampaignFleetAPI --doc    # ... plus each member's javadoc
  python api_lookup.py method Misc makeStoryCritical   # full source of the method(s), with javadoc
  python api_lookup.py const MemFlags NO_JUMP          # matching constants: value, javadoc, how often vanilla uses them
  python api_lookup.py uses MEMORY_KEY_NO_JUMP         # every use in vanilla code AND data (copy what vanilla does)
  python api_lookup.py grep "addCustomEntity\\(" --impl -C 2
  python api_lookup.py rulecmd                         # every rules.csv command class; `rulecmd AddRemoveCommodity` = its doc
  python api_lookup.py data "\\$hassle" --ext csv      # grep vanilla data files
  python api_lookup.py javap com.fs.starfarer.api.combat.ShipAPI    # exact compiled signatures (API or library jars)
  python api_lookup.py sources                         # what is searchable (API + library sources found in mods/)

Add --libs to class/method/const/uses/grep to also search library sources (MagicLib, LunaLib, GraphicsLib, Console
Commands) when they are installed. The cache lives in ~/.cache/starsector-modding/<game version>/ (override with the
SS_CACHE environment variable); it is rebuilt automatically when the game's API zip changes.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sslib  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LIB_SOURCES = [  # (label, path relative to the mod folder) - only used when present
    ("MagicLib", "src"),
    ("LunaLib", "src"),
    ("GraphicsLib", "org"),
    ("Console Commands", "src"),
]
DATA_EXT = (".csv", ".json", ".faction", ".ship", ".variant", ".wpn", ".proj", ".system", ".skin")


# ------------------------------------------------------------------------------------------------ source discovery
class Sources:
    def __init__(self, game, cache=None):
        self.game = game
        self.core = sslib.core_dir(game)
        ver = sslib.game_version(game) or "unknown"
        base = cache or os.environ.get("SS_CACHE") or os.path.join(os.path.expanduser("~"), ".cache", "starsector-modding")
        self.cache = os.path.join(base, ver)
        self.api_dir = os.path.join(self.cache, "apisrc")
        self._ensure_extracted()
        self.libs = []
        md = sslib.mods_dir(game)
        for label, sub in LIB_SOURCES:
            p = os.path.join(md, label, sub)
            if os.path.isdir(p):
                self.libs.append((label, p))
        self._index = None

    def _ensure_extracted(self):
        z = os.path.join(self.core, "starfarer.api.zip")
        if not os.path.isfile(z):
            sys.exit("API source zip not found: %s" % z)
        st = os.stat(z)
        stamp = "%d:%d" % (st.st_size, int(st.st_mtime))
        sp = os.path.join(self.cache, "apisrc.stamp")
        if os.path.isdir(self.api_dir) and os.path.isfile(sp) and open(sp).read().strip() == stamp:
            return
        print("[api_lookup] extracting %s -> %s (one time)" % (z, self.api_dir), file=sys.stderr)
        if os.path.isdir(self.api_dir):
            shutil.rmtree(self.api_dir)
        os.makedirs(self.api_dir, exist_ok=True)
        with zipfile.ZipFile(z) as zf:
            zf.extractall(self.api_dir)
        with open(sp, "w") as fh:
            fh.write(stamp)
        ip = os.path.join(self.cache, "index.json")
        if os.path.exists(ip):
            os.remove(ip)

    def roots(self, libs=False, impl=None):
        """[(label, dir)] to search. impl=True -> only api/impl, impl=False -> API without impl."""
        if impl is True:
            out = [("api-impl", os.path.join(self.api_dir, "com", "fs", "starfarer", "api", "impl"))]
        else:
            out = [("api", self.api_dir)]
        if libs:
            out += self.libs
        return out

    def files(self, libs=False, impl=None):
        impl_dir = os.path.join(self.api_dir, "com", "fs", "starfarer", "api", "impl")
        for label, root in self.roots(libs, impl):
            for dp, _, fs in os.walk(root):
                if impl is False and os.path.abspath(dp).startswith(os.path.abspath(impl_dir)):
                    continue
                for f in fs:
                    if f.endswith((".java", ".kt")):
                        yield label, os.path.join(dp, f)

    def index(self):
        """{simple type name: [file path, ...]} including nested types. Cached for the API part."""
        if self._index is not None:
            return self._index
        ip = os.path.join(self.cache, "index.json")
        idx = {}
        if os.path.isfile(ip):
            idx = json.load(open(ip, encoding="utf-8"))
        else:
            for _, p in self.files(libs=False):
                for name in _declared_types(_read(p)):
                    idx.setdefault(name, []).append(p)
            with open(ip, "w", encoding="utf-8") as fh:
                json.dump(idx, fh)
        for label, root in self.libs:
            for dp, _, fs in os.walk(root):
                for f in fs:
                    if f.endswith(".java"):
                        p = os.path.join(dp, f)
                        for name in _declared_types(_read(p)):
                            idx.setdefault(name, []).append(p)
        self._index = idx
        return idx

    def find_type(self, name, libs=False):
        """Files declaring `name` (simple name, Outer.Inner, or a fully qualified name)."""
        simple = name.split(".")[-1].split("$")[-1]
        cands = list(dict.fromkeys(self.index().get(simple, [])))
        if not libs:
            cands = [c for c in cands if os.path.abspath(c).startswith(os.path.abspath(self.api_dir))] or cands
        if "." in name and name[0].islower():  # fully qualified: prefer the matching path
            want = name.replace(".", os.sep)
            exact = [c for c in cands if want in c]
            cands = exact or cands
        return cands

    def rel(self, p):
        ap = os.path.abspath(p)
        if ap.startswith(os.path.abspath(self.api_dir)):
            return os.path.relpath(ap, self.api_dir).replace("\\", "/")
        for label, root in self.libs:
            if ap.startswith(os.path.abspath(root)):
                return "[%s] %s" % (label, os.path.relpath(ap, root).replace("\\", "/"))
        return ap


def _read(p):
    with open(p, encoding="utf-8", errors="replace") as fh:
        return fh.read()


# ------------------------------------------------------------------------------------------------ light Java parsing
def mask_java(text):
    """Same-length copy of `text` with comments and string/char literals blanked (newlines kept)."""
    out = list(text)
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = " "
            i = j
        elif c == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            for k in range(i, j):
                if text[k] != "\n":
                    out[k] = " "
            i = j
        elif c == '"' and text.startswith('"""', i):
            j = text.find('"""', i + 3)
            j = n if j < 0 else j + 3
            for k in range(i + 1, j - 1):
                if text[k] != "\n":
                    out[k] = " "
            i = j
        elif c in "\"'":
            j = i + 1
            while j < n and text[j] != c and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            for k in range(i + 1, min(j, n)):
                out[k] = " "
            i = j + 1
        else:
            i += 1
    return "".join(out)


_TYPE_DECL = re.compile(r"\b(class|interface|enum|record|@interface)\s+([A-Za-z_]\w*)")


def _declared_types(text):
    return [m.group(2) for m in _TYPE_DECL.finditer(mask_java(text))]


def _match_brace(masked, open_pos):
    depth = 0
    for i in range(open_pos, len(masked)):
        ch = masked[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
    return len(masked) - 1


def _javadoc_before(text, masked, pos):
    """Javadoc block that ends right before `pos` (only whitespace/annotations between), else ''."""
    j = pos
    while True:
        k = j
        while k > 0 and text[k - 1] in " \t\r\n":
            k -= 1
        line_start = text.rfind("\n", 0, k) + 1
        line = text[line_start:k].strip()
        if line.startswith("@") and masked[line_start:k].strip().startswith("@"):
            j = line_start
            continue
        if text[:k].endswith("*/"):
            s = text.rfind("/**", 0, k)
            if s >= 0 and "*/" not in text[s + 3:k - 2]:
                return text[s:k]
        return ""


def find_type_body(text, masked, name):
    """(decl_start, body_open, body_close) of type `name` in the file, or None."""
    for m in re.finditer(r"\b(class|interface|enum|record)\s+%s\b" % re.escape(name), masked):
        ob = masked.find("{", m.end())
        if ob < 0:
            continue
        ls = masked.rfind("\n", 0, m.start()) + 1
        return ls, ob, _match_brace(masked, ob)
    return None


def members(text, masked, body_open, body_close):
    """Yield (kind, start, header_end, end) for each member declared directly in a type body.

    kind: 'method' | 'ctor' | 'field' | 'type' | 'init' | 'enumconst'. header = text[start:header_end]."""
    i = body_open + 1
    start = i
    first = True
    while i < body_close:
        ch = masked[i]
        if ch == "{":
            close = _match_brace(masked, i)
            yield _classify(masked, start, i, close + 1, first)
            first = False
            i = close + 1
            start = i
            continue
        if ch == ";":
            yield _classify(masked, start, i, i + 1, first)
            first = False
            start = i + 1
        i += 1


def _classify(masked, start, header_end, end, first):
    h = masked[start:header_end]
    st = start + (len(h) - len(h.lstrip()))
    hs = re.sub(r"@\w+(\([^)]*\))?", " ", h).strip()
    if not hs:
        return ("init", st, header_end, end)
    if re.search(r"\b(class|interface|enum|record)\s+\w+", hs):
        return ("type", st, header_end, end)
    if "(" in hs:
        pre = hs.split("(", 1)[0]
        if "=" in pre:
            return ("field", st, header_end, end)
        toks = pre.split()
        if len(toks) == 1 or (toks and toks[-2:-1] and toks[-2] in ("public", "protected", "private")):
            if first and len(toks) == 1 and toks[0].isupper():
                return ("enumconst", st, header_end, end)
            return ("ctor", st, header_end, end)
        return ("method", st, header_end, end)
    if first and re.match(r"^[A-Z_0-9]+\s*(,|$)", hs):
        return ("enumconst", st, header_end, end)
    return ("field", st, header_end, end)


def _clean(s):
    return re.sub(r"\s+", " ", s).strip()


def _strip_doc(doc):
    lines = []
    for ln in doc.splitlines():
        ln = ln.strip()
        ln = re.sub(r"^/\*\*|\*/$", "", ln).strip()
        ln = re.sub(r"^\* ?", "", ln)
        lines.append(ln)
    return "\n".join(x for x in lines).strip()


# ------------------------------------------------------------------------------------------------ commands
def cmd_class(src, a):
    files = src.find_type(a.name, a.libs)
    if not files:
        sys.exit("no type named %r in the API%s. Try: api_lookup.py grep %s" % (a.name, " or libs" if a.libs else "", a.name))
    simple = a.name.split(".")[-1].split("$")[-1]
    for p in files[: a.max_files]:
        text = _read(p)
        masked = mask_java(text)
        tb = find_type_body(text, masked, simple)
        if not tb:
            continue
        ds, ob, cb = tb
        decl = _clean(text[ds:ob])
        print("=" * 100)
        print("%s  (line %d)" % (src.rel(p), text.count("\n", 0, ds) + 1))
        doc = _javadoc_before(text, masked, ds)
        if doc and a.doc:
            print(_indent(_strip_doc(doc), "  // "))
        print(decl + " {")
        groups = {"enumconst": [], "field": [], "ctor": [], "method": [], "type": []}
        for kind, st, he, en in members(text, masked, ob, cb):
            if kind == "init":
                continue
            head = text[st:he]
            headm = masked[st:he]
            if kind in ("field",) and not a.all and "private" in headm.split("=")[0].split():
                continue
            if kind in ("method", "ctor") and not a.all and re.search(r"\bprivate\b", headm.split("(")[0]):
                continue
            line = text.count("\n", 0, st) + 1
            shown = _clean(re.sub(r"/\*.*?\*/|//[^\n]*", " ", head, flags=re.S))
            if kind == "field":
                shown = _clean(re.sub(r"/\*.*?\*/|//[^\n]*", " ", text[st:en], flags=re.S))
                if len(shown) > 160:
                    shown = shown[:157] + "..."
            if kind == "type":
                shown = shown.split("{")[0]
            entry = "  %5d  %s" % (line, shown)
            if a.doc:
                d = _javadoc_before(text, masked, st)
                if d:
                    entry = _indent(_strip_doc(d), "         // ") + "\n" + entry
            groups[kind].append(entry)
        for kind, title in (("enumconst", "enum constants"), ("field", "fields"), ("ctor", "constructors"),
                            ("method", "methods"), ("type", "nested types")):
            if groups[kind]:
                print("  -- %s (%d)" % (title, len(groups[kind])))
                for e in groups[kind]:
                    print(e)
        print("}")
    if len(files) > a.max_files:
        print("(%d more files declare %s; use a fully qualified name)" % (len(files) - a.max_files, simple))


def _indent(s, pre):
    return "\n".join(pre + ln for ln in s.splitlines())


def cmd_method(src, a):
    files = src.find_type(a.cls, a.libs)
    if not files:
        sys.exit("no type named %r" % a.cls)
    simple = a.cls.split(".")[-1].split("$")[-1]
    found = 0
    for p in files:
        text = _read(p)
        masked = mask_java(text)
        tb = find_type_body(text, masked, simple)
        if not tb:
            continue
        _, ob, cb = tb
        for kind, st, he, en in members(text, masked, ob, cb):
            if kind not in ("method", "ctor"):
                continue
            name = masked[st:he].split("(")[0].split()[-1] if masked[st:he].split("(")[0].split() else ""
            if name != a.name:
                continue
            found += 1
            d = _javadoc_before(text, masked, st)
            s0 = text.rfind(d, 0, st) if d else st
            s0 = text.rfind("\n", 0, s0) + 1
            print("=" * 100)
            print("%s:%d" % (src.rel(p), text.count("\n", 0, st) + 1))
            body = text[s0:en]
            lines = body.splitlines()
            if len(lines) > a.max_lines:
                lines = lines[: a.max_lines] + ["    ... (%d more lines)" % (len(body.splitlines()) - a.max_lines)]
            print("\n".join(lines))
    if not found:
        sys.exit("no method %s in %s (inherited? check the supertypes printed by `class %s`)" % (a.name, a.cls, a.cls))


def cmd_const(src, a):
    files = src.find_type(a.cls, a.libs)
    if not files:
        sys.exit("no type named %r" % a.cls)
    simple = a.cls.split(".")[-1].split("$")[-1]
    pat = re.compile(a.pattern or ".", re.I)
    rows = []
    for p in files[:1]:
        text = _read(p)
        masked = mask_java(text)
        tb = find_type_body(text, masked, simple)
        if not tb:
            continue
        _, ob, cb = tb
        iface = bool(re.search(r"\binterface\s+%s\b" % re.escape(simple), masked[tb[0]:ob]))
        for kind, st, he, en in members(text, masked, ob, cb):
            if kind not in ("field", "enumconst"):
                continue
            hm = masked[st:en]
            mods = hm.split("=")[0].split()
            if kind == "field" and not iface and "static" not in mods:
                continue
            decl = _clean(re.sub(r"/\*.*?\*/|//[^\n]*", " ", text[st:en], flags=re.S))
            if kind == "field" and not iface and "final" not in mods:
                decl += "   [static, NOT final: set at runtime]"
            if kind == "enumconst":
                names = [x.strip().split("(")[0] for x in hm.split(",") if x.strip()]
            else:
                m = re.search(r"(\w+)\s*=", hm)
                names = [m.group(1)] if m else []
            for nm in names:
                if pat.search(nm):
                    rows.append((nm, decl if kind == "field" else "%s.%s (enum)" % (simple, nm),
                                 _strip_doc(_javadoc_before(text, masked, st)), text.count("\n", 0, st) + 1))
    if not rows:
        sys.exit("no constants matching %r in %s" % (a.pattern, a.cls))
    all_files = list(src.files(libs=a.libs))
    for nm, decl, doc, line in rows:
        rx = re.compile(r"\b%s\b" % re.escape(nm))
        users = []
        for _, p in all_files:
            t = _read(p)
            n = len(rx.findall(t))
            if n and os.path.basename(p) != simple + ".java":
                users.append((n, src.rel(p)))
        users.sort(reverse=True)
        print("-" * 100)
        print("%s  (line %d)" % (decl, line))
        if doc:
            print(_indent(doc, "    // "))
        tot = sum(u[0] for u in users)
        print("    used %d time(s) in %d other file(s)%s" % (tot, len(users), ":" if users else ""))
        for n, r in users[: a.max_users]:
            print("      %3d  %s" % (n, r))


def _grep(src, rx, libs, impl, ctx, max_hits, show_label=True):
    hits = 0
    for label, p in src.files(libs=libs, impl=impl):
        lines = _read(p).splitlines()
        for i, ln in enumerate(lines):
            if rx.search(ln):
                hits += 1
                if hits > max_hits:
                    return hits
                lo, hi = max(0, i - ctx), min(len(lines), i + ctx + 1)
                if ctx:
                    print("-- %s:%d" % (src.rel(p), i + 1))
                    for k in range(lo, hi):
                        print("%s%5d: %s" % (">" if k == i else " ", k + 1, lines[k].rstrip()))
                else:
                    print("%s:%d: %s" % (src.rel(p), i + 1, ln.strip()[:220]))
    return hits


def cmd_grep(src, a):
    rx = re.compile(a.regex, re.I if a.i else 0)
    impl = True if a.impl else (False if a.api else None)
    n = _grep(src, rx, a.libs, impl, a.C, a.max)
    if n > a.max:
        print("... more than %d hits; narrow the regex or add --impl/--api" % a.max)
    elif n == 0:
        print("no hits")


def _data_files(core, exts):
    for dp, _, fs in os.walk(os.path.join(core, "data")):
        for f in fs:
            if f.endswith(exts):
                yield os.path.join(dp, f)


def cmd_uses(src, a):
    rx = re.compile(r"(?<![\w$])%s(?![\w])" % re.escape(a.symbol))
    print("== code (%s)" % ("API + libs" if a.libs else "API incl. impl"))
    n = _grep(src, rx, a.libs, None, 0, a.max)
    if n == 0:
        print("   no hits")
    print("== vanilla data")
    k = 0
    for p in _data_files(src.core, DATA_EXT):
        for i, ln in enumerate(open(p, encoding="utf-8", errors="replace")):
            if rx.search(ln):
                k += 1
                if k <= a.max:
                    print("%s:%d: %s" % (os.path.relpath(p, src.core).replace("\\", "/"), i + 1, ln.strip()[:220]))
    if k == 0:
        print("   no hits")
    elif k > a.max:
        print("   ... %d hits total" % k)


def cmd_data(src, a):
    rx = re.compile(a.regex, re.I if a.i else 0)
    exts = tuple("." + e.lstrip(".") for e in a.ext.split(",")) if a.ext else DATA_EXT
    k = 0
    for p in _data_files(src.core, exts):
        r = os.path.relpath(p, src.core).replace("\\", "/")
        if a.files and not re.search(a.files, r):
            continue
        for i, ln in enumerate(open(p, encoding="utf-8", errors="replace")):
            if rx.search(ln):
                k += 1
                if k <= a.max:
                    print("%s:%d: %s" % (r, i + 1, ln.strip()[:240]))
    if k > a.max:
        print("... %d hits total" % k)
    elif k == 0:
        print("no hits")


def _rule_packages(core):
    try:
        s = sslib.load_loose_json(os.path.join(core, "data", "config", "settings.json"))
        return s.get("ruleCommandPackages") or []
    except Exception:
        return ["com.fs.starfarer.api.impl.campaign.rulecmd"]


def cmd_rulecmd(src, a):
    pk = _rule_packages(src.core)
    cmds = {}
    for p in pk:
        d = os.path.join(src.api_dir, *p.split("."))
        if os.path.isdir(d):
            for f in os.listdir(d):
                if f.endswith(".java"):
                    cmds.setdefault(f[:-5], os.path.join(d, f))
    if not a.name:
        names = sorted(cmds, key=str.lower)
        print("%d rule commands in %s" % (len(names), ", ".join(pk)))
        w = max(len(n) for n in names) + 2
        per = max(1, 110 // w)
        for i in range(0, len(names), per):
            print("".join(n.ljust(w) for n in names[i:i + per]))
        print("\n`api_lookup.py rulecmd <Name>` prints a command's documentation and argument parsing.")
        return
    p = cmds.get(a.name)
    if not p:
        close = [n for n in cmds if a.name.lower() in n.lower()]
        sys.exit("no rule command %r. Similar: %s" % (a.name, ", ".join(close[:10]) or "none"))
    text = _read(p)
    masked = mask_java(text)
    tb = find_type_body(text, masked, a.name)
    print("=" * 100)
    print(src.rel(p))
    if tb:
        doc = _javadoc_before(text, masked, tb[0])
        if doc:
            print(_strip_doc(doc))
            print()
        for kind, st, he, en in members(text, masked, tb[1], tb[2]):
            if kind == "method" and re.search(r"\bexecute\s*\(", masked[st:he]):
                body = text[st:en].splitlines()
                print("\n".join(body[: a.max_lines]))
                if len(body) > a.max_lines:
                    print("    ... (%d more lines; `api_lookup.py method %s execute`)" % (len(body) - a.max_lines, a.name))
    k = 0
    rx = re.compile(r"(?<![\w$])%s\b" % re.escape(a.name))
    for line in open(os.path.join(src.core, "data", "campaign", "rules.csv"), encoding="utf-8", errors="replace"):
        if rx.search(line):
            k += 1
            if k <= a.examples:
                print("rules.csv example: %s" % line.strip()[:200])
    print("(%d line(s) in vanilla rules.csv use it)" % k)


def cmd_javap(src, a):
    jp = shutil.which("javap")
    if not jp:
        sys.exit("javap not on PATH (install a JDK 17)")
    jars = [os.path.join(src.core, "starfarer.api.jar")]
    for mid, (folder, info) in sslib.installed_mods(src.game).items():
        jars += sslib.mod_jars(folder, info)
    target = a.fqcn
    for j in jars:
        cl = sslib.jar_classes(j)
        if target in cl or target.replace(".", "$") in cl:
            out = subprocess.run([jp, "-public" if not a.private else "-private", "-cp", j, target],
                                 capture_output=True, text=True)
            print("# from %s" % j)
            print(out.stdout or out.stderr)
            return
        simple = [c for c in cl if c.split(".")[-1] == target]
        if simple:
            print("# %s: did you mean %s" % (os.path.basename(j), ", ".join(sorted(simple)[:5])))
    sys.exit("class %s not found in the API jar or installed mods' jars" % target)


def cmd_sources(src, a):
    print("API source : %s (%d files)" % (src.api_dir, sum(1 for _ in src.files())))
    for label, root in src.libs:
        print("library    : %-16s %s" % (label, root))
    print("javap jars : starfarer.api.jar + jars of installed mods:")
    for mid, (folder, info) in sslib.installed_mods(src.game).items():
        print("             %-18s %s" % (mid, ", ".join(os.path.basename(j) for j in sslib.mod_jars(folder, info))))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", help="Starsector install folder (default: auto-detect)")
    ap.add_argument("--cache", help="cache folder (default ~/.cache/starsector-modding)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("class", help="summarise a type")
    p.add_argument("name")
    p.add_argument("--doc", action="store_true", help="include javadoc")
    p.add_argument("--all", action="store_true", help="include private members")
    p.add_argument("--libs", action="store_true")
    p.add_argument("--max-files", type=int, default=3)
    p.set_defaults(fn=cmd_class)

    p = sub.add_parser("method", help="print the full source of a method")
    p.add_argument("cls")
    p.add_argument("name")
    p.add_argument("--libs", action="store_true")
    p.add_argument("--max-lines", type=int, default=150)
    p.set_defaults(fn=cmd_method)

    p = sub.add_parser("const", help="constants of a class (MemFlags, Tags, Stats, Factions...)")
    p.add_argument("cls")
    p.add_argument("pattern", nargs="?", default="")
    p.add_argument("--libs", action="store_true")
    p.add_argument("--max-users", type=int, default=8)
    p.set_defaults(fn=cmd_const)

    p = sub.add_parser("uses", help="every use of a symbol in vanilla code and data")
    p.add_argument("symbol")
    p.add_argument("--libs", action="store_true")
    p.add_argument("--max", type=int, default=40)
    p.set_defaults(fn=cmd_uses)

    p = sub.add_parser("grep", help="regex search over the sources")
    p.add_argument("regex")
    p.add_argument("--impl", action="store_true", help="only com.fs.starfarer.api.impl (vanilla's own code)")
    p.add_argument("--api", action="store_true", help="only the API (no impl)")
    p.add_argument("--libs", action="store_true")
    p.add_argument("-C", type=int, default=0, help="context lines")
    p.add_argument("-i", action="store_true", help="ignore case")
    p.add_argument("--max", type=int, default=60)
    p.set_defaults(fn=cmd_grep)

    p = sub.add_parser("data", help="regex search over vanilla data files")
    p.add_argument("regex")
    p.add_argument("--ext", help="comma list of extensions, e.g. csv,json")
    p.add_argument("--files", help="regex on the relative path, e.g. rules.csv")
    p.add_argument("-i", action="store_true")
    p.add_argument("--max", type=int, default=60)
    p.set_defaults(fn=cmd_data)

    p = sub.add_parser("rulecmd", help="list rules.csv commands, or show one command's doc")
    p.add_argument("name", nargs="?")
    p.add_argument("--max-lines", type=int, default=60)
    p.add_argument("--examples", type=int, default=5)
    p.set_defaults(fn=cmd_rulecmd)

    p = sub.add_parser("javap", help="compiled public signatures of a class (API or installed library jars)")
    p.add_argument("fqcn")
    p.add_argument("--private", action="store_true")
    p.set_defaults(fn=cmd_javap)

    p = sub.add_parser("sources", help="show what is searchable")
    p.set_defaults(fn=cmd_sources)

    a = ap.parse_args()
    for attr in ("regex", "pattern"):
        if getattr(a, attr, None):
            try:
                re.compile(getattr(a, attr))
            except re.error as e:
                sys.exit("invalid regular expression %r: %s (escape special characters, e.g. \\$ or \\()"
                         % (getattr(a, attr), e))
    game = sslib.require_game_dir(a.game)
    src = Sources(game, a.cache)
    a.fn(src, a)


if __name__ == "__main__":
    main()
