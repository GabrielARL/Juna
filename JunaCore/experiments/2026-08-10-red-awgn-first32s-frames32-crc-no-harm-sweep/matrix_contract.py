#!/usr/bin/env python3
"""Approved AWGN-022 geometry and result-shape contract."""

import re


FAMILY = "2026-08-10-red-awgn-first32s-frames32-crc-no-harm"
CAMPAIGN = "AWGN-022"
EXPECTED_IDS = (
    f"{FAMILY}-n1024-cp64-rate025-p5-5-dc14-kfill-pfft4",
)
ID_RE = re.compile(
    rf"^{re.escape(FAMILY)}-n(?P<nfft>1024)-cp(?P<cp>64)-"
    r"rate(?P<rate>025)-p(?P<outer>5)-(?P<inner>5)-"
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
FRAMES = 32
CAPTURE_SECONDS = 32.0
SEED = 4
PARTIAL_FFT_PARTS = 4
SNAPSHOT_INDICES = (
    1, 96, 190, 285, 385, 480, 574, 669,
    769, 864, 958, 1053, 1153, 1248, 1342, 1437,
    1537, 1632, 1726, 1821, 1921, 2016, 2110, 2205,
    2305, 2400, 2494, 2589, 2689, 2784, 2878, 2973,
)
AGGREGATE_ROWS_PER_PATH = 80
FRAME_TRACE_ROWS_PER_PATH = 2560
PROTECTED_TRACE_ROWS_PER_PATH = 1024


class MatrixContractError(RuntimeError):
    """The approved AWGN-022 matrix shape was not met."""


def parse_geometry(experiment_id):
    match = ID_RE.fullmatch(experiment_id)
    if match is None:
        raise MatrixContractError(
            "unexpected AWGN-022 experiment ID: " + experiment_id
        )
    values = match.groupdict()
    geometry = (
        values["nfft"], values["cp"], "0.25", values["outer"],
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
        "nfft": 1024,
        "cp": 64,
        "code_rate": 0.25,
        "outer_spacing": 5,
        "inner_spacing": 5,
        "check_degree": 14,
        "horizon": 0,
        "partial_fft_parts": 4,
        "snr_db": list(range(0, 31, 2)),
        "frames": FRAMES,
        "seed": SEED,
        "capture_seconds": CAPTURE_SECONDS,
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
    if payload.get("payload_bits_per_frame") != 1616:
        raise MatrixContractError("source contract payload capacity differs")
    if payload.get("selection_reasons") != [
        "standard_crc_valid", "crc_rescue", "standard_fallback",
    ]:
        raise MatrixContractError("source contract selection reasons differ")
    if payload.get("optimized_variables") != {
        "profiled_cz": "C+z", "cwz_joint": "C+W+z",
    }:
        raise MatrixContractError("source contract optimized variables differ")
    receiver_source = payload.get("receiver_source", {})
    if not re.fullmatch(r"[0-9a-f]{40}", receiver_source.get("base_commit", "")):
        raise MatrixContractError("source contract base commit is not pinned")
    if not re.fullmatch(
            r"[0-9a-f]{64}",
            receiver_source.get("tracked_source_diff_sha256", "")):
        raise MatrixContractError("source contract receiver diff is not pinned")
    if receiver_source.get("loaded_modules") != [
        "JunaCore.JunaProfiledCzFrame.Modulation",
        "JunaCore.JunaCrcConditionedJointCwzFrame.Modulation",
    ]:
        raise MatrixContractError("source contract loaded modules differ")


if __name__ == "__main__":
    validate_ids()
    print(
        "AWGN-022 MATRIX CONTRACT PASS: 1 configuration, 12 paths, "
        "5 receivers, 0:2:30 dB, first 32 seconds, 32 frames, PFFT=4"
    )
