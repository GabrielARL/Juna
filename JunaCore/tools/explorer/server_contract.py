#!/usr/bin/env python3
"""Behavior contract for the JUNA-Lite explorer server.

Run:  python3 tools/explorer/server_contract.py       (exit 0 = holds)

Boots the server in-process on an ephemeral port and asserts:
S1  every nav page (/, /tests, /map, /chain, /source, /coverage, /health,
    /progress) returns 200 and carries the full nav label set.
S2  /coverage states the static-not-runtime distinction and both legend
    marks (direct ● vs declared-behavioral ◐).
S3  /chain embeds every stage declared in chain.json.
S4  /tests lists every suite key; inverse chain chips (data-stage
    attributes) reference only real chain.json stage ids, and at least one
    chip is rendered.
S5  /source-advanced is the retained analyzer page; /source is the unified
    Source page: server-rendered symbol list, persistent inspector
    container, the five-way evidence taxonomy labels, and a link to the
    legacy page.
S6  banned destinations 404: /benchmark, /history, /reproduce,
    /run/<unknown-suite>, /api/no-such-endpoint.
S7  GET is side-effect free: run/health output endpoints report idle
    without starting anything.
S8  every JSON API (/api/repository, /api/suites, /api/chain,
    /api/symbols, /api/coverage, /api/runs, /api/health, /api/palette)
    returns the provenance envelope {commit, working_tree_dirty,
    generated_at, schema_version==1, data}, with commit matching git and
    working_tree_dirty consistent with the scoped porcelain status.
S9  /api/symbol/<known-name> resolves with sig/file/line, resolved
    calls/callers, chain_stages, and the five-key evidence block;
    /api/symbol/no-such-symbol-xyz 404s.
S10 /health renders every fixed allowlist check row; POST /api/health/run
    with an unknown check name is rejected 400 (never executed).
S11 the dirty-state banner appears on pages exactly when the scoped
    package tree is dirty (consistency with independently computed
    `git status --porcelain -- .`).
S12 /static/palette.js, /static/source.js, /static/health.js are served,
    every page references palette.js, /source references source.js and the
    vendored vis-network, /health references health.js.
S13 legacy-vs-API parity: /api/symbols count and edge count equal a direct
    analyze() of src/, and every chain.json symbol resolves by name via
    /api/symbol/.
S14 /chain renders a selector for all catalog receivers, comparison controls,
    and explicit conditional-edge labels; /api/receivers returns the
    generated Julia catalog.
S15 Source has seamless Inspector and Advanced Graph modes; the graph API
    accepts receiver/stage/suite/file contexts; every navigation tab emits a
    contextual Source entry; and the retained original analyzer has the
    Explorer bridge bar instead of becoming an orphan application.
S16 a real headless browser observes painted canvas pixels for both a
    receiver-context graph and a selected symbol's ego graph. API/DOM-only
    success cannot satisfy this visual contract.
S17 Source alone opts into a full-viewport main area; its three-column grid
    gives compact bounded sidebars to a fluid center graph and retains the
    existing narrow-screen collapse.
S18 receiver graphs disclose complexity progressively: the default is the
    declared stage DAG, stage drill-down groups overloads and omits disconnected
    symbols, an explicit show-all mode restores every implementation symbol,
    and the page explains its node and edge semantics.
"""
import json
import os
import subprocess
import sys
import threading
import urllib.request
from http.server import ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import server  # noqa: E402
from source_symbol_explorer import analyze  # noqa: E402

NAV_LABELS = ["Home", "Tests", "Map", "Chain", "Source", "Coverage",
              "Health", "Progress"]
API_ENDPOINTS = ["/api/repository", "/api/suites", "/api/chain",
                 "/api/symbols", "/api/coverage", "/api/runs",
                 "/api/health", "/api/palette", "/api/receivers",
                 "/api/graph"]
