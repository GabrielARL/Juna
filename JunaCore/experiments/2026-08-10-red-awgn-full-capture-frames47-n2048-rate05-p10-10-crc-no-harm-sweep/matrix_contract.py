#!/usr/bin/env python3
"""Approved AWGN-027 geometry and result-shape contract."""

import re


FAMILY = "2026-08-10-red-awgn-full-capture-frames47-crc-no-harm"
CAMPAIGN = "AWGN-027"
EXPECTED_IDS = (
    f"{FAMILY}-n2048-cp64-rate05-p10-10-dc14-kfill-pfft4",
)
ID_RE = re.compile(
    rf"^{re.escape(FAMILY)}-n(?P<nfft>2048)-cp(?P<cp>64)-"
    r"rate(?P<rate>05)-p(?P<outer>10)-(?P<inner>10)-"
    r"dc(?P<check>14)-k(?P<horizon>fill)-pfft(?P<pfft>4)$"
)
EXPECTED_PATHS = tuple(
    (f"red{capture}", hydrophone)
    for capture in range(1, 5)
    for hydrophone in range(1, 4)
)
EXPECTED_SNRS = frozenset(float(value) for value in range(0, 31, 2))
EXPECTED_RECEIVERS = frozenset(
    {"ofdm_fec", "pfft", "lite", "profiled_cz", "cwz_joint"}
)
PROTECTED_RECEIVERS = frozenset({"profiled_cz", "cwz_joint"})
FRAMES = 47
CAPTURE_SECONDS = 47.78125
SEED = 4
PARTIAL_FFT_PARTS = 4
SNAPSHOT_INDICES = (
    1, 99, 197, 294, 392, 490, 588, 686,
    783, 881, 979, 1077, 1175, 1272, 1370, 1468,
    1566, 1664, 1761, 1859, 1957, 2055, 2153, 2250,
    2348, 2446, 2544, 2642, 2740, 2837, 2935, 3033,
    3131, 3229, 3326, 3424, 3522, 3620, 3718, 3815,
    3913, 4011, 4109, 4207, 4304, 4402, 4500,
)
AGGREGATE_ROWS_PER_PATH = 80
FRAME_TRACE_ROWS_PER_PATH = 3760
PROTECTED_TRACE_ROWS_PER_PATH = 1504
PAYLOAD_BITS_PER_FRAME = 3296
PAYLOAD_BITS_PER_POINT = 154912
AWGN023B_SWEEP_SHA256 = (
    "6a995c62fbd938d69b7aa2c19f76e0bf618769b956fe764f64f19a60cb5d38ca"
)
AWGN023B_SOURCE_CONTRACT_SHA256 = (
    "7081e56775f5665d615964dd7230596b0f8afd301ce0889dad5a0e606f510e00"
)
EXPECTED_CHANGED_SOURCE_SHA256 = {
    "JunaCore/src/JunaCore.jl": (
        "1666665f7a2728033d8f3645afa308fa8605d238dc534d038f4a611b0f419932"),
    "JunaCore/src/juna/common.jl": (
        "447bada2fb97bcff256f0d5acf6b9e6b867f1d852f0b3e24a9c8344eabb906ff"),
    "JunaCore/src/juna/frame_wide_ldpc.jl": (
        "f220e44dd80b5332ece6c140fdd8ac75e31ce8849bb2584de16e2cf561a12ab2"),
    "JunaCore/src/juna/profiled_cz_frame.jl": (
        "46c2e77080a6161c356acfe1691f9139ef0102ee5fa1696cd317ece426b4feb4"),
}
EXPECTED_CAPTURE_SHA256 = {
    "red_1.mat": "09556b49e453a351f72b5c71435aab0048f68a80ab3b926ca4353dab47e89c45",
    "red_2.mat": "0e42027cd51137e0c4519c7a9c109568ab513a5eece1abfc60b0073fe605f6eb",
    "red_3.mat": "e3e4e53e96ec361e3df492616ae3f024727f039b5e5b1405dd709c8265798179",
    "red_4.mat": "115ac3d1ae8b067858192f32a3fcfd073ee0220b3e2d0f5a6dc1dc7460bd27aa",
}


class MatrixContractError(RuntimeError):
    """The approved AWGN-027 matrix shape was not met."""


def parse_geometry(experiment_id):
    match = ID_RE.fullmatch(experiment_id)
    if match is None:
        raise MatrixContractError(
            "unexpected AWGN-027 experiment ID: " + experiment_id
        )
    values = match.groupdict()
    geometry = (
        values["nfft"], values["cp"], "0.5", values["outer"],
        values["inner"], values["check"], "0",
    )
    return geometry, int(values["pfft"])


def validate_ids():
    if len(EXPECTED_IDS) != 1 or len(set(EXPECTED_IDS)) != 1:
        raise MatrixContractError("experiment ID is not one unique value")
    parse_geometry(EXPECTED_IDS[0])


