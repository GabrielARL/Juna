#!/usr/bin/env python3
"""Synthetic contract tests for the AWGN-027 result pipeline."""

import copy
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
    replay_tail = 47.7734375 - (4500 - 1) / 96
    bit_errors = 3 + sorted(builder.EXPECTED_RECEIVERS).index(receiver) + frame
    return {
        "workload_id": (
            f"{channel}:lane{hydrophone}:snr{float(snr)}:seed4:frame{frame}"
        ),
        "snr_db": str(float(snr)), "frame": str(frame),
        "algorithm_id": receiver, "noise_model": "awgn",
        "capture_start_seconds": "0.0",
        "capture_stop_seconds": str(builder.CAPTURE_SECONDS),
        "snapshot_index": str(snapshot), "snapshot_seconds": str(start),
        "replay_support_end_seconds": str(start + replay_tail),
        "frame_duration_seconds": str(8320 / 9600), "frame_samples": "8320",
        "payload_bits": "3296", "payload_seed": str(frame + 3),
        "noise_seed": str(frame + 3), "replay_seed": str(frame + 3),
        "optimizer_seed": "4", "bit_errors": str(bit_errors),
        "success": "false", "decode_failure": "false",
        "partial_fft_parts": "4", "partial_fft_bands": "16",
    }


def _protected(frame_row):
    row = {
        key: frame_row[key]
        for key in builder.PROTECTED_TRACE_COLUMNS if key in frame_row
    }
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


def _aggregate(channel, hydrophone, receiver, snr, frames):
    errors = sum(int(row["bit_errors"]) for row in frames)
    successes = sum(row["success"] == "true" for row in frames)
    return {
        "channel": channel, "lane": str(hydrophone),
        "snr_db": str(float(snr)), "algorithm_id": receiver,
        "seed": "4", "frames": "47", "objective": "configuration",
        "noise_model": "awgn", "nfft": "2048", "cp": "64",
        "code_rate": "0.5", "outer_spacing": "10",
        "inner_spacing": "10", "check_degree": "14", "horizon": "0",
        "partial_fft_parts": "4", "partial_fft_bands": "16",
        "payload_bits_per_frame": "3296",
        "successful_frames": str(successes), "psr": str(successes / 47),
        "payload_bits": "154912", "bit_errors": str(errors),
        "ber": str(errors / 154912), "decode_failures": "0",
        "decode_seconds": "0.01", "effective_rate_bps": "0.0",
        "capture_start_seconds": "0.0", "capture_stop_seconds": "47.78125",
        "capture_tap_snapshots": "4588", "capture_phase_samples": "917600",
    }


