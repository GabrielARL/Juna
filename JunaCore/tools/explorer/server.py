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
import csv
import glob
import html
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
import urllib.parse
from fractions import Fraction
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
       ("/results", "Results"), ("/awgn-results", "AWGN results"),
       ("/no-harm-results", "Results")]
HIDDEN_NAV_TABS = {"/results", "/awgn-results"}
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
    receivers = [
        {"id": receiver["id"]}
        for receiver in RECEIVERS_CACHE.get()
        if sym["name"] in {
            receiver["facade"], *receiver.get("variant_facades", [])}
    ]
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
            public_facades = {
                facade
                for receiver in RECEIVERS_CACHE.get()
                for facade in [receiver["facade"],
                               *receiver.get("variant_facades", [])]
            }
            facades = [
                {"id": candidate["id"], "name": candidate["module"],
                 "kind": "facade"}
                for candidate in _data["symbols"]
                if candidate["name"] == "Modulation" and
                candidate["kind"] == "const" and
                candidate["module"] in public_facades
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
            receiver_facades = {
                catalog["facade"], *catalog.get("variant_facades", [])}
            ids.update(s["id"] for s in symbols
                       if s.get("module") in receiver_facades)
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
#results-analysis-tabs { position:static; z-index:auto; padding:0;
                         border:0; background:transparent; gap:.35rem;
                         margin:.15rem 0 .7rem; }
#results-analysis-tabs .results-analysis-tab {
  border:1px solid var(--line); border-radius:7px; padding:.35rem .75rem;
  color:var(--muted); background:var(--bg); }
#results-analysis-tabs a[aria-current=page] {
  color:var(--fg); border-color:var(--accent); background:var(--card);
  font-weight:600; }
.results-analysis-controls { display:flex; flex-wrap:wrap; align-items:end;
                             gap:.55rem .75rem; margin:.2rem 0 .7rem; }
.results-analysis-controls>span { display:flex; flex-wrap:wrap;
                                  align-items:center; gap:.55rem; }
.results-analysis-controls #results-open { margin-left:auto; }
@media (max-width:44rem) {
  .results-analysis-controls>* { max-width:100%; }
  .results-analysis-controls label { display:grid; width:100%; }
  .results-analysis-controls select { min-width:0; max-width:100%; }
  .results-analysis-controls #results-open { margin-left:0; }
}
"""


def shell(title, active, body, wide=False):
    parts = []
    for href, label in NAV:
        if href in HIDDEN_NAV_TABS:
            continue
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
independently. Five receiver paths:
Standard OFDM, Partial-FFT, JUNA-Lite, Profiled C,z, and Conditioned joint
C,W,z. HEAD:
<code>{esc(git_state()['head'])} {esc(git_state()['subject'])}</code><br>
Explore source:
<a href="/source/graph?receiver=standard">Standard</a> ·
<a href="/source/graph?receiver=partial-fft">Partial-FFT</a> ·
<a href="/source/graph?receiver=lite">JUNA-Lite</a> ·
<a href="/source/graph?receiver=profiled_cz">Profiled C,z</a> ·
<a href="/source/graph?receiver=conditioned_joint_cwz">Conditioned joint C,W,z</a></div>
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
<div class="card">The receiver entries are views over one shared,
contract-verified stage DAG. A baseline is a complete comparison receiver.
JUNA-Lite extends its Partial-FFT initial candidate only when that candidate
is invalid. Profiled C,z and Conditioned joint C,W,z process the complete
frame.</div>
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
    '<p><b>Code names</b><br><code>' +
    [selected.facade].concat(selected.variant_facades || []).join(
      '</code> · <code>') +
    '</code></p></details>';
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


_AWGN_PROGRESS_FAMILY = "2026-08-08-red-awgn-first4s-frames4-snr-sweep"
_AWGN_RATE_HARNESS = (
    "2026-08-08-red-awgn-first4s-frames4-rates0125-05-075-snr-sweep")
_AWGN_OUTER_HARNESS = (
    "2026-08-08-red-awgn-first4s-frames4-outer10-7-3-snr-sweep")
_AWGN_019_FAMILY = "2026-08-09-red-awgn-crc-no-harm-3receivers"
_AWGN_020_FAMILY = "2026-08-10-red-awgn-first8s-frames8-crc-no-harm"
_AWGN_021_FAMILY = "2026-08-10-red-awgn-first16s-frames16-crc-no-harm"
_AWGN_022_FAMILY = "2026-08-10-red-awgn-first32s-frames32-crc-no-harm"
_AWGN_023B_FAMILY = "2026-08-10-red-awgn-full-capture-frames47-crc-no-harm"
_AWGN_023C_FAMILY = (
    "2026-08-10-red-awgn-repeated-first32s-frames128-crc-no-harm")
_AWGN_025_FAMILY = (
    "2026-08-10-red-awgn-full-capture-frames47-rate05-crc-no-harm")
_AWGN_026_FAMILY = (
    "2026-08-10-red-awgn-full-capture-frames47-p10-10-crc-no-harm")
_AWGN_PROGRESS_AGGREGATE = (
    "red_snr_sweep_awgn_first4s_frames4_configuration.csv")
_AWGN_020_AGGREGATE = (
    "red_snr_sweep_awgn_first8s_frames8_configuration.csv")
_AWGN_021_AGGREGATE = (
    "red_snr_sweep_awgn_first16s_frames16_configuration.csv")
_AWGN_022_AGGREGATE = (
    "red_snr_sweep_awgn_first32s_frames32_configuration.csv")
_AWGN_023B_AGGREGATE = (
    "red_snr_sweep_awgn_full_capture_frames47_configuration.csv")
_AWGN_023C_AGGREGATE = (
    "red_snr_sweep_awgn_repeated_first32s_frames128_configuration.csv")
_AWGN_015_CONFIGURATIONS = (
    f"{_AWGN_PROGRESS_FAMILY}-n4096-cp64-"
    "rate025-p5-5-dc10-kfill-pfft4",
)
_AWGN_015_HARNESS = _AWGN_015_CONFIGURATIONS[0]
_AWGN_016_CONFIGURATIONS = tuple(
    f"{_AWGN_PROGRESS_FAMILY}-n4096-cp64-"
    f"rate025-p5-5-dc{check}-kfill-pfft4"
    for check in (6, 12, 14)
)
_AWGN_016_HARNESS = _AWGN_016_CONFIGURATIONS[0]
_AWGN_017_CONFIGURATIONS = tuple(
    f"{_AWGN_PROGRESS_FAMILY}-n2048-cp64-"
    f"rate025-p5-5-dc{check}-kfill-pfft4"
    for check in (12, 14)
)
_AWGN_017_HARNESS = _AWGN_017_CONFIGURATIONS[0]
_AWGN_018_CONFIGURATIONS = tuple(
    f"{_AWGN_PROGRESS_FAMILY}-n1024-cp64-"
    f"rate025-p5-5-dc{check}-kfill-pfft4"
    for check in (12, 14)
)
_AWGN_018_HARNESS = _AWGN_018_CONFIGURATIONS[0]
_AWGN_019_CONFIGURATIONS = tuple(
    f"{_AWGN_019_FAMILY}-n{nfft}-cp64-"
    f"rate025-p5-5-dc{check}-kfill-pfft4"
    for nfft in (1024, 2048)
    for check in (10, 12, 14)
)
_AWGN_019_HARNESS = _AWGN_019_CONFIGURATIONS[0]
_AWGN_020_CONFIGURATIONS = (
    f"{_AWGN_020_FAMILY}-n1024-cp64-"
    "rate025-p5-5-dc14-kfill-pfft4",
)
_AWGN_020_HARNESS = _AWGN_020_CONFIGURATIONS[0]
_AWGN_021_CONFIGURATIONS = (
    f"{_AWGN_021_FAMILY}-n1024-cp64-"
    "rate025-p5-5-dc14-kfill-pfft4",
)
_AWGN_021_HARNESS = _AWGN_021_CONFIGURATIONS[0]
_AWGN_022_CONFIGURATIONS = (
    f"{_AWGN_022_FAMILY}-n1024-cp64-"
    "rate025-p5-5-dc14-kfill-pfft4",
)
_AWGN_022_HARNESS = _AWGN_022_CONFIGURATIONS[0]
_AWGN_023B_CONFIGURATIONS = (
    f"{_AWGN_023B_FAMILY}-n1024-cp64-"
    "rate025-p5-5-dc14-kfill-pfft4",
)
_AWGN_023B_HARNESS = _AWGN_023B_CONFIGURATIONS[0]
_AWGN_023C_CONFIGURATIONS = (
    f"{_AWGN_023C_FAMILY}-n1024-cp64-"
    "rate025-p5-5-dc14-kfill-pfft4",
)
_AWGN_023C_HARNESS = _AWGN_023C_CONFIGURATIONS[0]
_AWGN_024_CONFIGURATIONS = (
    "2026-08-10-red-awgn-first32s-frames32-rate05-crc-no-harm-"
    "n1024-cp64-"
    "rate05-p5-5-dc14-kfill-pfft4",
)
_AWGN_024_HARNESS = _AWGN_024_CONFIGURATIONS[0]
_AWGN_025_CONFIGURATIONS = (
    f"{_AWGN_025_FAMILY}-n1024-cp64-"
    "rate05-p5-5-dc14-kfill-pfft4",
)
_AWGN_025_HARNESS = _AWGN_025_CONFIGURATIONS[0]
_AWGN_026_CONFIGURATIONS = (
    f"{_AWGN_026_FAMILY}-n1024-cp64-"
    "rate025-p10-10-dc14-kfill-pfft4",
)
_AWGN_026_HARNESS = _AWGN_026_CONFIGURATIONS[0]
_AWGN_027_CONFIGURATIONS = (
    f"{_AWGN_023B_FAMILY}-n2048-cp64-"
    "rate05-p10-10-dc14-kfill-pfft4",
)
_AWGN_027_HARNESS = _AWGN_027_CONFIGURATIONS[0]
_AWGN_PROGRESS_CAMPAIGNS = (
    {"campaign_id": "AWGN-008", "code_rate": "0.25",
     "rate_token": "025", "outer_spacing": 5,
     "harness": _AWGN_PROGRESS_FAMILY, "log": "awgn008_matrix.log"},
    {"campaign_id": "AWGN-009", "code_rate": "0.125",
     "rate_token": "0125", "outer_spacing": 5,
     "harness": _AWGN_RATE_HARNESS, "log": "awgn009_matrix.log"},
    {"campaign_id": "AWGN-012", "code_rate": "0.25",
     "rate_token": "025", "outer_spacing": 10,
     "harness": _AWGN_OUTER_HARNESS, "log": "awgn012_matrix.log"},
    {"campaign_id": "AWGN-015", "code_rate": "0.25",
     "rate_token": "025", "outer_spacing": 5,
     "configurations": _AWGN_015_CONFIGURATIONS,
     "harness": _AWGN_015_HARNESS, "log": "awgn015_sweep.log"},
    {"campaign_id": "AWGN-016", "code_rate": "0.25",
     "rate_token": "025", "outer_spacing": 5,
     "configurations": _AWGN_016_CONFIGURATIONS,
     "harness": _AWGN_016_HARNESS, "log": "awgn016_sweep.log"},
    {"campaign_id": "AWGN-017", "code_rate": "0.25",
     "rate_token": "025", "outer_spacing": 5,
     "configurations": _AWGN_017_CONFIGURATIONS,
     "harness": _AWGN_017_HARNESS, "log": "awgn017_sweep.log"},
    {"campaign_id": "AWGN-018", "code_rate": "0.25",
     "rate_token": "025", "outer_spacing": 5,
     "configurations": _AWGN_018_CONFIGURATIONS,
     "harness": _AWGN_018_HARNESS, "log": "awgn018_sweep.log"},
    {"campaign_id": "AWGN-019", "code_rate": "0.25",
     "rate_token": "025", "outer_spacing": 5,
     "configurations": _AWGN_019_CONFIGURATIONS,
     "harness": _AWGN_019_HARNESS, "log": "awgn019_sweep.log",
     "path_contract": "awgn019_path_contract.txt"},
    {"campaign_id": "AWGN-020", "code_rate": "0.25",
     "rate_token": "025", "outer_spacing": 5,
     "configurations": _AWGN_020_CONFIGURATIONS,
     "harness": _AWGN_020_HARNESS, "log": "awgn020_sweep.log",
     "path_contract": "awgn020_path_contract.txt",
     "aggregate": _AWGN_020_AGGREGATE},
    {"campaign_id": "AWGN-021", "code_rate": "0.25",
     "rate_token": "025", "outer_spacing": 5,
     "configurations": _AWGN_021_CONFIGURATIONS,
     "harness": _AWGN_021_HARNESS, "log": "awgn021_sweep.log",
     "path_contract": "awgn021_path_contract.txt",
     "aggregate": _AWGN_021_AGGREGATE},
    {"campaign_id": "AWGN-022", "code_rate": "0.25",
     "rate_token": "025", "outer_spacing": 5,
     "configurations": _AWGN_022_CONFIGURATIONS,
     "harness": _AWGN_022_HARNESS, "log": "awgn022_sweep.log",
     "path_contract": "awgn022_path_contract.txt",
     "aggregate": _AWGN_022_AGGREGATE},
    {"campaign_id": "AWGN-023B", "code_rate": "0.25",
     "rate_token": "025", "outer_spacing": 5,
     "configurations": _AWGN_023B_CONFIGURATIONS,
     "harness": _AWGN_023B_HARNESS, "log": "awgn023b_sweep.log",
     "path_contract": "awgn023b_path_contract.txt",
     "aggregate": _AWGN_023B_AGGREGATE},
    {"campaign_id": "AWGN-023C", "code_rate": "0.25",
     "rate_token": "025", "outer_spacing": 5,
     "configurations": _AWGN_023C_CONFIGURATIONS,
     "harness": _AWGN_023C_HARNESS, "log": "awgn023c_sweep.log",
     "path_contract": "awgn023c_path_contract.txt",
     "aggregate": _AWGN_023C_AGGREGATE},
    {"campaign_id": "AWGN-024", "code_rate": "0.5",
     "rate_token": "05", "outer_spacing": 5,
     "configurations": _AWGN_024_CONFIGURATIONS,
     "harness": _AWGN_024_HARNESS, "log": "awgn024_sweep.log",
     "path_contract": "awgn024_path_contract.txt",
     "aggregate": _AWGN_022_AGGREGATE},
    {"campaign_id": "AWGN-025", "code_rate": "0.5",
     "rate_token": "05", "outer_spacing": 5,
     "configurations": _AWGN_025_CONFIGURATIONS,
     "harness": _AWGN_025_HARNESS, "log": "awgn025_sweep.log",
     "path_contract": "awgn025_path_contract.txt",
     "aggregate": _AWGN_023B_AGGREGATE},
    {"campaign_id": "AWGN-026", "code_rate": "0.25",
     "rate_token": "025", "outer_spacing": 10,
     "configurations": _AWGN_026_CONFIGURATIONS,
     "harness": _AWGN_026_HARNESS, "log": "awgn026_sweep.log",
     "path_contract": "awgn026_path_contract.txt",
     "aggregate": _AWGN_023B_AGGREGATE},
    {"campaign_id": "AWGN-027", "code_rate": "0.5",
     "rate_token": "05", "outer_spacing": 10,
     "configurations": _AWGN_027_CONFIGURATIONS,
     "harness": _AWGN_027_HARNESS, "log": "awgn027_sweep.log",
     "path_contract": "awgn027_path_contract.txt",
     "aggregate": _AWGN_023B_AGGREGATE},
)
_AWGN_PROGRESS_PATHS = tuple(
    (f"red{channel}", hydrophone)
    for channel in range(1, 5)
    for hydrophone in range(1, 4))


def _awgn_configurations(campaign):
    explicit = campaign.get("configurations")
    if explicit is not None:
        return tuple(explicit)
    return tuple(
        f"{_AWGN_PROGRESS_FAMILY}-n{nfft}-cp{cp}-"
        f"rate{campaign['rate_token']}-p{campaign['outer_spacing']}-"
        f"{inner}-dc10-kfill-pfft4"
        for nfft in (1024, 2048)
        for cp in (64, 128, 256)
        for inner in (5, 10))


def _awgn_paths(campaign):
    """Return the explicitly approved paths, or the full 12-path matrix."""
    return tuple(campaign.get("paths", _AWGN_PROGRESS_PATHS))


def _awgn_progress_result_pair(campaign, experiment_id, channel, hydrophone):
    """Fixed final paths promoted only after one sweep path validates."""
    stem = f"{channel}_hydrophone{hydrophone}"
    run_dir = os.path.join(ROOT, "experiments", experiment_id, "results",
                           "runs", stem)
    aggregate = os.path.join(
        run_dir, campaign.get("aggregate", _AWGN_PROGRESS_AGGREGATE))
    trace = os.path.join(run_dir, f"{stem}_selection_trace.csv")
    return aggregate, trace


def _awgn_campaign_progress(campaign):
    """Count one approved sweep group and read only its fixed runner log."""
    configurations = _awgn_configurations(campaign)
    paths = _awgn_paths(campaign)
    completed = set()
    completed_configurations = 0
    for experiment_id in configurations:
        configuration_paths = set()
        for channel, hydrophone in paths:
            aggregate, trace = _awgn_progress_result_pair(
                campaign, experiment_id, channel, hydrophone)
            final_files = (aggregate, trace)
            path_contract = campaign.get("path_contract")
            if path_contract is not None:
                final_files += (
                    os.path.join(os.path.dirname(aggregate), path_contract),)
            if all(os.path.isfile(path) for path in final_files):
                key = (experiment_id, channel, hydrophone)
                completed.add(key)
                configuration_paths.add(key)
        if len(configuration_paths) == len(paths):
            completed_configurations += 1

    log_path = os.path.join(ROOT, "experiments", campaign["harness"],
                            campaign["log"])
    try:
        with open(log_path, encoding="utf-8", errors="replace") as handle:
            log = handle.read()
        updated_at = time.strftime(
            "%Y-%m-%dT%H:%M:%S%z",
            time.localtime(os.path.getmtime(log_path)))
    except OSError:
        log = ""
        updated_at = None

    marker = campaign["campaign_id"].replace("-", "_")
    lifecycle_events = list(re.finditer(
        rf"^{re.escape(marker)}_"
        r"(QUEUE_START|COMPUTE_START|COMPUTE_COMPLETE)(?:\s|$)",
        log, flags=re.MULTILINE))
    lifecycle = (lifecycle_events[-1].group(1)
                 if lifecycle_events else None)
    lifecycle_position = (lifecycle_events[-1].start()
                          if lifecycle_events else -1)

    current = None
    starts = list(re.finditer(
        r"^PATH_START\s+(AWGN-[0-9]+[A-Z]?)\s+(\S+)\s+"
        r"(red[1-4])\s+hydrophone\s+([1-3])(?:\s+\S+)?\s*$",
        log, flags=re.MULTILINE))
    if starts:
        (campaign_id, experiment_id, channel,
         hydrophone_text) = starts[-1].groups()
        hydrophone = int(hydrophone_text)
        key = (experiment_id, channel, hydrophone)
        if (lifecycle == "COMPUTE_START" and
                starts[-1].start() > lifecycle_position and
                campaign_id == campaign["campaign_id"] and
                experiment_id in configurations and
                (channel, hydrophone) in paths and
                key not in completed):
            current = {
                "experiment_id": experiment_id,
                "channel": channel,
                "hydrophone": hydrophone,
            }

    total_paths = len(configurations) * len(paths)
    completed_paths = len(completed)
    matrix_complete = completed_paths == total_paths
    if lifecycle == "COMPUTE_COMPLETE" and matrix_complete:
        state = "complete"
    elif matrix_complete:
        state = "checking"
    elif lifecycle == "COMPUTE_START":
        state = "running"
    elif lifecycle == "QUEUE_START":
        state = "queued"
    else:
        state = "not-started"
    return {
        "campaign_id": campaign["campaign_id"],
        "code_rate": campaign["code_rate"],
        "outer_spacing": campaign["outer_spacing"],
        "completed_paths": completed_paths,
        "total_paths": total_paths,
        "completed_configurations": completed_configurations,
        "total_configurations": len(configurations),
        "percent": 100 * completed_paths / total_paths,
        "current": current,
        "matrix_complete": matrix_complete,
        "state": state,
        "updated_at": updated_at,
    }


def _awgn_overall_state(campaigns, matrix_complete):
    """Summarize only unfinished lifecycle work after completed campaigns."""
    if all(item["state"] == "complete" for item in campaigns):
        return "complete"
    if matrix_complete:
        return "checking"
    if any(item["state"] in ("running", "checking")
           for item in campaigns):
        return "running"
    incomplete = [item for item in campaigns if not item["matrix_complete"]]
    if any(item["state"] == "queued" for item in incomplete):
        return "queued"
    if any(item["completed_paths"] for item in incomplete):
        return "running"
    return "not-started"


def _awgn_progress_data():
    """Aggregate approved AWGN-008 through AWGN-027 campaigns."""
    campaigns = [_awgn_campaign_progress(campaign)
                 for campaign in _AWGN_PROGRESS_CAMPAIGNS]
    completed_paths = sum(item["completed_paths"] for item in campaigns)
    total_paths = sum(item["total_paths"] for item in campaigns)
    completed_configurations = sum(
        item["completed_configurations"] for item in campaigns)
    total_configurations = sum(
        item["total_configurations"] for item in campaigns)
    active_paths = [dict(item["current"], campaign_id=item["campaign_id"])
                    for item in campaigns if item["current"] is not None]
    matrix_complete = completed_paths == total_paths
    state = _awgn_overall_state(campaigns, matrix_complete)
    updated = [item["updated_at"] for item in campaigns
               if item["updated_at"] is not None]
    return {
        "campaign_ids": [item["campaign_id"] for item in campaigns],
        "completed_paths": completed_paths,
        "total_paths": total_paths,
        "completed_configurations": completed_configurations,
        "total_configurations": total_configurations,
        "percent": 100 * completed_paths / total_paths,
        "active_paths": active_paths,
        "campaigns": campaigns,
        "matrix_complete": matrix_complete,
        "state": state,
        "updated_at": max(updated) if updated else None,
    }


def _awgn_progress_card():
    """Self-contained live bar used only by the AWGN Results page."""
    return """
