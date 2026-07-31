#!/usr/bin/env python3
"""JUNA-Lite explorer - unified workbench for the migrated package.

Serves http://127.0.0.1:8772/ with pages Home | Tests | Map | Chain |
Source | Coverage | Health | Progress, all rendered by one shell, plus a
JSON API layer (/api/*) wrapping every response in a provenance envelope
{commit, working_tree_dirty, generated_at, schema_version, data}.

Architecture: authoritative inputs (test/runtests.jl SUITES registry via
suites.json, chain.json stage semantics) feed a Python data layer (the
vendored source analyzer, the static coverage scanner, git state, run and
health managers); pages are server-rendered from the same data functions
the APIs expose, with small vanilla-JS modules (static/) for interactivity.
The vendored analyzer's own HTML page remains available at /source-legacy;
the /source tab is this product's unified page.

Evidence taxonomy (formal, used by API and UI): static call edge ·
interface implementation · direct test reference · suite-wide association ·
runtime result. Static evidence is never presented as execution.

Run:  python3 tools/explorer/server.py [--port 8772]
"""
import argparse
import html
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

import source_coverage  # noqa: E402
import source_symbol_explorer as source_symbols  # noqa: E402

SOURCE_SHA = "d49fff0"  # sonique research/JunaCore provenance (see README.md)
SONIQUE_CORE = "/home/gabiel/Documents/GitHub/BP/sonique/research/JunaCore"
SCHEMA_VERSION = 1
NAV = [("/", "Home"), ("/tests", "Tests"), ("/map", "Map"),
       ("/chain", "Chain"), ("/source", "Source"), ("/coverage", "Coverage"),
       ("/health", "Health"), ("/progress", "Progress")]
INTERFACE_METHODS = {"init", "modulate", "demodulate", "bitspersymbol",
                     "signallength", "payload_rate", "refinement_objective",
                     "frameblockcount", "framepayloadbits"}
TAXONOMY = [("Static call edge", "the analyzer found a lexical call"),
            ("Interface implementation",
             "the method extends the public Modulations contract"),
            ("Direct test reference", "a suite explicitly names the symbol"),
            ("Suite-wide association",
             "declared through a chain stage, not named directly"),
            ("Runtime result",
             "browser-recorded run outcome - separate from static evidence")]
TAXONOMY_NOTE = "Static edges and references never imply the code executed."

# ---------------------------------------------------------------- data layer


class _Cache:
    def __init__(self, loader, paths):
        self.loader, self.paths, self.stamp, self.value = loader, paths, None, None

    def get(self):
        stamp = tuple(os.path.getmtime(p) if os.path.exists(p) else 0
                      for p in self.paths)
        if stamp != self.stamp:
            self.value = self.loader()
            self.stamp = stamp
        return self.value


def _src_files():
    out = []
    for base, _dirs, files in os.walk(os.path.join(ROOT, "src")):
        out.extend(os.path.join(base, f) for f in files if f.endswith(".jl"))
    return sorted(out)


def _load_suites():
    with open(os.path.join(HERE, "suites.json")) as fh:
        return json.load(fh)["suites"]


def _load_chain():
    with open(os.path.join(HERE, "chain.json")) as fh:
        return json.load(fh)

def _load_receivers():
    with open(os.path.join(HERE, "receivers.json")) as fh:
        return json.load(fh)["receivers"]


SUITES_CACHE = _Cache(_load_suites, [os.path.join(HERE, "suites.json")])
CHAIN_CACHE = _Cache(_load_chain, [os.path.join(HERE, "chain.json")])
RECEIVERS_CACHE = _Cache(_load_receivers,
                         [os.path.join(HERE, "receivers.json")])
ANALYZE_CACHE = _Cache(lambda: source_symbols.analyze(os.path.join(ROOT, "src")),
                       _src_files())
COVERAGE_CACHE = _Cache(lambda: source_coverage.scan(ROOT),
                        _src_files() +
                        [os.path.join(HERE, "suites.json")] +
                        [os.path.join(ROOT, "test", f)
                         for f in sorted(os.listdir(os.path.join(ROOT, "test")))
                         if f.endswith(".jl")])

_GIT_STATE = {"stamp": 0.0, "value": None}


def git_state():
    now = time.time()
    if _GIT_STATE["value"] is not None and now - _GIT_STATE["stamp"] < 2.0:
        return _GIT_STATE["value"]
    try:
        head = subprocess.run(["git", "log", "-1", "--format=%h\t%s"],
                              capture_output=True, text=True, cwd=ROOT,
                              timeout=5).stdout.strip()
        sha, _, subject = head.partition("\t")
        porcelain = subprocess.run(["git", "status", "--porcelain", "--", "."],
                                   capture_output=True, text=True, cwd=ROOT,
                                   timeout=5).stdout.splitlines()
    except Exception:
        sha, subject, porcelain = "", "(git unavailable)", []
    modified = [ln[3:] for ln in porcelain if ln and not ln.startswith("??")]
    untracked = [ln[3:] for ln in porcelain if ln.startswith("??")]
    value = {"head": sha, "subject": subject,
             "dirty": bool(modified or untracked),
             "modified": modified, "untracked": untracked}
    _GIT_STATE.update(stamp=now, value=value)
    return value


def envelope(data):
    gs = git_state()
    return json.dumps({
        "commit": gs["head"],
        "working_tree_dirty": gs["dirty"],
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "schema_version": SCHEMA_VERSION,
        "data": data,
    })


def suites_stale():
    reg = os.path.getmtime(os.path.join(ROOT, "test", "runtests.jl"))
    exp = os.path.getmtime(os.path.join(HERE, "suites.json"))
    return reg > exp


def run_history():
    path = os.path.join(ROOT, "bench", "test_runs.jsonl")
    if not os.path.exists(path):
        return []
    records = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def last_run_by_key():
    out = {}
    for rec in run_history():
        out[rec.get("key")] = rec
    return out


_FILE_LINES = {}


def _file_lines(rel):
    path = os.path.join(ROOT, "src", rel)
    mtime = os.path.getmtime(path) if os.path.exists(path) else 0
    cached = _FILE_LINES.get(rel)
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        with open(path) as fh:
            lines = fh.read().split("\n")
    except OSError:
        lines = []
    _FILE_LINES[rel] = (mtime, lines)
    return lines


def _extract_doc(sym):
    """Docstring immediately above the definition, or None. Honest: no
    editorial prose is ever synthesized."""
    if sym.get("doc"):
        return sym["doc"]
    lines = _file_lines(sym["file"])
    j = sym["line"] - 2  # 0-based line above the definition
    while j >= 0 and not lines[j].strip():
        j -= 1
    if j < 0 or not lines[j].rstrip().endswith('"""'):
        return None
    if lines[j].strip() != '"""' and lines[j].strip().count('"""') == 2:
        return lines[j].strip().strip('"')
    k = j - 1
    while k >= 0 and '"""' not in lines[k]:
        k -= 1
    if k < 0:
        return None
    body = lines[k:j + 1]
    body[0] = body[0].split('"""', 1)[1]
    body[-1] = body[-1].rsplit('"""', 1)[0]
    text = "\n".join(body).strip()
    return text or None


def _symbol_index():
    data = ANALYZE_CACHE.get()
    by_id = {s["id"]: s for s in data["symbols"]}
    by_name = {}
    for s in data["symbols"]:
        by_name.setdefault(s["name"], []).append(s)
    return data, by_id, by_name


