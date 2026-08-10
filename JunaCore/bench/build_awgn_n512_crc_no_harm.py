#!/usr/bin/env python3
"""Build the N=512 CRC-gated no-harm AWGN aggregate and page."""

import csv
import hashlib
import json
import os
import subprocess
import sys


CAPTURE_SECONDS = int(os.environ.get("JUNA_N512_NO_HARM_CAPTURE_SECONDS", "32"))
EXPERIMENT_ID = (
    f"2026-08-10-red-awgn-first{CAPTURE_SECONDS}s-frames32-crc-gated-no-harm-"
    "n512-cp64-rate025-p5-5-dc14-kfill-pfft4"
)
PATHS = [(f"red{channel}", lane)
         for channel in range(1, 5) for lane in range(1, 4)]
PER_PATH = f"red_snr_sweep_awgn_first{CAPTURE_SECONDS}s_frames32_configuration.csv"
AGGREGATE = f"red_snr_sweep_awgn_first{CAPTURE_SECONDS}s_frames32_crc_no_harm.csv"


def digest(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def main():
    package = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    experiment = (os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else
                  os.path.join(package, "experiments", EXPERIMENT_ID))
    results = os.path.join(experiment, "results")
    rows, columns, sources = [], None, []
    reason_counts = {
        "profiled_cz": {}, "cwz_joint": {},
    }
    for channel, lane in PATHS:
        stem = f"{channel}_hydrophone{lane}"
        relative = os.path.join("runs", stem, PER_PATH)
        source = os.path.join(results, relative)
        with open(source, newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            current_columns = list(reader.fieldnames or [])
            current_rows = list(reader)
        if len(current_rows) != 80:
            raise SystemExit("per-path aggregate row count differs: " + relative)
        if columns is None:
            columns = current_columns
        elif columns != current_columns:
            raise SystemExit("per-path aggregate columns differ: " + relative)
        rows.extend(current_rows)
        trace = os.path.join(results, "runs", stem, stem + "_selection_trace.csv")
        with open(trace, newline="", encoding="utf-8") as handle:
            trace_rows = list(csv.DictReader(handle))
        if len(trace_rows) != 1024:
            raise SystemExit("selection trace row count differs: " + stem)
        for row in trace_rows:
            counts = reason_counts[row["algorithm_id"]]
            reason = row["selection_reason"]
            counts[reason] = counts.get(reason, 0) + 1
        sources.append({
            "path": relative.replace(os.sep, "/"),
            "rows": 80,
            "sha256": digest(source),
        })
    rows.sort(key=lambda row: (
        int(row["channel"][3:]), int(row["lane"]),
        float(row["snr_db"]), row["algorithm_id"]))
    output = os.path.join(results, AGGREGATE)
    with open(output, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    payloads = sorted({int(row["payload_bits_per_frame"]) for row in rows})
    manifest = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "result_group": "awgn",
        "result_scope": (
            f"BER versus SNR, first {CAPTURE_SECONDS} seconds, "
            "32 frames per point, seed 4"
        ),
        "geometry": {
            "nfft": "512", "cp": "64", "code_rate": "0.25",
            "outer_spacing": "5", "inner_spacing": "5",
            "check_degree": "14", "horizon": "0",
        },
        "geometry_display": {
            "nfft": "512", "cp": "64", "code_rate": "0.25",
            "outer_spacing": "5", "inner_spacing": "5",
            "check_degree": "14", "horizon": "fill",
            "partial_fft_parts": "4",
        },
        "frames_per_point": 32,
        "seed": 4,
        "capture_time_seconds": [0.0, float(CAPTURE_SECONDS)],
        "noise_model": {
            "kind": "awgn",
            "distribution": "proper-complex Gaussian",
            "injection": "after measured replay, before receiver alignment",
        },
        "receivers": [
            "cwz_joint", "lite", "ofdm_fec", "pfft", "profiled_cz",
        ],
        "receiver_policy": {
            "lite": "unchanged",
            "profiled_cz": "CRC-gated no-harm C+z",
            "cwz_joint": "CRC-gated no-harm C+W+z",
        },
        "no_harm_rule": {
            "standard_crc_valid": "return standard without gradient rescue",
            "crc_rescue": "return gradient only when its CRC is valid",
            "standard_fallback": "return standard when rescue CRC is invalid",
            "implementation": (
                "experiment-boundary instrumentation of the checked-in "
                "cz_crc_gate receiver; not the unpublished AWGN-022 wrapper"
            ),
        },
        "selection_reason_counts": reason_counts,
        "partial_fft_parts": 4,
        "payload_bits_per_frame": payloads[0],
        "row_count": 960,
        "frame_trace_row_count": 30_720,
        "selection_trace_row_count": 12_288,
        "panel_count": 12,
        "series_count": 60,
        "sources": sources,
    }
    with open(os.path.join(results, "results_manifest.json"), "w",
              encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    source_root = os.environ.get("JUNA_N512_NO_HARM_SOURCE_ROOT", repo_root)
    renderer = os.environ.get(
        "JUNA_N512_AWGN_RENDERER",
        os.path.join(
            source_root, "JunaCore", "experiments",
            "2026-08-08-red-awgn-snr-sweep", "build_awgn_view.py",
        ),
    )
    if not os.path.isfile(renderer):
        raise FileNotFoundError(
            "missing AWGN renderer; set JUNA_N512_AWGN_RENDERER or "
            "JUNA_N512_NO_HARM_SOURCE_ROOT"
        )
    subprocess.run([
        sys.executable, renderer, "--csv", output, "--out",
        os.path.join(results, "results_view.html"),
    ], check=True)
    print(
        f"BUILT N512 CRC NO-HARM FIRST{CAPTURE_SECONDS}S: 960 aggregates, "
        "30720 frame traces, "
        f"12288 selection traces, payload={payloads[0]}"
    )


if __name__ == "__main__":
    main()
