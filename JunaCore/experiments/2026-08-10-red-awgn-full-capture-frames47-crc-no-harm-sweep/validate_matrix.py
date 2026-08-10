#!/usr/bin/env python3
"""Validate the complete one-configuration AWGN-023B campaign."""

import os

import matrix_contract
import validate_results


def main():
    experiments = os.environ.get(
        "JUNA_AWGN023B_OUTPUT_EXPERIMENTS",
        "/home/gabiel/Documents/GitHub/Juna-worktrees/awgn-023bc-extended-observation/"
        "JunaCore/experiments",
    )
    matrix_contract.validate_ids()
    manifests = [
        validate_results.validate(os.path.join(experiments, experiment_id))
        for experiment_id in matrix_contract.EXPECTED_IDS
    ]
    if sum(item["row_count"] for item in manifests) != 960:
        raise SystemExit("AWGN-023B matrix aggregate count differs")
    if sum(item["frame_trace_row_count"] for item in manifests) != 45120:
        raise SystemExit("AWGN-023B matrix frame-trace count differs")
    if sum(item["protected_trace_row_count"] for item in manifests) != 18048:
        raise SystemExit("AWGN-023B matrix protected-trace count differs")
    print(
        "AWGN-023B MATRIX VALID: 1/1 configuration, 12/12 paths, "
        "960 aggregates, 45120 frame traces, 18048 protected traces, "
        "12 panels, 60 series"
    )


if __name__ == "__main__":
    main()