def _symbol_lookup(token):
    _data, by_id, by_name = _symbol_index()
    if token.isdigit() and int(token) in by_id:
        return by_id[int(token)]
    if "." in token:
        module, _, name = token.rpartition(".")
        qualified = [s for s in by_name.get(name, [])
                     if s.get("module") == module]
        if qualified:
            for match in qualified:
                if match["kind"] in ("function", "type", "struct"):
                    return match
            return qualified[0]
    matches = by_name.get(token)
    if not matches:
        return None
    for m in matches:
        if m["kind"] in ("function", "type", "struct"):
            return m
    return matches[0]


def _ref(by_id, sid):
    s = by_id.get(sid)
    return {"id": s["id"], "name": s["name"], "kind": s["kind"]} if s else None


def symbol_detail(sym):
    _data, by_id, by_name = _symbol_index()
    chain = CHAIN_CACHE.get()
    report = COVERAGE_CACHE.get()
    last = last_run_by_key()

    calls = [r for r in (_ref(by_id, i) for i in sym.get("calls", [])) if r]
    callers = [r for r in (_ref(by_id, i) for i in sym.get("callers", [])) if r]
    overloads = [{"id": s["id"], "sig": s["sig"], "file": s["file"],
                  "line": s["line"]}
                 for s in by_name.get(sym["name"], [])]
    stages = [{"id": st["id"], "title": st["title"]}
              for st in chain["stages"] if sym["name"] in st["symbols"]]

    direct = []
    for key, entry in report["suites"].items():
        lines = entry.get("direct", {}).get(sym["name"])
        if lines:
            direct.append({"suite": key, "lines": lines[:12]})
    direct_keys = {d["suite"] for d in direct}
    suite_wide = sorted({key for st in chain["stages"]
                         if sym["name"] in st["symbols"]
                         for key in st["suites"]} - direct_keys)
    involved = sorted(direct_keys | set(suite_wide))
    runtime = [{"suite": k, "status": last[k].get("status"),
                "ended": last[k].get("ended")}
               for k in involved if k in last]

    iface = (f"extends the public Modulations interface method "
             f"'{sym['name']}'" if sym["name"] in INTERFACE_METHODS else False)
    type_methods = []
    facades = []
    if sym["kind"] in ("struct", "type"):
        type_methods = [
            {"id": candidate["id"], "name": candidate["name"],
             "kind": candidate["kind"]}
            for candidate in _data["symbols"]
            if candidate["name"] in INTERFACE_METHODS and
            candidate.get("recv") == sym["name"] and
            (candidate["module"] == sym["module"] or
             sym["module"] == "Modulations")
        ]
        if sym["module"] == "Juna" and sym["name"] == "Modulation":
            facades = [
                {"id": candidate["id"], "name": candidate["module"],
                 "kind": "facade"}
                for candidate in _data["symbols"]
                if candidate["name"] == "Modulation" and
                candidate["kind"] == "const" and
                candidate["module"] in
                {"JunaStandard", "JunaPartialFFT", "JunaLite"}
            ]

    return {
        "id": sym["id"], "name": sym["name"], "qual": sym.get("qual"),
        "kind": sym["kind"], "module": sym["module"], "file": sym["file"],
        "line": sym["line"], "sig": sym["sig"], "src": sym.get("src"),
        "super": sym.get("super"), "recv": sym.get("recv"),
        "doc": _extract_doc(sym),
        "fields": _struct_fields(sym),
        "interface_methods": type_methods,
        "facades": facades,
        "overloads": overloads, "calls": calls, "callers": callers,
        "chain_stages": stages,
        "evidence": {
            "static_call_edges": {"calls": len(calls), "callers": len(callers)},
            "interface_implementation": iface,
            "direct_test_references": direct,
            "suite_wide_associations": suite_wide,
            "runtime_results": runtime,
            "note": TAXONOMY_NOTE,
        },
    }

def _struct_fields(sym):
    """Extract declared struct fields without inventing documentation."""
    if sym.get("kind") != "struct":
        return []
    fields = []
    for line in (sym.get("src") or "").splitlines()[1:]:
        stripped = line.strip()
        if not stripped or stripped == "end" or stripped.startswith("#"):
            continue
        code, _, comment = stripped.partition("#")
        match = re.match(
            r"([A-Za-z_][A-Za-z0-9_!]*)\s*::\s*([^=]+?)(?:\s*=\s*(.*))?$",
            code.strip())
        if match:
            fields.append({"name": match.group(1),
                           "type": match.group(2).strip(),
                           "default": (match.group(3) or "").strip() or None,
                           "comment": comment.strip() or None})
    return fields


def graph_data(query):
    """Context-filtered static graph. Edges are lexical, never runtime."""
    params = urllib.parse.parse_qs(query or "")
    analyzed, by_id, by_name = _symbol_index()
    symbols = [s for s in analyzed["symbols"] if s["kind"] != "module"]
    chosen = None
    context = []

    def narrow(ids, kind, value, label):
        nonlocal chosen
        ids = set(ids)
        chosen = ids if chosen is None else chosen & ids
        context.append({"kind": kind, "value": value, "label": label})

    file_name = params.get("file", [None])[0]
    if file_name:
        narrow((s["id"] for s in symbols if s["file"] == file_name),
               "file", file_name, f"src/{file_name}")

    chain = CHAIN_CACHE.get()
    stage_id = params.get("stage", [None])[0]
    if stage_id:
        stage = next((s for s in chain["stages"] if s["id"] == stage_id),
                     None)
        if stage:
            narrow((s["id"] for name in stage["symbols"]
                    for s in by_name.get(name, [])),
                   "stage", stage_id, stage["title"])

    receiver_id = params.get("receiver", [None])[0]
    if receiver_id:
        receiver = next((r for r in chain["receivers"]
                         if r["id"] == receiver_id), None)
        catalog = next((r for r in RECEIVERS_CACHE.get()
                        if r["id"] == receiver_id), None)
        if receiver and catalog:
            stage_ids = receiver["path"] + receiver.get("optional_stages", [])
            names = {name for st in chain["stages"] if st["id"] in stage_ids
                     for name in st["symbols"]}
            ids = {s["id"] for name in names for s in by_name.get(name, [])}
            ids.update(s["id"] for s in symbols
                       if s.get("module") == catalog["facade"])
            narrow(ids, "receiver", receiver_id, catalog["display_name"])

    suite_key = params.get("suite", [None])[0]
    if suite_key:
        report = COVERAGE_CACHE.get()
        direct = report["suites"].get(suite_key, {}).get("direct", {})
        names = set(direct)
        names.update(name for st in chain["stages"]
                     if suite_key in st["suites"] for name in st["symbols"])
        narrow((s["id"] for name in names for s in by_name.get(name, [])),
               "suite", suite_key, f"Suite: {suite_key}")

    token = params.get("symbol", [None])[0]
    if token:
        sym = _symbol_lookup(token)
        if sym:
            ids = {sym["id"], *sym.get("calls", []), *sym.get("callers", [])}
            narrow(ids, "symbol", token, f"Symbol: {sym['name']}")

    selected = {s["id"] for s in symbols} if chosen is None else chosen
    nodes = [{"id": s["id"], "name": s["name"], "kind": s["kind"],
              "module": s["module"], "file": s["file"], "line": s["line"]}
             for s in symbols if s["id"] in selected]
    edges = []
    seen = set()
    for s in symbols:
        if s["id"] not in selected:
            continue
        for target in s.get("calls", []):
            edge = (s["id"], target)
            if target in selected and edge not in seen:
                seen.add(edge)
                edges.append({"from": s["id"], "to": target,
                              "kind": "static_call"})
    return {"context": context, "nodes": nodes, "edges": edges,
            "note": TAXONOMY_NOTE}


