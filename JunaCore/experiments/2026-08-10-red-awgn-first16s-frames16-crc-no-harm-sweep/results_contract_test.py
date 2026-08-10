#!/usr/bin/env python3
"""Synthetic contract tests for the AWGN-021 result pipeline."""

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


def _frame(channel, hydrophone, receiver, snr, frame, capture_seconds=16.0):
    snapshot = builder.SNAPSHOT_INDICES[frame - 1]
    start = (snapshot - 1) / 96
    bit_errors = 3 + sorted(builder.EXPECTED_RECEIVERS).index(receiver) + frame
    return {
        "workload_id": (
            f"{channel}:lane{hydrophone}:snr{float(snr)}:seed4:frame{frame}"
        ),
        "snr_db": str(float(snr)), "frame": str(frame),
        "algorithm_id": receiver, "noise_model": "awgn",
        "capture_start_seconds": "0.0",
        "capture_stop_seconds": str(capture_seconds),
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


def _aggregate(channel, hydrophone, receiver, snr, frames, frame_count=16):
    selected = frames[:frame_count]
    errors = sum(int(row["bit_errors"]) for row in selected)
    successes = sum(row["success"] == "true" for row in selected)
    payload = 1616 * frame_count
    return {
        "channel": channel, "lane": str(hydrophone),
        "snr_db": str(float(snr)), "algorithm_id": receiver,
        "seed": "4", "frames": str(frame_count),
        "objective": "configuration", "noise_model": "awgn",
        "nfft": "1024", "cp": "64", "code_rate": "0.25",
        "outer_spacing": "5", "inner_spacing": "5",
        "check_degree": "14", "horizon": "0",
        "partial_fft_parts": "4", "partial_fft_bands": "16",
        "payload_bits_per_frame": "1616",
        "successful_frames": str(successes),
        "psr": str(successes / frame_count), "payload_bits": str(payload),
        "bit_errors": str(errors), "ber": str(errors / payload),
        "decode_failures": "0", "decode_seconds": "0.01",
        "effective_rate_bps": "0.0", "capture_start_seconds": "0.0",
        "capture_stop_seconds": str(float(frame_count)),
        "capture_tap_snapshots": "1537" if frame_count == 16 else "769",
        "capture_phase_samples": "307400" if frame_count == 16 else "153800",
    }


def _write_path_contract(run_dir, experiment_id, channel, hydrophone):
    values = (
        ("campaign", "AWGN-021"), ("experiment_id", experiment_id),
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
            os.path.join(builder.HERE, "run_awgn021.jl"))),
        ("sweep_sha256", builder.file_digest(
            os.path.join(builder.HERE, "awgn021_sweep.jl"))),
        ("aggregate_rows", "80"), ("frame_trace_rows", "1280"),
        ("protected_trace_rows", "512"), ("capture_seconds", "16.0"),
        ("snapshot_indices", ",".join(
            str(value) for value in builder.SNAPSHOT_INDICES)),
    )
    with open(os.path.join(run_dir, builder.PATH_CONTRACT_BASENAME),
              "w", encoding="utf-8") as handle:
        handle.write("".join(f"{key}={value}\n" for key, value in values))


