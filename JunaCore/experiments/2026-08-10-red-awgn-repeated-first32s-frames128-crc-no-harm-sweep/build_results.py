#!/usr/bin/env python3
"""Validate, combine, and render the approved AWGN-023C result."""

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import re

import matrix_contract


HERE = os.path.dirname(os.path.abspath(__file__))
EXPERIMENTS = os.path.dirname(HERE)
EXPECTED_IDS = matrix_contract.EXPECTED_IDS
EXPECTED_PATHS = matrix_contract.EXPECTED_PATHS
EXPECTED_SNRS = matrix_contract.EXPECTED_SNRS
EXPECTED_RECEIVERS = matrix_contract.EXPECTED_RECEIVERS
PROTECTED_RECEIVERS = matrix_contract.PROTECTED_RECEIVERS
FRAMES = matrix_contract.FRAMES
CAPTURE_SECONDS = matrix_contract.CAPTURE_SECONDS
SNAPSHOT_INDICES = matrix_contract.SNAPSHOT_INDICES
GEOMETRY_KEYS = (
    "nfft", "cp", "code_rate", "outer_spacing", "inner_spacing",
    "check_degree", "horizon",
)
SOURCE_BASENAME = "red_snr_sweep_awgn_repeated_first32s_frames128_configuration.csv"
OUTPUT_BASENAME = "red_snr_sweep_awgn_repeated_first32s_frames128.csv"
PATH_CONTRACT_BASENAME = "awgn023c_path_contract.txt"
AWGN022_EXPERIMENT_ID = (
    "2026-08-10-red-awgn-first32s-frames32-crc-no-harm-"
    "n1024-cp64-rate025-p5-5-dc14-kfill-pfft4"
)
AWGN022_REFERENCE_RESULTS = os.path.join(
    "/home/gabiel/Documents/GitHub/Juna-worktrees/awgn-results/"
    "JunaCore/experiments",
    AWGN022_EXPERIMENT_ID,
    "results",
)
AWGN022_REFERENCE_HASHES = {
    "aggregate": "b0a9140b86cbcc91f928a2d1d5c385b67e1823c8ec468a6cba781cf4758b3cd6",
    "manifest": "01d1cd8f31d31483d4ee22ae65d46a3cdca98cfcac223b3b93f1319a125af747",
    "view": "34558d020da47a9713c178e866393ac2cbae1ce49a496ccb10514245c774ad68",
}
AWGN022_ARTIFACTS = {
    "aggregate": "red_snr_sweep_awgn_first32s_frames32.csv",
    "manifest": "results_manifest.json",
    "view": "results_view.html",
}

AGGREGATE_COLUMNS = (
    "channel", "lane", "snr_db", "algorithm_id", "seed", "frames",
    "objective", "noise_model", "nfft", "cp", "code_rate",
    "outer_spacing", "inner_spacing", "check_degree", "horizon",
    "partial_fft_parts", "partial_fft_bands", "payload_bits_per_frame",
    "successful_frames", "psr", "payload_bits", "bit_errors", "ber",
    "decode_failures", "decode_seconds", "effective_rate_bps",
    "capture_start_seconds", "capture_stop_seconds",
    "capture_tap_snapshots", "capture_phase_samples",
)
FRAME_TRACE_COLUMNS = (
    "workload_id", "snr_db", "frame", "algorithm_id", "noise_model",
    "capture_start_seconds", "capture_stop_seconds", "snapshot_index",
    "snapshot_seconds", "replay_support_end_seconds",
    "frame_duration_seconds", "frame_samples", "payload_bits",
    "payload_seed", "noise_seed", "replay_seed", "optimizer_seed",
    "bit_errors", "success", "decode_failure", "partial_fft_parts",
    "partial_fft_bands",
)
PROTECTED_TRACE_COLUMNS = (
    "workload_id", "snr_db", "frame", "algorithm_id", "noise_model",
    "capture_start_seconds", "capture_stop_seconds", "snapshot_index",
    "snapshot_seconds", "replay_support_end_seconds",
    "frame_duration_seconds", "bit_errors", "success", "decode_failure",
    "selected_source", "selection_reason", "standard_crc_valid",
    "rescue_executed", "rescue_is_gradient", "rescue_crc_valid",
    "gradient_checkpoints", "selected_iteration", "optimized_variables",
    "partial_fft_parts", "partial_fft_bands",
)
REFERENCE_FRAME_FIELDS = tuple(
    field for field in FRAME_TRACE_COLUMNS if field != "capture_stop_seconds")
