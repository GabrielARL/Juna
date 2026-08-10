#!/usr/bin/env python3
"""Validate, combine, and render the approved AWGN-027 result."""

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
PAYLOAD_BITS_PER_FRAME = matrix_contract.PAYLOAD_BITS_PER_FRAME
PAYLOAD_BITS_PER_POINT = matrix_contract.PAYLOAD_BITS_PER_POINT
GEOMETRY_KEYS = (
    "nfft", "cp", "code_rate", "outer_spacing", "inner_spacing",
    "check_degree", "horizon",
)
SOURCE_BASENAME = "red_snr_sweep_awgn_full_capture_frames47_configuration.csv"
OUTPUT_BASENAME = "red_snr_sweep_awgn_full_capture_frames47.csv"
PATH_CONTRACT_BASENAME = "awgn027_path_contract.txt"

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
    """One measured AWGN-027 artifact violated the approved contract."""


def require(condition, message):
    if not condition:
        raise ResultContractError("AWGN-027 result contract failed: " + message)


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
        ("frame_trace_sha256", file_digest(
            os.path.join(results_dir, frame_trace))),
        ("protected_trace_sha256", file_digest(
            os.path.join(results_dir, protected_trace))),
        ("source_contract_sha256", file_digest(
            os.path.join(HERE, "source_contract.json"))),
        ("runner_sha256", file_digest(os.path.join(HERE, "run_awgn027.jl"))),
        ("sweep_sha256", file_digest(os.path.join(HERE, "awgn027_sweep.jl"))),
        ("aggregate_rows", "80"),
        ("frame_trace_rows", "3760"),
        ("protected_trace_rows", "1504"),
        ("capture_seconds", "47.78125"),
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
        require(row["seed"] == "4" and row["frames"] == "47",
                "seed or frame count differs: " + source)
        require(row["objective"] == "configuration"
                and row["noise_model"] == "awgn", "scope differs: " + source)
        require(float(row["capture_start_seconds"]) == 0.0
                and float(row["capture_stop_seconds"]) == CAPTURE_SECONDS,
                "capture interval differs: " + source)
        require(int(row["capture_tap_snapshots"]) == 4588
                and int(row["capture_phase_samples"]) == 917600,
                "capture geometry differs: " + source)
        require(int(row["partial_fft_parts"]) == expected_pfft
                and int(row["partial_fft_bands"]) == 16,
                "partial-FFT geometry differs: " + source)
        require(int(row["payload_bits_per_frame"]) == PAYLOAD_BITS_PER_FRAME
                and int(row["payload_bits"]) == PAYLOAD_BITS_PER_POINT,
                "payload geometry differs: " + source)
        require(int(row["decode_failures"]) == 0,
                "decode failure recorded: " + source)


def _validate_frame_traces(rows, source):
    require(len(rows) == 3760,
            f"expected 3760 frame traces, found {len(rows)}: {source}")
    require({row["algorithm_id"] for row in rows} == EXPECTED_RECEIVERS,
            "frame-trace receiver set differs: " + source)
    require({float(row["snr_db"]) for row in rows} == EXPECTED_SNRS,
            "frame-trace SNR set differs: " + source)
    keys = {(row["algorithm_id"], float(row["snr_db"]), int(row["frame"]))
            for row in rows}
    require(len(keys) == 3760, "frame-trace keys are duplicated: " + source)
    for row in rows:
        frame = int(row["frame"])
        require(1 <= frame <= 47, "frame index differs: " + source)
        require(int(row["snapshot_index"]) == SNAPSHOT_INDICES[frame - 1],
                "snapshot schedule differs: " + source)
        expected_seed = frame + 3
        require(int(row["payload_seed"]) == expected_seed
                and int(row["noise_seed"]) == expected_seed
                and int(row["replay_seed"]) == expected_seed
                and int(row["optimizer_seed"]) == 4,
                "frame seed differs: " + source)
        require(row["noise_model"] == "awgn"
                and float(row["capture_start_seconds"]) == 0.0
                and float(row["capture_stop_seconds"]) == CAPTURE_SECONDS,
                "frame scope differs: " + source)
        require(float(row["replay_support_end_seconds"])
                <= CAPTURE_SECONDS + 1e-9,
                "frame replay support exceeds the measured capture: " + source)
        require(int(row["frame_samples"]) == 8320
                and int(row["payload_bits"]) == PAYLOAD_BITS_PER_FRAME,
                "frame geometry differs: " + source)
        require(not _bool(row, "decode_failure", source),
                "frame decode failure recorded: " + source)
    workload_groups = {}
    for row in rows:
        key = (float(row["snr_db"]), int(row["frame"]))
        workload_groups.setdefault(key, []).append(row)
    for snr in EXPECTED_SNRS:
        for frame in range(1, 48):
            paired = workload_groups.get((snr, frame), [])
            require(len(paired) == 5, "paired receiver count differs: " + source)
            signature = {
                (row["workload_id"], row["snapshot_index"],
                 row["payload_seed"], row["noise_seed"], row["replay_seed"],
                 row["optimizer_seed"]) for row in paired
            }
            require(len(signature) == 1,
                    "five receivers do not share one workload: " + source)


