#!/usr/bin/env python3
"""Independent on-disk acceptance checks for one AWGN-024 result."""

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
            "AWGN-024 validation failed: " + message)


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
        "decision": "AWGN-024",
        "experiment_id": experiment_id,
        "geometry": expected_geometry,
        "capture_time_seconds": [0.0, 32.0],
        "time_window_s": [0.0, 32.0],
        "frame_count": 32,
        "frames_per_point": 32,
        "seed": 4,
        "snapshot_indices": list(builder.SNAPSHOT_INDICES),
        "receivers": sorted(builder.EXPECTED_RECEIVERS),
        "protected_receivers": sorted(builder.PROTECTED_RECEIVERS),
        "partial_fft_parts": expected_pfft,
        "partial_fft_bands": 16,
        "payload_bits_per_frame": 3248,
        "row_count": 960,
        "frame_trace_row_count": 30720,
        "protected_trace_row_count": 12288,
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
    require(page == builder.render_page(rows),
            "rendered page is not deterministic")
    require("AWGN-024: BER versus SNR" in page,
            "approved title is absent")
    block = re.search(r'<div class="provenance">(.*?)</div>', page, re.DOTALL)
    require(block is not None, "approved provenance block is absent")
    prose = " ".join(html.unescape(
        re.sub(r"<[^>]+>", "", block.group(1))).split())
    approved = (
        "Channel. Each panel uses one hydrophone from the first thirty-two "
        "seconds of the measured red replay capture. Frames. Each SNR point "
        "uses thirty-two approximately non-overlapping frames whose complete "
        "replay windows fit inside the first thirty-two seconds. The first "
        "sixteen replay windows are unchanged from the sixteen-second results; "
        "sixteen later replay windows extend the observation to thirty-two "
        "seconds. All five receivers use the same transmitted frames, channel "
        "replay, and added AWGN. Noise. Only independent complex AWGN is added "
        "after the measured channel replay. Its real and imaginary components "
        "each receive half of the target complex-noise power. Receivers. "
        "JUNA-Lite is unchanged. JUNA (C,z) Joint gradient and Juna joint "
        "(C,W,z) use the CRC no-harm implementation. Standard is returned when "
        "Standard passes CRC or the gradient does not produce a CRC-valid "
        "output. Reading. Hollow markers are zero-observed-error points drawn "
        "at 0.5/payload bits; that height is a measurement limit, not a "
        "measured BER.")
    require(prose == approved, "approved provenance wording differs")
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
        "VALID AWGN-024: 12/12 paths, 960 aggregates, 30720 frame traces, "
        "12288 protected traces, 12 panels, 60 series, payload=3248"
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
