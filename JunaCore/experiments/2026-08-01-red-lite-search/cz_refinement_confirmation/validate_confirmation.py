#!/usr/bin/env python3
"""Validate the durable C,z refinement confirmation artifacts."""

from __future__ import annotations

import collections
import csv
import hashlib
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
CONFIRMATION_CSV = HERE / "red_cz_refinement_confirmation_20db_seeds6to7.csv"
RANKING_JSON = HERE / "confirmed_receiver_ranking.json"
MANIFEST_JSON = HERE / "confirmation_manifest.json"
ANALYZER = HERE / "analyze_confirmation.py"
THREE_ARM_CSV = (
    EXPERIMENT / "results" / "red_config_finalists_20db_seeds6to7.csv"
)
PARTIAL_FFT_CSV = (
    EXPERIMENT
    / "results_partial_fft"
    / "red_config_finalists_20db_seeds6to7.csv"
)

RECEIVER_IDS = ("ofdm_fec", "lite", "pfft", "cz_refinement", "joint_cwz")
CONFIRMATION_IDS = ("lite", "cz_refinement", "joint_cwz")
CONFIGURATION_FIELDS = (
    "nfft",
    "cp",
    "code_rate",
    "outer_spacing",
    "inner_spacing",
    "check_degree",
    "horizon",
)
CONFIRMATION_FIELDS = (
    "channel",
    "lane",
    "seed",
    "frames",
    "algorithm_id",
    *CONFIGURATION_FIELDS,
    "frame_blocks",
    "payload_bits_per_frame",
    "successful_frames",
    "psr",
    "payload_bits",
    "bit_errors",
    "ber",
    "decode_failures",
    "decode_seconds",
    "effective_rate_bps",
    "refinement_selected_frames",
    "joint_cwz_accepted_steps",
    "joint_cwz_rejected_steps",
    "selection_reasons",
)
OUTCOME_FIELDS = (
    "frames",
    "frame_blocks",
    "payload_bits_per_frame",
    "successful_frames",
    "psr",
    "payload_bits",
    "bit_errors",
    "ber",
    "decode_failures",
    "effective_rate_bps",
)
EXPECTED_CONFIRMATION_SHA256 = (
    "812925fba6c8166df360aade9d644a1a8d0b8028637314c4e7c49c970133bc12"
)
EXPECTED_RECOVERED_SHA256 = (
    "a4667812072ece9e96f9c61c8e46bbaa1619ecbc87b5a183d777eb52b6526298"
)
EXPECTED_HARNESS_SHA256 = (
    "38f9823ca6bb82f9767055f285f7fb9e2e88ba9728ac5d9b7dca94c78bd0a99a"
)
EXPECTED_REPLAY_SHA256 = (
    "e4e00b84e96abc863c42d76a8494c3cefc9d81cf3dbb2354be08ceba3cfae6f3"
)
EXPECTED_PACKAGE_WORKTREE_COMMIT = "58c9f6174239e96ba564e5fb0d829a1e71621324"
EXPECTED_PRIMARY_HARNESS_COMMIT = "8a24c76d7bfe04e73c545383e4ebde38943eabf1"
AUDIT_OBSERVATION_QUALIFICATION = (
    "observed_during_this_audit_not_recorded_by_historical_run"
)
EXPECTED_POOLED = {
    "lite": (96, 5760, 892, 19_941_240, 3_000_933, 0, 0, 0),
    "cz_refinement": (96, 5760, 905, 19_941_240, 3_000_442, 14, 0, 0),
    "joint_cwz": (96, 5760, 909, 19_941_240, 3_000_102, 17, 38_952, 0),
}
EXPECTED_REASONS = {
    "lite": {},
    "cz_refinement": {
        "crc_fallback": 4855,
        "lite_crc_valid_skip": 891,
        "crc_rescue": 14,
    },
    "joint_cwz": {
        "crc_fallback": 4852,
        "lite_crc_valid_skip": 891,
        "crc_rescue": 17,
    },
}
EXPECTED_WINNER_COUNTS = {
    "ofdm_fec": 9,
    "lite": 1,
    "pfft": 0,
    "cz_refinement": 0,
    "joint_cwz": 2,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_csv(path: Path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return tuple(reader.fieldnames or ()), list(reader)


def configuration_key(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(row[field] for field in CONFIGURATION_FIELDS)


def row_key(row: dict[str, str]) -> tuple[object, ...]:
    return (
        row["channel"],
        int(row["lane"]),
        row["algorithm_id"],
        *configuration_key(row),
        int(row["seed"]),
    )


def parse_reasons(text: str) -> collections.Counter[str]:
    reasons: collections.Counter[str] = collections.Counter()
    for item in filter(None, text.split(";")):
        name, separator, count = item.partition(":")
        if not separator:
            raise ValueError(f"invalid selection reason {item!r}")
        reasons[name] += int(count)
    return reasons


def typed_configuration(values: tuple[str, ...]) -> dict[str, object]:
    return {
        "nfft": int(values[0]),
        "cp": int(values[1]),
        "code_rate": float(values[2]),
        "outer_spacing": int(values[3]),
        "inner_spacing": int(values[4]),
        "check_degree": int(values[5]),
        "horizon": int(values[6]),
    }


def ranking_payload(
    confirmation_rows: list[dict[str, str]],
    three_arm_rows: list[dict[str, str]],
    partial_fft_rows: list[dict[str, str]],
) -> dict[str, object]:
    # Timing ties must use the Lite measurements made in the same call as the
    # two C,z refinement forms. The retained three-arm CSV supplies OFDM+FEC;
    # the separate Partial-FFT confirmation supplies its own receiver rows.
    rows: list[dict[str, str]] = [
        {**row, "algorithm_id": "ofdm_fec"}
        for row in three_arm_rows
        if row["algorithm_id"] == "standard"
    ]
    rows.extend(partial_fft_rows)
    rows.extend(confirmation_rows)

    groups: dict[
        tuple[str, int, str, tuple[str, ...]], list[dict[str, str]]
    ] = collections.defaultdict(list)
    for row in rows:
        key = (
            row["channel"],
            int(row["lane"]),
            row["algorithm_id"],
            configuration_key(row),
        )
        groups[key].append(row)

    best_by_receiver: dict[tuple[str, int, str], dict[str, object]] = {}
    for (channel, lane, receiver_id, configuration), group in groups.items():
        if {int(row["seed"]) for row in group} != {6, 7} or len(group) != 2:
            continue
        if any(int(row["decode_failures"]) != 0 for row in group):
            continue
        payload_bits = sum(int(row["payload_bits"]) for row in group)
        result = {
            "receiver_id": receiver_id,
            "configuration": typed_configuration(configuration),
            "mean_effective_rate_bps": sum(
                float(row["effective_rate_bps"]) for row in group
            )
            / 2,
            "minimum_effective_rate_bps": min(
                float(row["effective_rate_bps"]) for row in group
            ),
            "mean_packet_success_rate": sum(float(row["psr"]) for row in group)
            / 2,
            "pooled_ber": sum(int(row["bit_errors"]) for row in group)
            / payload_bits,
            "mean_decode_seconds_per_frame": sum(
                float(row["decode_seconds"]) for row in group
            )
            / 2,
        }
        key = (channel, lane, receiver_id)
        order = (
            result["mean_effective_rate_bps"],
            -result["pooled_ber"],
            -result["mean_decode_seconds_per_frame"],
        )
        current = best_by_receiver.get(key)
        if current is None:
            best_by_receiver[key] = result
        else:
            current_order = (
                current["mean_effective_rate_bps"],
                -current["pooled_ber"],
                -current["mean_decode_seconds_per_frame"],
            )
            if order > current_order:
                best_by_receiver[key] = result

    winner_counts = {receiver_id: 0 for receiver_id in RECEIVER_IDS}
    paths = []
    path_keys = sorted({(key[0], key[1]) for key in best_by_receiver})
    for channel, lane in path_keys:
        receiver_results = [
            best_by_receiver[(channel, lane, receiver_id)]
            for receiver_id in RECEIVER_IDS
        ]
        ranked = sorted(
            receiver_results,
            key=lambda result: (
                result["mean_effective_rate_bps"],
                -result["pooled_ber"],
                -result["mean_decode_seconds_per_frame"],
            ),
            reverse=True,
        )
        maximum_rate = ranked[0]["mean_effective_rate_bps"]
        rate_tie_ids = [
            result["receiver_id"]
            for result in ranked
            if result["mean_effective_rate_bps"] == maximum_rate
        ]
        winner_id = ranked[0]["receiver_id"]
        winner_counts[winner_id] += 1
        paths.append(
            {
                "channel": channel,
                "hydrophone": lane,
                "winner_id": winner_id,
                "rate_tie_ids": rate_tie_ids,
                "receiver_results": receiver_results,
            }
        )

    return {
        "schema_version": 1,
        "result_scope": "60-frame confirmation",
        "receiver_ids": list(RECEIVER_IDS),
        "ranking_rule": {
            "required_confirmation_seeds": [6, 7],
            "required_decode_failures": 0,
            "order": [
                "mean_effective_rate_bps_descending",
                "pooled_ber_ascending",
                "mean_decode_seconds_per_frame_ascending",
            ],
            "lite_timing_source": "in_run_confirmation",
        },
        "winner_counts": winner_counts,
        "paths": paths,
    }


def main() -> int:
    problems: list[str] = []
    required = (CONFIRMATION_CSV, RANKING_JSON, MANIFEST_JSON, ANALYZER)
    missing = [path.name for path in required if not path.is_file()]
    if missing:
        print("confirmation artifact validation FAILED")
        for name in missing:
            print(f"  - missing {name}")
        return 1

    if sha256(CONFIRMATION_CSV) != EXPECTED_CONFIRMATION_SHA256:
        problems.append("confirmation CSV differs from the normalized recovered data")

    fields, rows = load_csv(CONFIRMATION_CSV)
    if fields != CONFIRMATION_FIELDS:
        problems.append("confirmation CSV columns differ from the current schema")
    if len(rows) != 288:
        problems.append(f"confirmation CSV has {len(rows)} rows, expected 288")

    counts = collections.Counter(row["algorithm_id"] for row in rows)
    expected_counts = collections.Counter({receiver_id: 96 for receiver_id in CONFIRMATION_IDS})
    if counts != expected_counts:
        problems.append(f"confirmation receiver counts differ: {dict(counts)}")
    keys = [row_key(row) for row in rows]
    if len(keys) != len(set(keys)):
        problems.append("confirmation CSV has duplicate receiver/configuration/seed rows")

    for row in rows:
        if int(row["seed"]) not in (6, 7):
            problems.append("confirmation CSV contains a seed outside 6 and 7")
            break
        if int(row["frames"]) != 60:
            problems.append("confirmation CSV contains a row other than 60 frames")
            break
        if int(row["decode_failures"]) != 0:
            problems.append("confirmation CSV contains a decode failure")
            break

    configurations: dict[tuple[str, int, str], set[tuple[str, ...]]] = (
        collections.defaultdict(set)
    )
    for row in rows:
        configurations[(row["channel"], int(row["lane"]), row["algorithm_id"])].add(
            configuration_key(row)
        )
    for channel in ("red1", "red2", "red3", "red4"):
        for lane in (1, 2, 3):
            sets = [configurations[(channel, lane, receiver_id)] for receiver_id in CONFIRMATION_IDS]
            if any(len(values) != 4 for values in sets) or not all(
                values == sets[0] for values in sets[1:]
            ):
                problems.append(
                    f"{channel} hydrophone {lane} does not share four confirmation configurations"
                )

    pooled: dict[str, tuple[int, ...]] = {}
    pooled_reasons: dict[str, collections.Counter[str]] = {}
    for receiver_id in CONFIRMATION_IDS:
        receiver_rows = [row for row in rows if row["algorithm_id"] == receiver_id]
        pooled[receiver_id] = (
            len(receiver_rows),
            sum(int(row["frames"]) for row in receiver_rows),
            sum(int(row["successful_frames"]) for row in receiver_rows),
            sum(int(row["payload_bits"]) for row in receiver_rows),
            sum(int(row["bit_errors"]) for row in receiver_rows),
            sum(int(row["refinement_selected_frames"]) for row in receiver_rows),
            sum(int(row["joint_cwz_accepted_steps"]) for row in receiver_rows),
            sum(int(row["joint_cwz_rejected_steps"]) for row in receiver_rows),
        )
        reason_counts: collections.Counter[str] = collections.Counter()
        for row in receiver_rows:
            reason_counts.update(parse_reasons(row["selection_reasons"]))
        pooled_reasons[receiver_id] = reason_counts
    if pooled != EXPECTED_POOLED:
        problems.append(f"pooled confirmation counts differ: {pooled}")
    if any(dict(pooled_reasons[key]) != EXPECTED_REASONS[key] for key in CONFIRMATION_IDS):
        problems.append(f"selection-reason counts differ: {pooled_reasons}")

    _, recorded_rows = load_csv(THREE_ARM_CSV)
    recorded_lite = {
        (
            row["channel"],
            int(row["lane"]),
            *configuration_key(row),
            int(row["seed"]),
        ): row
        for row in recorded_rows
        if row["algorithm_id"] == "lite"
    }
    confirmation_lite = [row for row in rows if row["algorithm_id"] == "lite"]
    if len(recorded_lite) != 96 or len(confirmation_lite) != 96:
        problems.append("Lite control does not contain 96 unique rows on both sides")
    for row in confirmation_lite:
        key = (
            row["channel"],
            int(row["lane"]),
            *configuration_key(row),
            int(row["seed"]),
        )
        recorded = recorded_lite.get(key)
        if recorded is None:
            problems.append(f"Lite control row has no recorded match: {key}")
            continue
        mismatches = [field for field in OUTCOME_FIELDS if row[field] != recorded[field]]
        if mismatches:
            problems.append(f"Lite outcome mismatch for {key}: {mismatches}")

    _, partial_fft_rows = load_csv(PARTIAL_FFT_CSV)
    expected_ranking = ranking_payload(rows, recorded_rows, partial_fft_rows)
    with RANKING_JSON.open(encoding="utf-8") as handle:
        actual_ranking = json.load(handle)
    if actual_ranking != expected_ranking:
        problems.append("ranking JSON differs from the full confirmation tuple")
    if actual_ranking.get("winner_counts") != EXPECTED_WINNER_COUNTS:
        problems.append(
            f"winner counts differ: {actual_ranking.get('winner_counts')}"
        )

    path_index = {
        (entry["channel"], entry["hydrophone"]): entry
        for entry in actual_ranking.get("paths", [])
    }
    expected_ties = {
        ("red1", 2): ("joint_cwz", ["joint_cwz", "cz_refinement"]),
        ("red1", 3): (
            "lite",
            ["lite", "joint_cwz", "cz_refinement"],
        ),
    }
    for path, (winner_id, tie_ids) in expected_ties.items():
        entry = path_index.get(path)
        if entry is None:
            problems.append(f"ranking omits {path}")
        elif entry["winner_id"] != winner_id or entry["rate_tie_ids"] != tie_ids:
            problems.append(f"ranking tie handling differs for {path}: {entry}")

    with MANIFEST_JSON.open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    expected_manifest_values = {
        "schema_version": 1,
        "experiment_id": "2026-08-01-red-lite-search",
        "artifact_id": "cz_refinement_confirmation",
        "result_scope": "60-frame confirmation",
        "receiver_ids": list(CONFIRMATION_IDS),
        "row_count": 288,
    }
    for field, expected in expected_manifest_values.items():
        if manifest.get(field) != expected:
            problems.append(f"manifest {field} differs: {manifest.get(field)!r}")
    historical = manifest.get("historical_run", {})
    if historical.get("recovered_csv_sha256") != EXPECTED_RECOVERED_SHA256:
        problems.append("manifest recovered CSV digest differs")
    if historical.get("harness_sha256") != EXPECTED_HARNESS_SHA256:
        problems.append("manifest harness digest differs")
    if historical.get("replay_harness_sha256") != EXPECTED_REPLAY_SHA256:
        problems.append("manifest replay harness digest differs")
    expected_audit_states = {
        "qualification": AUDIT_OBSERVATION_QUALIFICATION,
        "historical_package_worktree_commit": EXPECTED_PACKAGE_WORKTREE_COMMIT,
        "primary_harness_checkout_commit": EXPECTED_PRIMARY_HARNESS_COMMIT,
    }
    if historical.get("audit_observed_source_states") != expected_audit_states:
        problems.append(
            "manifest audit-observed source states differ or are not qualified "
            "as unrecorded by the historical run"
        )
    files = manifest.get("files", {})
    if files.get("confirmation_csv", {}).get("sha256") != sha256(CONFIRMATION_CSV):
        problems.append("manifest confirmation CSV digest differs")
    if files.get("ranking", {}).get("sha256") != sha256(RANKING_JSON):
        problems.append("manifest ranking digest differs")
    limitations = manifest.get("limitations", {})
    expected_limitations = {
        "source_commit_recorded": False,
        "per_frame_workload_digests_retained": False,
        "joint_cwz_step_scales_retained": False,
        "joint_cwz_trial_rejections_retained": False,
        "joint_cwz_step_counter_scope": "step_call",
        "maximum_trials_per_step_call": 7,
    }
    if limitations != expected_limitations:
        problems.append(f"manifest limitations differ: {limitations}")

    stale_names = (
        "profiled" + "_cz",
        "cwz" + "_joint",
        "gradient" + "_accepted_frames",
        "conditioned" + "_accepted_steps",
        "conditioned" + "_rejected_steps",
    )
    for path in (CONFIRMATION_CSV, RANKING_JSON, ANALYZER):
        text = path.read_text(encoding="utf-8")
        for stale in stale_names:
            if stale in text:
                problems.append(f"{path.name} contains stale identifier {stale}")

    if problems:
        print("confirmation artifact validation FAILED")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print("confirmation artifact validation PASS")
    print("  CSV: 288 rows; 96 per receiver; 5,760 frames per receiver")
    print("  Lite control: 96/96 outcome rows exact; timing excluded")
    print("  winners: ofdm_fec 9, lite 1, pfft 0, cz_refinement 0, joint_cwz 2")
    print("  rate ties: red1 hydrophone 2 and red1 hydrophone 3 retained")
    print("  provenance and unavailable step-scale evidence recorded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
