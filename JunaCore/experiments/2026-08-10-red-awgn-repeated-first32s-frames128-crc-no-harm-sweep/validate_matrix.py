#!/usr/bin/env python3
"""Validate the complete one-configuration AWGN-023C campaign."""

import os

import matrix_contract
import validate_results


def main():
    experiments = os.environ.get(
        "JUNA_AWGN023C_OUTPUT_EXPERIMENTS",
        "/home/gabiel/Documents/GitHub/Juna-worktrees/"
        "awgn-023bc-extended-observation/JunaCore/experiments",
    )
    matrix_contract.validate_ids()
    manifests = [
        validate_results.validate(os.path.join(experiments, experiment_id))
        for experiment_id in matrix_contract.EXPECTED_IDS
    ]
    if sum(item["row_count"] for item in manifests) != 960:
        raise SystemExit("AWGN-023C matrix aggregate count differs")
    if sum(item["frame_trace_row_count"] for item in manifests) != 122880:
        raise SystemExit("AWGN-023C matrix frame-trace count differs")
    if sum(item["protected_trace_row_count"] for item in manifests) != 49152:
        raise SystemExit("AWGN-023C matrix protected-trace count differs")
    print(
        "AWGN-023C MATRIX VALID: 1/1 configuration, 12/12 paths, "
        "960 aggregates, 122880 frame traces, 49152 protected traces, "
        "12 panels, 60 series"
    )


if __name__ == "__main__":
    main()
