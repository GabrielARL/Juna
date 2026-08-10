#!/usr/bin/env python3
"""Independent on-disk acceptance checks for one AWGN-020 result."""

import argparse
import csv
import json
import os
import re

import build_results as builder


def require(condition, message):
    if not condition:
        raise builder.ResultContractError(
            "AWGN-020 validation failed: " + message)


def _read_csv(path):
    require(os.path.isfile(path), "missing combined aggregate")
    require(not os.path.islink(path), "combined aggregate is a symlink")
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return tuple(reader.fieldnames or ()), list(reader)


def _no_partials(root):
    return not any(
        filename.endswith(".partial")
        for directory, _subdirs, files in os.walk(root)
        for filename in files
    )


def validate(experiment_dir, reference_csv=builder.FIRST4_REFERENCE_CSV,
             reference_sha256=builder.FIRST4_REFERENCE_SHA256):
    (experiment_id, results_dir, geometry_values, expected_pfft, rows,
     sources, frame_sources, protected_sources, contracts,
     first4) = builder.collect(
         experiment_dir, reference_csv=reference_csv,
         reference_sha256=reference_sha256)

    columns, combined = _read_csv(
        os.path.join(results_dir, builder.OUTPUT_BASENAME))
    require(columns == builder.AGGREGATE_COLUMNS,
            "combined aggregate schema differs")
    require(combined == rows, "combined aggregate differs from path sources")

    manifest_path = os.path.join(results_dir, "results_manifest.json")
    require(os.path.isfile(manifest_path), "missing result manifest")
    require(not os.path.islink(manifest_path), "result manifest is a symlink")
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    expected_geometry = dict(zip(builder.GEOMETRY_KEYS, geometry_values))
    exact = {
        "schema_version": 1,
        "decision": "AWGN-020",
        "experiment_id": experiment_id,
        "geometry": expected_geometry,
        "capture_time_seconds": [0.0, 8.0],
        "time_window_s": [0.0, 8.0],
        "frame_count": 8,
        "frames_per_point": 8,
        "seed": 4,
        "snapshot_indices": list(builder.SNAPSHOT_INDICES),
        "receivers": sorted(builder.EXPECTED_RECEIVERS),
        "protected_receivers": sorted(builder.PROTECTED_RECEIVERS),
        "partial_fft_parts": expected_pfft,
        "partial_fft_bands": 16,
        "payload_bits_per_frame": 1616,
        "row_count": 960,
        "frame_trace_row_count": 7680,
        "protected_trace_row_count": 3072,
        "panel_count": 12,
        "series_count": 60,
        "sources": sources,
        "frame_trace_sources": frame_sources,
        "protected_trace_sources": protected_sources,
        "path_contracts": contracts,
        "first_four_reference": first4,
    }
    for field, expected in exact.items():
        require(manifest.get(field) == expected, f"manifest {field} differs")
    require(manifest.get("noise_model", {}).get("kind") == "awgn",
            "manifest noise model differs")
    require(manifest.get("receiver_policy") == {
        "lite": "unchanged", "profiled_cz": "CRC no-harm",
        "cwz_joint": "CRC no-harm",
    }, "manifest receiver policy differs")
    source_contract, source_sha = builder._source_contract()
    require(manifest.get("source_contract") == source_contract
            and manifest.get("source_contract_sha256") == source_sha,
            "manifest source contract differs")
    require(manifest.get("runner_sources") == builder._family_source_hashes(),
            "manifest runner-source hashes differ")

    page_path = os.path.join(results_dir, "results_view.html")
    require(os.path.isfile(page_path), "missing rendered page")
    require(not os.path.islink(page_path), "rendered page is a symlink")
    with open(page_path, encoding="utf-8") as handle:
        page = handle.read()
    normalized_page = " ".join(page.split())
    require(page == builder.render_page(rows), "rendered page is not deterministic")
    require("AWGN-020: BER versus SNR" in page, "approved title is absent")
    require("first four replay windows are unchanged" in normalized_page,
            "approved nesting statement is absent")
    require("All five receivers use the" in normalized_page,
            "approved paired-receiver statement is absent")
    require(page.count('<path class="series"') == 60,
            "rendered series count differs")
    require(len(re.findall(r'<figure class="panel"', page)) == 12,
            "rendered panel count differs")
    for label in ("OFDM + FEC", "Partial-FFT + FEC", "JUNA-Lite",
                  "JUNA (C,z) Joint gradient", "Juna joint (C,W,z)"):
        require(label in page, "rendered receiver label is absent: " + label)
    require(_no_partials(experiment_dir), "partial files remain after promotion")
    print(
        "VALID AWGN-020: 12/12 paths, 960 aggregates, 7680 frame traces, "
        "3072 protected traces, 12 panels, 60 series, payload=1616"
    )
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment-dir", required=True)
    parser.add_argument("--reference-csv", default=builder.FIRST4_REFERENCE_CSV)
    args = parser.parse_args()
    try:
        validate(os.path.abspath(args.experiment_dir),
                 reference_csv=os.path.abspath(args.reference_csv),
                 reference_sha256=builder.FIRST4_REFERENCE_SHA256)
    except builder.ResultContractError as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
