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
    AWGN-016, AWGN-017, AWGN-018, AWGN-019, AWGN-020, AWGN-021, AWGN-022,
    AWGN-023B, AWGN-023C, AWGN-024, AWGN-025, AWGN-026, and AWGN-027 progress
    backed by a read-only provenance-wrapped API. The API counts their 708 approved paths,
    using each campaign's fixed aggregate, trace, and path-contract names, and
    the browser polls it every two seconds without counting historical results.
S24 /no-harm-results retains the Results controls but admits only AWGN
    manifests that explicitly declare CRC no-harm behavior for both protected
    receivers; its view, manifest, and comparison routes enforce the same gate.
    Each declared result also exposes a selectable-SNR effective-payload-rate
    figure with twelve channel/hydrophone panels and five receiver bars per
    panel. Each effective-rate panel links to a strict grouped-bar comparison
    that holds every configuration field fixed except N and pilot geometry.
    A matched-family best-observed view renders twelve maximum-rate envelopes,
    resolves equal-rate receivers in the approved decoding-time order, retains
    configuration ties, shows outages and near ties, and links every path/SNR
    cell back to the grouped-bar detail.
"""
import html
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
              "Health", "Progress", "No-harm results"]
REMOVED_NAV_LINKS = [("/results", "Results"),
                     ("/awgn-results", "AWGN results")]
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


def nav_fragment(document):
    """Return only the shell navigation markup."""
    if "<nav>" not in document or "</nav>" not in document:
        return ""
    return document.split("<nav>", 1)[1].split("</nav>", 1)[0]

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
        navigation = nav_fragment(text)
        if code != 200:
            problems.append(f"S1: {path} returned {code}")
        for label in NAV_LABELS:
            if f">{label}</a>" not in navigation:
                problems.append(f"S1: {path} lost nav label '{label}'")
        for href, label in REMOVED_NAV_LINKS:
            if f'<a href="{href}"' in navigation:
                problems.append(
                    f"S1: {path} retained removed nav label '{label}'")
    palette_pages = {
        (item["href"], item["label"])
        for item in server.palette_index()
        if item["kind"] == "page"
    }
    for href, label in REMOVED_NAV_LINKS:
        if (href, label) not in palette_pages:
            problems.append(
                f"S1: removed tab '{label}' is no longer reachable through "
                "the command palette")

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
        expected_facades = {
            "JunaStandard", "JunaPartialFFT", "JunaLite",
            "JunaProfiledCzFrame", "JunaCrcProfiledCzFrame",
            "JunaCrcConditionedJointCwzFrame",
        }
        if {f["name"] for f in detail.get("facades", [])} != expected_facades:
            problems.append(
                "S15: type inspector public facades differ from the catalog")
    source_js = open(os.path.join(HERE, "static", "source.js")).read()
    for marker in ("Static call edge", "doubleClick", "Fields (",
                   "Open in original analyzer"):
        if marker not in source_js:
            problems.append(f"S15: source interaction lost '{marker}'")
    for facade, receiver_id in (
            ("JunaProfiledCzFrame", "profiled_cz"),
            ("JunaCrcProfiledCzFrame", "profiled_cz"),
            ("JunaCrcConditionedJointCwzFrame",
             "conditioned_joint_cwz")):
        marker = f'{facade}: "{receiver_id}"'
        if marker not in source_js:
            problems.append(
                f"S15: Source facade link lost {facade} mapping")

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

    for receiver_id, display_name in (
            ("profiled_cz", "Profiled C,z"),
            ("conditioned_joint_cwz", "Conditioned joint C,W,z")):
        code, text = fetch(base, f"/api/graph?receiver={receiver_id}")
        graph = json.loads(text).get("data", {}) if code == 200 else {}
        expected = {
            "stage:" + stage_id
            for receiver in chain["receivers"]
            if receiver["id"] == receiver_id
            for stage_id in receiver["path"] + receiver.get(
                "optional_stages", [])
        }
        if graph.get("view") != "stages":
            problems.append(
                f"S18: {display_name} graph does not default to stage view")
        if {node.get("id") for node in graph.get("nodes", [])} != expected:
            problems.append(
                f"S18: {display_name} graph differs from its declared stage DAG")

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
    if "<h1>AWGN results</h1>" not in awgn_empty:
        problems.append("S22: /awgn-results lost its page heading")
    awgn_navigation = nav_fragment(awgn_empty)
    for href, label in REMOVED_NAV_LINKS:
        if f'<a href="{href}"' in awgn_navigation:
            problems.append(
                f"S22: /awgn-results retained removed tab '{label}'")

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
                panels = []
                for path in result_paths:
                    channel, hydrophone = path.rsplit(" ", 1)
                    suffix = (" — fixture configuration"
                              if path == "red4 3" else "")
                    panels.append(
                        '<figure class="panel"><figcaption>'
                        f'<b>{channel} hydrophone {hydrophone}{suffix}</b>'
                        '</figcaption>'
                        f'<svg data-contract-experiment="{experiment_id}" '
                        f'data-contract-path="{path}"></svg></figure>')
                panels = "".join(panels)
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

            # S24 no-harm results require an explicit manifest declaration,
            # not a matching experiment-directory name. Exercise both
            # retained manifest schemas.
            no_harm_ids = (
                legacy_awgn_ids[0], rate_awgn_ids[7], rate_awgn_ids[0],
                legacy_awgn_ids[2], rate_awgn_ids[15],
                rate_awgn_ids[21], outer_awgn_ids[2])
            modern_manifest_path = os.path.join(
                experiments, no_harm_ids[0], "results",
                "results_manifest.json")
            with open(modern_manifest_path, encoding="utf-8") as handle:
                modern_manifest = json.load(handle)
            modern_manifest["source_contract"] = {
                "receivers": [
                    {"id": "lite", "crc_no_harm": False},
                    {"id": "profiled_cz", "crc_no_harm": True},
                    {"id": "cwz_joint", "crc_no_harm": True},
                ],
                "selection_reasons": [
                    "standard_crc_valid", "crc_rescue",
                    "standard_fallback",
                ],
            }
            modern_manifest["receiver_policy"] = {
                "lite": "unchanged",
                "profiled_cz": "CRC no-harm",
                "cwz_joint": "CRC no-harm",
            }
            modern_manifest["frames_per_point"] = 8
            modern_manifest["capture_time_seconds"] = [0.0, 8.0]
            modern_manifest["geometry"] = {
                "nfft": "1024", "code_rate": "0.25",
                "outer_spacing": "5", "inner_spacing": "5",
                "cp": "128", "check_degree": "10", "horizon": "0",
            }
            modern_manifest["seed"] = 4
            modern_manifest["partial_fft_parts"] = 4
            modern_manifest["configured_frame_duration_seconds"] = 1.0
            modern_manifest["protected_receivers"] = [
                "profiled_cz", "cwz_joint"]
            with open(modern_manifest_path, "w", encoding="utf-8") as handle:
                json.dump(modern_manifest, handle)

            # UI-037 needs two otherwise-identical retained configurations
            # whose only comparison dimension is N.
            for sibling_id, nfft, outer, inner in (
                    (no_harm_ids[3], "2048", "5", "5"),
                    (no_harm_ids[4], "1024", "5", "10"),
                    (no_harm_ids[5], "2048", "5", "10"),
                    (no_harm_ids[6], "1024", "10", "5")):
                sibling_manifest_path = os.path.join(
                    experiments, sibling_id, "results",
                    "results_manifest.json")
                sibling_manifest = dict(modern_manifest)
                sibling_manifest["experiment_id"] = sibling_id
                sibling_manifest["geometry"] = dict(
                    modern_manifest["geometry"])
                sibling_parameters = server._sweep_name_parameters(sibling_id)
                sibling_manifest["geometry"].update({
                    "nfft": nfft,
                    "outer_spacing": outer,
                    "inner_spacing": inner,
                    "cp": sibling_parameters["CP"],
                    "code_rate": sibling_parameters["code rate"],
                    "check_degree": sibling_parameters["check degree"],
                    "horizon": "0",
                })
                with open(
                        sibling_manifest_path, "w",
                        encoding="utf-8") as handle:
                    json.dump(sibling_manifest, handle)
            rule_manifest_path = os.path.join(
                experiments, no_harm_ids[1], "results",
                "results_manifest.json")
            with open(rule_manifest_path, encoding="utf-8") as handle:
                rule_manifest = json.load(handle)
            rule_manifest["no_harm_rule"] = {
                "standard_crc_valid": "return standard",
                "crc_rescue": "return certified rescue",
                "standard_fallback": "return standard",
            }
            rule_manifest["receiver_policy"] = {
                "lite": "unchanged",
                "profiled_cz": "CRC-gated no-harm C+z",
                "cwz_joint": "CRC-gated no-harm C+W+z",
            }
            rule_manifest["frames_per_point"] = 32
            rule_manifest["capture_time_seconds"] = [0.0, 47.0]
            rule_parameters = server._sweep_name_parameters(no_harm_ids[1])
            rule_manifest["geometry"] = {
                "nfft": "2048", "code_rate": "0.125",
                "outer_spacing": "5", "inner_spacing": "10",
                "cp": rule_parameters["CP"],
                "check_degree": rule_parameters["check degree"],
                "horizon": "0",
            }
            rule_manifest["selection_reason_counts"] = {
                receiver: {
                    "standard_crc_valid": 1,
                    "crc_rescue": 1,
                    "standard_fallback": 1,
                }
                for receiver in ("profiled_cz", "cwz_joint")
            }
            rule_manifest.pop("paths")
            rule_manifest["sources"] = [
                {
                    "path": (
                        f"runs/red{channel}_hydrophone{hydrophone}/"
                        "red_snr_sweep_awgn_configuration.csv"),
                    "rows": 80,
                    "sha256": "0" * 64,
                }
                for channel in range(1, 5)
                for hydrophone in range(1, 4)
            ]
            with open(rule_manifest_path, "w", encoding="utf-8") as handle:
                json.dump(rule_manifest, handle)

            third_manifest_path = os.path.join(
                experiments, no_harm_ids[2], "results",
                "results_manifest.json")
            with open(third_manifest_path, encoding="utf-8") as handle:
                third_manifest = json.load(handle)
            third_manifest["source_contract"] = modern_manifest[
                "source_contract"]
            third_manifest["receiver_policy"] = {
                "lite": "unchanged",
                "profiled_cz": "CRC-gated no-harm C+z",
                "cwz_joint": "CRC-gated no-harm C+W+z",
            }
            third_manifest["protected_receivers"] = [
                "profiled_cz", "cwz_joint"]
            third_manifest["frames_per_point"] = 32
            third_manifest["capture_time_seconds"] = [0.0, 32.0]
            third_manifest["geometry"] = {
                "nfft": "1024", "code_rate": "0.125",
                "outer_spacing": "5", "inner_spacing": "5",
                "cp": "64", "check_degree": "10", "horizon": "0",
            }
            with open(third_manifest_path, "w", encoding="utf-8") as handle:
                json.dump(third_manifest, handle)

            # UI-032/UI-033: each declared no-harm result has one aggregate
            # table from which the selected-SNR effective-payload-rate figure
            # is rendered. Values are deliberately distinct across SNR and
            # receiver so the route cannot pass by drawing one shared payload
            # ceiling or by silently retaining the 20 dB rows.
            receiver_ids = (
                "ofdm_fec", "pfft", "lite", "profiled_cz", "cwz_joint")
            for experiment_index, experiment_id in enumerate(no_harm_ids):
                aggregate_path = os.path.join(
                    experiments, experiment_id, "results",
                    "contract_effective_rate.csv")
                with open(aggregate_path, "w", encoding="utf-8") as handle:
                    handle.write(
                        "channel,lane,snr_db,algorithm_id,"
                        "effective_rate_bps,frames,successful_frames\n")
                    for snr_db in range(0, 31, 2):
                        for channel in range(1, 5):
                            for hydrophone in range(1, 4):
                                for receiver_index, receiver_id in enumerate(
                                        receiver_ids):
                                    rate = (1000 + 100 * experiment_index +
                                            10 * channel + hydrophone +
                                            receiver_index / 10 +
                                            25 * (snr_db - 20))
                                    if (experiment_id == no_harm_ids[1] and
                                            snr_db == 14 and channel == 1 and
                                            hydrophone == 1):
                                        rate = 0.0
                                    elif (experiment_id == no_harm_ids[0] and
                                          snr_db == 14 and channel == 1 and
                                          hydrophone == 1 and
                                          receiver_id == "pfft"):
                                        rate = 0.0
                                    # UI-040 fixes four ranking cases in one
                                    # matched family without changing the
                                    # selected-SNR values used above: outage,
                                    # exact tie, unique winner, and near tie.
                                    if (experiment_index in (0, 3, 4, 5, 6)
                                            and channel == 1 and
                                            hydrophone == 1):
                                        if snr_db == 0:
                                            rate = 0.0
                                        elif snr_db == 2:
                                            rate = min(rate, 1100.0)
                                            if (experiment_index == 4 and
                                                    receiver_id in (
                                                        "lite", "profiled_cz",
                                                        "cwz_joint")):
                                                rate = 1200.0
                                        elif snr_db == 4:
                                            rate = min(rate, 1200.0)
                                            if (experiment_index == 5 and
                                                    receiver_id == "ofdm_fec"):
                                                rate = 1300.0
                                        elif snr_db in (6, 8):
                                            rate = min(rate, 1100.0)
                                            if (experiment_index == 6 and
                                                    receiver_id == "ofdm_fec"):
                                                rate = 1400.0
                                            elif (experiment_index == 4 and
                                                  receiver_id == "lite"):
                                                rate = 1399.0
                                        elif snr_db == 10:
                                            rate = min(rate, 1150.0)
                                            if (experiment_index == 4 and
                                                    receiver_id == "lite"):
                                                rate = 1500.0
                                            elif (experiment_index == 5 and
                                                  receiver_id ==
                                                  "profiled_cz"):
                                                rate = 1500.0
                                        elif snr_db == 12:
                                            rate = min(rate, 1200.0)
                                            if (experiment_index in (4, 5) and
                                                    receiver_id == "lite"):
                                                rate = 1600.0
                                            elif (experiment_index == 5 and
                                                  receiver_id ==
                                                  "profiled_cz"):
                                                rate = 1600.0
                                    elif (experiment_index == 2 and
                                          channel == 1 and hydrophone == 1 and
                                          snr_db == 10):
                                        rate = 9999.0
                                    frame_count = (8 if experiment_index in
                                                   (0, 3, 4, 5, 6) else 32)
                                    successful_frames = (
                                        0 if rate == 0 else
                                        max(1, min(frame_count,
                                                   int(rate // 180))))
                                    handle.write(
                                        f"red{channel},{hydrophone},{snr_db},"
                                        f"{receiver_id},{rate:.1f},"
                                        f"{frame_count},{successful_frames}\n")

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
            awgn021_harness_name = (
                "2026-08-10-red-awgn-first16s-frames16-crc-no-harm-"
                "n1024-cp64-rate025-p5-5-dc14-kfill-pfft4")
            awgn022_harness_name = (
                "2026-08-10-red-awgn-first32s-frames32-crc-no-harm-"
                "n1024-cp64-rate025-p5-5-dc14-kfill-pfft4")
            awgn023b_harness_name = (
                "2026-08-10-red-awgn-full-capture-frames47-crc-no-harm-"
                "n1024-cp64-rate025-p5-5-dc14-kfill-pfft4")
            awgn023c_harness_name = (
                "2026-08-10-red-awgn-repeated-first32s-frames128-crc-no-harm-"
                "n1024-cp64-rate025-p5-5-dc14-kfill-pfft4")
            awgn024_harness_name = (
                "2026-08-10-red-awgn-first32s-frames32-rate05-crc-no-harm-"
                "n1024-cp64-rate05-p5-5-dc14-kfill-pfft4")
            awgn025_harness_name = (
                "2026-08-10-red-awgn-full-capture-frames47-rate05-"
                "crc-no-harm-n1024-cp64-rate05-p5-5-dc14-kfill-pfft4")
            awgn026_harness_name = (
                "2026-08-10-red-awgn-full-capture-frames47-p10-10-"
                "crc-no-harm-n1024-cp64-rate025-p10-10-dc14-kfill-pfft4")
            awgn027_harness_name = (
                "2026-08-10-red-awgn-full-capture-frames47-crc-no-harm-"
                "n2048-cp64-rate05-p10-10-dc14-kfill-pfft4")
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
            progress_ids["AWGN-021"] = (awgn021_harness_name,)
            progress_ids["AWGN-022"] = (awgn022_harness_name,)
            progress_ids["AWGN-023B"] = (awgn023b_harness_name,)
            progress_ids["AWGN-023C"] = (awgn023c_harness_name,)
            progress_ids["AWGN-024"] = (awgn024_harness_name,)
            progress_ids["AWGN-025"] = (awgn025_harness_name,)
            progress_ids["AWGN-026"] = (awgn026_harness_name,)
            progress_ids["AWGN-027"] = (awgn027_harness_name,)
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
            # AWGN-021 likewise uses its own first-16-second aggregate and
            # does not promote a path until its final contract is present.
            awgn021_contract_dir = os.path.join(
                experiments, progress_ids["AWGN-021"][0], "results", "runs",
                "red1_hydrophone1")
            os.makedirs(awgn021_contract_dir)
            open(os.path.join(
                awgn021_contract_dir,
                "red_snr_sweep_awgn_first16s_frames16_configuration.csv"),
                "w").close()
            open(os.path.join(
                awgn021_contract_dir,
                "red1_hydrophone1_selection_trace.csv"), "w").close()
            awgn021_contract = os.path.join(
                awgn021_contract_dir, "awgn021_path_contract.txt")
            # AWGN-022 uses its own first-32-second aggregate and likewise
            # requires the final validation contract before path promotion.
            awgn022_contract_dir = os.path.join(
                experiments, progress_ids["AWGN-022"][0], "results", "runs",
                "red1_hydrophone1")
            os.makedirs(awgn022_contract_dir)
            open(os.path.join(
                awgn022_contract_dir,
                "red_snr_sweep_awgn_first32s_frames32_configuration.csv"),
                "w").close()
            open(os.path.join(
                awgn022_contract_dir,
                "red1_hydrophone1_selection_trace.csv"), "w").close()
            awgn022_contract = os.path.join(
                awgn022_contract_dir, "awgn022_path_contract.txt")
            # AWGN-023B and AWGN-023C each require their campaign-specific
            # aggregate, selection trace, and final path contract.
            awgn023b_contract_dir = os.path.join(
                experiments, progress_ids["AWGN-023B"][0], "results", "runs",
                "red1_hydrophone1")
            os.makedirs(awgn023b_contract_dir)
            open(os.path.join(
                awgn023b_contract_dir,
                "red_snr_sweep_awgn_full_capture_frames47_configuration.csv"),
                "w").close()
            open(os.path.join(
                awgn023b_contract_dir,
                "red1_hydrophone1_selection_trace.csv"), "w").close()
            awgn023b_contract = os.path.join(
                awgn023b_contract_dir, "awgn023b_path_contract.txt")
            awgn023c_contract_dir = os.path.join(
                experiments, progress_ids["AWGN-023C"][0], "results", "runs",
                "red1_hydrophone1")
            os.makedirs(awgn023c_contract_dir)
            open(os.path.join(
                awgn023c_contract_dir,
                "red_snr_sweep_awgn_repeated_first32s_frames128_"
                "configuration.csv"), "w").close()
            open(os.path.join(
                awgn023c_contract_dir,
                "red1_hydrophone1_selection_trace.csv"), "w").close()
            awgn023c_contract = os.path.join(
                awgn023c_contract_dir, "awgn023c_path_contract.txt")
            awgn024_contract_dir = os.path.join(
                experiments, progress_ids["AWGN-024"][0], "results", "runs",
                "red1_hydrophone1")
            os.makedirs(awgn024_contract_dir)
            open(os.path.join(
                awgn024_contract_dir,
                "red_snr_sweep_awgn_first32s_frames32_configuration.csv"),
                "w").close()
            open(os.path.join(
                awgn024_contract_dir,
                "red1_hydrophone1_selection_trace.csv"), "w").close()
            awgn024_contract = os.path.join(
                awgn024_contract_dir, "awgn024_path_contract.txt")
            awgn025_contract_dir = os.path.join(
                experiments, progress_ids["AWGN-025"][0], "results", "runs",
                "red1_hydrophone1")
            os.makedirs(awgn025_contract_dir)
            open(os.path.join(
                awgn025_contract_dir,
                "red_snr_sweep_awgn_full_capture_frames47_configuration.csv"),
                "w").close()
            open(os.path.join(
                awgn025_contract_dir,
                "red1_hydrophone1_selection_trace.csv"), "w").close()
            awgn025_contract = os.path.join(
                awgn025_contract_dir, "awgn025_path_contract.txt")
            awgn026_contract_dir = os.path.join(
                experiments, progress_ids["AWGN-026"][0], "results", "runs",
                "red1_hydrophone1")
            os.makedirs(awgn026_contract_dir)
            open(os.path.join(
                awgn026_contract_dir,
                "red_snr_sweep_awgn_full_capture_frames47_configuration.csv"),
                "w").close()
            open(os.path.join(
                awgn026_contract_dir,
                "red1_hydrophone1_selection_trace.csv"), "w").close()
            awgn026_contract = os.path.join(
                awgn026_contract_dir, "awgn026_path_contract.txt")
            awgn027_contract_dir = os.path.join(
                experiments, progress_ids["AWGN-027"][0], "results", "runs",
                "red1_hydrophone1")
            os.makedirs(awgn027_contract_dir)
            open(os.path.join(
                awgn027_contract_dir,
                "red_snr_sweep_awgn_full_capture_frames47_configuration.csv"),
                "w").close()
            open(os.path.join(
                awgn027_contract_dir,
                "red1_hydrophone1_selection_trace.csv"), "w").close()
            awgn027_contract = os.path.join(
                awgn027_contract_dir, "awgn027_path_contract.txt")
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
            awgn021_harness = os.path.join(
                experiments, awgn021_harness_name)
            awgn022_harness = os.path.join(
                experiments, awgn022_harness_name)
            awgn023b_harness = os.path.join(
                experiments, awgn023b_harness_name)
            awgn023c_harness = os.path.join(
                experiments, awgn023c_harness_name)
            awgn024_harness = os.path.join(
                experiments, awgn024_harness_name)
            awgn025_harness = os.path.join(
                experiments, awgn025_harness_name)
            awgn026_harness = os.path.join(
                experiments, awgn026_harness_name)
            awgn027_harness = os.path.join(
                experiments, awgn027_harness_name)
            os.makedirs(baseline_harness)
            os.makedirs(rate_harness)
            os.makedirs(outer_harness)
            os.makedirs(awgn015_harness, exist_ok=True)
            os.makedirs(awgn016_harness, exist_ok=True)
            os.makedirs(awgn017_harness, exist_ok=True)
            os.makedirs(awgn018_harness, exist_ok=True)
            os.makedirs(awgn019_harness, exist_ok=True)
            os.makedirs(awgn020_harness, exist_ok=True)
            os.makedirs(awgn021_harness, exist_ok=True)
            os.makedirs(awgn022_harness, exist_ok=True)
            os.makedirs(awgn023b_harness, exist_ok=True)
            os.makedirs(awgn023c_harness, exist_ok=True)
            os.makedirs(awgn024_harness, exist_ok=True)
            os.makedirs(awgn025_harness, exist_ok=True)
            os.makedirs(awgn026_harness, exist_ok=True)
            os.makedirs(awgn027_harness, exist_ok=True)
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
            with open(os.path.join(awgn021_harness, "awgn021_sweep.log"),
                      "w", encoding="utf-8") as handle:
                handle.write(
                    "AWGN_021_QUEUE_START 2026-08-10T00:00:00+08:00\n")
            with open(os.path.join(awgn022_harness, "awgn022_sweep.log"),
                      "w", encoding="utf-8") as handle:
                handle.write(
                    "AWGN_022_QUEUE_START 2026-08-10T00:00:00+08:00\n")
            with open(os.path.join(awgn023b_harness, "awgn023b_sweep.log"),
                      "w", encoding="utf-8") as handle:
                handle.write(
                    "AWGN_023B_QUEUE_START 2026-08-10T00:00:00+08:00\n")
            with open(os.path.join(awgn023c_harness, "awgn023c_sweep.log"),
                      "w", encoding="utf-8") as handle:
                handle.write(
                    "AWGN_023C_COMPUTE_START 2026-08-10T00:00:00+08:00\n"
                    f"PATH_START AWGN-023C {awgn023c_harness_name} "
                    "red3 hydrophone 2\n")
            with open(os.path.join(awgn024_harness, "awgn024_sweep.log"),
                      "w", encoding="utf-8") as handle:
                handle.write(
                    "AWGN_024_QUEUE_START 2026-08-10T00:00:00+08:00\n")
            with open(os.path.join(awgn025_harness, "awgn025_sweep.log"),
                      "w", encoding="utf-8") as handle:
                handle.write(
                    "AWGN_025_QUEUE_START 2026-08-10T00:00:00+08:00\n")
            with open(os.path.join(awgn026_harness, "awgn026_sweep.log"),
                      "w", encoding="utf-8") as handle:
                handle.write(
                    "AWGN_026_QUEUE_START 2026-08-10T00:00:00+08:00\n")
            with open(os.path.join(awgn027_harness, "awgn027_sweep.log"),
                      "w", encoding="utf-8") as handle:
                handle.write(
                    "AWGN_027_QUEUE_START 2026-08-10T00:00:00+08:00\n")
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

            # S24 exposes the same controls on a separate page, but only for
            # manifests that explicitly declare the CRC no-harm behavior.
            no_harm_selected = urllib.parse.quote(no_harm_ids[0], safe="")
            code, no_harm_page = fetch(
                base, f"/no-harm-results?experiment={no_harm_selected}")
            if code != 200:
                problems.append(
                    f"S24: populated /no-harm-results returned {code}")
            for marker in (
                    "<h1>No-harm results</h1>", ">No-harm results</a>",
                    '<select id="experiment-picker"',
                    'id="experiment-picker" onchange="var url = new '
                    'window.URL(location.href);',
                    'id="plot-picker" onchange="var url = new '
                    'window.URL(location.href);',
                    'id="sweep-parameters"',
                    'id="sweep-parameter-controls"',
                    '<select id="path-filter"',
                    'return "/no-harm-results/compare?"'):
                if marker not in no_harm_page:
                    problems.append(
                        f"S24: no-harm page lost marker '{marker}'")
            for marker in (
                    'id="awgn-live-progress"',
                    '<strong>Unregistered experiment output.</strong>',
                    "fetch('/api/awgn-results/progress'"):
                if marker in no_harm_page:
                    problems.append(
                        f"S24: no-harm page retained removed pane '{marker}'")
            no_harm_navigation = nav_fragment(no_harm_page)
            for href, label in REMOVED_NAV_LINKS:
                if f'<a href="{href}"' in no_harm_navigation:
                    problems.append(
                        f"S24: no-harm page retained removed tab '{label}'")
            compact_query = urllib.parse.urlencode([
                ("experiment", no_harm_ids[0]), ("page", "summary"),
                ("layout", "compact-four"),
            ])
            compact_view_url = "/no-harm-results/view?" + compact_query
            normal_view_url = (
                "/no-harm-results/view?" + urllib.parse.urlencode([
                    ("experiment", no_harm_ids[0]), ("page", "summary"),
                ]))
            if (f'<iframe id="single-result" src="{compact_view_url}"' not in
                    no_harm_page or
                    f'<a id="results-open" href="{normal_view_url}"' not in
                    no_harm_page):
                problems.append(
                    "S24: embedded no-harm view is not compact while the "
                    "own-tab link remains full size")

            fixture_view_path = os.path.join(
                experiments, no_harm_ids[0], "results", "results_view.html")
            with open(fixture_view_path, "rb") as handle:
                fixture_view_before = handle.read()
            code, compact_view = fetch(base, compact_view_url)
            compact_markers = (
                'id="no-harm-compact-four"',
                "grid-template-columns:repeat(3,minmax(0,1fr))",
                ".viz-root>h1,.viz-root>.axis-title,",
                ".viz-root>.provenance,.viz-root>.legend,",
                ".panel figcaption>span{display:none!important}",
            )
            if (code != 200 or
                    any(marker not in compact_view
                        for marker in compact_markers) or
                    compact_view.count('<figure class="panel">') != 12):
                problems.append(
                    "S24: compact no-harm view is not a provenance-free "
                    "three-column grid with all 12 panels retained")
            compact_paths = _re.findall(
                r'data-contract-path="([^"]+)"', compact_view)
            expected_compact_paths = [
                f"red{channel} {hydrophone}"
                for channel in range(1, 5)
                for hydrophone in range(1, 4)
            ]
            if compact_paths != expected_compact_paths:
                problems.append(
                    "S24: compact no-harm grid is not three hydrophone "
                    "columns by four channel rows")
            code, normal_view = fetch(base, normal_view_url)
            fixture_view_text = fixture_view_before.decode("utf-8")
            if (code != 200 or normal_view != fixture_view_text or
                    'id="no-harm-compact-four"' in normal_view):
                problems.append(
                    "S24: full-size no-harm own-tab view received compact "
                    "layout overrides or changed bytes")
            normal_paths = _re.findall(
                r'data-contract-path="([^"]+)"', normal_view)
            if normal_paths != list(paths):
                problems.append(
                    "S24: compact channel/hydrophone ordering changed the "
                    "full-size result view")
            awgn_compact_url = (
                "/awgn-results/view?" + urllib.parse.urlencode([
                    ("experiment", no_harm_ids[0]), ("page", "summary"),
                    ("layout", "compact-four"),
                ]))
            code, awgn_compact_view = fetch(base, awgn_compact_url)
            if (code != 200 or awgn_compact_view != fixture_view_text or
                    'id="no-harm-compact-four"' in awgn_compact_view):
                problems.append(
                    "S24: compact no-harm layout leaked into or changed "
                    "AWGN results")
            with open(fixture_view_path, "rb") as handle:
                fixture_view_after = handle.read()
            if fixture_view_after != fixture_view_before:
                problems.append(
                    "S24: compact no-harm rendering modified the generated "
                    "result file")

            rate_query = urllib.parse.urlencode([
                ("experiment", no_harm_ids[0]),
                ("plot", "effective-rate"),
            ])
            code, rate_page = fetch(
                base, "/no-harm-results?" + rate_query)
            rate_view_url = (
                "/no-harm-results/effective-rate?" +
                urllib.parse.urlencode([
                    ("experiment", no_harm_ids[0]),
                    ("snr_db", "20"),
                ]))
            if (code != 200 or
                    '<select id="plot-picker"' not in rate_page or
                    '<option value="effective-rate" selected>'
                    not in rate_page or
                    'id="effective-rate-snr-control"' not in rate_page or
                    'id="effective-rate-snr" type="range"' not in rate_page or
                    'min="0" max="30" step="2" value="20"' not in rate_page or
                    '<label for="effective-rate-snr">SNR</label>' not in
                    rate_page or
                    'aria-valuetext="20 dB"' not in rate_page or
                    'id="effective-rate-snr-value" '
                    'for="effective-rate-snr">20 dB</output>' not in rate_page or
                    'new window.URL(window.location.href)' not in rate_page or
                    'slider.addEventListener("input"' not in rate_page or
                    'slider.addEventListener("change"' not in rate_page or
                    'window.addEventListener("pageshow"' not in rate_page or
                    'history.replaceState(null, "", pageUrl)' not in rate_page or
                    'openLink.href = allowPathComparison ? singleUrl :' not in
                    rate_page or
                    f'<iframe id="single-result" src="{rate_view_url}"'
                    not in rate_page):
                problems.append(
                    "S24: no-harm page did not expose its selected-SNR "
                    "effective-payload-rate figure")
            rate_path_query = urllib.parse.urlencode([
                ("experiment", no_harm_ids[0]),
                ("plot", "effective-rate"),
                ("path", "red1:1"),
            ])
            rate_path_dom, browser_error = browser_dom(
                base, "/no-harm-results?" + rate_path_query)
            if rate_path_dom is None:
                problems.append(
                    "S24: retained-path effective-rate view not checked: "
                    f"{browser_error}")
            else:
                rate_path_select = _re.search(
                    r'<select id="path-filter"([^>]*)>', rate_path_dom)
                rate_path_single = _re.search(
                    r'<iframe id="single-result"([^>]*)>', rate_path_dom)
                rate_path_comparison = _re.search(
                    r'<iframe id="comparison-result"([^>]*)>', rate_path_dom)
                rate_path_open = _re.search(
                    r'<a id="results-open"([^>]*)>', rate_path_dom)
                if (not rate_path_select or
                        "disabled" not in rate_path_select.group(1) or
                        not rate_path_single or
                        "hidden" in rate_path_single.group(1) or
                        f'src="{rate_view_url}"' not in
                        html.unescape(rate_path_single.group(1)) or
                        not rate_path_comparison or
                        "hidden" not in rate_path_comparison.group(1) or
                        not rate_path_open or
                        f'href="{rate_view_url}"' not in
                        html.unescape(rate_path_open.group(1))):
                    problems.append(
                        "S24: channel/hydrophone selection replaced the "
                        "effective-payload-rate plot with a BER comparison")
            selected_snr_query = urllib.parse.urlencode([
                ("experiment", no_harm_ids[0]),
                ("plot", "effective-rate"),
                ("snr_db", "18"),
            ])
            selected_snr_url = (
                "/no-harm-results/effective-rate?" +
                urllib.parse.urlencode([
                    ("experiment", no_harm_ids[0]),
                    ("snr_db", "18"),
                ]))
            code, selected_snr_page = fetch(
                base, "/no-harm-results?" + selected_snr_query)
            if (code != 200 or
                    'min="0" max="30" step="2" value="18"' not in
                    selected_snr_page or
                    '>18 dB</output>' not in selected_snr_page or
                    f'<iframe id="single-result" src="{selected_snr_url}"'
                    not in selected_snr_page):
                problems.append(
                    "S24: selected SNR did not reach the slider and "
                    "effective-payload-rate iframe")
            code, selected_snr_view = fetch(base, selected_snr_url)
            if (code != 200 or
                    "<h1>Effective payload rate at 18 dB</h1>" not in
                    selected_snr_view or
                    'data-rate-bps="961.0"' not in selected_snr_view or
                    selected_snr_view.count('<figure class="rate-panel"') !=
                    12 or
                    selected_snr_view.count('class="receiver-bar"') != 60):
                problems.append(
                    "S24: selected SNR did not render its corresponding "
                    "twelve-panel effective-rate bars")
            invalid_snr_queries = (
                "", "-2", "1", "20.0", "31", "NaN", "Inf", "not-a-number",
            )
            for invalid_snr in invalid_snr_queries:
                invalid_pairs = [
                    ("experiment", no_harm_ids[0]),
                    ("plot", "effective-rate"),
                    ("snr_db", invalid_snr),
                ]
                outer_code, _ = fetch(
                    base, "/no-harm-results?" +
                    urllib.parse.urlencode(invalid_pairs))
                endpoint_code, _ = fetch(
                    base, "/no-harm-results/effective-rate?" +
                    urllib.parse.urlencode([
                        ("experiment", no_harm_ids[0]),
                        ("snr_db", invalid_snr),
                    ]))
                if outer_code != 404 or endpoint_code != 404:
                    problems.append(
                        "S24: effective-rate SNR accepted invalid value "
                        f"{invalid_snr!r}")
            duplicate_snr = urllib.parse.urlencode([
                ("experiment", no_harm_ids[0]),
                ("plot", "effective-rate"),
                ("snr_db", "18"), ("snr_db", "20"),
            ])
            duplicate_endpoint_snr = urllib.parse.urlencode([
                ("experiment", no_harm_ids[0]),
                ("snr_db", "18"), ("snr_db", "20"),
            ])
            if (fetch(base, "/no-harm-results?" + duplicate_snr)[0] != 404 or
                    fetch(base, "/no-harm-results/effective-rate?" +
                          duplicate_endpoint_snr)[0] != 404):
                problems.append(
                    "S24: effective-rate SNR accepted duplicate values")
            code, rate_view = fetch(base, rate_view_url)
            rate_markers = (
                "<h1>Effective payload rate at 20 dB</h1>",
                'id="effective-rate-legend"',
                "grid-template-columns:repeat(3,minmax(0,1fr))",
                ">OFDM+FEC<", ">PFFT<", ">Lite<", ">(C,z)<", ">(C,W,z)<",
                'data-rate-bps="1011.0"',
            )
            if (code != 200 or
                    any(marker not in rate_view for marker in rate_markers) or
                    rate_view.count('<figure class="rate-panel"') != 12 or
                    rate_view.count('class="receiver-bar"') != 60):
                problems.append(
                    "S24: 20 dB effective-payload-rate figure is not a "
                    "twelve-panel, five-receiver bar plot")
            if ('@media(max-width:760px){.rate-grid{'
                    'grid-template-columns:1fr}}' in rate_view):
                problems.append(
                    "S24: effective-payload-rate figure collapses below its "
                    "four-channel by three-hydrophone grid")
            rate_scale = _re.search(r'data-y-max="([^"]+)"', rate_view)
            selected_snr_scale = _re.search(
                r'data-y-max="([^"]+)"', selected_snr_view)
            if (not rate_scale or not selected_snr_scale or
                    rate_scale.group(1) != selected_snr_scale.group(1)):
                problems.append(
                    "S24: effective-rate vertical scale changed with SNR")
            rate_paths = _re.findall(
                r'data-contract-path="([^"]+)"', rate_view)
            if rate_paths != expected_compact_paths:
                problems.append(
                    "S24: effective-payload-rate panels are not four channel "
                    "rows by three hydrophone columns")
            rate_panel_links = _re.findall(
                r'<a class="rate-panel-link"([^>]*)>', rate_view)
            expected_first_by_n = (
                "/no-harm-results/effective-rate/by-n?" +
                urllib.parse.urlencode([
                    ("experiment", no_harm_ids[0]),
                    ("snr_db", "20"),
                    ("path", "red1:1"),
                ]))
            first_by_n_attrs = (html.unescape(rate_panel_links[0])
                                if rate_panel_links else "")
            if (len(rate_panel_links) != 12 or
                    any('target="_top"' not in attrs
                        for attrs in rate_panel_links) or
                    f'href="{expected_first_by_n}"' not in first_by_n_attrs):
                problems.append(
                    "S24: effective-rate panels are not twelve semantic "
                    "top-level links to their across-N comparison")
            selected_rate_links = _re.findall(
                r'<a class="rate-panel-link"([^>]*)>', selected_snr_view)
            if (not selected_rate_links or
                    'snr_db=18' not in html.unescape(
                        selected_rate_links[0])):
                problems.append(
                    "S24: effective-rate panel links did not retain the "
                    "selected SNR")

            by_n_query = urllib.parse.urlencode([
                ("experiment", no_harm_ids[0]),
                ("snr_db", "14"),
                ("path", "red1:1"),
            ])
            by_n_url = "/no-harm-results/effective-rate/by-n?" + by_n_query
            code, by_n_view = fetch(base, by_n_url)
            by_n_groups = _re.findall(
                r'<g class="n-group"[^>]*data-nfft="([^"]+)"[^>]*'
                r'data-combined-pilot-ratio="([^"]+)"[^>]*'
                r'data-pilot-spacing="([^"]+)"', by_n_view)
            by_n_bar_count = by_n_view.count(
                'class="grouped-receiver-bar"')
            by_n_zero_count = by_n_view.count('class="zero-rate-marker"')
            by_n_diagnostic_checks = {
                "heading": "<h1>RED1 · H1 effective payload rate across N "
                           "and pilot ratio at 14 dB</h1>" in by_n_view,
                "slider": 'min="0" max="30" step="2" value="14"' in
                          by_n_view,
                "percents": (by_n_view.count(
                    'data-pilot-percent="30"') == 3 and
                    by_n_view.count('data-pilot-percent="40"') == 2),
                "rates": all(
                    f'data-rate-bps="{rate}.0"' in by_n_view
                    for rate in (861, 1161, 1261, 1361, 1461)),
                "ids": all(
                    f'data-experiment-id="{no_harm_ids[index]}"' in by_n_view
                    for index in (0, 3, 4, 5, 6)),
                "formula": "Combined pilot ratio = 1 / outer spacing + 1 / "
                           "inner spacing." in by_n_view,
                "axis": ">N and combined pilot ratio<" in by_n_view,
            }
            by_n_diagnostic_missing = [
                name for name, passed in by_n_diagnostic_checks.items()
                if not passed]
            if (code != 200 or
                    "<h1>RED1 · H1 effective payload rate across N and "
                    "pilot ratio at "
                    "14 dB</h1>" not in by_n_view or
                    'id="effective-rate-by-n-snr-control"' not in by_n_view or
                    'id="effective-rate-by-n-snr" type="range"' not in
                    by_n_view or
                    'min="0" max="30" step="2" value="14"' not in
                    by_n_view or
                    'aria-valuetext="14 dB"' not in by_n_view or
                    'id="effective-rate-by-n-snr-value" '
                    'for="effective-rate-by-n-snr">14 dB</output>' not in
                    by_n_view or
                    'new window.URL(window.location.href)' not in by_n_view or
                    'slider.addEventListener("input"' not in by_n_view or
                    'slider.addEventListener("change"' not in by_n_view or
                    by_n_groups != [
                        ("1024", "3/10", "5/10"),
                        ("1024", "3/10", "10/5"),
                        ("1024", "2/5", "5/5"),
                        ("2048", "3/10", "5/10"),
                        ("2048", "2/5", "5/5"),
                    ] or
                    by_n_bar_count != 25 or
                    by_n_view.count('data-pilot-percent="30"') != 3 or
                    by_n_view.count('data-pilot-percent="40"') != 2 or
                    'data-rate-bps="861.0"' not in by_n_view or
                    'data-rate-bps="1161.0"' not in by_n_view or
                    'data-rate-bps="1261.0"' not in by_n_view or
                    'data-rate-bps="1361.0"' not in by_n_view or
                    'data-rate-bps="1461.0"' not in by_n_view or
                    by_n_zero_count != 1 or
                    by_n_view.count('class="zero-rate-label"') != 1 or
                    f'data-experiment-id="{no_harm_ids[0]}"' not in
                    by_n_view or
                    f'data-experiment-id="{no_harm_ids[3]}"' not in
                    by_n_view or
                    any(f'data-experiment-id="{no_harm_ids[index]}"' not in
                        by_n_view for index in (4, 5, 6)) or
                    no_harm_ids[1] in by_n_view or
                    no_harm_ids[2] in by_n_view or
                    "Combined pilot ratio = 1 / outer spacing + 1 / inner "
                    "spacing." not in by_n_view or
                    ">Effective payload rate (bps)<" not in by_n_view or
                    ">N and combined pilot ratio<" not in by_n_view):
                problems.append(
                    "S24: grouped detail did not render five sorted N/pilot "
                    "groups with 25 exact receiver bars and its SNR slider "
                    "for RED1 H1 at 14 dB "
                    f"(groups={by_n_groups!r}, bars="
                    f"{by_n_bar_count}, zero={by_n_zero_count}, missing="
                    f"{by_n_diagnostic_missing!r})")
            configuration_helper = getattr(
                server, "_no_harm_effective_rate_configuration", None)
            if configuration_helper is None:
                problems.append(
                    "S24: across-N comparison has no strict configuration "
                    "signature")
            else:
                base_n, base_signature, _ = configuration_helper(
                    no_harm_ids[0])
                sibling_n, sibling_signature, _ = configuration_helper(
                    no_harm_ids[3])
                expected_signature = (
                    "first8s-frames8", "crc-no-harm", "128", "0.25",
                    "10", "fill", "4", "1", "4")
                if (base_n != 1024 or sibling_n != 2048 or
                        base_signature != expected_signature or
                        sibling_signature != expected_signature):
                    problems.append(
                        "S24: grouped signature did not hold capture, frames, "
                        "policy, CP, rate, dc, K, PFFT, frame duration, and "
                        "seed fixed while excluding N and pilot geometry")
            by_n_20_query = urllib.parse.urlencode([
                ("experiment", no_harm_ids[0]),
                ("snr_db", "20"),
                ("path", "red1:1"),
            ])
            code_20, by_n_20_view = fetch(
                base, "/no-harm-results/effective-rate/by-n?" +
                by_n_20_query)
            by_n_scale = _re.search(r'data-y-max="([^"]+)"', by_n_view)
            by_n_20_scale = _re.search(
                r'data-y-max="([^"]+)"', by_n_20_view)
            if (code_20 != 200 or not by_n_scale or not by_n_20_scale or
                    by_n_scale.group(1) != by_n_20_scale.group(1)):
                problems.append(
                    "S24: across-N comparison changed its vertical scale "
                    "with the selected SNR")

            # UI-040: one matched comparison family becomes a twelve-panel
            # maximum-rate envelope without hiding exact ties or outages.
            best_outer_query = urllib.parse.urlencode([
                ("experiment", no_harm_ids[0]),
                ("plot", "best-observed"),
                ("scope", "family"),
                ("snr_db", "6"),
            ])
            best_endpoint_query = urllib.parse.urlencode([
                ("experiment", no_harm_ids[0]),
                ("snr_db", "6"),
                ("scope", "family"),
            ])
            best_endpoint_url = (
                "/no-harm-results/effective-rate/best?" +
                best_endpoint_query)
            best_outer_code, best_outer_page = fetch(
                base, "/no-harm-results?" + best_outer_query)
            if (best_outer_code != 200 or
                    '<option value="best-observed" selected>' not in
                    best_outer_page or
                    f'<iframe id="single-result" src="{best_endpoint_url}"'
                    not in best_outer_page or
                    '<select id="effective-rate-family-picker"' not in
                    best_outer_page or
                    '<select id="best-observed-scope-picker"' not in
                    best_outer_page or
                    '<option value="family" selected>Selected family</option>'
                    not in best_outer_page or
                    best_outer_page.count('data-family-size="') != 3 or
                    'data-family-size="5" selected' not in best_outer_page or
                    'id="sweep-parameters"' in best_outer_page or
                    'min="0" max="30" step="2" value="6"' not in
                    best_outer_page):
                problems.append(
                    "S24: best-observed plot did not retain its selected SNR "
                    "or disable the unrelated BER path comparison")
            best_code, best_view = fetch(base, best_endpoint_url)
            best_paths = _re.findall(
                r'<figure class="winner-panel" data-path="([^"]+)"',
                best_view)
            expected_best_paths = [
                f"red{channel}:{hydrophone}"
                for channel in range(1, 5)
                for hydrophone in range(1, 4)
            ]
            best_cell_pairs = _re.findall(
                r'<g class="winner-cell" data-path="([^"]+)" '
                r'data-snr-db="([^"]+)"', best_view)
            best_cell_blocks = {
                (match.group(2), match.group(3)): match.group(1)
                for match in _re.finditer(
                    r'(<g class="winner-cell" data-path="([^"]+)" '
                    r'data-snr-db="([^"]+)".*?</g></a>)',
                    best_view, _re.DOTALL)
            }
            expected_best_cell_pairs = [
                (path, str(snr_db))
                for path in expected_best_paths
                for snr_db in range(0, 31, 2)
            ]
            first_detail_url = (
                "/no-harm-results/effective-rate/by-n?" +
                urllib.parse.urlencode([
                    ("experiment", no_harm_ids[0]),
                    ("snr_db", "6"),
                    ("path", "red1:1"),
                    ("scope", "family"),
                ]))
            best_markers = (
                "<h1>Best observed effective payload rate</h1>",
                'id="best-observed-snr" type="range"',
                'min="0" max="30" step="2" value="6"',
                'data-family-size="5"',
                'data-focused-snr="6"',
                'data-path="red1:1" data-snr-db="0" '
                'data-outage="true" data-winner-count="0"',
                'data-path="red1:1" data-snr-db="2" '
                'data-outage="false" data-winner-count="1"',
                'data-rate-tied-receiver-count="3" '
                'data-selected-receiver="lite"',
                'data-winner-algorithms="lite"',
                'data-path="red1:1" data-snr-db="4" '
                'data-outage="false" data-winner-count="1"',
                'data-winner-algorithms="ofdm_fec"',
                'data-path="red1:1" data-snr-db="6" '
                'data-outage="false" data-winner-count="1"',
                'data-near-tie-count="1"',
                'data-path="red1:1" data-snr-db="10" '
                'data-outage="false" data-winner-count="1"',
                'data-rate-tied-receiver-count="2" '
                'data-selected-receiver="lite"',
                'data-path="red1:1" data-snr-db="12" '
                'data-outage="false" data-winner-count="2"',
                'data-winner-keys="n1024-p5-10-lite,'
                'n2048-p5-10-lite"',
                'data-receiver-tie-order="ofdm_fec pfft lite '
                'profiled_cz cwz_joint"',
                "Equal receiver rates use the approved decoding-time order: "
                "OFDM+FEC, PFFT, Lite, (C,z), (C,W,z).",
                "receiver order selected Lite from 3 equal-rate receivers",
                "receiver order selected Lite from 2 equal-rate receivers",
                'class="winner-range" data-path="red1:1" '
                'data-snr-start="6" data-snr-end="8"',
                f'href="{html.escape(first_detail_url, quote=True)}"',
                "Ranges join adjacent tested SNR points only when the full "
                "winner and near-tie sets are unchanged.",
                "Decoder time is not included in the effective payload rate.",
                "within one successful-frame rate step of the maximum",
                'class="winner-range-near"',
                "Provenance unverified.",
            )
            compact_best_view = _re.sub(r"\s+", " ", best_view)
            missing_best_markers = tuple(
                marker for marker in best_markers
                if marker not in best_view and marker not in compact_best_view)
            cell_0 = best_cell_blocks.get(("red1:1", "0"), "")
            cell_2 = best_cell_blocks.get(("red1:1", "2"), "")
            cell_4 = best_cell_blocks.get(("red1:1", "4"), "")
            cell_6 = best_cell_blocks.get(("red1:1", "6"), "")
            cell_10 = best_cell_blocks.get(("red1:1", "10"), "")
            cell_12 = best_cell_blocks.get(("red1:1", "12"), "")
            winner_counts = _re.findall(
                r'<g class="winner-cell"[^>]*data-winner-count="([0-9]+)"',
                best_view)
            expected_winner_distribution = {
                "0": 1,
                "1": 190,
                "2": 1,
            }
            winner_distribution = {
                count: winner_counts.count(count)
                for count in set(winner_counts)
            }
            exact_cell_contract = (
                'data-outage="true"' in cell_0 and
                'data-winner-count="0"' in cell_0 and
                'data-selected-receiver=""' in cell_0 and
                'data-near-tie-count="0"' in cell_0 and
                'fill="#868e96"' in cell_0 and
                'fill="#adb5bd"' in cell_0 and
                'data-winner-keys="n1024-p5-10-lite"' in cell_2 and
                'data-selected-receiver="lite"' in cell_2 and
                'fill="#51cf66"' in cell_2 and
                'data-selected-receiver="ofdm_fec"' in cell_4 and
                'fill="#339af0"' in cell_4 and
                'data-near-tie-keys="n1024-p5-10-lite"' in cell_6 and
                'observed lead 1.0 bps' in cell_6 and
                'data-winner-keys="n1024-p5-10-lite"' in cell_10 and
                'data-selected-receiver="lite"' in cell_10 and
                'fill="#51cf66"' in cell_10 and
                'data-winner-keys="n1024-p5-10-lite,'
                'n2048-p5-10-lite"' in cell_12 and
                'data-selected-receiver="lite"' in cell_12 and
                cell_12.count('winner-ribbon-stripe') == 2 and
                'fill="#51cf66"' in cell_12)

            priority_contract = True
            priority_cases = (
                (("ofdm_fec", "pfft", "lite", "profiled_cz", "cwz_joint"),
                 "ofdm_fec"),
                (("pfft", "lite", "profiled_cz", "cwz_joint"), "pfft"),
                (("lite", "profiled_cz", "cwz_joint"), "lite"),
                (("profiled_cz", "cwz_joint"), "profiled_cz"),
            )
            for tied_receiver_ids, expected_receiver in priority_cases:
                priority_observations = {
                    (1, 1, receiver_id): {
                        "rate": (100.0 if receiver_id in tied_receiver_ids
                                 else 50.0),
                        "successful_frames": 1,
                    }
                    for receiver_id, _label, _color
                    in server._EFFECTIVE_RATE_RECEIVERS
                }
                priority_family = (((1024, 5, 5), {
                    "experiment_id": "priority-contract",
                    "observations": {0.0: priority_observations},
                }),)
                priority_cell = server._best_observed_cell(
                    priority_family, 0.0, 1, 1)
                if (priority_cell["selected_receiver"] != expected_receiver or
                        {winner["receiver_id"]
                         for winner in priority_cell["winners"]} !=
                        {expected_receiver}):
                    priority_contract = False
            if (best_code != 200 or
                    missing_best_markers or
                    best_paths != expected_best_paths or
                    best_cell_pairs != expected_best_cell_pairs or
                    best_view.count('class="winner-panel"') != 12 or
                    best_view.count('class="winner-cell-link"') != 192 or
                    best_view.count('class="winner-point"') != 192 or
                    best_view.count('winner-ribbon-stripe') != 192 or
                    best_view.count(
                        'class="winner-config-legend-item"') != 5 or
                    winner_distribution != expected_winner_distribution or
                    not exact_cell_contract or
                    not priority_contract or
                    _re.search(
                        r'<circle class="winner-point"[^>]*'
                        r'fill="#212529"', best_view) or
                    no_harm_ids[2] in best_view):
                problems.append(
                    "S24: best-observed figure did not render twelve strict "
                    "winner envelopes with every tested SNR, ordered receiver "
                    "tie resolution, configuration ties, outages, near ties, "
                    "ranges, and detail links; missing markers="
                    f"{missing_best_markers!r}")

            # UI-043: Best observed defaults to every tested no-harm
            # configuration, while retaining the strict family restriction.
            all_best_endpoint_query = urllib.parse.urlencode([
                ("experiment", no_harm_ids[0]),
                ("snr_db", "10"),
                ("scope", "all"),
            ])
            all_best_endpoint_url = (
                "/no-harm-results/effective-rate/best?" +
                all_best_endpoint_query)
            default_all_outer_query = urllib.parse.urlencode([
                ("experiment", no_harm_ids[0]),
                ("plot", "best-observed"),
                ("snr_db", "10"),
            ])
            default_all_outer_code, default_all_outer = fetch(
                base, "/no-harm-results?" + default_all_outer_query)
            all_best_code, all_best_view = fetch(
                base, all_best_endpoint_url)
            all_cell_blocks = {
                (match.group(2), match.group(3)): match.group(1)
                for match in _re.finditer(
                    r'(<g class="winner-cell" data-path="([^"]+)" '
                    r'data-snr-db="([^"]+)".*?</g></a>)',
                    all_best_view, _re.DOTALL)
            }
            all_cell_0 = all_cell_blocks.get(("red1:1", "0"), "")
            all_cell_10 = all_cell_blocks.get(("red1:1", "10"), "")
            all_cell_12 = all_cell_blocks.get(("red1:1", "12"), "")
            all_legend_ids = _re.findall(
                r'class="winner-config-legend-item" '
                r'data-experiment-id="([^"]+)"', all_best_view)
            all_detail_url = (
                "/no-harm-results/effective-rate/by-n?" +
                urllib.parse.urlencode([
                    ("experiment", no_harm_ids[0]),
                    ("snr_db", "10"),
                    ("path", "red1:1"),
                    ("scope", "all"),
                ]))
            all_scope_contract = (
                default_all_outer_code == 200 and
                '<select id="best-observed-scope-picker"' in
                default_all_outer and
                '<option value="all" selected>All tested no-harm '
                'configurations</option>' in default_all_outer and
                'id="effective-rate-family-picker" disabled' in
                default_all_outer and
                f'<iframe id="single-result" src="{all_best_endpoint_url}"'
                in default_all_outer and
                all_best_code == 200 and
                'data-comparison-scope="all"' in all_best_view and
                'data-family-count="3"' in all_best_view and
                'data-configuration-count="7"' in all_best_view and
                'data-candidate-count="35"' in all_best_view and
                all_best_view.count('class="winner-panel"') == 12 and
                all_best_view.count('class="winner-cell-link"') == 192 and
                all_best_view.count('class="winner-point"') == 192 and
                len(all_legend_ids) == 7 and
                set(all_legend_ids) == set(no_harm_ids) and
                'data-selected-receiver="cwz_joint"' in all_cell_0 and
                f'data-winner-experiment-ids="{no_harm_ids[2]}"' in
                all_cell_0 and
                'data-rate-tied-receiver-count="5"' in all_cell_10 and
                'data-selected-receiver="ofdm_fec"' in all_cell_10 and
                f'data-winner-experiment-ids="{no_harm_ids[2]}"' in
                all_cell_10 and
                '9999.0 bps' in all_cell_10 and
                'fill="#339af0"' in all_cell_10 and
                'data-selected-receiver="lite"' in all_cell_12 and
                f'data-winner-experiment-ids="{no_harm_ids[4]},'
                f'{no_harm_ids[5]}"' in all_cell_12 and
                f'href="{html.escape(all_detail_url, quote=True)}"' in
                all_best_view and
                'This view includes configurations with different capture '
                'windows, frame counts, receiver policies, code rates, and '
                'frame durations.' in all_best_view and
                'It reports the largest stored effective payload rate; it '
                'is not a controlled comparison.' in all_best_view and
                not _re.search(
                    r'<circle class="winner-point"[^>]*fill="#212529"',
                    all_best_view))
            all_detail_code, all_detail_view = fetch(base, all_detail_url)
            all_detail_ids = _re.findall(
                r'<g class="n-group"[^>]*data-experiment-id="([^"]+)"',
                all_detail_view)
            repeated_n_pilots = _re.findall(
                r'<g class="n-group" data-nfft="1024"[^>]*'
                r'data-pilot-spacing="5/5"', all_detail_view)
            all_detail_contract = (
                all_detail_code == 200 and
                'data-comparison-scope="all"' in all_detail_view and
                all_detail_view.count('class="n-group"') == 7 and
                all_detail_view.count('class="grouped-receiver-bar"') == 35
                and len(all_detail_ids) == 7 and
                set(all_detail_ids) == set(no_harm_ids) and
                len(repeated_n_pilots) == 2 and
                'effective payload rate across tested configurations at '
                '10 dB' in all_detail_view and
                all_detail_view.count('class="group-family-label"') == 7 and
                all(expression in all_detail_view for expression in
                    no_harm_ids) and
                'plot=best-observed' in all_detail_view and
                'scope=all' in all_detail_view)
            if not all_scope_contract:
                problems.append(
                    "S24: best-observed all-configurations scope did not "
                    "scan every family, preserve duplicate N/pilot records, "
                    "or identify the selected algorithm and source result")
            if not all_detail_contract:
                problems.append(
                    "S24: all-configurations winner link did not retain its "
                    "scope or render every source configuration and receiver")
            invalid_best_queries = (
                [("experiment", no_harm_ids[0]), ("snr_db", "1")],
                [("experiment", impulsive_id), ("snr_db", "6")],
                [("experiment", no_harm_ids[0]), ("snr_db", "6"),
                 ("extra", "value")],
                [("experiment", no_harm_ids[0]),
                 ("experiment", no_harm_ids[0]), ("snr_db", "6")],
                [("experiment", no_harm_ids[0]), ("snr_db", "6"),
                 ("scope", "bogus")],
                [("experiment", no_harm_ids[0]), ("snr_db", "6"),
                 ("scope", "all"), ("scope", "family")],
            )
            for invalid_pairs in invalid_best_queries:
                invalid_best_code, _ = fetch(
                    base, "/no-harm-results/effective-rate/best?" +
                    urllib.parse.urlencode(invalid_pairs))
                if invalid_best_code != 404:
                    problems.append(
                        "S24: best-observed route accepted an ambiguous, "
                        "undeclared, unknown, or off-grid query")
                    break
            single_n_query = urllib.parse.urlencode([
                ("experiment", no_harm_ids[1]),
                ("snr_db", "14"),
                ("path", "red1:1"),
            ])
            single_n_code, single_n_view = fetch(
                base, "/no-harm-results/effective-rate/by-n?" +
                single_n_query)
            if (single_n_code != 200 or
                    single_n_view.count('class="n-group"') != 1 or
                    single_n_view.count(
                        'class="grouped-receiver-bar"') != 5 or
                    single_n_view.count('class="zero-rate-marker"') != 5 or
                    single_n_view.count('class="zero-rate-label"') != 5 or
                    "Only one matching N and pilot setting is currently "
                    "available." not in
                    single_n_view or
                    "All five stored effective payload rates are 0 bps at "
                    "14 dB for this path." not in single_n_view or
                    'min="0" max="30" step="2" value="14"' not in
                    single_n_view):
                problems.append(
                    "S24: single-N zero-rate detail did not retain its SNR "
                    "slider and visible zero-value explanation")
            original_experiment_ids = server._experiment_ids
            server._experiment_ids = lambda **_kwargs: list(no_harm_ids) + [
                no_harm_ids[0]]
            try:
                duplicate_n_code, _ = fetch(base, by_n_url)
                duplicate_best_code, _ = fetch(base, best_endpoint_url)
            finally:
                server._experiment_ids = original_experiment_ids
            if duplicate_n_code != 404 or duplicate_best_code != 404:
                problems.append(
                    "S24: grouped comparison or best-observed figure silently "
                    "selected or averaged duplicate configurations")
            invalid_by_n_queries = (
                [("experiment", no_harm_ids[0]), ("snr_db", "14")],
                [("experiment", no_harm_ids[0]), ("path", "red1:1")],
                [("snr_db", "14"), ("path", "red1:1")],
                [("experiment", no_harm_ids[0]), ("snr_db", "1"),
                 ("path", "red1:1")],
                [("experiment", no_harm_ids[0]), ("snr_db", "14"),
                 ("path", "red0:1")],
                [("experiment", no_harm_ids[0]), ("snr_db", "14"),
                 ("path", "red1:4")],
                [("experiment", impulsive_id), ("snr_db", "14"),
                 ("path", "red1:1")],
                [("experiment", no_harm_ids[0]), ("snr_db", "14"),
                 ("path", "red1:1"), ("extra", "value")],
                [("experiment", no_harm_ids[0]),
                 ("experiment", no_harm_ids[0]), ("snr_db", "14"),
                 ("path", "red1:1")],
            )
            for invalid_pairs in invalid_by_n_queries:
                invalid_code, _ = fetch(
                    base, "/no-harm-results/effective-rate/by-n?" +
                    urllib.parse.urlencode(invalid_pairs))
                if invalid_code != 404:
                    problems.append(
                        "S24: across-N route accepted an incomplete, "
                        "ambiguous, unsafe, or off-grid query")
                    break
            code, _excluded_rate = fetch(
                base, "/no-harm-results/effective-rate?" +
                urllib.parse.urlencode([("experiment", impulsive_id)]))
            if code != 404:
                problems.append(
                    "S24: effective-payload-rate route accepted a result "
                    "without a no-harm declaration")
            aggregate_path = os.path.join(
                experiments, no_harm_ids[0], "results",
                "contract_effective_rate.csv")
            with open(aggregate_path, "rb") as handle:
                aggregate_before = handle.read()
            aggregate_lines = aggregate_before.splitlines(keepends=True)
            with open(aggregate_path, "wb") as handle:
                removed = False
                retained_lines = []
                for line in aggregate_lines:
                    if (not removed and
                            line.startswith(b"red4,3,20,cwz_joint,")):
                        removed = True
                        continue
                    retained_lines.append(line)
                handle.write(b"".join(retained_lines))
            code, _incomplete_rate = fetch(base, rate_view_url)
            by_n_incomplete_code, _ = fetch(
                base,
                "/no-harm-results/effective-rate/by-n?" +
                by_n_20_query)
            best_incomplete_code, _ = fetch(
                base, best_endpoint_url)
            ber_code, _ber_with_incomplete_rate = fetch(
                base, "/no-harm-results?" + urllib.parse.urlencode([
                    ("experiment", no_harm_ids[0]),
                ]))
            with open(aggregate_path, "wb") as handle:
                handle.write(aggregate_before)
            if code != 404:
                problems.append(
                    "S24: effective-payload-rate route accepted incomplete "
                    "path/receiver coverage")
            if by_n_incomplete_code != 404:
                problems.append(
                    "S24: across-N route accepted an incomplete matching "
                    "aggregate")
            if best_incomplete_code != 404:
                problems.append(
                    "S24: best-observed route accepted an incomplete "
                    "matching aggregate")
            if ber_code != 200:
                problems.append(
                    "S24: incomplete effective-rate data disabled the BER "
                    "result page")
            with open(fixture_view_path, "rb") as handle:
                if handle.read() != fixture_view_before:
                    problems.append(
                        "S24: effective-payload-rate rendering modified the "
                        "generated BER result file")
            no_harm_picker = _re.search(
                r'<select id="experiment-picker"[^>]*>(.*?)</select>',
                no_harm_page, flags=_re.S)
            if (not no_harm_picker or
                    no_harm_picker.group(1).count("<option ") != 7):
                problems.append(
                    "S24: no-harm experiment picker does not contain "
                    "exactly seven declared options")
            expected_no_harm_labels = {
                no_harm_ids[0]: (
                    "N=1024 · rate=0.25 · pilots=5/5 · first 8 s · "
                    "8 frames · CRC no-harm"),
                no_harm_ids[1]: (
                    "N=2048 · rate=0.125 · pilots=5/10 · first 47 s · "
                    "32 frames · CRC-gated no-harm"),
                no_harm_ids[2]: (
                    "N=1024 · rate=0.125 · pilots=5/5 · first 32 s · "
                    "32 frames · CRC-gated no-harm"),
                no_harm_ids[3]: (
                    "N=2048 · rate=0.25 · pilots=5/5 · first 8 s · "
                    "8 frames · CRC no-harm"),
                no_harm_ids[4]: (
                    "N=1024 · rate=0.25 · pilots=5/10 · first 8 s · "
                    "8 frames · CRC no-harm"),
                no_harm_ids[5]: (
                    "N=2048 · rate=0.25 · pilots=5/10 · first 8 s · "
                    "8 frames · CRC no-harm"),
                no_harm_ids[6]: (
                    "N=1024 · rate=0.25 · pilots=10/5 · first 8 s · "
                    "8 frames · CRC no-harm"),
            }
            if no_harm_picker:
                picker_options = {}
                for tag, label in _re.findall(
                        r'(<option\b[^>]*>)(.*?)</option>',
                        no_harm_picker.group(1), flags=_re.S):
                    value = _re.search(r'\bvalue="([^"]+)"', tag)
                    title = _re.search(r'\btitle="([^"]+)"', tag)
                    if value:
                        picker_options[value.group(1)] = {
                            "label": label.strip(),
                            "title": title.group(1) if title else None,
                        }
                for experiment_id, label in expected_no_harm_labels.items():
                    if picker_options.get(experiment_id) != {
                            "label": label, "title": experiment_id}:
                        problems.append(
                            "S24: compact picker label/title mismatch for "
                            f"'{experiment_id}'")
                if len({item["label"] for item in picker_options.values()}) != 7:
                    problems.append(
                        "S24: compact experiment labels are not unique")
            policy_label = getattr(
                server, "_no_harm_policy_label", lambda _policy: "missing")
            if policy_label({
                    "profiled_cz": "CRC-gated no-harm C+z",
                    "cwz_joint": "CRC no-harm",
                    "lite": "unchanged",
                    }) is not None:
                problems.append(
                    "S24: mixed protected receiver policies got one compact "
                    "policy label")
            for marker in (
                    '"Capture / frames"', '"Receiver policy"',
                    '"N"', '"code rate"', '"pilots"',
                    'id="sweep-match-count" role="status" '
                    'aria-live="polite"'):
                if marker not in no_harm_page:
                    problems.append(
                        f"S24: compact no-harm filters lost '{marker}'")
            for experiment_id in no_harm_ids:
                if experiment_id not in no_harm_page:
                    problems.append(
                        f"S24: no-harm page omitted '{experiment_id}'")
            expected_no_harm_paths = [
                {
                    "value": f"red{channel}:{hydrophone}",
                    "label": f"red{channel} hydrophone {hydrophone}",
                }
                for channel in range(1, 5)
                for hydrophone in range(1, 4)
            ]
            if (server._experiment_result_paths(no_harm_ids[1]) !=
                    expected_no_harm_paths):
                problems.append(
                    "S24: legacy no-harm manifest sources did not provide "
                    "all 12 comparison paths")
            excluded_awgn_id = next(
                item for item in awgn_ids if item not in no_harm_ids)
            if (excluded_awgn_id in no_harm_page or
                    impulsive_id in no_harm_page):
                problems.append(
                    "S24: no-harm page included an undeclared result")
            code, no_harm_latest = fetch(base, "/no-harm-results")
            if (code != 200 or
                    not any(item in no_harm_latest for item in no_harm_ids)):
                problems.append(
                    "S24: no-ID no-harm route did not select a declared result")
            for marker in (
                    'id="awgn-live-progress"',
                    '<strong>Unregistered experiment output.</strong>',
                    "fetch('/api/awgn-results/progress'"):
                if marker in no_harm_latest:
                    problems.append(
                        f"S24: no-ID no-harm page retained removed pane "
                        f"'{marker}'")
            with tempfile.TemporaryDirectory(
                    prefix="juna-empty-no-harm-contract-") as empty_root:
                os.makedirs(os.path.join(empty_root, "experiments"))
                populated_root = server.ROOT
                server.ROOT = empty_root
                try:
                    empty_no_harm = server.page_results(
                        "", awgn=True, no_harm=True)
                finally:
                    server.ROOT = populated_root
            if ("No experiment results page exists yet" not in empty_no_harm or
                    any(marker in empty_no_harm for marker in (
                        'id="awgn-live-progress"',
                        '<strong>Unregistered experiment output.</strong>',
                        "fetch('/api/awgn-results/progress'"))):
                problems.append(
                    "S24: empty no-harm page retained a removed pane or lost "
                    "its empty-state message")

            no_harm_dom, browser_error = browser_dom(
                base, f"/no-harm-results?experiment={no_harm_selected}")
            if no_harm_dom is None:
                problems.append(
                    "S24: no-harm browser controls not checked: "
                    f"{browser_error}")
            else:
                controls = _re.search(
                    r'<span id="sweep-parameter-controls"[^>]*>'
                    r'(.*?)</span>', no_harm_dom, flags=_re.S)
                if (not controls or controls.group(1).count("<select") != 5 or
                        "7 experiments match" not in no_harm_dom):
                    problems.append(
                        "S24: browser did not render five compact controls "
                        "and seven matches")
                if controls:
                    expected_filters = (
                        ("sweep-filter-capture_frames", "Capture / frames",
                         [("", "(all)"),
                          ("first8s-frames8", "first 8 s · 8 frames"),
                          ("first32s-frames32", "first 32 s · 32 frames"),
                          ("first47s-frames32", "first 47 s · 32 frames")]),
                        ("sweep-filter-receiver_policy", "Receiver policy",
                         [("", "(all)"),
                          ("crc-no-harm", "CRC no-harm"),
                          ("crc-gated-no-harm", "CRC-gated no-harm")]),
                        ("sweep-filter-nfft", "N",
                         [("", "(all)"), ("1024", "1024"),
                          ("2048", "2048")]),
                        ("sweep-filter-code_rate", "code rate",
                         [("", "(all)"), ("0.125", "0.125"),
                          ("0.25", "0.25")]),
                        ("sweep-filter-pilots", "pilots",
                         [("", "(all)"), ("5/5", "5/5"),
                          ("5/10", "5/10"), ("10/5", "10/5")]),
                    )
                    for select_id, label, expected_options in expected_filters:
                        select = _re.search(
                            rf'<label for="{_re.escape(select_id)}">'
                            rf'{_re.escape(label)} </label>\s*'
                            rf'<select id="{_re.escape(select_id)}">'
                            r'(.*?)</select>', controls.group(1), flags=_re.S)
                        options = (_re.findall(
                            r'<option[^>]*value="([^"]*)"[^>]*>'
                            r'(.*?)</option>', select.group(1), flags=_re.S)
                                   if select else [])
                        if options != expected_options:
                            problems.append(
                                f"S24: {label} options {options!r}, "
                                f"expected {expected_options!r}")
                default_picker = _re.search(
                    r'<select id="experiment-picker"[^>]*>(.*?)</select>',
                    no_harm_dom, flags=_re.S)
                default_tags = (_re.findall(r'<option\b[^>]*>',
                                             default_picker.group(1))
                                if default_picker else [])
                default_single = _re.search(
                    r'<iframe id="single-result"([^>]*)>', no_harm_dom)
                default_comparison = _re.search(
                    r'<iframe id="comparison-result"([^>]*)>', no_harm_dom)
                if (len(default_tags) != 7 or
                        any("hidden" in tag or "disabled" in tag
                            for tag in default_tags) or
                        not default_single or
                        "hidden" in default_single.group(1) or
                        not default_comparison or
                        "hidden" not in default_comparison.group(1)):
                    problems.append(
                        "S24: (all) did not restore every experiment and the "
                        "single-result view")

            multi_query = urllib.parse.urlencode([
                ("experiment", no_harm_ids[0]), ("page", "trace"),
                ("sentinel", "kept"),
                ("receiver_policy", "crc-gated-no-harm"),
            ])
            multi_dom, browser_error = browser_dom(
                base, "/no-harm-results?" + multi_query)
            if multi_dom is None:
                problems.append(
                    "S24: multiple no-harm matches not checked: "
                    f"{browser_error}")
            else:
                multi_picker = _re.search(
                    r'<select id="experiment-picker"[^>]*>(.*?)</select>',
                    multi_dom, flags=_re.S)
                multi_tags = (_re.findall(r'<option\b[^>]*>',
                                           multi_picker.group(1))
                              if multi_picker else [])
                visible = [tag for tag in multi_tags
                           if "hidden" not in tag and "disabled" not in tag]
                placeholders = [tag for tag in multi_tags
                                if "data-filter-placeholder" in tag]
                multi_single = _re.search(
                    r'<iframe id="single-result"([^>]*)>', multi_dom)
                if ("2 experiments match" not in multi_dom or
                        len(visible) != 2 or
                        len(placeholders) != 1 or
                        "selected" not in placeholders[0] or
                        "Choose one of 2 matching experiments" not in
                        multi_dom or
                        any("selected" in tag for tag in visible) or
                        not multi_single or
                        "hidden" not in multi_single.group(1) or
                        "page=trace" not in multi_dom or
                        "sentinel=kept" not in multi_dom):
                    problems.append(
                        "S24: multiple matches did not wait for an explicit "
                        "experiment choice "
                        f"(visible={len(visible)}, placeholders="
                        f"{placeholders!r}, single="
                        f"{(multi_single.group(1) if multi_single else None)!r}, "
                        f"prompt={'Choose one of 2 matching experiments' in multi_dom}, "
                        f"page={'page=trace' in multi_dom}, "
                        f"sentinel={'sentinel=kept' in multi_dom})")

            unique_query = urllib.parse.urlencode([
                ("experiment", no_harm_ids[0]), ("page", "trace"),
                ("sentinel", "kept"), ("nfft", "2048"),
                ("code_rate", "0.125"), ("pilots", "5/10"),
                ("capture_frames", "first47s-frames32"),
                ("receiver_policy", "crc-gated-no-harm"),
            ])
            unique_dom, browser_error = browser_dom(
                base, "/no-harm-results?" + unique_query)
            if unique_dom is None:
                problems.append(
                    "S24: unique no-harm filter not checked: "
                    f"{browser_error}")
            else:
                unique_picker = _re.search(
                    r'<select id="experiment-picker"[^>]*>(.*?)</select>',
                    unique_dom, flags=_re.S)
                unique_options = {}
                if unique_picker:
                    for tag, label in _re.findall(
                            r'(<option\b[^>]*>)(.*?)</option>',
                            unique_picker.group(1), flags=_re.S):
                        value = _re.search(r'\bvalue="([^"]+)"', tag)
                        if value:
                            unique_options[value.group(1)] = tag
                chosen_tag = unique_options.get(no_harm_ids[1], "")
                hidden_tag = unique_options.get(no_harm_ids[0], "")
                if ("1 experiments match" not in unique_dom or
                        "selected" not in chosen_tag or
                        "hidden" in chosen_tag or "disabled" in chosen_tag or
                        "hidden" not in hidden_tag or
                        "disabled" not in hidden_tag or
                        "page=trace" not in unique_dom or
                        "sentinel=kept" not in unique_dom):
                    problems.append(
                        "S24: unique filters did not narrow the picker, "
                        "select the match, and preserve the query")
            for suffix in ("view", "manifest"):
                code, _ = fetch(
                    base,
                    f"/no-harm-results/{suffix}?experiment={no_harm_selected}")
                if code != 200:
                    problems.append(
                        f"S24: /no-harm-results/{suffix} returned {code}")
                excluded = urllib.parse.quote(excluded_awgn_id, safe="")
                code, _ = fetch(
                    base,
                    f"/no-harm-results/{suffix}?experiment={excluded}")
                if code != 404:
                    problems.append(
                        f"S24: /no-harm-results/{suffix} accepted a result "
                        "without a no-harm declaration")
            excluded = urllib.parse.quote(excluded_awgn_id, safe="")
            code, _ = fetch(
                base, f"/no-harm-results?experiment={excluded}")
            if code != 404:
                problems.append(
                    "S24: no-harm page accepted an undeclared AWGN result")
            no_harm_comparison_query = urllib.parse.urlencode([
                *(('experiment', item) for item in no_harm_ids),
                ('path', 'red1:1'),
            ])
            code, no_harm_comparison = fetch(
                base,
                "/no-harm-results/compare?" + no_harm_comparison_query)
            if (code != 200 or no_harm_comparison.count(
                    'class="experiment-result"') != 7):
                problems.append(
                    "S24: no-harm comparison did not render all declared "
                    "experiments")
            for experiment_id, label in expected_no_harm_labels.items():
                if (f'data-experiment-id="{experiment_id}"' not in
                        no_harm_comparison or
                        f"<h2>{label}</h2>" not in no_harm_comparison):
                    problems.append(
                        "S24: no-harm comparison lost compact heading/full "
                        f"ID for '{experiment_id}'")
            mixed_comparison_query = urllib.parse.urlencode([
                ('experiment', no_harm_ids[0]),
                ('experiment', excluded_awgn_id),
                ('path', 'red1:1'),
            ])
            code, _ = fetch(
                base,
                "/no-harm-results/compare?" + mixed_comparison_query)
            if code != 404:
                problems.append(
                    "S24: no-harm comparison accepted an undeclared result")

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
                        "26 of 708 paths validated (3.7%); 2 of 59 "
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
                        "AWGN-021 (rate 0.25, outer spacing 5): "
                        "0 of 12 paths; queued",
                        "AWGN-022 (rate 0.25, outer spacing 5): "
                        "0 of 12 paths; queued",
                        "AWGN-023B (rate 0.25, outer spacing 5): "
                        "0 of 12 paths; queued",
                        "AWGN-023C (rate 0.25, outer spacing 5): "
                        "0 of 12 paths; running",
                        "AWGN-024 (rate 0.5, outer spacing 5): "
                        "0 of 12 paths; queued",
                        "AWGN-025 (rate 0.5, outer spacing 5): "
                        "0 of 12 paths; queued",
                        "AWGN-026 (rate 0.25, outer spacing 10): "
                        "0 of 12 paths; queued",
                        "AWGN-027 (rate 0.5, outer spacing 10): "
                        "0 of 12 paths; queued",
                        f"Current: AWGN-009, {active_id}, "
                        "red1 hydrophone 2 | AWGN-016, "
                        f"{active_awgn016_id}, red4 hydrophone 2 | "
                        f"AWGN-019, {active_awgn019_id}, "
                        "red2 hydrophone 3 | AWGN-023C, "
                        f"{awgn023c_harness_name}, red3 hydrophone 2"):
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
                ("experiment", awgn_ids[0]), ("nfft", "4096"),
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
            elif not _re.search(
                    rf'<option\b[^>]*value="{_re.escape(single_awgn_id)}"'
                    r'[^>]*\bselected', single_dom):
                problems.append(
                    "S22: unique AWGN geometry did not select its experiment")

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
            # Historical campaigns promote aggregate/trace pairs. AWGN-019,
            # AWGN-020 through AWGN-027 additionally promote a per-path
            # contract after validation.
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
                        "AWGN-020", "AWGN-021", "AWGN-022", "AWGN-023B",
                        "AWGN-023C", "AWGN-024", "AWGN-025", "AWGN-026",
                        "AWGN-027"],
                    "total_configurations": 59,
                    "total_paths": 708,
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
                        {
                            "campaign_id": "AWGN-023C",
                            "experiment_id": awgn023c_harness_name,
                            "channel": "red3",
                            "hydrophone": 2,
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
                    "AWGN-021": ("0.25", 5, 0, 0, "queued", 12, 1),
                    "AWGN-022": ("0.25", 5, 0, 0, "queued", 12, 1),
                    "AWGN-023B": ("0.25", 5, 0, 0, "queued", 12, 1),
                    "AWGN-023C": ("0.25", 5, 0, 0, "running", 12, 1),
                    "AWGN-024": ("0.5", 5, 0, 0, "queued", 12, 1),
                    "AWGN-025": ("0.5", 5, 0, 0, "queued", 12, 1),
                    "AWGN-026": ("0.25", 10, 0, 0, "queued", 12, 1),
                    "AWGN-027": ("0.5", 10, 0, 0, "queued", 12, 1),
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
                expected_percent = 100 * 26 / 708
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
            open(awgn021_contract, "w").close()
            code, contracted021_body = fetch(
                base, "/api/awgn-results/progress")
            if code != 200:
                problems.append(
                    "S23: progress failed after AWGN-021 contract promotion")
            else:
                contracted021 = json.loads(contracted021_body).get("data", {})
                campaigns = {
                    item.get("campaign_id"): item
                    for item in contracted021.get("campaigns", [])}
                awgn021 = campaigns.get("AWGN-021", {})
                if (contracted021.get("completed_paths") != 29 or
                        awgn021.get("completed_paths") != 1):
                    problems.append(
                        "S23: AWGN-021 final contract did not promote exactly "
                        "one completed path")
            open(awgn022_contract, "w").close()
            code, contracted022_body = fetch(
                base, "/api/awgn-results/progress")
            if code != 200:
                problems.append(
                    "S23: progress failed after AWGN-022 contract promotion")
            else:
                contracted022 = json.loads(contracted022_body).get("data", {})
                campaigns = {
                    item.get("campaign_id"): item
                    for item in contracted022.get("campaigns", [])}
                awgn022 = campaigns.get("AWGN-022", {})
                if (contracted022.get("completed_paths") != 30 or
                        awgn022.get("completed_paths") != 1):
                    problems.append(
                        "S23: AWGN-022 final contract did not promote exactly "
                        "one completed path")
            open(awgn023b_contract, "w").close()
            code, contracted023b_body = fetch(
                base, "/api/awgn-results/progress")
            if code != 200:
                problems.append(
                    "S23: progress failed after AWGN-023B contract promotion")
            else:
                contracted023b = json.loads(contracted023b_body).get("data", {})
                campaigns = {
                    item.get("campaign_id"): item
                    for item in contracted023b.get("campaigns", [])}
                awgn023b = campaigns.get("AWGN-023B", {})
                if (contracted023b.get("completed_paths") != 31 or
                        awgn023b.get("completed_paths") != 1):
                    problems.append(
                        "S23: AWGN-023B final contract did not promote exactly "
                        "one completed path")
            open(awgn023c_contract, "w").close()
            code, contracted023c_body = fetch(
                base, "/api/awgn-results/progress")
            if code != 200:
                problems.append(
                    "S23: progress failed after AWGN-023C contract promotion")
            else:
                contracted023c = json.loads(contracted023c_body).get("data", {})
                campaigns = {
                    item.get("campaign_id"): item
                    for item in contracted023c.get("campaigns", [])}
                awgn023c = campaigns.get("AWGN-023C", {})
                if (contracted023c.get("completed_paths") != 32 or
                        awgn023c.get("completed_paths") != 1):
                    problems.append(
                        "S23: AWGN-023C final contract did not promote exactly "
                        "one completed path")
            open(awgn024_contract, "w").close()
            code, contracted024_body = fetch(
                base, "/api/awgn-results/progress")
            if code != 200:
                problems.append(
                    "S23: progress failed after AWGN-024 contract promotion")
            else:
                contracted024 = json.loads(contracted024_body).get("data", {})
                campaigns = {
                    item.get("campaign_id"): item
                    for item in contracted024.get("campaigns", [])}
                awgn024 = campaigns.get("AWGN-024", {})
                if (contracted024.get("completed_paths") != 33 or
                        awgn024.get("completed_paths") != 1):
                    problems.append(
                        "S23: AWGN-024 final contract did not promote exactly "
                        "one completed path")
            open(awgn025_contract, "w").close()
            code, contracted025_body = fetch(
                base, "/api/awgn-results/progress")
            if code != 200:
                problems.append(
                    "S23: progress failed after AWGN-025 contract promotion")
            else:
                contracted025 = json.loads(contracted025_body).get("data", {})
                campaigns = {
                    item.get("campaign_id"): item
                    for item in contracted025.get("campaigns", [])}
                awgn025 = campaigns.get("AWGN-025", {})
                if (contracted025.get("completed_paths") != 34 or
                        awgn025.get("completed_paths") != 1):
                    problems.append(
                        "S23: AWGN-025 final contract did not promote exactly "
                        "one completed path")
            open(awgn026_contract, "w").close()
            code, contracted026_body = fetch(
                base, "/api/awgn-results/progress")
            if code != 200:
                problems.append(
                    "S23: progress failed after AWGN-026 contract promotion")
            else:
                contracted026 = json.loads(contracted026_body).get("data", {})
                campaigns = {
                    item.get("campaign_id"): item
                    for item in contracted026.get("campaigns", [])}
                awgn026 = campaigns.get("AWGN-026", {})
                if (contracted026.get("completed_paths") != 35 or
                        awgn026.get("completed_paths") != 1):
                    problems.append(
                        "S23: AWGN-026 final contract did not promote exactly "
                        "one completed path")
            open(awgn027_contract, "w").close()
            code, contracted027_body = fetch(
                base, "/api/awgn-results/progress")
            if code != 200:
                problems.append(
                    "S23: progress failed after AWGN-027 contract promotion")
            else:
                contracted027 = json.loads(contracted027_body).get("data", {})
                campaigns = {
                    item.get("campaign_id"): item
                    for item in contracted027.get("campaigns", [])}
                awgn027 = campaigns.get("AWGN-027", {})
                if (contracted027.get("completed_paths") != 36 or
                        awgn027.get("completed_paths") != 1):
                    problems.append(
                        "S23: AWGN-027 final contract did not promote exactly "
                        "one completed path")
            state_helper = getattr(server, "_awgn_overall_state", None)
            if state_helper is None:
                problems.append("S23: missing truthful overall-state helper")
            else:
                complete = {"state": "complete", "matrix_complete": True,
                            "completed_paths": 708}
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
                    'max="708"',
                    "AWGN-008, AWGN-009, AWGN-012, AWGN-015, AWGN-016, "
                    "AWGN-017, AWGN-018, AWGN-019, AWGN-020, AWGN-021, "
                    "AWGN-022, AWGN-023B, AWGN-023C, AWGN-024, AWGN-025, "
                    "AWGN-026, and AWGN-027 "
                    "real-time "
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
            for route, document in (("/results", results_page),
                                    ("/awgn-results", awgn_page)):
                if "Unregistered experiment output." not in document:
                    problems.append(
                        f"S23: {route} lost its unregistered-output notice")
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
    print("server contract: PASS (S1-S24)")
