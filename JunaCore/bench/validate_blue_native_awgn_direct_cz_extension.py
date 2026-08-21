#!/usr/bin/env python3
"""Validate a native-Blue pilot-density result with direct C,z added."""

import csv
import json
import math
import os
import sys


NFFT = int(os.environ["JUNA_BLUE_NATIVE_NFFT"])
MODE = os.environ.get("JUNA_BLUE_DIRECT_CZ_MODE", "density")
REQUESTED_PERCENT = int(os.environ.get(
    "JUNA_BLUE_NATIVE_REQUESTED_PERCENT", "0"))
SPACING = int(os.environ.get("JUNA_BLUE_NATIVE_SPACING", "0"))
OUTER_SPACING = int(os.environ.get(
    "JUNA_BLUE_NATIVE_OUTER_SPACING", str(SPACING)))
INNER_SPACING = int(os.environ.get(
    "JUNA_BLUE_NATIVE_INNER_SPACING", str(SPACING)))
FRAME_BUDGET = float(os.environ["JUNA_BLUE_NATIVE_FRAME_BUDGET"])
PATHS = {(f"blue{channel}", lane)
         for channel in range(1, 5) for lane in range(1, 4)}
RECEIVERS = {
    "ofdm_fec", "pfft", "lite", "direct_cz", "profiled_cz", "cwz_joint",
}
PROTECTED = {"profiled_cz", "cwz_joint"}
SNRS = {float(value) for value in range(0, 31, 2)}


def require(condition, message):
    if not condition:
        raise SystemExit("Blue direct-CZ validation failed: " + message)


def truth(value):
    return value.lower() == "true"