def _validate_protected_traces(rows, source, frame_rows):
    require(len(rows) == 1504,
            f"expected 1504 protected traces, found {len(rows)}: {source}")
    require({row["algorithm_id"] for row in rows} == PROTECTED_RECEIVERS,
            "protected receiver set differs: " + source)
    keys = {(row["algorithm_id"], float(row["snr_db"]), int(row["frame"]))
            for row in rows}
    require(len(keys) == 1504, "protected keys are duplicated: " + source)
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
    aggregate_index = {
        (row["algorithm_id"], float(row["snr_db"])): row
        for row in aggregates
    }
    frame_groups = {}
    for row in frame_rows:
        key = (row["algorithm_id"], float(row["snr_db"]))
        frame_groups.setdefault(key, []).append(row)
    for receiver in EXPECTED_RECEIVERS:
        for snr in EXPECTED_SNRS:
            aggregate = aggregate_index[(receiver, snr)]
            frames = frame_groups.get((receiver, snr), [])
            successes = sum(_bool(row, "success", source) for row in frames)
            errors = sum(int(row["bit_errors"]) for row in frames)
            failures = sum(_bool(row, "decode_failure", source) for row in frames)
            require(len(frames) == FRAMES
                    and successes == int(aggregate["successful_frames"])
                    and errors == int(aggregate["bit_errors"])
                    and failures == int(aggregate["decode_failures"]),
                    "aggregate/frame outcomes do not reconcile: " + source)


def _source_contract():
    path = os.path.join(HERE, "source_contract.json")
    require(os.path.isfile(path), "missing source contract")
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    try:
        matrix_contract.validate_source_contract(payload)
    except matrix_contract.MatrixContractError as error:
        raise ResultContractError(str(error)) from error
    active_project = payload["active_project"]
    require(os.path.isfile(active_project) and not os.path.islink(active_project),
            "missing active project")
    require(file_digest(active_project) == payload["active_project_sha256"],
            "active project hash differs")
    active_manifest = os.path.join(
        os.path.dirname(active_project), "Manifest.toml")
    require(os.path.isfile(active_manifest)
            and not os.path.islink(active_manifest),
            "missing active manifest")
    require(file_digest(active_manifest) == payload["active_manifest_sha256"],
            "active manifest hash differs")
    receiver_source = payload["receiver_source"]
    for relative, expected in receiver_source["changed_source_sha256"].items():
        source_path = os.path.join(receiver_source["repository"], relative)
        require(os.path.isfile(source_path) and not os.path.islink(source_path),
                "missing receiver source: " + relative)
        require(file_digest(source_path) == expected,
                "receiver source hash differs: " + relative)
    schedule = payload["schedule_provenance"]
    sweep_path = schedule.get("source_sweep", "")
    require(os.path.isfile(sweep_path) and not os.path.islink(sweep_path),
            "missing AWGN-023B schedule source")
    require(file_digest(sweep_path) == schedule["source_sweep_sha256"],
            "AWGN-023B schedule source hash differs")
    contract_path = os.path.join(os.path.dirname(sweep_path), "source_contract.json")
    require(os.path.isfile(contract_path) and not os.path.islink(contract_path),
            "missing AWGN-023B source contract")
    require(file_digest(contract_path) == schedule["source_contract_sha256"],
            "AWGN-023B source contract hash differs")
    return payload, file_digest(path)