<div id="awgn-live-progress" class="card" role="status" aria-live="polite">
<div style="display:flex;justify-content:space-between;gap:.8rem">
<strong>AWGN-008, AWGN-009, AWGN-012, AWGN-015, AWGN-016, AWGN-017, AWGN-018, AWGN-019, AWGN-020, AWGN-021, AWGN-022, AWGN-023B, AWGN-023C, AWGN-024, AWGN-025, AWGN-026, and AWGN-027 real-time progress</strong>
<span id="awgn-progress-state">checking...</span></div>
<progress id="awgn-progress-bar" max="708" value="0"
style="display:block;width:100%;height:1.1rem;margin:.55rem 0"></progress>
<div id="awgn-progress-text">Reading validated result paths...</div>
<div id="awgn-progress-campaigns" style="white-space:pre-line"></div>
<div id="awgn-progress-current" style="color:var(--muted);
overflow-wrap:anywhere"></div>
</div>
<script>
function pollAwgnProgress() {
  fetch('/api/awgn-results/progress', {cache: 'no-store'})
    .then(function (response) {
      if (!response.ok) throw new Error('progress request failed');
      return response.json();
    })
    .then(function (envelope) {
      var data = envelope.data;
      var bar = document.getElementById('awgn-progress-bar');
      bar.max = data.total_paths;
      bar.value = data.completed_paths;
      document.getElementById('awgn-progress-text').textContent =
        data.completed_paths + ' of ' + data.total_paths +
        ' paths validated (' + data.percent.toFixed(1) + '%); ' +
        data.completed_configurations + ' of ' + data.total_configurations +
        ' configurations complete.';
      var labels = {'not-started': 'not started', queued: 'queued',
                    running: 'running', checking: 'results complete; checks running',
                    complete: 'complete'};
      document.getElementById('awgn-progress-state').textContent =
        labels[data.state] || data.state;
      document.getElementById('awgn-progress-campaigns').textContent =
        data.campaigns.map(function (campaign) {
          return campaign.campaign_id + ' (rate ' + campaign.code_rate +
            ', outer spacing ' + campaign.outer_spacing + '): ' +
            campaign.completed_paths + ' of ' + campaign.total_paths +
            ' paths; ' + (labels[campaign.state] || campaign.state);
        }).join(String.fromCharCode(10));
      document.getElementById('awgn-progress-current').textContent =
        data.active_paths.length
        ? 'Current: ' + data.active_paths.map(function (current) {
            return current.campaign_id + ', ' + current.experiment_id + ', ' +
              current.channel + ' hydrophone ' + current.hydrophone;
          }).join(' | ')
        : '';
      if (data.state !== 'complete') {
        setTimeout(pollAwgnProgress, 2000);
      }
    })
    .catch(function () {
      document.getElementById('awgn-progress-state').textContent =
        'retrying progress check';
      setTimeout(pollAwgnProgress, 5000);
    });
}
pollAwgnProgress();
</script>"""


def _latest_experiment_results(awgn=False, no_harm=False):
    """Newest rendered result in one noise-model family."""
    experiment_ids = _experiment_ids(awgn=awgn, no_harm=no_harm)
    if not experiment_ids:
        family = "AWGN" if awgn else "non-AWGN"
        raise FileNotFoundError(f"no {family} experiment results")
    return _experiment_result_file(experiment_ids[0], "results_view.html")


_EXPERIMENT_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_RESULTS_PAGE_RE = re.compile(r"[a-z][a-z0-9-]*")


def _results_query(query):
    """Return the explicit experiment, requested page, and other state."""
    pairs = urllib.parse.parse_qsl(query or "", keep_blank_values=True)
    experiment_values = [value for key, value in pairs
                         if key == "experiment"]
    if len(experiment_values) > 1:
        raise FileNotFoundError("multiple experiment IDs")
    experiment_id = experiment_values[0] if experiment_values else None
    if experiment_id is not None and not _EXPERIMENT_ID_RE.fullmatch(
            experiment_id):
        raise FileNotFoundError("unsafe experiment ID")

    page_values = [value for key, value in pairs if key == "page"]
    page = page_values[0] if len(page_values) == 1 else "summary"
    if not _RESULTS_PAGE_RE.fullmatch(page):
        page = "summary"
    other = [(key, value) for key, value in pairs
             if key not in ("experiment", "page")]
    return experiment_id, page, other


def _experiment_result_file(experiment_id, filename):
    """Resolve one known result file without allowing path traversal."""
    if not experiment_id or not _EXPERIMENT_ID_RE.fullmatch(experiment_id):
        raise FileNotFoundError("missing or unsafe experiment ID")
    experiments = os.path.realpath(os.path.join(ROOT, "experiments"))
    path = os.path.realpath(os.path.join(experiments, experiment_id,
                                         "results", filename))
    if os.path.commonpath((experiments, path)) != experiments:
        raise FileNotFoundError("unsafe experiment path")
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    return path


def _experiment_id_from_result(path):
    return os.path.basename(os.path.dirname(os.path.dirname(path)))


def _experiment_manifest(experiment_id):
    """Read one self-identifying result manifest, or None when invalid."""
    try:
        manifest = _experiment_result_file(experiment_id,
                                           "results_manifest.json")
        with open(manifest, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    if (not isinstance(payload, dict) or
            payload.get("experiment_id") != experiment_id):
        return None
    return payload


def _experiment_family(experiment_id):
    """Return awgn/results for a valid manifest, else None."""
    manifest = _experiment_manifest(experiment_id)
    if manifest is None:
        return None
    noise_model = manifest.get("noise_model")
    if isinstance(noise_model, dict):
        kind = noise_model.get("kind", "")
    else:
        kind = noise_model if isinstance(noise_model, str) else ""
    return "awgn" if str(kind).strip().casefold() == "awgn" else "results"


def _manifest_declares_crc_no_harm(manifest):
    """True only for either retained explicit CRC no-harm declaration."""
    protected = {"profiled_cz", "cwz_joint"}
    reasons = {"standard_crc_valid", "crc_rescue", "standard_fallback"}
    policy = manifest.get("receiver_policy")
    if (not isinstance(policy, dict) or policy.get("lite") != "unchanged" or
            any(not isinstance(policy.get(receiver), str) or
                "no-harm" not in policy[receiver].casefold()
                for receiver in protected)):
        return False
    source_contract = manifest.get("source_contract")
    receivers = (source_contract.get("receivers", [])
                 if isinstance(source_contract, dict) else [])
    enabled = {
        receiver.get("id") for receiver in receivers
        if isinstance(receiver, dict) and
        receiver.get("crc_no_harm") is True
    }
    source_reasons = (source_contract.get("selection_reasons", [])
                      if isinstance(source_contract, dict) else [])
    declared_protected = manifest.get("protected_receivers", [])
    if (isinstance(declared_protected, list) and
            protected <= enabled and
            reasons <= set(source_reasons) and
            protected <= set(declared_protected)):
        return True
    rule = manifest.get("no_harm_rule")
    counts = manifest.get("selection_reason_counts")
    return (isinstance(rule, dict) and
            all(isinstance(rule.get(key), str) and rule[key].strip()
                for key in reasons) and
            isinstance(counts, dict) and
            all(isinstance(counts.get(receiver), dict) and
                reasons <= set(counts[receiver])
                for receiver in protected))


def _family_result_file(experiment_id, filename, awgn=False, no_harm=False):
    """Resolve a result file only when its manifest has the right family."""
    path = _experiment_result_file(experiment_id, filename)
    expected = "awgn" if awgn else "results"
    if _experiment_family(experiment_id) != expected:
        raise FileNotFoundError("experiment has no valid matching family")
    if no_harm:
        manifest = _experiment_manifest(experiment_id)
        if manifest is None or not _manifest_declares_crc_no_harm(manifest):
            raise FileNotFoundError(
                "experiment has no explicit CRC no-harm declaration")
    return path


def _experiment_ids(awgn=False, no_harm=False):
    """Every experiment in one noise-model family, newest first.

    Without this the Results tab silently shows whichever experiment was
    written last, and the others are reachable only by typing a query string.
    AWGN results are deliberately excluded from the original Results page;
    only an explicit manifest declaration can place them on the AWGN page.
    """
    pattern = os.path.join(ROOT, "experiments", "*", "results",
                           "results_view.html")
    found = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    experiment_ids = [_experiment_id_from_result(path) for path in found]
    expected = "awgn" if awgn else "results"
    selected = [experiment_id for experiment_id in experiment_ids
                if _experiment_family(experiment_id) == expected]
    if no_harm:
        selected = [experiment_id for experiment_id in selected
                    if _manifest_declares_crc_no_harm(
                        _experiment_manifest(experiment_id) or {})]
    return selected


_SWEEP_NAME_PATTERN = re.compile(
    r"-n(\d+)-cp(\d+)-rate(\d+)-p(\d+)-(\d+)-dc(\d+)-k([A-Za-z0-9]+)"
    r"(?:-pfft\d+)?$")
_PARTIAL_FFT_NAME_PATTERN = re.compile(r"-pfft([1-9][0-9]*)$")
_RESULTS_PATH_PATTERN = re.compile(r"([A-Za-z0-9._-]+):([1-9][0-9]*)")
_SWEEP_FIELDS = [
    ("N", "nfft"),
    ("CP", "cp"),
    ("code rate", "code_rate"),
    ("outer spacing", "outer_spacing"),
    ("inner spacing", "inner_spacing"),
    ("check degree", "check_degree"),
    ("horizon", "horizon"),
]
_NO_HARM_FIELDS = [
    ("Capture / frames", "capture_frames"),
    ("Receiver policy", "receiver_policy"),
    ("N", "nfft"),
    ("code rate", "code_rate"),
    ("pilots", "pilots"),
]


def _sweep_name_parameters(name):
    """The seven sweep parameters an experiment directory name encodes.

    `...-n2048-cp16-rate025-p3-5-dc10-k4` carries nfft, cp, code_rate,
    outer_spacing, inner_spacing, check_degree, and horizon — the columns
    of red_snr_sweep_uwa_noise.csv. A trailing `-pfft1` is read and
    discarded: it keeps those directories parsing, and the partial-FFT
    setting is not one of the dropdowns. Names without the suffix return
    None.
    """
    match = _SWEEP_NAME_PATTERN.search(name)
    if not match:
        return None
    nfft, cp, rate, outer, inner, check, horizon = match.groups()
    if rate.startswith("0") and len(rate) > 1:
        rate = "0." + rate[1:]
    return {"N": nfft, "CP": cp, "code rate": rate, "outer spacing": outer,
            "inner spacing": inner, "check degree": check, "horizon": horizon}


def _no_harm_policy_label(receiver_policy):
    """One retained policy label, or None for incomplete/mixed policies."""
    if not isinstance(receiver_policy, dict):
        return None
    protected = [receiver_policy.get(receiver)
                 for receiver in ("profiled_cz", "cwz_joint")]
    if (len(protected) != 2 or
            any(not isinstance(value, str) for value in protected)):
        return None
    if all("CRC-gated no-harm" in value for value in protected):
        return "CRC-gated"
    if all("CRC no-harm" in value for value in protected):
        return "CRC"
    return None


def _combined_pilot_percent_text(outer_spacing, inner_spacing):
    """Configured outer-plus-inner pilot density as a short percentage."""
    try:
        outer_spacing = int(outer_spacing)
        inner_spacing = int(inner_spacing)
    except (TypeError, ValueError) as exc:
        raise ValueError("pilot spacing must be a positive integer") from exc
    if outer_spacing < 1 or inner_spacing < 1:
        raise ValueError("pilot spacing must be a positive integer")
    percent = 100 * (
        Fraction(1, outer_spacing) + Fraction(1, inner_spacing))
    if percent.denominator == 1:
        return str(percent.numerator)
    return f"{float(percent):.1f}".rstrip("0").rstrip(".")


def _no_harm_result_metadata(experiment_id):
    """Compact reader label and useful filters for one no-harm result."""
    manifest = _experiment_manifest(experiment_id)
    if not isinstance(manifest, dict):
        return None

    geometry = manifest.get("geometry")
    if not isinstance(geometry, dict):
        geometry = manifest.get("geometry_display")
    geometry = geometry if isinstance(geometry, dict) else {}
    name_parameters = _sweep_name_parameters(experiment_id) or {}

    nfft = geometry.get("nfft", name_parameters.get("N"))
    code_rate = geometry.get("code_rate", name_parameters.get("code rate"))
    outer = geometry.get(
        "outer_spacing", name_parameters.get("outer spacing"))
    inner = geometry.get(
        "inner_spacing", name_parameters.get("inner spacing"))
    if any(value is None for value in (nfft, code_rate, outer, inner)):
        return None
    nfft, code_rate, outer, inner = map(str, (nfft, code_rate, outer, inner))

    frames = manifest.get("frames_per_point", manifest.get("frame_count"))
    if not isinstance(frames, int) or isinstance(frames, bool) or frames < 1:
        frame_match = re.search(r"-frames([1-9][0-9]*)-", experiment_id)
        frames = int(frame_match.group(1)) if frame_match else None
    if frames is None:
        return None

    if "-full-capture-" in experiment_id:
        capture_key = "full-capture"
        capture = "complete measured capture"
    else:
        first_match = re.search(r"-first([1-9][0-9]*)s-", experiment_id)
        if first_match:
            seconds_label = first_match.group(1)
        else:
            time_range = manifest.get("capture_time_seconds")
            if (not isinstance(time_range, list) or len(time_range) != 2 or
                    isinstance(time_range[0], bool) or
                    isinstance(time_range[1], bool) or
                    not isinstance(time_range[0], (int, float)) or
                    not isinstance(time_range[1], (int, float)) or
                    time_range[1] <= time_range[0]):
                return None
            seconds_label = f"{time_range[1] - time_range[0]:g}"
        capture_key = f"first{seconds_label}s"
        capture = f"first {seconds_label} s"

    receiver_policy = manifest.get("receiver_policy")
    policy = _no_harm_policy_label(receiver_policy)
    if policy is None:
        return None

    capture_frames = f"{capture} · {frames} frames"
    capture_frames_key = f"{capture_key}-frames{frames}"
    policy_key = (
        "crc-gated-no-harm" if policy == "CRC-gated" else "crc-no-harm")
    pilots = f"{outer}/{inner}"
    pilot_percent = _combined_pilot_percent_text(outer, inner)
    label = f"N={nfft} · rate={code_rate} · pilots={pilot_percent}%"
    return {
        "label": label,
        "pilot_spacing": pilots,
        "pilot_percent": pilot_percent,
        "parameters": {
            "Capture / frames": capture_frames_key,
            "Receiver policy": policy_key,
            "N": nfft,
            "code rate": code_rate,
            "pilots": pilots,
        },
        "parameter_labels": {
            "Capture / frames": capture_frames,
            "Receiver policy": policy,
            "N": nfft,
            "code rate": code_rate,
            "pilots": pilots,
        },
    }


def _experiment_display_label(experiment_id, no_harm=False):
    if no_harm:
        metadata = _no_harm_result_metadata(experiment_id)
        if metadata is not None:
            return metadata["label"]
    return experiment_id


def _experiment_result_paths(experiment_id):
    """Channel/hydrophone paths declared by one result manifest."""
    try:
        manifest = _experiment_result_file(experiment_id,
                                           "results_manifest.json")
        with open(manifest, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return []
    raw_paths = payload.get("paths")
    if raw_paths is None:
        raw_paths = []
        source_pattern = re.compile(
            r"runs/([A-Za-z0-9._-]+)_hydrophone([1-9][0-9]*)/"
            r"[^/]+\.csv")
        for source in payload.get("sources", []):
            if not isinstance(source, dict):
                continue
            source_path = source.get("path")
            digest = source.get("sha256")
            rows = source.get("rows")
            match = (source_pattern.fullmatch(source_path)
                     if isinstance(source_path, str) else None)
            if (match and isinstance(rows, int) and rows > 0 and
                    isinstance(digest, str) and
                    re.fullmatch(r"[0-9a-fA-F]{64}", digest)):
                raw_paths.append(" ".join(match.groups()))
    if not isinstance(raw_paths, list):
        return []
    paths = []
    seen = set()
    for raw in raw_paths:
        match = re.fullmatch(r"([A-Za-z0-9._-]+)\s+([1-9][0-9]*)",
                             str(raw).strip())
        if not match:
            continue
        channel, hydrophone = match.groups()
        value = f"{channel}:{hydrophone}"
        if value not in seen:
            paths.append({"value": value,
                          "label": f"{channel} hydrophone {hydrophone}"})
            seen.add(value)
    return paths


def _sweep_parameter_row(available, experiment_id, single_url,
                         initial_path="", route_prefix="/results",
                         no_harm=False, path_comparison=True):
    """One dropdown per sweep parameter, above the experiment dropdown.

    Each dropdown lists every value that exists across the sweep
    experiments; values incompatible with the other selections stay visible
    but disabled, so an existing configuration is never hidden. Choosing a
    channel/hydrophone shows that BER-SNR panel from every compatible
    fixed-geometry experiment.
    Experiments whose names carry no parameters stay reachable through the
    experiment dropdown but do not enter the comparison grid.
    """
    parsed = []
    for name in available:
        metadata = _no_harm_result_metadata(name) if no_harm else None
        parameters = (metadata["parameters"] if metadata is not None else
                      _sweep_name_parameters(name) if not no_harm else None)
        paths = _experiment_result_paths(name)
        if parameters and paths:
            parsed.append({"id": name, "parameters": parameters,
                           "parameter_labels": (
                               metadata.get("parameter_labels", {})
                               if metadata is not None else {}),
                           "paths": paths})
    if len(parsed) < 2:
        return ""
    all_paths = {}
    for entry in parsed:
        for path in entry["paths"]:
            all_paths[path["value"]] = path["label"]
    if initial_path not in all_paths:
        initial_path = ""
    path_options = ['<option value="">(all)</option>']
    path_options.extend(
        f'<option value="{esc(value)}"'
        f'{" selected" if value == initial_path else ""}>'
        f'{esc(all_paths[value])}</option>'
        for value in sorted(
            all_paths,
            key=lambda value: (value.rsplit(":", 1)[0],
                               int(value.rsplit(":", 1)[1]))))
    data = json.dumps(parsed).replace("</", "<\\/")
    current = json.dumps(experiment_id).replace("</", "<\\/")
    active_fields = _NO_HARM_FIELDS if no_harm else _SWEEP_FIELDS
    fields = json.dumps([{"name": name, "query": query}
                         for name, query in active_fields])
    default_view = json.dumps(single_url).replace("</", "<\\/")
    comparison_prefix = json.dumps(
        route_prefix + "/compare?").replace("</", "<\\/")
    narrow_picker = "true" if no_harm else "false"
    allow_path_comparison = "true" if path_comparison else "false"
    return ("""