def validate_source_contract(payload):
    if payload.get("campaign") != CAMPAIGN or payload.get("family") != FAMILY:
        raise MatrixContractError("source contract campaign or family differs")
    expected_measurement = {
        "nfft": 2048,
        "cp": 64,
        "code_rate": 0.5,
        "outer_spacing": 10,
        "inner_spacing": 10,
        "check_degree": 14,
        "horizon": 0,
        "partial_fft_parts": 4,
        "snr_db": list(range(0, 31, 2)),
        "frames": FRAMES,
        "seed": SEED,
        "capture_seconds": CAPTURE_SECONDS,
        "frame_samples": 8320,
        "capture_position_stop": 4500,
        "final_replay_support_end_seconds": 47.7734375,
        "snapshot_indices": list(SNAPSHOT_INDICES),
        "paths": 12,
    }
    if payload.get("measurement") != expected_measurement:
        raise MatrixContractError("source contract measurement differs")
    expected_receivers = [
        {"id": "ofdm_fec", "name": "OFDM + FEC", "crc_no_harm": False},
        {"id": "pfft", "name": "Partial-FFT + FEC", "crc_no_harm": False},
        {"id": "lite", "name": "JUNA-Lite", "crc_no_harm": False},
        {
            "id": "profiled_cz",
            "name": "JUNA (C,z) Joint gradient",
            "crc_no_harm": True,
        },
        {
            "id": "cwz_joint",
            "name": "Juna joint (C,W,z)",
            "crc_no_harm": True,
        },
    ]
    if payload.get("receivers") != expected_receivers:
        raise MatrixContractError("source contract receiver set differs")
    if payload.get("per_path") != {
        "aggregate_rows": AGGREGATE_ROWS_PER_PATH,
        "frame_trace_rows": FRAME_TRACE_ROWS_PER_PATH,
        "protected_trace_rows": PROTECTED_TRACE_ROWS_PER_PATH,
    }:
        raise MatrixContractError("source contract per-path counts differ")
    if (payload.get("payload_bits_per_frame") != PAYLOAD_BITS_PER_FRAME
            or payload.get("payload_bits_per_point") != PAYLOAD_BITS_PER_POINT):
        raise MatrixContractError("source contract payload capacity differs")
    if payload.get("selection_reasons") != [
        "standard_crc_valid", "crc_rescue", "standard_fallback",
    ]:
        raise MatrixContractError("source contract selection reasons differ")
    if payload.get("optimized_variables") != {
        "profiled_cz": "C+z", "cwz_joint": "C+W+z",
    }:
        raise MatrixContractError("source contract optimized variables differ")
    expected_receiver_source = {
        "repository": (
            "/home/gabiel/Documents/GitHub/Juna-worktrees/"
            "crc-no-harm-gradients"),
        "base_commit": "7fbdec9dd93e7ed5caade4bae4a73ccd030a7d3f",
        "tracked_source_diff_sha256": (
            "4e19b15bea8fd9c96c2721691629ae35deb3538e43b92ccc1ec9a7fe8cdf8821"),
        "changed_source_sha256": EXPECTED_CHANGED_SOURCE_SHA256,
        "loaded_modules": [
            "JunaCore.JunaProfiledCzFrame.Modulation",
            "JunaCore.JunaCrcConditionedJointCwzFrame.Modulation",
        ],
    }
    if payload.get("receiver_source") != expected_receiver_source:
        raise MatrixContractError("source contract receiver source differs")
    if payload.get("active_project") != (
            "/home/gabiel/Documents/GitHub/Juna-worktrees/"
            "src-001a-receiver-source/JunaCore/experiments/"
            "2026-08-04-red-snr-sweep/Project.toml"):
        raise MatrixContractError("source contract active project differs")
    if payload.get("active_project_sha256") != (
            "09dd9b79369735576e21c210c969e16dbf77cc1ea333aecb2e4ee9d3b13a0ef0"):
        raise MatrixContractError("source contract project hash differs")
    if payload.get("active_manifest_sha256") != (
            "ab8752e8e162a64bcf22441d1b4906dd30ef7c40447b7d8abe5bc22a93226b90"):
        raise MatrixContractError("source contract manifest hash differs")
    expected_schedule = {
        "schedule_source": "AWGN-023B",
        "source_sweep": (
            "/home/gabiel/Documents/GitHub/Juna-worktrees/awgn-results/"
            "JunaCore/experiments/2026-08-10-red-awgn-full-capture-"
            "frames47-crc-no-harm-sweep/awgn023b_sweep.jl"),
        "source_sweep_sha256": AWGN023B_SWEEP_SHA256,
        "source_contract_sha256": AWGN023B_SOURCE_CONTRACT_SHA256,
        "payload_seed_range": [4, 50],
        "noise_seed_range": [4, 50],
        "replay_seed_range": [4, 50],
        "optimizer_seed": 4,
        "outcome_equality_required": False,
        "snapshot_schedule_equality_required": False,
    }
    if payload.get("schedule_provenance") != expected_schedule:
        raise MatrixContractError("source contract schedule provenance differs")
    if payload.get("capture_sources") != EXPECTED_CAPTURE_SHA256:
        raise MatrixContractError("source contract capture sources differ")
    if payload.get("global") != {
        "aggregate_rows": 960,
        "frame_trace_rows": 45120,
        "protected_trace_rows": 18048,
    }:
        raise MatrixContractError("source contract global counts differ")


if __name__ == "__main__":
    validate_ids()
    print(
        "AWGN-027 MATRIX CONTRACT PASS: 1 configuration, 12 paths, "
        "5 receivers, 0:2:30 dB, complete measured capture, 47 frames, PFFT=4"
    )
