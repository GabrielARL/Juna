#!/usr/bin/env python3
"""Independent on-disk acceptance checks for one AWGN-023C result."""

import argparse
import csv
import json
import os
import re

import build_results as builder


def require(condition, message):
    if not condition:
        raise builder.ResultContractError(
            "AWGN-023C validation failed: " + message)


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


def validate(experiment_dir,
             reference_results=builder.AWGN022_REFERENCE_RESULTS,
             reference_hashes=builder.AWGN022_REFERENCE_HASHES):
    (experiment_id, results_dir, geometry_values, expected_pfft, rows,
     sources, frame_sources, protected_sources, contracts,
     reference) = builder.collect(
         experiment_dir, reference_results=reference_results,
         reference_hashes=reference_hashes)
    columns, combined = _read_csv(
        os.path.join(results_dir, builder.OUTPUT_BASENAME))
    require(columns == builder.AGGREGATE_COLUMNS,
            "combined aggregate schema differs")
    require(combined == rows,
            "combined aggregate differs from path sources")
    manifest_path = os.path.join(results_dir, "results_manifest.json")
    require(os.path.isfile(manifest_path), "missing result manifest")
    require(not os.path.islink(manifest_path), "result manifest is a symlink")
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    expected_geometry = dict(zip(builder.GEOMETRY_KEYS, geometry_values))
    exact = {
        "schema_version": 1,
        "decision": "AWGN-023C",
        "experiment_id": experiment_id,
        "geometry": expected_geometry,
        "capture_time_seconds": [0.0, 32.0],
        "time_window_s": [0.0, 32.0],
        "frame_count": 128,
        "frames_per_point": 128,
        "seed": 4,
        "replay_passes": 4,
        "replay_windows_per_pass": 32,
        "base_snapshot_indices": list(builder.matrix_contract.BASE_SNAPSHOT_INDICES),
        "snapshot_indices": list(builder.SNAPSHOT_INDICES),
        "frame_window_selection": (
            "the first thirty-two seconds of measured replay are used in four "
            "passes; each pass uses the same thirty-two replay windows"),
        "receivers": sorted(builder.EXPECTED_RECEIVERS),
        "protected_receivers": sorted(builder.PROTECTED_RECEIVERS),
        "partial_fft_parts": expected_pfft,
        "partial_fft_bands": 16,
        "payload_bits_per_frame": 1616,
        "payload_bits_per_point": 206848,
        "row_count": 960,
        "frame_trace_row_count": 122880,
        "protected_trace_row_count": 49152,
        "panel_count": 12,
        "series_count": 60,
        "sources": sources,
        "frame_trace_sources": frame_sources,
        "protected_trace_sources": protected_sources,
        "path_contracts": contracts,
        "awgn022_reference": reference,
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
    require(page == builder.render_page(rows),
            "rendered page is not deterministic")
    require("AWGN-023C: BER versus SNR" in page,
            "approved title is absent")
    channel_text = (
        "Each panel uses one hydrophone from the first thirty-two seconds of "
        "the measured red replay capture. The same measured channel replay is "
        "used in four passes.")
    frames_text = (
        "Each SNR point uses 128 transmitted frames. Each pass uses the same "
        "thirty-two replay windows, while the payload and added AWGN change "
        "with the frame seed. Hence the curves average more transmitted frames "
        "but do not extend the measured channel observation beyond thirty-two "
        "seconds. All five receivers use the same transmitted frames, channel "
        "replay, and added AWGN.")
    noise_text = (
        "Only independent complex AWGN is added after the measured channel "
        "replay. Its real and imaginary components each receive half of the "
        "target complex-noise power.")
    receivers_text = (
        "JUNA-Lite is unchanged. JUNA (C,z) Joint gradient and Juna joint "
        "(C,W,z) use the CRC no-harm implementation. Standard is returned when "
        "Standard passes CRC or the gradient does not produce a CRC-valid "
        "output.")
    reading_text = (
        "Hollow markers are zero-observed-error points drawn at 0.5/payload "
        "bits; that height is a measurement limit, not a measured BER.")
    for label, approved in (
            ("Channel", channel_text), ("Frames", frames_text),
            ("Noise", noise_text), ("Receivers", receivers_text),
            ("Reading", reading_text)):
        require(approved in normalized_page,
                f"approved {label} statement is absent")
    require("one hundred twenty-eight seconds" not in normalized_page,
            "page misleadingly describes a 128-second observation")
    require(page.count('<path class="series"') == 60,
            "rendered series count differs")
    require(len(re.findall(r'<figure class="panel"', page)) == 12,
            "rendered panel count differs")
    for label in (
            "OFDM + FEC", "Partial-FFT + FEC", "JUNA-Lite",
            "JUNA (C,z) Joint gradient", "Juna joint (C,W,z)"):
        require(label in page, "rendered receiver label is absent: " + label)
    require(_no_partials(experiment_dir),
            "partial files remain after promotion")
    print(
        "VALID AWGN-023C: 12/12 paths, 960 aggregates, 122880 frame traces, "
        "49152 protected traces, 12 panels, 60 series, payload=1616"
    )
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment-dir", required=True)
    parser.add_argument("--reference-results",
                        default=builder.AWGN022_REFERENCE_RESULTS)
    args = parser.parse_args()
    try:
        validate(
            os.path.abspath(args.experiment_dir),
            reference_results=os.path.abspath(args.reference_results),
            reference_hashes=builder.AWGN022_REFERENCE_HASHES)
    except builder.ResultContractError as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