<p style="margin:.2rem 0 .4rem;display:flex;align-items:center;gap:.6rem;
flex-wrap:wrap" id="sweep-parameters">
<span id="sweep-parameter-controls" style="display:contents"></span>
<label>Channel / hydrophone <select id="path-filter">""" +
            "".join(path_options) + """</select></label>
<span id="sweep-match-count" role="status" aria-live="polite"
aria-atomic="true"></span></p>
<script>
window.addEventListener("DOMContentLoaded", function () {
  var experiments = """ + data + """;
  var current = """ + current + """;
  var fields = """ + fields + """;
  var names = fields.map(function (field) { return field.name; });
  var narrowPicker = """ + narrow_picker + """;
  var query = new URLSearchParams(location.search);
  var chosen = {};
  fields.forEach(function (field) {
    chosen[field.name] = query.get(field.query) || "";
  });
  var controls = document.getElementById("sweep-parameter-controls");
  var count = document.getElementById("sweep-match-count");
  var pathSelect = document.getElementById("path-filter");
  var single = document.getElementById("single-result");
  var comparison = document.getElementById("comparison-result");
  var empty = document.getElementById("comparison-empty");
  var openLink = document.getElementById("results-open");
  var singleUrl = """ + default_view + """;
  var allowPathComparison = """ + allow_path_comparison + """;
  if (!allowPathComparison) {
    pathSelect.value = "";
    pathSelect.disabled = true;
  }
  var selectedPath = pathSelect.value;

  function matching(skipped) {
    return experiments.filter(function (entry) {
      return names.every(function (name) {
        return name === skipped || chosen[name] === "" ||
               entry.parameters[name] === chosen[name];
      });
    });
  }

  function updateAddress() {
    var url = new URL(location.href);
    fields.forEach(function (field) {
      if (chosen[field.name])
        url.searchParams.set(field.query, chosen[field.name]);
      else
        url.searchParams.delete(field.query);
    });
    if (selectedPath) url.searchParams.set("path", selectedPath);
    else url.searchParams.delete("path");
    history.replaceState(null, "", url);
  }

  function comparisonUrl(found) {
    var params = new URLSearchParams();
    found.forEach(function (entry) {
      params.append("experiment", entry.id);
    });
    params.set("path", selectedPath);
    return """ + comparison_prefix + """ + params.toString();
  }

  function renderResult(found) {
    if (!found.length) {
      comparison.hidden = true;
      single.hidden = true;
      empty.hidden = false;
      empty.textContent = "No experiment matches the selected filters.";
      openLink.removeAttribute("href");
      return;
    }
    if (!selectedPath) {
      comparison.hidden = true;
      empty.hidden = true;
      single.hidden = false;
      openLink.href = allowPathComparison ? singleUrl :
        single.getAttribute("src");
      return;
    }
    var withPath = found.filter(function (entry) {
      return entry.paths.some(function (path) {
        return path.value === selectedPath;
      });
    });
    single.hidden = true;
    if (!withPath.length) {
      comparison.hidden = true;
      empty.hidden = false;
      empty.textContent = "No BER-SNR plot matches the selected " +
                          "experiment conditions and channel/hydrophone.";
      openLink.removeAttribute("href");
      return;
    }
    var url = comparisonUrl(withPath);
    empty.hidden = true;
    comparison.hidden = false;
    if (comparison.getAttribute("src") !== url)
      comparison.setAttribute("src", url);
    openLink.href = url;
  }

  function narrowExperimentPicker(found) {
    var picker = document.getElementById("experiment-picker");
    if (!picker) return "ready";
    if (!narrowPicker) {
      if (!selectedPath && found.length === 1 && found[0].id !== current) {
        var uniqueUrl = new URL(location.href);
        uniqueUrl.searchParams.set("experiment", found[0].id);
        location.href = uniqueUrl;
        return "redirect";
      }
      return "ready";
    }
    var oldPlaceholder = picker.querySelector(
      "option[data-filter-placeholder]");
    if (oldPlaceholder) oldPlaceholder.remove();
    var filtering = names.some(function (name) { return chosen[name] !== ""; });
    var foundIds = found.map(function (entry) { return entry.id; });
    Array.prototype.forEach.call(picker.options, function (option) {
      var matches = !filtering || foundIds.indexOf(option.value) >= 0;
      option.hidden = !matches;
      option.disabled = !matches;
    });
    if (!filtering || foundIds.indexOf(current) >= 0) {
      picker.value = current;
      return "ready";
    }
    if (found.length === 1 && !selectedPath) {
      var url = new URL(location.href);
      url.searchParams.set("experiment", found[0].id);
      location.href = url;
      return "redirect";
    }
    var placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.disabled = true;
    placeholder.selected = true;
    placeholder.setAttribute("selected", "selected");
    placeholder.dataset.filterPlaceholder = "true";
    placeholder.textContent = found.length
      ? "Choose one of " + found.length + " matching experiments"
      : "No matching experiment";
    picker.insertBefore(placeholder, picker.firstChild);
    return "choose";
  }

  function parameterLabel(name, value) {
    for (var i = 0; i < experiments.length; i += 1) {
      var entry = experiments[i];
      if (entry.parameters[name] === value &&
          entry.parameter_labels && entry.parameter_labels[name])
        return entry.parameter_labels[name];
    }
    return value;
  }

  function compareParameterValues(name, a, b) {
    if (name === "Capture / frames") {
      var firstA = /^first([0-9.]+)s-/.exec(a);
      var firstB = /^first([0-9.]+)s-/.exec(b);
      var rankA = firstA ? parseFloat(firstA[1]) : Number.POSITIVE_INFINITY;
      var rankB = firstB ? parseFloat(firstB[1]) : Number.POSITIVE_INFINITY;
      if (rankA !== rankB) return rankA - rankB;
    }
    if (name === "pilots") {
      var partsA = a.split("/").map(Number);
      var partsB = b.split("/").map(Number);
      if (partsA[0] !== partsB[0]) return partsA[0] - partsB[0];
      if (partsA[1] !== partsB[1]) return partsA[1] - partsB[1];
    }
    if (name === "Receiver policy") {
      var policyOrder = ["crc-no-harm", "crc-gated-no-harm"];
      return policyOrder.indexOf(a) - policyOrder.indexOf(b);
    }
    var x = parseFloat(a), y = parseFloat(b);
    if (!isNaN(x) && !isNaN(y) && x !== y) return x - y;
    return a < b ? -1 : a > b ? 1 : 0;
  }

  function render() {
    controls.textContent = "";
    fields.forEach(function (field) {
      var name = field.name;
      var values = [];
      experiments.forEach(function (entry) {
        if (values.indexOf(entry.parameters[name]) < 0)
          values.push(entry.parameters[name]);
      });
      if (chosen[name] && values.indexOf(chosen[name]) < 0)
        values.push(chosen[name]);
      var compatible = [];
      matching(name).forEach(function (entry) {
        if (compatible.indexOf(entry.parameters[name]) < 0)
          compatible.push(entry.parameters[name]);
      });
      values.sort(function (a, b) {
        return compareParameterValues(name, a, b);
      });
      var label = document.createElement("label");
      var select = document.createElement("select");
      label.textContent = name + " ";
      if (narrowPicker) {
        select.id = "sweep-filter-" + field.query;
        label.htmlFor = select.id;
      }
      var blank = document.createElement("option");
      blank.value = "";
      blank.textContent = "(all)";
      select.appendChild(blank);
      values.forEach(function (value) {
        var option = document.createElement("option");
        option.value = value;
        option.textContent = parameterLabel(name, value);
        if (compatible.indexOf(value) < 0 && value !== chosen[name]) {
          option.disabled = true;
          option.textContent += " (no match with other selections)";
        }
        if (value === chosen[name]) option.selected = true;
        select.appendChild(option);
      });
      select.onchange = function () {
        chosen[name] = select.value;
        updateAddress();
        render();
      };
      if (narrowPicker) {
        controls.appendChild(label);
        controls.appendChild(select);
      } else {
        label.appendChild(select);
        controls.appendChild(label);
      }
    });
    var found = matching(null);
    var pickerState = narrowExperimentPicker(found);
    if (pickerState === "redirect") return;
    count.textContent = selectedPath
      ? found.filter(function (entry) {
          return entry.paths.some(function (path) {
            return path.value === selectedPath;
          });
        }).length + " plots match across experiments"
      : found.length + " experiments match";
    if (pickerState === "choose" && !selectedPath) {
      comparison.hidden = true;
      single.hidden = true;
      empty.hidden = false;
      empty.textContent = "Choose an experiment from the filtered list.";
      openLink.removeAttribute("href");
    } else {
      renderResult(found);
    }
  }

  pathSelect.onchange = function () {
    selectedPath = pathSelect.value;
    updateAddress();
    render();
  };
  var picker = document.getElementById("experiment-picker");
  if (picker) picker.onchange = function () {
    var url = new URL(location.href);
    url.searchParams.set("experiment", picker.value);
    location.href = url;
  };
  render();
});
</script>""")


def _results_comparison_query(query, awgn=False, no_harm=False):
    """Validated same-family IDs and one channel/hydrophone comparison key."""
    pairs = urllib.parse.parse_qsl(query or "", keep_blank_values=True)
    experiment_ids = [value for key, value in pairs
                      if key == "experiment"]
    path_values = [value for key, value in pairs if key == "path"]
    if not experiment_ids or len(experiment_ids) > 64 or len(path_values) != 1:
        raise FileNotFoundError("incomplete comparison query")
    if any(not _EXPERIMENT_ID_RE.fullmatch(value)
           for value in experiment_ids):
        raise FileNotFoundError("unsafe experiment ID")
    match = _RESULTS_PATH_PATTERN.fullmatch(path_values[0])
    if not match:
        raise FileNotFoundError("unsafe channel/hydrophone path")
    unique_ids = list(dict.fromkeys(experiment_ids))
    for experiment_id in unique_ids:
        _family_result_file(experiment_id, "results_view.html", awgn=awgn,
                            no_harm=no_harm)
    return unique_ids, match.group(1), int(match.group(2))


_RESULT_PANEL_RE = re.compile(
    r'<figure\b[^>]*class="[^"]*\bpanel\b[^"]*"[^>]*>.*?</figure>',
    re.IGNORECASE | re.DOTALL)


_NO_HARM_COMPACT_FOUR_STYLE = """<style id="no-harm-compact-four">
html,body{margin:0}
.viz-root{padding:4px!important;min-height:0!important}
.viz-root>h1,.viz-root>.axis-title,
.viz-root>.provenance,.viz-root>.legend,
.viz-root>details{display:none!important}
.grid-panels,.grid-panels.single,.grid-panels.pair{
display:grid!important;
grid-template-columns:repeat(3,minmax(0,1fr))!important;
gap:4px!important}
.panel{min-width:0!important;padding:3px 2px 1px!important;
border-radius:5px!important}
.panel figcaption{padding:0 3px 1px!important;font-size:9px!important;
line-height:1.15!important;min-width:0}
.panel figcaption b{font-size:10px!important;white-space:nowrap;
overflow:hidden;text-overflow:ellipsis}
.panel figcaption>span{display:none!important}
.panel svg{width:100%!important;height:auto!important;display:block!important}
</style>"""


_EFFECTIVE_RATE_RECEIVERS = (
    ("ofdm_fec", "OFDM+FEC", "#339af0"),
    ("pfft", "PFFT", "#ff922b"),
    ("lite", "Lite", "#51cf66"),
    ("profiled_cz", "(C,z)", "#e66daf"),
    ("cwz_joint", "(C,W,z)", "#9775fa"),
)


def _no_harm_effective_rate_observations(experiment_id):
    """Strict stored rate and frame-count observations by exact SNR."""
    view = _family_result_file(
        experiment_id, "results_view.html", awgn=True, no_harm=True)
    result_dir = os.path.realpath(os.path.dirname(view))
    aggregate_files = []
    for candidate in glob.glob(os.path.join(result_dir, "*.csv")):
        real_candidate = os.path.realpath(candidate)
        if (os.path.commonpath((result_dir, real_candidate)) == result_dir and
                os.path.isfile(candidate) and not os.path.islink(candidate)):
            aggregate_files.append(candidate)
    if len(aggregate_files) != 1:
        raise FileNotFoundError("one aggregate CSV is required")

    receiver_ids = tuple(receiver_id for receiver_id, _label, _color
                         in _EFFECTIVE_RATE_RECEIVERS)
    expected = {
        (f"red{channel}", hydrophone, receiver_id)
        for channel in range(1, 5)
        for hydrophone in range(1, 4)
        for receiver_id in receiver_ids
    }
    rows_by_snr = {}
    try:
        with open(aggregate_files[0], newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            required = {
                "channel", "lane", "snr_db", "algorithm_id",
                "effective_rate_bps", "frames", "successful_frames",
            }
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise FileNotFoundError("aggregate columns are incomplete")
            for row in reader:
                try:
                    row_snr = float(row["snr_db"])
                except (TypeError, ValueError):
                    raise FileNotFoundError("invalid aggregate SNR")
                if not math.isfinite(row_snr):
                    raise FileNotFoundError("invalid aggregate SNR")
                channel = row["channel"]
                receiver_id = row["algorithm_id"]
                try:
                    hydrophone = int(row["lane"])
                    rate = float(row["effective_rate_bps"])
                    frames = int(row["frames"])
                    successful_frames = int(row["successful_frames"])
                except (TypeError, ValueError):
                    raise FileNotFoundError("invalid effective-rate row")
                key = channel, hydrophone, receiver_id
                rows = rows_by_snr.setdefault(row_snr, {})
                if (key not in expected or key in rows or
                        not math.isfinite(rate) or rate < 0 or frames < 1 or
                        successful_frames < 0 or
                        successful_frames > frames or
                        (rate == 0) != (successful_frames == 0)):
                    raise FileNotFoundError("invalid effective-rate coverage")
                rows[key] = {
                    "rate": rate,
                    "frames": frames,
                    "successful_frames": successful_frames,
                }
    except (OSError, csv.Error) as error:
        raise FileNotFoundError("unreadable aggregate CSV") from error
    if (not rows_by_snr or
            any(set(rows) != expected for rows in rows_by_snr.values())):
        raise FileNotFoundError("incomplete effective-rate coverage")
    frame_counts = {
        observation["frames"]
        for rows in rows_by_snr.values()
        for observation in rows.values()
    }
    if len(frame_counts) != 1:
        raise FileNotFoundError("effective-rate frame counts disagree")
    return dict(sorted(rows_by_snr.items()))


def _no_harm_effective_rate_data(experiment_id):
    """Strict stored effective-rate values grouped by their exact SNR."""
    return {
        snr_db: {
            key: observation["rate"]
            for key, observation in rows.items()
        }
        for snr_db, rows in
        _no_harm_effective_rate_observations(experiment_id).items()
    }


def _no_harm_effective_rate_snr(values, snr_grid):
    """One canonical query SNR from the stored grid; omitted means 20 dB."""
    if len(values) > 1:
        raise FileNotFoundError("multiple effective-rate SNR values")
    requested = values[0] if values else "20"
    canonical = {f"{snr_db:g}": snr_db for snr_db in snr_grid}
    if requested not in canonical:
        raise FileNotFoundError("effective-rate SNR is outside the stored grid")
    return canonical[requested]


def _no_harm_effective_rate_slider(
        snr_grid, selected_snr, rate_url, plot_value="effective-rate"):
    """Range control for a uniformly spaced stored SNR grid."""
    if len(snr_grid) < 2:
        raise FileNotFoundError("effective-rate SNR grid is incomplete")
    step = snr_grid[1] - snr_grid[0]
    if (step <= 0 or any(
            not math.isclose(right - left, step, abs_tol=1e-12, rel_tol=0)
            for left, right in zip(snr_grid, snr_grid[1:]))):
        raise FileNotFoundError("effective-rate SNR grid is not uniform")
    minimum = f"{snr_grid[0]:g}"
    maximum = f"{snr_grid[-1]:g}"
    step_text = f"{step:g}"
    selected = f"{selected_snr:g}"
    allowed = json.dumps([f"{snr_db:g}" for snr_db in snr_grid])
    base_rate_url = json.dumps(rate_url).replace("</", "<\\/")
    selected_plot = json.dumps(plot_value).replace("</", "<\\/")
    return f'''<span id="effective-rate-snr-control"
style="display:inline-flex;align-items:center;gap:.4rem"
data-default-snr="{selected}">
<label for="effective-rate-snr">SNR</label>
<input id="effective-rate-snr" type="range"
min="{minimum}" max="{maximum}" step="{step_text}" value="{selected}"
aria-label="SNR in dB" aria-valuetext="{selected} dB"
aria-describedby="effective-rate-snr-value">
<output id="effective-rate-snr-value" for="effective-rate-snr">{selected} dB</output></span>
<script>
window.addEventListener("DOMContentLoaded", function () {{
  var control = document.getElementById("effective-rate-snr-control");
  var slider = document.getElementById("effective-rate-snr");
  var output = document.getElementById("effective-rate-snr-value");
  var single = document.getElementById("single-result");
  var comparison = document.getElementById("comparison-result");
  var empty = document.getElementById("comparison-empty");
  var openLink = document.getElementById("results-open");
  var allowed = {allowed};
  var baseRateUrl = {base_rate_url};
  var selectedPlot = {selected_plot};

  function updateLabel() {{
    var text = slider.value + " dB";
    output.value = text;
    slider.setAttribute("aria-valuetext", text);
  }}

  function applyRate(commit) {{
    updateLabel();
    var rateUrl = new window.URL(baseRateUrl, window.location.href);
    rateUrl.searchParams.set("snr_db", slider.value);
    var relativeRateUrl = rateUrl.pathname + rateUrl.search;
    var openRateUrl = new window.URL(rateUrl);
    openRateUrl.searchParams.delete("embedded");
    var relativeOpenRateUrl = openRateUrl.pathname + openRateUrl.search;
    comparison.hidden = true;
    empty.hidden = true;
    single.hidden = false;
    if (single.getAttribute("src") !== relativeRateUrl)
      single.setAttribute("src", relativeRateUrl);
    openLink.href = relativeOpenRateUrl;
    if (commit) {{
      var pageUrl = new window.URL(window.location.href);
      pageUrl.searchParams.set("plot", selectedPlot);
      pageUrl.searchParams.set("snr_db", slider.value);
      history.replaceState(null, "", pageUrl);
    }}
  }}

  function restoreFromAddress() {{
    var requested = new window.URL(window.location.href).searchParams.get(
      "snr_db");
    slider.value = allowed.indexOf(requested) >= 0
      ? requested : control.dataset.defaultSnr;
    applyRate(false);
  }}

  slider.addEventListener("input", updateLabel);
  slider.addEventListener("change", function () {{ applyRate(true); }});
  window.addEventListener("pageshow", restoreFromAddress);
  restoreFromAddress();
}});
</script>'''


def _no_harm_effective_rate_query(query):
    """One no-harm experiment and optional canonical SNR, with no extras."""
    pairs = urllib.parse.parse_qsl(query or "", keep_blank_values=True)
    if any(key not in ("experiment", "snr_db") for key, _value in pairs):
        raise FileNotFoundError("unknown effective-rate query value")
    experiments = [value for key, value in pairs if key == "experiment"]
    if (len(experiments) != 1 or
            not _EXPERIMENT_ID_RE.fullmatch(experiments[0])):
        raise FileNotFoundError("one no-harm experiment is required")
    rows_by_snr = _no_harm_effective_rate_data(experiments[0])
    snr_values = [value for key, value in pairs if key == "snr_db"]
    snr_db = _no_harm_effective_rate_snr(
        snr_values, tuple(rows_by_snr))
    return experiments[0], snr_db


def _best_observed_scope(values, default="all"):
    """One canonical best-observed comparison scope."""
    if len(values) > 1:
        raise FileNotFoundError("multiple best-observed scopes")
    scope = values[0] if values else default
    if scope not in ("family", "all"):
        raise FileNotFoundError("unknown best-observed scope")
    return scope


def _no_harm_effective_rate_best_query(query):
    """One anchor, canonical SNR, scope, and optional embedded marker."""
    pairs = urllib.parse.parse_qsl(query or "", keep_blank_values=True)
    if any(key not in ("experiment", "snr_db", "scope", "embedded")
           for key, _value in pairs):
        raise FileNotFoundError("unknown best-observed query value")
    experiments = [value for key, value in pairs if key == "experiment"]
    if (len(experiments) != 1 or
            not _EXPERIMENT_ID_RE.fullmatch(experiments[0])):
        raise FileNotFoundError("one no-harm experiment is required")
    rows_by_snr = _no_harm_effective_rate_data(experiments[0])
    snr_db = _no_harm_effective_rate_snr(
        [value for key, value in pairs if key == "snr_db"],
        tuple(rows_by_snr))
    scope = _best_observed_scope(
        [value for key, value in pairs if key == "scope"])
    embedded_values = [value for key, value in pairs if key == "embedded"]
    if len(embedded_values) > 1 or any(
            value != "1" for value in embedded_values):
        raise FileNotFoundError("unknown best-observed embedded value")
    return experiments[0], snr_db, scope, bool(embedded_values)


def _no_harm_effective_rate_rows(experiment_id, snr_db=20.0):
    """Strict stored effective-rate rows for one no-harm result and SNR."""
    rows_by_snr = _no_harm_effective_rate_data(experiment_id)
    if snr_db not in rows_by_snr:
        raise FileNotFoundError("effective-rate SNR is outside the stored grid")
    return rows_by_snr[snr_db]


def _no_harm_effective_rate_configuration(experiment_id):
    """One N and every configuration field that must not vary with N."""
    manifest = _experiment_manifest(experiment_id)
    metadata = _no_harm_result_metadata(experiment_id)
    name_parameters = _sweep_name_parameters(experiment_id)
    pfft_match = _PARTIAL_FFT_NAME_PATTERN.search(experiment_id)
    if (not isinstance(manifest, dict) or metadata is None or
            name_parameters is None or pfft_match is None):
        raise FileNotFoundError("effective-rate configuration is incomplete")

    parameters = metadata["parameters"]
    try:
        nfft = int(name_parameters["N"])
    except (KeyError, TypeError, ValueError):
        raise FileNotFoundError("invalid effective-rate N")
    if (nfft < 1 or parameters.get("N") != str(nfft) or
            parameters.get("code rate") != name_parameters["code rate"] or
            parameters.get("pilots") !=
            f'{name_parameters["outer spacing"]}/'
            f'{name_parameters["inner spacing"]}'):
        raise FileNotFoundError("effective-rate geometry disagrees")

    geometry = manifest.get("geometry")
    geometry_display = manifest.get("geometry_display")
    if not isinstance(geometry, dict):
        raise FileNotFoundError("effective-rate manifest geometry is missing")
    geometry_display = (geometry_display
                        if isinstance(geometry_display, dict) else {})

    def manifest_geometry_value(field):
        return geometry_display.get(field, geometry.get(field))

    expected_geometry = {
        "nfft": name_parameters["N"],
        "cp": name_parameters["CP"],
        "outer_spacing": name_parameters["outer spacing"],
        "inner_spacing": name_parameters["inner spacing"],
        "check_degree": name_parameters["check degree"],
    }
    if any(str(manifest_geometry_value(field)) != str(expected)
           for field, expected in expected_geometry.items()):
        raise FileNotFoundError("manifest and named geometry disagree")
    try:
        manifest_rate = float(manifest_geometry_value("code_rate"))
        named_rate = float(name_parameters["code rate"])
    except (TypeError, ValueError):
        raise FileNotFoundError("manifest code rate is invalid")
    if (not math.isfinite(manifest_rate) or
            not math.isclose(manifest_rate, named_rate,
                             rel_tol=0, abs_tol=1e-12)):
        raise FileNotFoundError("manifest and named code rate disagree")
    manifest_horizon = str(manifest_geometry_value("horizon")).casefold()
    named_horizon = str(name_parameters["horizon"]).casefold()
    if named_horizon == "fill":
        if manifest_horizon not in ("fill", "0"):
            raise FileNotFoundError("manifest and named horizon disagree")
    elif manifest_horizon != named_horizon:
        raise FileNotFoundError("manifest and named horizon disagree")

    frame_match = re.search(r"-frames([1-9][0-9]*)-", experiment_id)
    manifest_frames = manifest.get("frames_per_point", manifest.get(
        "frame_count"))
    if (frame_match is not None and
            (isinstance(manifest_frames, bool) or
             not isinstance(manifest_frames, int) or
             manifest_frames != int(frame_match.group(1)))):
        raise FileNotFoundError("manifest and named frame count disagree")
    capture_range = manifest.get("capture_time_seconds")
    if (not isinstance(capture_range, list) or len(capture_range) != 2 or
            any(isinstance(value, bool) or
                not isinstance(value, (int, float)) or
                not math.isfinite(value) for value in capture_range) or
            capture_range[0] != 0 or capture_range[1] <= capture_range[0]):
        raise FileNotFoundError("manifest capture window is invalid")
    first_match = re.search(r"-first([1-9][0-9]*)s-", experiment_id)
    if (first_match is not None and
            not math.isclose(capture_range[1], int(first_match.group(1)),
                             rel_tol=0, abs_tol=1e-12)):
        raise FileNotFoundError("manifest and named capture window disagree")

    pfft_parts = pfft_match.group(1)
    manifest_pfft = manifest.get(
        "partial_fft_parts", manifest_geometry_value("partial_fft_parts"))
    if manifest_pfft is not None and str(manifest_pfft) != pfft_parts:
        raise FileNotFoundError("partial-FFT setting disagrees")
    seed = manifest.get("seed", "unspecified")
    if (isinstance(seed, bool) or
            not isinstance(seed, (int, str))):
        raise FileNotFoundError("invalid effective-rate seed")
    configured_duration = manifest.get(
        "configured_frame_duration_seconds",
        manifest.get("frame_duration_budget_seconds", "unspecified"))
    if configured_duration != "unspecified":
        if (isinstance(configured_duration, bool) or
                not isinstance(configured_duration, (int, float)) or
                not math.isfinite(configured_duration) or
                configured_duration <= 0):
            raise FileNotFoundError("invalid configured frame duration")
        configured_duration = f"{configured_duration:g}"

    signature = (
        parameters["Capture / frames"],
        parameters["Receiver policy"],
        name_parameters["CP"],
        name_parameters["code rate"],
        name_parameters["check degree"],
        name_parameters["horizon"],
        pfft_parts,
        str(configured_duration),
        str(seed),
    )
    labels = metadata["parameter_labels"]
    summary = (
        f'{labels["Capture / frames"]} · '
        f'{labels["Receiver policy"]} · rate {name_parameters["code rate"]} '
        f'· pilots shown by group · CP {name_parameters["CP"]} '
        f'· dc {name_parameters["check degree"]} · '
        f'K {name_parameters["horizon"]} · PFFT {pfft_parts}'
    )
    return nfft, signature, summary


_BEST_OBSERVED_CONFIG_COLORS = (
    "#1971c2", "#e67700", "#2b8a3e", "#c2255c", "#6741d9",
    "#0b7285", "#d9480f", "#5f3dc4", "#087f5b", "#862e9c",
    "#364fc7", "#a61e4d",
)


def _best_observed_config_color(index):
    """Deterministic configuration color without a fixed family-size cap."""
    if index < len(_BEST_OBSERVED_CONFIG_COLORS):
        return _BEST_OBSERVED_CONFIG_COLORS[index]
    hue = (index * 137.508) % 360
    return f"hsl({hue:.1f} 65% 42%)"


# CL-155: the joint paper's presentation, mirrored back into this page.
_PAPER_RECEIVER_STYLE = {
    "ofdm_fec": ("OFDM+LDPC", "#2a78d6"),
    "pfft": ("Partial-FFT+LDPC", "#eb6834"),
    "lite": ("JUNA-Lite", "#1baf7a"),
    "profiled_cz": ("C,z", "#eda100"),
    "cwz_joint": ("C,W,z", "#e87ba4"),
}
_PAPER_VIRIDIS = ("#440154", "#46327e", "#365c8d", "#277f8e",
                  "#1fa187", "#4ac16d", "#a0da39", "#fde725")
_PAPER_N_SHAPES = {"512": "square", "1024": "circle", "1536": "diamond",
                   "2048": "triangle-up", "4096": "triangle-down"}


def _paper_marker_markup(shape, x, y, r, fill, stroke, extra=""):
    """One winning-N marker in the paper's shape convention."""
    if shape == "square":
        s = r * 1.7
        return (f'<rect class="winner-point" x="{x - s / 2:.2f}" '
                f'y="{y - s / 2:.2f}" width="{s:.2f}" height="{s:.2f}" '
                f'fill="{fill}" stroke="{stroke}" stroke-width="1.2">'
                f'{extra}</rect>')
    if shape == "diamond":
        pts = (f"{x:.2f},{y - r * 1.25:.2f} {x + r * 1.25:.2f},{y:.2f} "
               f"{x:.2f},{y + r * 1.25:.2f} {x - r * 1.25:.2f},{y:.2f}")
    elif shape == "triangle-down":
        pts = (f"{x - r * 1.2:.2f},{y - r:.2f} "
               f"{x + r * 1.2:.2f},{y - r:.2f} {x:.2f},{y + r * 1.2:.2f}")
    elif shape == "triangle-up":
        pts = (f"{x:.2f},{y - r * 1.2:.2f} {x + r * 1.2:.2f},{y + r:.2f} "
               f"{x - r * 1.2:.2f},{y + r:.2f}")
    else:
        return (f'<circle class="winner-point" cx="{x:.2f}" cy="{y:.2f}" '
                f'r="{r:.1f}" fill="{fill}" stroke="{stroke}" '
                f'stroke-width="1.2">{extra}</circle>')
    return (f'<polygon class="winner-point" points="{pts}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="1.2">{extra}</polygon>')


