#!/usr/bin/env python3
"""Validate the complete one-configuration AWGN-024 campaign."""

import os

import matrix_contract
import validate_results


def main():
    experiments = os.environ.get(
        "JUNA_AWGN024_OUTPUT_EXPERIMENTS",
        "/home/gabiel/Documents/GitHub/Juna-worktrees/awgn-024-rate05-first32s/"
        "JunaCore/experiments",
    )
    matrix_contract.validate_ids()
    manifests = [
        validate_results.validate(os.path.join(experiments, experiment_id))
        for experiment_id in matrix_contract.EXPECTED_IDS
    ]
    if sum(item["row_count"] for item in manifests) != 960:
        raise SystemExit("AWGN-024 matrix aggregate count differs")
    if sum(item["frame_trace_row_count"] for item in manifests) != 30720:
        raise SystemExit("AWGN-024 matrix frame-trace count differs")
    if sum(item["protected_trace_row_count"] for item in manifests) != 12288:
        raise SystemExit("AWGN-024 matrix protected-trace count differs")
    print(
        "AWGN-024 MATRIX VALID: 1/1 configuration, 12/12 paths, "
        "960 aggregates, 30720 frame traces, 12288 protected traces, "
        "12 panels, 60 series"
    )


if __name__ == "__main__":
    main()
