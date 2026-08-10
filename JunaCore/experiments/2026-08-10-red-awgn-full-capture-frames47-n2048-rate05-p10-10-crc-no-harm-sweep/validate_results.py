#!/usr/bin/env python3
"""Independent on-disk acceptance checks for one AWGN-027 result."""

import argparse
import csv
import html
import json
import os
import re

import build_results as builder


def require(condition, message):
    if not condition:
        raise builder.ResultContractError(
            "AWGN-027 validation failed: " + message)


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


def validate(experiment_dir):
    (experiment_id, results_dir, geometry_values, expected_pfft, rows,
     sources, frame_sources, protected_sources, contracts) = builder.collect(
         experiment_dir)
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
    source_contract, source_sha = builder._source_contract()
    exact = {
        "schema_version": 1,
        "decision": "AWGN-027",
        "experiment_id": experiment_id,
        "geometry": expected_geometry,
        "capture_time_seconds": [0.0, 47.78125],
        "time_window_s": [0.0, 47.78125],
        "frame_count": 47,
        "frames_per_point": 47,
        "seed": 4,
        "snapshot_indices": list(builder.SNAPSHOT_INDICES),
        "schedule_provenance": source_contract["schedule_provenance"],
        "receivers": sorted(builder.EXPECTED_RECEIVERS),
        "protected_receivers": sorted(builder.PROTECTED_RECEIVERS),
        "partial_fft_parts": expected_pfft,
        "partial_fft_bands": 16,
        "payload_bits_per_frame": 3296,
        "payload_bits_per_point": 154912,
        "row_count": 960,
        "frame_trace_row_count": 45120,
        "protected_trace_row_count": 18048,
        "panel_count": 12,
        "series_count": 60,
        "sources": sources,
        "frame_trace_sources": frame_sources,
        "protected_trace_sources": protected_sources,
        "path_contracts": contracts,
    }
    for field, expected in exact.items():
        require(manifest.get(field) == expected, f"manifest {field} differs")
    require(manifest.get("noise_model", {}).get("kind") == "awgn",
            "manifest noise model differs")
    require(manifest.get("receiver_policy") == {
        "lite": "unchanged", "profiled_cz": "CRC no-harm",
        "cwz_joint": "CRC no-harm",
    }, "manifest receiver policy differs")
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
    require(page == builder.render_page(rows),
            "rendered page is not deterministic")
    require(page.count("AWGN-027: BER versus SNR") == 2,
            "approved title differs")
    block = re.search(r'<div class="provenance">(.*?)</div>', page, re.DOTALL)
    require(block is not None, "approved provenance block is absent")
    prose = " ".join(html.unescape(
        re.sub(r"<[^>]+>", "", block.group(1))).split())
    approved = (
        "Channel. Each panel uses one hydrophone from the complete measured "
        "red replay capture. Frames. Each SNR point uses forty-seven "
        "approximately non-overlapping frames whose complete replay windows "
        "fit inside the measured capture. All five receivers use the same "
        "transmitted frames, channel replay, and added AWGN. Noise. Only "
        "independent complex AWGN is added after the measured channel replay. "
        "Its real and imaginary components each receive half of the target "
        "complex-noise power. Receivers. JUNA-Lite is unchanged. JUNA (C,z) "
        "Joint gradient and Juna joint (C,W,z) use the CRC no-harm "
        "implementation. Standard is returned when Standard passes CRC or the "
        "gradient does not produce a CRC-valid output. Reading. Hollow markers "
        "are zero-observed-error points drawn at 0.5/payload bits; that height "
        "is a measurement limit, not a measured BER.")
    require(prose == approved, "approved provenance wording differs")
    require(page.count('<path class="series"') == 60,
            "rendered series count differs")
    require(len(re.findall(r'<figure class="panel"', page)) == 12,
            "rendered panel count differs")
    require(page.count("pilots=10/10") == 12,
            "printed pilot configuration differs")
    for label in (
            "OFDM + FEC", "Partial-FFT + FEC", "JUNA-Lite",
            "JUNA (C,z) Joint gradient", "Juna joint (C,W,z)"):
        require(label in page, "rendered receiver label is absent: " + label)
    require(_no_partials(experiment_dir),
            "partial files remain after promotion")
    print(
        "VALID AWGN-027: 12/12 paths, 960 aggregates, 45120 all-frame traces, "
        "18048 protected selection traces, 12 panels, 60 series, payload=3296"
    )
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment-dir", required=True)
    args = parser.parse_args()
    try:
        validate(os.path.abspath(args.experiment_dir))
    except builder.ResultContractError as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
