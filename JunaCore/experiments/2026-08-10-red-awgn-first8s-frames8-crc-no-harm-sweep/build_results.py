#!/usr/bin/env python3
"""Validate, combine, and render the approved AWGN-020 result."""

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
PARTIAL_FFT_PARTS = matrix_contract.PARTIAL_FFT_PARTS
SNAPSHOT_INDICES = matrix_contract.SNAPSHOT_INDICES
GEOMETRY_KEYS = (
    "nfft", "cp", "code_rate", "outer_spacing", "inner_spacing",
    "check_degree", "horizon",
)
SOURCE_BASENAME = "red_snr_sweep_awgn_first8s_frames8_configuration.csv"
OUTPUT_BASENAME = "red_snr_sweep_awgn_first8s_frames8.csv"
PATH_CONTRACT_BASENAME = "awgn020_path_contract.txt"
FIRST4_REFERENCE_CSV = os.path.join(
    "/home/gabiel/Documents/GitHub/Juna-worktrees/awgn-results/JunaCore/experiments",
    "2026-08-09-red-awgn-crc-no-harm-3receivers-"
    "n1024-cp64-rate025-p5-5-dc14-kfill-pfft4",
    "results", "red_snr_sweep_awgn_first4s_frames4.csv",
)
FIRST4_REFERENCE_SHA256 = (
    "69f127ad662aa1dfe4212283767c3d131f52298b735f4b06aaddc61fc43575da"
)

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
CAPTURE_MD5 = {
    "red_1.mat": "76ee45172cd0bf5deb4a7bfb04907884",
    "red_2.mat": "cb1b4566f5e9db67b93c072dbce8db06",
    "red_3.mat": "befb441590ddafc4383746cc0526d4b6",
    "red_4.mat": "bbab171a6af14632944d1fee157cde86",
}


class ResultContractError(RuntimeError):
    """One measured AWGN-020 artifact violated the approved contract."""


def require(condition, message):
    if not condition:
        raise ResultContractError("AWGN-020 result contract failed: " + message)


def file_digest(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def parse_geometry(experiment_id):
    try:
        return matrix_contract.parse_geometry(experiment_id)
    except matrix_contract.MatrixContractError as error:
        raise ResultContractError(str(error)) from error


def source_name(channel, hydrophone):
    return f"runs/{channel}_hydrophone{hydrophone}/{SOURCE_BASENAME}"


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
        ("frame_trace_sha256", file_digest(os.path.join(results_dir, frame_trace))),
        ("protected_trace_sha256",
         file_digest(os.path.join(results_dir, protected_trace))),
        ("source_contract_sha256", file_digest(os.path.join(HERE, "source_contract.json"))),
        ("runner_sha256", file_digest(os.path.join(HERE, "run_awgn020.jl"))),
        ("sweep_sha256", file_digest(os.path.join(HERE, "awgn020_sweep.jl"))),
        ("aggregate_rows", "80"),
        ("frame_trace_rows", "640"),
        ("protected_trace_rows", "256"),
        ("capture_seconds", "8.0"),
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
        require(row["seed"] == "4" and row["frames"] == "8",
                "seed or frame count differs: " + source)
        require(row["objective"] == "configuration"
                and row["noise_model"] == "awgn", "scope differs: " + source)
        require(float(row["capture_start_seconds"]) == 0.0
                and float(row["capture_stop_seconds"]) == 8.0,
                "capture interval differs: " + source)
        require(int(row["capture_tap_snapshots"]) == 769
                and int(row["capture_phase_samples"]) == 153800,
                "capture geometry differs: " + source)
        require(int(row["partial_fft_parts"]) == expected_pfft
                and int(row["partial_fft_bands"]) > 0,
                "partial-FFT geometry differs: " + source)
        require(int(row["payload_bits_per_frame"]) == 1616
                and int(row["payload_bits"]) == 8 * 1616,
                "payload geometry differs: " + source)
        require(int(row["decode_failures"]) == 0,
                "decode failure recorded: " + source)


def _validate_frame_traces(rows, source):
    require(len(rows) == 640,
            f"expected 640 frame traces, found {len(rows)}: {source}")
    require({row["algorithm_id"] for row in rows} == EXPECTED_RECEIVERS,
            "frame-trace receiver set differs: " + source)
    require({float(row["snr_db"]) for row in rows} == EXPECTED_SNRS,
            "frame-trace SNR set differs: " + source)
    keys = {(row["algorithm_id"], float(row["snr_db"]), int(row["frame"]))
            for row in rows}
    require(len(keys) == 640, "frame-trace keys are duplicated: " + source)
    for row in rows:
        frame = int(row["frame"])
        require(1 <= frame <= 8, "frame index differs: " + source)
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
                and float(row["capture_stop_seconds"]) == 8.0,
                "frame scope differs: " + source)
        require(float(row["replay_support_end_seconds"]) <= 8.0 + 1e-9,
                "frame replay support exceeds 8 seconds: " + source)
        require(int(row["frame_samples"]) == 9536
                and int(row["payload_bits"]) == 1616,
                "frame geometry differs: " + source)
        require(not _bool(row, "decode_failure", source),
                "frame decode failure recorded: " + source)
    for snr in EXPECTED_SNRS:
        for frame in range(1, 9):
            paired = [row for row in rows
                      if float(row["snr_db"]) == snr
                      and int(row["frame"]) == frame]
            require(len(paired) == 5, "paired receiver count differs: " + source)
            signature = {
                (row["workload_id"], row["snapshot_index"], row["payload_seed"],
                 row["noise_seed"], row["replay_seed"], row["optimizer_seed"])
                for row in paired
            }
            require(len(signature) == 1,
                    "five receivers do not share one workload: " + source)


