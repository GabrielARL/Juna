#!/usr/bin/env python3
"""JUNA-Lite explorer - a chain-centric workbench for the migrated package.

Serves http://127.0.0.1:8772/ with tabs Home | Tests | Map | Chain | Source |
Coverage | Progress. Fresh design for this package (not a fork of the source
repository's workbench): the data models are the repository's own truths -
suites.json exported from test/runtests.jl, chain.json (declared stage map,
contract-verified), the vendored static analyzer, and source_coverage's
static reference scan. Static references are always labelled as such, never
as runtime coverage.

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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

import source_coverage  # noqa: E402
import source_symbol_explorer as source_symbols  # noqa: E402

SOURCE_SHA = "d49fff0"  # sonique research/JunaCore provenance (see README.md)
NAV = [("/", "Home"), ("/tests", "Tests"), ("/map", "Map"),
       ("/chain", "Chain"), ("/source", "Source"), ("/coverage", "Coverage"),
       ("/progress", "Progress")]

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


SUITES_CACHE = _Cache(_load_suites, [os.path.join(HERE, "suites.json")])
CHAIN_CACHE = _Cache(_load_chain, [os.path.join(HERE, "chain.json")])
ANALYZE_CACHE = _Cache(lambda: source_symbols.analyze(os.path.join(ROOT, "src")),
                       _src_files())
COVERAGE_CACHE = _Cache(lambda: source_coverage.scan(ROOT),
                        _src_files() +
                        [os.path.join(HERE, "suites.json")] +
                        [os.path.join(ROOT, "test", f)
                         for f in sorted(os.listdir(os.path.join(ROOT, "test")))
                         if f.endswith(".jl")])


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


def git_head():
    try:
        return subprocess.run(["git", "log", "-1", "--format=%h %s"],
                              capture_output=True, text=True, cwd=ROOT,
                              timeout=5).stdout.strip()
    except Exception:
        return "(git unavailable)"

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
                  "returncode": self.returncode, "status": self.status}
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
      background:var(--bg); }
nav a { text-decoration:none; color:var(--muted); padding:.25rem .7rem;
        border-radius:6px; }
nav a.active, nav a:hover { color:var(--fg); background:var(--card); }
main { max-width:72rem; margin:0 auto; padding:1.2rem 1rem 3rem; }
h1 { font-size:1.35rem; } h2 { font-size:1.1rem; margin-top:1.6rem; }
.card { background:var(--card); border:1px solid var(--line);
        border-radius:8px; padding: .9rem 1rem; margin:.7rem 0; }
table { border-collapse:collapse; width:100%; }
.wrap { overflow-x:auto; }
th, td { text-align:left; padding:.4rem .6rem; border-bottom:1px solid var(--line);
         vertical-align:top; }
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
.stage { border:1px solid var(--line); border-left:4px solid var(--accent);
         border-radius:8px; padding:.6rem .9rem; margin:.45rem 0;
         cursor:pointer; background:var(--card); }
.stage:hover { border-color:var(--accent); }
.stage .kind { float:right; }
.arrow { text-align:center; color:var(--muted); margin:-.1rem 0; }
#detail { position:sticky; top:3.2rem; }
.grid2 { display:grid; grid-template-columns: minmax(0,1fr) minmax(0,1fr);
         gap:1rem; }
@media (max-width: 60rem) { .grid2 { grid-template-columns: 1fr; } }
.note { border-left:4px solid var(--warn); padding:.5rem .8rem;
        background:var(--card); border-radius:0 8px 8px 0; margin:.7rem 0; }
button { font:inherit; padding:.3rem .8rem; border-radius:6px;
         border:1px solid var(--line); background:var(--card);
         color:var(--fg); cursor:pointer; }
button:hover { border-color:var(--accent); }
.dot { font-size:1rem; }
"""


def shell(title, active, body):
    parts = []
    for href, label in NAV:
        cls = ' class="active"' if href == active else ""
        parts.append(f'<a href="{href}"{cls}>{label}</a>')
    nav = "".join(parts)
    return (f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{html.escape(title)} · JUNA-Lite explorer</title>"
            f"<style>{CSS}</style></head><body>"
            f"<nav>{nav}</nav><main>{body}</main></body></html>")


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


def page_home():
    suites = SUITES_CACHE.get()
    chain = CHAIN_CACHE.get()
    last = last_run_by_key()
    ran = [k for k in last]
    strip = " → ".join(
        f'<a href="/chain#{esc(st["id"])}">{esc(st["title"])}</a>'
        for st in chain["stages"])
    rows = "".join(
        f"<tr><td><a href='/run/{esc(r['key'])}'>{esc(r['key'])}</a></td>"
        f"<td>{status_badge(r)}</td>"
        f"<td>{time.strftime('%H:%M:%S', time.localtime(r['ended']))}</td></tr>"
        for r in run_history()[-5:][::-1])
    body = f"""
<h1>JUNA-Lite explorer</h1>
<div class="card">Standalone home of the JUNA-Lite receiver, migrated from
sonique <code>research/JunaCore @ {SOURCE_SHA}</code>. Three public facades:
Standard OFDM, Partial-FFT, JUNA-Lite. HEAD: <code>{esc(git_head())}</code></div>
{stale_banner()}
<h2>Receiver chain</h2>
<div class="card">{strip}</div>
<div class="grid2">
<div><h2>Test surface</h2><div class="card">{len(suites)} suites in the
<a href="/tests">registry</a> · {len(ran)} with recorded runs ·
static <a href="/coverage">reference coverage</a></div></div>
<div><h2>Recent runs</h2><div class="wrap"><table>
<tr><th>suite</th><th>status</th><th>ended</th></tr>{rows or
'<tr><td colspan="3">none recorded yet</td></tr>'}</table></div></div>
</div>
<h2>Verification</h2>
<div class="card"><code>julia --project=. -e 'using Pkg; Pkg.test()'</code>
 · parity vs source repo: <code>julia --project=. tools/parity_check.jl</code>
 · data contracts: <code>python3 tools/explorer/explorer_contract.py</code></div>"""
    return shell("Home", "/", body)


