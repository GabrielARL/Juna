#!/usr/bin/env python3
"""Data contracts for the JUNA-Lite explorer.

Run:  python3 tools/explorer/explorer_contract.py       (exit 0 = all hold)

C1  suites.json freshness: re-export the registry via julia into a temp file
    and byte-compare against the committed suites.json.
C2  suites.json integrity: parses; keys unique; every suite file exists under
    test/.
C3  registry completeness: every test/*.jl except test/support/ appears in the
    registry, so a new suite cannot exist outside the catalog.
C4  chain.json integrity: parses; stage ids unique; kind in
    {shared, seed, iterative, deployment}; evidence in {direct, behavioral};
    every stage symbol exists in the analyzer symbol table; every stage suite
    key exists in suites.json.
C5  evidence honesty: every evidence="direct" stage has at least one declared
    suite whose file textually references at least one stage symbol (per
    source_coverage.scan); every evidence="behavioral" stage has NO such
    direct reference (otherwise it must be promoted to "direct" so the
    coverage page cannot understate the evidence).
C6  scanner honesty: source_coverage's report note states the static-not-
    runtime distinction verbatim.
C7  vendored analyzer health: analyze() sees exactly the migrated source
    files with a sane symbol count, and render_html is offline-safe (the
    vendored vis-network is embedded; no CDN fallback) with the #sym= deep
    link route present. (The analyzer's full authoritative contract runs in
    the source repository it is vendored from; this is the migrated-scope
    check.)
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)

import source_coverage  # noqa: E402
from source_symbol_explorer import analyze  # noqa: E402

ALLOWED_KINDS = {"shared", "seed", "iterative", "deployment"}
ALLOWED_EVIDENCE = {"direct", "behavioral"}


def check():
    problems = []

    # C1 freshness
    fd, tmp = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        run = subprocess.run(
            ["julia", os.path.join(HERE, "export_suites.jl"), tmp],
            capture_output=True, text=True, cwd=ROOT)
        if run.returncode != 0:
            problems.append("C1: export_suites.jl failed: " +
                            run.stderr.strip()[-300:])
        else:
            with open(tmp) as fh:
                fresh = fh.read()
            with open(os.path.join(HERE, "suites.json")) as fh:
                committed = fh.read()
            if fresh != committed:
                problems.append(
                    "C1: suites.json is stale relative to test/runtests.jl - "
                    "rerun: julia tools/explorer/export_suites.jl")
    finally:
        os.unlink(tmp)

    # C2 integrity
    with open(os.path.join(HERE, "suites.json")) as fh:
        suites = json.load(fh)["suites"]
    keys = [s["key"] for s in suites]
    if len(set(keys)) != len(keys):
        problems.append("C2: duplicate suite keys in suites.json")
    for s in suites:
        if not os.path.isfile(os.path.join(ROOT, "test", s["file"])):
            problems.append(f"C2: suite '{s['key']}' file test/{s['file']} "
                            "does not exist")

    # C3 completeness
    registered = {s["file"] for s in suites}
    on_disk = {f for f in os.listdir(os.path.join(ROOT, "test"))
               if f.endswith(".jl") and f != "runtests.jl"}
    for orphan in sorted(on_disk - registered):
        problems.append(f"C3: test/{orphan} is not in the SUITES registry "
                        "(register it or move it under test/support/)")

    # C4 chain integrity
    with open(os.path.join(HERE, "chain.json")) as fh:
        chain = json.load(fh)
    stages = chain["stages"]
    ids = [st["id"] for st in stages]
    if len(set(ids)) != len(ids):
        problems.append("C4: duplicate stage ids in chain.json")
    table = {s["name"] for s in analyze(os.path.join(ROOT, "src"))["symbols"]}
    for st in stages:
        if st["kind"] not in ALLOWED_KINDS:
            problems.append(f"C4: stage '{st['id']}' has unknown kind "
                            f"'{st['kind']}'")
        if st.get("evidence") not in ALLOWED_EVIDENCE:
            problems.append(f"C4: stage '{st['id']}' has unknown evidence "
                            f"'{st.get('evidence')}'")
        for sym in st["symbols"]:
            if sym not in table:
                problems.append(f"C4: stage '{st['id']}' symbol '{sym}' is "
                                "absent from the analyzer symbol table")
        for key in st["suites"]:
            if key not in keys:
                problems.append(f"C4: stage '{st['id']}' suite '{key}' is "
                                "absent from suites.json")

    # C5 evidence honesty
    report = source_coverage.scan(ROOT)
    evidence = source_coverage.stage_evidence(ROOT, report)
    for st in stages:
        direct = evidence.get(st["id"], {}).get("with_direct_reference", [])
        if st["evidence"] == "direct" and not direct:
            problems.append(
                f"C5: stage '{st['id']}' claims direct evidence but no "
                "declared suite textually references any stage symbol")
        if st["evidence"] == "behavioral" and direct:
            problems.append(
                f"C5: stage '{st['id']}' claims behavioral evidence but "
                f"{direct} directly reference stage symbols - promote the "
                "stage to evidence=\"direct\"")

    # C6 scanner honesty
    if "not runtime coverage" not in report.get("note", ""):
        problems.append("C6: source_coverage report note lost the "
                        "static-not-runtime distinction")

    # C7 vendored analyzer health
    from source_symbol_explorer import render_html
    analyzed = analyze(os.path.join(ROOT, "src"))
    files = {s["file"] for s in analyzed["symbols"]}
    expected_files = {"JunaCore.jl", "Juna.jl", "Modulations.jl", "LDPC.jl",
                      os.path.join("juna", "common.jl"),
                      os.path.join("juna", "frame_wide_ldpc.jl"),
                      os.path.join("juna", "lite.jl")}
    if files != expected_files:
        problems.append(f"C7: analyzer file set drifted: {sorted(files)}")
    if len(analyzed["symbols"]) < 250:
        problems.append(f"C7: suspicious symbol count "
                        f"{len(analyzed['symbols'])} (< 250)")
    page = render_html(False, analyzed, os.path.join(ROOT, "src"),
                       locked=True)
    if "unpkg.com" in page:
        problems.append("C7: /source page fell back to the CDN - "
                        "tools/explorer/vendor/vis-network.min.js missing")
    if "#sym=" not in page:
        problems.append("C7: analyzer page lost the #sym= deep-link route")

    return problems


if __name__ == "__main__":
    problems = check()
    if problems:
        print("EXPLORER CONTRACT FAILURES:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("explorer contract: PASS (C1-C7)")