def _validate_protected_traces(rows, source, frame_rows):
    require(len(rows) == 256,
            f"expected 256 protected traces, found {len(rows)}: {source}")
    require({row["algorithm_id"] for row in rows} == PROTECTED_RECEIVERS,
            "protected receiver set differs: " + source)
    keys = {(row["algorithm_id"], float(row["snr_db"]), int(row["frame"]))
            for row in rows}
    require(len(keys) == 256, "protected keys are duplicated: " + source)
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
        for field in ("workload_id", "snapshot_index", "bit_errors", "success",
                      "partial_fft_parts", "partial_fft_bands"):
            require(row[field] == frame[field],
                    f"protected/frame {field} differs: {source}")


def _reconcile(aggregates, frame_rows, source):
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
            require(len(frames) == 8
                    and successes == int(aggregate["successful_frames"])
                    and errors == int(aggregate["bit_errors"])
                    and failures == int(aggregate["decode_failures"]),
                    "aggregate/frame outcomes do not reconcile: " + source)


def _first4_reference(rows, reference_csv, reference_sha256):
    require(os.path.isfile(reference_csv), "missing first-four reference")
    require(not os.path.islink(reference_csv), "first-four reference is a symlink")
    if reference_sha256 is not None:
        require(file_digest(reference_csv) == reference_sha256,
                "first-four reference hash differs")
    with open(reference_csv, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        require(tuple(reader.fieldnames or ()) == AGGREGATE_COLUMNS,
                "first-four reference schema differs")
        reference_rows = list(reader)
    require(len(reference_rows) == 960, "first-four reference row count differs")
    reference = {
        (row["channel"], int(row["lane"]), row["algorithm_id"],
         float(row["snr_db"])): row for row in reference_rows
    }
    require(len(reference) == 960, "first-four reference keys are duplicated")
    grouped = {}
    for row in rows:
        if int(row["frame"]) <= 4:
            key = (row["channel"], int(row["lane"]), row["algorithm_id"],
                   float(row["snr_db"]))
            grouped.setdefault(key, []).append(row)
    require(set(grouped) == set(reference), "first-four key sets differ")
    for key, frames in grouped.items():
        require(len(frames) == 4, "first-four frame count differs")
        ref = reference[key]
        successes = sum(_bool(row, "success", "first-four") for row in frames)
        errors = sum(int(row["bit_errors"]) for row in frames)
        failures = sum(_bool(row, "decode_failure", "first-four") for row in frames)
        duration = float(frames[0]["frame_duration_seconds"])
        expected_rate = successes * 1616 / (4 * duration)
        exact = {
            "seed": "4", "frames": "4", "objective": "configuration",
            "noise_model": "awgn", "nfft": "1024", "cp": "64",
            "code_rate": "0.25", "outer_spacing": "5",
            "inner_spacing": "5", "check_degree": "14", "horizon": "0",
            "partial_fft_parts": "4", "payload_bits_per_frame": "1616",
            "successful_frames": str(successes), "payload_bits": str(4 * 1616),
            "bit_errors": str(errors), "decode_failures": str(failures),
            "capture_start_seconds": "0.0", "capture_stop_seconds": "4.0",
            "capture_tap_snapshots": "385", "capture_phase_samples": "77000",
        }
        for field, value in exact.items():
            require(ref[field] == value,
                    f"first-four {field} differs at {key}")
        require(int(ref["partial_fft_bands"]) == 16,
                f"first-four bands differ at {key}")
        for field, expected in (
                ("psr", successes / 4),
                ("ber", errors / (4 * 1616)),
                ("effective_rate_bps", expected_rate)):
            require(abs(float(ref[field]) - expected) <= 1e-9 * max(1.0, abs(expected)),
                    f"first-four {field} differs at {key}")
    return {
        "path": reference_csv,
        "sha256": file_digest(reference_csv),
        "rows": len(reference_rows),
        "matched_outcome_rows": len(grouped),
        "excluded_field": "decode_seconds",
    }


def collect(experiment_dir, reference_csv=FIRST4_REFERENCE_CSV,
            reference_sha256=FIRST4_REFERENCE_SHA256):
    experiment_id = os.path.basename(os.path.normpath(experiment_dir))
    geometry, expected_pfft = parse_geometry(experiment_id)
    results_dir = os.path.join(experiment_dir, "results")
    aggregates = []
    all_frames = []
    protected = []
    sources = []
    frame_sources = []
    protected_sources = []
    contracts = []
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
        for row in frame_rows:
            row["channel"] = channel
            row["lane"] = str(hydrophone)
        _reconcile(source_rows, frame_rows, frame_name)
        all_frames.extend(frame_rows)
        frame_sources.append({"path": frame_name, "rows": 640,
                              "sha256": file_digest(os.path.join(results_dir, frame_name))})

        protected_name = protected_trace_name(channel, hydrophone)
        columns, protected_rows = load_csv(results_dir, protected_name)
        require(columns == PROTECTED_TRACE_COLUMNS,
                "protected columns differ: " + protected_name)
        _validate_protected_traces(protected_rows, protected_name, frame_rows)
        protected.extend(protected_rows)
        protected_sources.append({"path": protected_name, "rows": 256,
                                  "sha256": file_digest(os.path.join(results_dir, protected_name))})
        contracts.append(_path_contract_record(
            results_dir, experiment_id, channel, hydrophone,
            source, frame_name, protected_name))

    require(len(aggregates) == 960, "combined aggregate row count differs")
    require(len(all_frames) == 7680, "combined frame-trace row count differs")
    require(len(protected) == 3072, "combined protected row count differs")
    require(len(bands) == 1 and next(iter(bands)) == 16,
            "partial-FFT band count differs")
    first4 = _first4_reference(all_frames, reference_csv, reference_sha256)
    aggregates.sort(key=lambda row: (
        int(row["channel"][3:]), int(row["lane"]),
        float(row["snr_db"]), row["algorithm_id"]))
    return (experiment_id, results_dir, geometry, expected_pfft,
            aggregates, sources, frame_sources, protected_sources,
            contracts, first4)


def load_renderer(receiver_ids):
    path = os.path.join(EXPERIMENTS, "2026-08-04-red-snr-sweep",
                        "results", "build_sweep_view.py")
    require(os.path.isfile(path), "missing retained results renderer")
    spec = importlib.util.spec_from_file_location("awgn020_sweep_view", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.RECEIVERS = [receiver for receiver in module.RECEIVERS
                        if receiver[0] in receiver_ids]
    module.coincident_groups = lambda _entry: []
    return module


def render_page(rows):
    page = load_renderer(EXPECTED_RECEIVERS).render(rows, configuration_only=True)
    title = "AWGN-020: BER versus SNR"
    page = page.replace(
        "<title>Red replay channel: BER versus added-noise SNR</title>",
        f"<title>{title}</title>")
    page = page.replace(
        "<h1>Red replay channel: BER versus added-noise SNR</h1>",
        f"<h1>{title}</h1>")
    provenance = """<div class="provenance">
<p><b>Channel.</b> Each panel uses one hydrophone from the first eight seconds
of the measured red replay capture.</p>
<p><b>Frames.</b> Each SNR point uses eight approximately non-overlapping frames
whose complete replay windows fit inside the first eight seconds. The first four
replay windows are unchanged from the four-second results; four later replay
windows extend the observation to eight seconds. All five receivers use the
same transmitted frames, channel replay, and added AWGN.</p>
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
    names = ("awgn020_contract_test.jl", "awgn020_sweep.jl",
             "run_awgn020.jl", "matrix_contract.py", "build_results.py",
             "validate_results.py", "validate_matrix.py",
             "results_contract_test.py",
             "source_contract.json")
    return {name: file_digest(os.path.join(HERE, name)) for name in names
            if os.path.isfile(os.path.join(HERE, name))}


def _atomic_text(path, content):
    partial = path + ".partial"
    with open(partial, "w", encoding="utf-8") as handle:
        handle.write(content)
    os.replace(partial, path)


def build(experiment_dir, reference_csv=FIRST4_REFERENCE_CSV,
          reference_sha256=FIRST4_REFERENCE_SHA256):
    (experiment_id, results_dir, geometry_values, expected_pfft, rows,
     sources, frame_sources, protected_sources, contracts,
     first4) = collect(experiment_dir, reference_csv, reference_sha256)
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
        "noise_model": {"kind": "awgn", "generator": "BenchmarkPort._add_awgn",
                        "note": "independent complex Gaussian samples"},
        "channel_model": "measured red replay capture, one hydrophone per path",
        "capture_time_seconds": [0.0, 8.0],
        "time_window_s": [0.0, 8.0],
        "frame_count": 8,
        "frames_per_point": 8,
        "seed": 4,
        "snapshot_indices": list(SNAPSHOT_INDICES),
        "frame_window_selection": (
            "eight approximately non-overlapping complete replay windows; "
            "the first four are unchanged from the four-second result"),
        "paths": [f"{channel} {hydrophone}"
                  for channel, hydrophone in EXPECTED_PATHS],
        "receivers": sorted(EXPECTED_RECEIVERS),
        "protected_receivers": sorted(PROTECTED_RECEIVERS),
        "receiver_policy": {"lite": "unchanged", "profiled_cz": "CRC no-harm",
                            "cwz_joint": "CRC no-harm"},
        "partial_fft_parts": expected_pfft,
        "partial_fft_bands": 16,
        "payload_bits_per_frame": 1616,
        "result_group": "configuration",
        "result_scope": "BER versus SNR, first 8 s, 8 frames per point, seed 4",
        "row_count": 960,
        "frame_trace_row_count": 7680,
        "protected_trace_row_count": 3072,
        "panel_count": 12,
        "series_count": 60,
        "snr_db": [float(value) for value in range(0, 31, 2)],
        "snr_definition": (
            "mean replayed-signal power divided by target added complex AWGN power"),
        "capture_sources": [{"path": f"data/{name}", "md5": digest}
                            for name, digest in sorted(CAPTURE_MD5.items())],
        "source_contract": source_contract,
        "source_contract_sha256": source_sha,
        "runner_sources": _family_source_hashes(),
        "sources": sources,
        "frame_trace_sources": frame_sources,
        "protected_trace_sources": protected_sources,
        "path_contracts": contracts,
        "first_four_reference": first4,
    }
    _atomic_text(os.path.join(results_dir, "results_manifest.json"),
                 json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    _atomic_text(os.path.join(results_dir, "results_view.html"), render_page(rows))
    print("BUILT AWGN-020: 960 rows, 7680 frame traces, 3072 protected "
          "traces, 12 panels, 60 series, payload=1616")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment-dir", required=True)
    parser.add_argument("--reference-csv", default=FIRST4_REFERENCE_CSV)
    args = parser.parse_args()
    try:
        build(os.path.abspath(args.experiment_dir),
              reference_csv=os.path.abspath(args.reference_csv),
              reference_sha256=FIRST4_REFERENCE_SHA256)
    except ResultContractError as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