REFERENCE_PROTECTED_FIELDS = tuple(
    field for field in PROTECTED_TRACE_COLUMNS
    if field != "capture_stop_seconds")
CAPTURE_MD5 = {
    "red_1.mat": "76ee45172cd0bf5deb4a7bfb04907884",
    "red_2.mat": "cb1b4566f5e9db67b93c072dbce8db06",
    "red_3.mat": "befb441590ddafc4383746cc0526d4b6",
    "red_4.mat": "bbab171a6af14632944d1fee157cde86",
}


class ResultContractError(RuntimeError):
    """One measured AWGN-023C artifact violated the approved contract."""


def require(condition, message):
    if not condition:
        raise ResultContractError("AWGN-023C result contract failed: " + message)


def file_digest(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def reference_artifact_hashes(results_dir):
    return {
        name: file_digest(os.path.join(results_dir, filename))
        for name, filename in AWGN022_ARTIFACTS.items()
    }


def parse_geometry(experiment_id):
    try:
        return matrix_contract.parse_geometry(experiment_id)
    except matrix_contract.MatrixContractError as error:
        raise ResultContractError(str(error)) from error


def source_name(channel, hydrophone):
    return (
        f"runs/{channel}_hydrophone{hydrophone}/{SOURCE_BASENAME}"
    )


def frame_trace_name(channel, hydrophone):
    stem = f"{channel}_hydrophone{hydrophone}"
    return f"runs/{stem}/{stem}_frame_trace.csv"


def protected_trace_name(channel, hydrophone):
    stem = f"{channel}_hydrophone{hydrophone}"
    return f"runs/{stem}/{stem}_selection_trace.csv"


def path_contract_name(channel, hydrophone):
    stem = f"{channel}_hydrophone{hydrophone}"
    return f"runs/{stem}/{PATH_CONTRACT_BASENAME}"


def load_csv(results_dir, name):
    path = os.path.join(results_dir, name)
    require(os.path.isfile(path), "missing source " + name)
    require(not os.path.islink(path), "source is a symlink: " + name)
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return tuple(reader.fieldnames or ()), list(reader)


def _bool(row, field, source):
    value = row[field]
    require(value in ("true", "false"), f"{source} {field} is not Boolean")
    return value == "true"


def _validate_no_harm_selection(row, source):
    selected = row["selected_source"]
    reason = row["selection_reason"]
    standard_valid = _bool(row, "standard_crc_valid", source)
    executed = _bool(row, "rescue_executed", source)
    is_gradient = _bool(row, "rescue_is_gradient", source)
    rescue_valid = _bool(row, "rescue_crc_valid", source)
    checkpoints = int(row["gradient_checkpoints"])
    iteration = int(row["selected_iteration"])
    expected_variables = {
        "profiled_cz": "C+z", "cwz_joint": "C+W+z",
    }[row["algorithm_id"]]
    require(row["optimized_variables"] == expected_variables,
            f"{source} optimized variables differ")
    if reason == "standard_crc_valid":
        valid = (selected == "standard" and standard_valid and not executed
                 and not is_gradient and not rescue_valid
                 and checkpoints == 0 and iteration == 0)
    elif reason == "crc_rescue":
        valid = (selected == "gradient" and not standard_valid and executed
                 and is_gradient and rescue_valid and checkpoints > 0
                 and iteration > 0)
    elif reason == "standard_fallback":
        valid = (selected == "standard" and not standard_valid and executed
                 and not rescue_valid and checkpoints > 0 and iteration >= 0)
    else:
        valid = False
    require(valid, f"{source} no-harm selection is inconsistent")


def _path_contract_record(results_dir, experiment_id, channel, hydrophone,
                          aggregate, frame_trace, protected_trace):
    name = path_contract_name(channel, hydrophone)
    path = os.path.join(results_dir, name)
    require(os.path.isfile(path), "missing path contract " + name)
    require(not os.path.islink(path), "path contract is a symlink: " + name)
    expected = (
        ("campaign", matrix_contract.CAMPAIGN),
        ("experiment_id", experiment_id),
        ("channel", channel),
        ("hydrophone", str(hydrophone)),
        ("aggregate_sha256", file_digest(os.path.join(results_dir, aggregate))),
        ("frame_trace_sha256", file_digest(
            os.path.join(results_dir, frame_trace))),
        ("protected_trace_sha256", file_digest(
            os.path.join(results_dir, protected_trace))),
        ("source_contract_sha256", file_digest(
            os.path.join(HERE, "source_contract.json"))),
        ("runner_sha256", file_digest(os.path.join(HERE, "run_awgn023c.jl"))),
        ("sweep_sha256", file_digest(os.path.join(HERE, "awgn023c_sweep.jl"))),
        ("aggregate_rows", "80"),
        ("frame_trace_rows", "10240"),
        ("protected_trace_rows", "4096"),
        ("capture_seconds", "32.0"),
        ("snapshot_indices", ",".join(str(value) for value in SNAPSHOT_INDICES)),
    )
    expected_text = "".join(f"{key}={value}\n" for key, value in expected)
    with open(path, encoding="utf-8") as handle:
        require(handle.read() == expected_text, "path contract differs: " + name)
    return {"path": name, "sha256": file_digest(path)}


def _validate_aggregate(rows, source, channel, hydrophone,
                        geometry, expected_pfft):
    require(len(rows) == 80, f"expected 80 rows, found {len(rows)}: {source}")
    require({row["algorithm_id"] for row in rows} == EXPECTED_RECEIVERS,
            "receiver set differs: " + source)
    require({(row["channel"], int(row["lane"])) for row in rows}
            == {(channel, hydrophone)}, "path differs: " + source)
    require({float(row["snr_db"]) for row in rows} == EXPECTED_SNRS,
            "SNR set differs: " + source)
    require(len({(row["algorithm_id"], float(row["snr_db"])) for row in rows})
            == 80, "receiver/SNR keys are duplicated: " + source)
    for row in rows:
        require(tuple(row[key] for key in GEOMETRY_KEYS) == geometry,
                "geometry differs: " + source)
        require(row["seed"] == "4" and row["frames"] == "128",
                "seed or frame count differs: " + source)
        require(row["objective"] == "configuration"
                and row["noise_model"] == "awgn", "scope differs: " + source)
        require(float(row["capture_start_seconds"]) == 0.0
                and float(row["capture_stop_seconds"]) == 32.0,
                "capture interval differs: " + source)
        require(int(row["capture_tap_snapshots"]) == 3073
                and int(row["capture_phase_samples"]) == 614600,
                "capture geometry differs: " + source)
        require(int(row["partial_fft_parts"]) == expected_pfft
                and int(row["partial_fft_bands"]) == 16,
                "partial-FFT geometry differs: " + source)
        require(int(row["payload_bits_per_frame"]) == 1616
                and int(row["payload_bits"]) == 128 * 1616,
                "payload geometry differs: " + source)
        require(int(row["decode_failures"]) == 0,
                "decode failure recorded: " + source)


def _validate_frame_traces(rows, source):
    require(len(rows) == 10240,
            f"expected 10240 frame traces, found {len(rows)}: {source}")
    require({row["algorithm_id"] for row in rows} == EXPECTED_RECEIVERS,
            "frame-trace receiver set differs: " + source)
    require({float(row["snr_db"]) for row in rows} == EXPECTED_SNRS,
            "frame-trace SNR set differs: " + source)
    keys = {(row["algorithm_id"], float(row["snr_db"]), int(row["frame"]))
            for row in rows}
    require(len(keys) == 10240, "frame-trace keys are duplicated: " + source)
    paired_groups = {}
    pass_groups = {}
    for row in rows:
        frame = int(row["frame"])
        snr = float(row["snr_db"])
        receiver = row["algorithm_id"]
        require(1 <= frame <= 128, "frame index differs: " + source)
        require(int(row["snapshot_index"]) == SNAPSHOT_INDICES[frame - 1],
                "nested snapshot differs: " + source)
        expected_seed = frame + 3
        require(int(row["payload_seed"]) == expected_seed
                and int(row["noise_seed"]) == expected_seed
                and int(row["replay_seed"]) == expected_seed
                and int(row["optimizer_seed"]) == 4,
                "frame seed differs: " + source)
        require(row["noise_model"] == "awgn"
                and float(row["capture_start_seconds"]) == 0.0
                and float(row["capture_stop_seconds"]) == 32.0,
                "frame scope differs: " + source)
        require(float(row["replay_support_end_seconds"]) <= 32.0 + 1e-9,
                "frame replay support exceeds 32 seconds: " + source)
        require(int(row["frame_samples"]) == 9536
                and int(row["payload_bits"]) == 1616,
                "frame geometry differs: " + source)
        require(not _bool(row, "decode_failure", source),
                "frame decode failure recorded: " + source)
        paired_groups.setdefault((snr, frame), []).append(row)
        base = (frame - 1) % 32 + 1
        pass_groups.setdefault((receiver, snr, base), []).append(row)
    for snr in EXPECTED_SNRS:
        for frame in range(1, 129):
            paired = paired_groups.get((snr, frame), [])
            require(len(paired) == 5, "paired receiver count differs: " + source)
            signature = {
                (row["workload_id"], row["snapshot_index"],
                 row["payload_seed"], row["noise_seed"], row["replay_seed"],
                 row["optimizer_seed"]) for row in paired
            }
            require(len(signature) == 1,
                    "five receivers do not share one workload: " + source)
    for receiver in EXPECTED_RECEIVERS:
        for snr in EXPECTED_SNRS:
            for base in range(1, 33):
                passes = sorted(pass_groups.get((receiver, snr, base), []),
                                key=lambda row: int(row["frame"]))
                require(len(passes) == 4,
                        "replay pass count differs: " + source)
                windows = {
                    (row["snapshot_index"], row["snapshot_seconds"],
                     row["replay_support_end_seconds"],
                     row["frame_duration_seconds"], row["frame_samples"])
                    for row in passes
                }
                require(len(windows) == 1,
                        "replay window changed between passes: " + source)
                expected = [base + 3 + 32 * replay_pass
                            for replay_pass in range(4)]
                for field in ("payload_seed", "noise_seed", "replay_seed"):
                    require([int(row[field]) for row in passes] == expected,
                            f"{field} did not advance between passes: {source}")


def _validate_protected_traces(rows, source, frame_rows):
    require(len(rows) == 4096,
            f"expected 4096 protected traces, found {len(rows)}: {source}")
    require({row["algorithm_id"] for row in rows} == PROTECTED_RECEIVERS,
            "protected receiver set differs: " + source)
    keys = {(row["algorithm_id"], float(row["snr_db"]), int(row["frame"]))
            for row in rows}
    require(len(keys) == 4096, "protected keys are duplicated: " + source)
    frame_index = {
        (row["algorithm_id"], float(row["snr_db"]), int(row["frame"])): row
        for row in frame_rows if row["algorithm_id"] in PROTECTED_RECEIVERS
    }
    require(set(frame_index) == keys, "protected/frame key sets differ: " + source)
    for row in rows:
        _validate_no_harm_selection(row, source)
        require(not _bool(row, "decode_failure", source),
                "protected decode failure recorded: " + source)
        key = (row["algorithm_id"], float(row["snr_db"]), int(row["frame"]))
        frame = frame_index[key]
        for field in (
                "workload_id", "snr_db", "frame", "algorithm_id",
                "noise_model", "capture_start_seconds",
                "capture_stop_seconds", "snapshot_index", "snapshot_seconds",
                "replay_support_end_seconds", "frame_duration_seconds",
                "bit_errors", "success", "decode_failure",
                "partial_fft_parts", "partial_fft_bands"):
            require(row[field] == frame[field],
                    f"protected/frame {field} differs: {source}")


def _reconcile(aggregates, frame_rows, source, frame_count=128):
    for receiver in EXPECTED_RECEIVERS:
        for snr in EXPECTED_SNRS:
            aggregate = next(row for row in aggregates
                             if row["algorithm_id"] == receiver
                             and float(row["snr_db"]) == snr)
            frames = [row for row in frame_rows
                      if row["algorithm_id"] == receiver
                      and float(row["snr_db"]) == snr]
            successes = sum(_bool(row, "success", source) for row in frames)
            errors = sum(int(row["bit_errors"]) for row in frames)
            failures = sum(_bool(row, "decode_failure", source) for row in frames)
            require(len(frames) == frame_count
                    and successes == int(aggregate["successful_frames"])
                    and errors == int(aggregate["bit_errors"])
                    and failures == int(aggregate["decode_failures"]),
                    "aggregate/frame outcomes do not reconcile: " + source)


def _key(row):
    return row["algorithm_id"], float(row["snr_db"]), int(row["frame"])


def _reference_records(manifest, field, expected_rows):
    records = manifest.get(field)
    require(isinstance(records, list) and len(records) == 12,
            f"AWGN-022 {field} differs")
    require(all(record.get("rows") == expected_rows for record in records),
            f"AWGN-022 {field} row counts differ")
    return {record["path"]: record for record in records}


def _compare_reference_rows(candidate, reference, fields, message):
    candidate_index = {_key(row): row for row in candidate if int(row["frame"]) <= 32}
    reference_index = {_key(row): row for row in reference}
    require(len(candidate_index) == len(reference_index)
            and set(candidate_index) == set(reference_index), message + " keys differ")
    for key, expected in reference_index.items():
        actual = candidate_index[key]
        for field in fields:
            require(actual[field] == expected[field],
                    f"{message} {field} differs at {key}")


def _awgn022_reference(candidate_frames, candidate_protected,
                       reference_results, reference_hashes):
    require(os.path.isdir(reference_results), "missing AWGN-022 reference results")
    for filename in AWGN022_ARTIFACTS.values():
        path = os.path.join(reference_results, filename)
        require(os.path.isfile(path) and not os.path.islink(path),
                "missing AWGN-022 reference artifact: " + filename)
    actual_hashes = reference_artifact_hashes(reference_results)
    if reference_hashes is not None:
        for name, expected in reference_hashes.items():
            require(actual_hashes.get(name) == expected,
                    f"AWGN-022 {name} hash differs")
    manifest_path = os.path.join(reference_results, AWGN022_ARTIFACTS["manifest"])
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    require(manifest.get("decision") == "AWGN-022",
            "AWGN-022 manifest decision differs")
    require(manifest.get("experiment_id") == AWGN022_EXPERIMENT_ID,
            "AWGN-022 manifest experiment differs")
    require(manifest.get("row_count") == 960
            and manifest.get("frame_trace_row_count") == 30720
            and manifest.get("protected_trace_row_count") == 12288,
            "AWGN-022 manifest counts differ")
    frame_records = _reference_records(manifest, "frame_trace_sources", 2560)
    protected_records = _reference_records(
        manifest, "protected_trace_sources", 1024)
    matched_frames = 0
    matched_protected = 0
    frame_evidence = []
    protected_evidence = []
    reference_frames_by_path = {}
    for channel, hydrophone in EXPECTED_PATHS:
        path_key = (channel, hydrophone)
        frame_name = frame_trace_name(channel, hydrophone)
        protected_name = protected_trace_name(channel, hydrophone)
        require(frame_name in frame_records,
                "AWGN-022 frame evidence path differs: " + frame_name)
        require(protected_name in protected_records,
                "AWGN-022 protected evidence path differs: " + protected_name)
        frame_record = frame_records[frame_name]
        protected_record = protected_records[protected_name]
        frame_path = os.path.join(reference_results, frame_name)
        protected_path = os.path.join(reference_results, protected_name)
        require(file_digest(frame_path) == frame_record["sha256"],
                "AWGN-022 frame evidence hash differs: " + frame_name)
        require(file_digest(protected_path) == protected_record["sha256"],
                "AWGN-022 protected evidence hash differs: " + protected_name)
        columns, reference_frames = load_csv(reference_results, frame_name)
        require(columns == FRAME_TRACE_COLUMNS and len(reference_frames) == 2560,
                "AWGN-022 frame evidence schema differs: " + frame_name)
        columns, reference_protected = load_csv(reference_results, protected_name)
        require(columns == PROTECTED_TRACE_COLUMNS
                and len(reference_protected) == 1024,
                "AWGN-022 protected evidence schema differs: " + protected_name)
        _compare_reference_rows(
            candidate_frames[path_key], reference_frames,
            REFERENCE_FRAME_FIELDS, "AWGN-022 first-thirty-two frame")
        _compare_reference_rows(
            candidate_protected[path_key], reference_protected,
            REFERENCE_PROTECTED_FIELDS, "AWGN-022 protected")
        reference_frames_by_path[path_key] = reference_frames
        matched_frames += len(reference_frames)
        matched_protected += len(reference_protected)
        frame_evidence.append(dict(frame_record))
        protected_evidence.append(dict(protected_record))

    aggregate_name = AWGN022_ARTIFACTS["aggregate"]
    columns, aggregate_rows = load_csv(reference_results, aggregate_name)
    require(columns == AGGREGATE_COLUMNS and len(aggregate_rows) == 960,
            "AWGN-022 aggregate schema or count differs")
    aggregate_index = {
        (row["channel"], int(row["lane"]), row["algorithm_id"],
         float(row["snr_db"])): row for row in aggregate_rows
    }
    require(len(aggregate_index) == 960,
            "AWGN-022 aggregate keys are duplicated")
    for (channel, hydrophone), frames in reference_frames_by_path.items():
        for receiver in EXPECTED_RECEIVERS:
            for snr in EXPECTED_SNRS:
                selected = [row for row in frames
                            if row["algorithm_id"] == receiver
                            and float(row["snr_db"]) == snr]
                aggregate = aggregate_index[(channel, hydrophone, receiver, snr)]
                require(len(selected) == 32
                        and int(aggregate["bit_errors"]) == sum(
                            int(row["bit_errors"]) for row in selected)
                        and int(aggregate["successful_frames"]) == sum(
                            _bool(row, "success", "AWGN-022") for row in selected)
                        and int(aggregate["decode_failures"]) == sum(
                            _bool(row, "decode_failure", "AWGN-022")
                            for row in selected),
                        "AWGN-022 aggregate/frame outcomes differ")
    return {
        "decision": "AWGN-022",
        "experiment_id": AWGN022_EXPERIMENT_ID,
        "aggregate": {
            "path": aggregate_name, "sha256": actual_hashes["aggregate"],
            "rows": 960,
        },
        "manifest": {
            "path": AWGN022_ARTIFACTS["manifest"],
            "sha256": actual_hashes["manifest"],
        },
        "view": {
            "path": AWGN022_ARTIFACTS["view"],
            "sha256": actual_hashes["view"],
        },
        "frame_trace_sources": frame_evidence,
        "protected_trace_sources": protected_evidence,
        "matched_frame_rows": matched_frames,
        "matched_protected_rows": matched_protected,
        "excluded_candidate_fields": ["capture_stop_seconds"],
    }


def collect(experiment_dir, reference_results=AWGN022_REFERENCE_RESULTS,
            reference_hashes=AWGN022_REFERENCE_HASHES):
    experiment_id = os.path.basename(os.path.normpath(experiment_dir))
    geometry, expected_pfft = parse_geometry(experiment_id)
    results_dir = os.path.join(experiment_dir, "results")
    aggregates = []
    sources = []
    frame_sources = []
    protected_sources = []
    contracts = []
    candidate_frames = {}
    candidate_protected = {}
    bands = set()
    for channel, hydrophone in EXPECTED_PATHS:
        source = source_name(channel, hydrophone)
        columns, source_rows = load_csv(results_dir, source)
        require(columns == AGGREGATE_COLUMNS, "aggregate columns differ: " + source)
        _validate_aggregate(source_rows, source, channel, hydrophone,
                            geometry, expected_pfft)
        aggregates.extend(source_rows)
        bands.update(int(row["partial_fft_bands"]) for row in source_rows)
        sources.append({"path": source, "rows": 80,
                        "sha256": file_digest(os.path.join(results_dir, source))})
        frame_name = frame_trace_name(channel, hydrophone)
        columns, frame_rows = load_csv(results_dir, frame_name)
        require(columns == FRAME_TRACE_COLUMNS,
                "frame-trace columns differ: " + frame_name)
        _validate_frame_traces(frame_rows, frame_name)
        _reconcile(source_rows, frame_rows, frame_name)
        candidate_frames[(channel, hydrophone)] = frame_rows
        frame_sources.append({
            "path": frame_name, "rows": 10240,
            "sha256": file_digest(os.path.join(results_dir, frame_name)),
        })
        protected_name = protected_trace_name(channel, hydrophone)
        columns, protected_rows = load_csv(results_dir, protected_name)
        require(columns == PROTECTED_TRACE_COLUMNS,
                "protected columns differ: " + protected_name)
        _validate_protected_traces(protected_rows, protected_name, frame_rows)
        candidate_protected[(channel, hydrophone)] = protected_rows
        protected_sources.append({
            "path": protected_name, "rows": 4096,
            "sha256": file_digest(os.path.join(results_dir, protected_name)),
        })
        contracts.append(_path_contract_record(
            results_dir, experiment_id, channel, hydrophone,
            source, frame_name, protected_name))
    require(len(aggregates) == 960, "combined aggregate row count differs")
    require(sum(item["rows"] for item in frame_sources) == 122880,
            "combined frame-trace row count differs")
    require(sum(item["rows"] for item in protected_sources) == 49152,
            "combined protected row count differs")
    require(bands == {16}, "partial-FFT band count differs")
    reference = _awgn022_reference(
        candidate_frames, candidate_protected,
        reference_results, reference_hashes)
    aggregates.sort(key=lambda row: (
        int(row["channel"][3:]), int(row["lane"]),
        float(row["snr_db"]), row["algorithm_id"]))
    return (experiment_id, results_dir, geometry, expected_pfft,
            aggregates, sources, frame_sources, protected_sources,
            contracts, reference)


def load_renderer(receiver_ids):
    path = os.path.join(EXPERIMENTS, "2026-08-04-red-snr-sweep",
                        "results", "build_sweep_view.py")
    require(os.path.isfile(path), "missing retained results renderer")
    spec = importlib.util.spec_from_file_location("awgn023c_sweep_view", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.RECEIVERS = [receiver for receiver in module.RECEIVERS
                        if receiver[0] in receiver_ids]
    module.coincident_groups = lambda _entry: []
    return module


def render_page(rows):
    page = load_renderer(EXPECTED_RECEIVERS).render(
        rows, configuration_only=True)
    title = "AWGN-023C: BER versus SNR"
    page = page.replace(
        "<title>Red replay channel: BER versus added-noise SNR</title>",
        f"<title>{title}</title>")
    page = page.replace(
        "<h1>Red replay channel: BER versus added-noise SNR</h1>",
        f"<h1>{title}</h1>")
    provenance = """<div class="provenance">
<p><b>Channel.</b> Each panel uses one hydrophone from the first thirty-two seconds
of the measured red replay capture. The same measured channel replay is used in
four passes.</p>
<p><b>Frames.</b> Each SNR point uses 128 transmitted frames. Each pass uses the same
thirty-two replay windows, while the payload and added AWGN change with the frame
seed. Hence the curves average more transmitted frames but do not extend the
measured channel observation beyond thirty-two seconds. All five receivers use
the same transmitted frames, channel replay, and added AWGN.</p>
<p><b>Noise.</b> Only independent complex AWGN is added after the measured
channel replay. Its real and imaginary components each receive half of the
target complex-noise power.</p>
<p><b>Receivers.</b> JUNA-Lite is unchanged. JUNA (C,z) Joint gradient and Juna
joint (C,W,z) use the CRC no-harm implementation. Standard is returned when
Standard passes CRC or the gradient does not produce a CRC-valid output.</p>
<p><b>Reading.</b> Hollow markers are zero-observed-error points drawn at
0.5/payload bits; that height is a measurement limit, not a measured BER.</p>
</div>"""
    page, count = re.subn(r'<div class="provenance">.*?</div>', provenance,
                          page, count=1, flags=re.DOTALL)
    require(count == 1, "could not replace result provenance")
    return page


def _source_contract():
    path = os.path.join(HERE, "source_contract.json")
    require(os.path.isfile(path), "missing source contract")
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    try:
        matrix_contract.validate_source_contract(payload)
    except matrix_contract.MatrixContractError as error:
        raise ResultContractError(str(error)) from error
    return payload, file_digest(path)


def _family_source_hashes():
    names = (
        "awgn023c_contract_test.jl", "awgn023c_sweep.jl", "run_awgn023c.jl",
        "matrix_contract.py", "build_results.py", "validate_results.py",
        "validate_matrix.py", "results_contract_test.py",
        "source_contract.json",
    )
    return {name: file_digest(os.path.join(HERE, name)) for name in names
            if os.path.isfile(os.path.join(HERE, name))}


def _atomic_text(path, content):
    partial = path + ".partial"
    with open(partial, "w", encoding="utf-8") as handle:
        handle.write(content)
    os.replace(partial, path)


def build(experiment_dir, reference_results=AWGN022_REFERENCE_RESULTS,
          reference_hashes=AWGN022_REFERENCE_HASHES):
    (experiment_id, results_dir, geometry_values, expected_pfft, rows,
     sources, frame_sources, protected_sources, contracts,
     reference) = collect(experiment_dir, reference_results, reference_hashes)
    os.makedirs(results_dir, exist_ok=True)
    output = os.path.join(results_dir, OUTPUT_BASENAME)
    partial = output + ".partial"
    with open(partial, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=AGGREGATE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(partial, output)
    source_contract, source_sha = _source_contract()
    geometry = dict(zip(GEOMETRY_KEYS, geometry_values))
    manifest = {
        "schema_version": 1,
        "decision": matrix_contract.CAMPAIGN,
        "experiment_id": experiment_id,
        "geometry": geometry,
        "geometry_display": dict(geometry),
        "noise_model": {
            "kind": "awgn", "generator": "BenchmarkPort._add_awgn",
            "note": "independent complex Gaussian samples",
        },
        "channel_model": "measured red replay capture, one hydrophone per path",
        "capture_time_seconds": [0.0, 32.0],
        "time_window_s": [0.0, 32.0],
        "frame_count": 128,
        "frames_per_point": 128,
        "seed": 4,
        "replay_passes": 4,
        "replay_windows_per_pass": 32,
        "base_snapshot_indices": list(matrix_contract.BASE_SNAPSHOT_INDICES),
        "snapshot_indices": list(SNAPSHOT_INDICES),
        "frame_window_selection": (
            "the first thirty-two seconds of measured replay are used in four "
            "passes; each pass uses the same thirty-two replay windows"),
        "paths": [f"{channel} {hydrophone}"
                  for channel, hydrophone in EXPECTED_PATHS],
        "receivers": sorted(EXPECTED_RECEIVERS),
        "protected_receivers": sorted(PROTECTED_RECEIVERS),
        "receiver_policy": {
            "lite": "unchanged", "profiled_cz": "CRC no-harm",
            "cwz_joint": "CRC no-harm",
        },
        "partial_fft_parts": expected_pfft,
        "partial_fft_bands": 16,
        "payload_bits_per_frame": 1616,
        "payload_bits_per_point": 206848,
        "result_group": "configuration",
        "result_scope": (
            "BER versus SNR, repeated first 32 s, 128 frames per point, seed 4"),
        "row_count": 960,
        "frame_trace_row_count": 122880,
        "protected_trace_row_count": 49152,
        "panel_count": 12,
        "series_count": 60,
        "snr_db": [float(value) for value in range(0, 31, 2)],
        "snr_definition": (
            "mean replayed-signal power divided by target added complex AWGN power"),
        "capture_sources": [
            {"path": f"data/{name}", "md5": digest}
            for name, digest in sorted(CAPTURE_MD5.items())
        ],
        "source_contract": source_contract,
        "source_contract_sha256": source_sha,
        "runner_sources": _family_source_hashes(),
        "sources": sources,
        "frame_trace_sources": frame_sources,
        "protected_trace_sources": protected_sources,
        "path_contracts": contracts,
        "awgn022_reference": reference,
    }
    _atomic_text(os.path.join(results_dir, "results_manifest.json"),
                 json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    _atomic_text(os.path.join(results_dir, "results_view.html"),
                 render_page(rows))
    print("BUILT AWGN-023C: 960 rows, 122880 frame traces, 49152 protected "
          "traces, 12 panels, 60 series, payload=1616")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment-dir", required=True)
    parser.add_argument("--reference-results", default=AWGN022_REFERENCE_RESULTS)
    args = parser.parse_args()
    try:
        build(os.path.abspath(args.experiment_dir),
              reference_results=os.path.abspath(args.reference_results),
              reference_hashes=AWGN022_REFERENCE_HASHES)
    except ResultContractError as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
