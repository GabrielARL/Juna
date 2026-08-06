#!/usr/bin/env python3
"""Behavior contract for the JUNA-Lite explorer server.

Run:  python3 tools/explorer/server_contract.py       (exit 0 = holds)

Boots the server in-process on an ephemeral port and asserts:
S1  every nav page (/, /tests, /map, /chain, /source, /coverage, /health,
    /progress, /results) returns 200 and carries the full nav label set.
S2  /coverage states the static-not-runtime distinction and both legend
    marks (direct ● vs declared-behavioral ◐).
S3  /chain embeds every stage declared in chain.json.
S4  /tests presents every suite in reader-facing language, keeps technical
    registry data in collapsed details, labels browser-recorded results as
    Explorer runs, and retains valid receiver-stage links.
S5  /source is the three-panel source-definition page; /source/inspector is
    the server-rendered symbol list and persistent evidence inspector.
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
S15 Source retains Inspector and Advanced Graph modes; the graph API
    accepts receiver/stage/suite/file contexts; every navigation tab emits a
    contextual Source entry; and the primary three-panel page has the
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
S22 Results resolves an explicit experiment ID, preserves query-routed views,
    serves that experiment's completeness manifest, and rejects unsafe IDs.
S23 OFDM+FEC is the canonical Explorer receiver, while the legacy
    receiver=standard query resolves to that canonical receiver.
S24 Source promotes the rich three-pane analyzer to /source, retains the
    Evidence Inspector at /source/inspector and the receiver-stage graph at
    /source/graph, and keeps /source-advanced plus /source-legacy as aliases.
    The rich analyzer uses the five labels approved as JCM-073 through
    JCM-077 and omits their five predecessors.
S25 a full source rescan discovers a newly added .jl file without restarting
    the Explorer process.
S26 Results offers one channel/hydrophone selector and a comparison view that
    returns exactly that BER-SNR panel from every requested sweep experiment,
    while rejecting unknown paths and unsafe experiment IDs.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
from http.server import ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
import server  # noqa: E402
from source_symbol_explorer import analyze  # noqa: E402

NAV_LABELS = ["Home", "Tests", "Map", "Chain", "Source", "Coverage",
              "Health", "Progress", "Results"]
API_ENDPOINTS = ["/api/repository", "/api/suites", "/api/chain",
                 "/api/symbols", "/api/coverage", "/api/runs",
                 "/api/health", "/api/palette", "/api/receivers",
                 "/api/graph"]
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
    run = subprocess.run(
        [chrome, "--headless", "--no-sandbox", "--disable-gpu",
         "--virtual-time-budget=8000", "--dump-dom", base + path],
        capture_output=True, text=True, timeout=30)
    return run.stdout, run.stderr[-500:]


def check():
    experiments = os.path.join(ROOT, "experiments")
    os.makedirs(experiments, exist_ok=True)
    fixture = tempfile.mkdtemp(prefix="server-contract-", dir=experiments)
    fixture_id = os.path.basename(fixture)
    fixture_results = os.path.join(fixture, "results")
    os.makedirs(fixture_results)
    with open(os.path.join(fixture_results, "results_view.html"), "w") as fh:
        fh.write('<!doctype html><div data-results-view="fixture">fixture</div>')
    with open(os.path.join(fixture_results, "results_manifest.json"), "w") as fh:
        json.dump({"schema_version": 1, "experiment_id": fixture_id,
                   "row_count": 2, "columns": ["channel", "lane"]}, fh)

    fixture_token = fixture_id.removeprefix("server-contract-")
    sweep_fixture_ids = [
        (f"server-contract-{fixture_token}-"
         "n512-cp16-rate05-p3-4-dc10-kfill"),
        (f"server-contract-{fixture_token}-"
         "n1024-cp32-rate025-p5-8-dc8-k4"),
    ]
    for index, sweep_id in enumerate(sweep_fixture_ids, start=1):
        sweep_results = os.path.join(experiments, sweep_id, "results")
        os.makedirs(sweep_results)
        with open(os.path.join(sweep_results, "results_view.html"), "w") as fh:
            fh.write(
                '<!doctype html><style>.panel{display:block}</style>'
                '<div class="viz-root"><div class="legend">fixture legend</div>'
                '<div class="grid-panels">'
                '<figure class="panel"><figcaption><b>red1 hydrophone 1</b>'
                f'</figcaption><svg data-contract-experiment="{index}"></svg>'
                '</figure>'
                '<figure class="panel"><figcaption><b>red2 hydrophone 2</b>'
                f'</figcaption><svg data-contract-other="{index}"></svg>'
                '</figure></div></div>')
        with open(os.path.join(sweep_results, "results_manifest.json"), "w") as fh:
            json.dump({"schema_version": 2, "experiment_id": sweep_id,
                       "paths": ["red1 1", "red2 2"], "row_count": 4}, fh)

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
                 "/health", "/progress", "/results"]:
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
    src_page = pages.get("/source", "")
    inspector_code, inspector_page = fetch(base, "/source/inspector")
    if inspector_code != 200:
        problems.append(f"S5: /source/inspector returned {inspector_code}")
    if ('id="inspector"' not in inspector_page or
            'id="symlist"' not in inspector_page):
        problems.append(
            "S5: /source/inspector lost the inspector or symbol list")
    if "_juna_lite_candidate" not in inspector_page:
        problems.append(
            "S5: /source/inspector symbol list is not server-rendered")
    for label in TAXONOMY:
        if label not in inspector_page:
            problems.append(
                f"S5: /source/inspector lost taxonomy label '{label}'")
    if "/source" not in inspector_page:
        problems.append("S5: Inspector lost its primary Source link")

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
    if ("/static/source.js" not in inspector_page or
            "vis-network" not in inspector_page):
        problems.append(
            "S12: /source/inspector lost source.js or vis-network")
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
    for text in ("Source definitions", "Evidence Inspector", "Advanced Graph",
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
    for href in ("/source", "/source/inspector", "/source/graph", "/chain",
                 "/tests", "/coverage"):
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
            "JunaOFDMFEC", "JunaPartialFFT", "JunaLite",
            "JunaProfiledCzFrame", "JunaCrcProfiledCzFrame",
            "JunaCrcConditionedJointCwzFrame",
        }
        if {f["name"] for f in detail.get("facades", [])} != expected_facades:
            problems.append(
                "S15: type inspector public facades differ from the catalog")
    source_js = open(os.path.join(HERE, "static", "source.js")).read()
    for marker in ("Static call edge", "doubleClick", "Fields (",
                   "Open in Source definitions"):
        if marker not in source_js:
            problems.append(f"S15: source interaction lost '{marker}'")
    for facade in ("JunaProfiledCzFrame", "JunaCrcProfiledCzFrame",
                   "JunaCrcConditionedJointCwzFrame"):
        marker = f'{facade}: "profiled_cz"'
        if marker not in source_js:
            problems.append(
                f"S15: Source facade link lost Profiled C,z mapping {facade}")

    # S16
    for path, label in (
            ("/source/graph?receiver=lite", "receiver graph"),
            ("/source/inspector#sym=_juna_step", "symbol ego graph")):
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

    code, text = fetch(base, "/api/graph?receiver=profiled_cz")
    profiled_graph = json.loads(text).get("data", {}) if code == 200 else {}
    expected_profiled_stage_ids = {
        "stage:" + stage_id
        for receiver in chain["receivers"] if receiver["id"] == "profiled_cz"
        for stage_id in receiver["path"] + receiver.get("optional_stages", [])
    }
    if profiled_graph.get("view") != "stages":
        problems.append(
            "S18: Profiled C,z graph does not default to stage view")
    if {node.get("id") for node in profiled_graph.get("nodes", [])} != \
            expected_profiled_stage_ids:
        problems.append(
            "S18: Profiled C,z graph differs from its declared stage DAG")

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
    definition_summary = (
        f'{len(analyzed["symbols"])} source definitions: '
        f'{kind_counts.get("function", 0)} function or method definitions, '
        f'{kind_counts.get("const", 0)} constants, '
        f'{kind_counts.get("module", 0)} module declarations, '
        f'{kind_counts.get("struct", 0)} structure declarations, and '
        f'{kind_counts.get("type", 0)} abstract type declaration.')
    map_markers = (
        definition_summary,
        "A repeated name is counted separately for each definition.",
        "These definitions were found in the source code. This count does "
        "not show that the code ran.",
    )
    for marker in map_markers:
        if marker not in normalized_map_page:
            problems.append(f"S20: /map lost approved wording '{marker}'")
    for file_name, count in per_file_counts.items():
        noun = "source definition" if count == 1 else "source definitions"
        marker = f">{count} {noun}</td>"
        if marker not in map_page:
            problems.append(
                f"S20: /map has no correct count label for {file_name}: "
                f"'{marker}'")

    code, source_page = fetch(base, "/source/inspector")
    code_graph, graph_page = fetch(base, "/source/graph")
    for path, status, page in (("/source/inspector", code, source_page),
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
            "S20: /source/inspector renders "
            f"{rendered_definitions} source definitions, "
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

    # S22
    stable_query = "experiment=" + fixture_id + "&page=summary"
    code, results_index = fetch(base, "/results?experiment=" + fixture_id)
    if code != 200 or stable_query not in results_index:
        problems.append("S22: /results did not retain the explicit experiment ID")
    if "Unregistered experiment output" in results_index:
        problems.append("S22: /results retained the removed experiment banner")
    code, results_view = fetch(base, "/results/view?" + stable_query)
    if code != 200 or 'data-results-view="fixture"' not in results_view:
        problems.append("S22: stable results view did not serve the requested experiment")
    code, manifest_text = fetch(
        base, "/results/manifest?experiment=" + fixture_id)
    if code != 200:
        problems.append(f"S22: results manifest returned {code}")
    else:
        manifest = json.loads(manifest_text)
        if manifest.get("experiment_id") != fixture_id:
            problems.append("S22: results manifest came from another experiment")
    code, _ = fetch(base, "/results/view?experiment=..%2Foutside")
    if code != 404:
        problems.append(f"S22: unsafe experiment ID returned {code}, expected 404")

    # S23
    code, receiver_text = fetch(base, "/api/receivers")
    receiver_data = (json.loads(receiver_text).get("data", [])
                     if code == 200 else [])
    ofdm_fec = next((receiver for receiver in receiver_data
                     if receiver.get("id") == "ofdm_fec"), None)
    expected = {"display_name": "OFDM+FEC", "facade": "JunaOFDMFEC",
                "mode": "ofdm_fec", "profile": "ofdm_fec"}
    if ofdm_fec is None or any(ofdm_fec.get(key) != value
                               for key, value in expected.items()):
        problems.append(
            "S23: /api/receivers lacks the canonical OFDM+FEC receiver")
    code, alias_text = fetch(base, "/api/graph?receiver=standard")
    alias_data = (json.loads(alias_text).get("data", {})
                  if code == 200 else {})
    alias_context = alias_data.get("context", [])
    if not any(context.get("kind") == "receiver" and
               context.get("value") == "ofdm_fec" and
               context.get("label") == "OFDM+FEC"
               for context in alias_context):
        problems.append(
            "S23: receiver=standard did not resolve to canonical OFDM+FEC")
    profiled_cz = next((receiver for receiver in receiver_data
                        if receiver.get("id") == "profiled_cz"), None)
    expected_profiled_cz = {
        "display_name": "Profiled C,z",
        "facade": "JunaProfiledCzFrame",
        "variant_facades": ["JunaCrcProfiledCzFrame",
                            "JunaCrcConditionedJointCwzFrame"],
        "mode": "frame_wide_ldpc",
        "profile": "frame_wide_ldpc",
        "frame_receiver": "profiled_cz",
        "objective": "profiled_cz_frame",
    }
    if profiled_cz is None or any(
            profiled_cz.get(key) != value
            for key, value in expected_profiled_cz.items()):
        problems.append(
            "S23: /api/receivers lacks the approved Profiled C,z family")

    # S24
    rich_markers = ('id="side"', 'id="net"', 'id="detail"')
    rich_pages = {"/source": src_page}
    for path in ("/source-advanced", "/source-legacy"):
        code, page = fetch(base, path)
        if code != 200:
            problems.append(f"S24: {path} returned {code}")
            continue
        rich_pages[path] = page
    approved_source_labels = (
        "Types and interface methods",
        "Receiver stages",
        "Static calls",
        "Public interface",
        "Modulation fields",
    )
    removed_source_labels = (
        "OOP view",
        "JunaCore pipeline",
        "call-focus sphere view",
        "interface I/O",
        "object fields",
    )
    for path, page in rich_pages.items():
        for marker in rich_markers:
            if marker not in page:
                problems.append(
                    f"S24: {path} lacks rich analyzer marker {marker}")
        for label in approved_source_labels:
            if label not in page:
                problems.append(
                    f"S24: {path} lacks approved label '{label}'")
        for old_label in removed_source_labels:
            if old_label in page:
                problems.append(
                    f"S24: {path} retains old label '{old_label}'")
    if 'data-source-mode="inspector"' not in inspector_page:
        problems.append(
            "S24: /source/inspector is not the Evidence Inspector")
    if 'data-source-mode="graph"' not in graph_page:
        problems.append("S24: /source/graph changed away from graph mode")
    if 'href="/source/inspector"' not in src_page:
        problems.append(
            "S24: primary Source bridge does not link to Evidence Inspector")
    if ('"embedded": true' not in src_page or
            "if(CFG.embedded){location.reload();return;}" not in src_page):
        problems.append(
            "S24: primary Source Reload does not request a fresh source scan")
    if "/source/inspector#sym=" not in src_page:
        problems.append(
            "S24: primary Source evidence link misses the Inspector")

    rich_dom, rich_error = browser_dom(base, "/source#sym=_juna_step")
    if rich_dom is None:
        problems.append(
            f"S24: primary Source deep link not checked: {rich_error}")
    elif not all(marker in rich_dom for marker in
                 ("<b>Code name</b>", "<h2>implementation</h2>",
                  "_juna_step")):
        problems.append(
            "S24: primary Source deep link did not show the implementation")

    inspector_dom, inspector_error = browser_dom(
        base, "/source/inspector#sym=Juna.Modulation")
    expected_source_link = 'href="/source#sym=Modulation&amp;module=Juna"'
    if inspector_dom is None:
        problems.append(
            f"S24: Inspector Source link not checked: {inspector_error}")
    elif expected_source_link not in inspector_dom:
        problems.append(
            "S24: Inspector emitted a Source link that cannot identify "
            "Juna.Modulation")

    modulation_dom, modulation_error = browser_dom(
        base, "/source#sym=Modulation&module=Juna")
    if modulation_dom is None:
        problems.append(
            f"S24: Juna.Modulation Source link not checked: "
            f"{modulation_error}")
    elif '<h3>Modulation<span class="kind">struct</span></h3>' not in \
          modulation_dom:
        problems.append(
            "S24: Juna.Modulation Source link did not open its definition")

    source_explorer_path = os.path.join(
        HERE, "source_symbol_explorer.py")
    with open(source_explorer_path, encoding="utf-8") as source_handle:
        source_explorer_text = source_handle.read()
    pipeline_text = source_explorer_text.split(
        "const PIPELINE=[", 1)[1].split("const MODPRI=", 1)[0]
    pipeline_functions = {
        name
        for function_list in _re.findall(r"\bf:\[([^\]]*)\]",
                                         pipeline_text)
        for name in _re.findall(r"['\"]([^'\"]+)['\"]", function_list)
    }
    current_functions = {symbol["name"] for symbol in analyzed["symbols"]}
    absent_pipeline_functions = sorted(
        pipeline_functions - current_functions)
    if absent_pipeline_functions:
        problems.append(
            "S24: Receiver stages names absent source functions: " +
            ", ".join(absent_pipeline_functions))
    required_profiled_functions = {
        "ProfiledCzFrameModulation",
        "CrcProfiledCzFrameModulation",
        "CrcTurboCwzFrameModulation",
        "CrcConditionedCwzFrameModulation",
        "CrcConditionedJointCwzFrameModulation",
        "_frame_profiled_cz_refine",
        "_cz_profile_C!",
        "_cz_update_W!",
        "_cz_candidate_crc_valid",
        "_cz_bp_feedback!",
        "_cz_conditioned_joint_step!",
        "_cz_restart_logits",
    }
    missing_profiled_functions = sorted(
        required_profiled_functions - pipeline_functions)
    if missing_profiled_functions:
        problems.append(
            "S24: Receiver stages omits Profiled C,z functions: " +
            ", ".join(missing_profiled_functions))
    if "Profiled C,z" not in source_explorer_text:
        problems.append(
            "S24: Receiver stages omits the approved Profiled C,z label")
    for stale_marker in ("sync_profile", "Rpchan", ":rpchan",
                         "_rpchan_acquire"):
        if stale_marker in source_explorer_text:
            problems.append(
                "S24: Receiver stages retains absent source entry " +
                stale_marker)
    family_text = source_explorer_text.split(
        "function artFamilies", 1)[1].split("async function load", 1)[0]
    drawn_facades = set(_re.findall(r"['\"](Juna[A-Za-z0-9_]+)['\"]",
                                    family_text))
    current_facades = {
        symbol["module"] for symbol in analyzed["symbols"]
        if symbol.get("file") == "JunaCore.jl" and
        symbol.get("kind") == "const" and
        symbol.get("name") == "Modulation" and
        symbol.get("module") != "JunaCore"
    }
    absent_drawn_facades = sorted(drawn_facades - current_facades)
    if absent_drawn_facades:
        problems.append(
            "S24: Receiver stages draws absent facades: " +
            ", ".join(absent_drawn_facades))
    missing_drawn_facades = sorted(current_facades - drawn_facades)
    if missing_drawn_facades:
        problems.append(
            "S24: Receiver stages omits current facades: " +
            ", ".join(missing_drawn_facades))

    # S25
    probe_name = "_server_contract_rescan_probe"
    code, before_text = fetch(base, "/api/symbols")
    before = (json.loads(before_text).get("data", [])
              if code == 200 else [])
    if any(symbol.get("name") == probe_name for symbol in before):
        problems.append("S25: source-rescan probe name already exists")
    probe_path = os.path.join(
        ROOT, "src", "juna", "server_contract_rescan_probe.jl")
    try:
        with open(probe_path, "w") as fh:
            fh.write(f"function {probe_name}()\n  nothing\nend\n")
        code, after_text = fetch(base, "/api/symbols")
        after = (json.loads(after_text).get("data", [])
                 if code == 200 else [])
        if not any(symbol.get("name") == probe_name for symbol in after):
            problems.append(
                "S25: full rescan did not discover a newly added .jl file")
    finally:
        if os.path.exists(probe_path):
            os.unlink(probe_path)

    # S26
    original_experiment_ids = server._experiment_ids
    server._experiment_ids = lambda: sweep_fixture_ids + [fixture_id]
    try:
        code, filter_page = fetch(
            base, "/results?experiment=" + sweep_fixture_ids[0])
        for marker in ('id="path-filter"', "Channel / hydrophone",
                       'value="red1:1"', 'value="red2:2"',
                       'id="comparison-result"'):
            if code != 200 or marker not in filter_page:
                problems.append(
                    f"S26: Results channel/hydrophone control lost '{marker}'")

        selected_query = urllib.parse.urlencode([
            ("experiment", sweep_fixture_ids[0]), ("path", "red1:1")])
        selected_dom, browser_error = browser_dom(
            base, "/results?" + selected_query)
        if selected_dom is None:
            problems.append(
                f"S26: browser comparison not checked: {browser_error}")
        else:
            if "2 plots match across experiments" not in selected_dom:
                problems.append(
                    "S26: browser did not render both matching plots")
            comparison_tag = _re.search(
                r'<iframe id="comparison-result"([^>]*)>', selected_dom)
            single_tag = _re.search(
                r'<iframe id="single-result"([^>]*)>', selected_dom)
            if (not comparison_tag or "hidden" in comparison_tag.group(1) or
                    not single_tag or "hidden" not in single_tag.group(1)):
                problems.append(
                    "S26: selected path did not replace the single result view")

        one_query = urllib.parse.urlencode([
            ("experiment", sweep_fixture_ids[0]), ("path", "red1:1"),
            ("nfft", "1024")])
        one_dom, browser_error = browser_dom(base, "/results?" + one_query)
        if one_dom is None:
            problems.append(
                f"S26: one-experiment comparison not checked: {browser_error}")
        else:
            comparison_tag = _re.search(
                r'<iframe id="comparison-result"([^>]*)>', one_dom)
            comparison_attributes = (comparison_tag.group(1)
                                     if comparison_tag else "")
            if ("1 plots match across experiments" not in one_dom or
                    sweep_fixture_ids[1] not in comparison_attributes or
                    sweep_fixture_ids[0] in comparison_attributes):
                problems.append(
                    "S26: parameter condition did not narrow the comparison")

        empty_query = urllib.parse.urlencode([
            ("experiment", sweep_fixture_ids[0]), ("path", "red1:1"),
            ("nfft", "512"), ("cp", "32")])
        empty_dom, browser_error = browser_dom(base, "/results?" + empty_query)
        if empty_dom is None:
            problems.append(
                f"S26: empty comparison not checked: {browser_error}")
        else:
            empty_tag = _re.search(
                r'<div id="comparison-empty"([^>]*)>', empty_dom)
            if ("0 plots match across experiments" not in empty_dom or
                    not empty_tag or "hidden" in empty_tag.group(1)):
                problems.append(
                    "S26: zero-match selection lacks its empty state")

        all_dom, browser_error = browser_dom(
            base, "/results?experiment=" + sweep_fixture_ids[0])
        if all_dom is None:
            problems.append(
                f"S26: all-path restoration not checked: {browser_error}")
        else:
            comparison_tag = _re.search(
                r'<iframe id="comparison-result"([^>]*)>', all_dom)
            single_tag = _re.search(
                r'<iframe id="single-result"([^>]*)>', all_dom)
            if (not comparison_tag or "hidden" not in comparison_tag.group(1) or
                    not single_tag or "hidden" in single_tag.group(1)):
                problems.append(
                    "S26: (all) did not restore the single experiment view")
    finally:
        server._experiment_ids = original_experiment_ids
    compare_query = urllib.parse.urlencode([
        ("experiment", sweep_fixture_ids[0]),
        ("experiment", sweep_fixture_ids[1]),
        ("path", "red1:1"),
    ])
    code, comparison = fetch(base, "/results/compare?" + compare_query)
    if code != 200:
        problems.append(f"S26: comparison returned {code}")
    else:
        if comparison.count('<figure class="panel">') != 2:
            problems.append(
                "S26: comparison did not return one panel per experiment")
        for marker in ('data-contract-experiment="1"',
                       'data-contract-experiment="2"'):
            if marker not in comparison:
                problems.append(
                    f"S26: comparison lost requested panel '{marker}'")
        if "data-contract-other" in comparison:
            problems.append(
                "S26: comparison retained a different channel/hydrophone")
    bad_path_query = urllib.parse.urlencode([
        ("experiment", sweep_fixture_ids[0]), ("path", "red9:9")])
    code, _ = fetch(base, "/results/compare?" + bad_path_query)
    if code != 404:
        problems.append(
            f"S26: unknown comparison path returned {code}, expected 404")
    unsafe_compare = urllib.parse.urlencode([
        ("experiment", "../outside"), ("path", "red1:1")])
    code, _ = fetch(base, "/results/compare?" + unsafe_compare)
    if code != 404:
        problems.append(
            f"S26: unsafe comparison experiment returned {code}, expected 404")

    httpd.shutdown()
    for sweep_id in sweep_fixture_ids:
        shutil.rmtree(os.path.join(experiments, sweep_id), ignore_errors=True)
    shutil.rmtree(fixture, ignore_errors=True)
    return problems


if __name__ == "__main__":
    problems = check()
    if problems:
        print("SERVER CONTRACT FAILURES:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("server contract: PASS (S1-S26)")
