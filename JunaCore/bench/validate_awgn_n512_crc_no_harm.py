#!/usr/bin/env python3
"""Strictly validate the N=512 CRC-gated no-harm AWGN result."""

import csv
import json
import math
import os
import sys


CAPTURE_SECONDS = int(os.environ.get("JUNA_N512_NO_HARM_CAPTURE_SECONDS", "32"))
EXPERIMENT_ID = (
    f"2026-08-10-red-awgn-first{CAPTURE_SECONDS}s-frames32-crc-gated-no-harm-"
    "n512-cp64-rate025-p5-5-dc14-kfill-pfft4"
)
PATHS = {(f"red{channel}", lane)
         for channel in range(1, 5) for lane in range(1, 4)}
RECEIVERS = {"ofdm_fec", "pfft", "lite", "profiled_cz", "cwz_joint"}
PROTECTED = {"profiled_cz", "cwz_joint"}
SNRS = {float(value) for value in range(0, 31, 2)}


def require(condition, message):
    if not condition:
        raise SystemExit("N512 CRC no-harm validation failed: " + message)


def truth(value):
    return value.lower() == "true"


def main():
    package = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    experiment = (os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else
                  os.path.join(package, "experiments", EXPERIMENT_ID))
    results = os.path.join(experiment, "results")
    aggregate_path = os.path.join(
        results,
        f"red_snr_sweep_awgn_first{CAPTURE_SECONDS}s_frames32_crc_no_harm.csv")
    require(os.path.isfile(aggregate_path), "missing aggregate")
    with open(aggregate_path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    require(len(rows) == 960, f"expected 960 aggregates, found {len(rows)}")
    require({(row["channel"], int(row["lane"])) for row in rows} == PATHS,
            "path set differs")
    require({row["algorithm_id"] for row in rows} == RECEIVERS,
            "receiver set differs")
    require({float(row["snr_db"]) for row in rows} == SNRS,
            "SNR set differs")
    exact = {
        "seed": "4", "frames": "32", "noise_model": "awgn",
        "nfft": "512", "cp": "64", "code_rate": "0.25",
        "outer_spacing": "5", "inner_spacing": "5",
        "check_degree": "14", "horizon": "0",
        "partial_fft_parts": "4", "capture_start_seconds": "0.0",
        "capture_stop_seconds": f"{float(CAPTURE_SECONDS)}",
        "capture_tap_snapshots": str(CAPTURE_SECONDS * 96 + 1),
        "capture_phase_samples": str(CAPTURE_SECONDS * 19_200 + 200),
    }
    for field, expected in exact.items():
        require({row[field] for row in rows} == {expected}, field + " differs")
    require(all(math.isfinite(float(row["ber"])) and
                0 <= float(row["ber"]) <= 1 for row in rows),
            "BER is not finite in [0,1]")
    aggregate_index = {
        (row["channel"], int(row["lane"]), float(row["snr_db"]),
         row["algorithm_id"]): row for row in rows
    }
    require(len(aggregate_index) == 960, "aggregate keys are not unique")

    frame_total = selection_total = 0
    selection_counts = {receiver: {} for receiver in PROTECTED}
    for channel, lane in sorted(PATHS):
        stem = f"{channel}_hydrophone{lane}"
        run = os.path.join(results, "runs", stem)
        frame_path = os.path.join(run, stem + "_frame_trace.csv")
        selection_path = os.path.join(run, stem + "_selection_trace.csv")
        contract_path = os.path.join(run, "n512_crc_no_harm_path_contract.txt")
        require(os.path.isfile(contract_path), stem + " missing contract")
        with open(frame_path, newline="", encoding="utf-8") as handle:
            frames = list(csv.DictReader(handle))
        with open(selection_path, newline="", encoding="utf-8") as handle:
            selections = list(csv.DictReader(handle))
        require(len(frames) == 2560, stem + " frame trace count differs")
        require(len(selections) == 1024,
                stem + " selection trace count differs")
        frame_total += len(frames)
        selection_total += len(selections)
        frame_index = {
            (float(row["snr_db"]), int(row["frame"]), row["algorithm_id"]): row
            for row in frames
        }
        require(len(frame_index) == 2560, stem + " frame keys differ")
        for row in selections:
            receiver = row["algorithm_id"]
            require(receiver in PROTECTED, "unprotected selection trace")
            reason = row["selection_reason"]
            counts = selection_counts[receiver]
            counts[reason] = counts.get(reason, 0) + 1
            selected = row["selected_source"]
            standard_valid = truth(row["standard_crc_valid"])
            rescue = truth(row["rescue_executed"])
            rescue_valid = truth(row["rescue_crc_valid"])
            checkpoints = int(row["gradient_checkpoints"])
            if reason == "standard_crc_valid":
                require(selected == "standard" and standard_valid and
                        not rescue and not rescue_valid and checkpoints == 0,
                        "standard short-circuit trace differs")
            elif reason == "crc_rescue":
                require(selected == "gradient" and not standard_valid and
                        rescue and rescue_valid and checkpoints > 0,
                        "CRC rescue trace differs")
            elif reason == "standard_fallback":
                require(selected == "standard" and not standard_valid and
                        rescue and not rescue_valid and checkpoints > 0,
                        "standard fallback trace differs")
            else:
                require(False, "unknown selection reason " + reason)
            if selected == "standard":
                key = (float(row["snr_db"]), int(row["frame"]), "lite")
                require(int(row["bit_errors"]) ==
                        int(frame_index[key]["bit_errors"]),
                        "standard selection differs from paired Lite")
        for receiver in RECEIVERS:
            for snr in SNRS:
                selected_frames = [
                    row for row in frames
                    if row["algorithm_id"] == receiver and
                    float(row["snr_db"]) == snr
                ]
                require(len(selected_frames) == 32,
                        "frame group count differs")
                aggregate = aggregate_index[(channel, lane, snr, receiver)]
                require(sum(int(row["bit_errors"]) for row in selected_frames) ==
                        int(aggregate["bit_errors"]),
                        "frame errors do not reconcile")
                require(sum(truth(row["success"]) for row in selected_frames) ==
                        int(aggregate["successful_frames"]),
                        "frame successes do not reconcile")
    require(frame_total == 30720, "total frame trace count differs")
    require(selection_total == 12288, "total selection trace count differs")
    manifest_path = os.path.join(results, "results_manifest.json")
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    require(manifest.get("experiment_id") == EXPERIMENT_ID,
            "manifest ID differs")
    require(manifest.get("row_count") == 960, "manifest row count differs")
    require(manifest.get("frame_trace_row_count") == 30720,
            "manifest frame trace count differs")
    require(manifest.get("selection_trace_row_count") == 12288,
            "manifest selection trace count differs")
    require(manifest.get("panel_count") == 12, "manifest panels differ")
    require(manifest.get("series_count") == 60, "manifest series differ")
    require(manifest.get("selection_reason_counts") == selection_counts,
            "manifest selection counts differ")
    require(os.path.isfile(os.path.join(results, "results_view.html")),
            "missing rendered results page")
    print(
        f"VALID N512 CRC NO-HARM FIRST{CAPTURE_SECONDS}S: 12/12 paths, "
        "960 aggregates, "
        "30720 frame traces, 12288 selection traces, 12 panels, 60 series"
    )


if __name__ == "__main__":
    main()
