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
import glob
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
# JUNA_CORE_ROOT points the explorer at another checkout, so one Explorer can
# read and run a second agent's package without editing it. The variable name
# is the one test/interface_contract.jl already uses.
ROOT = os.path.normpath(os.environ.get(
    "JUNA_CORE_ROOT", os.path.join(HERE, "..", "..")))
sys.path.insert(0, HERE)

import source_coverage  # noqa: E402
import source_symbol_explorer as source_symbols  # noqa: E402

SOURCE_SHA = "d49fff0"  # sonique research/JunaCore provenance (see README.md)
SCHEMA_VERSION = 1
NAV = [("/", "Home"), ("/tests", "Tests"), ("/map", "Map"),
       ("/chain", "Chain"), ("/source", "Source"), ("/coverage", "Coverage"),
       ("/health", "Health"), ("/progress", "Progress"),
       ("/results", "Results")]
INTERFACE_METHODS = {"init", "modulate", "demodulate", "bitspersymbol",
                     "signallength", "payload_rate", "refinement_objective",
                     "frameblockcount", "framepayloadbits"}
TAXONOMY = [("Static call edge", "the analyzer found a lexical call"),
            ("Interface implementation",
             "the method extends the public Modulations contract"),
            ("Direct test reference", "the test file includes the code name"),
            ("Suite-wide association",
             "declared through a chain stage, not named directly"),
            ("Runtime result",
             "browser-recorded run outcome - separate from static evidence")]
TAXONOMY_NOTE = "Static edges and references never imply the code executed."

# ---------------------------------------------------------------- data layer


class _Cache:
    """Reload when the watched files change.

    `paths` may be a callable, which is re-evaluated on every request. A fixed
    list cannot see a file that did not exist when the server started, so any
    watch set that a new file can join must be passed as a callable.
    """

    def __init__(self, loader, paths):
        self.loader, self.paths, self.stamp, self.value = loader, paths, None, None

    def get(self):
        paths = self.paths() if callable(self.paths) else self.paths
        stamp = tuple((p, os.path.getmtime(p) if os.path.exists(p) else 0)
                      for p in paths)
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


def _coverage_files():
    return (_src_files() +
            [os.path.join(HERE, "suites.json")] +
            [os.path.join(ROOT, "test", f)
             for f in sorted(os.listdir(os.path.join(ROOT, "test")))
             if f.endswith(".jl")])


SUITES_CACHE = _Cache(_load_suites, [os.path.join(HERE, "suites.json")])
CHAIN_CACHE = _Cache(_load_chain, [os.path.join(HERE, "chain.json")])
RECEIVERS_CACHE = _Cache(_load_receivers,
                         [os.path.join(HERE, "receivers.json")])
ANALYZE_CACHE = _Cache(lambda: source_symbols.analyze(os.path.join(ROOT, "src")),
                       _src_files)
COVERAGE_CACHE = _Cache(lambda: source_coverage.scan(ROOT), _coverage_files)

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


def _comment_block(lines, start, step):
    """Contiguous '#' comment lines from `start` walking by `step`, verbatim.
    A block running back to line 1 is the file header, which describes the
    repository rather than the definition below it, so it is not a purpose."""
    block, j = [], start
    while 0 <= j < len(lines) and lines[j].lstrip().startswith("#"):
        block.append(lines[j].lstrip().lstrip("#").strip())
        j += step
    if step < 0:
        if j < 0:
            return None
        block.reverse()
    text = "\n".join(block).strip()
    return text or None


