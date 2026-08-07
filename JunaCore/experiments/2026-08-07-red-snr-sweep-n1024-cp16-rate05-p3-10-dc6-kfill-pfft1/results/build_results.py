#!/usr/bin/env python3
"""Compose the N=1024, CP=16, rate=0.5, pilots=3/10, K=fill, PFFT=1 result."""

import csv
import hashlib
import json
import os


HERE = os.path.dirname(os.path.abspath(__file__))
EXPERIMENT_ID = (
    "2026-08-07-red-snr-sweep-n1024-cp16-rate05-p3-10-dc6-kfill-pfft1")
OUTPUT = "red_snr_sweep_uwa_noise.csv"
SOURCE_BASENAME = "red_snr_sweep_uwa_noise_configuration.csv"
EXPECTED_RECEIVERS = {"ofdm_fec", "pfft", "lite", "profiled_cz", "cwz_joint"}
EXPECTED_SNRS = {float(value) for value in range(0, 31, 2)}
EXPECTED_PATHS = tuple(
    (f"red{capture}", lane)
    for capture in range(1, 5)
    for lane in range(1, 4)
)
GEOMETRY_KEYS = (
    "nfft", "cp", "code_rate", "outer_spacing", "inner_spacing",
    "check_degree", "horizon",
)
EXPECTED_GEOMETRY = ("1024", "16", "0.5", "3", "10", "6", "0")
EXPECTED_PAYLOAD_BITS_PER_FRAME = 3044
EXPECTED_PARTIAL_FFT_PARTS = 1


def source_name(channel, lane):
    return f"runs/{channel}_hydrophone{lane}/{SOURCE_BASENAME}"


def trace_name(channel, lane):
    return (f"runs/{channel}_hydrophone{lane}/"
            f"{channel}_hydrophone{lane}_selection_trace.csv")


def load(name):
    path = os.path.join(HERE, name)
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def digest(name):
    with open(os.path.join(HERE, name), "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def main():
    columns = None
    rows = []
    sources = []
    trace_sources = []
    for channel, lane in EXPECTED_PATHS:
        source = source_name(channel, lane)
        source_columns, source_rows = load(source)
        if columns is None:
            columns = source_columns
        elif source_columns != columns:
            raise SystemExit(f"source columns differ: {source}")
        if len(source_rows) != 80:
            raise SystemExit(
                f"expected 80 rows, found {len(source_rows)}: {source}")
        if {row["algorithm_id"] for row in source_rows} != EXPECTED_RECEIVERS:
            raise SystemExit(f"receiver set differs: {source}")
        if {(row["channel"], int(row["lane"])) for row in source_rows} != {
                (channel, lane)}:
            raise SystemExit(f"capture/hydrophone differs: {source}")
        if {row["objective"] for row in source_rows} != {"configuration"}:
            raise SystemExit(f"result group differs: {source}")
        if {row["frames"] for row in source_rows} != {"60"}:
            raise SystemExit(f"frame count differs: {source}")
        if {row["seed"] for row in source_rows} != {"4"}:
            raise SystemExit(f"seed differs: {source}")
        if {int(row["partial_fft_parts"]) for row in source_rows} != {
                EXPECTED_PARTIAL_FFT_PARTS}:
            raise SystemExit(f"partial-FFT part count differs: {source}")
        if {float(row["snr_db"]) for row in source_rows} != EXPECTED_SNRS:
            raise SystemExit(f"SNR set differs: {source}")
        if any(tuple(row[key] for key in GEOMETRY_KEYS) != EXPECTED_GEOMETRY
               for row in source_rows):
            raise SystemExit(f"geometry differs: {source}")
        if {int(row["payload_bits_per_frame"]) for row in source_rows} != {
                EXPECTED_PAYLOAD_BITS_PER_FRAME}:
            raise SystemExit(f"payload capacity differs: {source}")
        keys = {(row["algorithm_id"], float(row["snr_db"]))
                for row in source_rows}
        if len(keys) != 80:
            raise SystemExit(f"receiver/SNR rows are duplicated: {source}")
        rows.extend(source_rows)
        sources.append({
            "path": source,
            "rows": 80,
            "retained_rows": 80,
            "sha256": digest(source),
        })

        trace = trace_name(channel, lane)
        _trace_columns, trace_rows = load(trace)
        if len(trace_rows) != 1920:
            raise SystemExit(
                f"expected 1920 trace rows, found {len(trace_rows)}: {trace}")
        if {row["algorithm_id"] for row in trace_rows} != {
                "profiled_cz", "cwz_joint"}:
            raise SystemExit(f"trace receiver set differs: {trace}")
        if {row["selection_reason"] for row in trace_rows} != {"gradient_only"}:
            raise SystemExit(f"trace selection reason differs: {trace}")
        if {int(row["partial_fft_parts"]) for row in trace_rows} != {
                EXPECTED_PARTIAL_FFT_PARTS}:
            raise SystemExit(f"trace partial-FFT part count differs: {trace}")
        trace_sources.append({
            "path": trace,
            "rows": 1920,
            "sha256": digest(trace),
        })

    rows.sort(key=lambda row: (int(row["channel"][3:]), int(row["lane"]),
                               float(row["snr_db"]), row["algorithm_id"]))
    if len(rows) != 960:
        raise SystemExit(f"expected 960 rows, found {len(rows)}")
    with open(os.path.join(HERE, OUTPUT), "w", newline="",
              encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    geometry = dict(zip(GEOMETRY_KEYS, EXPECTED_GEOMETRY))
    manifest = {
        "decisions": ["CL-29", "CL-30", "CL-33", "CL-36", "CL-38", "CL-41"],
        "experiment_id": EXPERIMENT_ID,
        "geometry": geometry,
        "geometry_display": dict(geometry),
        "noise_model": {
            "alpha": 1.7,
            "generator": (
                "uwa-channels/python src/uwa_channels/noisegen.py, mixing path"),
            "note": "impulsive, correlated across three hydrophones",
            "source": "red_noise.mat, Zenodo record 21287414",
        },
        "not_comparable_with": (
            "2026-08-01-red-lite-search: different channel-application path "
            "(uwa-channels mixing model, not the harness AWGN)"),
        "paths": [f"{channel} {lane}" for channel, lane in EXPECTED_PATHS],
        "receivers": sorted(EXPECTED_RECEIVERS),
        "partial_fft_parts": EXPECTED_PARTIAL_FFT_PARTS,
        "result_group": "configuration",
        "result_scope": "BER versus added-noise SNR, 60 frames per point, seed 4",
        "row_count": 960,
        "schema_version": 2,
        "snr_db": [float(value) for value in range(0, 31, 2)],
        "snr_definition": (
            "signal power over the alpha-stable pseudo-power 2*delta^2; "
            "Mahmood & Chitre, IEEE JOE 42(3) 2017, eq. (35)"),
        "sources": sources,
        "trace_sources": trace_sources,
    }
    with open(os.path.join(HERE, "results_manifest.json"), "w",
              encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print("composed 960 rows: 5 receivers, 16 SNR points, 12 panels, PFFT=1")


if __name__ == "__main__":
    main()