def collect(experiment_dir):
    experiment_id = os.path.basename(os.path.normpath(experiment_dir))
    geometry, expected_pfft = parse_geometry(experiment_id)
    results_dir = os.path.join(experiment_dir, "results")
    aggregates, sources = [], []
    frame_sources, protected_sources, contracts = [], [], []
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
        frame_sources.append({
            "path": frame_name, "rows": 3760,
            "sha256": file_digest(os.path.join(results_dir, frame_name)),
        })
        protected_name = protected_trace_name(channel, hydrophone)
        columns, protected_rows = load_csv(results_dir, protected_name)
        require(columns == PROTECTED_TRACE_COLUMNS,
                "protected columns differ: " + protected_name)
        _validate_protected_traces(protected_rows, protected_name, frame_rows)
        protected_sources.append({
            "path": protected_name, "rows": 1504,
            "sha256": file_digest(os.path.join(results_dir, protected_name)),
        })
        contracts.append(_path_contract_record(
            results_dir, experiment_id, channel, hydrophone,
            source, frame_name, protected_name))
    require(len(aggregates) == 960, "combined aggregate row count differs")
    require(sum(item["rows"] for item in frame_sources) == 45120,
            "combined all-frame trace row count differs")
    require(sum(item["rows"] for item in protected_sources) == 18048,
            "combined protected selection trace row count differs")
    require(bands == {16}, "partial-FFT band count differs")
    aggregates.sort(key=lambda row: (
        int(row["channel"][3:]), int(row["lane"]),
        float(row["snr_db"]), row["algorithm_id"]))
    return (experiment_id, results_dir, geometry, expected_pfft,
            aggregates, sources, frame_sources, protected_sources, contracts)


def load_renderer(receiver_ids):
    path = os.path.join(EXPERIMENTS, "2026-08-04-red-snr-sweep",
                        "results", "build_sweep_view.py")
    require(os.path.isfile(path), "missing retained results renderer")
    spec = importlib.util.spec_from_file_location("awgn027_sweep_view", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.RECEIVERS = [receiver for receiver in module.RECEIVERS
                        if receiver[0] in receiver_ids]
    module.coincident_groups = lambda _entry: []
    return module


def render_page(rows):
    page = load_renderer(EXPECTED_RECEIVERS).render(
        rows, configuration_only=True)
    title = "AWGN-027: BER versus SNR"
    page = page.replace(
        "<title>Red replay channel: BER versus added-noise SNR</title>",
        f"<title>{title}</title>")
    page = page.replace(
        "<h1>Red replay channel: BER versus added-noise SNR</h1>",
        f"<h1>{title}</h1>")
    provenance = """<div class="provenance">
<p><b>Channel.</b> Each panel uses one hydrophone from the complete measured red replay capture.</p>
<p><b>Frames.</b> Each SNR point uses forty-seven approximately non-overlapping frames
whose complete replay windows fit inside the measured capture. All five receivers use
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


def _family_source_hashes():
    names = (
        "awgn027_contract_test.jl", "awgn027_sweep.jl", "run_awgn027.jl",
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


def build(experiment_dir):
    (experiment_id, results_dir, geometry_values, expected_pfft, rows,
     sources, frame_sources, protected_sources, contracts) = collect(
         experiment_dir)
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
        "capture_time_seconds": [0.0, CAPTURE_SECONDS],
        "time_window_s": [0.0, CAPTURE_SECONDS],
        "frame_count": FRAMES,
        "frames_per_point": FRAMES,
        "seed": 4,
        "snapshot_indices": list(SNAPSHOT_INDICES),
        "frame_window_selection": (
            "forty-seven approximately non-overlapping complete replay windows"),
        "schedule_provenance": source_contract["schedule_provenance"],
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
        "payload_bits_per_frame": PAYLOAD_BITS_PER_FRAME,
        "payload_bits_per_point": PAYLOAD_BITS_PER_POINT,
        "result_group": "configuration",
        "result_scope": (
            "BER versus SNR, complete measured capture, 47 frames per point, seed 4"),
        "row_count": 960,
        "frame_trace_row_count": 45120,
        "protected_trace_row_count": 18048,
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
    }
    _atomic_text(os.path.join(results_dir, "results_manifest.json"),
                 json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    _atomic_text(os.path.join(results_dir, "results_view.html"),
                 render_page(rows))
    print("BUILT AWGN-027: 960 rows, 45120 all-frame traces, 18048 protected "
          "selection traces, 12 panels, 60 series, payload=3296")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment-dir", required=True)
    args = parser.parse_args()
    try:
        build(os.path.abspath(args.experiment_dir))
    except ResultContractError as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