def _extract_comment(sym):
    """The author's '#' comment for a definition, or None. Verbatim source
    text; no editorial prose is ever synthesized. A comment block sits above
    the definition, except for a module, whose comment opens its body."""
    lines = _file_lines(sym["file"])
    j = sym["line"] - 2  # 0-based line above the definition
    while j >= 0 and not lines[j].strip():
        j -= 1
    above = _comment_block(lines, j, -1)
    if above or sym["kind"] != "module":
        return above
    k = sym["line"]  # 0-based first line of the module body
    while k < len(lines) and not lines[k].strip():
        k += 1
    return _comment_block(lines, k, 1)


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
    receivers = [{"id": r["id"]} for r in chain.get("receivers", [])
                 if r.get("facade") == sym["name"]]
    doc = _extract_doc(sym)
    comment = None if doc else _extract_comment(sym)
    # A facade module carries no code of its own; what it binds Modulation to
    # is the one thing that distinguishes one facade from another.
    binding = next(({"id": c["id"], "sig": c["sig"], "file": c["file"],
                     "line": c["line"]}
                    for c in _data["symbols"]
                    if c["kind"] == "const" and c["name"] == "Modulation" and
                    c["module"] == sym["name"]), None
                   ) if sym["kind"] == "module" else None

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
        "doc": doc or comment,
        "doc_origin": "docstring" if doc else ("comment" if comment else None),
        "fields": _struct_fields(sym),
        "interface_methods": type_methods,
        "facades": facades,
        "overloads": overloads, "calls": calls, "callers": callers,
        "chain_stages": stages, "chain_receivers": receivers,
        "module_binding": binding,
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
    requested_view = params.get("view", [None])[0]
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
    receiver = None
    catalog = None
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
            narrow(ids, "symbol", token,
                   f"Source definition: {sym['name']}")

    # A receiver is a conceptual stage DAG before it is a source call graph.
    # Keep that architecture visible by default and disclose implementation
    # symbols only after a stage is selected.
    stage_view = (
        receiver is not None
        and requested_view in (None, "stages")
        and not any((file_name, stage_id, suite_key, token))
    )
    if stage_view:
        stage_ids = receiver["path"] + receiver.get("optional_stages", [])
        stages = {stage["id"]: stage for stage in chain["stages"]
                  if stage["id"] in stage_ids}
        nodes = []
        for stage_id_ in stage_ids:
            stage = stages[stage_id_]
            implementation_ids = {
                sym["id"] for name in stage["symbols"]
                for sym in by_name.get(name, [])
            }
            nodes.append({
                "id": f"stage:{stage_id_}",
                "stage_id": stage_id_,
                "name": stage["title"],
                "kind": "stage",
                "stage_kind": stage["kind"],
                "detail": stage["detail"],
                "symbol_count": len(implementation_ids),
            })
        edges = [{
            "from": f"stage:{edge['from']}",
            "to": f"stage:{edge['to']}",
            "kind": "declared_stage_flow",
            "condition": edge.get("condition"),
        } for edge in chain.get("edges", [])
            if edge.get("receiver") == receiver_id
            and edge["from"] in stages and edge["to"] in stages]
        return {"context": context, "view": "stages", "nodes": nodes,
                "edges": edges, "note": TAXONOMY_NOTE}

    selected = {s["id"] for s in symbols} if chosen is None else chosen
    selected_symbols = [s for s in symbols if s["id"] in selected]

    # Multiple Julia methods with the same module/name are one visual concept.
    groups = {}
    for sym in selected_symbols:
        groups.setdefault((sym["module"], sym["name"]), []).append(sym)
    representative = {
        sym["id"]: min(group, key=lambda item: (item["line"], item["id"]))["id"]
        for group in groups.values() for sym in group
    }
    nodes = []
    for group in groups.values():
        first = min(group, key=lambda item: (item["line"], item["id"]))
        nodes.append({
            "id": first["id"], "name": first["name"], "kind": first["kind"],
            "module": first["module"], "file": first["file"],
            "line": first["line"], "overload_count": len(group),
        })

    edges = []
    seen = set()
    for s in symbols:
        if s["id"] not in selected:
            continue
        for target in s.get("calls", []):
            if target not in selected:
                continue
            edge = (representative[s["id"]], representative[target])
            if edge[0] != edge[1] and edge not in seen:
                seen.add(edge)
                edges.append({"from": edge[0], "to": edge[1],
                              "kind": "static_call"})

    view = "all" if requested_view == "all" else "symbols"
    if view == "symbols" and edges:
        connected = {endpoint for edge in edges
                     for endpoint in (edge["from"], edge["to"])}
        nodes = [node for node in nodes if node["id"] in connected]
    return {"context": context, "view": view, "nodes": nodes, "edges": edges,
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
                      "hint": (f"{m['count']} source definition" +
                               ("" if m["count"] == 1 else "s"))})
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


