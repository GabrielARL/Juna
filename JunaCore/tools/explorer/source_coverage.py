#!/usr/bin/env python3
"""Static source-to-test reference scanner for the JUNA-Lite explorer.

HONESTY CONTRACT: everything this module reports is a STATIC TEXTUAL
reference — "this suite names this source symbol" — never runtime execution
coverage. No line here is claimed to have executed. The /coverage page must
carry this distinction verbatim.

Output shape (scan(root)):
  {
    "note": "...static, not runtime...",
    "suites": {key: {"file": ..., "direct": {symbol: [line, ...]}}},
    "unresolved": [{"suite": key, "line": n, "name": "Qualified.ref"}, ...],
  }

"direct" hits are word-bounded occurrences of analyzer symbol names in the
suite file. "unresolved" records qualified references (Juna.X / JunaCore.X)
whose trailing name is absent from the analyzer table — the honest bucket
for typos, removed symbols, or references into non-migrated code.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from source_symbol_explorer import analyze  # noqa: E402

STATIC_NOTE = ("static textual references only - a hit means the suite NAMES "
               "the code name, never that a line executed (not runtime coverage)")

_KNOWN_CONTAINERS = {"Juna", "JunaCore", "Modulations", "LDPC",
                     "JunaLite", "JunaOFDMFEC", "JunaPartialFFT",
                     "JunaStandard", "JunaProfiledCzFrame",
                     "JunaCrcProfiledCzFrame",
                     "JunaCrcConditionedJointCwzFrame"}


def scan(root):
    data = analyze(os.path.join(root, "src"))
    names = {}
    for s in data["symbols"]:
        if s["kind"] == "module":
            continue
        names.setdefault(s["name"], []).append(
            {"file": s["file"], "line": s["line"], "kind": s["kind"],
             "module": s["module"]})

    # One alternation pass per line; longest-first so overlapping names
    # (_juna_lite vs _juna_lite_candidate) resolve to the longest match.
    ordered = sorted(names, key=len, reverse=True)
    combined = re.compile(
        r"(?<![A-Za-z0-9_!])(" + "|".join(re.escape(n) for n in ordered) +
        r")(?![A-Za-z0-9_!])")
    qualified = re.compile(r"\b(JunaCore|Juna)\.([A-Za-z_][A-Za-z0-9_!]*)")

    with open(os.path.join(root, "tools", "explorer", "suites.json")) as fh:
        suites = json.load(fh)["suites"]

    report = {"note": STATIC_NOTE, "suites": {}, "unresolved": []}
    for su in suites:
        path = os.path.join(root, "test", su["file"])
        if not os.path.isfile(path):
            report["unresolved"].append(
                {"suite": su["key"], "line": 0, "name": su["file"],
                 "reason": "suite file missing"})
            continue
        hits = {}
        with open(path) as fh:
            for lineno, line in enumerate(fh, 1):
                for m in combined.finditer(line):
                    hits.setdefault(m.group(1), []).append(lineno)
                for m in qualified.finditer(line):
                    trailing = m.group(2)
                    if trailing not in names and trailing not in _KNOWN_CONTAINERS:
                        report["unresolved"].append(
                            {"suite": su["key"], "line": lineno,
                             "name": m.group(0)})
        report["suites"][su["key"]] = {
            "file": su["file"],
            "direct": {n: lines[:50] for n, lines in sorted(hits.items())},
        }
    return report


def stage_evidence(root, report=None):
    """Per chain stage: which declared suites carry a DIRECT textual
    reference to at least one of the stage's symbols."""
    report = report or scan(root)
    with open(os.path.join(root, "tools", "explorer", "chain.json")) as fh:
        chain = json.load(fh)
    out = {}
    for stage in chain["stages"]:
        direct_suites = []
        for key in stage["suites"]:
            direct = report["suites"].get(key, {}).get("direct", {})
            if any(sym in direct for sym in stage["symbols"]):
                direct_suites.append(key)
        out[stage["id"]] = {"declared": stage["suites"],
                            "with_direct_reference": direct_suites}
    return out


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else \
        os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
    rep = scan(root)
    print(json.dumps({"note": rep["note"],
                      "per_suite_direct_counts": {
                          k: len(v["direct"]) for k, v in rep["suites"].items()},
                      "unresolved_count": len(rep["unresolved"]),
                      "stage_evidence": stage_evidence(root, rep)},
                     indent=2))