def _reference_fixture(root, path_rows):
    results = os.path.join(root, "awgn020-reference", "results")
    aggregates, frame_sources, protected_sources = [], [], []
    for channel, hydrophone in builder.EXPECTED_PATHS:
        run = os.path.join(results, "runs", f"{channel}_hydrophone{hydrophone}")
        frames = []
        protected = []
        for receiver in sorted(builder.EXPECTED_RECEIVERS):
            for snr in sorted(builder.EXPECTED_SNRS):
                rows = [dict(row) for row in path_rows[(channel, hydrophone,
                                                        receiver, snr)][:8]]
                for row in rows:
                    row["capture_stop_seconds"] = "8.0"
                frames.extend(rows)
                if receiver in builder.PROTECTED_RECEIVERS:
                    protected.extend(_protected(row) for row in rows)
                aggregates.append(_aggregate(
                    channel, hydrophone, receiver, snr, rows, 8))
        frame_name = f"{channel}_hydrophone{hydrophone}_frame_trace.csv"
        protected_name = f"{channel}_hydrophone{hydrophone}_selection_trace.csv"
        frame_path = os.path.join(run, frame_name)
        protected_path = os.path.join(run, protected_name)
        _write_csv(frame_path, builder.FRAME_TRACE_COLUMNS, frames)
        _write_csv(protected_path, builder.PROTECTED_TRACE_COLUMNS, protected)
        frame_sources.append({
            "path": f"runs/{channel}_hydrophone{hydrophone}/{frame_name}",
            "rows": 640, "sha256": builder.file_digest(frame_path),
        })
        protected_sources.append({
            "path": f"runs/{channel}_hydrophone{hydrophone}/{protected_name}",
            "rows": 256, "sha256": builder.file_digest(protected_path),
        })
    aggregate_path = os.path.join(
        results, "red_snr_sweep_awgn_first8s_frames8.csv")
    _write_csv(aggregate_path, builder.AGGREGATE_COLUMNS, aggregates)
    manifest = {
        "decision": "AWGN-020",
        "experiment_id": builder.AWGN020_EXPERIMENT_ID,
        "row_count": 960, "frame_trace_row_count": 7680,
        "protected_trace_row_count": 3072,
        "frame_trace_sources": frame_sources,
        "protected_trace_sources": protected_sources,
    }
    with open(os.path.join(results, "results_manifest.json"),
              "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, sort_keys=True)
    with open(os.path.join(results, "results_view.html"),
              "w", encoding="utf-8") as handle:
        handle.write("<title>AWGN-020: BER versus SNR</title>\n")
    return results


def _fixture(root):
    experiment = os.path.join(root, builder.EXPECTED_IDS[0])
    results = os.path.join(experiment, "results")
    path_rows = {}
    for channel, hydrophone in builder.EXPECTED_PATHS:
        all_frames, protected, aggregates = [], [], []
        for receiver in sorted(builder.EXPECTED_RECEIVERS):
            for snr in sorted(builder.EXPECTED_SNRS):
                frames = [_frame(channel, hydrophone, receiver, snr, frame)
                          for frame in range(1, 17)]
                path_rows[(channel, hydrophone, receiver, snr)] = frames
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
    return experiment, _reference_fixture(root, path_rows)


def _refresh_path_contract(experiment, channel="red1", hydrophone=1):
    run_dir = os.path.join(
        experiment, "results", "runs", f"{channel}_hydrophone{hydrophone}")
    _write_path_contract(
        run_dir, os.path.basename(experiment), channel, hydrophone)


class Awgn021ResultsContract(unittest.TestCase):
    def test_page021a_reader_wording_is_exact(self):
        path = os.path.join(
            builder.AWGN020_REFERENCE_RESULTS,
            builder.AWGN020_ARTIFACTS["aggregate"],
        )
        with open(path, newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        page = builder.render_page(rows)
        block = re.search(
            r'<div class="provenance">(.*?)</div>', page, re.DOTALL)
        self.assertIsNotNone(block)
        text = " ".join(html.unescape(
            re.sub(r"<[^>]+>", "", block.group(1))).split())
        self.assertEqual(text, (
            "Channel. Each panel uses one hydrophone from the first sixteen "
            "seconds of the measured red replay capture. Frames. Each SNR "
            "point uses sixteen approximately non-overlapping frames whose "
            "complete replay windows fit inside the first sixteen seconds. "
            "The first eight replay windows are unchanged from the "
            "eight-second results; eight later replay windows extend the "
            "observation to sixteen seconds. All five receivers use the same "
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
        self.assertEqual(page.count("AWGN-021: BER versus SNR"), 2)

    def test_retained_awgn020_artifacts_and_trace_evidence_are_pinned(self):
        results = builder.AWGN020_REFERENCE_RESULTS
        self.assertEqual(
            builder.reference_artifact_hashes(results),
            builder.AWGN020_REFERENCE_HASHES,
        )
        with open(os.path.join(results, "results_manifest.json"),
                  encoding="utf-8") as handle:
            manifest = json.load(handle)
        for field, rows in (("frame_trace_sources", 640),
                            ("protected_trace_sources", 256)):
            records = manifest[field]
            self.assertEqual(len(records), 12)
            for record in records:
                self.assertEqual(record["rows"], rows)
                self.assertEqual(
                    builder.file_digest(os.path.join(results, record["path"])),
                    record["sha256"],
                )

    def test_static_source_contract_matches_approved_campaign(self):
        with open(os.path.join(builder.HERE, "source_contract.json"),
                  encoding="utf-8") as handle:
            builder.matrix_contract.validate_source_contract(json.load(handle))

    def test_build_and_validate_synthetic_complete_result(self):
        with tempfile.TemporaryDirectory(prefix="awgn021-results-") as root:
            experiment, reference = _fixture(root)
            builder.build(experiment, reference_results=reference,
                          reference_hashes=None)
            validator.validate(experiment, reference_results=reference,
                               reference_hashes=None)
            with open(os.path.join(
                    experiment, "results", "results_manifest.json"),
                    encoding="utf-8") as handle:
                manifest = json.load(handle)
            self.assertEqual(manifest["decision"], "AWGN-021")
            self.assertEqual(manifest["row_count"], 960)
            self.assertEqual(manifest["frame_trace_row_count"], 15360)
            self.assertEqual(manifest["protected_trace_row_count"], 6144)
            self.assertEqual(manifest["panel_count"], 12)
            self.assertEqual(manifest["series_count"], 60)
            self.assertEqual(
                manifest["awgn020_reference"]["matched_frame_rows"], 7680)
            self.assertEqual(
                manifest["awgn020_reference"]["matched_protected_rows"], 3072)

    def test_first_eight_replay_drift_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="awgn021-results-") as root:
            experiment, reference = _fixture(root)
            path = os.path.join(
                experiment, "results", builder.frame_trace_name("red1", 1))
            with open(path, newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            for row in rows:
                if float(row["snr_db"]) == 0.0 and int(row["frame"]) == 1:
                    row["snapshot_seconds"] = "0.001"
            _write_csv(path, builder.FRAME_TRACE_COLUMNS, rows)
            _refresh_path_contract(experiment)
            with self.assertRaisesRegex(
                    builder.ResultContractError, "AWGN-020 first-eight frame"):
                builder.collect(experiment, reference_results=reference,
                                reference_hashes=None)

    def test_first_eight_protected_selection_drift_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="awgn021-results-") as root:
            experiment, reference = _fixture(root)
            path = os.path.join(
                experiment, "results",
                builder.protected_trace_name("red1", 1))
            with open(path, newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            rows[0]["selected_iteration"] = "1"
            _write_csv(path, builder.PROTECTED_TRACE_COLUMNS, rows)
            _refresh_path_contract(experiment)
            with self.assertRaisesRegex(
                    builder.ResultContractError, "AWGN-020 protected"):
                builder.collect(experiment, reference_results=reference,
                                reference_hashes=None)

    def test_reference_artifact_drift_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="awgn021-results-") as root:
            experiment, reference = _fixture(root)
            hashes = builder.reference_artifact_hashes(reference)
            with open(os.path.join(reference, "results_view.html"),
                      "a", encoding="utf-8") as handle:
                handle.write("drift")
            with self.assertRaisesRegex(
                    builder.ResultContractError, "AWGN-020 view hash"):
                builder.collect(experiment, reference_results=reference,
                                reference_hashes=hashes)

    def test_missing_all_frame_trace_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="awgn021-results-") as root:
            experiment, reference = _fixture(root)
            os.remove(os.path.join(
                experiment, "results", builder.frame_trace_name("red1", 1)))
            with self.assertRaisesRegex(builder.ResultContractError,
                                        "missing source"):
                builder.collect(experiment, reference_results=reference,
                                reference_hashes=None)


if __name__ == "__main__":
    unittest.main()