def _write_path_contract(run_dir, experiment_id, channel, hydrophone):
    values = (
        ("campaign", "AWGN-027"), ("experiment_id", experiment_id),
        ("channel", channel), ("hydrophone", str(hydrophone)),
        ("aggregate_sha256", builder.file_digest(
            os.path.join(run_dir, builder.SOURCE_BASENAME))),
        ("frame_trace_sha256", builder.file_digest(os.path.join(
            run_dir, f"{channel}_hydrophone{hydrophone}_frame_trace.csv"))),
        ("protected_trace_sha256", builder.file_digest(os.path.join(
            run_dir, f"{channel}_hydrophone{hydrophone}_selection_trace.csv"))),
        ("source_contract_sha256", builder.file_digest(
            os.path.join(builder.HERE, "source_contract.json"))),
        ("runner_sha256", builder.file_digest(
            os.path.join(builder.HERE, "run_awgn027.jl"))),
        ("sweep_sha256", builder.file_digest(
            os.path.join(builder.HERE, "awgn027_sweep.jl"))),
        ("aggregate_rows", "80"), ("frame_trace_rows", "3760"),
        ("protected_trace_rows", "1504"),
        ("capture_seconds", "47.78125"),
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
                frames = [
                    _frame(channel, hydrophone, receiver, snr, frame)
                    for frame in range(1, 48)
                ]
                all_frames.extend(frames)
                if receiver in builder.PROTECTED_RECEIVERS:
                    protected.extend(_protected(row) for row in frames)
                aggregates.append(_aggregate(
                    channel, hydrophone, receiver, snr, frames))
        run_dir = os.path.join(
            results, "runs", f"{channel}_hydrophone{hydrophone}")
        _write_csv(os.path.join(run_dir, builder.SOURCE_BASENAME),
                   builder.AGGREGATE_COLUMNS, aggregates)
        _write_csv(os.path.join(
            run_dir, f"{channel}_hydrophone{hydrophone}_frame_trace.csv"),
            builder.FRAME_TRACE_COLUMNS, all_frames)
        _write_csv(os.path.join(
            run_dir, f"{channel}_hydrophone{hydrophone}_selection_trace.csv"),
            builder.PROTECTED_TRACE_COLUMNS, protected)
        _write_path_contract(
            run_dir, os.path.basename(experiment), channel, hydrophone)
    return experiment


def _refresh_path_contract(experiment, channel="red1", hydrophone=1):
    run_dir = os.path.join(
        experiment, "results", "runs", f"{channel}_hydrophone{hydrophone}")
    _write_path_contract(
        run_dir, os.path.basename(experiment), channel, hydrophone)


class Awgn027ResultsContract(unittest.TestCase):
    def test_page_reader_wording_is_exact(self):
        with tempfile.TemporaryDirectory(prefix="awgn027-results-") as root:
            experiment = _fixture(root)
            _, _, _, _, rows, *_ = builder.collect(experiment)
            page = builder.render_page(rows)
        block = re.search(
            r'<div class="provenance">(.*?)</div>', page, re.DOTALL)
        self.assertIsNotNone(block)
        text = " ".join(html.unescape(
            re.sub(r"<[^>]+>", "", block.group(1))).split())
        self.assertEqual(text, (
            "Channel. Each panel uses one hydrophone from the complete measured "
            "red replay capture. Frames. Each SNR point uses forty-seven "
            "approximately non-overlapping frames whose complete replay windows "
            "fit inside the measured capture. All five receivers use the same "
            "transmitted frames, channel replay, and added AWGN. Noise. Only "
            "independent complex AWGN is added after the measured channel "
            "replay. Its real and imaginary components each receive half of "
            "the target complex-noise power. Receivers. JUNA-Lite is "
            "unchanged. JUNA (C,z) Joint gradient and Juna joint (C,W,z) use "
            "the CRC no-harm implementation. Standard is returned when "
            "Standard passes CRC or the gradient does not produce a "
            "CRC-valid output. Reading. Hollow markers are "
            "zero-observed-error points drawn at 0.5/payload bits; that "
            "height is a measurement limit, not a measured BER."
        ))
        self.assertEqual(page.count("AWGN-027: BER versus SNR"), 2)
        self.assertEqual(page.count("pilots=10/10"), 12)

    def test_static_source_contract_matches_approved_campaign(self):
        with open(os.path.join(builder.HERE, "source_contract.json"),
                  encoding="utf-8") as handle:
            builder.matrix_contract.validate_source_contract(json.load(handle))

    def test_schedule_seed_drift_is_rejected(self):
        with open(os.path.join(builder.HERE, "source_contract.json"),
                  encoding="utf-8") as handle:
            payload = copy.deepcopy(json.load(handle))
        payload["schedule_provenance"]["payload_seed_range"] = [5, 50]
        with self.assertRaisesRegex(
                builder.matrix_contract.MatrixContractError,
                "schedule provenance differs"):
            builder.matrix_contract.validate_source_contract(payload)

    def test_schedule_is_pinned_without_outcome_equality(self):
        with open(os.path.join(builder.HERE, "source_contract.json"),
                  encoding="utf-8") as handle:
            schedule = json.load(handle)["schedule_provenance"]
        self.assertEqual(schedule["schedule_source"], "AWGN-023B")
        self.assertFalse(schedule["outcome_equality_required"])
        self.assertFalse(schedule["snapshot_schedule_equality_required"])
        with open(os.path.join(builder.HERE, "build_results.py"),
                  encoding="utf-8") as handle:
            source = handle.read()
        self.assertNotIn("_compare_reference_rows", source)
        self.assertNotIn("REFERENCE_RESULTS", source)

    def test_build_and_validate_synthetic_complete_result(self):
        with tempfile.TemporaryDirectory(prefix="awgn027-results-") as root:
            experiment = _fixture(root)
            builder.build(experiment)
            validator.validate(experiment)
            with open(os.path.join(
                    experiment, "results", "results_manifest.json"),
                    encoding="utf-8") as handle:
                manifest = json.load(handle)
            self.assertEqual(manifest["decision"], "AWGN-027")
            self.assertEqual(manifest["row_count"], 960)
            self.assertEqual(manifest["frame_trace_row_count"], 45120)
            self.assertEqual(manifest["protected_trace_row_count"], 18048)
            self.assertEqual(manifest["panel_count"], 12)
            self.assertEqual(manifest["series_count"], 60)
            self.assertEqual(manifest["payload_bits_per_frame"], 3296)
            self.assertEqual(manifest["payload_bits_per_point"], 154912)
            self.assertFalse(
                manifest["schedule_provenance"]["outcome_equality_required"])
            self.assertFalse(manifest["schedule_provenance"][
                "snapshot_schedule_equality_required"])

    def test_payload_drift_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="awgn027-results-") as root:
            experiment = _fixture(root)
            path = os.path.join(
                experiment, "results", builder.source_name("red1", 1))
            with open(path, newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            rows[0]["payload_bits_per_frame"] = "1616"
            _write_csv(path, builder.AGGREGATE_COLUMNS, rows)
            _refresh_path_contract(experiment)
            with self.assertRaisesRegex(
                    builder.ResultContractError, "payload geometry differs"):
                builder.collect(experiment)

    def test_missing_all_frame_trace_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="awgn027-results-") as root:
            experiment = _fixture(root)
            os.remove(os.path.join(
                experiment, "results", builder.frame_trace_name("red1", 1)))
            with self.assertRaisesRegex(builder.ResultContractError,
                                        "missing source"):
                builder.collect(experiment)

    def test_build_is_deterministic(self):
        with tempfile.TemporaryDirectory(prefix="awgn027-results-") as root:
            experiment = _fixture(root)
            builder.build(experiment)
            results = os.path.join(experiment, "results")
            names = (builder.OUTPUT_BASENAME, "results_manifest.json",
                     "results_view.html")
            first = {name: builder.file_digest(os.path.join(results, name))
                     for name in names}
            builder.build(experiment)
            second = {name: builder.file_digest(os.path.join(results, name))
                      for name in names}
            self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