class SuiteBattery:
    """Runs every registered test one at a time, reusing the single-test Run so
    each one still streams to its own page and records its own
    bench/test_runs.jsonl entry. Sequential because two Julia test processes on
    one machine distort each other's timings and can exhaust memory."""

    def __init__(self, suites):
        self.queue = [(s["key"], s["file"]) for s in suites]
        self.done = []
        self.current = None
        self.status = "running"
        threading.Thread(target=self._work, daemon=True).start()

    def _work(self):
        for key, file in self.queue:
            if self.status == "cancelled":
                break
            self.current = key
            with RUNS_LOCK:
                running = RUNS.get(key)
                if running is not None and running.status == "running":
                    running.cancel()
                RUNS[key] = Run(key, file)
                run = RUNS[key]
            while run.status == "running":
                time.sleep(0.4)
            self.done.append(key)
        self.current = None
        if self.status != "cancelled":
            self.status = "finished"

    def cancel(self):
        self.status = "cancelled"
        key = self.current
        if key is None:
            return
        with RUNS_LOCK:
            run = RUNS.get(key)
        if run is not None:
            run.cancel()


BATTERY = {"run": None}
BATTERY_LOCK = threading.Lock()


def suite_run_status():
    """Per-test state for the Tests page: a live process outranks history, so a
    test that is running now reports running rather than its previous result."""
    last = last_run_by_key()
    with RUNS_LOCK:
        live = {key: run.status for key, run in RUNS.items()}
    rows = {}
    for suite in SUITES_CACHE.get():
        key = suite["key"]
        if live.get(key) == "running":
            rows[key] = {"status": "running", "seconds": None}
            continue
        rec = last.get(key)
        seconds = None
        if rec and rec.get("ended") and rec.get("started"):
            seconds = round(rec["ended"] - rec["started"], 1)
        rows[key] = {"status": rec.get("status") if rec else "not run",
                     "seconds": seconds}
    battery = BATTERY["run"]
    return {"suites": rows,
            "battery": {
                "status": battery.status if battery else "idle",
                "current": battery.current if battery else None,
                "done": len(battery.done) if battery else 0,
                "total": len(battery.queue) if battery else 0}}


# --------------------------------------------------------------- health layer

HEALTH_CHECKS = [
    ("source-file-check", "Source file check",
     ["julia", "--project=.", "test/source_file_check.jl"]),
    ("explorer-data", "Explorer data C1-C12",
     ["python3", "tools/explorer/explorer_contract.py"]),
    ("server-behavior", "Explorer server S1-S21",
     ["python3", "tools/explorer/server_contract.py"]),
    ("package-load", "Package load",
     ["julia", "--project=.", "-e", 'using JunaCore; println("load OK")']),
    ("pkg-test", "Full Pkg.test",
     ["julia", "--project=.", "-e", "using Pkg; Pkg.test()"]),
    ("fixed-results", "Fixed receiver results",
     ["julia", "--project=.", "tools/parity_check.jl"]),
]
HEALTH_BATTERY = ["source-file-check", "explorer-data", "server-behavior",
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
    fixed = recs.get("fixed-results")
    parity = {
        "digest": fixed.get("digest") if fixed else None,
        "passed": fixed.get("status") == "passed" if fixed else None,
    }
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
main.wide { max-width:none; padding-left:1.5rem; padding-right:1.5rem; }
h1 { font-size:1.35rem; } h2 { font-size:1.1rem; margin-top:1.6rem; }
.card { background:var(--card); border:1px solid var(--line);
        border-radius:8px; padding:.9rem 1rem; margin:.7rem 0; }
table { border-collapse:collapse; width:100%; }
.wrap { overflow-x:auto; }
th, td { text-align:left; padding:.4rem .6rem;
         border-bottom:1px solid var(--line); vertical-align:top; }
th { color:var(--muted); font-weight:600; }
.kinds-table { margin:.7rem 0; }
.kinds-table td:first-child { white-space:nowrap; }
th.kind-count, td.kind-count { text-align:right; width:5rem;
         font-variant-numeric:tabular-nums; }
code, pre { font:13px/1.5 ui-monospace, monospace; }
pre { background:var(--card); border:1px solid var(--line); border-radius:8px;
      padding:.8rem 1rem; overflow-x:auto; }
a { color:var(--accent); }
.badge { display:inline-block; padding:.05rem .5rem; border-radius:99px;
         font-size:.78rem; border:1px solid var(--line); color:var(--muted); }
.runall-bar { display:flex; align-items:center; gap:.75rem; flex-wrap:wrap;
              margin:0 0 .75rem; }
.runall-bar #runall-note { color:var(--muted); font-size:.9rem; }
.badge.ok { color:var(--ok); border-color:var(--ok); }
.badge.bad { color:var(--bad); border-color:var(--bad); }
.badge.warn { color:var(--warn); border-color:var(--warn); }
.chip { display:inline-block; margin:.1rem .15rem 0 0; padding:.02rem .45rem;
        border:1px solid var(--line); border-radius:99px; font-size:.75rem;
        text-decoration:none; color:var(--muted); }
.chip:hover { border-color:var(--accent); color:var(--accent); }
.suite-title { font-weight:650; }
.suite-summary { display:block; color:var(--muted); max-width:52rem; }
.suite-details { margin-top:.45rem; font-size:.9rem; }
.suite-details summary { color:var(--accent); cursor:pointer; width:max-content; }
.suite-meta { display:grid; grid-template-columns:max-content minmax(0,1fr);
              gap:.25rem .8rem; margin:.55rem 0 .1rem; }
.suite-meta dt { color:var(--muted); font-weight:600; }
.suite-meta dd { margin:0; min-width:0; }
.tests-table .suite-name { width:27%; }
.tests-table .run-status { width:11rem; min-width:11rem; }
.tests-table .run-action { width:7rem; min-width:7rem; white-space:nowrap; }
.stage { border:1px solid var(--line); border-left:4px solid var(--accent);
         border-radius:8px; padding:.6rem .9rem; margin:.45rem 0;
         cursor:pointer; background:var(--card); }
.stage:hover { border-color:var(--accent); }
.stage .kind { float:right; }
.arrow { text-align:center; color:var(--muted); margin:-.1rem 0; }
#detail { position:sticky; top:3.2rem; }
.grid2 { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr);
         gap:1rem; }
