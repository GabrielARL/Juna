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
    link route present. This contract checks the analyzer maintained by Juna.
C8  receivers.json freshness and integrity: it is exported from the Julia
    receiver catalog; receiver ids/facades are unique and exactly match the
    receivers declared by chain.json.
C9  multi-receiver DAG integrity: schema version 2, every receiver path and
    edge references real stages, paths start at acquisition, the three
    package facades are represented, and conditional edges carry labels.
C10 suite applicability is explicit and computable: each registry entry is
    structural, all receivers, one receiver, or a DAG stage; stage-scoped
    suites are declared on that stage; each receiver has universal coverage
    and either a receiver-specific suite or a justified exemption.
C11 reader-visible stage names exactly match the nine labels approved on
    2026-08-01, and the combiner-refit description follows the current code by
    stating that data-anchor confidence values weight the refit.
C12 the interface test uses the four reader-visible result labels approved on
    2026-08-01 and does not retain their ambiguous predecessors.
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
APPROVED_STAGE_TITLES = {
    "acquisition": "Packet acquisition",
    "ofdm_fec": "One-tap pilot-interpolated equalization + FEC",
    "seed": "Partial-FFT/FEC seed path",
    "posterior": "Posterior means and confidences",
    "anchors": "Anchor selection",
    "refit": "Combiner refit",
    "redecode": "Re-decode",
    "keep-best": "Candidate selection",
    "frame": "Frame-wide FEC receiver",
}


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

    # C8 receiver catalog freshness and integrity
    fd, tmp = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        run = subprocess.run(
            ["julia", "--project=.", os.path.join(HERE,
                                                  "export_receivers.jl"), tmp],
            capture_output=True, text=True, cwd=ROOT)
        if run.returncode != 0:
            problems.append("C8: export_receivers.jl failed: " +
                            run.stderr.strip()[-300:])
        else:
            with open(tmp) as fh:
                fresh = fh.read()
            with open(os.path.join(HERE, "receivers.json")) as fh:
                committed = fh.read()
            if fresh != committed:
                problems.append(
                    "C8: receivers.json is stale relative to "
                    "receiver_catalog.jl - rerun: julia --project=. "
                    "tools/explorer/export_receivers.jl")
    finally:
        os.unlink(tmp)
    with open(os.path.join(HERE, "receivers.json")) as fh:
        receivers = json.load(fh)["receivers"]
    receiver_ids = [r["id"] for r in receivers]
    facades = [r["facade"] for r in receivers]
    if len(set(receiver_ids)) != len(receiver_ids):
        problems.append("C8: duplicate receiver ids")
    if len(set(facades)) != len(facades):
        problems.append("C8: duplicate receiver facades")
    if set(receiver_ids) != {"ofdm_fec", "partial-fft", "lite"}:
        problems.append("C8: canonical receiver IDs must use ofdm_fec")
    ofdm_fec = next((r for r in receivers if r["id"] == "ofdm_fec"), {})
    expected_ofdm_fec = {
        "display_name": "OFDM+FEC",
        "facade": "JunaOFDMFEC",
        "mode": "ofdm_fec",
        "profile": "ofdm_fec",
        "chain_path": ["acquisition", "ofdm_fec"],
    }
    if any(ofdm_fec.get(key) != value
           for key, value in expected_ofdm_fec.items()):
        problems.append("C8: canonical OFDM+FEC catalog fields differ from "
                        f"{expected_ofdm_fec}")

    # C9 shared stage DAG integrity
    if chain.get("schema_version") != 2:
        problems.append("C9: chain schema_version must be 2")
    chain_receivers = chain.get("receivers", [])
    chain_ids = [r.get("id") for r in chain_receivers]
    if set(chain_ids) != set(receiver_ids):
        problems.append("C9: chain receiver ids do not match receivers.json")
    if set(facades) != {"JunaOFDMFEC", "JunaPartialFFT", "JunaLite"}:
        problems.append("C9: catalog must expose the three package facades")
    stage_ids = set(ids)
    for receiver in chain_receivers:
        path = receiver.get("path", [])
        if not path or path[0] != "acquisition":
            problems.append(
                f"C9: receiver '{receiver.get('id')}' must start at acquisition")
        for stage_id in path:
            if stage_id not in stage_ids:
                problems.append(
                    f"C9: receiver '{receiver.get('id')}' references unknown "
                    f"stage '{stage_id}'")
        for stage_id in receiver.get("optional_stages", []):
            if stage_id not in stage_ids:
                problems.append(
                    f"C9: receiver '{receiver.get('id')}' optional stage "
                    f"'{stage_id}' is unknown")
        catalog_receiver = next(
            (r for r in receivers if r["id"] == receiver.get("id")), None)
        if catalog_receiver and catalog_receiver["chain_path"] != path:
            problems.append(
                f"C9: receiver '{receiver.get('id')}' path differs between "
                "chain.json and receivers.json")
    conditional = 0
    for edge in chain.get("edges", []):
        if edge.get("from") not in stage_ids or edge.get("to") not in stage_ids:
            problems.append(f"C9: edge references unknown stage: {edge}")
        if edge.get("condition"):
            conditional += 1
    if conditional < 2:
        problems.append("C9: DAG must declare Lite's conditional exit/refine edges")

    # C10 executable test tiers and applicability
    allowed_tiers = {"structural", "universal", "mechanism",
                     "receiver-specific"}
    for suite in suites:
        tier = suite.get("tier")
        scope = suite.get("receivers", "")
        if tier not in allowed_tiers:
            problems.append(f"C10: suite '{suite['key']}' has invalid tier "
                            f"'{tier}'")
        if scope in {"structural", "all"}:
            continue
        prefix, sep, target = scope.partition(":")
        if sep != ":" or prefix not in {"stage", "receiver"}:
            problems.append(f"C10: suite '{suite['key']}' has invalid receiver "
                            f"scope '{scope}'")
        elif prefix == "stage":
            if target not in stage_ids:
                problems.append(f"C10: suite '{suite['key']}' references "
                                f"unknown stage '{target}'")
            else:
                stage = next(st for st in stages if st["id"] == target)
                if suite["key"] not in stage["suites"]:
                    problems.append(f"C10: stage-scoped suite '{suite['key']}' "
                                    f"is absent from stage '{target}'")
        elif target not in receiver_ids:
            problems.append(f"C10: suite '{suite['key']}' references unknown "
                            f"receiver '{target}'")
    if not any(s.get("tier") == "universal" and
               s.get("receivers") == "all" for s in suites):
        problems.append("C10: no universal all-receiver suite exists")
    specific = {s.get("receivers", "").split(":", 1)[1]
                for s in suites
                if s.get("tier") == "receiver-specific" and
                s.get("receivers", "").startswith("receiver:")}
    for receiver in receivers:
        if (receiver["id"] not in specific and
                not receiver.get("specific_suite_exemption")):
            problems.append(f"C10: receiver '{receiver['id']}' has neither a "
                            "receiver-specific suite nor an exemption")

    # C11 approved reader-visible stage names and code-authoritative wording
    actual_titles = {stage["id"]: stage.get("title") for stage in stages}
    if actual_titles != APPROVED_STAGE_TITLES:
        problems.append(
            "C11: stage titles differ from the nine labels approved on "
            f"2026-08-01: {actual_titles}")
    refit = next((stage for stage in stages if stage["id"] == "refit"), {})
    if "Data-anchor confidence values weight the refit." not in refit.get(
            "detail", ""):
        problems.append(
            "C11: combiner-refit detail does not state the current code's "
            "data-anchor confidence weighting")

    # C12 approved JNR-016 through JNR-019 interface result labels
    with open(os.path.join(ROOT, "test", "interface_contract.jl")) as fh:
        interface_test = fh.read()
    for marker in (
            '@testset verbose = true "Checks shared by all receivers" begin',
            '@testset "Receiver mode names map to their expected profiles" '
            'begin',
            '@testset "The default receiver is JUNA-Lite" begin',
            '@testset "$(descriptor.name) recovers all 128 test bits from '
            'its own clean waveform" begin',
            'println("Checks shared by all receivers passed")'):
        if marker not in interface_test:
            problems.append(
                f"C12: interface test lost approved result label {marker}")
    for old_label in (
            "JUNA interface contract",
            "receiver family includes per-symbol modes",
            "default constructor remains the Lite public alias",
            "interface + noiseless loopback decodes payload-exactly"):
        if old_label in interface_test:
            problems.append(
                f"C12: interface test retains old result label '{old_label}'")
    contract_suite = next((suite for suite in suites
                           if suite["key"] == "contract"), None)
    if (contract_suite is None or contract_suite.get("reader_title") !=
            "Checks shared by all receivers"):
        problems.append(
            "C12: contract registry reader title is not "
            "'Checks shared by all receivers'")

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
    print("explorer contract: PASS (C1-C12)")