def _best_observed_all_scope_eligible(
        code_rate, combined_pilot_ratio, configured_duration):
    """Whether one tested configuration enters the broad winner scan."""
    try:
        rate = Fraction(code_rate)
        pilot_ratio = Fraction(combined_pilot_ratio)
        duration = (Fraction(1) if configured_duration == "unspecified"
                    else Fraction(configured_duration))
    except (TypeError, ValueError, ZeroDivisionError):
        raise FileNotFoundError("invalid best-observed eligibility value")
    return (rate != Fraction(1, 2) and
            pilot_ratio <= Fraction(1, 2) and
            duration == Fraction(1))


def _no_harm_effective_rate_family_choices(available, experiment_id):
    """One deterministic picker option for each strict comparison family."""
    families = {}
    selected_signature = None
    for candidate in available:
        try:
            _nfft, signature, summary = (
                _no_harm_effective_rate_configuration(candidate))
        except FileNotFoundError:
            continue
        family = families.setdefault(signature, {
            "summary": summary,
            "members": [],
        })
        family["members"].append(candidate)
        if candidate == experiment_id:
            selected_signature = signature
    if selected_signature is None:
        raise FileNotFoundError("selected effective-rate family is incomplete")
    choices = []
    for signature, family in families.items():
        members = tuple(sorted(family["members"]))
        selected = signature == selected_signature
        choices.append({
            "experiment_id": experiment_id if selected else members[0],
            "label": family["summary"],
            "size": len(members),
            "selected": selected,
        })
    return tuple(sorted(
        choices,
        key=lambda choice: (choice["label"], choice["experiment_id"]),
    ))