def palette_index():
    items = [{"label": label, "kind": "page", "href": href, "hint": "page"}
             for href, label in NAV]
    for s in SUITES_CACHE.get():
        items.append({"label": s["key"], "kind": "suite",
                      "href": f"/tests#{s['key']}", "hint": s["title"]})
    for st in CHAIN_CACHE.get()["stages"]:
        items.append({"label": st["title"], "kind": "stage",
                      "href": f"/chain#{st['id']}", "hint": st["kind"]})
    for receiver in RECEIVERS_CACHE.get():
        items.append({"label": receiver["display_name"], "kind": "receiver",
                      "href": f"/chain?receiver={receiver['id']}",
                      "hint": receiver["facade"]})
    data = ANALYZE_CACHE.get()
    for m in data["modules"]:
        items.append({"label": m["name"], "kind": "module", "href": "/source",
                      "hint": f"{m['count']} symbols"})
    for s in data["symbols"]:
        if s["kind"] == "module":
            continue
        items.append({"label": s["name"], "kind": "symbol",
                      "href": f"/source#sym={urllib.parse.quote(s['name'])}",
                      "hint": f"{s['kind']} · {s['module']} · {s['file']}"})
    return items

# ---------------------------------------------------------------- run manager


class Run:
    def __init__(self, key, file):
        self.key, self.file = key, file
        self.lines = []
        self.status = "running"
        self.returncode = None
        self.started = time.time()
        self.proc = subprocess.Popen(
            ["julia", "--project=.", os.path.join("test", file)],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True)
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        for line in self.proc.stdout:
            self.lines.append(line)
        self.proc.wait()
        self.returncode = self.proc.returncode
        if self.status != "cancelled":
            self.status = "passed" if self.returncode == 0 else "failed"
        record = {"key": self.key, "file": self.file,
                  "started": round(self.started, 2),
                  "ended": round(time.time(), 2),
                  "returncode": self.returncode, "status": self.status,
                  "commit": git_state()["head"],
                  "dirty": git_state()["dirty"]}
        os.makedirs(os.path.join(ROOT, "bench"), exist_ok=True)
        with open(os.path.join(ROOT, "bench", "test_runs.jsonl"), "a") as fh:
            fh.write(json.dumps(record) + "\n")

    def cancel(self):
        self.status = "cancelled"
        try:
            self.proc.terminate()
        except Exception:
            pass


RUNS = {}
RUNS_LOCK = threading.Lock()

# --------------------------------------------------------------- health layer

HEALTH_CHECKS = [
    ("provenance-pins", "Provenance pins",
     ["julia", "--project=.", "test/provenance_contract.jl"]),
    ("explorer-data", "Explorer data C1-C7",
     ["python3", "tools/explorer/explorer_contract.py"]),
    ("server-behavior", "Explorer server S1-S13",
     ["python3", "tools/explorer/server_contract.py"]),
    ("package-load", "Package load",
     ["julia", "--project=.", "-e", 'using JunaCore; println("load OK")']),
    ("pkg-test", "Full Pkg.test",
     ["julia", "--project=.", "-e", "using Pkg; Pkg.test()"]),
    ("parity-migrated", "Parity digest (this repo)",
     ["julia", "--project=.", "tools/parity_check.jl"]),
    ("parity-source", "Parity digest (source repo)",
     ["julia", "--project=" + SONIQUE_CORE, "tools/parity_check.jl"]),
]
HEALTH_BATTERY = ["provenance-pins", "explorer-data", "server-behavior",
                  "package-load"]
HEALTH_TIMEOUT_S = 1800
HEALTH = {"run": None}
HEALTH_LOCK = threading.Lock()


class HealthRun:
    """Runs an allowlisted subset of HEALTH_CHECKS sequentially, streaming
    output and appending one record per check to bench/health_runs.jsonl."""

    def __init__(self, names):
        self.names = names
        self.lines = []
        self.status = "running"
        self.current = None
        threading.Thread(target=self._work, daemon=True).start()

    def _work(self):
        by_name = {n: (label, argv) for n, label, argv in HEALTH_CHECKS}
        ok = True
        for name in self.names:
            label, argv = by_name[name]
            self.current = name
            self.lines.append(f"==> {name}: {' '.join(argv)}\n")
            started = time.time()
            digest = None
            try:
                proc = subprocess.Popen(argv, cwd=ROOT,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True)
                timer = threading.Timer(HEALTH_TIMEOUT_S, proc.terminate)
                timer.start()
                for line in proc.stdout:
                    self.lines.append(line)
                    m = re.search(r"parity digest: ([0-9a-f]{64})", line)
                    if m:
                        digest = m.group(1)
                proc.wait()
                timer.cancel()
                rc = proc.returncode
            except Exception as exc:
                self.lines.append(f"launcher error: {exc}\n")
                rc = -1
            record = {"check": name, "status": "passed" if rc == 0 else "failed",
                      "returncode": rc,
                      "seconds": round(time.time() - started, 1),
                      "started": round(started, 2),
                      "ended": round(time.time(), 2),
                      "commit": git_state()["head"],
                      "dirty": git_state()["dirty"]}
            if digest:
                record["digest"] = digest
            os.makedirs(os.path.join(ROOT, "bench"), exist_ok=True)
            with open(os.path.join(ROOT, "bench", "health_runs.jsonl"),
                      "a") as fh:
                fh.write(json.dumps(record) + "\n")
            ok = ok and rc == 0
            self.lines.append(f"<== {name}: "
                              f"{'PASS' if rc == 0 else 'FAIL'}\n\n")
        self.status = "passed" if ok else "failed"
        self.current = None


def health_records():
    path = os.path.join(ROOT, "bench", "health_runs.jsonl")
    out = {}
    if os.path.exists(path):
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        rec = json.loads(line)
                        out[rec.get("check")] = rec
                    except json.JSONDecodeError:
                        pass
    return out


def health_data():
    recs = health_records()
    head = git_state()["head"]
    run = HEALTH["run"]
    checks = []
    for name, label, _argv in HEALTH_CHECKS:
        last = recs.get(name)
        stale = bool(last) and (last.get("commit") != head or
                                last.get("dirty"))
        checks.append({"name": name, "label": label, "last": last,
                       "stale": stale,
                       "running": bool(run and run.status == "running" and
                                       run.current == name)})
    pm, ps = recs.get("parity-migrated"), recs.get("parity-source")
    if pm and ps and pm.get("digest") and ps.get("digest"):
        parity = {"migrated": pm["digest"], "source": ps["digest"],
                  "match": pm["digest"] == ps["digest"]}
    else:
        parity = {"migrated": pm.get("digest") if pm else None,
                  "source": ps.get("digest") if ps else None,
                  "match": None}
    return {"checks": checks,
            "running": run.current if run and run.status == "running" else None,
            "parity": parity}

# ---------------------------------------------------------------- rendering