@media (max-width:60rem) {
  .grid2 { grid-template-columns:1fr; }
  .suite-meta { grid-template-columns:1fr; gap:.05rem; }
  .suite-meta dd { margin-bottom:.35rem; }
}
.note { border-left:4px solid var(--warn); padding:.5rem .8rem;
        background:var(--card); border-radius:0 8px 8px 0; margin:.7rem 0; }
.banner-dirty { border-left:4px solid var(--bad); background:var(--card);
                padding:.5rem 1rem; margin:0; font-size:.9rem; }
button, .button-link { display:inline-block; font:inherit; padding:.3rem .8rem;
                       border-radius:6px; border:1px solid var(--line);
                       background:var(--card); color:var(--fg); cursor:pointer;
                       text-decoration:none; white-space:nowrap; }
button:hover, .button-link:hover { border-color:var(--accent); }
.dot { font-size:1rem; }
.grid-source { display:grid;
               grid-template-columns:minmax(12rem,15rem) minmax(0,1fr) minmax(18rem,22rem);
               gap:1rem; align-items:start; }
@media (max-width:75rem) { .grid-source { grid-template-columns:1fr; } }
#symlist { max-height:75vh; overflow-y:auto; font-size:.86rem; }
#symlist details { margin:.2rem 0; }
#symlist summary { color:var(--muted); cursor:pointer; }
.symlink { display:block; padding:.06rem .3rem; text-decoration:none;
           font-family:ui-monospace, monospace; font-size:.8rem;
           color:var(--fg); border-radius:4px; }
.symlink:hover { background:var(--card); color:var(--accent); }
#egograph { height:32rem; min-height:26rem; border:1px solid var(--line);
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
#graph-controls { display:flex; flex-wrap:wrap; align-items:center; gap:.5rem; }
#graph-legend { display:flex; flex-wrap:wrap; gap:.35rem; margin-left:auto; }
"""


def shell(title, active, body, wide=False):
    parts = []
    for href, label in NAV:
        cls = ' class="active"' if href == active else ""
        parts.append(f'<a href="{href}"{cls}>{label}</a>')
    parts.append('<span class="spacer"></span>')
    parts.append('<a href="#" id="palette-open" title="Ctrl-K">⌘K</a>')
    nav = "".join(parts)
    main_class = ' class="wide"' if wide else ""
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
            f"<nav>{nav}</nav>{banner}<main{main_class}>{body}</main>"
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
<div class="card">Standalone home of the JUNA-Lite receiver. Its history begins
at sonique <code>research/JunaCore @ {SOURCE_SHA}</code>, but Juna is maintained
independently. Three public facades:
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
 · fixed receiver results: <code>julia --project=. tools/parity_check.jl</code>
 · contracts: <a href="/health">run from the Health page</a></div>"""
    return shell("Home", "/", body)