def _no_harm_effective_rate_family(experiment_id, scope="family"):
    """Load one strict family or every tested no-harm configuration."""
    if scope not in ("family", "all"):
        raise FileNotFoundError("invalid effective-rate comparison scope")
    _anchor_nfft, anchor_signature, summary = (
        _no_harm_effective_rate_configuration(experiment_id))
    groups = []
    identities = set()
    anchor_seen = False
    shared_snr_grid = None
    for candidate in _experiment_ids(awgn=True, no_harm=True):
        try:
            nfft, signature, candidate_summary = (
                _no_harm_effective_rate_configuration(candidate))
        except FileNotFoundError:
            if scope == "all":
                raise
            continue
        if scope == "family" and signature != anchor_signature:
            continue
        anchor_seen = anchor_seen or candidate == experiment_id
        name_parameters = _sweep_name_parameters(candidate)
        if name_parameters is None:
            raise FileNotFoundError("matching pilot geometry is incomplete")
        try:
            outer_spacing = int(name_parameters["outer spacing"])
            inner_spacing = int(name_parameters["inner spacing"])
        except (KeyError, TypeError, ValueError):
            raise FileNotFoundError("matching pilot geometry is invalid")
        if outer_spacing < 1 or inner_spacing < 1:
            raise FileNotFoundError("matching pilot geometry is invalid")
        group_key = nfft, outer_spacing, inner_spacing
        combined_pilot_ratio = (
            Fraction(1, outer_spacing) + Fraction(1, inner_spacing))
        try:
            code_rate = Fraction(name_parameters["code rate"])
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            raise FileNotFoundError("matching code rate is invalid")
        if (scope == "all" and
                not _best_observed_all_scope_eligible(
                    code_rate, combined_pilot_ratio, signature[7])):
            continue
        identity = signature, nfft, outer_spacing, inner_spacing
        if identity in identities:
            raise FileNotFoundError(
                "more than one result claims one complete configuration")
        identities.add(identity)
        observations = _no_harm_effective_rate_observations(candidate)
        candidate_snr_grid = tuple(observations)
        if shared_snr_grid is None:
            shared_snr_grid = candidate_snr_grid
        elif candidate_snr_grid != shared_snr_grid:
            raise FileNotFoundError(
                "matching configurations use different SNR grids")
        groups.append((group_key, {
            "experiment_id": candidate,
            "observations": observations,
            "combined_pilot_ratio": combined_pilot_ratio,
            "signature": signature,
            "family_summary": candidate_summary,
            "display_label": _experiment_display_label(
                candidate, no_harm=True),
            "broad_candidate_key": candidate if scope == "all" else None,
        }))
    if not groups or not anchor_seen or shared_snr_grid is None:
        raise FileNotFoundError("no matching effective-rate family")
    ordered = tuple(sorted(
        groups,
        key=lambda item: (
            item[0][0], item[1]["combined_pilot_ratio"],
            item[0][1], item[0][2], item[1]["signature"],
            item[1]["experiment_id"]),
    ))
    comparison_summary = (
        "Eligible configurations: frame budget = 1 s, pilot ≤ 50%, "
        "code rate ≠ 0.5"
        if scope == "all" else summary)
    return ordered, comparison_summary, shared_snr_grid


def _no_harm_effective_rate_n_groups(
        experiment_id, snr_db, channel, hydrophone, scope="family"):
    """Stored receiver rates for every unambiguous matching N."""
    family, summary, snr_grid = _no_harm_effective_rate_family(
        experiment_id, scope)
    if snr_db not in snr_grid:
        raise FileNotFoundError(
            "matching N does not contain the selected SNR")
    groups = []
    peak = 0.0
    for group_key, candidate in family:
        observations = candidate["observations"]
        rates = tuple(
            observations[snr_db][
                (channel, hydrophone, receiver_id)]["rate"]
            for receiver_id, _label, _color in _EFFECTIVE_RATE_RECEIVERS)
        groups.append((group_key, {
            "experiment_id": candidate["experiment_id"],
            "rates": rates,
            "combined_pilot_ratio": candidate["combined_pilot_ratio"],
            "display_label": candidate["display_label"],
            "family_summary": candidate["family_summary"],
        }))
        peak = max(
            peak,
            max(observation["rate"]
                for rows in observations.values()
                for observation in rows.values()),
        )
    y_max = max(500.0, math.ceil(peak / 500.0) * 500.0)
    return tuple(groups), summary, y_max


def _no_harm_effective_rate_by_n_query(query):
    """One declared anchor, exact stored SNR, and canonical RED/H path."""
    pairs = urllib.parse.parse_qsl(query or "", keep_blank_values=True)
    allowed = {"experiment", "snr_db", "path", "scope"}
    if any(key not in allowed for key, _value in pairs):
        raise FileNotFoundError("unknown across-N query value")
    values = {
        key: [value for pair_key, value in pairs if pair_key == key]
        for key in allowed
    }
    if (any(len(values[key]) != 1
            for key in ("experiment", "snr_db", "path")) or
            not _EXPERIMENT_ID_RE.fullmatch(values["experiment"][0])):
        raise FileNotFoundError("one across-N query value is required")
    path_match = re.fullmatch(r"red([1-4]):([1-3])", values["path"][0])
    if path_match is None:
        raise FileNotFoundError("invalid across-N channel/hydrophone")
    experiment_id = values["experiment"][0]
    rows_by_snr = _no_harm_effective_rate_data(experiment_id)
    snr_db = _no_harm_effective_rate_snr(
        values["snr_db"], tuple(rows_by_snr))
    channel = f"red{path_match.group(1)}"
    hydrophone = int(path_match.group(2))
    scope = _best_observed_scope(values["scope"], default="family")
    return experiment_id, snr_db, channel, hydrophone, scope


def _no_harm_effective_rate_by_n_slider(snr_grid, selected_snr):
    """SNR range control that reloads one across-N detail page."""
    if len(snr_grid) < 2:
        raise FileNotFoundError("effective-rate SNR grid is incomplete")
    step = snr_grid[1] - snr_grid[0]
    if (step <= 0 or any(
            not math.isclose(right - left, step, abs_tol=1e-12, rel_tol=0)
            for left, right in zip(snr_grid, snr_grid[1:]))):
        raise FileNotFoundError("effective-rate SNR grid is not uniform")
    minimum = f"{snr_grid[0]:g}"
    maximum = f"{snr_grid[-1]:g}"
    selected = f"{selected_snr:g}"
    return f'''<span id="effective-rate-by-n-snr-control"
data-default-snr="{selected}"
style="display:inline-flex;align-items:center;gap:.4rem;margin:.2rem 0 .7rem">
<label for="effective-rate-by-n-snr">SNR</label>
<input id="effective-rate-by-n-snr" type="range"
min="{minimum}" max="{maximum}" step="{step:g}" value="{selected}"
aria-label="SNR in dB" aria-valuetext="{selected} dB"
aria-describedby="effective-rate-by-n-snr-value">
<output id="effective-rate-by-n-snr-value" for="effective-rate-by-n-snr">{selected} dB</output></span>
<script>
window.addEventListener("DOMContentLoaded", function () {{
  var slider = document.getElementById("effective-rate-by-n-snr");
  var output = document.getElementById("effective-rate-by-n-snr-value");
  function updateLabel() {{
    var text = slider.value + " dB";
    output.value = text;
    slider.setAttribute("aria-valuetext", text);
  }}
  slider.addEventListener("input", updateLabel);
  slider.addEventListener("change", function () {{
    updateLabel();
    var url = new window.URL(window.location.href);
    url.searchParams.set("snr_db", slider.value);
    window.location.href = url;
  }});
}});
</script>'''


def _no_harm_effective_rate_view(experiment_id, snr_db=20.0):
    """Twelve stored effective-rate bar plots with one shared vertical scale."""
    rows_by_snr = _no_harm_effective_rate_data(experiment_id)
    if snr_db not in rows_by_snr:
        raise FileNotFoundError("effective-rate SNR is outside the stored grid")
    rows = rows_by_snr[snr_db]
    peak = max((rate for stored_rows in rows_by_snr.values()
                for rate in stored_rows.values()), default=0.0)
    y_max = max(500.0, math.ceil(peak / 500.0) * 500.0)
    plot_top, plot_bottom = 20.0, 174.0
    plot_height = plot_bottom - plot_top
    bar_width, bar_gap, first_x = 39.0, 7.0, 52.0

    panels = []
    for channel_number in range(1, 5):
        channel = f"red{channel_number}"
        for hydrophone in range(1, 4):
            detail_url = (
                "/no-harm-results/effective-rate/by-n?" +
                urllib.parse.urlencode([
                    ("experiment", experiment_id),
                    ("snr_db", f"{snr_db:g}"),
                    ("path", f"{channel}:{hydrophone}"),
                ]))
            bars = []
            for receiver_index, (receiver_id, label, color) in enumerate(
                    _EFFECTIVE_RATE_RECEIVERS):
                rate = rows[(channel, hydrophone, receiver_id)]
                height = rate / y_max * plot_height
                x = first_x + receiver_index * (bar_width + bar_gap)
                y = plot_bottom - height
                bars.append(
                    f'<rect class="receiver-bar" data-receiver="{receiver_id}" '
                    f'data-rate-bps="{rate:.1f}" x="{x:.1f}" y="{y:.2f}" '
                    f'width="{bar_width:.1f}" height="{height:.2f}" '
                    f'fill="{color}"><title>{esc(label)}: {rate:.1f} bps'
                    f'</title></rect>')
            midpoint = y_max / 2.0
            panels.append(
                f'<a class="rate-panel-link" href="{esc(detail_url)}" '
                f'target="_top" aria-label="{channel.upper()} H{hydrophone} '
                f'effective payload rate across N and pilot ratio at '
                f'{snr_db:g} dB">'
                f'<figure class="rate-panel" data-contract-path="{channel} '
                f'{hydrophone}"><figcaption><b>{channel.upper()}</b> · '
                f'H{hydrophone}</figcaption>'
                '<svg viewBox="0 0 300 205" role="img" '
                f'aria-label="{channel} hydrophone {hydrophone}, effective '
                f'payload rate at {snr_db:g} dB">'
                f'<line x1="44" y1="{plot_top:.1f}" x2="44" '
                f'y2="{plot_bottom:.1f}" class="axis"/>'
                f'<line x1="44" y1="{plot_bottom:.1f}" x2="292" '
                f'y2="{plot_bottom:.1f}" class="axis"/>'
                f'<line x1="44" y1="{plot_top:.1f}" x2="292" '
                f'y2="{plot_top:.1f}" class="grid"/>'
                f'<line x1="44" y1="{plot_top + plot_height / 2:.1f}" '
                f'x2="292" y2="{plot_top + plot_height / 2:.1f}" '
                'class="grid"/>'
                f'<text x="40" y="{plot_top + 4:.1f}" text-anchor="end">'
                f'{y_max:g}</text>'
                f'<text x="40" y="{plot_top + plot_height / 2 + 4:.1f}" '
                f'text-anchor="end">{midpoint:g}</text>'
                f'<text x="40" y="{plot_bottom + 4:.1f}" '
                'text-anchor="end">0</text>' + "".join(bars) +
                '</svg></figure></a>')

    legend = "".join(
        f'<span><i style="background:{color}"></i>{esc(label)}</span>'
        for _receiver_id, label, color in _EFFECTIVE_RATE_RECEIVERS)
    configuration = _experiment_display_label(experiment_id, no_harm=True)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Effective payload rate at {snr_db:g} dB</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#fff;color:#18212b;