CSS = """
:root { --bg:#ffffff; --fg:#1a1d21; --muted:#5c6570; --line:#d8dde3;
        --card:#f4f6f8; --accent:#0b6e6e; --ok:#1a7f37; --bad:#b42318;
        --warn:#9a6700; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#14171a; --fg:#e6e9ec; --muted:#9aa4ae; --line:#31383f;
          --card:#1d2226; --accent:#4cc4c4; --ok:#4ade80; --bad:#f87171;
          --warn:#fbbf24; } }
* { box-sizing: border-box; }
body { margin:0; font:15px/1.55 system-ui, sans-serif; background:var(--bg);
       color:var(--fg); }
nav { display:flex; flex-wrap:wrap; gap:.25rem; padding:.6rem 1rem;
      border-bottom:1px solid var(--line); position:sticky; top:0;
      background:var(--bg); z-index:5; }
nav a { text-decoration:none; color:var(--muted); padding:.25rem .7rem;
        border-radius:6px; }
nav a.active, nav a:hover { color:var(--fg); background:var(--card); }
nav .spacer { flex:1; }
main { max-width:76rem; margin:0 auto; padding:1.2rem 1rem 3rem; }
h1 { font-size:1.35rem; } h2 { font-size:1.1rem; margin-top:1.6rem; }
.card { background:var(--card); border:1px solid var(--line);
        border-radius:8px; padding:.9rem 1rem; margin:.7rem 0; }
table { border-collapse:collapse; width:100%; }
.wrap { overflow-x:auto; }
th, td { text-align:left; padding:.4rem .6rem;
         border-bottom:1px solid var(--line); vertical-align:top; }
th { color:var(--muted); font-weight:600; }
code, pre { font:13px/1.5 ui-monospace, monospace; }
pre { background:var(--card); border:1px solid var(--line); border-radius:8px;
      padding:.8rem 1rem; overflow-x:auto; }
a { color:var(--accent); }
.badge { display:inline-block; padding:.05rem .5rem; border-radius:99px;
         font-size:.78rem; border:1px solid var(--line); color:var(--muted); }
.badge.ok { color:var(--ok); border-color:var(--ok); }
.badge.bad { color:var(--bad); border-color:var(--bad); }
.badge.warn { color:var(--warn); border-color:var(--warn); }
.chip { display:inline-block; margin:.1rem .15rem 0 0; padding:.02rem .45rem;
        border:1px solid var(--line); border-radius:99px; font-size:.75rem;
        text-decoration:none; color:var(--muted); }
.chip:hover { border-color:var(--accent); color:var(--accent); }
.stage { border:1px solid var(--line); border-left:4px solid var(--accent);
         border-radius:8px; padding:.6rem .9rem; margin:.45rem 0;
         cursor:pointer; background:var(--card); }
.stage:hover { border-color:var(--accent); }
.stage .kind { float:right; }
.arrow { text-align:center; color:var(--muted); margin:-.1rem 0; }
#detail { position:sticky; top:3.2rem; }
.grid2 { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr);
         gap:1rem; }
@media (max-width:60rem) { .grid2 { grid-template-columns:1fr; } }
.note { border-left:4px solid var(--warn); padding:.5rem .8rem;
        background:var(--card); border-radius:0 8px 8px 0; margin:.7rem 0; }
.banner-dirty { border-left:4px solid var(--bad); background:var(--card);
                padding:.5rem 1rem; margin:0; font-size:.9rem; }
button { font:inherit; padding:.3rem .8rem; border-radius:6px;
         border:1px solid var(--line); background:var(--card);
         color:var(--fg); cursor:pointer; }
button:hover { border-color:var(--accent); }
.dot { font-size:1rem; }
.grid-source { display:grid;
               grid-template-columns:17rem minmax(0,1fr) 24rem; gap:1rem; }
@media (max-width:75rem) { .grid-source { grid-template-columns:1fr; } }
#symlist { max-height:75vh; overflow-y:auto; font-size:.86rem; }
#symlist details { margin:.2rem 0; }
#symlist summary { color:var(--muted); cursor:pointer; }
.symlink { display:block; padding:.06rem .3rem; text-decoration:none;
           font-family:ui-monospace, monospace; font-size:.8rem;
           color:var(--fg); border-radius:4px; }
.symlink:hover { background:var(--card); color:var(--accent); }
#egograph { min-height:26rem; border:1px solid var(--line);
            border-radius:8px; background:var(--card); }
#inspector { position:sticky; top:3.2rem; max-height:85vh; overflow-y:auto; }
#symsearch { width:100%; padding:.35rem .6rem; margin-bottom:.4rem;
             border:1px solid var(--line); border-radius:6px;
             background:var(--bg); color:var(--fg); font:inherit; }
.source-mode-tabs { display:flex; flex-wrap:wrap; gap:.35rem; margin:.5rem 0; }
.source-mode { border:1px solid var(--line); border-radius:7px;
               padding:.35rem .75rem; text-decoration:none; color:var(--muted); }
.source-mode.active, .source-mode:hover { color:var(--fg);
                                          border-color:var(--accent);
                                          background:var(--card); }
#source-context:empty { display:none; }
"""


def shell(title, active, body):
    parts = []
    for href, label in NAV:
        cls = ' class="active"' if href == active else ""
        parts.append(f'<a href="{href}"{cls}>{label}</a>')
    parts.append('<span class="spacer"></span>')
    parts.append('<a href="#" id="palette-open" title="Ctrl-K">⌘K</a>')
    nav = "".join(parts)
    gs = git_state()
    banner = ""
    if gs["dirty"]:
        banner = (f'<div class="banner-dirty"><b>UNCOMMITTED PACKAGE STATE'
                  f"</b> — Results describe working-tree code, not commit "
                  f"<code>{esc(gs['head'])}</code>. "
                  f"{len(gs['modified'])} tracked files modified · "
                  f"{len(gs['untracked'])} untracked package files</div>")
    return (f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(title)} · JUNA-Lite explorer</title>"
            f"<style>{CSS}</style></head><body>"
            f"<nav>{nav}</nav>{banner}<main>{body}</main>"
            f'<script type="module" src="/static/palette.js"></script>'
            f"</body></html>")


def esc(s):
    return html.escape(str(s), quote=True)


def status_badge(rec):
    if not rec:
        return '<span class="badge">not run</span>'
    cls = {"passed": "ok", "failed": "bad", "cancelled": "warn",
           "running": "warn"}.get(rec.get("status"), "")
    return f'<span class="badge {cls}">{esc(rec.get("status"))}</span>'


def stale_banner():
    if suites_stale():
        return ('<div class="note">suites.json is older than test/runtests.jl '
                '- regenerate with <code>julia tools/explorer/export_suites.jl'
                '</code> (the contract fails until then).</div>')
    return ""


def suite_stage_chips(key):
    chain = CHAIN_CACHE.get()
    chips = "".join(
        f'<a class="chip" data-stage="{esc(st["id"])}" '
        f'href="/chain#{esc(st["id"])}">{esc(st["title"])}</a>'
        for st in chain["stages"] if key in st["suites"])
    return chips