def page_tests():
    suites = SUITES_CACHE.get()
    last = last_run_by_key()
    rows = ""
    for s in suites:
        rec = last.get(s["key"])
        chips = suite_stage_chips(s["key"])
        steps = chips or "No receiver step is assigned to this structural test."
        details = (
            '<details class="suite-details">'
            '<summary>Technical details</summary>'
            '<dl class="suite-meta">'
            f'<dt>How it works</dt><dd>{esc(s["method"])}</dd>'
            f'<dt>Test origin</dt><dd>{esc(s["reader_origin"])}</dd>'
            f'<dt>Internal key</dt><dd><code>{esc(s["key"])}</code></dd>'
            f'<dt>Test file</dt><dd><code>{esc(s["file"])}</code></dd>'
            f'<dt>Source view</dt><dd><a href="/source/graph?'
            f'suite={esc(s["key"])}">Open source view</a></dd>'
            f'<dt>Associated receiver steps</dt><dd>{steps}</dd>'
            '</dl></details>')
        rows += (f'<tr id="{esc(s["key"])}">'
                 f'<td class="suite-name"><span class="suite-title">'
                 f'{esc(s["reader_title"])}</span></td>'
                 f'<td><span class="suite-summary">'
                 f'{esc(s["reader_summary"])}</span>{details}</td>'
                 f'<td class="run-status">{status_badge(rec)}</td>'
                 f'<td class="run-action"><a class="button-link" '
                 f'href="/run/{esc(s["key"])}">Run test</a></td></tr>')
    body = f"""
<h1>Tests</h1>
<div class="card">This page lists the tests included with JUNA-Lite. Each row
explains what the test checks and shows its most recent Explorer run. Results
on this page come only from tests started in the Explorer. Open
<b>Technical details</b> for the method, origin, internal key, test file,
source view, and associated receiver steps.</div>
{stale_banner()}
<div class="runall-bar">
  <button id="runall">Run all tests</button>
  <span id="runall-note">Tests run one at a time. Each result turns green when
  it passes, red when it fails, and orange while it is running. Closing this
  page does not stop them.</span>
</div>
<div class="wrap"><table class="tests-table">
<tr><th>Test</th><th>What it checks</th>
<th class="run-status">Most recent Explorer run</th>
<th class="run-action">Action</th></tr>
{rows}</table></div>
<script>
const RUNALL = document.getElementById('runall');
const NOTE = document.getElementById('runall-note');
const IDLE_NOTE = NOTE.textContent;
const BADGE = {{passed: 'ok', failed: 'bad', cancelled: 'warn',
                running: 'warn'}};
let polling = null;

function paint(data) {{
  for (const [key, row] of Object.entries(data.suites)) {{
    const tr = document.getElementById(key);
    if (!tr) continue;
    const cell = tr.querySelector('.run-status');
    if (!cell) continue;
    const cls = BADGE[row.status] || '';
    const secs = row.seconds ? ' ' + row.seconds + 's' : '';
    cell.innerHTML = '<span class="badge ' + cls + '">' + row.status +
      secs + '</span>';
  }}
  const b = data.battery;
  if (b.status === 'running') {{
    RUNALL.textContent = 'Stop';
    NOTE.textContent = b.done + ' of ' + b.total + ' finished' +
      (b.current ? ', now running ' + b.current : '');
  }} else {{
    RUNALL.textContent = 'Run all tests';
    NOTE.textContent = b.status === 'finished' ?
      'All ' + b.total + ' tests finished. Every result above is from this run.'
      : b.status === 'cancelled' ?
      'Stopped. Results above are from the tests that had already run.'
      : IDLE_NOTE;
  }}
  return b.status === 'running';
}}

function poll() {{
  fetch('/api/tests/status').then(r => r.json()).then(env => {{
    const busy = paint(env.data || env);
    if (!busy && polling) {{ clearInterval(polling); polling = null; }}
  }});
}}

RUNALL.addEventListener('click', () => {{
  const stopping = RUNALL.textContent === 'Stop';
  fetch(stopping ? '/api/tests/stop-all' : '/api/tests/run-all',
        {{method: 'POST'}}).then(() => {{
    poll();
    if (!polling) polling = setInterval(poll, 1500);
  }});
}});

poll();
</script>"""
    return shell("Tests", "/tests", body)


