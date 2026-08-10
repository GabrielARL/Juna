#!/usr/bin/env python3
"""Synthetic contract tests for the AWGN-020 result pipeline."""

import csv
import json
import os
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
        "workload_id": f"{channel}:lane{hydrophone}:snr{float(snr)}:seed4:frame{frame}",
        "snr_db": str(float(snr)), "frame": str(frame),
        "algorithm_id": receiver, "noise_model": "awgn",
        "capture_start_seconds": "0.0", "capture_stop_seconds": "8.0",
        "snapshot_index": str(snapshot), "snapshot_seconds": str(start),
        "replay_support_end_seconds": str(start + 0.99),
        "frame_duration_seconds": "0.99", "frame_samples": "9536",
        "payload_bits": "1616", "payload_seed": str(frame + 3),
        "noise_seed": str(frame + 3), "replay_seed": str(frame + 3),
        "optimizer_seed": "4", "bit_errors": str(bit_errors),
        "success": "false", "decode_failure": "false",
        "partial_fft_parts": "4", "partial_fft_bands": "16",
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
            "C+z" if frame_row["algorithm_id"] == "profiled_cz" else "C+W+z"
        ),
    })
    return row


def _aggregate(channel, hydrophone, receiver, snr, frames, frame_count=8):
    selected = frames[:frame_count]
    errors = sum(int(row["bit_errors"]) for row in selected)
    successes = sum(row["success"] == "true" for row in selected)
    payload = 1616 * frame_count
    return {
        "channel": channel, "lane": str(hydrophone), "snr_db": str(float(snr)),
        "algorithm_id": receiver, "seed": "4", "frames": str(frame_count),
        "objective": "configuration", "noise_model": "awgn", "nfft": "1024",
        "cp": "64", "code_rate": "0.25", "outer_spacing": "5",
        "inner_spacing": "5", "check_degree": "14", "horizon": "0",
        "partial_fft_parts": "4", "partial_fft_bands": "16",
        "payload_bits_per_frame": "1616", "successful_frames": str(successes),
        "psr": str(successes / frame_count), "payload_bits": str(payload),
        "bit_errors": str(errors), "ber": str(errors / payload),
        "decode_failures": "0", "decode_seconds": "0.01",
        "effective_rate_bps": "0.0", "capture_start_seconds": "0.0",
        "capture_stop_seconds": str(float(frame_count)),
        "capture_tap_snapshots": "769" if frame_count == 8 else "385",
        "capture_phase_samples": "153800" if frame_count == 8 else "77000",
    }


def _write_path_contract(run_dir, experiment_id, channel, hydrophone):
    values = (
        ("campaign", "AWGN-020"), ("experiment_id", experiment_id),
        ("channel", channel), ("hydrophone", str(hydrophone)),
        ("aggregate_sha256", builder.file_digest(os.path.join(run_dir, builder.SOURCE_BASENAME))),
        ("frame_trace_sha256", builder.file_digest(os.path.join(run_dir, f"{channel}_hydrophone{hydrophone}_frame_trace.csv"))),
        ("protected_trace_sha256", builder.file_digest(os.path.join(run_dir, f"{channel}_hydrophone{hydrophone}_selection_trace.csv"))),
        ("source_contract_sha256", builder.file_digest(os.path.join(builder.HERE, "source_contract.json"))),
        ("runner_sha256", builder.file_digest(os.path.join(builder.HERE, "run_awgn020.jl"))),
        ("sweep_sha256", builder.file_digest(os.path.join(builder.HERE, "awgn020_sweep.jl"))),
        ("aggregate_rows", "80"), ("frame_trace_rows", "640"),
        ("protected_trace_rows", "256"),
        ("capture_seconds", "8.0"),
        ("snapshot_indices", "1,96,190,285,385,480,574,669"),
    )
    with open(os.path.join(run_dir, builder.PATH_CONTRACT_BASENAME), "w", encoding="utf-8") as handle:
        handle.write("".join(f"{key}={value}\n" for key, value in values))