def page_home():
    suites = SUITES_CACHE.get()
    chain = CHAIN_CACHE.get()
    last = last_run_by_key()
    lite = next(r for r in RECEIVERS_CACHE.get() if r["id"] == "lite")
    by_stage = {st["id"]: st for st in chain["stages"]}
    strip = " → ".join(
        f'<a href="/chain#{esc(st["id"])}">{esc(st["title"])}</a>'
        for st in (by_stage[stage_id] for stage_id in lite["chain_path"]))
    rows = "".join(
        f"<tr><td><a href='/run/{esc(r['key'])}'>{esc(r['key'])}</a></td>"
        f"<td>{status_badge(r)}</td>"
        f"<td>{time.strftime('%H:%M:%S', time.localtime(r['ended']))}</td></tr>"
        for r in run_history()[-5:][::-1])
    hd = health_data()
    hbad = [c["name"] for c in hd["checks"]
            if c["last"] and c["last"].get("status") == "failed"]
    hsum = (f'<span class="badge bad">{len(hbad)} failing</span>' if hbad else
            '<span class="badge ok">no recorded failures</span>')
    body = f"""
<h1>JUNA-Lite explorer</h1>
<div class="card">Standalone home of the JUNA-Lite receiver, migrated from
sonique <code>research/JunaCore @ {SOURCE_SHA}</code>. Three public facades:
Standard OFDM, Partial-FFT, JUNA-Lite. HEAD:
<code>{esc(git_state()['head'])} {esc(git_state()['subject'])}</code><br>
Explore source:
<a href="/source/graph?receiver=standard">Standard</a> ·
<a href="/source/graph?receiver=partial-fft">Partial-FFT</a> ·
<a href="/source/graph?receiver=lite">JUNA-Lite</a></div>
{stale_banner()}
<h2>Receiver chain</h2>
<div class="card">{strip}</div>
<div class="grid2">
<div><h2>Test surface</h2><div class="card">{len(suites)} suites in the
<a href="/tests">registry</a> · {len(last)} with recorded runs ·
static <a href="/coverage">reference coverage</a> ·
<a href="/health">health</a> {hsum}</div></div>
<div><h2>Recent runs</h2><div class="wrap"><table>
<tr><th>suite</th><th>status</th><th>ended</th></tr>{rows or
'<tr><td colspan="3">none recorded yet</td></tr>'}</table></div></div>
</div>
<h2>Verification</h2>
<div class="card"><code>julia --project=. -e 'using Pkg; Pkg.test()'</code>
 · parity vs source repo: <code>julia --project=. tools/parity_check.jl</code>
 · contracts: <a href="/health">run from the Health page</a></div>"""
    return shell("Home", "/", body)


def page_tests():
    suites = SUITES_CACHE.get()
    last = last_run_by_key()
    rows = ""
    for s in suites:
        rec = last.get(s["key"])
        chips = suite_stage_chips(s["key"])
        chips_html = (f"<br>{chips}" if chips else "")
        rows += (f'<tr id="{esc(s["key"])}"><td><code>{esc(s["key"])}</code>'
                 f'</td>'
                 f'<td><b>{esc(s["title"])}</b><br>'
                 f'<span style="color:var(--muted)">{esc(s["claim"])}</span>'
                 f'<br><span class="badge">{esc(s["provenance"])}</span>'
                 f'{chips_html}</td>'
                 f'<td><code>{esc(s["file"])}</code><br>'
                 f'<a href="/source/graph?suite={esc(s["key"])}">'
                 f"source graph</a></td>"
                 f'<td>{status_badge(rec)}</td>'
                 f'<td><a href="/run/{esc(s["key"])}"><button>run</button>'
                 f'</a></td></tr>')
    body = f"""
<h1>Test suites</h1>
<div class="card">Generated from the authoritative registry in
<code>test/runtests.jl</code> via <code>suites.json</code>. Stage chips are
the reverse traversal of <code>chain.json</code>: they mark which receiver
stages each suite protects.</div>
{stale_banner()}
<div class="wrap"><table>
<tr><th>key</th><th>title / claim / protected stages</th><th>file</th>
<th>last run</th><th></th></tr>
{rows}</table></div>"""
    return shell("Tests", "/tests", body)


def page_map():
    analyzed = ANALYZE_CACHE.get()
    suites = SUITES_CACHE.get()
    per_file = {}
    for s in analyzed["symbols"]:
        per_file[s["file"]] = per_file.get(s["file"], 0) + 1
    src_rows = "".join(
        f'<tr><td><a href="/source/graph?file='
        f'{urllib.parse.quote(f)}"><code>src/{esc(f)}</code></a></td>'
        f"<td>{n} symbols</td></tr>"
        for f, n in sorted(per_file.items()))
    body = f"""
<h1>Repository map</h1>
<div class="card">The migrated package's real structure - no source-repo
areas are mapped here because they are not part of this repository.</div>
<h2>src/ <span class="badge">loaded by JunaCore.jl</span></h2>
<div class="wrap"><table>{src_rows}</table></div>
<h2>test/ <span class="badge">verified by Pkg.test</span></h2>
<div class="card">{len(suites)} suites - see <a href="/tests">Tests</a>;
shared fixtures in <code>test/support/</code>; registry in
<code>test/runtests.jl</code>.</div>
<h2>tools/ <span class="badge">analyzed by</span></h2>
<div class="card"><code>tools/ldpc</code>: LDPC helper binaries (runtime
requirement of LDPC.jl - see THIRD_PARTY_NOTICES.md) ·
<code>tools/explorer</code>: this server, analyzer, coverage scanner,
contracts · <code>tools/parity_check.jl</code>: cross-repo parity gate.</div>
<h2>bench/ <span class="badge">run history</span></h2>
<div class="card"><code>bench/test_runs.jsonl</code> and
<code>bench/health_runs.jsonl</code>: appended by browser-triggered runs
(gitignored).</div>"""
    return shell("Map", "/map", body)


