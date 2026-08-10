#!/usr/bin/env python3
"""Synthetic contract tests for the AWGN-024 result pipeline."""

import csv
import html
import json
import os
import re
import tempfile
import unittest

import build_results as builder
import validate_results as validator


def _write_csv(path, columns, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _frame(channel, hydrophone, receiver, snr, frame):
    snapshot = builder.SNAPSHOT_INDICES[frame - 1]
    start = (snapshot - 1) / 96
    bit_errors = 3 + sorted(builder.EXPECTED_RECEIVERS).index(receiver) + frame
    return {
        "workload_id": (
            f"{channel}:lane{hydrophone}:snr{float(snr)}:seed4:frame{frame}"),
        "snr_db": str(float(snr)), "frame": str(frame),
        "algorithm_id": receiver, "noise_model": "awgn",
        "capture_start_seconds": "0.0", "capture_stop_seconds": "32.0",
        "snapshot_index": str(snapshot), "snapshot_seconds": str(start),
        "replay_support_end_seconds": str(start + 0.99),
        "frame_duration_seconds": "0.99", "frame_samples": "9536",
        "payload_bits": str(builder.PAYLOAD_BITS_PER_FRAME),
        "payload_seed": str(frame + 3), "noise_seed": str(frame + 3),
        "replay_seed": str(frame + 3), "optimizer_seed": "4",
        "bit_errors": str(bit_errors), "success": "false",
        "decode_failure": "false", "partial_fft_parts": "4",
        "partial_fft_bands": "16",
    }


def _protected(frame_row):
    row = {key: frame_row[key] for key in builder.PROTECTED_TRACE_COLUMNS
           if key in frame_row}
    row.update({
        "selected_source": "standard",
        "selection_reason": "standard_fallback",
        "standard_crc_valid": "false", "rescue_executed": "true",
        "rescue_is_gradient": "true", "rescue_crc_valid": "false",
        "gradient_checkpoints": "3", "selected_iteration": "0",
        "optimized_variables": (
            "C+z" if frame_row["algorithm_id"] == "profiled_cz"
            else "C+W+z"),
    })
    return row


def _aggregate(channel, hydrophone, receiver, snr, frames):
    errors = sum(int(row["bit_errors"]) for row in frames)
    successes = sum(row["success"] == "true" for row in frames)
    payload = builder.PAYLOAD_BITS_PER_FRAME * builder.FRAMES
    return {
        "channel": channel, "lane": str(hydrophone),
        "snr_db": str(float(snr)), "algorithm_id": receiver,
        "seed": "4", "frames": "32", "objective": "configuration",
        "noise_model": "awgn", "nfft": "1024", "cp": "64",
        "code_rate": "0.5", "outer_spacing": "5", "inner_spacing": "5",
        "check_degree": "14", "horizon": "0", "partial_fft_parts": "4",
        "partial_fft_bands": "16",
        "payload_bits_per_frame": str(builder.PAYLOAD_BITS_PER_FRAME),
        "successful_frames": str(successes), "psr": str(successes / 32),
        "payload_bits": str(payload), "bit_errors": str(errors),
        "ber": str(errors / payload), "decode_failures": "0",
        "decode_seconds": "0.01", "effective_rate_bps": "0.0",
        "capture_start_seconds": "0.0", "capture_stop_seconds": "32.0",
        "capture_tap_snapshots": "3073", "capture_phase_samples": "614600",
    }


def _write_path_contract(run_dir, experiment_id, channel, hydrophone):
    stem = f"{channel}_hydrophone{hydrophone}"
    values = (
        ("campaign", "AWGN-024"), ("experiment_id", experiment_id),
        ("channel", channel), ("hydrophone", str(hydrophone)),
        ("aggregate_sha256", builder.file_digest(
            os.path.join(run_dir, builder.SOURCE_BASENAME))),
        ("frame_trace_sha256", builder.file_digest(
            os.path.join(run_dir, stem + "_frame_trace.csv"))),
        ("protected_trace_sha256", builder.file_digest(
            os.path.join(run_dir, stem + "_selection_trace.csv"))),
        ("source_contract_sha256", builder.file_digest(
            os.path.join(builder.HERE, "source_contract.json"))),
        ("runner_sha256", builder.file_digest(
            os.path.join(builder.HERE, "run_awgn024.jl"))),
        ("sweep_sha256", builder.file_digest(
            os.path.join(builder.HERE, "awgn024_sweep.jl"))),
        ("aggregate_rows", "80"), ("frame_trace_rows", "2560"),
        ("protected_trace_rows", "1024"), ("capture_seconds", "32.0"),
        ("snapshot_indices", ",".join(
            str(value) for value in builder.SNAPSHOT_INDICES)),
    )
    with open(os.path.join(run_dir, builder.PATH_CONTRACT_BASENAME),
              "w", encoding="utf-8") as handle:
        handle.write("".join(f"{key}={value}\n" for key, value in values))


def _fixture(root):
    experiment = os.path.join(root, builder.EXPECTED_IDS[0])
    results = os.path.join(experiment, "results")
    for channel, hydrophone in builder.EXPECTED_PATHS:
        all_frames, protected, aggregates = [], [], []
        for receiver in sorted(builder.EXPECTED_RECEIVERS):
            for snr in sorted(builder.EXPECTED_SNRS):
                frames = [_frame(channel, hydrophone, receiver, snr, frame)
                          for frame in range(1, builder.FRAMES + 1)]
                all_frames.extend(frames)
                if receiver in builder.PROTECTED_RECEIVERS:
                    protected.extend(_protected(row) for row in frames)
                aggregates.append(_aggregate(
                    channel, hydrophone, receiver, snr, frames))
        stem = f"{channel}_hydrophone{hydrophone}"
        run_dir = os.path.join(results, "runs", stem)
        _write_csv(os.path.join(run_dir, builder.SOURCE_BASENAME),
                   builder.AGGREGATE_COLUMNS, aggregates)
        _write_csv(os.path.join(run_dir, stem + "_frame_trace.csv"),
                   builder.FRAME_TRACE_COLUMNS, all_frames)
        _write_csv(os.path.join(run_dir, stem + "_selection_trace.csv"),
                   builder.PROTECTED_TRACE_COLUMNS, protected)
        _write_path_contract(
            run_dir, os.path.basename(experiment), channel, hydrophone)
    return experiment


def _refresh(experiment, channel="red1", hydrophone=1):
    run_dir = os.path.join(experiment, "results", "runs",
                           f"{channel}_hydrophone{hydrophone}")
    _write_path_contract(
        run_dir, os.path.basename(experiment), channel, hydrophone)


class Awgn024ResultsContract(unittest.TestCase):
    def test_page024_reader_wording_is_exact(self):
        path = os.path.join(builder.AWGN022_REFERENCE_RESULTS,
                            builder.AWGN022_ARTIFACTS["aggregate"])
        with open(path, newline="", encoding="utf-8") as handle:
            page = builder.render_page(list(csv.DictReader(handle)))
        block = re.search(r'<div class="provenance">(.*?)</div>',
                          page, re.DOTALL)
        self.assertIsNotNone(block)
        text = " ".join(html.unescape(
            re.sub(r"<[^>]+>", "", block.group(1))).split())
        self.assertEqual(text, (
            "Channel. Each panel uses one hydrophone from the first thirty-two "
            "seconds of the measured red replay capture. Frames. Each SNR "
            "point uses thirty-two approximately non-overlapping frames whose "
            "complete replay windows fit inside the first thirty-two seconds. "
            "The first sixteen replay windows are unchanged from the "
            "sixteen-second results; sixteen later replay windows extend the "
            "observation to thirty-two seconds. All five receivers use the same "
            "transmitted frames, channel replay, and added AWGN. Noise. Only "
            "independent complex AWGN is added after the measured channel "
            "replay. Its real and imaginary components each receive half of "
            "the target complex-noise power. Receivers. JUNA-Lite is unchanged. "
            "JUNA (C,z) Joint gradient and Juna joint (C,W,z) use the CRC "
            "no-harm implementation. Standard is returned when Standard passes "
            "CRC or the gradient does not produce a CRC-valid output. Reading. "
            "Hollow markers are zero-observed-error points drawn at 0.5/payload "
            "bits; that height is a measurement limit, not a measured BER."))
        self.assertEqual(page.count("AWGN-024: BER versus SNR"), 2)

    def test_retained_awgn022_artifacts_are_pinned(self):
        self.assertEqual(builder.reference_artifact_hashes(
            builder.AWGN022_REFERENCE_RESULTS), builder.AWGN022_REFERENCE_HASHES)

    def test_build_and_validate_synthetic_complete_result(self):
        with tempfile.TemporaryDirectory(prefix="awgn024-results-") as root:
            experiment = _fixture(root)
            builder.build(experiment)
            manifest = validator.validate(experiment)
            self.assertEqual((manifest["row_count"],
                              manifest["frame_trace_row_count"],
                              manifest["protected_trace_row_count"]),
                             (960, 30720, 12288))
            self.assertEqual((manifest["panel_count"], manifest["series_count"]),
                             (12, 60))
            self.assertEqual(manifest["payload_bits_per_frame"], 3248)

    def test_frame_payload_drift_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="awgn024-results-") as root:
            experiment = _fixture(root)
            path = os.path.join(experiment, "results",
                                builder.frame_trace_name("red1", 1))
            with open(path, newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            rows[0]["payload_bits"] = "3247"
            _write_csv(path, builder.FRAME_TRACE_COLUMNS, rows)
            _refresh(experiment)
            with self.assertRaisesRegex(builder.ResultContractError,
                                        "frame geometry differs"):
                builder.collect(experiment)

    def test_no_harm_selection_drift_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="awgn024-results-") as root:
            experiment = _fixture(root)
            path = os.path.join(experiment, "results",
                                builder.protected_trace_name("red1", 1))
            with open(path, newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            rows[0]["selection_reason"] = "crc_rescue"
            _write_csv(path, builder.PROTECTED_TRACE_COLUMNS, rows)
            _refresh(experiment)
            with self.assertRaisesRegex(builder.ResultContractError,
                                        "no-harm selection is inconsistent"):
                builder.collect(experiment)

    def test_reference_hash_drift_is_rejected(self):
        wrong = dict(builder.AWGN022_REFERENCE_HASHES)
        wrong["view"] = "0" * 64
        with self.assertRaisesRegex(builder.ResultContractError,
                                    "AWGN-022 view hash differs"):
            builder._awgn022_reference({}, {},
                                       builder.AWGN022_REFERENCE_RESULTS, wrong)


if __name__ == "__main__":
    unittest.main()