def page_tests():
    suites = SUITES_CACHE.get()
    last = last_run_by_key()
    rows = ""
    for s in suites:
        rec = last.get(s["key"])
        rows += (f'<tr id="{esc(s["key"])}"><td><code>{esc(s["key"])}</code></td>'
                 f'<td><b>{esc(s["title"])}</b><br><span style="color:var(--muted)">'
                 f'{esc(s["claim"])}</span><br>'
                 f'<span class="badge">{esc(s["provenance"])}</span></td>'
                 f'<td><code>{esc(s["file"])}</code></td>'
                 f'<td>{status_badge(rec)}</td>'
                 f'<td><a href="/run/{esc(s["key"])}"><button>run</button></a>'
                 f'</td></tr>')
    body = f"""
<h1>Test suites</h1>
<div class="card">Generated from the authoritative registry in
<code>test/runtests.jl</code> via <code>suites.json</code>; a suite absent
here cannot run in Pkg.test either (contract C3).</div>
{stale_banner()}
<div class="wrap"><table>
<tr><th>key</th><th>title / claim</th><th>file</th><th>last run</th><th></th></tr>
{rows}</table></div>"""
    return shell("Tests", "/tests", body)


def page_map():
    analyzed = ANALYZE_CACHE.get()
    suites = SUITES_CACHE.get()
    per_file = {}
    for s in analyzed["symbols"]:
        per_file[s["file"]] = per_file.get(s["file"], 0) + 1
    src_rows = "".join(
        f"<tr><td><code>src/{esc(f)}</code></td><td>{n} symbols</td></tr>"
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
<div class="card"><code>bench/test_runs.jsonl</code>: appended by browser-
triggered runs (gitignored).</div>"""
    return shell("Map", "/map", body)


def page_chain():
    chain = CHAIN_CACHE.get()
    payload = json.dumps(chain["stages"]).replace("</", "<\\/")
    boxes = ""
    for i, st in enumerate(chain["stages"]):
        if i:
            boxes += '<div class="arrow">↓</div>'
        boxes += (f'<div class="stage" id="{esc(st["id"])}" '
                  f'onclick="show(\'{esc(st["id"])}\')">'
                  f'<span class="badge kind">{esc(st["kind"])}</span>'
                  f'<b>{esc(st["title"])}</b><br>'
                  f'<span style="color:var(--muted)">'
                  f'{esc(", ".join(st["symbols"][:3]))}'
                  f'{"…" if len(st["symbols"]) > 3 else ""}</span></div>')
    body = f"""
<h1>JUNA-Lite receiver chain</h1>
<div class="card">Declared in <code>tools/explorer/chain.json</code> and
contract-verified against the analyzer and the suite registry. Lite refits
the combiner <b>W</b> only - the physical response C is never formed - and
stops on success, non-improvement, or the iteration limit.</div>
<div class="grid2"><div>{boxes}</div>
<div id="detail"><div class="card">Click a stage for its symbols, suites,
and evidence.</div></div></div>
<script>
var STAGES = {payload};
function show(id) {{
  var st = STAGES.find(function(s) {{ return s.id === id; }});
  if (!st) return;
  var evCls = st.evidence === "direct" ? "ok" : "warn";
  var syms = st.symbols.map(function(s) {{
    return '<a href="/source#sym=' + encodeURIComponent(s) + '"><code>' +
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
  if (history.replaceState) history.replaceState(null, '', '#' + id);
}}
if (location.hash) show(location.hash.slice(1));
</script>"""
    return shell("Chain", "/chain", body)


def page_source():
    analyzed = ANALYZE_CACHE.get()
    return source_symbols.render_html(False, analyzed,
                                      os.path.join(ROOT, "src"), locked=True)


def page_coverage():
    chain = CHAIN_CACHE.get()
    suites = SUITES_CACHE.get()
    report = COVERAGE_CACHE.get()
    last = last_run_by_key()
    keys = [s["key"] for s in suites]
    head = "".join(
        f"<th><a href='/tests#{esc(k)}'>{esc(k)}</a><br>{status_badge(last.get(k))}</th>"
        for k in keys)
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
                 f"</a></td>{cells}</tr>")
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
            f"<tr><td><a href='/source#sym={esc(n)}'><code>{esc(n)}</code></a>"
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
<code>tail -f .migration_progress.log</code></div>
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


class Handler(BaseHTTPRequestHandler):
    def _send(self, text, code=200, ctype="text/html; charset=utf-8"):
        data = text.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass

    def do_GET(self):
        path, _, query = self.path.partition("?")
        try:
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
            if path == "/coverage":
                return self._send(page_coverage())
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
                    return self._send(shell("404", "", "<h1>unknown suite</h1>"),
                                      404)
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