def page_chain():
    chain = CHAIN_CACHE.get()
    receivers = RECEIVERS_CACHE.get()
    optional = {r["id"]: r.get("optional_stages", [])
                for r in chain["receivers"]}
    payload = json.dumps({"stages": chain["stages"],
                          "receivers": receivers,
                          "edges": chain["edges"],
                          "optionalStages": optional}).replace("</", "<\\/")
    options = "".join(
        f'<option value="{esc(r["id"])}"'
        f'{" selected" if r["id"] == "lite" else ""}>'
        f'{esc(r["display_name"])}</option>' for r in receivers)
    compare_options = ('<option value="">None</option>' + "".join(
        f'<option value="{esc(r["id"])}">{esc(r["display_name"])}</option>'
        for r in receivers))
    conditions = "".join(
        f'<li><code>{esc(edge["from"])}</code> → '
        f'<code>{esc(edge["to"])}</code>: {esc(edge["condition"])}</li>'
        for edge in chain["edges"] if edge.get("condition"))
    body = f"""
<h1>Receiver chains</h1>
<div class="card">The two baselines and JUNA-Lite are views over one shared,
contract-verified stage DAG. A baseline is a complete comparison receiver,
not an incomplete implementation. Lite extends its Partial-FFT seed only
when that seed is invalid.</div>
<div class="card"><label>Receiver:
<select id="receiver-select">{options}</select></label>
&nbsp; <label>Compare with:
<select id="compare-select">{compare_options}</select></label>
<div id="receiver-purpose" style="margin-top:.7rem"></div></div>
<div class="grid2"><div id="chain-boxes"></div>
<div id="detail"><div class="card">Click a stage for its symbols, suites,
and evidence.</div></div></div>
<h2>Conditional execution</h2>
<div class="card"><ul>{conditions}</ul></div>
<script>
var MODEL = {payload};
var STAGES = MODEL.stages;
function receiver(id) {{
  return MODEL.receivers.find(function(r) {{ return r.id === id; }});
}}
function renderChain() {{
  var selected = receiver(document.getElementById('receiver-select').value);
  var compared = receiver(document.getElementById('compare-select').value);
  var comparedPath = compared ? compared.chain_path : [];
  document.getElementById('receiver-purpose').innerHTML =
    '<b>' + selected.display_name + '</b> · <code>' + selected.facade +
    '</code> · ' + selected.purpose;
  document.getElementById('chain-boxes').innerHTML =
    selected.chain_path.map(function(id, index) {{
      var st = STAGES.find(function(s) {{ return s.id === id; }});
      var shared = comparedPath.indexOf(id) >= 0;
      var marker = compared ? (shared ? 'shared' : 'selected only') : st.kind;
      return (index ? '<div class="arrow">↓</div>' : '') +
        '<div class="stage" id="' + st.id + '" data-stage="' + st.id + '">' +
        '<span class="badge kind">' + marker + '</span><b>' + st.title +
        '</b><br><span style="color:var(--muted)">' +
        st.symbols.slice(0, 3).join(', ') +
        (st.symbols.length > 3 ? '…' : '') + '</span></div>';
    }}).join('') +
    (MODEL.optionalStages[selected.id] || []).map(function(id) {{
      var st = STAGES.find(function(s) {{ return s.id === id; }});
      return '<div class="arrow">optional deployment wrapper</div>' +
        '<div class="stage" id="' + st.id + '" data-stage="' + st.id + '">' +
        '<span class="badge kind">optional</span><b>' + st.title +
        '</b><br><span style="color:var(--muted)">' +
        st.symbols.slice(0, 3).join(', ') + '</span></div>';
    }}).join('');
  document.querySelectorAll('#chain-boxes .stage').forEach(function(node) {{
    node.addEventListener('click', function() {{ show(node.dataset.stage); }});
  }});
  var url = new URL(location.href);
  url.searchParams.set('receiver', selected.id);
  if (compared) url.searchParams.set('compare', compared.id);
  else url.searchParams.delete('compare');
  history.replaceState(null, '', url.pathname + url.search + location.hash);
}}
function show(id) {{
  var st = STAGES.find(function(s) {{ return s.id === id; }});
  if (!st) return;
  var evCls = st.evidence === "direct" ? "ok" : "warn";
  var syms = st.symbols.map(function(s) {{
    return '<a href="/source/graph?stage=' + encodeURIComponent(st.id) +
           '#sym=' + encodeURIComponent(s) + '"><code>' +
           s + '</code></a>'; }}).join(" · ");
  var suites = st.suites.map(function(k) {{
    return '<a href="/tests#' + k + '">' + k + '</a> (<a href="/run/' + k +
           '">run</a>)'; }}).join(" · ");
  document.getElementById('detail').innerHTML =
    '<div class="card"><span class="badge">' + st.kind + '</span> ' +
    '<span class="badge ' + evCls + '">evidence: ' + st.evidence + '</span>' +
    '<h2>' + st.title + '</h2><p>' + st.detail + '</p>' +
    '<p><b>Symbols</b><br>' + syms + '</p>' +
    '<p><b>Protecting suites</b><br>' + suites + '</p>' +
    (st.evidence === 'behavioral' ?
      '<p class="note">behavioral evidence: the declared suites exercise ' +
      'this stage through the public API without naming its internals - ' +
      'see the <a href="/coverage">coverage legend</a>.</p>' : '') +
    '</div>';
  if (history.replaceState) {{
    var url = new URL(location.href);
    url.hash = id;
    history.replaceState(null, '', url.pathname + url.search + url.hash);
  }}
}}
var params = new URLSearchParams(location.search);
if (receiver(params.get('receiver'))) {{
  document.getElementById('receiver-select').value = params.get('receiver');
}}
if (receiver(params.get('compare'))) {{
  document.getElementById('compare-select').value = params.get('compare');
}}
document.getElementById('receiver-select').addEventListener('change', renderChain);
document.getElementById('compare-select').addEventListener('change', renderChain);
renderChain();
if (location.hash) show(location.hash.slice(1));
</script>"""
    return shell("Chain", "/chain", body)


def page_source(mode="inspector"):
    data = ANALYZE_CACHE.get()
    per_file = {}
    for s in data["symbols"]:
        if s["kind"] == "module":
            continue
        per_file.setdefault(s["file"], []).append(s)
    groups = ""
    for f in sorted(per_file):
        entries = "".join(
            f'<a class="symlink" data-id="{s["id"]}" '
            f'data-name="{esc(s["name"])}" '
            f'href="#sym={urllib.parse.quote(s["name"])}">{esc(s["name"])}'
            f"</a>"
            for s in sorted(per_file[f], key=lambda s: (s["name"], s["line"])))
        groups += (f'<details class="symgroup" open><summary>{esc(f)} '
                   f"({len(per_file[f])})</summary>{entries}</details>")
    legend = "".join(
        f"<li><b>{esc(term)}</b>: {esc(meaning)}</li>"
        for term, meaning in TAXONOMY)
    inspector_active = " active" if mode == "inspector" else ""
    graph_active = " active" if mode == "graph" else ""
    body = f"""
<h1>Source</h1>
<div class="source-mode-tabs">
<a class="source-mode{inspector_active}" href="/source">Evidence Inspector</a>
<a class="source-mode{graph_active}" href="/source/graph">Advanced Graph</a>
<a class="source-mode" href="/source-advanced">Original Analyzer</a>
</div>
<div class="card">One analyzer, two Explorer views. Inspector connects a
selected symbol to chain meaning and evidence. Advanced Graph accepts
receiver, stage, suite, file, and symbol context while preserving the same
inspector. Static graph edges never claim runtime execution.</div>
<div id="source-context" class="card"></div>
<div class="grid-source" data-source-mode="{esc(mode)}">
<div><input id="symsearch" placeholder="filter symbols…" autocomplete="off">
<div id="symlist">{groups}</div></div>
<div id="egograph"></div>
<div id="inspector"><div class="card">
<p>Select a symbol to inspect it. Evidence taxonomy used here:</p>
<ul>{legend}</ul>
<p class="note">{esc(TAXONOMY_NOTE)}</p>
</div></div>
</div>
<script src="/static/vendor/vis-network.min.js"></script>
<script type="module" src="/static/source.js"></script>"""
    return shell("Source", "/source", body)


def page_source_legacy():
    analyzed = ANALYZE_CACHE.get()
    page = source_symbols.render_html(False, analyzed,
                                      os.path.join(ROOT, "src"), locked=True)
    bridge_css = """
<style>
#explorer-source-bridge{position:fixed;left:0;right:0;bottom:0;z-index:99999;
display:flex;align-items:center;gap:8px;padding:8px 14px;background:#0b1220;
border-top:1px solid #334155;color:#cbd5e1;font:13px system-ui,sans-serif}
#explorer-source-bridge a{color:#7dd3fc;text-decoration:none;padding:3px 7px}
#explorer-source-bridge a:hover{background:#1e293b;border-radius:5px}
#explorer-source-bridge .spacer{flex:1}
body{padding-bottom:46px!important}
</style>"""
    bridge = """
<div id="explorer-source-bridge" aria-label="Explorer source bridge">
<b>Explorer source bridge</b>
<a href="/source">Evidence Inspector</a>
<a href="/source/graph">Advanced Graph</a>
<span class="spacer"></span>
<a href="/chain">Chain</a><a href="/tests">Tests</a>
<a href="/coverage">Coverage</a>
</div>"""
    if "</head>" in page:
        page = page.replace("</head>", bridge_css + "</head>", 1)
    if "<body" in page:
        body_end = page.find(">", page.find("<body"))
        page = page[:body_end + 1] + bridge + page[body_end + 1:]
    return page


