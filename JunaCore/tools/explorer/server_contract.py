#!/usr/bin/env python3
"""Behavior contract for the JUNA-Lite explorer server.

Run:  python3 tools/explorer/server_contract.py       (exit 0 = holds)

Boots the server in-process on an ephemeral port and asserts:
S1  every nav page (/, /tests, /map, /chain, /source, /coverage, /health,
    /progress) returns 200 and carries the full nav label set.
S2  /coverage states the static-not-runtime distinction and both legend
    marks (direct ● vs declared-behavioral ◐).
S3  /chain embeds every stage declared in chain.json.
S4  /tests presents every suite in reader-facing language, keeps technical
    registry data in collapsed details, labels browser-recorded results as
    Explorer runs, and retains valid receiver-stage links.
S5  /source-advanced is the retained analyzer page; /source is the unified
    Source page: server-rendered symbol list, persistent inspector
    container, the five-way evidence taxonomy labels, and a link to the
    legacy page.
S6  banned destinations 404: /benchmark, /history, /reproduce,
    /run/<unknown-suite>, /api/no-such-endpoint.
S7  GET is side-effect free: run output reports the last recorded result (or
    idle when none exists), and run/health output endpoints start nothing.
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
S15 Source has seamless inspector and graph modes; the graph API
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
S19 every /run/<suite> page uses the suite's reader title and summary, keeps
    status and actions primary, and places the command, method, origin, internal
    key, test file, and streamed Julia output in collapsed Technical details.
S20 reader-facing analyzer wording uses the approved "source definition" and
    "code name" terms; Map explains the definition count and its limits; Chain
    keeps literal Julia names in collapsed Technical details; internal API
    routes, keys, and graph view values remain compatible.
S21 Map uses the approved Package files heading, plain section summaries, and
    four collapsed Technical details sections while retaining the exact package
    paths and program names inside those details.
S22 /awgn-results is a separate AWGN-only Results surface: it retains the
    experiment, seven sweep-parameter, and channel/hydrophone controls; its
    view, manifest, and comparison routes cannot include impulsive-noise
    experiments; and the original /results surface cannot include AWGN sweeps.
S23 /awgn-results shows live AWGN-008, AWGN-009, AWGN-012, AWGN-015,
    AWGN-016, AWGN-017, AWGN-018, AWGN-019, and AWGN-020 progress backed by a
    read-only provenance-wrapped API. The API counts their 612 approved paths,
    using each campaign's fixed aggregate, trace, and path-contract names, and
    the browser polls it every two seconds without counting historical results.
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import server  # noqa: E402
from source_symbol_explorer import analyze  # noqa: E402

NAV_LABELS = ["Home", "Tests", "Map", "Chain", "Source", "Coverage",
              "Health", "Progress", "Results", "AWGN results"]
API_ENDPOINTS = ["/api/repository", "/api/suites", "/api/chain",
                 "/api/symbols", "/api/coverage", "/api/runs",
                 "/api/health", "/api/palette", "/api/receivers",
                 "/api/graph", "/api/awgn-results/progress"]
TAXONOMY = ["Static call edge", "Interface implementation",
            "Direct test reference", "Suite-wide association",
            "Runtime result"]
HEALTH_CHECKS = ["source-file-check", "explorer-data", "server-behavior",
                 "package-load", "pkg-test", "fixed-results"]


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
    try:
        run = subprocess.run(
            [chrome, "--headless", "--no-sandbox", "--disable-gpu",
             "--virtual-time-budget=8000", "--dump-dom", base + path],
            capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return None, "headless Chrome timed out after 60 seconds"
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
        for field in ("reader_title", "reader_summary", "method",
                      "reader_origin"):
            if not s.get(field):
                problems.append(
                    f"S4: suite '{s['key']}' has no {field} explanation")
    import re as _re
    normalized_tests_page = " ".join(tests_page.split())
    for marker in (
            "This page lists the tests included with JUNA-Lite.",
            "<h1>Tests</h1>",
            "Most recent Explorer run",
            "Results on this page come only from tests started in the Explorer.",
            "<th>Test</th>",
            "<th>What it checks</th>"):
        if marker not in normalized_tests_page:
            problems.append(f"S4: /tests lost reader-facing marker '{marker}'")

    detail_tags = _re.findall(
        r'<details\b[^>]*class="suite-details"[^>]*>', tests_page)
    detail_blocks = _re.findall(
        r'<details\b[^>]*class="suite-details"[^>]*>(.*?)</details>',
        tests_page, flags=_re.S)
    if len(detail_blocks) != len(suites):
        problems.append(
            f"S4: /tests renders {len(detail_blocks)} technical details for "
            f"{len(suites)} suites")
    if any(_re.search(r'\sopen(?:\s|=|>)', tag) for tag in detail_tags):
        problems.append("S4: technical details must be collapsed by default")
    for detail in detail_blocks:
        for label in ("How it works", "Test origin", "Internal key",
                      "Test file", "Source view",
                      "Associated receiver steps"):
            if label not in detail:
                problems.append(
                    f"S4: technical details lost the '{label}' label")

    for suite in suites:
        row_match = _re.search(
            rf'<tr id="{_re.escape(suite["key"])}">(.*?)</tr>',
            tests_page, flags=_re.S)
        if not row_match:
            continue
        row = row_match.group(1)
        detail_match = _re.search(
            r'<details\b[^>]*class="suite-details"[^>]*>(.*?)</details>',
            row, flags=_re.S)
        if not detail_match:
            continue
        technical = detail_match.group(1)
        primary_row = row[:detail_match.start()] + row[detail_match.end():]
        primary_markers = ['class="suite-title"', 'class="suite-summary"']
        primary_markers.extend(
            server.esc(suite[field])
            for field in ("reader_title", "reader_summary")
            if suite.get(field))
        for marker in primary_markers:
            if marker not in primary_row:
                problems.append(
                    f"S4: suite '{suite['key']}' lost primary '{marker}'")
        detail_markers = [server.esc(suite["key"]),
                          server.esc(suite["file"])]
        detail_markers.extend(
            server.esc(suite[field])
            for field in ("method", "reader_origin")
            if suite.get(field))
        for marker in detail_markers:
            if marker not in technical:
                problems.append(
                    f"S4: suite '{suite['key']}' details lost '{marker}'")
        expected_stages = [
            stage["id"] for stage in chain["stages"]
            if suite["key"] in stage["suites"]]
        actual_stages = _re.findall(r'data-stage="([^"]+)"', technical)
        if actual_stages != expected_stages:
            problems.append(
                f"S4: suite '{suite['key']}' receiver steps "
                f"{actual_stages} != {expected_stages}")

    primary = _re.sub(
        r'<details\b[^>]*class="suite-details"[^>]*>.*?</details>', "",
        tests_page, flags=_re.S)
    for jargon in ("authoritative registry", "reverse traversal",
                   "protected stages",
                   "pinned sha256", "silent fork", "public facades",
                   "Lite closure", "facade pruning", "benchmark geometry",
                   "migration gate"):
        if jargon.casefold() in primary.casefold():
            problems.append(
                f"S4: primary Tests copy exposes maintainer jargon '{jargon}'")

    chips = _re.findall(r'data-stage="([^"]+)"', "".join(detail_blocks))
    if not chips:
        problems.append("S4: /tests technical details render no stage links")
    if 'data-stage="' in primary:
        problems.append("S4: stage links escaped the technical details")
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
    with server.RUNS_LOCK:
        runs_before = set(server.RUNS)
    last_runs = server.last_run_by_key()
    for suite in suites:
        code, text = fetch(base, f"/run/{suite['key']}/output")
        expected_status = last_runs.get(suite["key"], {}).get("status", "idle")
        if code != 200 or json.loads(text).get("status") != expected_status:
            problems.append(
                f"S7: GET run output for '{suite['key']}' did not report "
                f"the last recorded status '{expected_status}'")
    with server.RUNS_LOCK:
        if set(server.RUNS) != runs_before:
            problems.append("S7: GET run output started or registered a run")
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
    for text in ('data-source-mode="graph"', 'id="source-context"'):
        if text not in graph_page:
            problems.append(f"S15: graph mode lost '{text}'")
    for query in ("receiver=lite", "stage=initial-candidate", "suite=pfft",
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
        base, "/api/graph?receiver=lite&stage=initial-candidate&view=symbols")
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
        base, "/api/graph?receiver=lite&stage=initial-candidate&view=all")
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

    # S19
    for suite in suites:
        code, run_page = fetch(base, "/run/" + suite["key"])
        if code != 200:
            problems.append(
                f"S19: /run/{suite['key']} returned {code}")
            continue
        detail_match = _re.search(
            r'<details\b[^>]*class="suite-details run-details"[^>]*>'
            r'(.*?)</details>', run_page, flags=_re.S)
        if not detail_match:
            problems.append(
                f"S19: /run/{suite['key']} has no consolidated Technical "
                "details")
            continue
        detail_tag = detail_match.group(0).split(">", 1)[0] + ">"
        technical = detail_match.group(1)
        primary = run_page[:detail_match.start()] + run_page[detail_match.end():]
        if _re.search(r'\sopen(?:\s|=|>)', detail_tag):
            problems.append(
                f"S19: /run/{suite['key']} Technical details are open by "
                "default")
        for marker in (
                suite["reader_title"], suite["reader_summary"],
                "Most recent Explorer run", ">Run test</button>",
                ">Cancel</button>", ">Back to tests</a>"):
            if server.esc(marker) not in primary and marker not in primary:
                problems.append(
                    f"S19: /run/{suite['key']} lost primary marker '{marker}'")
        for hidden in (suite["title"], suite["claim"], suite["origin"],
                       f"julia --project=. test/{suite['file']}",
                       '<pre id="out"'):
            if hidden and hidden != suite["reader_title"] and hidden in primary:
                problems.append(
                    f"S19: /run/{suite['key']} exposes technical content "
                    f"outside details: '{hidden}'")
        for marker in (
                "Technical details", "How it works", suite["method"],
                "Test origin", suite["reader_origin"], "Internal key",
                suite["key"], "Test file", suite["file"],
                f"julia --project=. test/{suite['file']}", '<pre id="out"'):
            if server.esc(marker) not in technical and marker not in technical:
                problems.append(
                    f"S19: /run/{suite['key']} details lost '{marker}'")
        expected_title = (
            f"<title>{server.esc(suite['reader_title'])} · "
            "JUNA-Lite explorer</title>")
        if expected_title not in run_page:
            problems.append(
                f"S19: /run/{suite['key']} browser title is not reader-facing")
        for marker in ("/output?from=", "/start", "/cancel", "seen = 0",
                       "d.status === 'running'"):
            if marker not in run_page:
                problems.append(
                    f"S19: /run/{suite['key']} lost runner behavior '{marker}'")

    # S20 approved JNR-001 through JNR-006 reader vocabulary
    code, map_page = fetch(base, "/map")
    if code != 200:
        problems.append(f"S20: /map returned {code}")
    normalized_map_page = " ".join(map_page.split())
    kind_counts = {}
    per_file_counts = {}
    for definition in analyzed["symbols"]:
        kind = definition["kind"]
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
        file_name = definition["file"]
        per_file_counts[file_name] = per_file_counts.get(file_name, 0) + 1
    map_markers = (
        f'<b>{len(analyzed["symbols"])} source definitions</b>, counted '
        "afresh on every page load.",
        "A repeated name is counted separately for each definition.",
        "These definitions were found in the source code. This count does "
        "not show that the code ran.",
    )
    for marker in map_markers:
        if marker not in normalized_map_page:
            problems.append(f"S20: /map lost approved wording '{marker}'")
    # The kind table replaces the run-on sentence (JCM-059). Each row must
    # carry the live count, so a kind that gains or loses a definition without
    # the page following it is a failure rather than a silent drift.
    kind_labels = [("function", "Function or method definition"),
                   ("const", "Constant"),
                   ("module", "Module declaration"),
                   ("struct", "Structure declaration"),
                   ("type", "Abstract type declaration")]
    for kind, singular in kind_labels:
        count = kind_counts.get(kind, 0)
        label = singular if count == 1 else singular + "s"
        marker = (f'<tr><td>{label}</td>'
                  f'<td class="kind-count">{count}</td>')
        if marker not in normalized_map_page:
            problems.append(
                f"S20: /map kind table has no correct row for {kind}: "
                f"'{marker}'")
    # Kinds small enough to enumerate name every definition they count.
    for kind in ("module", "struct", "type"):
        named = list(dict.fromkeys(d["name"] for d in analyzed["symbols"]
                                   if d["kind"] == kind))
        if len(named) > 12:
            continue
        for name in named:
            if f"<code>{name}</code>" not in normalized_map_page:
                problems.append(
                    f"S20: /map kind table omits the {kind} '{name}'")
    for file_name, count in per_file_counts.items():
        noun = "source definition" if count == 1 else "source definitions"
        marker = f">{count} {noun}</td>"
        if marker not in map_page:
            problems.append(
                f"S20: /map has no correct count label for {file_name}: "
                f"'{marker}'")

    code, source_page = fetch(base, "/source")
    code_graph, graph_page = fetch(base, "/source/graph")
    for path, status, page in (("/source", code, source_page),
                               ("/source/graph", code_graph, graph_page)):
        if status != 200:
            problems.append(f"S20: {path} returned {status}")
            continue
        for marker in ("selected source definition",
                       "source definition context",
                       'placeholder="filter source definitions…"',
                       "Select a source definition to inspect it"):
            if marker not in page:
                problems.append(
                    f"S20: {path} lost approved wording '{marker}'")
    if "Show all code names" not in graph_page:
        problems.append("S20: Source graph control uses the old analyzer term")
    rendered_definitions = len(_re.findall(r'class="symlink"', source_page))
    if rendered_definitions != len(analyzed["symbols"]):
        problems.append(
            f"S20: /source renders {rendered_definitions} source definitions, "
            f"expected {len(analyzed['symbols'])}")

    code, chain_page = fetch(base, "/chain")
    if code != 200:
        problems.append(f"S20: /chain returned {code}")
    normalized_chain_page = " ".join(chain_page.split())
    for marker in ("Click a receiver step to see its description, tests, and "
                   "technical details.",
                   '<details class="stage-technical">',
                   '<details class="receiver-technical">',
                   "<summary>Technical details</summary>",
                   "<b>Code names</b>"):
        if marker not in normalized_chain_page:
            problems.append(f"S20: /chain lost approved display rule '{marker}'")
    if "st.symbols.slice(0, 3)" in chain_page:
        problems.append("S20: /chain exposes raw code names in primary stage cards")
    for detail_class in ("stage-technical", "receiver-technical"):
        if _re.search(
                rf'<details class="{detail_class}"\s+open(?:\s|=|>)',
                chain_page):
            problems.append(
                f"S20: /chain {detail_class} is not collapsed by default")

    code, coverage_page = fetch(base, "/coverage")
    if code != 200:
        problems.append(f"S20: /coverage returned {code}")
    for marker in ("directly referenced code names",
                   "<th>Code name</th>",
                   "direct textual reference to a stage code name"):
        if marker not in coverage_page:
            problems.append(f"S20: /coverage lost approved wording '{marker}'")

    for marker in ("Could not load source definition",
                   "Source definition not found",
                   "Code name",
                   "implementation source definition",
                   "all code names",
                   "grouped code names",
                   "Hide disconnected code names",
                   "Show all code names"):
        if marker not in source_js:
            problems.append(f"S20: source.js lost approved wording '{marker}'")

    code, palette_js = fetch(base, "/static/palette.js")
    if code != 200:
        problems.append(f"S20: /static/palette.js returned {code}")
    for marker in ("page, suite, stage, code name, module",
                   'symbol: "code name"'):
        if marker not in palette_js:
            problems.append(f"S20: palette lost approved wording '{marker}'")

    code, original_page = fetch(base, "/source-advanced")
    if code != 200:
        problems.append(f"S20: /source-advanced returned {code}")
    for marker in ("JunaCore source definition explorer",
                   "JunaCore source definitions",
                   "Source definition not found", "Code name"):
        if marker not in original_page:
            problems.append(
                f"S20: original analyzer lost approved wording '{marker}'")

    # S21 approved JNR-007 through JNR-015 Map structure and wording
    primary_map = _re.sub(
        r'<details\b[^>]*class="suite-details map-details"[^>]*>.*?</details>',
        "", map_page, flags=_re.S)
    normalized_primary_map = " ".join(primary_map.split())
    map_visible = " ".join(_re.sub(r"<[^>]+>", " ", primary_map).split())
    approved_map_structure = (
        "<h1>Package files</h1>",
        "<h2>Source files</h2>",
        "<h2>Tests</h2>",
        "<h2>Tools</h2>",
        "<h2>Explorer run records</h2>",
    )
    for marker in approved_map_structure:
        if marker not in normalized_primary_map:
            problems.append(f"S21: /map lost approved structure '{marker}'")
    approved_map_wording = (
        "This page shows the source files, tests, tools, and Explorer run "
        "records included with this package.",
        f"This package includes {len(suites)} tests. Open Tests to see what "
        "each one checks.",
        "The package uses helper programs for error correction. The Explorer "
        "files provide these pages and their checks.",
        "The Explorer saves the results of tests and checks started here.",
    )
    for marker in approved_map_wording:
        if marker not in map_visible:
            problems.append(f"S21: /map lost approved wording '{marker}'")
    map_details = list(_re.finditer(
        r'(<details\b[^>]*class="suite-details map-details"[^>]*>)'
        r'(.*?)</details>', map_page, flags=_re.S))
    if len(map_details) != 4:
        problems.append(
            f"S21: /map has {len(map_details)} Map Technical details; "
            "expected 4")
    expected_detail_markers = (
        ("<code>src/</code>", "<code>JunaCore.jl</code>"),
        ("<code>test/</code>", "<code>Pkg.test</code>",
         "<code>test/support/</code>", "<code>test/runtests.jl</code>"),
        ("<code>tools/ldpc</code>", "<code>tools/explorer</code>",
         "<code>tools/parity_check.jl</code>"),
        ("<code>bench/test_runs.jsonl</code>",
         "<code>bench/health_runs.jsonl</code>"),
    )
    for index, match in enumerate(map_details, start=1):
        opening, details = match.group(1), match.group(2)
        if _re.search(r'\sopen(?:\s|=|>)', opening):
            problems.append(
                f"S21: Map Technical details {index} is open by default")
        if "<summary>Technical details</summary>" not in details:
            problems.append(
                f"S21: Map details {index} lacks its Technical details label")
        if index <= len(expected_detail_markers):
            for marker in expected_detail_markers[index - 1]:
                if marker not in details:
                    problems.append(
                        f"S21: Map details {index} lost exact marker "
                        f"'{marker}'")
    for old_primary in (
            "Repository map", "migrated package's real structure",
            "loaded by JunaCore.jl", "verified by Pkg.test",
            "analyzed by", "run history"):
        if old_primary in primary_map:
            problems.append(
                f"S21: /map still exposes old primary wording "
                f"'{old_primary}'")
    for markers in expected_detail_markers:
        for marker in markers:
            if marker in primary_map:
                problems.append(
                    f"S21: /map exposes technical marker outside details "
                    f"'{marker}'")

    # S22 separate AWGN-only result routes with the same Results controls.
    code, awgn_empty = fetch(base, "/awgn-results")
    if code != 200:
        problems.append(f"S22: /awgn-results returned {code}")
    for marker in ("<h1>AWGN results</h1>", ">AWGN results</a>"):
        if marker not in awgn_empty:
            problems.append(f"S22: /awgn-results lost marker '{marker}'")

    original_root = server.ROOT
    try:
        with tempfile.TemporaryDirectory(
                prefix="juna-awgn-results-contract-") as fixture:
            experiments = os.path.join(fixture, "experiments")
            os.makedirs(experiments)
            legacy_awgn_ids = tuple(
                f"contract-red-awgn-full-snr-sweep-n{nfft}-cp{cp}-"
                f"rate025-p5-{inner}-dc10-kfill-pfft4"
                for nfft in (1024, 2048)
                for cp in (128, 256)
                for inner in (5,))
            rate_awgn_ids = tuple(
                f"contract-red-awgn-snr-sweep-n{nfft}-cp{cp}-rate{rate}-"
                f"p5-{inner}-dc10-kfill-pfft4"
                for rate in ("0125", "025")
                for nfft in (1024, 2048)
                for cp in (64, 128, 256)
                for inner in (5, 10))
            outer_awgn_ids = tuple(
                f"contract-red-awgn-snr-sweep-n{nfft}-cp{cp}-rate025-"
                f"p{outer}-{inner}-dc10-kfill-pfft4"
                for outer in (10,)
                for nfft in (1024, 2048)
                for cp in (64, 128, 256)
                for inner in (5, 10))
            single_awgn_id = (
                "contract-red-awgn-snr-sweep-n4096-cp64-rate025-"
                "p5-5-dc10-kfill-pfft4")
            partial_awgn_ids = tuple(
                "contract-red-awgn-snr-sweep-n4096-cp64-rate025-"
                f"p5-5-dc{check}-kfill-pfft4"
                for check in (6, 12, 14))
            awgn017_ids = tuple(
                "contract-red-awgn-snr-sweep-n2048-cp64-rate025-"
                f"p5-5-dc{check}-kfill-pfft4"
                for check in (12, 14))
            awgn018_ids = tuple(
                "contract-red-awgn-snr-sweep-n1024-cp64-rate025-"
                f"p5-5-dc{check}-kfill-pfft4"
                for check in (12, 14))
            awgn019_ids = tuple(
                "2026-08-09-red-awgn-crc-no-harm-3receivers-"
                f"n{nfft}-cp64-rate025-p5-5-dc{check}-kfill-pfft4"
                for nfft in (1024, 2048)
                for check in (10, 12, 14))
            awgn_ids = (legacy_awgn_ids + rate_awgn_ids + outer_awgn_ids +
                        (single_awgn_id,) + partial_awgn_ids + awgn017_ids +
                        awgn018_ids + awgn019_ids)
            impulsive_id = (
                "contract-red-snr-sweep-n1024-cp128-rate025-"
                "p5-5-dc10-kfill-pfft4")
            invalid_ids = (
                "contract-awgn-missing-manifest",
                "contract-awgn-malformed-manifest",
                "contract-awgn-mismatched-manifest",
            )
            paths = tuple(f"red{channel} {hydrophone}"
                          for channel in range(1, 5)
                          for hydrophone in range(1, 4))
            for experiment_id in awgn_ids + (impulsive_id,):
                results = os.path.join(experiments, experiment_id, "results")
                os.makedirs(results)
                result_paths = paths
                panels = "".join(
                    '<figure class="panel"><figcaption>'
                    f'<b>{path.rsplit(" ", 1)[0]} hydrophone '
                    f'{path.rsplit(" ", 1)[1]}</b></figcaption>'
                    f'<svg data-contract-experiment="{experiment_id}" '
                    f'data-contract-path="{path}"></svg></figure>'
                    for path in result_paths)
                with open(os.path.join(results, "results_view.html"),
                          "w", encoding="utf-8") as handle:
                    handle.write(
                        "<!doctype html><style>.panel{display:block}</style>"
                        '<div class="legend">fixture legend</div>' + panels)
                with open(os.path.join(results, "results_manifest.json"),
                          "w", encoding="utf-8") as handle:
                    json.dump({
                        "schema_version": 2,
                        "experiment_id": experiment_id,
                        "paths": result_paths,
                        "noise_model": {
                            "kind": ("awgn" if experiment_id in awgn_ids
                                     else "alpha-stable"),
                        },
                    }, handle)

            # A rendered page alone cannot select a noise family. Missing,
            # malformed, and self-mismatched manifests belong to neither.
            for experiment_id in invalid_ids:
                results = os.path.join(experiments, experiment_id, "results")
                os.makedirs(results)
                with open(os.path.join(results, "results_view.html"),
                          "w", encoding="utf-8") as handle:
                    handle.write(f"<!doctype html><p>{experiment_id}</p>")
            with open(os.path.join(
                    experiments, invalid_ids[1], "results",
                    "results_manifest.json"), "w", encoding="utf-8") as handle:
                handle.write("{not valid json")
            with open(os.path.join(
                    experiments, invalid_ids[2], "results",
                    "results_manifest.json"), "w", encoding="utf-8") as handle:
                json.dump({
                    "schema_version": 2,
                    "experiment_id": "a-different-experiment",
                    "noise_model": {"kind": "awgn"},
                }, handle)

            # S23 fixture: one complete CP64 configuration in AWGN-008 and
            # AWGN-009, one active AWGN-009 CP64 path, one queued outer-
            # spacing campaign, and one historical full-capture path that
            # must not enter the total.
            family = "2026-08-08-red-awgn-first4s-frames4-snr-sweep"
            baseline_harness_name = (
                "2026-08-08-red-awgn-first4s-frames4-snr-sweep")
            rate_harness_name = (
                "2026-08-08-red-awgn-first4s-frames4-"
                "rates0125-05-075-snr-sweep")
            outer_harness_name = (
                "2026-08-08-red-awgn-first4s-frames4-"
                "outer10-7-3-snr-sweep")
            awgn015_harness_name = (
                f"{family}-n4096-cp64-rate025-p5-5-"
                "dc10-kfill-pfft4")
            awgn016_harness_name = (
                f"{family}-n4096-cp64-rate025-p5-5-"
                "dc6-kfill-pfft4")
            awgn017_harness_name = (
                f"{family}-n2048-cp64-rate025-p5-5-"
                "dc12-kfill-pfft4")
            awgn018_harness_name = (
                f"{family}-n1024-cp64-rate025-p5-5-"
                "dc12-kfill-pfft4")
            awgn019_harness_name = awgn019_ids[0]
            awgn020_harness_name = (
                "2026-08-10-red-awgn-first8s-frames8-crc-no-harm-"
                "n1024-cp64-rate025-p5-5-dc14-kfill-pfft4")
            campaign_specs = (
                ("AWGN-008", "025", "0.25", 5, baseline_harness_name,
                 "awgn008_matrix.log"),
                ("AWGN-009", "0125", "0.125", 5, rate_harness_name,
                 "awgn009_matrix.log"),
                ("AWGN-012", "025", "0.25", 10, outer_harness_name,
                 "awgn012_matrix.log"),
            )
            progress_ids = {
                decision: tuple(
                    f"{family}-n{nfft}-cp{cp}-rate{rate}-p{outer}-{inner}-"
                    "dc10-kfill-pfft4"
                    for nfft in (1024, 2048)
                    for cp in (64, 128, 256)
                    for inner in (5, 10))
                for (decision, rate, _value, outer, _harness,
                     _log) in campaign_specs
            }
            progress_ids["AWGN-015"] = (
                awgn015_harness_name,)
            progress_ids["AWGN-016"] = tuple(
                f"{family}-n4096-cp64-rate025-p5-5-"
                f"dc{check}-kfill-pfft4"
                for check in (6, 12, 14))
            progress_ids["AWGN-017"] = tuple(
                f"{family}-n2048-cp64-rate025-p5-5-"
                f"dc{check}-kfill-pfft4"
                for check in (12, 14))
            progress_ids["AWGN-018"] = tuple(
                f"{family}-n1024-cp64-rate025-p5-5-"
                f"dc{check}-kfill-pfft4"
                for check in (12, 14))
            progress_ids["AWGN-019"] = awgn019_ids
            progress_ids["AWGN-020"] = (awgn020_harness_name,)
            aggregate = (
                "red_snr_sweep_awgn_first4s_frames4_configuration.csv")
            complete_pairs = tuple(
                (progress_ids[decision][0],
                 f"red{channel}_hydrophone{hydrophone}")
                for decision in ("AWGN-008", "AWGN-009")
                for channel in range(1, 5)
                for hydrophone in range(1, 4)) + (
                    (progress_ids["AWGN-016"][0], "red4_hydrophone2"),
                    # A second path proves that AWGN-016 now counts the full
                    # channel/hydrophone matrix, not only red4/hydrophone 2.
                    (progress_ids["AWGN-016"][0], "red1_hydrophone1"),
                )
            for experiment_id, path in complete_pairs:
                run_dir = os.path.join(
                    experiments, experiment_id, "results", "runs", path)
                os.makedirs(run_dir)
                open(os.path.join(run_dir, aggregate), "w").close()
                open(os.path.join(
                    run_dir, path + "_selection_trace.csv"), "w").close()
            # AWGN-019 must not count aggregate/trace files until its runner
            # also promotes the final per-path validation contract.
            awgn019_contract_dir = os.path.join(
                experiments, progress_ids["AWGN-019"][0], "results", "runs",
                "red1_hydrophone1")
            os.makedirs(awgn019_contract_dir)
            open(os.path.join(awgn019_contract_dir, aggregate), "w").close()
            open(os.path.join(
                awgn019_contract_dir,
                "red1_hydrophone1_selection_trace.csv"), "w").close()
            awgn019_contract = os.path.join(
                awgn019_contract_dir, "awgn019_path_contract.txt")
            # AWGN-020 uses a different aggregate basename. Its final
            # validation contract must be present before the path is counted.
            awgn020_contract_dir = os.path.join(
                experiments, progress_ids["AWGN-020"][0], "results", "runs",
                "red1_hydrophone1")
            os.makedirs(awgn020_contract_dir)
            open(os.path.join(
                awgn020_contract_dir,
                "red_snr_sweep_awgn_first8s_frames8_configuration.csv"),
                "w").close()
            open(os.path.join(
                awgn020_contract_dir,
                "red1_hydrophone1_selection_trace.csv"), "w").close()
            awgn020_contract = os.path.join(
                awgn020_contract_dir, "awgn020_path_contract.txt")
            old_id = ("2026-08-07-red-awgn-snr-sweep-"
                      "n1024-cp128-rate025-p5-5-"
                      "dc10-kfill-pfft4")
            old_dir = os.path.join(
                experiments, old_id, "results", "runs", "red1_hydrophone1")
            os.makedirs(old_dir)
            open(os.path.join(old_dir, aggregate), "w").close()
            open(os.path.join(
                old_dir, "red1_hydrophone1_selection_trace.csv"), "w").close()

            baseline_harness = os.path.join(
                experiments, baseline_harness_name)
            rate_harness = os.path.join(experiments, rate_harness_name)
            outer_harness = os.path.join(experiments, outer_harness_name)
            awgn015_harness = os.path.join(
                experiments, awgn015_harness_name)
            awgn016_harness = os.path.join(
                experiments, awgn016_harness_name)
            awgn017_harness = os.path.join(
                experiments, awgn017_harness_name)
            awgn018_harness = os.path.join(
                experiments, awgn018_harness_name)
            awgn019_harness = os.path.join(
                experiments, awgn019_harness_name)
            awgn020_harness = os.path.join(
                experiments, awgn020_harness_name)
            os.makedirs(baseline_harness)
            os.makedirs(rate_harness)
            os.makedirs(outer_harness)
            os.makedirs(awgn015_harness, exist_ok=True)
            os.makedirs(awgn016_harness, exist_ok=True)
            os.makedirs(awgn017_harness, exist_ok=True)
            os.makedirs(awgn018_harness, exist_ok=True)
            os.makedirs(awgn019_harness, exist_ok=True)
            os.makedirs(awgn020_harness, exist_ok=True)
            with open(os.path.join(baseline_harness, "awgn008_matrix.log"),
                      "w", encoding="utf-8") as handle:
                handle.write(
                    "AWGN_008_COMPUTE_START 2026-08-08T00:00:00+08:00\n")
            with open(os.path.join(awgn015_harness, "awgn015_sweep.log"),
                      "w", encoding="utf-8") as handle:
                handle.write(
                    "AWGN_015_QUEUE_START 2026-08-08T00:00:00+08:00\n")
            active_awgn016_id = progress_ids["AWGN-016"][1]
            with open(os.path.join(awgn016_harness, "awgn016_sweep.log"),
                      "w", encoding="utf-8") as handle:
                handle.write(
                    "AWGN_016_COMPUTE_START 2026-08-08T00:00:00+08:00\n"
                    f"PATH_START AWGN-016 {active_awgn016_id} "
                    "red4 hydrophone 2\n")
            with open(os.path.join(awgn017_harness, "awgn017_sweep.log"),
                      "w", encoding="utf-8") as handle:
                handle.write(
                    "AWGN_017_QUEUE_START 2026-08-08T00:00:00+08:00\n")
            with open(os.path.join(awgn018_harness, "awgn018_sweep.log"),
                      "w", encoding="utf-8") as handle:
                handle.write(
                    "AWGN_018_QUEUE_START 2026-08-08T00:00:00+08:00\n")
            active_awgn019_id = progress_ids["AWGN-019"][0]
            with open(os.path.join(awgn019_harness, "awgn019_sweep.log"),
                      "w", encoding="utf-8") as handle:
                handle.write(
                    "AWGN_019_COMPUTE_START 2026-08-09T00:00:00+08:00\n"
                    f"PATH_START AWGN-019 {active_awgn019_id} "
                    "red2 hydrophone 3 2026-08-09T00:00:01+08:00\n")
            with open(os.path.join(awgn020_harness, "awgn020_sweep.log"),
                      "w", encoding="utf-8") as handle:
                handle.write(
                    "AWGN_020_QUEUE_START 2026-08-10T00:00:00+08:00\n")
            active_id = progress_ids["AWGN-009"][1]
            with open(os.path.join(rate_harness, "awgn009_matrix.log"), "w",
                      encoding="utf-8") as handle:
                handle.write(
                    "AWGN_009_COMPUTE_START 2026-08-08T00:00:00+08:00\n"
                    f"PATH_START AWGN-009 {active_id} red1 hydrophone 2\n"
                    "garbled worker output without a complete line")
            for decision in ("AWGN-012",):
                number = decision.rsplit("-", 1)[1]
                marker = decision.replace("-", "_")
                with open(os.path.join(
                        outer_harness, f"awgn{number}_matrix.log"), "w",
                        encoding="utf-8") as handle:
                    handle.write(
                        f"{marker}_COMPUTE_START "
                        "2026-08-07T23:59:00+08:00\n"
                        f"PATH_START {decision} "
                        f"{progress_ids[decision][0]} red1 hydrophone 1\n"
                        f"{marker}_QUEUE_START 2026-08-08T00:00:00+08:00\n")

            server.ROOT = fixture
            selected = urllib.parse.quote(awgn_ids[0], safe="")
            code, awgn_page = fetch(
                base, f"/awgn-results?experiment={selected}")
            if code != 200:
                problems.append(
                    f"S22: populated /awgn-results returned {code}")
            for marker in (
                    '<select id="experiment-picker"',
                    'id="sweep-parameters"',
                    'id="sweep-parameter-controls"',
                    '<select id="path-filter"',
                    '"N"', '"CP"', '"code rate"', '"outer spacing"',
                    '"inner spacing"', '"check degree"', '"horizon"',
                    'return "/awgn-results/compare?"'):
                if marker not in awgn_page:
                    problems.append(
                        f"S22: AWGN page lost Results control '{marker}'")
            for experiment_id in awgn_ids:
                if experiment_id not in awgn_page:
                    problems.append(
                        f"S22: AWGN page omitted '{experiment_id}'")
            if impulsive_id in awgn_page:
                problems.append(
                    "S22: AWGN page included an impulsive-noise experiment")
            if any(experiment_id in awgn_page for experiment_id in invalid_ids):
                problems.append(
                    "S22: AWGN page included an invalid-manifest experiment")
            if "/results/manifest" in awgn_page:
                problems.append(
                    "S22: AWGN page contains a hardcoded Results manifest route")
            picker = _re.search(
                r'<select id="experiment-picker"[^>]*>(.*?)</select>',
                awgn_page, flags=_re.S)
            if not picker or picker.group(1).count("<option ") != 54:
                problems.append(
                    "S22: AWGN experiment picker does not contain 54 options")
            path_picker = _re.search(
                r'<select id="path-filter"[^>]*>(.*?)</select>',
                awgn_page, flags=_re.S)
            if not path_picker or path_picker.group(1).count("<option ") != 13:
                problems.append(
                    "S22: AWGN path picker does not contain (all) plus 12 paths")
            elif any(f'value="red{channel}:{hydrophone}"' not in
                     path_picker.group(1)
                     for channel in range(1, 5)
                     for hydrophone in range(1, 4)):
                problems.append(
                    "S22: AWGN path picker lost an exact channel/hydrophone")

            code, awgn_latest = fetch(base, "/awgn-results")
            if (code != 200 or not any(experiment_id in awgn_latest
                                       for experiment_id in awgn_ids) or
                    any(experiment_id in awgn_latest
                        for experiment_id in invalid_ids + (impulsive_id,))):
                problems.append(
                    "S22: no-ID AWGN route did not select a valid AWGN family")

            code, results_page = fetch(base, "/results")
            if code != 200 or impulsive_id not in results_page:
                problems.append(
                    "S22: /results lost its impulsive-noise experiment")
            if any(experiment_id in results_page for experiment_id in awgn_ids):
                problems.append("S22: /results included an AWGN experiment")
            if any(experiment_id in results_page for experiment_id in invalid_ids):
                problems.append(
                    "S22: /results included an invalid-manifest experiment")

            default_dom, browser_error = browser_dom(
                base, f"/awgn-results?experiment={selected}")
            if default_dom is None:
                problems.append(
                    f"S22: AWGN browser controls not checked: {browser_error}")
            else:
                controls = _re.search(
                    r'<span id="sweep-parameter-controls"[^>]*>(.*?)</span>',
                    default_dom, flags=_re.S)
                if (not controls or controls.group(1).count("<select") != 7 or
                        "54 experiments match" not in default_dom):
                    problems.append(
                        "S22: browser did not render 7 controls and 54 matches")
                if controls:
                    for label, expected_values in (
                            ("N", {"", "1024", "2048", "4096"}),
                            ("CP", {"", "64", "128", "256"}),
                            ("code rate", {"", "0.125", "0.25"}),
                            ("outer spacing", {"", "5", "10"}),
                            ("check degree", {"", "6", "10", "12", "14"})):
                        select = _re.search(
                            rf"<label>{_re.escape(label)} <select>"
                            r"(.*?)</select>", controls.group(1), flags=_re.S)
                        values = (set(_re.findall(r'value="([^"]*)"',
                                                  select.group(1)))
                                  if select else set())
                        if values != expected_values:
                            problems.append(
                                f"S22: {label} values {sorted(values)!r}, "
                                f"expected {sorted(expected_values)!r}")
                comparison_tag = _re.search(
                    r'<iframe id="comparison-result"([^>]*)>', default_dom)
                single_tag = _re.search(
                    r'<iframe id="single-result"([^>]*)>', default_dom)
                if (not comparison_tag or
                        "hidden" not in comparison_tag.group(1) or
                        not single_tag or "hidden" in single_tag.group(1)):
                    problems.append(
                        "S22: (all) did not retain the single AWGN result view")
                for marker in (
                        "26 of 612 paths validated (4.2%); 2 of 51 "
                        "configurations complete.",
                        "AWGN-008 (rate 0.25, outer spacing 5): "
                        "12 of 144 paths; running",
                        "AWGN-009 (rate 0.125, outer spacing 5): "
                        "12 of 144 paths; running",
                        "AWGN-012 (rate 0.25, outer spacing 10): "
                        "0 of 144 paths; queued",
                        "AWGN-015 (rate 0.25, outer spacing 5): "
                        "0 of 12 paths; queued",
                        "AWGN-016 (rate 0.25, outer spacing 5): "
                        "2 of 36 paths; running",
                        "AWGN-017 (rate 0.25, outer spacing 5): "
                        "0 of 24 paths; queued",
                        "AWGN-018 (rate 0.25, outer spacing 5): "
                        "0 of 24 paths; queued",
                        "AWGN-019 (rate 0.25, outer spacing 5): "
                        "0 of 72 paths; running",
                        "AWGN-020 (rate 0.25, outer spacing 5): "
                        "0 of 12 paths; queued",
                        f"Current: AWGN-009, {active_id}, "
                        "red1 hydrophone 2 | AWGN-016, "
                        f"{active_awgn016_id}, red4 hydrophone 2 | "
                        f"AWGN-019, {active_awgn019_id}, "
                        "red2 hydrophone 3"):
                    if marker not in default_dom:
                        problems.append(
                            f"S23: browser did not render live marker "
                            f"'{marker}'")

            narrowed_query = urllib.parse.urlencode([
                ("experiment", awgn_ids[0]), ("nfft", "1024"),
                ("cp", "64"), ("code_rate", "0.25"),
                ("outer_spacing", "5"), ("inner_spacing", "5"),
                ("check_degree", "10"), ("horizon", "fill")])
            narrowed_dom, browser_error = browser_dom(
                base, "/awgn-results?" + narrowed_query)
            if narrowed_dom is None:
                problems.append(
                    f"S22: narrowed AWGN controls not checked: {browser_error}")
            elif "2 experiments match" not in narrowed_dom:
                problems.append(
                    "S22: CP64 rate-0.25 geometry did not narrow to two results")

            outer_query = urllib.parse.urlencode([
                ("experiment", outer_awgn_ids[0]), ("nfft", "1024"),
                ("cp", "64"), ("code_rate", "0.25"),
                ("outer_spacing", "10"), ("inner_spacing", "5"),
                ("check_degree", "10"), ("horizon", "fill")])
            outer_dom, browser_error = browser_dom(
                base, "/awgn-results?" + outer_query)
            if outer_dom is None:
                problems.append(
                    f"S22: outer-spacing controls not checked: {browser_error}")
            elif "1 experiments match" not in outer_dom:
                problems.append(
                    "S22: full outer-spacing geometry did not narrow to one")

            single_query = urllib.parse.urlencode([
                ("experiment", single_awgn_id), ("nfft", "4096"),
                ("cp", "64"), ("code_rate", "0.25"),
                ("outer_spacing", "5"), ("inner_spacing", "5"),
                ("check_degree", "10"), ("horizon", "fill")])
            single_dom, browser_error = browser_dom(
                base, "/awgn-results?" + single_query)
            if single_dom is None:
                problems.append(
                    f"S22: N4096 controls not checked: {browser_error}")
            elif "1 experiments match" not in single_dom:
                problems.append(
                    "S22: N4096 geometry did not narrow to one result")

            n4096_parameters = {
                "N": "4096", "CP": "64", "code rate": "0.25",
                "outer spacing": "5", "inner spacing": "5",
                "horizon": "fill",
            }
            n4096_family = tuple(
                experiment_id for experiment_id in awgn_ids
                if all(server._sweep_name_parameters(experiment_id).get(
                    field) == value
                       for field, value in n4096_parameters.items()))
            if set(n4096_family) != {single_awgn_id, *partial_awgn_ids}:
                problems.append(
                    "S22: N4096 check-degree family is not four results")
            expected_result_paths = [
                {
                    "value": f"red{channel}:{hydrophone}",
                    "label": f"red{channel} hydrophone {hydrophone}",
                }
                for channel in range(1, 5)
                for hydrophone in range(1, 4)
            ]
            for experiment_id, check in zip(partial_awgn_ids, (6, 12, 14)):
                paths_for_result = server._experiment_result_paths(
                    experiment_id)
                if paths_for_result != expected_result_paths:
                    problems.append(
                        f"S22: dc{check} result does not have all 12 paths")
                parameters = server._sweep_name_parameters(experiment_id)
                expected_parameters = dict(
                    n4096_parameters, **{"check degree": str(check)})
                if parameters != expected_parameters:
                    problems.append(
                        f"S22: dc{check} geometry was not parsed exactly")
            awgn017_parameters = dict(n4096_parameters, N="2048")
            for experiment_id, check in zip(awgn017_ids, (12, 14)):
                paths_for_result = server._experiment_result_paths(
                    experiment_id)
                if paths_for_result != expected_result_paths:
                    problems.append(
                        f"S22: AWGN-017 dc{check} result does not have "
                        "all 12 paths")
                parameters = server._sweep_name_parameters(experiment_id)
                expected_parameters = dict(
                    awgn017_parameters, **{"check degree": str(check)})
                if parameters != expected_parameters:
                    problems.append(
                        f"S22: AWGN-017 dc{check} geometry was not parsed "
                        "exactly")
            awgn018_parameters = dict(n4096_parameters, N="1024")
            for experiment_id, check in zip(awgn018_ids, (12, 14)):
                paths_for_result = server._experiment_result_paths(
                    experiment_id)
                if paths_for_result != expected_result_paths:
                    problems.append(
                        f"S22: AWGN-018 dc{check} result does not have "
                        "all 12 paths")
                parameters = server._sweep_name_parameters(experiment_id)
                expected_parameters = dict(
                    awgn018_parameters, **{"check degree": str(check)})
                if parameters != expected_parameters:
                    problems.append(
                        f"S22: AWGN-018 dc{check} geometry was not parsed "
                        "exactly")
            for experiment_id, (nfft, check) in zip(
                    awgn019_ids,
                    ((nfft, check) for nfft in (1024, 2048)
                     for check in (10, 12, 14))):
                paths_for_result = server._experiment_result_paths(
                    experiment_id)
                if paths_for_result != expected_result_paths:
                    problems.append(
                        f"S22: AWGN-019 N{nfft} dc{check} result does not "
                        "have all 12 paths")
                parameters = server._sweep_name_parameters(experiment_id)
                expected_parameters = {
                    "N": str(nfft), "CP": "64", "code rate": "0.25",
                    "outer spacing": "5", "inner spacing": "5",
                    "check degree": str(check), "horizon": "fill",
                }
                if parameters != expected_parameters:
                    problems.append(
                        f"S22: AWGN-019 N{nfft} dc{check} geometry was not "
                        "parsed exactly")

            selected_path_query = urllib.parse.urlencode([
                ("experiment", awgn_ids[0]), ("path", "red1:1")])
            selected_dom, browser_error = browser_dom(
                base, "/awgn-results?" + selected_path_query)
            if selected_dom is None:
                problems.append(
                    f"S22: AWGN path comparison not checked: {browser_error}")
            else:
                comparison_tag = _re.search(
                    r'<iframe id="comparison-result"([^>]*)>', selected_dom)
                single_tag = _re.search(
                    r'<iframe id="single-result"([^>]*)>', selected_dom)
                if ("54 plots match across experiments" not in selected_dom or
                        not comparison_tag or
                        "hidden" in comparison_tag.group(1) or
                        not single_tag or "hidden" not in single_tag.group(1)):
                    problems.append(
                        "S22: path selection did not replace the single view")

            comparison_query = urllib.parse.urlencode([
                *(("experiment", experiment_id)
                  for experiment_id in awgn_ids),
                ("path", "red1:1"),
            ])
            code, comparison = fetch(
                base, "/awgn-results/compare?" + comparison_query)
            if code != 200 or comparison.count(
                'class="experiment-result"') != 54:
                problems.append(
                    "S22: AWGN comparison did not render all 54 AWGN panels")
            for experiment_id in awgn_ids:
                present = (f'data-contract-experiment="{experiment_id}"'
                           in comparison)
                if not present:
                    problems.append(
                        f"S22: red1 comparison scope differs for "
                        f"'{experiment_id}'")
            if 'data-contract-path="red2 1"' in comparison:
                problems.append(
                    "S22: AWGN comparison retained a different path")
            for channel in range(1, 5):
                for hydrophone in range(1, 4):
                    expected_panels = 54
                    path_query = urllib.parse.urlencode([
                        *(("experiment", experiment_id)
                          for experiment_id in awgn_ids),
                        ("path", f"red{channel}:{hydrophone}"),
                    ])
                    code, path_comparison = fetch(
                        base, "/awgn-results/compare?" + path_query)
                    if (code != 200 or path_comparison.count(
                            'class="experiment-result"') != expected_panels or
                            f'data-contract-path="red{channel} '
                            f'{hydrophone}"' not in path_comparison):
                        problems.append(
                            f"S22: AWGN comparison did not render "
                            f"{expected_panels} panels "
                            f"for red{channel} hydrophone {hydrophone}")
            overflow_query = urllib.parse.urlencode(
                [("experiment", experiment_id) for experiment_id in awgn_ids]
                + [("experiment", awgn_ids[0])] * (65 - len(awgn_ids))
                + [("path", "red1:1")])
            code, _ = fetch(
                base, "/awgn-results/compare?" + overflow_query)
            if code != 404:
                problems.append(
                    "S22: AWGN comparison accepted more than 64 IDs")

            bad_query = urllib.parse.urlencode([
                ("experiment", impulsive_id), ("path", "red1:1")])
            code, _ = fetch(base, "/awgn-results/compare?" + bad_query)
            if code != 404:
                problems.append(
                    "S22: AWGN comparison accepted an impulsive experiment")
            unknown_path = urllib.parse.urlencode([
                ("experiment", awgn_ids[0]), ("path", "red9:9")])
            code, _ = fetch(base, "/awgn-results/compare?" + unknown_path)
            if code != 404:
                problems.append("S22: AWGN comparison accepted an unknown path")
            unsafe = urllib.parse.urlencode([
                ("experiment", "../outside"), ("path", "red1:1")])
            code, _ = fetch(base, "/awgn-results/compare?" + unsafe)
            if code != 404:
                problems.append("S22: AWGN comparison accepted an unsafe ID")

            for suffix in ("view", "manifest"):
                code, body = fetch(
                    base, f"/awgn-results/{suffix}?experiment={selected}")
                if code != 200:
                    problems.append(
                        f"S22: /awgn-results/{suffix} returned {code}")
                if "alpha-stable" in body:
                    problems.append(
                        f"S22: /awgn-results/{suffix} exposed impulsive data")
                bad = urllib.parse.quote(impulsive_id, safe="")
                code, _ = fetch(
                    base, f"/awgn-results/{suffix}?experiment={bad}")
                if code != 404:
                    problems.append(
                        f"S22: /awgn-results/{suffix} accepted impulsive data")

            awgn_bad = urllib.parse.quote(awgn_ids[0], safe="")
            for route in ("", "/view", "/manifest"):
                code, _ = fetch(
                    base, f"/results{route}?experiment={awgn_bad}")
                if code != 404:
                    problems.append(
                        f"S22: /results{route} accepted an AWGN experiment")
            code, _ = fetch(base, "/results/compare?" + comparison_query)
            if code != 404:
                problems.append("S22: /results/compare accepted AWGN data")

            impulsive_bad = urllib.parse.quote(impulsive_id, safe="")
            code, _ = fetch(
                base, f"/awgn-results?experiment={impulsive_bad}")
            if code != 404:
                problems.append(
                    "S22: /awgn-results accepted an impulsive experiment")
            for experiment_id in invalid_ids:
                encoded = urllib.parse.quote(experiment_id, safe="")
                for prefix in ("/results", "/awgn-results"):
                    for route in ("", "/view", "/manifest"):
                        code, _ = fetch(
                            base, f"{prefix}{route}?experiment={encoded}")
                        if code != 404:
                            problems.append(
                                f"S22: {prefix}{route} accepted invalid "
                                f"manifest '{experiment_id}'")

            # S23 live campaign progress is computed from final result files.
            # Historical campaigns promote aggregate/trace pairs. AWGN-019
            # and AWGN-020 additionally promote a per-path contract after
            # validation.
            code, progress_body = fetch(base, "/api/awgn-results/progress")
            if code != 200:
                problems.append(
                    f"S23: /api/awgn-results/progress returned {code}")
            else:
                progress = json.loads(progress_body).get("data", {})
                expected = {
                    "campaign_ids": [
                        "AWGN-008", "AWGN-009", "AWGN-012", "AWGN-015",
                        "AWGN-016", "AWGN-017", "AWGN-018", "AWGN-019",
                        "AWGN-020"],
                    "total_configurations": 51,
                    "total_paths": 612,
                    "completed_configurations": 2,
                    "completed_paths": 26,
                    "active_paths": [
                        {
                            "campaign_id": "AWGN-009",
                            "experiment_id": active_id,
                            "channel": "red1",
                            "hydrophone": 2,
                        },
                        {
                            "campaign_id": "AWGN-016",
                            "experiment_id": active_awgn016_id,
                            "channel": "red4",
                            "hydrophone": 2,
                        },
                        {
                            "campaign_id": "AWGN-019",
                            "experiment_id": active_awgn019_id,
                            "channel": "red2",
                            "hydrophone": 3,
                        },
                    ],
                    "matrix_complete": False,
                    "state": "running",
                }
                for key, value in expected.items():
                    if progress.get(key) != value:
                        problems.append(
                            f"S23: progress {key}={progress.get(key)!r}, "
                            f"expected {value!r}")
                expected_campaigns = {
                    "AWGN-008": ("0.25", 5, 12, 1, "running", 144, 12),
                    "AWGN-009": ("0.125", 5, 12, 1, "running", 144, 12),
                    "AWGN-012": ("0.25", 10, 0, 0, "queued", 144, 12),
                    "AWGN-015": ("0.25", 5, 0, 0, "queued", 12, 1),
                    "AWGN-016": ("0.25", 5, 2, 0, "running", 36, 3),
                    "AWGN-017": ("0.25", 5, 0, 0, "queued", 24, 2),
                    "AWGN-018": ("0.25", 5, 0, 0, "queued", 24, 2),
                    "AWGN-019": ("0.25", 5, 0, 0, "running", 72, 6),
                    "AWGN-020": ("0.25", 5, 0, 0, "queued", 12, 1),
                }
                campaigns = {item.get("campaign_id"): item
                             for item in progress.get("campaigns", [])}
                for campaign_id, values in expected_campaigns.items():
                    item = campaigns.get(campaign_id, {})
                    actual = (
                        item.get("code_rate"), item.get("outer_spacing"),
                        item.get("completed_paths"),
                        item.get("completed_configurations"),
                        item.get("state"), item.get("total_paths"),
                        item.get("total_configurations"))
                    if actual != values:
                        problems.append(
                            f"S23: {campaign_id} progress {actual!r}, "
                            f"expected {values!r}")
                expected_percent = 100 * 26 / 612
                if abs(progress.get("percent", -1) - expected_percent) > 1e-9:
                    problems.append(
                        "S23: progress percent does not match completed work")
            open(awgn019_contract, "w").close()
            code, contracted_body = fetch(
                base, "/api/awgn-results/progress")
            if code != 200:
                problems.append(
                    "S23: progress failed after AWGN-019 contract promotion")
            else:
                contracted = json.loads(contracted_body).get("data", {})
                campaigns = {
                    item.get("campaign_id"): item
                    for item in contracted.get("campaigns", [])}
                awgn019 = campaigns.get("AWGN-019", {})
                if (contracted.get("completed_paths") != 27 or
                        awgn019.get("completed_paths") != 1):
                    problems.append(
                        "S23: AWGN-019 final contract did not promote exactly "
                        "one completed path")
            open(awgn020_contract, "w").close()
            code, contracted020_body = fetch(
                base, "/api/awgn-results/progress")
            if code != 200:
                problems.append(
                    "S23: progress failed after AWGN-020 contract promotion")
            else:
                contracted020 = json.loads(contracted020_body).get("data", {})
                campaigns = {
                    item.get("campaign_id"): item
                    for item in contracted020.get("campaigns", [])}
                awgn020 = campaigns.get("AWGN-020", {})
                if (contracted020.get("completed_paths") != 28 or
                        awgn020.get("completed_paths") != 1):
                    problems.append(
                        "S23: AWGN-020 final contract did not promote exactly "
                        "one completed path")
            state_helper = getattr(server, "_awgn_overall_state", None)
            if state_helper is None:
                problems.append("S23: missing truthful overall-state helper")
            else:
                complete = {"state": "complete", "matrix_complete": True,
                            "completed_paths": 612}
                queued = {"state": "queued", "matrix_complete": False,
                          "completed_paths": 0}
                not_started = {"state": "not-started",
                               "matrix_complete": False,
                               "completed_paths": 0}
                if state_helper([complete, queued], False) != "queued":
                    problems.append(
                        "S23: completed campaigns mask a queued campaign")
                if state_helper([complete, not_started], False) != "not-started":
                    problems.append(
                        "S23: completed campaigns mask a not-started campaign")
            for marker in (
                    'id="awgn-live-progress"',
                    'id="awgn-progress-bar"',
                    'max="612"',
                    "AWGN-008, AWGN-009, AWGN-012, AWGN-015, AWGN-016, "
                    "AWGN-017, AWGN-018, AWGN-019, and AWGN-020 real-time "
                    "progress",
                    "fetch('/api/awgn-results/progress'",
                    "setTimeout(pollAwgnProgress, 2000)"):
                if marker not in awgn_page:
                    problems.append(
                        f"S23: AWGN page lost live progress marker '{marker}'")
            if 'id="awgn-live-progress"' not in awgn_empty:
                problems.append(
                    "S23: empty AWGN page has no live progress block")
            if 'id="awgn-live-progress"' in results_page:
                problems.append(
                    "S23: live AWGN progress leaked onto /results")
    finally:
        server.ROOT = original_root

    httpd.shutdown()
    return problems


if __name__ == "__main__":
    problems = check()
    if problems:
        print("SERVER CONTRACT FAILURES:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("server contract: PASS (S1-S23)")
