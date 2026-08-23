#!/usr/bin/env python3
"""Fail-closed contract for the JCM-386 correction to the one-frame demo."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_demo.jl"
RESULTS = HERE / "frame_results.csv"
MANIFEST = HERE / "demo_manifest.json"

SOURCE_WORKTREE = Path(
    "/home/gabiel/Documents/GitHub/Juna-worktrees/codex-direct-cz-ci"
)
SOURCE_COMMIT = "827bbb217e717291090b014b8aba8ea2df4c6dbf"
ACQUISITION_BASE_COMMIT = "261a4418327b2bbef77eeaad9e621d280f4617d3"
HELPER_DIR = Path(
    "/home/gabiel/Documents/GitHub/Juna-worktrees/codex-direct-cz-ci/"
    "JunaCore/experiments/2026-08-04-red-snr-sweep"
)
DIRECT_SOURCE = SOURCE_WORKTREE / "JunaCore/src/juna/direct_cz_frame.jl"
DIRECT_SOURCE_SHA256 = (
    "6004c01aac1d98c685f204ac4b065e91af0d6307940dab9444a0b8014d8e7342"
)
RED_MAT = Path(
    "/home/gabiel/Documents/GitHub/Juna/JunaCore/experiments/"
    "2026-08-01-red-lite-search/data/red_1.mat"
)
BLUE_MAT = Path("/home/gabiel/Documents/GitHub/replaychan/data/blue_1.mat")

EXPECTED_HASHES = {
    "benchmark_port": (
        HELPER_DIR / "benchmark_port.jl",
        "404685dcb0b98c5667b5391fdb8ee211f970db16880b5d566f9cd38a2b4b6ee8",
    ),
    "replay_lane": (
        HELPER_DIR / "replay_lane.jl",
        "78f9e16f1cedd7512ae88c77de23022b2f506939fccfe723dea75d7c9fac31cf",
    ),
    "red_mat": (
        RED_MAT,
        "09556b49e453a351f72b5c71435aab0048f68a80ab3b926ca4353dab47e89c45",
    ),
    "blue_mat": (
        BLUE_MAT,
        "639830f78ea044b877284dc0058f1c25179ba2448c06f228c9f0a62d0b2162de",
    ),
    "direct_cz_source": (DIRECT_SOURCE, DIRECT_SOURCE_SHA256),
}

DIRECT_IDENTITY = {
    "public_constructor": "JunaCore.JunaDirectCzFrame.Modulation",
    "concrete_receiver_type": "JunaCore.Juna.DirectCzFrameModulation",
    "descriptor_profile": "lite",
    "decode_adapter": "frame_decode_function",
    "objective_identity": "direct_cz_frame",
    "trace_accessor": "JunaCore.Juna._direct_cz_last_trace",
    "source_path": str(DIRECT_SOURCE),
    "source_sha256": DIRECT_SOURCE_SHA256,
}

RECEIVERS = {
    "ofdm_fec": "OFDM+LDPC",
    "pfft": "Partial-FFT+LDPC",
    "lite": "JUNA-Iterative",
    "profiled_cz": "profiled JUNA-(C,z)",
    "direct_cz": "JUNA-Direct-(C,z)",
}
NATIVE_PROFILES = {
    "ofdm_fec": "standard",
    "pfft": "pfft",
    "lite": "lite",
    "profiled_cz": "profiled_cz",
}
DATASETS = {
    "red": ("red1", 9_600.0),
    "blue": ("blue1", 4_882.8125),
}
EXPECTED_GEOMETRY = {
    ("red", 512): (1_653, 9_280, 6),
    ("red", 1024): (1_839, 9_536, 6),
    ("blue", 512): (726, 4_388, 16),
    ("blue", 1024): (726, 4_260, 16),
}
PAIR_DIGESTS = (
    "workload_digest",
    "payload_digest",
    "code_digest",
    "transmitted_digest",
    "received_digest",
    "noise_digest",
    "replay_digest",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def integer(row: dict[str, str], field: str) -> int:
    value = float(row[field])
    require(value.is_integer(), f"{field} is not an integer: {row[field]}")
    return int(value)


def close(left: float, right: float, *, atol: float = 1e-12) -> bool:
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=atol)


def git_output(*arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(SOURCE_WORKTREE), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main() -> None:
    require(RUNNER.is_file() and not RUNNER.is_symlink(), f"missing regular runner: {RUNNER}")
    require(RESULTS.is_file() and not RESULTS.is_symlink(), f"missing regular results: {RESULTS}")
    require(MANIFEST.is_file() and not MANIFEST.is_symlink(), f"missing regular manifest: {MANIFEST}")

    for label, (path, expected) in EXPECTED_HASHES.items():
        require(path.is_file() and not path.is_symlink(), f"missing regular {label}: {path}")
        require(sha256(path) == expected, f"{label} SHA-256 differs")

    require(git_output("rev-parse", "HEAD") == SOURCE_COMMIT, "live source commit differs")
    require(git_output("status", "--porcelain=v1", "--untracked-files=all") == "", "live source worktree is not clean")
    require(
        git_output("merge-base", SOURCE_COMMIT, "c7fce64af71fb75a23cffaa300a41171379622ae")
        == ACQUISITION_BASE_COMMIT,
        "Direct and demonstration sources do not share the pinned acquisition base",
    )

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    require(manifest.get("approval_id") == "JCM-385", "approval ID differs")
    require(manifest.get("correction_approval_id") == "JCM-386", "correction approval ID differs")
    require(
        manifest.get("superseded_result_sha256")
        == "681add3a01a8a2e928c458b1221f7fb61fc7ba2d5618629ae12a14c7385dbfcb",
        "superseded result identity differs",
    )
    require(manifest.get("status") == "complete", "manifest status differs")
    require(manifest.get("illustration_only") is True, "illustration-only flag differs")
    require(manifest.get("frames_per_condition") == 1, "frame count differs")
    require(manifest.get("snr_db") == 20, "SNR differs")
    require(manifest.get("seed") == 4, "seed differs")
    require(manifest.get("scope") == "red1-h1-blue1-h1-n512-n1024", "scope differs")
    require(manifest.get("not_general_evidence") is True, "general-evidence guard differs")

    source = manifest.get("source", {})
    require(source.get("worktree") == str(SOURCE_WORKTREE), "source worktree differs")
    require(source.get("commit") == SOURCE_COMMIT, "source commit differs")
    require(source.get("clean") is True, "source was not recorded clean")
    require(source.get("juna_core_path") == str(SOURCE_WORKTREE / "JunaCore"), "JunaCore path differs")
    require(source.get("acquisition_base_commit") == ACQUISITION_BASE_COMMIT, "acquisition base differs")

    direct_identity = manifest.get("direct_receiver_identity", {})
    require(direct_identity == DIRECT_IDENTITY, "manifest Direct receiver identity differs")

    inputs = manifest.get("inputs", {})
    for label, (path, expected) in EXPECTED_HASHES.items():
        entry = inputs.get(label, {})
        require(entry.get("path") == str(path), f"manifest {label} path differs")
        require(entry.get("sha256") == expected, f"manifest {label} hash differs")

    outputs = manifest.get("outputs", {})
    result_entry = outputs.get("frame_results", {})
    require(result_entry.get("path") == str(RESULTS), "result path differs")
    require(result_entry.get("sha256") == sha256(RESULTS), "result hash differs")
    require(result_entry.get("rows") == 20, "manifest result-row count differs")
    require(outputs.get("runner_sha256") == sha256(RUNNER), "runner hash differs")

    with RESULTS.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        require(reader.fieldnames is not None, "results header is missing")
        for field in (
            "dataset", "channel", "hydrophone", "configuration", "nfft", "cp",
            "code_rate", "outer_spacing", "inner_spacing", "partial_fft_bands",
            "snr_db", "frame", "receiver_id",
            "receiver_label", "bandwidth_hz", "useful_symbol_seconds", "cp_seconds",
            "subcarrier_spacing_hz", "frame_duration_seconds", "frame_samples",
            "payload_bits", "bit_errors", "ber", "success",
            "configured_rate_bit_per_s_hz", "decode_failure", "snapshot_index",
            "payload_seed", "noise_seed", "replay_seed", "optimizer_seed",
            "public_constructor", "concrete_receiver_type", "descriptor_profile",
            "decode_adapter", "objective_identity", "trace_accessor",
            "receiver_source_path", "receiver_source_sha256",
            "standard_crc_valid", "rescue_executed", "rescue_crc_valid",
            "gradient_checkpoints", "accepted_steps", "rejected_steps",
            *PAIR_DIGESTS,
        ):
            require(field in reader.fieldnames, f"missing result field: {field}")

    require(len(rows) == 20, f"expected 20 rows, found {len(rows)}")
    expected_keys = {
        (dataset, nfft, receiver)
        for dataset in DATASETS
        for nfft in (512, 1024)
        for receiver in RECEIVERS
    }
    seen_keys: set[tuple[str, int, str]] = set()
    grouped: dict[tuple[str, int], list[dict[str, str]]] = {}

    for row in rows:
        dataset = row["dataset"]
        require(dataset in DATASETS, f"unknown dataset: {dataset}")
        channel, bandwidth = DATASETS[dataset]
        nfft = integer(row, "nfft")
        receiver_id = row["receiver_id"]
        key = (dataset, nfft, receiver_id)
        require(key in expected_keys, f"unexpected result key: {key}")
        require(key not in seen_keys, f"duplicate result key: {key}")
        seen_keys.add(key)
        grouped.setdefault((dataset, nfft), []).append(row)

        require(row["channel"] == channel, f"{key}: channel differs")
        require(integer(row, "hydrophone") == 1, f"{key}: hydrophone differs")
        require(row["configuration"] == f"n{nfft}-cp64-p6-8", f"{key}: configuration differs")
        require(integer(row, "cp") == 64, f"{key}: CP differs")
        require(integer(row, "outer_spacing") == 6, f"{key}: outer spacing differs")
        require(integer(row, "inner_spacing") == 8, f"{key}: inner spacing differs")
        require(close(float(row["code_rate"]), 0.25), f"{key}: code rate differs")
        expected_payload, expected_samples, expected_bands = EXPECTED_GEOMETRY[(dataset, nfft)]
        require(integer(row, "partial_fft_bands") == expected_bands, f"{key}: Partial-FFT band count differs")
        require(close(float(row["snr_db"]), 20.0), f"{key}: SNR differs")
        require(integer(row, "frame") == 1, f"{key}: frame differs")
        require(row["receiver_label"] == RECEIVERS[receiver_id], f"{key}: receiver label differs")
        if receiver_id == "direct_cz":
            for field, expected in DIRECT_IDENTITY.items():
                csv_field = {
                    "source_path": "receiver_source_path",
                    "source_sha256": "receiver_source_sha256",
                }.get(field, field)
                require(row[csv_field] == expected, f"{key}: Direct {csv_field} differs")
            require(row["selection_reason"] in {
                "standard_crc_valid", "crc_rescue", "standard_fallback"
            }, f"{key}: Direct selection trace differs")
            standard_crc_valid = row["standard_crc_valid"].lower() == "true"
            rescue_executed = row["rescue_executed"].lower() == "true"
            rescue_crc_valid = row["rescue_crc_valid"].lower() == "true"
            accepted_steps = integer(row, "accepted_steps")
            rejected_steps = integer(row, "rejected_steps")
            require(integer(row, "gradient_checkpoints") == accepted_steps, f"{key}: Direct checkpoint count differs")
            require(accepted_steps >= 0 and rejected_steps >= 0, f"{key}: Direct step counts differ")
            require(rescue_executed == (not standard_crc_valid), f"{key}: Direct rescue boundary differs")
            require(rescue_crc_valid == (row["selection_reason"] == "crc_rescue"), f"{key}: Direct rescue selection differs")
        else:
            require(row["decode_adapter"] == "benchmark-native", f"{key}: native decoder identity differs")
            require(row["public_constructor"] == "benchmark-native", f"{key}: native constructor identity differs")
            require(row["descriptor_profile"] == NATIVE_PROFILES[receiver_id], f"{key}: native descriptor profile differs")
        require(close(float(row["bandwidth_hz"]), bandwidth), f"{key}: bandwidth differs")
        require(close(float(row["useful_symbol_seconds"]), nfft / bandwidth), f"{key}: symbol duration differs")
        require(close(float(row["cp_seconds"]), 64 / bandwidth), f"{key}: CP duration differs")
        require(close(float(row["subcarrier_spacing_hz"]), bandwidth / nfft), f"{key}: subcarrier spacing differs")
        frame_duration = float(row["frame_duration_seconds"])
        require(0 < frame_duration <= 1.0, f"{key}: frame duration is outside (0,1]")
        require(integer(row, "frame_samples") == expected_samples, f"{key}: frame sample count differs")
        payload = integer(row, "payload_bits")
        require(payload == expected_payload, f"{key}: payload geometry differs")
        errors = integer(row, "bit_errors")
        require(payload > 0 and 0 <= errors <= payload, f"{key}: error arithmetic differs")
        require(close(float(row["ber"]), errors / payload), f"{key}: BER arithmetic differs")
        decode_failure = row["decode_failure"].lower() == "true"
        success = row["success"].lower() == "true"
        require(success == (errors == 0 and not decode_failure), f"{key}: success flag differs")
        expected_rate = payload / bandwidth if success else 0.0
        require(close(float(row["configured_rate_bit_per_s_hz"]), expected_rate), f"{key}: configured-rate arithmetic differs")
        require(integer(row, "snapshot_index") == 1, f"{key}: snapshot differs")
        for seed_field in ("payload_seed", "noise_seed", "replay_seed", "optimizer_seed"):
            require(integer(row, seed_field) == 4, f"{key}: {seed_field} differs")
        for digest_field in PAIR_DIGESTS:
            value = row[digest_field]
            require(len(value) == 64 and all(c in "0123456789abcdef" for c in value), f"{key}: {digest_field} is not SHA-256")

    require(seen_keys == expected_keys, "result grid is incomplete")
    for condition, condition_rows in grouped.items():
        require(len(condition_rows) == 5, f"{condition}: receiver count differs")
        for digest_field in PAIR_DIGESTS:
            require(len({row[digest_field] for row in condition_rows}) == 1, f"{condition}: receivers did not share {digest_field}")
        require(len({row["payload_bits"] for row in condition_rows}) == 1, f"{condition}: payload size differs across receivers")
        require(len({row["frame_samples"] for row in condition_rows}) == 1, f"{condition}: frame size differs across receivers")

    print(
        "JCM386_DIRECT_CORRECTION_VALID conditions=4 rows=20 receivers=5 "
        "direct_facade=true injected_decoder=true frames=1 illustration_only=true"
    )


if __name__ == "__main__":
    main()