def page_coverage():
    chain = CHAIN_CACHE.get()
    suites = SUITES_CACHE.get()
    report = COVERAGE_CACHE.get()
    last = last_run_by_key()
    keys = [s["key"] for s in suites]
    head = "".join(
        f"<th><a href='/tests#{esc(k)}'>{esc(k)}</a><br>"
        f"{status_badge(last.get(k))}</th>" for k in keys)
    rows = ""
    for st in chain["stages"]:
        cells = ""
        for k in keys:
            direct = report["suites"].get(k, {}).get("direct", {})
            has_direct = any(sym in direct for sym in st["symbols"])
            declared = k in st["suites"]
            if has_direct:
                cell = '<span class="dot" title="direct textual reference">●</span>'
            elif declared:
                cell = ('<span class="dot" title="declared association '
                        '(behavioral evidence, no textual reference)">◐</span>')
            else:
                cell = '<span style="color:var(--muted)">·</span>'
            cells += f"<td>{cell}</td>"
        rows += (f'<tr><td><a href="/chain#{esc(st["id"])}">{esc(st["title"])}'
                 f'</a><br><a href="/source/graph?stage={esc(st["id"])}">'
                 f"source graph</a></td>{cells}</tr>")
    unresolved = report["unresolved"]
    unresolved_rows = "".join(
        f"<tr><td>{esc(u['suite'])}</td><td>{esc(u.get('line', ''))}</td>"
        f"<td><code>{esc(u['name'])}</code></td>"
        f"<td>{esc(u.get('reason', 'qualified name absent from analyzer table'))}"
        f"</td></tr>" for u in unresolved[:50])
    drill = ""
    for k in keys:
        entry = report["suites"].get(k, {})
        direct = entry.get("direct", {})
        if not direct:
            continue
        items = "".join(
            f"<tr><td><a href='/source/graph?suite={esc(k)}"
            f"&symbol={urllib.parse.quote(n)}#sym={urllib.parse.quote(n)}'>"
            f"<code>{esc(n)}</code></a>"
            f"</td><td>{esc(', '.join(map(str, lines[:12])))}"
            f"{'…' if len(lines) > 12 else ''}</td></tr>"
            for n, lines in direct.items())
        drill += (f"<details><summary><code>{esc(k)}</code> - "
                  f"{len(direct)} directly referenced symbols</summary>"
                  f"<div class='wrap'><table><tr><th>symbol</th>"
                  f"<th>lines in {esc(entry.get('file', ''))}</th></tr>"
                  f"{items}</table></div></details>")
    body = f"""
<h1>Source-to-test coverage</h1>
<div class="note"><b>Static references, not runtime coverage.</b>
{esc(report['note'])} Run-status chips answer the separate question of
whether the suite last passed.</div>
<h2>Chain stage × suite</h2>
<div class="wrap"><table><tr><th>stage</th>{head}</tr>{rows}</table></div>
<div class="card">● direct textual reference to a stage symbol ·
◐ declared association with behavioral evidence only ·
chip = most recent recorded browser run (suites also run in Pkg.test,
which is not recorded here).</div>
<h2>Direct references by suite</h2>{drill or '<div class="card">none</div>'}
<h2>Unresolved qualified references ({len(unresolved)})</h2>
<div class="wrap"><table><tr><th>suite</th><th>line</th><th>reference</th>
<th>reason</th></tr>{unresolved_rows or
'<tr><td colspan="4">none - every qualified reference resolves</td></tr>'}
</table></div>"""
    return shell("Coverage", "/coverage", body)


def page_health():
    rows = ""
    for name, label, argv in HEALTH_CHECKS:
        rows += (f'<tr data-check="{esc(name)}"><td><b>{esc(label)}</b><br>'
                 f'<code style="font-size:.75rem">{esc(" ".join(argv))}'
                 f"</code></td>"
                 f'<td class="h-status"><span class="badge">—</span></td>'
                 f'<td class="h-commit">—</td>'
                 f'<td class="h-seconds">—</td>'
                 f'<td class="h-ended">—</td>'
                 f'<td><button class="h-run" data-check="{esc(name)}">run'
                 f"</button></td></tr>")
    body = f"""
<h1>Health</h1>
<div class="card">Fixed command allowlist - nothing here executes arbitrary
input. One run at a time; each check appends a record (with commit and
dirty-state) to <code>bench/health_runs.jsonl</code>, kept separate from
browser test runs. STALE means the last result predates the current commit
or was recorded on a dirty tree.
<button id="health-run-all">run health battery</button>
<span style="color:var(--muted)">(battery = provenance-pins, explorer-data,
server-behavior, package-load; the long checks run individually)</span></div>
<div class="wrap"><table>
<tr><th>check</th><th>status</th><th>commit</th><th>run time</th>
<th>ended</th><th></th></tr>
{rows}</table></div>
<div id="health-parity" class="card">Cross-repository parity: run both
parity checks to compare digests. Inspect the
<a href="/source/graph?file=juna%2Fcommon.jl">shared receiver substrate</a>.
</div>
<pre id="health-log">(no health run this session)</pre>
<script type="module" src="/static/health.js"></script>"""
    return shell("Health", "/health", body)


def page_progress():
    path = os.path.join(ROOT, ".migration_progress.log")
    try:
        with open(path) as fh:
            tail = "".join(fh.readlines()[-100:])
    except FileNotFoundError:
        tail = "(no migration log present)"
    body = f"""
<h1>Live progress log</h1>
<div class="card">Tail of <code>.migration_progress.log</code>; the page
refreshes every 5 s. Terminal equivalent:
<code>tail -f .migration_progress.log</code> ·
<a href="/source/graph?receiver=lite">open the Lite source context</a></div>
<pre>{esc(tail)}</pre>
<script>setTimeout(function() {{ location.reload(); }}, 5000);</script>"""
    return shell("Progress", "/progress", body)


def page_run(key):
    suites = {s["key"]: s for s in SUITES_CACHE.get()}
    if key not in suites:
        return None
    s = suites[key]
    body = f"""
<h1>Run: {esc(s['title'])}</h1>
<div class="card"><code>julia --project=. test/{esc(s['file'])}</code>
<span id="status" class="badge warn">idle</span>
<button onclick="start()">start</button>
<button onclick="cancel()">cancel</button>
<a href="/tests#{esc(key)}">back to tests</a></div>
<pre id="out">(not started)</pre>
<script>
var KEY = {json.dumps(key)}, seen = 0, timer = null;
function poll() {{
  fetch('/run/' + KEY + '/output?from=' + seen).then(function(r) {{
    return r.json(); }}).then(function(d) {{
    if (d.text) {{
      var pre = document.getElementById('out');
      if (seen === 0) pre.textContent = '';
      pre.textContent += d.text; seen = d.seen;
      pre.scrollTop = pre.scrollHeight;
    }}
    document.getElementById('status').textContent = d.status;
    document.getElementById('status').className = 'badge ' +
      (d.status === 'passed' ? 'ok' : d.status === 'failed' ? 'bad' : 'warn');
    if (d.status === 'running') timer = setTimeout(poll, 700);
  }});
}}
function start() {{
  fetch('/run/' + KEY + '/start', {{method: 'POST'}}).then(function() {{
    seen = 0; poll(); }});
}}
function cancel() {{
  fetch('/run/' + KEY + '/cancel', {{method: 'POST'}});
}}
poll();
</script>"""
    return shell(f"Run {key}", "/tests", body)

