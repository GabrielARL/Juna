#!/usr/bin/env python3
"""Validate the N=2048, CP=0, rate=0.25, pilots=2/3, K=4 result."""

import csv
import hashlib
import json
import math
import os


HERE = os.path.dirname(os.path.abspath(__file__))
EXPERIMENT_ID = (
    "2026-08-05-red-snr-sweep-n2048-cp0-rate025-p2-3-dc10-k4")
CSV_PATH = os.path.join(HERE, "red_snr_sweep_uwa_noise.csv")
HTML_PATH = os.path.join(HERE, "results_view.html")
MANIFEST_PATH = os.path.join(HERE, "results_manifest.json")
EXPECTED_RECEIVERS = {"ofdm_fec", "pfft", "lite", "profiled_cz", "cwz_joint"}
PROFILED_RECEIVERS = {"profiled_cz", "cwz_joint"}
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
EXPECTED_GEOMETRY = ("2048", "0", "0.25", "2", "3", "10", "4")
EXPECTED_PAYLOAD_BITS_PER_FRAME = 1338
SOURCE_BASENAME = "red_snr_sweep_uwa_noise_configuration.csv"
EXPECTED_LABELS = {
    "OFDM + FEC", "Partial-FFT + FEC", "JUNA-Lite",
    "JUNA (C,z) Joint gradient", "Juna joint (C,W,z)",
}


def require(condition, message):
    if not condition:
        raise SystemExit("N2048 CP0 rate-0.25 K=4 validation failed: " + message)


def read_csv(path):
    require(os.path.isfile(path), "missing output: " + path)
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def source_name(channel, lane):
    return f"runs/{channel}_hydrophone{lane}/{SOURCE_BASENAME}"


def trace_name(channel, lane):
    return (f"runs/{channel}_hydrophone{lane}/"
            f"{channel}_hydrophone{lane}_selection_trace.csv")


