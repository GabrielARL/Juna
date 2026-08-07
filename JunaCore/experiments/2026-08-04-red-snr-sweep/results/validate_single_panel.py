#!/usr/bin/env python3
"""Validate the twelve-panel, five-receiver min-BER SNR result."""

import csv
import hashlib
import json
import os


HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, "red_snr_sweep_uwa_noise.csv")
HTML_PATH = os.path.join(HERE, "results_view.html")
MANIFEST_PATH = os.path.join(HERE, "results_manifest.json")

EXPECTED_RECEIVERS = {
    "ofdm_fec",
    "pfft",
    "lite",
    "profiled_cz",
    "cwz_joint",
}
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
EXPECTED_LABELS = {
    "OFDM + FEC",
    "Partial-FFT + FEC",
    "JUNA-Lite",
    "JUNA (C,z) Joint gradient",
    "Juna joint (C,W,z)",
}
REPLACED_LABELS = {
    "JUNA (C,z) frame gradient",
    "Conditioned joint (C,W,z)",
}


def require(condition, message):
    if not condition:
        raise SystemExit("twelve-panel validation failed: " + message)


def geometry_dict(values):
    return dict(zip(GEOMETRY_KEYS, values))


def source_name(channel, lane):
    return (f"runs/{channel}_hydrophone{lane}/"
            "red_snr_sweep_uwa_noise_minber.csv")


def main():
    with open(CSV_PATH, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    with open(MANIFEST_PATH, encoding="utf-8") as handle:
        manifest = json.load(handle)
    with open(HTML_PATH, encoding="utf-8") as handle:
        page = handle.read()

    require(len(rows) == 960, f"expected 960 CSV rows, found {len(rows)}")
    require({row["algorithm_id"] for row in rows} == EXPECTED_RECEIVERS,
            "receiver set differs")
    require({row["objective"] for row in rows} == {"min-BER"},
            "an objective other than min-BER remains")
    actual_paths = {(row["channel"], int(row["lane"])) for row in rows}
    require(actual_paths == set(EXPECTED_PATHS),
            "capture/hydrophone path set differs")
    require({row["frames"] for row in rows} == {"60"},
            "a row does not use 60 frames")
    require({row["seed"] for row in rows} == {"4"},
            "a row does not use seed 4")
    for channel, lane in EXPECTED_PATHS:
        path_rows = [row for row in rows
                     if row["channel"] == channel and int(row["lane"]) == lane]
        require(len(path_rows) == 80,
                f"{channel} hydrophone {lane} does not have 80 rows")
        expected_geometry = EXPECTED_GEOMETRIES[(channel, lane)]
        require(all(tuple(row[key] for key in GEOMETRY_KEYS) ==
                    expected_geometry for row in path_rows),
                f"{channel} hydrophone {lane} geometry differs")

    keys = {(row["channel"], int(row["lane"]), row["algorithm_id"],
             float(row["snr_db"])) for row in rows}
    require(len(keys) == 960, "path/receiver/SNR rows are duplicated")
    for channel, lane in EXPECTED_PATHS:
        for receiver in EXPECTED_RECEIVERS:
            receiver_snrs = {
                float(row["snr_db"]) for row in rows
                if row["channel"] == channel and int(row["lane"]) == lane
                and row["algorithm_id"] == receiver
            }
            require(receiver_snrs == EXPECTED_SNRS,
                    f"{channel} hydrophone {lane} {receiver} does not have "
                    "all 16 SNR points")

    require(manifest["schema_version"] == 2,
            "manifest schema version is not 2")
    require(manifest["row_count"] == 960, "manifest row count is not 960")
    require(set(manifest["receivers"]) == EXPECTED_RECEIVERS,
            "manifest receiver set differs")
    require(manifest["objectives"] == ["min-BER"],
            "manifest still declares another objective")
    expected_manifest_geometries = {
        "min-BER": {
            f"{channel} {lane}": geometry_dict(EXPECTED_GEOMETRIES[(channel, lane)])
            for channel, lane in EXPECTED_PATHS
        }
    }
    require(manifest["geometries"] == expected_manifest_geometries,
            "manifest geometry differs")
    expected_manifest_paths = [f"{channel} {lane}"
                               for channel, lane in EXPECTED_PATHS]
    require(manifest["paths"] == expected_manifest_paths,
            "manifest paths differ")
    require("CL-35" in manifest["decisions"],
            "manifest does not record CL-35")
    require(manifest.get("supersedes") == {"CL-35": ["CL-32"]},
            "manifest does not record CL-35 superseding CL-32")
    require(len(manifest["sources"]) == 12,
            "manifest does not contain twelve sources")
    expected_source_paths = {
        source_name(channel, lane): (channel, str(lane))
        for channel, lane in EXPECTED_PATHS
    }
    require({source["path"] for source in manifest["sources"]} ==
            set(expected_source_paths),
            "manifest source path set differs")
    require(all("maxrate" not in source["path"] for source in manifest["sources"]),
            "manifest still publishes a max-rate source")
    for source in manifest["sources"]:
        source_path = os.path.join(HERE, source["path"])
        require(os.path.isfile(source_path),
                f"manifest source is missing: {source['path']}")
        with open(source_path, "rb") as handle:
            actual_digest = hashlib.sha256(handle.read()).hexdigest()
        require(source["sha256"] == actual_digest,
                f"manifest hash differs: {source['path']}")
        with open(source_path, newline="", encoding="utf-8") as handle:
            source_rows = list(csv.DictReader(handle))
        actual_rows = len(source_rows)
        require(source["rows"] == actual_rows,
                f"manifest row count differs: {source['path']}")
        require(source["retained_rows"] == actual_rows == 80,
                f"manifest retained row count differs: {source['path']}")
        require({(row["channel"], row["lane"]) for row in source_rows} ==
                {expected_source_paths[source["path"]]},
                f"manifest source path content differs: {source['path']}")

    require(page.count('<figure class="panel">') == 12,
            "rendered page does not contain exactly twelve panels")
    require(page.count('<path class="series"') == 60,
            "rendered page does not contain five series per panel")
    require("max-rate" not in page, "rendered page still mentions max-rate")
    require("cz_standalone" not in page,
            "rendered page still exposes the duplicate standalone id")
    require("5 receivers" in page, "rendered page does not report five receivers")
    require("12 capture–hydrophone paths" in page,
            "rendered page does not report twelve paths")
    require("Data table — 960 rows over 12 paths" in page,
            "rendered data-table count differs")
    for channel, lane in EXPECTED_PATHS:
        geometry = geometry_dict(EXPECTED_GEOMETRIES[(channel, lane)])
        caption = (f"N={geometry['nfft']} · CP={geometry['cp']} · "
                   f"rate={geometry['code_rate']} · "
                   f"pilots={geometry['outer_spacing']}/"
                   f"{geometry['inner_spacing']} · "
                   f"dc={geometry['check_degree']} · K={geometry['horizon']}")
        panel_start = (f'<figure class="panel"><figcaption><b>{channel} '
                       f'hydrophone {lane} — min-BER</b><span>{caption}</span>')
        require(panel_start in page,
                f"rendered {channel} hydrophone {lane} panel or geometry "
                "differs")
    require(all(label in page for label in EXPECTED_LABELS),
            "an approved receiver label is missing")
    require(all(label not in page for label in REPLACED_LABELS),
            "a replaced receiver label remains")

    print("twelve-panel validation passed: 960 rows, 5 complete receiver "
          "series per path, 12 min-BER panels")


if __name__ == "__main__":
    main()