# ---------------------------------------------------------------- handler

STATIC_FILES = {"palette.js", "source.js", "health.js"}


class Handler(BaseHTTPRequestHandler):
    def _send(self, text, code=200, ctype="text/html; charset=utf-8"):
        data = text.encode() if isinstance(text, str) else text
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass

    def _api(self, path, query):
        if path == "/api/repository":
            gs = git_state()
            return envelope({"root": ROOT, "package": "JunaCore",
                             "head": gs["head"], "subject": gs["subject"],
                             "dirty": gs["dirty"],
                             "modified": gs["modified"],
                             "untracked": gs["untracked"],
                             "suites_json_stale": suites_stale()})
        if path == "/api/suites":
            last = last_run_by_key()
            return envelope([dict(s, last_run=last.get(s["key"]))
                             for s in SUITES_CACHE.get()])
        if path == "/api/chain":
            return envelope(CHAIN_CACHE.get())
        if path == "/api/receivers":
            return envelope(RECEIVERS_CACHE.get())
        if path == "/api/graph":
            return envelope(graph_data(query))
        if path == "/api/symbols":
            return envelope([{k: s[k] for k in
                              ("id", "name", "kind", "module", "file", "line")}
                             for s in ANALYZE_CACHE.get()["symbols"]])
        if path == "/api/coverage":
            return envelope(COVERAGE_CACHE.get())
        if path == "/api/runs":
            return envelope(run_history())
        if path == "/api/health":
            return envelope(health_data())
        if path == "/api/palette":
            return envelope(palette_index())
        if path == "/api/health/output":
            frm = 0
            qm = re.search(r"from=(\d+)", query or "")
            if qm:
                frm = int(qm.group(1))
            run = HEALTH["run"]
            if run is None:
                return json.dumps({"text": "", "seen": 0, "status": "idle"})
            lines = run.lines[frm:]
            return json.dumps({"text": "".join(lines),
                               "seen": frm + len(lines),
                               "status": run.status,
                               "check": run.current})
        m = re.fullmatch(r"/api/symbol/(.+)", path)
        if m:
            token = urllib.parse.unquote(m.group(1))
            sym = _symbol_lookup(token)
            if sym is None:
                return None
            return envelope(symbol_detail(sym))
        return None

    def do_GET(self):
        path, _, query = self.path.partition("?")
        try:
            if path.startswith("/static/vendor/"):
                name = os.path.basename(path)
                full = os.path.join(HERE, "vendor", name)
                if name == "vis-network.min.js" and os.path.isfile(full):
                    with open(full, "rb") as fh:
                        return self._send(fh.read(),
                                          ctype="application/javascript")
                return self._send("not found", 404, "text/plain")
            if path.startswith("/static/"):
                name = os.path.basename(path)
                full = os.path.join(HERE, "static", name)
                if name in STATIC_FILES and os.path.isfile(full):
                    with open(full, "rb") as fh:
                        return self._send(fh.read(),
                                          ctype="application/javascript")
                return self._send("not found", 404, "text/plain")
            if path.startswith("/api/"):
                out = self._api(path, query)
                if out is None:
                    return self._send('{"error": "not found"}', 404,
                                      "application/json")
                return self._send(out, ctype="application/json")
            if path == "/":
                return self._send(page_home())
            if path == "/tests":
                return self._send(page_tests())
            if path == "/map":
                return self._send(page_map())
            if path == "/chain":
                return self._send(page_chain())
            if path == "/source":
                return self._send(page_source())
            if path == "/source/graph":
                return self._send(page_source("graph"))
            if path in ("/source-advanced", "/source-legacy"):
                return self._send(page_source_legacy())
            if path == "/coverage":
                return self._send(page_coverage())
            if path == "/health":
                return self._send(page_health())
            if path == "/progress":
                return self._send(page_progress())
            if path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return
            m = re.fullmatch(r"/run/([a-z0-9-]+)", path)
            if m:
                page = page_run(m.group(1))
                if page is None:
                    return self._send(shell("404", "",
                                            "<h1>unknown suite</h1>"), 404)
                return self._send(page)
            m = re.fullmatch(r"/run/([a-z0-9-]+)/output", path)
            if m:
                frm = 0
                qm = re.search(r"from=(\d+)", query)
                if qm:
                    frm = int(qm.group(1))
                with RUNS_LOCK:
                    run = RUNS.get(m.group(1))
                if run is None:
                    return self._send(json.dumps(
                        {"text": "", "seen": 0, "status": "idle"}),
                        ctype="application/json")
                lines = run.lines[frm:]
                return self._send(json.dumps(
                    {"text": "".join(lines), "seen": frm + len(lines),
                     "status": run.status}), ctype="application/json")
            return self._send(shell("404", "", "<h1>404</h1><p>No such page. "
                                    "This explorer has no benchmark, history, "
                                    "or reproduce pages.</p>"), 404)
        except BrokenPipeError:
            pass
        except Exception as exc:  # surface, don't hide
            return self._send(shell("error", "",
                                    f"<h1>server error</h1><pre>{esc(exc)}"
                                    f"</pre>"), 500)

    def do_POST(self):
        if self.path == "/api/health/run":
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length).decode() if length else "{}"
            try:
                req = json.loads(body or "{}")
            except json.JSONDecodeError:
                return self._send('{"error": "bad json"}', 400,
                                  "application/json")
            known = {n for n, _l, _a in HEALTH_CHECKS}
            if "check" in req:
                if req["check"] not in known:
                    return self._send('{"error": "unknown check"}', 400,
                                      "application/json")
                names = [req["check"]]
            else:
                names = HEALTH_BATTERY
            with HEALTH_LOCK:
                run = HEALTH["run"]
                if run is not None and run.status == "running":
                    return self._send('{"error": "a check is running"}', 409,
                                      "application/json")
                HEALTH["run"] = HealthRun(names)
            return self._send('{"started": true}', 200, "application/json")
        m = re.fullmatch(r"/run/([a-z0-9-]+)/(start|cancel)", self.path)
        if not m:
            return self._send("{}", 404, "application/json")
        key, action = m.groups()
        suites = {s["key"]: s for s in SUITES_CACHE.get()}
        if key not in suites:
            return self._send("{}", 404, "application/json")
        with RUNS_LOCK:
            run = RUNS.get(key)
            if action == "start":
                if run is None or run.status != "running":
                    RUNS[key] = Run(key, suites[key]["file"])
            elif action == "cancel" and run is not None:
                run.cancel()
        return self._send("{}", 200, "application/json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8772)
    args = ap.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"JUNA-Lite explorer: http://127.0.0.1:{args.port}/ (root {ROOT})")
    server.serve_forever()


if __name__ == "__main__":
    main()