TAXONOMY = ["Static call edge", "Interface implementation",
            "Direct test reference", "Suite-wide association",
            "Runtime result"]
HEALTH_CHECKS = ["provenance-pins", "explorer-data", "server-behavior",
                 "package-load", "pkg-test", "parity-migrated",
                 "parity-source"]


def fetch(base, path, method="GET", body=None):
    req = urllib.request.Request(base + path, method=method,
                                 data=body.encode() if body else None,
                                 headers={"Content-Type": "application/json"}
                                 if body else {})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode()

def browser_dom(base, path):
    chrome = next((candidate for candidate in
                   ("/usr/bin/google-chrome", "/usr/bin/chromium",
                    "/usr/bin/chromium-browser")
                   if os.path.isfile(candidate)), None)
    if chrome is None:
        return None, "headless Chrome unavailable"
    run = subprocess.run(
        [chrome, "--headless", "--no-sandbox", "--disable-gpu",
         "--virtual-time-budget=8000", "--dump-dom", base + path],
        capture_output=True, text=True, timeout=30)
    return run.stdout, run.stderr[-500:]


def check():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    problems = []

    with open(os.path.join(HERE, "suites.json")) as fh:
        suites = json.load(fh)["suites"]
    with open(os.path.join(HERE, "chain.json")) as fh:
        chain = json.load(fh)
    stage_ids = {st["id"] for st in chain["stages"]}

    # S1
    pages = {}
    for path in ["/", "/tests", "/map", "/chain", "/source", "/coverage",
                 "/health", "/progress"]:
        code, text = fetch(base, path)
        pages[path] = text
        if code != 200:
            problems.append(f"S1: {path} returned {code}")
        for label in NAV_LABELS:
            if f">{label}</a>" not in text:
                problems.append(f"S1: {path} lost nav label '{label}'")

    # S2
    cov = pages.get("/coverage", "")
    if "Static references, not runtime coverage" not in cov:
        problems.append("S2: /coverage lost the static-not-runtime statement")
    for mark, meaning in [("●", "direct"), ("◐", "declared association")]:
        if mark not in cov or meaning not in cov:
            problems.append(f"S2: /coverage lost the {mark} ({meaning}) legend")

    # S3
    for st in chain["stages"]:
        if st["title"] not in pages.get("/chain", ""):
            problems.append(f"S3: /chain lost stage '{st['id']}'")

    # S4
    tests_page = pages.get("/tests", "")
    for s in suites:
        if f'id="{s["key"]}"' not in tests_page:
            problems.append(f"S4: /tests lost suite '{s['key']}'")
    import re as _re
    chips = _re.findall(r'data-stage="([^"]+)"', tests_page)
    if not chips:
        problems.append("S4: /tests renders no inverse chain chips")
    for chip in set(chips):
        if chip not in stage_ids:
            problems.append(f"S4: chip references unknown stage '{chip}'")

    # S5
    legacy_code, legacy = fetch(base, "/source-advanced")
    if legacy_code != 200 or "_juna_lite" not in legacy:
        problems.append("S5: /source-legacy is not the analyzer page")
    src_page = pages.get("/source", "")
    if 'id="inspector"' not in src_page or 'id="symlist"' not in src_page:
        problems.append("S5: /source lost the inspector or symbol list")
    if "_juna_lite_candidate" not in src_page:
        problems.append("S5: /source symbol list is not server-rendered")
    for label in TAXONOMY:
        if label not in src_page:
            problems.append(f"S5: /source lost taxonomy label '{label}'")
    if "/source-advanced" not in src_page:
        problems.append("S5: /source lost the original-analyzer link")

    # S6
    for path in ["/benchmark", "/history", "/reproduce",
                 "/run/no-such-suite", "/api/no-such-endpoint"]:
        code, _ = fetch(base, path)
        if code != 404:
            problems.append(f"S6: {path} returned {code}, expected 404")

    # S7
    code, text = fetch(base, f"/run/{suites[0]['key']}/output")
    if code != 200 or json.loads(text).get("status") != "idle":
        problems.append("S7: GET run output is not side-effect free")
    code, text = fetch(base, "/api/health/output")
    if code != 200 or json.loads(text).get("status") not in ("idle", "done",
                                                             "passed",
                                                             "failed"):
        problems.append("S7: GET health output must not start a run")

    # S8
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True, cwd=ROOT
                          ).stdout.strip()
    porcelain = subprocess.run(["git", "status", "--porcelain", "--", "."],
                               capture_output=True, text=True, cwd=ROOT
                               ).stdout.strip()
    actually_dirty = bool(porcelain)
    for path in API_ENDPOINTS:
        code, text = fetch(base, path)
        if code != 200:
            problems.append(f"S8: {path} returned {code}")
            continue
        try:
            env = json.loads(text)
        except json.JSONDecodeError:
            problems.append(f"S8: {path} is not JSON")
            continue
        for key in ("commit", "working_tree_dirty", "generated_at",
                    "schema_version", "data"):
            if key not in env:
                problems.append(f"S8: {path} envelope missing '{key}'")
        if env.get("schema_version") != 1:
            problems.append(f"S8: {path} schema_version != 1")
        if head and env.get("commit") and not env["commit"].startswith(head):
            problems.append(f"S8: {path} commit '{env.get('commit')}' does "
                            f"not match git HEAD {head}")
        if env.get("working_tree_dirty") != actually_dirty:
            problems.append(f"S8: {path} working_tree_dirty="
                            f"{env.get('working_tree_dirty')} but porcelain "
                            f"says {actually_dirty}")

    # S9
    code, text = fetch(base, "/api/symbol/_juna_lite_candidate")
    if code != 200:
        problems.append(f"S9: /api/symbol/_juna_lite_candidate -> {code}")
    else:
        d = json.loads(text)["data"]
        for key in ("sig", "file", "line", "calls", "callers",
                    "chain_stages", "evidence"):
            if key not in d:
                problems.append(f"S9: symbol detail missing '{key}'")
        if d.get("calls") and "name" not in d["calls"][0]:
            problems.append("S9: calls are not resolved to names")
        stages = {st.get("id") for st in d.get("chain_stages", [])}
        if "keep-best" not in stages:
            problems.append("S9: _juna_lite_candidate lost its keep-best "
                            "chain membership")
        ev = d.get("evidence", {})
        for key in ("static_call_edges", "interface_implementation",
                    "direct_test_references", "suite_wide_associations",
                    "runtime_results"):
            if key not in ev:
                problems.append(f"S9: evidence block missing '{key}'")
    code, _ = fetch(base, "/api/symbol/no-such-symbol-xyz")
    if code != 404:
        problems.append(f"S9: unknown symbol returned {code}, expected 404")

    # S10
    health_page = pages.get("/health", "")
    for name in HEALTH_CHECKS:
        if f'data-check="{name}"' not in health_page:
            problems.append(f"S10: /health lost check row '{name}'")
    code, _ = fetch(base, "/api/health/run", method="POST",
                    body='{"check": "rm -rf /"}')
    if code != 400:
        problems.append(f"S10: unknown health check returned {code}, "
                        "expected 400")

    # S11
    banner = "UNCOMMITTED PACKAGE STATE"
    has_banner = banner in pages.get("/", "")
    if has_banner != actually_dirty:
        problems.append(f"S11: dirty banner shown={has_banner} but tree "
                        f"dirty={actually_dirty}")

    # S12
    for asset in ["/static/palette.js", "/static/source.js",
                  "/static/health.js"]:
        code, _ = fetch(base, asset)
        if code != 200:
            problems.append(f"S12: {asset} returned {code}")
    for path, text in pages.items():
        if "/static/palette.js" not in text:
            problems.append(f"S12: {path} does not load the palette")
    if "/static/source.js" not in src_page or "vis-network" not in src_page:
        problems.append("S12: /source lost source.js or vis-network")
    if "/static/health.js" not in health_page:
        problems.append("S12: /health lost health.js")

    # S13
    analyzed = analyze(os.path.join(ROOT, "src"))
    code, text = fetch(base, "/api/symbols")
    if code == 200:
        api_syms = json.loads(text)["data"]
        if len(api_syms) != len(analyzed["symbols"]):
            problems.append(f"S13: /api/symbols count {len(api_syms)} != "
                            f"analyze() count {len(analyzed['symbols'])}")
    for st in chain["stages"]:
        for sym in st["symbols"]:
            code, _ = fetch(base, "/api/symbol/" + sym)
            if code != 200:
                problems.append(f"S13: chain symbol '{sym}' does not "
                                "resolve via /api/symbol/")

    # S14
    chain_page = pages.get("/chain", "")
    with open(os.path.join(HERE, "receivers.json")) as fh:
        receivers = json.load(fh)["receivers"]
    if 'id="receiver-select"' not in chain_page:
        problems.append("S14: /chain lost receiver selector")
    if 'id="compare-select"' not in chain_page:
        problems.append("S14: /chain lost comparison selector")
    for receiver in receivers:
        if receiver["display_name"] not in chain_page:
            problems.append(
                f"S14: /chain lost receiver '{receiver['id']}'")
    for edge in chain.get("edges", []):
        condition = edge.get("condition")
        if condition and condition not in chain_page:
            problems.append(
                f"S14: /chain lost edge condition '{condition}'")

    # S15
    graph_code, graph_page = fetch(base, "/source/graph?receiver=lite")
    if graph_code != 200:
        problems.append(f"S15: /source/graph returned {graph_code}")
    for text in ("Evidence Inspector", "Advanced Graph", "Original Analyzer",
                 'data-source-mode="graph"', 'id="source-context"'):
        if text not in graph_page:
            problems.append(f"S15: graph mode lost '{text}'")
    for query in ("receiver=lite", "stage=seed", "suite=pfft",
                  "file=juna%2Flite.jl"):
        code, text = fetch(base, "/api/graph?" + query)
        if code != 200:
            problems.append(f"S15: /api/graph?{query} returned {code}")
            continue
        data = json.loads(text).get("data", {})
        if not data.get("nodes") or "edges" not in data:
            problems.append(f"S15: /api/graph?{query} lacks nodes/edges")
        if not data.get("context"):
            problems.append(f"S15: /api/graph?{query} lacks context")
    for path in ("/", "/tests", "/map", "/chain", "/coverage", "/health",
                 "/progress"):
        if "/source/graph?" not in pages.get(path, ""):
            problems.append(f"S15: {path} has no contextual Source entry")
    legacy_code, legacy = fetch(base, "/source-advanced")
    if legacy_code != 200 or "Explorer source bridge" not in legacy:
        problems.append("S15: retained analyzer lacks Explorer source bridge")
    for href in ("/source", "/source/graph", "/chain", "/tests",
                 "/coverage"):
        if f'href="{href}"' not in legacy:
            problems.append(f"S15: retained analyzer bridge lost '{href}'")
    code, text = fetch(base, "/api/symbol/Juna.Modulation")
    if code != 200:
        problems.append("S15: qualified Juna.Modulation does not resolve")
    else:
        detail = json.loads(text)["data"]
        if len(detail.get("fields", [])) < 20:
            problems.append("S15: Juna.Modulation field inspector is incomplete")
        if not detail.get("interface_methods"):
            problems.append("S15: type inspector lacks interface implementations")
        if {f["name"] for f in detail.get("facades", [])} != {
                "JunaStandard", "JunaPartialFFT", "JunaLite"}:
            problems.append("S15: type inspector lacks the three public facades")
    source_js = open(os.path.join(HERE, "static", "source.js")).read()
    for marker in ("Static call edge", "doubleClick", "Fields (",
                   "Open in original analyzer"):
        if marker not in source_js:
            problems.append(f"S15: source interaction lost '{marker}'")

    # S16
    for path, label in (
            ("/source/graph?receiver=lite", "receiver graph"),
            ("/source#sym=_juna_step", "symbol ego graph")):
        dom, error = browser_dom(base, path)
        if dom is None:
            problems.append(f"S16: {label} not checked: {error}")
        elif 'data-graph-paint="painted"' not in dom:
            problems.append(f"S16: {label} painted no canvas pixels")

    # S17
    if '<main class="wide">' not in graph_page:
        problems.append("S17: Source graph does not use the wide page shell")
    if '<main class="wide">' in pages.get("/", ""):
        problems.append("S17: wide page shell leaked outside Source")
    server_text = open(os.path.join(HERE, "server.py")).read()
    for marker in ("main.wide { max-width:none;",
                   "grid-template-columns:minmax(12rem,15rem) minmax(0,1fr) "
                   "minmax(18rem,22rem)"):
        if marker not in server_text:
            problems.append(f"S17: fluid Source layout lost '{marker}'")

    # S18
    code, text = fetch(base, "/api/graph?receiver=lite")
    stage_graph = json.loads(text).get("data", {}) if code == 200 else {}
    expected_stage_ids = {
        "stage:" + stage_id
        for receiver in chain["receivers"] if receiver["id"] == "lite"
        for stage_id in receiver["path"] + receiver.get("optional_stages", [])
    }
    if stage_graph.get("view") != "stages":
        problems.append("S18: receiver graph does not default to stage view")
    if {node.get("id") for node in stage_graph.get("nodes", [])} != expected_stage_ids:
        problems.append("S18: default Lite graph does not match its declared stage DAG")
    if any(node.get("kind") != "stage" for node in stage_graph.get("nodes", [])):
        problems.append("S18: default receiver graph contains raw symbol nodes")

    code, text = fetch(
        base, "/api/graph?receiver=lite&stage=seed&view=symbols")
    symbol_graph = json.loads(text).get("data", {}) if code == 200 else {}
    if symbol_graph.get("view") != "symbols":
        problems.append("S18: stage drill-down did not enter symbol view")
    if not symbol_graph.get("nodes"):
        problems.append("S18: stage drill-down has no implementation symbols")
    if any(node.get("kind") == "stage" for node in symbol_graph.get("nodes", [])):
        problems.append("S18: stage drill-down still contains stage nodes")
    if len({(n.get("module"), n.get("name"))
            for n in symbol_graph.get("nodes", [])}) != len(
                symbol_graph.get("nodes", [])):
        problems.append("S18: overloads were not grouped in symbol view")

    code, text = fetch(
        base, "/api/graph?receiver=lite&stage=seed&view=all")
    all_graph = json.loads(text).get("data", {}) if code == 200 else {}
    if all_graph.get("view") != "all":
        problems.append("S18: show-all graph did not report all mode")
    if len(all_graph.get("nodes", [])) < len(symbol_graph.get("nodes", [])):
        problems.append("S18: show-all graph lost focused implementation symbols")

    for marker in ('id="graph-show-all"', 'id="graph-legend"',
                   "Stage — declared receiver step",
                   "Function — grouped source implementation"):
        if marker not in graph_page:
            problems.append(f"S18: Source graph lost progressive control '{marker}'")
    for marker in ("openStage", "toggleShowAll", "overload_count"):
        if marker not in source_js:
            problems.append(f"S18: Source graph interaction lost '{marker}'")

    httpd.shutdown()
    return problems


if __name__ == "__main__":
    problems = check()
    if problems:
        print("SERVER CONTRACT FAILURES:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("server contract: PASS (S1-S18)")