def _fixture(root):
    experiment = os.path.join(root, builder.EXPECTED_IDS[0])
    results = os.path.join(experiment, "results")
    references = []
    for channel, hydrophone in builder.EXPECTED_PATHS:
        all_frames, protected, aggregates = [], [], []
        for receiver in sorted(builder.EXPECTED_RECEIVERS):
            for snr in sorted(builder.EXPECTED_SNRS):
                frames = [_frame(channel, hydrophone, receiver, snr, frame)
                          for frame in range(1, 9)]
                all_frames.extend(frames)
                if receiver in builder.PROTECTED_RECEIVERS:
                    protected.extend(_protected(row) for row in frames)
                aggregates.append(_aggregate(channel, hydrophone, receiver, snr, frames))
                references.append(_aggregate(channel, hydrophone, receiver, snr, frames, 4))
        run_dir = os.path.join(results, "runs", f"{channel}_hydrophone{hydrophone}")
        _write_csv(os.path.join(run_dir, builder.SOURCE_BASENAME), builder.AGGREGATE_COLUMNS, aggregates)
        _write_csv(os.path.join(run_dir, f"{channel}_hydrophone{hydrophone}_frame_trace.csv"), builder.FRAME_TRACE_COLUMNS, all_frames)
        _write_csv(os.path.join(run_dir, f"{channel}_hydrophone{hydrophone}_selection_trace.csv"), builder.PROTECTED_TRACE_COLUMNS, protected)
        _write_path_contract(run_dir, os.path.basename(experiment), channel, hydrophone)
    reference = os.path.join(root, "first4.csv")
    _write_csv(reference, builder.AGGREGATE_COLUMNS, references)
    return experiment, reference


class Awgn020ResultsContract(unittest.TestCase):
    def test_static_source_contract_matches_approved_campaign(self):
        with open(os.path.join(builder.HERE, "source_contract.json"), encoding="utf-8") as handle:
            builder.matrix_contract.validate_source_contract(json.load(handle))

    def test_build_and_validate_synthetic_complete_result(self):
        with tempfile.TemporaryDirectory(prefix="awgn020-results-") as root:
            experiment, reference = _fixture(root)
            builder.build(experiment, reference_csv=reference, reference_sha256=None)
            validator.validate(experiment, reference_csv=reference, reference_sha256=None)
            with open(os.path.join(experiment, "results", "results_manifest.json"), encoding="utf-8") as handle:
                manifest = json.load(handle)
            self.assertEqual(manifest["decision"], "AWGN-020")
            self.assertEqual(manifest["row_count"], 960)
            self.assertEqual(manifest["frame_trace_row_count"], 7680)
            self.assertEqual(manifest["protected_trace_row_count"], 3072)
            self.assertEqual(manifest["panel_count"], 12)
            self.assertEqual(manifest["series_count"], 60)
            self.assertEqual(len(manifest["path_contracts"]), 12)

    def test_first_four_reference_drift_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="awgn020-results-") as root:
            experiment, reference = _fixture(root)
            with open(reference, newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            rows[0]["bit_errors"] = str(int(rows[0]["bit_errors"]) + 1)
            _write_csv(reference, builder.AGGREGATE_COLUMNS, rows)
            with self.assertRaisesRegex(builder.ResultContractError, "first-four"):
                builder.collect(experiment, reference_csv=reference, reference_sha256=None)

    def test_missing_all_frame_trace_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="awgn020-results-") as root:
            experiment, reference = _fixture(root)
            os.remove(os.path.join(experiment, "results", builder.frame_trace_name("red1", 1)))
            with self.assertRaisesRegex(builder.ResultContractError, "missing source"):
                builder.collect(experiment, reference_csv=reference, reference_sha256=None)


if __name__ == "__main__":
    unittest.main()
