#!/usr/bin/env python3
"""Compose the twelve-path, five-receiver min-BER CSV and its manifest."""

import csv
import hashlib
import json
import os


HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT = "red_snr_sweep_uwa_noise.csv"

EXPECTED_RECEIVERS = {"ofdm_fec", "pfft", "lite", "profiled_cz", "cwz_joint"}
EXPECTED_SNRS = {float(value) for value in range(0, 31, 2)}
EXPECTED_PATHS = tuple(
    (f"red{capture}", lane)
    for capture in range(1, 5)
    for lane in range(1, 4)
)
EXPECTED_GEOMETRIES = {
    ("red1", 1): ("2048", "32", "0.25", "3", "10", "10", "4"),
    ("red1", 2): ("2048", "32", "0.25", "3", "8", "10", "4"),
    ("red1", 3): ("2048", "128", "0.5", "5", "5", "10", "4"),
    ("red2", 1): ("512", "32", "0.25", "3", "10", "10", "0"),
    ("red2", 2): ("2048", "0", "0.25", "5", "5", "10", "1"),
    ("red2", 3): ("2048", "0", "0.25", "5", "5", "10", "4"),
    ("red3", 1): ("2048", "32", "0.125", "5", "8", "10", "0"),
    ("red3", 2): ("2048", "128", "0.25", "5", "10", "10", "0"),
    ("red3", 3): ("2048", "16", "0.25", "5", "8", "10", "0"),
    ("red4", 1): ("2048", "32", "0.25", "5", "10", "10", "4"),
    ("red4", 2): ("2048", "16", "0.25", "5", "5", "10", "4"),
    ("red4", 3): ("2048", "0", "0.5", "5", "5", "10", "4"),
}
GEOMETRY_KEYS = (
    "nfft", "cp", "code_rate", "outer_spacing", "inner_spacing",
    "check_degree", "horizon",
)


def source_name(channel, lane):
    return (f"runs/{channel}_hydrophone{lane}/"
            "red_snr_sweep_uwa_noise_minber.csv")


def geometry_dict(values):
    return dict(zip(GEOMETRY_KEYS, values))


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
    for channel, lane in EXPECTED_PATHS:
        source = source_name(channel, lane)
        source_columns, source_rows = load(source)
        if columns is None:
            columns = source_columns
        elif source_columns != columns:
            raise SystemExit(f"source columns differ: {source}")
        if len(source_rows) != 80:
            raise SystemExit(
                f"expected 80 rows for {channel} hydrophone {lane}, "
                f"found {len(source_rows)}")
        if {row["algorithm_id"] for row in source_rows} != EXPECTED_RECEIVERS:
            raise SystemExit(
                f"receiver set differs for {channel} hydrophone {lane}")
        if {(row["channel"], int(row["lane"])) for row in source_rows} != {
                (channel, lane)}:
            raise SystemExit(f"source path differs: {source}")
        if {row["objective"] for row in source_rows} != {"min-BER"}:
            raise SystemExit(f"source objective differs: {source}")
        if {row["frames"] for row in source_rows} != {"60"}:
            raise SystemExit(f"source frame count differs: {source}")
        if {row["seed"] for row in source_rows} != {"4"}:
            raise SystemExit(f"source seed differs: {source}")
        if {float(row["snr_db"]) for row in source_rows} != EXPECTED_SNRS:
            raise SystemExit(f"source SNR set differs: {source}")
        expected_geometry = EXPECTED_GEOMETRIES[(channel, lane)]
        if any(tuple(row[key] for key in GEOMETRY_KEYS) != expected_geometry
               for row in source_rows):
            raise SystemExit(f"source geometry differs: {source}")
        keys = {(row["algorithm_id"], float(row["snr_db"]))
                for row in source_rows}
        if len(keys) != 80:
            raise SystemExit(f"source receiver/SNR rows are duplicated: {source}")
        rows.extend(source_rows)
        sources.append({
            "path": source,
            "rows": len(source_rows),
            "retained_rows": len(source_rows),
            "sha256": digest(source),
        })

    rows = sorted(rows,
                  key=lambda row: (int(row["channel"][3:]),
                                   int(row["lane"]), float(row["snr_db"]),
                                   row["algorithm_id"]))
    if len(rows) != 960:
        raise SystemExit(f"expected 960 selected rows, found {len(rows)}")
    if {row["algorithm_id"] for row in rows} != EXPECTED_RECEIVERS:
        raise SystemExit("selected receiver set differs")

    output_path = os.path.join(HERE, OUTPUT)
    with open(output_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)

    manifest = {
        "decisions": ["CL-28", "CL-29", "CL-30", "CL-32", "CL-33", "CL-35"],
        "experiment_id": "2026-08-04-red-snr-sweep",
        "geometries": {
            "min-BER": {
                f"{channel} {lane}": geometry_dict(
                    EXPECTED_GEOMETRIES[(channel, lane)])
                for channel, lane in EXPECTED_PATHS
            }
        },
        "noise_model": {
            "alpha": 1.7,
            "generator": "uwa-channels/python src/uwa_channels/noisegen.py, mixing path",
            "note": "impulsive, correlated across three hydrophones",
            "source": "red_noise.mat, Zenodo record 21287414",
        },
        "not_comparable_with": (
            "2026-08-01-red-lite-search: different channel-application path "
            "(uwa-channels mixing model, not the harness AWGN)"),
        "objectives": ["min-BER"],
        "paths": [f"{channel} {lane}" for channel, lane in EXPECTED_PATHS],
        "receivers": sorted(EXPECTED_RECEIVERS),
        "result_scope": "BER versus added-noise SNR, 60 frames per point, seed 4",
        "row_count": len(rows),
        "schema_version": 2,
        "snr_db": [float(value) for value in range(0, 31, 2)],
        "snr_definition": (
            "signal power over the alpha-stable pseudo-power 2*delta^2; "
            "Mahmood & Chitre, IEEE JOE 42(3) 2017, eq. (35)"),
        "sources": sources,
        "supersedes": {"CL-35": ["CL-32"]},
    }
    with open(os.path.join(HERE, "results_manifest.json"), "w",
              encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")

    print("composed 960 rows: 5 receivers, 16 SNR points, "
          "12 min-BER panels")


if __name__ == "__main__":
    main()