def nearest_spacing(requested_total_percent):
    half_density = requested_total_percent / 200.0
    inverse = 1.0 / half_density
    lower = max(2, int(inverse // 1))
    upper = lower + 1
    return min((lower, upper),
               key=lambda value: (abs(half_density - 1.0 / value), value))


def main():
    require(NFFT in (512, 1024, 1152, 1200, 1280, 1344, 1408, 1536, 2048, 4096), "unsupported N")
    require(MODE in ("density", "baseline"), "unsupported experiment mode")
    if MODE == "density":
        require(REQUESTED_PERCENT in (10, 14, 20, 30, 60), "unsupported percentage")
        require(OUTER_SPACING == INNER_SPACING ==
                nearest_spacing(REQUESTED_PERCENT),
                "50/50 nearest spacing differs")
    else:
        require((OUTER_SPACING, INNER_SPACING) == (6, 8),
                "baseline spacing differs")
    expected_budget = 1.28 if MODE == "density" and NFFT == 4096 else 1.0
    require(FRAME_BUDGET == expected_budget, "frame budget differs")
    experiment_id = if_density = (
        "2026-08-13-blue-awgn-native-f47s-f1s-frames32-crc-no-harm-"
        f"n{NFFT}-d{REQUESTED_PERCENT}-p{SPACING}"
    )
    if MODE == "baseline":
        experiment_id = (
            "2026-08-13-blue-awgn-native-f47s-f1s-frames32-crc-no-harm-"
            f"n{NFFT}-cp64-r025-p6-8-dc14-kfill-pfft4"
        )
    package = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    experiment = (os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else
                  os.path.join(package, "experiments", experiment_id))
    results = os.path.join(experiment, "results")
    aggregate_name = "blue_snr_sweep_awgn_native_first47s_frames32_crc_no_harm.csv"
    aggregate_path = os.path.join(results, aggregate_name)
    require(os.path.isfile(aggregate_path), "missing aggregate")
    with open(aggregate_path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    require(len(rows) == 1_152,
            f"expected 1152 aggregates, found {len(rows)}")
    require({(row["channel"], int(row["lane"])) for row in rows} == PATHS,
            "path set differs")
    require({row["algorithm_id"] for row in rows} == RECEIVERS,
            "receiver set differs")
    require({float(row["snr_db"]) for row in rows} == SNRS,
            "SNR set differs")
    exact = {
        "seed": "4", "frames": "32", "noise_model": "awgn",
        "nfft": str(NFFT), "cp": "64", "code_rate": "0.25",
        "outer_spacing": str(OUTER_SPACING),
        "inner_spacing": str(INNER_SPACING),
        "check_degree": "14", "horizon": "0",
        "partial_fft_parts": "4", "capture_start_seconds": "0.0",
        "capture_stop_seconds": "47.0", "capture_tap_snapshots": "2295",
        "capture_phase_samples": "459184",
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
    require(len(aggregate_index) == 1_152, "aggregate keys are not unique")

    frame_total = selection_total = 0
    selection_counts = {receiver: {} for receiver in PROTECTED}
    sample_counts, durations, payloads = set(), set(), set()
    for channel, lane in sorted(PATHS):
        stem = f"{channel}_hydrophone{lane}"
        run = os.path.join(results, "runs", stem)
        per_path = os.path.join(
            run, "blue_snr_sweep_awgn_native_first47s_frames32_configuration.csv")
        frame_path = os.path.join(run, stem + "_frame_trace.csv")
        selection_path = os.path.join(run, stem + "_selection_trace.csv")
        with open(per_path, newline="", encoding="utf-8") as handle:
            path_rows = list(csv.DictReader(handle))
        with open(frame_path, newline="", encoding="utf-8") as handle:
            frames = list(csv.DictReader(handle))
        with open(selection_path, newline="", encoding="utf-8") as handle:
            selections = list(csv.DictReader(handle))
        require(len(path_rows) == 96, stem + " aggregate count differs")
        require(len(frames) == 3_072, stem + " frame trace count differs")
        require(len(selections) == 1_024,
                stem + " selection trace count differs")
        frame_total += len(frames)
        selection_total += len(selections)
        frame_index = {
            (float(row["snr_db"]), int(row["frame"]), row["algorithm_id"]): row
            for row in frames
        }
        require(len(frame_index) == 3_072, stem + " frame keys differ")
        sample_counts.update(int(row["frame_samples"]) for row in frames)
        durations.update(float(row["frame_duration_seconds"]) for row in frames)
        payloads.update(int(row["payload_bits"]) for row in frames)
        for row in selections:
            receiver = row["algorithm_id"]
            require(receiver in PROTECTED, "unprotected selection trace")
            counts = selection_counts[receiver]
            reason = row["selection_reason"]
            counts[reason] = counts.get(reason, 0) + 1
            if row["selected_source"] == "standard":
                key = (float(row["snr_db"]), int(row["frame"]), "lite")
                require(int(row["bit_errors"]) ==
                        int(frame_index[key]["bit_errors"]),
                        "standard selection differs from paired Lite")
        for receiver in RECEIVERS:
            for snr in SNRS:
                selected = [row for row in frames
                            if row["algorithm_id"] == receiver and
                            float(row["snr_db"]) == snr]
                require(len(selected) == 32, "frame group count differs")
                aggregate = aggregate_index[(channel, lane, snr, receiver)]
                require(sum(int(row["bit_errors"]) for row in selected) ==
                        int(aggregate["bit_errors"]),
                        "frame errors do not reconcile")
                require(sum(truth(row["success"]) for row in selected) ==
                        int(aggregate["successful_frames"]),
                        "frame successes do not reconcile")
    require(frame_total == 36_864, "total frame trace count differs")
    require(selection_total == 12_288, "total selection trace count differs")
    require(len(sample_counts) == len(durations) == len(payloads) == 1,
            "frame packing differs")
    sample_count, duration = next(iter(sample_counts)), next(iter(durations))
    require(0 < duration <= FRAME_BUDGET, "duration outside budget")
    require(math.isclose(duration, sample_count / 4_882.8125,
                         rel_tol=0.0, abs_tol=1e-12),
            "duration/sample identity differs")

    with open(os.path.join(results, "results_manifest.json"),
              encoding="utf-8") as handle:
        manifest = json.load(handle)
    require(manifest.get("experiment_id") == experiment_id,
            "manifest ID differs")
    require(set(manifest.get("receivers", [])) == RECEIVERS,
            "manifest receivers differ")
    require(manifest.get("receiver_policy", {}).get("direct_cz") ==
            "direct ungated C+z gradient",
            "manifest direct-CZ policy differs")
    require(manifest.get("row_count") == 1_152, "manifest rows differ")
    require(manifest.get("frame_trace_row_count") == 36_864,
            "manifest frame traces differ")
    require(manifest.get("selection_trace_row_count") == 12_288,
            "manifest selection traces differ")
    require(manifest.get("panel_count") == 12, "manifest panels differ")
    require(manifest.get("series_count") == 72, "manifest series differ")
    require(manifest.get("selection_reason_counts") == selection_counts,
            "manifest selection counts differ")
    require(manifest.get("frame_duration_budget_seconds") == FRAME_BUDGET,
            "manifest budget differs")
    require(manifest.get("frame_samples") == sample_count,
            "manifest samples differ")
    require(manifest.get("frame_duration_seconds") == duration,
            "manifest duration differs")
    html = open(os.path.join(results, "results_view.html"),
                encoding="utf-8").read()
    require("JUNA (C,z) direct" in html, "direct C,z missing from curves")
    require("Blue native-bandwidth replay + AWGN" in html,
            "Blue native-bandwidth label missing")
    print(
        f"VALID BLUE DIRECT CZ N{NFFT} mode={MODE} "
        f"P{OUTER_SPACING}/{INNER_SPACING}: 12/12 paths, 1152 aggregates, "
        f"{frame_total} frame traces, {selection_total} selection traces, "
        f"12 panels, 72 series, packed={duration}, samples={sample_count}"
    )


if __name__ == "__main__":
    main()