# One entry per definition kind the analyzer reports, in the order the Source
# files table lists them: analyzer kind, reader label singular and plural, and
# how the kind is written. A None gloss means the names themselves are listed.
DEFINITION_KINDS = [
    ("function", "Function or method definition",
     "Function or method definitions",
     "Written as <code>function f(…)</code> or <code>f(…) = …</code>."),
    ("const", "Constant", "Constants",
     "Written as <code>const NAME = …</code>."),
    ("module", "Module declaration", "Module declarations", None),
    ("struct", "Structure declaration", "Structure declarations", None),
    ("type", "Abstract type declaration", "Abstract type declarations", None),
]
# Above this many, naming them costs more room than it returns.
NAME_LIST_LIMIT = 12


def definition_kind_rows(symbols):
    """One row per definition kind: reader label, count, and either the names
    themselves when few enough to read, or how that kind is written."""
    by_kind = {}
    for definition in symbols:
        by_kind.setdefault(definition["kind"], []).append(definition["name"])
    rows = []
    for kind, singular, plural, gloss in DEFINITION_KINDS:
        names = by_kind.get(kind, [])
        what = gloss
        if what is None:
            unique = list(dict.fromkeys(names))  # source order, first use wins
            what = (", ".join(f"<code>{esc(n)}</code>" for n in unique)
                    if 0 < len(unique) <= NAME_LIST_LIMIT
                    else "Listed per file under <b>Technical details</b>.")
        rows.append(f'<tr><td>{esc(singular if len(names) == 1 else plural)}'
                    f'</td><td class="kind-count">{len(names)}</td>'
                    f'<td>{what}</td></tr>')
    return "".join(rows)