font:14px system-ui,sans-serif}}main{{padding:12px}}h1{{font-size:21px;
margin:0 0 3px}}.configuration{{margin:0 0 8px;color:#4b5563}}
#effective-rate-legend{{display:flex;gap:14px;flex-wrap:wrap;margin:5px 0 10px}}
#effective-rate-legend span{{display:flex;align-items:center;gap:5px}}
#effective-rate-legend i{{display:inline-block;width:14px;height:10px}}
.rate-layout{{display:grid;grid-template-columns:24px 1fr;gap:5px}}
.y-label{{writing-mode:vertical-rl;transform:rotate(180deg);text-align:center;
font-weight:600;padding:8px 0}}
.rate-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}}
.rate-panel-link{{display:block;min-width:0;color:inherit;text-decoration:none;
border-radius:6px}}.rate-panel-link:hover .rate-panel,
.rate-panel-link:focus-visible .rate-panel{{border-color:#147d73;
box-shadow:0 0 0 2px rgba(20,125,115,.18)}}
.rate-panel{{margin:0;border:1px solid #d8dde3;border-radius:6px;padding:5px;
min-width:0;background:#fff}}.rate-panel figcaption{{font-size:13px;margin:0 0 2px}}
.rate-panel svg{{display:block;width:100%;height:auto}}
.axis{{stroke:#9aa3ad;stroke-width:1}}.grid{{stroke:#e7e9ed;stroke-width:1}}
.rate-panel text{{font-size:10px;fill:#4b5563}}
</style></head><body><main>
<h1>Effective payload rate at {snr_db:g} dB</h1>
<p class="configuration">{esc(configuration)}</p>
<div id="effective-rate-legend">{legend}</div>
<div class="rate-layout"><div class="y-label">Effective payload rate (bps)</div>
<div class="rate-grid" data-y-max="{y_max:g}">{''.join(panels)}</div></div>
</main></body></html>"""


def page_no_harm_effective_rate_by_n(query):
    """One RED/H path compared across selected stored configurations."""
    experiment_id, snr_db, channel, hydrophone, scope = (
        _no_harm_effective_rate_by_n_query(query))
    groups, configuration, y_max = _no_harm_effective_rate_n_groups(
        experiment_id, snr_db, channel, hydrophone, scope)
    snr_grid = tuple(_no_harm_effective_rate_data(experiment_id))
    snr_control = _no_harm_effective_rate_by_n_slider(snr_grid, snr_db)

    plot_left, plot_right = 62.0, 18.0
    plot_top, plot_bottom = 24.0, 252.0
    plot_height = plot_bottom - plot_top
    chart_width = max(560.0, 115.0 + 150.0 * len(groups))
    group_width = (chart_width - plot_left - plot_right) / len(groups)
    bar_gap = 4.0
    bar_width = min(
        30.0,
        (group_width - 24.0 - bar_gap * 4) /
        len(_EFFECTIVE_RATE_RECEIVERS),
    )
    group_markup = []
    for group_index, (group_key, group) in enumerate(groups):
        nfft, outer_spacing, inner_spacing = group_key
        combined_pilot_ratio = group["combined_pilot_ratio"]
        ratio_text = (
            f"{combined_pilot_ratio.numerator}/"
            f"{combined_pilot_ratio.denominator}")
        pilot_percent_text = _combined_pilot_percent_text(
            outer_spacing, inner_spacing)
        pilot_spacing = f"{outer_spacing}/{inner_spacing}"
        group_center = plot_left + group_width * (group_index + 0.5)
        bars_width = (bar_width * len(_EFFECTIVE_RATE_RECEIVERS) +
                      bar_gap * (len(_EFFECTIVE_RATE_RECEIVERS) - 1))
        first_x = group_center - bars_width / 2.0
        bars = []
        for receiver_index, ((receiver_id, label, color), rate) in enumerate(
                zip(_EFFECTIVE_RATE_RECEIVERS, group["rates"])):
            height = rate / y_max * plot_height
            x = first_x + receiver_index * (bar_width + bar_gap)
            y = plot_bottom - height
            bars.append(
                f'<rect class="grouped-receiver-bar" '
                f'data-receiver="{receiver_id}" '
                f'data-rate-bps="{rate:.1f}" x="{x:.2f}" y="{y:.2f}" '
                f'width="{bar_width:.2f}" height="{height:.2f}" '
                f'fill="{color}"><title>{esc(label)}: {rate:.1f} bps; '
                f'N={nfft}; pilots {pilot_spacing}; combined pilot ratio '
                f'{pilot_percent_text}%; result '
                f'{group_index + 1}</title></rect>')
            if rate == 0:
                center = x + bar_width / 2.0
                bars.append(
                    f'<rect class="zero-rate-marker" '
                    f'data-receiver="{receiver_id}" data-rate-bps="0.0" '
                    f'x="{x + 3:.2f}" y="{plot_bottom - 5:.1f}" '
                    f'width="{bar_width - 6:.2f}" height="4" rx="2" '
                    f'fill="{color}"><title>{esc(label)}: 0.0 bps; '
                    f'N={nfft}; pilots {pilot_spacing}; combined pilot ratio '
                    f'{pilot_percent_text}%; result '
                    f'{group_index + 1}</title></rect>'
                    f'<text class="zero-rate-label" x="{center:.2f}" '
                    f'y="{plot_bottom - 7:.1f}" text-anchor="middle">'
                    '0</text>')
        group_markup.append(
            f'<g class="n-group" data-nfft="{nfft}" '
            f'data-combined-pilot-ratio="{ratio_text}" '
            f'data-pilot-percent="{pilot_percent_text}" '
            f'data-pilot-spacing="{pilot_spacing}" '
            f'data-experiment-id="{esc(group["experiment_id"])}">'
            f'<title>{esc(group["display_label"])}; ordered pilot spacing '
            f'{pilot_spacing}; result {group_index + 1}</title>'
            + "".join(bars) +
            f'<text class="n-label" x="{group_center:.2f}" '
            f'y="{plot_bottom + 22:.1f}" text-anchor="middle">'
            f'<tspan x="{group_center:.2f}">N={nfft}</tspan>'
            f'<tspan x="{group_center:.2f}" dy="14">pilots '
            f'{pilot_percent_text}%</tspan>'
            + (f'<tspan class="group-family-label" '
               f'x="{group_center:.2f}" dy="14">result '
               f'{group_index + 1}</tspan>' if scope == "all" else "") +
            '</text></g>')

    legend = "".join(
        f'<span><i style="background:{color}"></i>{esc(label)}</span>'
        for _receiver_id, label, color in _EFFECTIVE_RATE_RECEIVERS)
    midpoint = y_max / 2.0
    back_query = [
        ("experiment", experiment_id),
        ("plot", "best-observed" if scope == "all" else "effective-rate"),
        ("snr_db", f"{snr_db:g}"),
    ]
    if scope == "all":
        back_query.append(("scope", "all"))
    back_url = "/no-harm-results?" + urllib.parse.urlencode(back_query)
    single_note = (
        '<p class="note">Only one matching N and pilot setting is currently '
        'available.</p>'
        if len(groups) == 1 else "")
    all_zero = all(
        rate == 0 for _nfft, group in groups for rate in group["rates"])
    zero_note = (
        f'<p class="note">All five stored effective payload rates are 0 bps '
        f'at {snr_db:g} dB for this path.</p>'
        if all_zero else "")
    heading = (
        f"{channel.upper()} · H{hydrophone} effective payload rate across "
        f"eligible configurations at {snr_db:g} dB" if scope == "all" else
        f"{channel.upper()} · H{hydrophone} effective payload rate across "
        f"N and pilot ratio at {snr_db:g} dB")
    scope_note = ("<p class=\"warning-note\">This view includes "
                  "configurations with different capture windows, frame "
                  "counts, receiver policies, and code rates. It reports "
                  "the largest stored effective "
                  "payload rate; it is not a controlled comparison.</p>"
                  if scope == "all" else "")
    body = f"""
<p><a class="button-link" href="{esc(back_url)}">Back to all paths</a></p>
<h1>{esc(heading)}</h1>
<p class="grouped-rate-configuration">{esc(configuration)}</p>
{scope_note}
<p class="grouped-rate-formula">Combined pilot ratio = 1 / outer spacing + 1 / inner spacing. Ordered pilot spacings remain separate.</p>
{snr_control}
{single_note}
{zero_note}
<div id="grouped-rate-legend">{legend}</div>
<div class="grouped-rate-chart">
<div class="grouped-rate-y-label">Effective payload rate (bps)</div>
<svg id="effective-rate-by-n" viewBox="0 0 {chart_width:.0f} 330"
role="img" aria-label="{esc(heading)}" data-y-max="{y_max:g}"
data-comparison-scope="{scope}">
<line x1="{plot_left:.1f}" y1="{plot_top:.1f}" x2="{plot_left:.1f}"
y2="{plot_bottom:.1f}" class="axis"/>
<line x1="{plot_left:.1f}" y1="{plot_bottom:.1f}"
x2="{chart_width - plot_right:.1f}" y2="{plot_bottom:.1f}" class="axis"/>
<line x1="{plot_left:.1f}" y1="{plot_top:.1f}"
x2="{chart_width - plot_right:.1f}" y2="{plot_top:.1f}" class="grid"/>
<line x1="{plot_left:.1f}" y1="{plot_top + plot_height / 2:.1f}"
x2="{chart_width - plot_right:.1f}"
y2="{plot_top + plot_height / 2:.1f}" class="grid"/>
<text x="{plot_left - 7:.1f}" y="{plot_top + 4:.1f}"
text-anchor="end">{y_max:g}</text>
<text x="{plot_left - 7:.1f}" y="{plot_top + plot_height / 2 + 4:.1f}"
text-anchor="end">{midpoint:g}</text>
<text x="{plot_left - 7:.1f}" y="{plot_bottom + 4:.1f}"
text-anchor="end">0</text>
{"".join(group_markup)}
<text class="x-label" x="{chart_width / 2:.1f}" y="324"
text-anchor="middle">{"Eligible configuration" if scope == "all" else "N and combined pilot ratio"}</text></svg></div>
<style>
.grouped-rate-configuration{{color:var(--muted);margin:.25rem 0 .6rem}}
.grouped-rate-formula{{color:var(--muted);margin:.25rem 0 .5rem}}
.warning-note{{background:#fff3bf;border:1px solid #ffe066;border-radius:6px;
padding:7px;margin:.5rem 0}}
#grouped-rate-legend{{display:flex;gap:14px;flex-wrap:wrap;margin:.4rem 0 .8rem}}
#grouped-rate-legend span{{display:flex;align-items:center;gap:5px}}
#grouped-rate-legend i{{display:inline-block;width:14px;height:10px}}
.grouped-rate-chart{{display:grid;grid-template-columns:28px minmax(0,1fr);
gap:5px;max-width:1000px}}
.grouped-rate-y-label{{writing-mode:vertical-rl;transform:rotate(180deg);
text-align:center;font-weight:600;padding:20px 0}}
#effective-rate-by-n{{display:block;width:100%;height:auto;background:#fff;
border:1px solid var(--line);border-radius:8px}}
#effective-rate-by-n .axis{{stroke:#9aa3ad;stroke-width:1}}
#effective-rate-by-n .grid{{stroke:#e7e9ed;stroke-width:1}}
#effective-rate-by-n text{{font-size:12px;fill:#4b5563}}
#effective-rate-by-n .n-label,#effective-rate-by-n .x-label{{font-weight:600;
fill:#18212b}}
#effective-rate-by-n .zero-rate-label{{font-size:10px;font-weight:600;
fill:#18212b}}
</style>"""
    return shell(heading, "/no-harm-results", body, wide=True)


def _best_observed_candidate_key(
        group_key, receiver_id, broad_candidate_key=None):
    """Stable identity for one configuration and receiver candidate."""
    if broad_candidate_key is not None:
        return f"{broad_candidate_key}:{receiver_id}"
    nfft, outer_spacing, inner_spacing = group_key
    return f"n{nfft}-p{outer_spacing}-{inner_spacing}-{receiver_id}"


def _best_observed_cell(family, snr_db, channel, hydrophone):
    """Ordered receiver winners, next distinct rate, and near ties."""
    candidates = []
    for config_index, (group_key, group) in enumerate(family):
        rows = group["observations"][snr_db]
        for receiver_index, (receiver_id, label, receiver_color) in enumerate(
                _EFFECTIVE_RATE_RECEIVERS):
            observation = rows[(channel, hydrophone, receiver_id)]
            successful_frames = observation["successful_frames"]
            quantum = (observation["rate"] / successful_frames
                       if successful_frames else None)
            candidates.append({
                "config_index": config_index,
                "group_key": group_key,
                "experiment_id": group["experiment_id"],
                "receiver_id": receiver_id,
                "receiver_label": label,
                "receiver_color": receiver_color,
                "rate": observation["rate"],
                "quantum": quantum,
                "key": _best_observed_candidate_key(
                    group_key, receiver_id,
                    group.get("broad_candidate_key")),
                "configuration_label": group.get(
                    "display_label",
                    f"N={group_key[0]} · pilots="
                    f"{_combined_pilot_percent_text(group_key[1], group_key[2])}%"),
            })
    peak = max(candidate["rate"] for candidate in candidates)
    if peak == 0:
        return {
            "peak": 0.0, "winners": (), "near_ties": (),
            "runner_up": None, "margin": None, "outage": True,
        }
    exact_rate_winners = tuple(
        candidate for candidate in candidates
        if math.isclose(candidate["rate"], peak,
                        rel_tol=1e-12, abs_tol=1e-9))
    tied_receivers = tuple(
        receiver_id for receiver_id, _label, _color
        in _EFFECTIVE_RATE_RECEIVERS
        if any(candidate["receiver_id"] == receiver_id
               for candidate in exact_rate_winners))
    selected_receiver = tied_receivers[0]
    winners = tuple(
        candidate for candidate in exact_rate_winners
        if candidate["receiver_id"] == selected_receiver)
    remaining = tuple(candidate for candidate in candidates
                      if candidate not in exact_rate_winners)
    runner_up = max((candidate["rate"] for candidate in remaining),
                    default=None)
    margin = peak - runner_up if runner_up is not None else None
    winner_quantum = max(
        (candidate["quantum"] or 0.0
         for candidate in exact_rate_winners), default=0.0)
    near_ties = []
    for candidate in remaining:
        gap = peak - candidate["rate"]
        threshold = max(winner_quantum, candidate["quantum"] or 0.0)
        if gap > 0 and threshold > 0 and gap <= threshold + 1e-9:
            near_ties.append(candidate)
    return {
        "peak": peak,
        "winners": winners,
        "rate_tied_receivers": tied_receivers,
        "selected_receiver": selected_receiver,
        "near_ties": tuple(near_ties),
        "runner_up": runner_up,
        "margin": margin,
        "outage": False,
    }


def _best_observed_runs(cells):
    """Adjacent tested SNRs with identical winner and near-tie sets."""
    runs = []
    for snr_db, cell in cells:
        identity = (
            cell["outage"],
            tuple(candidate["key"] for candidate in cell["winners"]),
            tuple(candidate["key"] for candidate in cell["near_ties"]),
        )
        if runs and runs[-1]["identity"] == identity:
            runs[-1]["stop"] = snr_db
            runs[-1]["snrs"].append(snr_db)
        else:
            runs.append({
                "start": snr_db,
                "stop": snr_db,
                "snrs": [snr_db],
                "identity": identity,
                "cell": cell,
            })
    return tuple(runs)


def _best_observed_provenance_identity(experiment_id):
    """Comparable source/project/harness digests, or None if incomplete."""
    source_contract = _experiment_manifest(experiment_id).get(
        "source_contract")
    if not isinstance(source_contract, dict):
        return None
    receiver_source = source_contract.get("receiver_source")
    schedule = source_contract.get("schedule_provenance")
    if not isinstance(receiver_source, dict) or not isinstance(schedule, dict):
        return None
    base_commit = receiver_source.get("base_commit")
    source_diff = receiver_source.get("tracked_source_diff_sha256")
    changed_sources = receiver_source.get("changed_source_sha256")
    project_digest = source_contract.get("active_project_sha256")
    manifest_digest = source_contract.get("active_manifest_sha256")
    sweep_digest = schedule.get("source_sweep_sha256")
    if (not isinstance(base_commit, str) or
            re.fullmatch(r"[0-9a-fA-F]{40}", base_commit) is None or
            any(not isinstance(value, str) or
                re.fullmatch(r"[0-9a-fA-F]{64}", value) is None
                for value in (source_diff, project_digest, manifest_digest,
                              sweep_digest)) or
            not isinstance(changed_sources, dict) or not changed_sources or
            any(not isinstance(value, str) or
                re.fullmatch(r"[0-9a-fA-F]{64}", value) is None
                for value in changed_sources.values())):
        return None
    return (
        base_commit.casefold(), source_diff.casefold(),
        tuple(sorted((str(path), digest.casefold())
                     for path, digest in changed_sources.items())),
        project_digest.casefold(), manifest_digest.casefold(),
        sweep_digest.casefold(),
    )


def _best_observed_snr_slider(snr_grid, selected_snr):
    """SNR focus control for the full-grid best-observed figure."""
    if len(snr_grid) < 2:
        raise FileNotFoundError("best-observed SNR grid is incomplete")
    step = snr_grid[1] - snr_grid[0]
    if (step <= 0 or any(
            not math.isclose(right - left, step, abs_tol=1e-12, rel_tol=0)
            for left, right in zip(snr_grid, snr_grid[1:]))):
        raise FileNotFoundError("best-observed SNR grid is not uniform")
    selected = f"{selected_snr:g}"
    return f'''<span id="best-observed-snr-control"
style="display:inline-flex;align-items:center;gap:.4rem;margin:.15rem 0 .6rem">
<label for="best-observed-snr">SNR focus</label>
<input id="best-observed-snr" type="range" min="{snr_grid[0]:g}" max="{snr_grid[-1]:g}" step="{step:g}" value="{selected}"
aria-label="Focused SNR in dB" aria-valuetext="{selected} dB"
aria-describedby="best-observed-snr-value">
<output id="best-observed-snr-value" for="best-observed-snr">{selected} dB</output>
</span>
<script>
window.addEventListener("DOMContentLoaded", function () {{
  var slider = document.getElementById("best-observed-snr");
  var output = document.getElementById("best-observed-snr-value");
  function updateLabel() {{
    var text = slider.value + " dB";
    output.value = text;
    slider.setAttribute("aria-valuetext", text);
  }}
  slider.addEventListener("input", updateLabel);
  slider.addEventListener("change", function () {{
    updateLabel();
    var url = new window.URL(window.location.href);
    url.searchParams.set("snr_db", slider.value);
    window.location.href = url;
  }});
}});
</script>'''


def page_no_harm_effective_rate_best(query):
    """Twelve maximum-rate envelopes for one family or every tested result."""
    experiment_id, selected_snr, scope, embedded = (
        _no_harm_effective_rate_best_query(query))
    family, configuration, snr_grid = _no_harm_effective_rate_family(
        experiment_id, scope)
    if selected_snr not in snr_grid:
        raise FileNotFoundError("best-observed SNR is outside the stored grid")
    candidate_count = len(family) * len(_EFFECTIVE_RATE_RECEIVERS)
    all_cells = {}
    peak = 0.0
    for channel_number in range(1, 5):
        channel = f"red{channel_number}"
        for hydrophone in range(1, 4):
            path_cells = []
            for snr_db in snr_grid:
                cell = _best_observed_cell(
                    family, snr_db, channel, hydrophone)
                peak = max(peak, cell["peak"])
                path_cells.append((snr_db, cell))
            all_cells[(channel, hydrophone)] = tuple(path_cells)
    y_max = max(500.0, math.ceil(peak / 500.0) * 500.0)

    # CL-155: discrete paper-style identities computed over the whole page.
    winning_indexes = sorted({
        candidate["config_index"]
        for cells in all_cells.values()
        for _snr, cell in cells
        for candidate in cell["winners"]})

    def _config_geometry_label(index):
        nfft, outer_spacing, inner_spacing = family[index][0]
        percent = _combined_pilot_percent_text(outer_spacing, inner_spacing)
        return f"N={nfft} · {percent}%"

    def _config_density_key(index):
        nfft, outer_spacing, inner_spacing = family[index][0]
        return (Fraction(1, int(outer_spacing)) +
                Fraction(1, int(inner_spacing)), int(nfft))

    # One discrete color per winning GEOMETRY (N and combined pilot
    # percent), the paper's configuration identity; experiments sharing a
    # geometry share a ribbon color.
    label_order = []
    label_key = {}
    for index in sorted(winning_indexes, key=_config_density_key):
        label = _config_geometry_label(index)
        if label not in label_key:
            label_key[label] = _config_density_key(index)
            label_order.append(label)
    if len(label_order) <= 1:
        viridis_picks = [0] * len(label_order)
    else:
        viridis_picks = [
            round(i * (len(_PAPER_VIRIDIS) - 1) / (len(label_order) - 1))
            for i in range(len(label_order))]
    label_color = {label: _PAPER_VIRIDIS[pick]
                   for label, pick in zip(label_order, viridis_picks)}
    config_color = {index: label_color[_config_geometry_label(index)]
                    for index in winning_indexes}
    seen_tie_sets = []
    seen_shapes = set()
    for cells in all_cells.values():
        for _snr, cell in cells:
            if cell["outage"]:
                continue
            tied = tuple(cell["rate_tied_receivers"])
            if tied not in seen_tie_sets:
                seen_tie_sets.append(tied)
            seen_shapes.add(str(cell["winners"][0]["group_key"][0]))

    plot_left, plot_right = 38.0, 8.0
    plot_top, plot_bottom = 14.0, 158.0
    ribbon_top, ribbon_height = 174.0, 18.0
    plot_width = 360.0 - plot_left - plot_right
    plot_height = plot_bottom - plot_top
    cell_width = plot_width / len(snr_grid)
    receiver_display = {
        receiver_id: (label, color) for receiver_id, label, color
        in _EFFECTIVE_RATE_RECEIVERS
    }
    panels = []
    for channel_number in range(1, 5):
        channel = f"red{channel_number}"
        for hydrophone in range(1, 4):
            path = f"{channel}:{hydrophone}"
            cells = all_cells[(channel, hydrophone)]
            envelope_points = []
            cell_markup = []
            focused_cell = None
            for snr_index, (snr_db, cell) in enumerate(cells):
                x = plot_left + cell_width * (snr_index + 0.5)
                y = plot_bottom - cell["peak"] / y_max * plot_height
                if snr_db == selected_snr:
                    focused_cell = cell
                winner_algorithms = cell.get("selected_receiver") or ""
                winner_keys = ",".join(
                    candidate["key"] for candidate in cell["winners"])
                winner_experiment_ids = ",".join(dict.fromkeys(
                    candidate["experiment_id"]
                    for candidate in cell["winners"]))
                near_keys = ",".join(
                    candidate["key"] for candidate in cell["near_ties"])
                if cell["outage"]:
                    point_color = "#8a887f"
                    cross_x = plot_left + cell_width * (snr_index + 0.5)
                    cross_y = ribbon_top + ribbon_height / 2
                    ribbon_markup = (
                        f'<rect class="winner-ribbon-cell '
                        f'winner-ribbon-outage" '
                        f'x="{plot_left + cell_width * snr_index:.2f}" '
                        f'y="{ribbon_top:.2f}" width="{cell_width:.2f}" '
                        f'height="{ribbon_height:.2f}" fill="#f4f4f2"/>'
                        f'<line x1="{cross_x - 3.2:.2f}" '
                        f'y1="{cross_y - 3.2:.2f}" x2="{cross_x + 3.2:.2f}" '
                        f'y2="{cross_y + 3.2:.2f}" stroke="#8a887f" '
                        'stroke-width="1.2"/>'
                        f'<line x1="{cross_x - 3.2:.2f}" '
                        f'y1="{cross_y + 3.2:.2f}" x2="{cross_x + 3.2:.2f}" '
                        f'y2="{cross_y - 3.2:.2f}" stroke="#8a887f" '
                        'stroke-width="1.2"/>')
                    title = (f"{snr_db:g} dB: 0 bps; outage; none of "
                             f"{candidate_count} choices delivered positive "
                             "payload")
                else:
                    config_indexes = sorted({
                        candidate["config_index"]
                        for candidate in cell["winners"]})
                    stripe_width = cell_width / len(config_indexes)
                    ribbon_markup = "".join(
                        f'<rect class="winner-ribbon-cell '
                        f'winner-ribbon-stripe" data-config-index="{index}" '
                        f'x="{plot_left + cell_width * snr_index + stripe_width * stripe_index:.2f}" '
                        f'y="{ribbon_top:.2f}" width="{stripe_width:.2f}" '
                        f'height="{ribbon_height:.2f}" '
                        f'fill="{config_color.get(index, "#d8dde3")}" '
                        'stroke="#fff" stroke-width="0.4"/>'
                        for stripe_index, index in enumerate(config_indexes))
                    tied = tuple(cell["rate_tied_receivers"])
                    tie_label = " = ".join(
                        _PAPER_RECEIVER_STYLE[r][0] for r in tied)
                    point_color = _PAPER_RECEIVER_STYLE[tied[0]][1]
                    point_hollow = len(tied) == 1
                    selected_label = tie_label
                    tied_receiver_count = len(cell["rate_tied_receivers"])
                    winner_text = "; ".join(
                        (f'{candidate["configuration_label"]}, '
                         f'{candidate["receiver_label"]}' if scope == "all"
                         else f'N={candidate["group_key"][0]}, pilots '
                         f'{candidate["group_key"][1]}/'
                         f'{candidate["group_key"][2]}, '
                         f'{candidate["receiver_label"]}')
                        for candidate in cell["winners"])
                    receiver_choice_text = (
                        f"best receivers {tie_label}"
                        if tied_receiver_count > 1 else
                        f"{tie_label} holds the maximum alone")
                    margin_text = ("no distinct runner-up" if
                                   cell["margin"] is None else
                                   f'observed lead {cell["margin"]:.1f} bps')
                    near_text = ("none" if not cell["near_ties"] else
                                 "; ".join(
                                     f'{candidate["configuration_label"]}, '
                                     f'{candidate["receiver_label"]}'
                                     for candidate in cell["near_ties"]))
                    title = (f"{snr_db:g} dB: {cell['peak']:.1f} bps; "
                             f"{winner_text}; {receiver_choice_text}; "
                             f"{margin_text}; near ties: {near_text}")
                if not cell["outage"]:
                    envelope_points.append((x, y))
                detail_url = (
                    "/no-harm-results/effective-rate/by-n?" +
                    urllib.parse.urlencode([
                        ("experiment", experiment_id),
                        ("snr_db", f"{snr_db:g}"),
                        ("path", path),
                        ("scope", scope),
                    ]))
                winner_count = len(cell["winners"])
                winner_results = ", ".join(
                    str(index + 1) for index in sorted({
                        candidate["config_index"]
                        for candidate in cell["winners"]
                    })) or "none"
                aria = (f"{channel.upper()} H{hydrophone}, {snr_db:g} dB, "
                        f"{cell['peak']:.1f} bps, "
                        f"{winner_count} winning configuration"
                        f"{'s' if winner_count != 1 else ''}, "
                        f"winning results {winner_results}, "
                        f"selected receiver "
                        f"{receiver_display[cell['selected_receiver']][0] if not cell['outage'] else 'none'}, "
                        f"{len(cell['near_ties'])} near ties; open all "
                        "configuration bars")
                cell_markup.append(
                    f'<a class="winner-cell-link" href="{esc(detail_url)}" '
                    f'target="_top" aria-label="{esc(aria)}">'
                    f'<g class="winner-cell" data-path="{path}" '
                    f'data-snr-db="{snr_db:g}" '
                    f'data-outage="{str(cell["outage"]).lower()}" '
                    f'data-winner-count="{len(cell["winners"])}" '
                    f'data-rate-tied-receiver-count="{len(cell.get("rate_tied_receivers", ()))}" '
                    f'data-selected-receiver="{cell.get("selected_receiver") or ""}" '
                    f'data-near-tie-count="{len(cell["near_ties"])}" '
                    f'data-winner-algorithms="{winner_algorithms}" '
                    f'data-winner-keys="{winner_keys}" '
                    f'data-winner-experiment-ids="{winner_experiment_ids}" '
                    f'data-near-tie-keys="{near_keys}">'
                    + ribbon_markup +
                    ("" if cell["outage"] else _paper_marker_markup(
                        _PAPER_N_SHAPES.get(
                            str(cell["winners"][0]["group_key"][0]),
                            "circle"),
                        x, y, 4.6 if snr_db == selected_snr else 3.4,
                        "#fff" if point_hollow else point_color,
                        point_color,
                        f'<title>{esc(title)}</title>'))
                    + (f'<circle class="near-tie-ring" cx="{x:.2f}" '
                       f'cy="{y:.2f}" r="6.6" fill="none" stroke="#495057" '
                       'stroke-width="1" stroke-dasharray="2 2"/>'
                       if cell["near_ties"] else "") +
                    '</g></a>')
            if focused_cell is None:
                raise FileNotFoundError("focused SNR is missing")
            focus_index = snr_grid.index(selected_snr)
            focus_x = plot_left + cell_width * (focus_index + 0.5)
            if focused_cell["outage"]:
                summary = "0.0 bps · outage"
            else:
                focused_winners = focused_cell["winners"]
                receiver_summary = " = ".join(
                    _PAPER_RECEIVER_STYLE[r][0]
                    for r in focused_cell["rate_tied_receivers"])
                if len(focused_winners) == 1:
                    focused_group = focused_winners[0]["group_key"]
                    configuration_summary = (
                        f"N={focused_group[0]} · pilot="
                        f"{_combined_pilot_percent_text(focused_group[1], focused_group[2])}%")
                else:
                    configuration_summary = (
                        f"{len(focused_winners)} configurations")
                summary = (f'{focused_cell["peak"]:.1f} bps · '
                           f'{configuration_summary} · {receiver_summary}')
            envelope_markup = (
                '<polyline class="winner-envelope" fill="none" '
                'stroke="#b9b7af" stroke-width="1.2" points="'
                + " ".join(f"{px:.2f},{py:.2f}"
                           for px, py in envelope_points)
                + '"/>') if envelope_points else ""
            title_id = f"best-rate-title-{channel}-{hydrophone}"
            desc_id = f"best-rate-desc-{channel}-{hydrophone}"
            panels.append(
                f'<figure class="winner-panel" data-path="{path}">'
                f'<figcaption><b>{channel.upper()}</b> · H{hydrophone} '
                f'<span>{selected_snr:g} dB: {esc(summary)}</span></figcaption>'
                f'<svg viewBox="0 0 360 218" role="img" '
                f'aria-labelledby="{title_id} {desc_id}" '
                f'data-y-max="{y_max:g}" data-focused-snr="{selected_snr:g}">'
                f'<title id="{title_id}">{channel.upper()} H{hydrophone} '
                'best observed effective payload rate</title>'
                f'<desc id="{desc_id}">Maximum stored rate at every tested '
                'SNR; marker color names the receivers sharing the maximum, '
                'joined with equals, hollow when one receiver holds it '
                'alone; marker shape names the winning N; the ribbon names '
                'the winning configuration.</desc>'
                f'<line class="axis" x1="{plot_left}" y1="{plot_top}" '
                f'x2="{plot_left}" y2="{plot_bottom}"/>'
                f'<line class="axis" x1="{plot_left}" y1="{plot_bottom}" '
                'x2="352" y2="158"/>'
                f'<line class="grid" x1="{plot_left}" y1="{plot_top}" '
                'x2="352" y2="14"/>'
                f'<line class="grid" x1="{plot_left}" '
                f'y1="{plot_top + plot_height / 2}" x2="352" '
                f'y2="{plot_top + plot_height / 2}"/>'
                f'<text x="34" y="18" text-anchor="end">{y_max:g}</text>'
                f'<text x="34" y="162" text-anchor="end">0</text>'
                + envelope_markup +
                f'<line class="winner-focus" data-snr-db="{selected_snr:g}" '
                f'x1="{focus_x:.2f}" y1="{plot_top}" x2="{focus_x:.2f}" '
                f'y2="{ribbon_top + ribbon_height}"/>'
                + "".join(cell_markup) +
                f'<text x="{plot_left}" y="211">{snr_grid[0]:g}</text>'
                f'<text x="352" y="211" text-anchor="end">'
                f'{snr_grid[-1]:g} dB</text></svg></figure>')
    config_rows = []
    for index, (group_key, group) in enumerate(family):
        nfft, outer_spacing, inner_spacing = group_key
        code_rate = group["signature"][3]
        pilot_spacing = f"{outer_spacing}/{inner_spacing}"
        pilot_percent = _combined_pilot_percent_text(
            outer_spacing, inner_spacing)
        config_rows.append(
            '<tr class="winner-config-table-row" '
            f'data-nfft="{nfft}" data-code-rate="{esc(code_rate)}" '
            f'data-pilot-percent="{pilot_percent}" '
            f'data-pilot-spacing="{pilot_spacing}" '
            f'data-config-index="{index}" '
            f'data-experiment-id="{esc(group["experiment_id"])}" '
            f'><td>{nfft}</td><td>{esc(code_rate)}</td>'
            f'<td><span title="Ordered pilot spacing {pilot_spacing}">'
            f'{pilot_percent}%</span><span class="visually-hidden">; '
            f'ordered pilot spacing {pilot_spacing}</span></td>'
            '<th scope="row" class="winner-config-table-result" '
            f'data-experiment-id="{esc(group["experiment_id"])}" '
            f'data-config-index="{index}">'
            '<i class="winner-config-swatch" '
            f'style="background:{config_color.get(index, "#d8dde3")}" '
            f'aria-hidden="true"></i>Result {index + 1}</th></tr>')
    config_table = (
        '<table id="best-config-table" class="winner-config-table">'
        '<caption>Configurations</caption><thead><tr>'
        '<th scope="col">N</th><th scope="col">Rate</th>'
        '<th scope="col">Pilot</th><th scope="col">Result</th>'
        '</tr></thead><tbody>' + "".join(config_rows) + '</tbody></table>')
    tie_rank = {receiver_id: rank for rank, (receiver_id, _label, _color)
                in enumerate(_EFFECTIVE_RATE_RECEIVERS)}
    seen_tie_sets.sort(key=lambda tied: (tie_rank[tied[0]], -len(tied)))
    receiver_legend = "".join(
        '<span><i style="background:'
        + ("#fff" if len(tied) == 1 else _PAPER_RECEIVER_STYLE[tied[0]][1])
        + f';border:2px solid {_PAPER_RECEIVER_STYLE[tied[0]][1]};'
        'border-radius:50%;width:10px;height:10px"></i>'
        + esc(" = ".join(_PAPER_RECEIVER_STYLE[r][0] for r in tied))
        + '</span>'
        for tied in seen_tie_sets)
    shape_glyph = {"circle": "●", "triangle-up": "▲", "triangle-down": "▼",
                   "square": "■", "diamond": "◆"}
    shape_legend = "".join(
        f'<span style="color:#6f6d66">'
        f'{shape_glyph[_PAPER_N_SHAPES.get(n, "circle")]} N={esc(n)}</span>'
        for n in sorted(seen_shapes, key=int)) + (
        '<span style="color:#8a887f">✕ no recovered frame</span>')
    config_bar = "".join(
        f'<span><i style="background:{label_color[label]}"></i>'
        f'{esc(label)}</span>'
        for label in label_order)
    provenance_identities = tuple(
        _best_observed_provenance_identity(group["experiment_id"])
        for _group_key, group in family)
    provenance_recorded = all(
        identity is not None for identity in provenance_identities)
    if (scope == "family" and provenance_recorded and
            len(set(provenance_identities)) != 1):
        raise FileNotFoundError(
            "matching configurations have different source provenance")
    family_count = len({group["signature"] for _key, group in family})
    grid_text = " ".join(f"{snr_db:g}" for snr_db in snr_grid)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Best observed effective payload rate</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#fff;color:#18212b;
font:14px system-ui,sans-serif}}main{{padding:12px}}h1{{font-size:21px;
margin:0 0 3px}}.configuration{{color:#4b5563;margin:.25rem 0}}
.best-observed-grid{{display:grid;
grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}}
.winner-panel{{margin:0;border:1px solid #d8dde3;border-radius:6px;padding:5px;
min-width:0;background:#fff}}.winner-panel figcaption{{display:flex;
justify-content:space-between;gap:5px;font-size:12px;margin-bottom:2px}}
.winner-panel figcaption span{{color:#4b5563;font-size:10px}}
.winner-panel svg{{display:block;width:100%;height:auto}}
.winner-panel text{{font-size:9px;fill:#4b5563}}.axis{{stroke:#9aa3ad}}
.grid{{stroke:#e7e9ed}}.winner-focus{{stroke:#e03131;stroke-width:1.2}}
.winner-cell-link:focus .winner-ribbon-cell{{stroke:#111;stroke-width:2}}
.legend-row{{display:flex;gap:12px;flex-wrap:wrap;margin:.3rem 0 .35rem}}
.legend-row span{{display:flex;align-items:center;gap:4px;font-size:12px}}
.legend-row i{{display:inline-block;width:13px;height:9px}}
.legend-row b{{font-size:12px}}#best-config-bar i{{width:20px;height:11px}}
.winner-config-table{{border-collapse:collapse;margin:.35rem 0 .6rem;
font-size:12px;min-width:330px}}
.winner-config-table caption{{font-weight:600;text-align:left;margin-bottom:3px}}
.winner-config-table th,.winner-config-table td{{border:1px solid #d8dde3;
padding:3px 7px;text-align:left;white-space:nowrap}}
.winner-config-table thead th{{background:#f5f6f8}}
.winner-config-swatch{{display:inline-block;width:13px;height:9px;
margin-right:5px}}
#best-configurations{{margin:.7rem 0}}
#best-configurations>summary{{cursor:pointer;font-weight:600}}
.visually-hidden{{position:absolute!important;width:1px!important;
height:1px!important;padding:0!important;margin:-1px!important;
overflow:hidden!important;clip:rect(0,0,0,0)!important;
white-space:nowrap!important;border:0!important}}
</style></head><body><main id="best-observed-rate-view"
data-anchor-experiment="{esc(experiment_id)}" data-family-size="{len(family)}"
data-comparison-scope="{scope}" data-family-count="{family_count}"
data-configuration-count="{len(family)}"
data-candidate-count="{candidate_count}" data-focused-snr="{selected_snr:g}"
data-snr-grid="{grid_text}" data-y-max="{y_max:g}"
data-receiver-tie-order="ofdm_fec pfft lite profiled_cz cwz_joint">
<h1>Best observed effective payload rate</h1>
<p class="configuration">{esc(configuration)}</p>
{'' if embedded else _best_observed_snr_slider(snr_grid, selected_snr)}
<div class="legend-row" id="best-receiver-legend">
<b>best receivers (ties joined with =):</b>{receiver_legend}</div>
<div class="legend-row" id="best-shape-legend">{shape_legend}</div>
<div class="legend-row" id="best-config-bar">
<b>winning configuration (ribbon color):</b>{config_bar}</div>
<div class="best-observed-grid">{''.join(panels)}</div>
<details id="best-configurations">
<summary>Configurations ({len(family)})</summary>{config_table}</details>
</main></body></html>"""


def _no_harm_channel_hydrophone_grid(document):
    """Order three hydrophones across and four channels down."""
    matches = list(_RESULT_PANEL_RE.finditer(document))
    if len(matches) != 12:
        return document
    panels = {}
    hydrophones = set()
    for match in matches:
        panel = match.group(0)
        caption = re.search(
            r'<figcaption\b[^>]*>\s*<b\b[^>]*>(.*?)</b>', panel,
            re.IGNORECASE | re.DOTALL)
        if not caption:
            return document
        title = html.unescape(
            re.sub(r"<[^>]+>", "", caption.group(1))).strip()
        key_match = re.fullmatch(
            r"([A-Za-z0-9._-]+) hydrophone ([1-9][0-9]*)(?:\s+—.*)?",
            title)
        if not key_match:
            return document
        channel, hydrophone_text = key_match.groups()
        hydrophone = int(hydrophone_text)
        key = channel, hydrophone
        if key in panels:
            return document
        panels[key] = panel
        hydrophones.add(hydrophone)
    channels = [f"red{channel}" for channel in range(1, 5)]
    ordered_hydrophones = sorted(hydrophones)
    wanted = [(channel, hydrophone)
              for channel in channels
              for hydrophone in ordered_hydrophones]
    if (len(ordered_hydrophones) != 3 or set(wanted) != set(panels)):
        return document
    ordered = iter(panels[key] for key in wanted)
    return _RESULT_PANEL_RE.sub(lambda _match: next(ordered), document)


def _no_harm_compact_four_view(document):
    """Add an iframe-only compact matrix without changing result files."""
    document = _no_harm_channel_hydrophone_grid(document)
    if 'id="no-harm-compact-four"' in document:
        return document
    lowered = document.lower()
    head_end = lowered.find("</head>")
    if head_end >= 0:
        return (document[:head_end] + _NO_HARM_COMPACT_FOUR_STYLE +
                document[head_end:])
    style_end = lowered.find("</style>")
    if style_end >= 0:
        style_end += len("</style>")
        return (document[:style_end] + _NO_HARM_COMPACT_FOUR_STYLE +
                document[style_end:])
    return _NO_HARM_COMPACT_FOUR_STYLE + document


def _default_results_presentation(document):
    """Hide the now-default selection policy in generated reader prose."""
    return document.replace(
        "CRC-gated no-harm implementation", "CRC-gated implementation"
    ).replace(
        "CRC no-harm implementation", "CRC implementation"
    )


def _result_panel(document, channel, hydrophone):
    """Extract one generated BER-SNR figure by its reader-facing caption."""
    wanted = f"{channel} hydrophone {hydrophone}"
    for panel in _RESULT_PANEL_RE.findall(document):
        caption = re.search(
            r'<figcaption\b[^>]*>\s*<b\b[^>]*>(.*?)</b>', panel,
            re.IGNORECASE | re.DOTALL)
        if not caption:
            continue
        title = html.unescape(re.sub(r"<[^>]+>", "", caption.group(1))).strip()
        if title == wanted or title.startswith(wanted + " —"):
            return panel
    return None


def page_results_comparison(query, awgn=False, no_harm=False):
    """One selected BER-SNR panel from each same-family experiment."""
    experiment_ids, channel, hydrophone = _results_comparison_query(
        query, awgn=awgn, no_harm=no_harm)
    cards, plot_style, legend = [], "", ""
    for result_index, experiment_id in enumerate(experiment_ids, start=1):
        result = _family_result_file(experiment_id, "results_view.html",
                                     awgn=awgn, no_harm=no_harm)
        with open(result, encoding="utf-8") as handle:
            document = handle.read()
        panel = _result_panel(document, channel, hydrophone)
        if panel is None:
            continue
        if not plot_style:
            style = re.search(r"<style\b[^>]*>(.*?)</style>", document,
                              re.IGNORECASE | re.DOTALL)
            plot_style = style.group(1) if style else ""
        if not legend:
            block = re.search(r'<div\b[^>]*class="[^"]*\blegend\b[^"]*"[^>]*>'
                              r'.*?</div>', document,
                              re.IGNORECASE | re.DOTALL)
            legend = block.group(0) if block else ""
        cards.append(
            f'<article class="experiment-result" '
            f'data-experiment-id="{esc(experiment_id)}" '
            f'data-channel="{esc(channel)}" '
            f'data-hydrophone="{hydrophone}">'
            f'<h2 title="{esc(_experiment_display_label(experiment_id, no_harm))}; '
            f'result {result_index}">'
            f'{esc(_experiment_display_label(experiment_id, no_harm))}'
            f'</h2>{panel}</article>')
    if not cards:
        raise FileNotFoundError("no matching BER-SNR panels")
    label = f"{channel} hydrophone {hydrophone}"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(label)} across experiments</title>
<style>{plot_style}
.comparison-grid {{ display:grid;gap:12px;
  grid-template-columns:repeat(auto-fill,minmax(320px,1fr)); }}
.experiment-result {{ min-width:0; }}
.experiment-result h2 {{ font:600 12px/1.35 system-ui,sans-serif;
  overflow-wrap:anywhere;margin:0 0 5px;color:var(--text-secondary); }}
.experiment-result .panel {{ height:calc(100% - 22px); }}
</style></head><body><div class="viz-root">
<h1>{"" if no_harm else ("AWGN — " if awgn else "")}{esc(label)}: BER versus added-noise SNR across experiments</h1>
<p class="axis-title">{len(cards)} plots from {len(experiment_ids)} matching
experiments.</p>
{legend}
<div class="comparison-grid">{"".join(cards)}</div>
</div></body></html>"""


def page_results(query="", awgn=False, no_harm=False):
    """Render one noise-model result family with shared controls."""
    route_prefix = ("/no-harm-results" if no_harm else
                    ("/awgn-results" if awgn else "/results"))
    page_title = ("Results" if no_harm else
                  ("AWGN results" if awgn else "Experiment results"))
    shell_title = ("Results" if no_harm else
                   ("AWGN results" if awgn else "Results"))
    progress_card = _awgn_progress_card() if awgn and not no_harm else ""
    experiment_id, page, other = _results_query(query)
    plot_values = [value for key, value in other if key == "plot"]
    if no_harm:
        if len(plot_values) > 1 or any(
                value not in ("ber", "effective-rate", "best-observed")
                for value in plot_values):
            raise FileNotFoundError("unknown no-harm plot")
        selected_plot = plot_values[0] if plot_values else "ber"
    else:
        selected_plot = "ber"
    scope_values = [value for key, value in other if key == "scope"]
    selected_scope = "family"
    if no_harm and selected_plot == "best-observed":
        selected_scope = _best_observed_scope(scope_values)
    elif scope_values:
        raise FileNotFoundError(
            "best-observed scope requires the best-observed plot")
    try:
        if experiment_id is None:
            path = _latest_experiment_results(awgn=awgn, no_harm=no_harm)
            experiment_id = _experiment_id_from_result(path)
        else:
            path = _family_result_file(experiment_id, "results_view.html",
                                       awgn=awgn, no_harm=no_harm)
    except FileNotFoundError:
        if experiment_id is not None:
            raise
        body = f"""
<h1>{page_title}</h1>
{progress_card}
<div class="card">No experiment results page exists yet. A search writes
<code>experiments/&lt;name&gt;/results/results_view.html</code>; this tab
shows the newest one.</div>"""
        return shell(shell_title, route_prefix, body)
    selected_snr = 20.0
    snr_control = ""
    rate_grid = ()
    if no_harm and selected_plot in ("effective-rate", "best-observed"):
        snr_values = [value for key, value in other if key == "snr_db"]
        rate_data = _no_harm_effective_rate_data(experiment_id)
        rate_grid = tuple(rate_data)
        selected_snr = _no_harm_effective_rate_snr(
            snr_values, rate_grid)
    stable_other = [
        (key, value) for key, value in other
        if not (no_harm and key in ("layout", "plot", "snr_db", "scope"))]
    if no_harm and selected_plot in ("effective-rate", "best-observed"):
        rate_route = ("/effective-rate/best" if
                      selected_plot == "best-observed" else
                      "/effective-rate")
        rate_query = [
            ("experiment", experiment_id),
            ("snr_db", f"{selected_snr:g}"),
        ]
        if selected_plot == "best-observed":
            rate_query.append(("scope", selected_scope))
        view_url = (route_prefix + rate_route + "?" +
                    urllib.parse.urlencode(rate_query))
        embedded_view_url = (
            view_url + "&embedded=1"
            if selected_plot == "best-observed" else view_url)
        snr_control = _no_harm_effective_rate_slider(
            rate_grid, selected_snr, embedded_view_url, selected_plot)
    else:
        stable_query = urllib.parse.urlencode(
            [("experiment", experiment_id), ("page", page)] + stable_other)
        view_url = route_prefix + "/view?" + stable_query
        embedded_view_url = (
            view_url + "&layout=compact-four" if no_harm else view_url)
    available = _experiment_ids(awgn=awgn, no_harm=no_harm)
    if no_harm and selected_plot == "best-observed":
        family_options = []
        for choice in _no_harm_effective_rate_family_choices(
                available, experiment_id):
            selected = " selected" if choice["selected"] else ""
            family_options.append(
                f'<option value="{esc(choice["experiment_id"])}" '
                f'data-family-size="{choice["size"]}"{selected}>'
                f'{esc(choice["label"])} · {choice["size"]} configurations'
                '</option>')
        jump = ("var url = new window.URL(location.href); "
                "url.searchParams.set('experiment', this.value); "
                "url.searchParams.set('scope', 'family'); "
                "location.href = url")
        scope_jump = ("var url = new window.URL(location.href); "
                      "url.searchParams.set('scope', this.value); "
                      "location.href = url")
        scope_options = (
            f'<option value="all"'
            f'{" selected" if selected_scope == "all" else ""}>'
            'Eligible configurations</option>'
            f'<option value="family"'
            f'{" selected" if selected_scope == "family" else ""}>'
            'Selected family</option>')
        family_picker = ""
        if selected_scope == "family":
            family_picker = (
                '<label>Comparison family '
                '<select id="effective-rate-family-picker" '
                f'onchange="{esc(jump)}">'
                f'{"".join(family_options)}</select></label>')
        picker = (
            '<span style="margin-right:auto;display:flex;gap:.6rem;'
            'align-items:center"><label>Comparison scope '
            f'<select id="best-observed-scope-picker" '
            f'onchange="{esc(scope_jump)}">{scope_options}</select></label>'
            f'{family_picker}</span>')
    elif len(available) > 1:
        option_rows = []
        for result_index, name in enumerate(available, start=1):
            metadata = _no_harm_result_metadata(name) if no_harm else None
            if metadata is not None:
                pilot_spacing = metadata["pilot_spacing"]
                pilot_percent = metadata["pilot_percent"]
                title = (
                    f' title="{esc(metadata["label"])}; ordered pilot '
                    f'spacing {esc(pilot_spacing)}; result {result_index}"')
                pilot_attrs = (
                    f' data-pilot-spacing="{esc(pilot_spacing)}"'
                    f' data-pilot-percent="{esc(pilot_percent)}"'
                    f' aria-label="{esc(metadata["label"])}; ordered pilot '
                    f'spacing {esc(pilot_spacing)}; result {result_index}"')
            else:
                title = f' title="{esc(name)}"' if no_harm else ""
                pilot_attrs = ""
            selected = " selected" if name == experiment_id else ""
            label = _experiment_display_label(name, no_harm)
            option_rows.append(
                f'<option value="{esc(name)}"{title}{pilot_attrs}{selected}>'
                f'{esc(label)}</option>')
        options = "".join(option_rows)
        jump = ("var url = new window.URL(location.href); "
                "url.searchParams.set('experiment', this.value); "
                "location.href = url")
        picker = ('<label style="margin-right:auto">Experiment '
                  f'<select id="experiment-picker" onchange="{esc(jump)}">'
                  f'{options}</select></label>')
    else:
        picker = '<span style="margin-right:auto"></span>'
    if no_harm:
        tab_base = [("experiment", experiment_id), ("page", page)]
        tab_base.extend(stable_other)

        def analysis_tab(plot_value, label, extra):
            query_rows = list(tab_base)
            if plot_value != "ber":
                query_rows.append(("plot", plot_value))
            query_rows.extend(extra)
            href = route_prefix + "?" + urllib.parse.urlencode(query_rows)
            current = (' aria-current="page"'
                       if selected_plot == plot_value else "")
            return (
                '<a class="results-analysis-tab" '
                f'data-plot="{plot_value}"{current} href="{esc(href)}">'
                f'{esc(label)}</a>')

        best_scope = (selected_scope if selected_plot == "best-observed"
                      else "all")
        analysis_tabs = (
            '<nav id="results-analysis-tabs" aria-label="Analysis">' +
            analysis_tab("best-observed", "Best observed payload", [
                ("scope", best_scope),
                ("snr_db", f"{selected_snr:g}"),
            ]) +
            analysis_tab("effective-rate", "Effective payload rate", [
                ("snr_db", f"{selected_snr:g}"),
            ]) +
            analysis_tab("ber", "BER versus SNR", []) +
            '</nav>')
    else:
        analysis_tabs = ""
    path_values = [value for key, value in other if key == "path"]
    initial_path = path_values[0] if len(path_values) == 1 else ""
    parameter_row = ("" if selected_plot == "best-observed" else
        _sweep_parameter_row(
            available, experiment_id, view_url, initial_path,
            route_prefix=route_prefix, no_harm=no_harm,
            path_comparison=(selected_plot == "ber")))
    rel = os.path.relpath(path, ROOT)
    family_note = ("Only results with an explicit CRC no-harm declaration "
                   "in the manifest are shown."
                   if no_harm else
                   "The added noise is independent complex AWGN. The "
                   "impulsive red-noise model is not used on this page."
                   if awgn else
                   "AWGN SNR sweeps with an explicit AWGN manifest "
                   "declaration are shown on AWGN results.")
    unregistered_card = "" if no_harm else f"""
<div class="card"><strong>Unregistered experiment output.</strong> This page
renders <code>{esc(rel)}</code> from the gitignored
<code>experiments/</code> directory. It is not part of the test registry and
is not package evidence. {family_note}</div>"""
    body = f"""
<h1>{page_title}</h1>
{progress_card}
{unregistered_card}
{parameter_row}
{analysis_tabs}
<div class="results-analysis-controls">
{picker}
{snr_control}
<a id="results-open" href="{view_url}" target="_blank">Open in its own tab</a>
</div>
<div id="comparison-empty" class="card" hidden></div>
<iframe id="single-result" src="{embedded_view_url}"
style="width:100%;height:calc(100vh - 150px);
border:1px solid var(--line, #ccc);border-radius:6px;background:white">
 </iframe>
<iframe id="comparison-result" hidden
style="width:100%;height:calc(100vh - 150px);
border:1px solid var(--line, #ccc);border-radius:6px;background:white">
</iframe>"""
    return shell(shell_title, route_prefix, body, wide=True)


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
        if path == "/api/awgn-results/progress":
            return envelope(_awgn_progress_data())
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
                try:
                    return self._send(page_results(query))
                except FileNotFoundError:
                    return self._send("experiment results not found", 404,
                                      "text/plain")
            if path == "/results/compare":
                try:
                    return self._send(page_results_comparison(query))
                except FileNotFoundError:
                    return self._send("comparison results not found", 404,
                                      "text/plain")
            if path == "/results/view":
                try:
                    experiment_id, _page, _other = _results_query(query)
                    result = (_latest_experiment_results(awgn=False)
                              if experiment_id is None else
                              _family_result_file(experiment_id,
                                                  "results_view.html",
                                                  awgn=False))
                    with open(result, "rb") as fh:
                        return self._send(fh.read(), ctype="text/html")
                except FileNotFoundError:
                    return self._send("no experiment results yet", 404,
                                      "text/plain")
            if path == "/results/manifest":
                try:
                    experiment_id, _page, _other = _results_query(query)
                    manifest = _family_result_file(
                        experiment_id, "results_manifest.json", awgn=False)
                    with open(manifest, "rb") as fh:
                        return self._send(fh.read(), ctype="application/json")
                except FileNotFoundError:
                    return self._send(
                        '{"error": "results manifest not found"}',
                        404, "application/json")
            if path == "/awgn-results":
                try:
                    return self._send(page_results(query, awgn=True))
                except FileNotFoundError:
                    return self._send("AWGN results not found", 404,
                                      "text/plain")
            if path == "/awgn-results/compare":
                try:
                    return self._send(page_results_comparison(
                        query, awgn=True))
                except FileNotFoundError:
                    return self._send("AWGN comparison results not found", 404,
                                      "text/plain")
            if path == "/awgn-results/view":
                try:
                    experiment_id, _page, _other = _results_query(query)
                    result = (_latest_experiment_results(awgn=True)
                              if experiment_id is None else
                              _family_result_file(experiment_id,
                                                  "results_view.html",
                                                  awgn=True))
                    with open(result, "rb") as fh:
                        return self._send(fh.read(), ctype="text/html")
                except FileNotFoundError:
                    return self._send("no AWGN results yet", 404,
                                      "text/plain")
            if path == "/awgn-results/manifest":
                try:
                    experiment_id, _page, _other = _results_query(query)
                    manifest = _family_result_file(
                        experiment_id, "results_manifest.json", awgn=True)
                    with open(manifest, "rb") as fh:
                        return self._send(fh.read(), ctype="application/json")
                except FileNotFoundError:
                    return self._send(
                        '{"error": "AWGN results manifest not found"}',
                        404, "application/json")
            if path == "/no-harm-results":
                try:
                    return self._send(page_results(
                        query, awgn=True, no_harm=True))
                except FileNotFoundError:
                    return self._send("results not found", 404,
                                      "text/plain")
            if path == "/no-harm-results/compare":
                try:
                    return self._send(page_results_comparison(
                        query, awgn=True, no_harm=True))
                except FileNotFoundError:
                    return self._send(
                        "comparison results not found", 404,
                        "text/plain")
            if path == "/no-harm-results/view":
                try:
                    experiment_id, _page, other = _results_query(query)
                    result = (_latest_experiment_results(
                        awgn=True, no_harm=True)
                        if experiment_id is None else
                        _family_result_file(
                            experiment_id, "results_view.html", awgn=True,
                            no_harm=True))
                    layout_values = [value for key, value in other
                                     if key == "layout"]
                    with open(result, encoding="utf-8") as fh:
                        document = _default_results_presentation(fh.read())
                    if layout_values == ["compact-four"]:
                        document = _no_harm_compact_four_view(document)
                        return self._send(document, ctype="text/html")
                    return self._send(document, ctype="text/html")
                except FileNotFoundError:
                    return self._send("no results yet", 404,
                                      "text/plain")
            if path == "/no-harm-results/effective-rate":
                try:
                    experiment_id, snr_db = (
                        _no_harm_effective_rate_query(query))
                    document = _no_harm_effective_rate_view(
                        experiment_id, snr_db)
                    return self._send(document, ctype="text/html")
                except FileNotFoundError:
                    return self._send(
                        "no effective-payload-rate result found", 404,
                        "text/plain")
            if path == "/no-harm-results/effective-rate/by-n":
                try:
                    return self._send(
                        page_no_harm_effective_rate_by_n(query))
                except FileNotFoundError:
                    return self._send(
                        "no across-N effective-payload-rate result found",
                        404, "text/plain")
            if path == "/no-harm-results/effective-rate/best":
                try:
                    return self._send(
                        page_no_harm_effective_rate_best(query))
                except FileNotFoundError:
                    return self._send(
                        "no best-observed effective-payload-rate result found",
                        404, "text/plain")
            if path == "/no-harm-results/manifest":
                try:
                    experiment_id, _page, _other = _results_query(query)
                    manifest = _family_result_file(
                        experiment_id, "results_manifest.json", awgn=True,
                        no_harm=True)
                    with open(manifest, "rb") as fh:
                        return self._send(fh.read(),
                                          ctype="application/json")
                except FileNotFoundError:
                    return self._send(
                        '{"error": "results manifest not found"}',
                        404, "application/json")
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
