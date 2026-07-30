#!/usr/bin/env python3
"""Behavior contract for the JUNA-Lite explorer server.

Run:  python3 tools/explorer/server_contract.py       (exit 0 = holds)

Boots the server in-process on an ephemeral port and asserts:
S1  every nav page (/, /tests, /map, /chain, /source, /coverage, /progress)
    returns 200 and carries the full nav label set.
S2  /coverage states the static-not-runtime distinction and both legend
    marks (direct ● vs declared-behavioral ◐).
S3  /chain embeds every stage declared in chain.json.
S4  /tests lists every suite key from suites.json.
S5  /source is the vendored analyzer page (contains a known Lite symbol).
S6  banned destinations 404: /benchmark, /history, /reproduce (this explorer
    deliberately has no such pages), and /run/<unknown-suite> 404s.
S7  /run/<key> pages exist for every registry key WITHOUT starting a run
    (GET must have no side effects).
"""
import json
import os
import sys
import threading
import urllib.request
from http.server import ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import server  # noqa: E402

NAV_LABELS = ["Home", "Tests", "Map", "Chain", "Source", "Coverage",
              "Progress"]


def fetch(base, path):
    try:
        with urllib.request.urlopen(base + path) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode()


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

    # S1
    pages = {}
    for path in ["/", "/tests", "/map", "/chain", "/source", "/coverage",
                 "/progress"]:
        code, text = fetch(base, path)
        pages[path] = text
        if code != 200:
            problems.append(f"S1: {path} returned {code}")
        if path != "/source":  # analyzer page has its own chrome
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
    for s in suites:
        if f'id="{s["key"]}"' not in pages.get("/tests", ""):
            problems.append(f"S4: /tests lost suite '{s['key']}'")

    # S5
    if "_juna_lite" not in pages.get("/source", ""):
        problems.append("S5: /source does not look like the analyzer page")

    # S6
    for path in ["/benchmark", "/history", "/reproduce", "/run/no-such-suite"]:
        code, _ = fetch(base, path)
        if code != 404:
            problems.append(f"S6: {path} returned {code}, expected 404")

    # S7
    for s in suites:
        code, text = fetch(base, f"/run/{s['key']}")
        if code != 200:
            problems.append(f"S7: /run/{s['key']} returned {code}")
    code, text = fetch(base, f"/run/{suites[0]['key']}/output")
    if code != 200 or json.loads(text).get("status") != "idle":
        problems.append("S7: GET run page/output must not start a run "
                        f"(got status {json.loads(text).get('status')!r})")

    httpd.shutdown()
    return problems


if __name__ == "__main__":
    problems = check()
    if problems:
        print("SERVER CONTRACT FAILURES:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("server contract: PASS (S1-S7)")