def page_map():
    analyzed = ANALYZE_CACHE.get()
    suites = SUITES_CACHE.get()
    per_file = {}
    for s in analyzed["symbols"]:
        per_file[s["file"]] = per_file.get(s["file"], 0) + 1
    src_rows = "".join(
        f'<tr><td><a href="/source/graph?file='
        f'{urllib.parse.quote(f)}"><code>src/{esc(f)}</code></a></td>'
        f'<td>{n} source definition{"" if n == 1 else "s"}</td></tr>'
        for f, n in sorted(per_file.items()))
    body = f"""
<h1>Package files</h1>
<div class="card">This page shows the source files, tests, tools, and Explorer
run records included with this package.</div>
<h2>Source files</h2>
<div class="card"><b>{len(analyzed["symbols"])} source definitions</b>, counted
afresh on every page load.
<div class="wrap"><table class="kinds-table">
<tr><th>Kind</th><th class="kind-count">Count</th><th>What it is</th></tr>
{definition_kind_rows(analyzed["symbols"])}</table></div>
A repeated name is counted separately for each definition.<br>
These definitions were found in the source code. This count does not show
that the code ran.</div>
<details class="suite-details map-details">
<summary>Technical details</summary>
<div class="card"><code>src/</code> contains the source files and is loaded by
<code>JunaCore.jl</code>.
<div class="wrap"><table>{src_rows}</table></div></div>
</details>
<h2>Tests</h2>
<div class="card">This package includes {len(suites)} tests. Open
<a href="/tests">Tests</a> to see what each one checks.</div>
<details class="suite-details map-details">
<summary>Technical details</summary>
<div class="card"><code>test/</code> contains the test files. Run all package
tests with the <code>Pkg.test</code> command:
<code>julia --project=. -e 'using Pkg; Pkg.test()'</code>.<br>
Shared fixtures are in <code>test/support/</code>; the test registry is in
<code>test/runtests.jl</code>.</div>
</details>
<h2>Tools</h2>
<div class="card">The package uses helper programs for error correction. The
Explorer files provide these pages and their checks.</div>
<details class="suite-details map-details">
<summary>Technical details</summary>
<div class="card"><code>tools/ldpc</code>: LDPC helper binaries (runtime
requirement of LDPC.jl - see THIRD_PARTY_NOTICES.md) ·
<code>tools/explorer</code>: this server, analyzer, coverage scanner,
contracts · <code>tools/parity_check.jl</code>: fixed Juna receiver results.</div>
</details>
<h2>Explorer run records</h2>
<div class="card">The Explorer saves the results of tests and checks started
here.</div>
<details class="suite-details map-details">
<summary>Technical details</summary>
<div class="card"><code>bench/test_runs.jsonl</code> and
<code>bench/health_runs.jsonl</code> store browser-triggered results and are
excluded from Git.</div>
</details>"""
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
not an incomplete implementation. Lite extends its Partial-FFT initial
candidate only when that candidate is invalid.</div>
<div class="card"><label>Receiver:
<select id="receiver-select">{options}</select></label>
&nbsp; <label>Compare with:
<select id="compare-select">{compare_options}</select></label>
<div id="receiver-purpose" style="margin-top:.7rem"></div></div>
<div class="grid2"><div id="chain-boxes"></div>
<div id="detail"><div class="card">Click a receiver step to see its
description, tests, and technical details.</div></div></div>
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
    '<b>' + selected.display_name + '</b> · ' + selected.purpose +
    '<details class="receiver-technical"><summary>Technical details</summary>' +
    '<p><b>Code name</b><br><code>' + selected.facade + '</code></p></details>';
  document.getElementById('chain-boxes').innerHTML =
    selected.chain_path.map(function(id, index) {{
      var st = STAGES.find(function(s) {{ return s.id === id; }});
      var shared = comparedPath.indexOf(id) >= 0;
      var marker = compared ? (shared ? 'shared' : 'selected only') : st.kind;
      return (index ? '<div class="arrow">↓</div>' : '') +
        '<div class="stage" id="' + st.id + '" data-stage="' + st.id + '">' +
        '<span class="badge kind">' + marker + '</span><b>' + st.title +
        '</b></div>';
    }}).join('') +
    (MODEL.optionalStages[selected.id] || []).map(function(id) {{
      var st = STAGES.find(function(s) {{ return s.id === id; }});
      return '<div class="arrow">optional deployment wrapper</div>' +
        '<div class="stage" id="' + st.id + '" data-stage="' + st.id + '">' +
        '<span class="badge kind">optional</span><b>' + st.title +
        '</b></div>';
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
    '<div class="card"><h2>' + st.title + '</h2><p>' + st.detail + '</p>' +
    '<details class="stage-technical"><summary>Technical details</summary>' +
    '<p><span class="badge">' + st.kind + '</span> ' +
    '<span class="badge ' + evCls + '">evidence: ' + st.evidence + '</span></p>' +
    '<p><b>Code names</b><br>' + syms + '</p>' +
    '<p><b>Tests</b><br>' + suites + '</p>' +
    (st.evidence === 'behavioral' ?
      '<p class="note">behavioral evidence: the declared suites exercise ' +
      'this stage through the public API without naming its internals - ' +
      'see the <a href="/coverage">coverage legend</a>.</p>' : '') +
    '</details></div>';
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
    graph_active = " active" if mode == "graph" else ""
    graph_toggle = "/source" if mode == "graph" else "/source/graph"
    graph_controls = """
<div id="graph-controls" class="card">
<button id="graph-back-stages" type="button">Receiver stages</button>
<button id="graph-show-all" type="button">Show all code names</button>
<span id="graph-legend">
<span class="badge">Stage — declared receiver step</span>
<span class="badge">Function — grouped source implementation</span>
<span class="badge">Arrow — declared flow or static call, never runtime</span>
</span>
</div>""" if mode == "graph" else ""
    body = f"""
<h1>Source</h1>
<div class="source-mode-tabs">
<a class="source-mode{graph_active}" href="{graph_toggle}">Graph</a>
</div>
<div class="card">One analyzer, two Explorer views. This page connects a
selected source definition to chain meaning and evidence. Graph accepts
receiver, stage, suite, file, and source definition context while preserving the same
panel. Static graph edges never claim runtime execution.
<span class="note"><a href="/source-advanced">Original Analyzer</a></span></div>
<div id="source-context" class="card"></div>
{graph_controls}
<div class="grid-source" data-source-mode="{esc(mode)}">
<div><input id="symsearch" placeholder="filter source definitions…" autocomplete="off">
<div id="symlist">{groups}</div></div>
<div id="egograph"></div>
<div id="inspector"><div class="card">
<p>Select a source definition to inspect it. Evidence taxonomy used here:</p>
<ul>{legend}</ul>
<p class="note">{esc(TAXONOMY_NOTE)}</p>
</div></div>
</div>
<script src="/static/vendor/vis-network.min.js"></script>
<script type="module" src="/static/source.js"></script>"""
    return shell("Source", "/source", body, wide=True)


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
<a href="/source">Source</a>
<a href="/source/graph">Graph</a>
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
                  f"{len(direct)} directly referenced code names</summary>"
                  f"<div class='wrap'><table><tr><th>Code name</th>"
                  f"<th>lines in {esc(entry.get('file', ''))}</th></tr>"
                  f"{items}</table></div></details>")
    body = f"""
<h1>Source-to-test coverage</h1>
<div class="note"><b>Static references, not runtime coverage.</b>
{esc(report['note'])} Run-status chips answer the separate question of
whether the suite last passed.</div>
<h2>Chain stage × suite</h2>
<div class="wrap"><table><tr><th>stage</th>{head}</tr>{rows}</table></div>
<div class="card">● direct textual reference to a stage code name ·
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
or was recorded on a dirty tree. <a href="/source/graph?receiver=lite">Open
the JUNA-Lite source view</a>.
<button id="health-run-all">run health battery</button>
<span style="color:var(--muted)">(battery = source-file-check, explorer-data,
server-behavior, package-load; the long checks run individually)</span></div>
<div class="wrap"><table>
<tr><th>check</th><th>status</th><th>commit</th><th>run time</th>
<th>ended</th><th></th></tr>
{rows}</table></div>
<div id="health-parity" class="card">Fixed Juna receiver results are compared
with values stored in this repository. Run the check above to see its result.
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


def _latest_experiment_results():
    """Newest experiments/*/results/results_view.html, or None."""
    pattern = os.path.join(ROOT, "experiments", "*", "results",
                           "results_view.html")
    candidates = glob.glob(pattern)
    candidates or (_ for _ in ()).throw(FileNotFoundError(pattern))
    return max(candidates, key=os.path.getmtime)


def page_results():
    try:
        path = _latest_experiment_results()
    except FileNotFoundError:
        body = """
<h1>Experiment results</h1>
<div class="card">No experiment results page exists yet. A search writes
<code>experiments/&lt;name&gt;/results/results_view.html</code>; this tab
shows the newest one.</div>"""
        return shell("Results", "/results", body)
    rel = os.path.relpath(path, ROOT)
    body = f"""
<h1>Experiment results</h1>
<div class="card"><strong>Unregistered experiment output.</strong> This page
renders <code>{esc(rel)}</code> from the gitignored
<code>experiments/</code> directory. It is not part of the test registry and
is not package evidence. ·
<a href="/results/view" target="_blank">open in its own tab</a></div>
<iframe src="/results/view" style="width:100%;height:calc(100vh - 200px);
border:1px solid var(--line, #ccc);border-radius:6px;background:white">
</iframe>"""
    return shell("Results", "/results", body, wide=True)


def page_run(key):
    suites = {s["key"]: s for s in SUITES_CACHE.get()}
    if key not in suites:
        return None
    s = suites[key]
    body = f"""
<h1>{esc(s['reader_title'])}</h1>
<p class="suite-summary">{esc(s['reader_summary'])}</p>
<div class="card"><b>Most recent Explorer run</b>
<span id="status" class="badge warn">idle</span>
<button onclick="start()">Run test</button>
<button onclick="cancel()">Cancel</button>
<a href="/tests#{esc(key)}">Back to tests</a></div>
<details class="suite-details run-details">
<summary>Technical details</summary>
<dl class="suite-meta">
<dt>How it works</dt><dd>{esc(s['method'])}</dd>
<dt>Test origin</dt><dd>{esc(s['reader_origin'])}</dd>
<dt>Internal key</dt><dd><code>{esc(s['key'])}</code></dd>
<dt>Test file</dt><dd><code>{esc(s['file'])}</code></dd>
</dl>
<p><code>julia --project=. test/{esc(s['file'])}</code></p>
<pre id="out">(not started)</pre>
</details>
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
    return shell(s["reader_title"], "/tests", body)

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
        if path == "/api/tests/status":
            return envelope(suite_run_status())
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
            if path == "/results":
                return self._send(page_results())
            if path == "/results/view":
                try:
                    with open(_latest_experiment_results(), "rb") as fh:
                        return self._send(fh.read(), ctype="text/html")
                except FileNotFoundError:
                    return self._send("no experiment results yet", 404,
                                      "text/plain")
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
                    last = last_run_by_key().get(m.group(1), {})
                    return self._send(json.dumps(
                        {"text": "", "seen": 0,
                         "status": last.get("status", "idle")}),
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
        if self.path in ("/api/tests/run-all", "/api/tests/stop-all"):
            with BATTERY_LOCK:
                battery = BATTERY["run"]
                busy = battery is not None and battery.status == "running"
                if self.path.endswith("stop-all"):
                    if busy:
                        battery.cancel()
                elif busy:
                    return self._send('{"error": "tests are already running"}',
                                      409, "application/json")
                else:
                    BATTERY["run"] = SuiteBattery(SUITES_CACHE.get())
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
