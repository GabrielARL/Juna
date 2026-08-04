#!/usr/bin/env python3
"""Rank the current receiver IDs with the confirmation search rule."""

from __future__ import annotations

import collections
import csv
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE.parent
CONFIRMATION_CSV = HERE / "red_cz_refinement_confirmation_20db_seeds6to7.csv"
THREE_ARM_CSV = (
    EXPERIMENT / "results" / "red_config_finalists_20db_seeds6to7.csv"
)
PARTIAL_FFT_CSV = (
    EXPERIMENT
    / "results_partial_fft"
    / "red_config_finalists_20db_seeds6to7.csv"
)
OUTPUT = HERE / "confirmed_receiver_ranking.json"
RECEIVER_IDS = ("ofdm_fec", "lite", "pfft", "cz_refinement", "joint_cwz")
CONFIGURATION_FIELDS = (
    "nfft",
    "cp",
    "code_rate",
    "outer_spacing",
    "inner_spacing",
    "check_degree",
    "horizon",
)


def load(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def configuration_key(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(row[field] for field in CONFIGURATION_FIELDS)


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


def result_order(result: dict[str, object]) -> tuple[float, float, float]:
    return (
        float(result["mean_effective_rate_bps"]),
        -float(result["pooled_ber"]),
        -float(result["mean_decode_seconds_per_frame"]),
    )


def best_results() -> dict[tuple[str, int, str], dict[str, object]]:
    retained_rows = [
        {**row, "algorithm_id": "ofdm_fec"}
        for row in load(THREE_ARM_CSV)
        if row["algorithm_id"] == "standard"
    ]
    retained_rows.extend(load(PARTIAL_FFT_CSV))
    # This supplies Lite timing from the same run as both C,z refinement forms.
    retained_rows.extend(load(CONFIRMATION_CSV))

    groups: dict[
        tuple[str, int, str, tuple[str, ...]], list[dict[str, str]]
    ] = collections.defaultdict(list)
    for row in retained_rows:
        key = (
            row["channel"],
            int(row["lane"]),
            row["algorithm_id"],
            configuration_key(row),
        )
        groups[key].append(row)

    best: dict[tuple[str, int, str], dict[str, object]] = {}
    for (channel, hydrophone, receiver_id, configuration), rows in groups.items():
        if len(rows) != 2 or {int(row["seed"]) for row in rows} != {6, 7}:
            continue
        if any(int(row["decode_failures"]) != 0 for row in rows):
            continue
        payload_bits = sum(int(row["payload_bits"]) for row in rows)
        result = {
            "receiver_id": receiver_id,
            "configuration": typed_configuration(configuration),
            "mean_effective_rate_bps": sum(
                float(row["effective_rate_bps"]) for row in rows
            )
            / 2,
            "minimum_effective_rate_bps": min(
                float(row["effective_rate_bps"]) for row in rows
            ),
            "mean_packet_success_rate": sum(float(row["psr"]) for row in rows)
            / 2,
            "pooled_ber": sum(int(row["bit_errors"]) for row in rows)
            / payload_bits,
            "mean_decode_seconds_per_frame": sum(
                float(row["decode_seconds"]) for row in rows
            )
            / 2,
        }
        key = (channel, hydrophone, receiver_id)
        if key not in best or result_order(result) > result_order(best[key]):
            best[key] = result
    return best


def build_payload() -> dict[str, object]:
    best = best_results()
    winner_counts = {receiver_id: 0 for receiver_id in RECEIVER_IDS}
    path_keys = sorted({(key[0], key[1]) for key in best})
    paths = []
    for channel, hydrophone in path_keys:
        missing = [
            receiver_id
            for receiver_id in RECEIVER_IDS
            if (channel, hydrophone, receiver_id) not in best
        ]
        if missing:
            raise ValueError(
                f"{channel} hydrophone {hydrophone} lacks receivers {missing}"
            )
        receiver_results = [
            best[(channel, hydrophone, receiver_id)] for receiver_id in RECEIVER_IDS
        ]
        ranked = sorted(receiver_results, key=result_order, reverse=True)
        maximum_rate = ranked[0]["mean_effective_rate_bps"]
        rate_tie_ids = [
            result["receiver_id"]
            for result in ranked
            if result["mean_effective_rate_bps"] == maximum_rate
        ]
        winner_id = str(ranked[0]["receiver_id"])
        winner_counts[winner_id] += 1
        paths.append(
            {
                "channel": channel,
                "hydrophone": hydrophone,
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


def main() -> None:
    payload = build_payload()
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUTPUT} ({len(payload['paths'])} channel-hydrophone results)")


if __name__ == "__main__":
    main()