def main():
    rows = read_csv(CSV_PATH)
    require(os.path.isfile(MANIFEST_PATH), "missing results manifest")
    require(os.path.isfile(HTML_PATH), "missing rendered results page")
    with open(MANIFEST_PATH, encoding="utf-8") as handle:
        manifest = json.load(handle)
    with open(HTML_PATH, encoding="utf-8") as handle:
        page = handle.read()

    require(len(rows) == 960, f"expected 960 aggregate rows, found {len(rows)}")
    require({row["algorithm_id"] for row in rows} == EXPECTED_RECEIVERS,
            "receiver set differs")
    require({row["objective"] for row in rows} == {"configuration"},
            "result group differs")
    require({(row["channel"], int(row["lane"])) for row in rows} ==
            set(EXPECTED_PATHS), "capture/hydrophone set differs")
    require({row["frames"] for row in rows} == {"60"}, "frame count differs")
    require({row["seed"] for row in rows} == {"4"}, "seed differs")
    require({float(row["snr_db"]) for row in rows} == EXPECTED_SNRS,
            "aggregate SNR set differs")
    keys = {(row["channel"], int(row["lane"]), row["algorithm_id"],
             float(row["snr_db"])) for row in rows}
    require(len(keys) == 960, "aggregate keys are duplicated")
    for row in rows:
        require(tuple(row[key] for key in GEOMETRY_KEYS) == EXPECTED_GEOMETRY,
                "an aggregate row has the wrong geometry")
        require(int(row["payload_bits_per_frame"]) ==
                EXPECTED_PAYLOAD_BITS_PER_FRAME,
                "an aggregate row does not realize the K=4 payload")
        bits = int(row["payload_bits"])
        errors = int(row["bit_errors"])
        require(bits == EXPECTED_PAYLOAD_BITS_PER_FRAME * 60,
                "payload-bit arithmetic differs")
        require(math.isclose(float(row["ber"]), errors / bits,
                             rel_tol=0, abs_tol=1e-15), "BER arithmetic differs")
        require(math.isclose(float(row["psr"]),
                             int(row["successful_frames"]) / 60,
                             rel_tol=0, abs_tol=1e-15), "PSR arithmetic differs")

    trace_total = 0
    zero_iterations = {receiver: 0 for receiver in PROFILED_RECEIVERS}
    canonical_rows = []
    source_paths = set()
    trace_paths = set()
    for channel, lane in EXPECTED_PATHS:
        source = source_name(channel, lane)
        source_path = os.path.join(HERE, source)
        source_rows = read_csv(source_path)
        require(len(source_rows) == 80, f"{source} does not have 80 rows")
        canonical_rows.extend(source_rows)
        source_paths.add(source)
        trace_value = trace_name(channel, lane)
        trace = read_csv(os.path.join(HERE, trace_value))
        trace_paths.add(trace_value)
        require(len(trace) == 1920,
                f"{channel} hydrophone {lane} trace does not have 1920 rows")
        trace_total += len(trace)
        require({row["algorithm_id"] for row in trace} == PROFILED_RECEIVERS,
                f"{channel} hydrophone {lane} trace receiver set differs")
        require({float(row["snr_db"]) for row in trace} == EXPECTED_SNRS,
                f"{channel} hydrophone {lane} trace SNR set differs")
        require({int(row["frame"]) for row in trace} == set(range(1, 61)),
                f"{channel} hydrophone {lane} trace frame set differs")
        require({row["selection_reason"] for row in trace} == {"gradient_only"},
                f"{channel} hydrophone {lane} selection reason differs")
        require(all(
            row["workload_id"] ==
            f"{channel}:lane{lane}:snr{float(row['snr_db'])}:seed4:"
            f"frame{int(row['frame'])}"
            for row in trace
        ), f"{channel} hydrophone {lane} trace workload provenance differs")
        trace_keys = {(row["algorithm_id"], float(row["snr_db"]),
                       int(row["frame"])) for row in trace}
        require(len(trace_keys) == 1920,
                f"{channel} hydrophone {lane} trace keys are duplicated")
        for receiver in PROFILED_RECEIVERS:
            zero_iterations[receiver] += sum(
                int(row["selected_iteration"]) == 0 for row in trace
                if row["algorithm_id"] == receiver)
            for snr in EXPECTED_SNRS:
                frames = [row for row in trace
                          if row["algorithm_id"] == receiver
                          and float(row["snr_db"]) == snr]
                aggregate = next(row for row in source_rows
                                 if row["algorithm_id"] == receiver
                                 and float(row["snr_db"]) == snr)
                require(sum(int(row["bit_errors"]) for row in frames) ==
                        int(aggregate["bit_errors"]), "trace errors differ")
                require(sum(row["success"] == "true" for row in frames) ==
                        int(aggregate["successful_frames"]),
                        "trace successes differ")
                require(sum(row["decode_failure"] == "true" for row in frames) ==
                        int(aggregate["decode_failures"]),
                        "trace failures differ")
    require(trace_total == 23040,
            f"expected 23040 trace rows, found {trace_total}")
    canonical_rows.sort(key=lambda row: (
        int(row["channel"][3:]), int(row["lane"]),
        float(row["snr_db"]), row["algorithm_id"]))
    require(rows == canonical_rows,
            "aggregate CSV differs from its twelve source CSVs")

    require(manifest["schema_version"] == 2, "manifest schema differs")
    require(manifest["experiment_id"] == EXPERIMENT_ID,
            "manifest experiment ID differs")
    require(manifest["row_count"] == 960, "manifest row count differs")
    require(set(manifest["receivers"]) == EXPECTED_RECEIVERS,
            "manifest receiver set differs")
    require(tuple(manifest["geometry"][key] for key in GEOMETRY_KEYS) ==
            EXPECTED_GEOMETRY, "manifest geometry differs")
    require(manifest["geometry_display"]["horizon"] == "4",
            "manifest does not display K=4")
    require({source["path"] for source in manifest["sources"]} == source_paths,
            "manifest source paths differ")
    for source in manifest["sources"]:
        path = os.path.join(HERE, source["path"])
        require(source["sha256"] == sha256(path),
                f"manifest hash differs: {source['path']}")
        require(source["rows"] == source["retained_rows"] == 80,
                f"manifest row count differs: {source['path']}")
    require({source["path"] for source in manifest["trace_sources"]} == trace_paths,
            "manifest trace source paths differ")
    for source in manifest["trace_sources"]:
        path = os.path.join(HERE, source["path"])
        require(source["sha256"] == sha256(path),
                f"manifest trace hash differs: {source['path']}")
        require(source["rows"] == 1920,
                f"manifest trace row count differs: {source['path']}")

    require(page.count('<figure class="panel">') == 12,
            "rendered panel count differs")
    require(page.count('<path class="series"') == 60,
            "rendered series count differs")
    require(page.count("K=4") == 12, "not every panel displays K=4")
    require("Data table — 960 rows over 12 paths" in page,
            "rendered table count differs")
    require(all(label in page for label in EXPECTED_LABELS),
            "an approved receiver label is missing")
    caption = "N=2048 · CP=0 · rate=0.25 · pilots=2/3 · dc=10 · K=4"
    for channel, lane in EXPECTED_PATHS:
        start = (f'<figure class="panel"><figcaption><b>{channel} '
                 f'hydrophone {lane}</b><span>{caption}</span>')
        require(start in page, f"{channel} hydrophone {lane} panel differs")

    experiments_dir = os.path.dirname(os.path.dirname(HERE))
    view_builder = os.path.join(
        experiments_dir, "2026-08-04-red-snr-sweep", "results",
        "build_sweep_view.py")
    namespace = {"__file__": view_builder, "__name__": "_n2048_cp0_p2_3_view"}
    with open(view_builder, encoding="utf-8") as handle:
        exec(compile(handle.read(), view_builder, "exec"), namespace)
    require(page == namespace["render"](rows, configuration_only=True),
            "rendered page is not the deterministic view of the aggregate CSV")

    print("N2048 CP0 rate-0.25 K=4 validation passed: "
          "960 aggregate rows, 23040 trace rows, 12 panels, 60 series")
    print("selected_iteration=0", json.dumps(zero_iterations, sort_keys=True))


if __name__ == "__main__":
    main()
