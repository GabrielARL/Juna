#!/usr/bin/env python3
"""Validate the complete one-configuration AWGN-021 campaign."""

import os

import matrix_contract
import validate_results


def main():
    experiments = os.environ.get(
        "JUNA_AWGN021_OUTPUT_EXPERIMENTS",
        "/home/gabiel/Documents/GitHub/Juna-worktrees/awgn-021-first16s/"
        "JunaCore/experiments",
    )
    matrix_contract.validate_ids()
    manifests = [
        validate_results.validate(os.path.join(experiments, experiment_id))
        for experiment_id in matrix_contract.EXPECTED_IDS
    ]
    if sum(item["row_count"] for item in manifests) != 960:
        raise SystemExit("AWGN-021 matrix aggregate count differs")
    if sum(item["frame_trace_row_count"] for item in manifests) != 15360:
        raise SystemExit("AWGN-021 matrix frame-trace count differs")
    if sum(item["protected_trace_row_count"] for item in manifests) != 6144:
        raise SystemExit("AWGN-021 matrix protected-trace count differs")
    print(
        "AWGN-021 MATRIX VALID: 1/1 configuration, 12/12 paths, "
        "960 aggregates, 15360 frame traces, 6144 protected traces, "
        "12 panels, 60 series"
    )


if __name__ == "__main__":
    main()
