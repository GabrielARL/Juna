#!/usr/bin/env python3
"""Snapshot and validate the Blue2-Blue4 acquisition-CFO rerun."""

import csv
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys


PACKAGE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(PACKAGE)
SOURCE = os.path.join(PACKAGE, "src", "juna", "common.jl")
CHANNELS = ("blue1",)
PRESERVED = ("blue2", "blue3", "blue4")
LANES = (1, 2, 3)
PER_PATH = "blue_snr_sweep_awgn_native_first47s_frames32_configuration.csv"
GATE_LIMIT = 0.1
# Record-only mode keeps the 0.1 gate as a recorded verdict but lets the
# campaign continue past a breach. Structural checks stay hard failures.
RECORD_ONLY = os.environ.get("JUNA_BLUE_CFOFIX_RECORD_ONLY") == "1"


def require(condition, message):
    if not condition:
        raise SystemExit("Blue CFO-fix validation failed: " + message)


def digest(path):
    value = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def preserved_snapshot(experiment):
    results = os.path.join(experiment, "results", "runs")
    snapshot = {}
    for channel in PRESERVED:
        for lane in LANES:
            root = os.path.join(results, f"{channel}_hydrophone{lane}")
            require(os.path.isdir(root), "missing preserved path " + root)
            for directory, _, names in os.walk(root):
                for name in sorted(names):
                    path = os.path.join(directory, name)
                    relative = os.path.relpath(
                        path, experiment).replace(os.sep, "/")
                    snapshot[relative] = digest(path)
    return snapshot


def load_rows(path):
    require(os.path.isfile(path), "missing " + path)
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def source_commit():
    return subprocess.check_output(
        ["git", "-C", REPO, "rev-parse", "HEAD"], text=True
    ).strip()


def validate_manifest(experiment, expected_commit):
    manifest_path = os.path.join(experiment, "results", "results_manifest.json")
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    rerun = manifest.get("blue1_refresh", {})
    require(manifest.get("acquisition_source_commit") == expected_commit,
            "manifest source commit differs")
    require(manifest.get("acquisition_source_sha256") == digest(SOURCE),
            "manifest acquisition source hash differs")
    require(rerun.get("channels") == list(CHANNELS),
            "manifest rerun channels differ")
    require(rerun.get("hydrophones") == list(LANES),
            "manifest rerun hydrophones differ")
    require(rerun.get("path_count") == 3,
            "manifest refresh path count differs")
    require(rerun.get("blue234_preserved") is True,
            "manifest does not record preserved Blue2-Blue4 evidence")
    recorded_max = float(rerun.get("high_snr_ofdm_ber_max", 1.0))
    if not (RECORD_ONLY and rerun.get("gate", {}).get("mode") == "record_only"):
        require(recorded_max < GATE_LIMIT, "manifest 30 dB OFDM gate differs")
    return manifest


def finalize(experiment, snapshot_path, started_ms, expected_commit):
    require(source_commit() == expected_commit,
            "repository HEAD changed during the rerun")
    with open(snapshot_path, encoding="utf-8") as handle:
        before = json.load(handle)
    require(preserved_snapshot(experiment) == before,
            "Blue2-Blue4 evidence changed during a Blue1-only refresh")

    results = os.path.join(experiment, "results", "runs")
    high_snr = []
    gate_failures = []
    for channel in CHANNELS:
        for lane in LANES:
            stem = f"{channel}_hydrophone{lane}"
            root = os.path.join(results, stem)
            required = (
                os.path.join(root, PER_PATH),
                os.path.join(root, stem + "_frame_trace.csv"),
                os.path.join(root, stem + "_selection_trace.csv"),
                os.path.join(root, f"n{os.environ['JUNA_BLUE_NATIVE_NFFT']}_crc_no_harm_path_contract.txt"),
            )
            for path in required:
                require(os.path.isfile(path), "missing refreshed file " + path)
                require(os.stat(path).st_mtime_ns / 1_000_000 >= started_ms,
                        "refreshed file predates rerun " + path)
            aggregates = load_rows(required[0])
            frames = load_rows(required[1])
            selections = load_rows(required[2])
            require(len(aggregates) == 96, stem + " aggregate count differs")
            require(len(frames) == 3_072, stem + " frame count differs")
            require(len(selections) == 1_024,
                    stem + " selection count differs")
            selected = [row for row in aggregates
                        if row["algorithm_id"] == "ofdm_fec" and
                        float(row["snr_db"]) == 30.0]
            require(len(selected) == 1, stem + " 30 dB OFDM row differs")
            ber = float(selected[0]["ber"])
            require(ber >= 0.0, f"{stem} 30 dB OFDM BER is negative: {ber}")
            if ber >= GATE_LIMIT:
                if not RECORD_ONLY:
                    require(False,
                            f"{stem} 30 dB OFDM BER is {ber}, "
                            f"expected below {GATE_LIMIT}")
                gate_failures.append({"path": stem, "ber": ber})
                print(f"BLUE_CFO_FIX_GATE_FAIL path={stem} ber={ber!r} "
                      f"limit={GATE_LIMIT}")
            high_snr.append(ber)

    manifest_path = os.path.join(experiment, "results", "results_manifest.json")
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    manifest["acquisition_source_commit"] = expected_commit
    manifest["acquisition_source_sha256"] = digest(SOURCE)
    manifest["blue1_refresh"] = {
        "channels": list(CHANNELS),
        "hydrophones": list(LANES),
        "path_count": 3,
        "blue234_preserved": True,
        "high_snr_ofdm_ber_max": max(high_snr),
        "gate": {
            "limit": GATE_LIMIT,
            "mode": "record_only" if RECORD_ONLY else "enforced",
            "failures": gate_failures,
        },
        "completed_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    with open(manifest_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    validate_manifest(experiment, expected_commit)
    verdict = "VALID" if not gate_failures else "RECORDED-WITH-GATE-FAILURES"
    print(
        f"{verdict} BLUE1 REFRESH channels=blue1 paths=3 "
        f"max_30db_ofdm_ber={max(high_snr):.9g} "
        f"gate_failures={len(gate_failures)} "
        f"commit={expected_commit[:12]}"
    )


def main():
    require(len(sys.argv) >= 3,
            "usage: snapshot EXPERIMENT JSON | finalize EXPERIMENT JSON START_MS COMMIT | check EXPERIMENT COMMIT")
    mode = sys.argv[1]
    experiment = os.path.abspath(sys.argv[2])
    if mode == "snapshot":
        require(len(sys.argv) == 4, "snapshot arguments differ")
        with open(sys.argv[3], "w", encoding="utf-8", newline="\n") as handle:
            json.dump(preserved_snapshot(experiment), handle, indent=2,
                      sort_keys=True)
            handle.write("\n")
        print("BLUE234 SNAPSHOT paths=9")
    elif mode == "finalize":
        require(len(sys.argv) == 6, "finalize arguments differ")
        finalize(experiment, sys.argv[3], int(sys.argv[4]), sys.argv[5])
    elif mode == "check":
        require(len(sys.argv) == 4, "check arguments differ")
        validate_manifest(experiment, sys.argv[3])
        print("VALID BLUE CFO FIX MANIFEST " + os.path.basename(experiment))
    else:
        raise SystemExit("unknown mode " + mode)


if __name__ == "__main__":
    main()
