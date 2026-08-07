#!/usr/bin/env python3
"""Validate the approved N=2048, rate=0.25, pilots=3/4, K=4 result."""

import csv
import hashlib
import json
import math
import os


HERE = os.path.dirname(os.path.abspath(__file__))
EXPERIMENT_ID = (
    "2026-08-05-red-snr-sweep-n2048-cp128-rate025-p3-4-dc8-k4")
CSV_PATH = os.path.join(HERE, "red_snr_sweep_uwa_noise.csv")
HTML_PATH = os.path.join(HERE, "results_view.html")
MANIFEST_PATH = os.path.join(HERE, "results_manifest.json")
EXPECTED_RECEIVERS = {"ofdm_fec", "pfft", "lite", "profiled_cz", "cwz_joint"}
PROFILED_RECEIVERS = {"profiled_cz", "cwz_joint"}
EXPECTED_SNRS = {float(value) for value in range(0, 31, 2)}
EXPECTED_PATHS = tuple(
    (f"red{capture}", lane)
    for capture in range(1, 5)
    for lane in range(1, 4)
)
GEOMETRY_KEYS = (
    "nfft", "cp", "code_rate", "outer_spacing", "inner_spacing",
    "check_degree", "horizon",
)
EXPECTED_GEOMETRY = ("2048", "128", "0.25", "3", "4", "8", "4")
EXPECTED_PAYLOAD_BITS_PER_FRAME = 2024
SOURCE_BASENAME = "red_snr_sweep_uwa_noise_configuration.csv"
EXPECTED_LABELS = {
    "OFDM + FEC",
    "Partial-FFT + FEC",
    "JUNA-Lite",
    "JUNA (C,z) Joint gradient",
    "Juna joint (C,W,z)",
}
EXPECTED_DECISIONS = {
    "CL-29", "CL-30", "CL-33", "CL-36", "CL-38", "CL-41", "JCM-097",
}
N512_HASHES = {
    "red_snr_sweep_uwa_noise.csv":
        "c6ddacc4abc712d39d3b873f4962acd3d71b5164d75f9a07063d740a40eb9686",
    "results_manifest.json":
        "6acf0ddbf64b631f639cdee9cc8013d3920d89243516f0882497e91e361ea09d",
    "results_view.html":
        "c70a3e8c38bfa596b3dcf8e6bf2eb2e703eac32f5b13c013bf4d2dd214330805",
}
N2048_RATE05_HASHES = {
    "red_snr_sweep_uwa_noise.csv":
        "72d86a6504b4e371a6e6037ba11b7bbb63b7965d1b387bf5376350fd5398df8d",
    "results_manifest.json":
        "8a4b54eb6bdc0ff605782171c906bb6874a6e6da5d11c6e274f870966c300a78",
    "results_view.html":
        "a12297704890a00bf595d873faeb6b473cb800902dd2cc0e1b68a13830f5502c",
}
N1024_HASHES = {
    "red_snr_sweep_uwa_noise.csv":
        "3c54351219d8238447554de4ce9bfc588855fe7517bfa9940745ff1fc57a19ae",
    "results_manifest.json":
        "433f22f4e63b511e0111844a9065fa6a63c7c7340bebdaf5633216459ee35b94",
    "results_view.html":
        "0a770b97469874c14625e879e310a1ad7ee0b36be8683a6c30c43006109e7699",
}
N2048_RATE025_P5_10_HASHES = {
    "red_snr_sweep_uwa_noise.csv":
        "691935fdb6c2b61176fccd5637b2270d181f2efb17984260de161733206acc5a",
    "results_manifest.json":
        "4f378e217820f52eab457fa4fd872fdef37808036ad2318a2e69a0f09a64cbf1",
    "results_view.html":
        "ec84aead1dd61e40e533a641fb999d25ba9fa58ac7c1ef4a848917c372171bca",
}
N1024_RATE025_P10_3_HASHES = {
    "red_snr_sweep_uwa_noise.csv":
        "6488956d526b70365e639cfcacedfae9470ec92fef3f1d74865efbd3da9172e5",
    "results_manifest.json":
        "7eb3472d33818c389070ea8c329a964421b84fcfe6081d1051a43916e6112340",
    "results_view.html":
        "cf45f1c41ac9d646e737d992fb7662c0c17e03994731f5efa266a4a49e61d2d2",
}
N1024_RATE025_P3_10_HASHES = {
    "red_snr_sweep_uwa_noise.csv":
        "bfdf504f32dfb16ed033f5df4f96e0d28eae814e4a7c5ffe0cbf0d6f8384e341",
    "results_manifest.json":
        "8be1aaa000c6dfcfe5ffffa517827ba04a8f25949a83891695c4216375d46d08",
    "results_view.html":
        "47ee1b6a132e85a219ebdd25f305fd561110eac9cb0a8eb4c1092c5ca1522e1d",
}
N1024_RATE025_P5_5_HASHES = {
    "red_snr_sweep_uwa_noise.csv":
        "32ffd48cc5f78383a1f841488e10a714ca64618907af686e3384fe29584c509c",
    "results_manifest.json":
        "fc8d5b1b6d41edeaf0fee5fd75608b1d59bf25c9f22e2910d1bc134571f168f6",
    "results_view.html":
        "77b294ac3dfeb2670046bfc6547c715235ffb16958a4a22919bf5a2056428c3d",
}
N2048_CP0_P2_3_HASHES = {
    "red_snr_sweep_uwa_noise.csv":
        "bc62c5bc0d46b86e0b83efe6c5415c6f165a75b38afd29b68c16107c3979fd3b",
    "results_manifest.json":
        "e636c6a411481c0ca6d371e0b2f5cbbeecc0a418f422a454910d36534c090f2e",
    "results_view.html":
        "677d3261b9968eb2288ebb9bea63eb3fac6d31331032c98c0db9d610dabe4ac5",
}
N2048_CP16_P3_5_HASHES = {
    "red_snr_sweep_uwa_noise.csv":
        "5f7b1089093978ec95c41ba9ffc94795ede367af54b3740606d8f29b04cde87c",
    "results_manifest.json":
        "1d186cbe09f006e8f2de71bde82c33814447e629fac05c24c9de2c6c84c624c2",
    "results_view.html":
        "6f647d76c7b78d91b4d29159eceeb92a570502b5cedf8ea0705fe2a1771789e7",
}


def require(condition, message):
    if not condition:
        raise SystemExit(
            "N2048 rate=0.25 pilots=3/4 validation failed: " + message)


def read_csv(path):
    require(os.path.isfile(path), "missing output: " + path)
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def source_name(channel, lane):
    return f"runs/{channel}_hydrophone{lane}/{SOURCE_BASENAME}"


def trace_name(channel, lane):
    return (f"runs/{channel}_hydrophone{lane}/"
            f"{channel}_hydrophone{lane}_selection_trace.csv")


def require_pinned_results(results_dir, expected_hashes, label):
    for name, expected in expected_hashes.items():
        path = os.path.join(results_dir, name)
        require(os.path.isfile(path), f"{label} result is missing: {name}")
        require(sha256(path) == expected, f"{label} result changed: {name}")


def main():
    rows = read_csv(CSV_PATH)
    require(os.path.isfile(MANIFEST_PATH), "missing results manifest")
    require(os.path.isfile(HTML_PATH), "missing rendered results page")
    with open(MANIFEST_PATH, encoding="utf-8") as handle:
        manifest = json.load(handle)
    with open(HTML_PATH, encoding="utf-8") as handle:
        page = handle.read()

    require(len(rows) == 960, f"expected 960 aggregate rows, found {len(rows)}")
    require({row["algorithm_id"] for row in rows} == EXPECTED_RECEIVERS,
            "receiver set differs")
    require({row["objective"] for row in rows} == {"configuration"},
            "result group differs")
    require({(row["channel"], int(row["lane"])) for row in rows} ==
            set(EXPECTED_PATHS), "capture/hydrophone set differs")
    require({row["frames"] for row in rows} == {"60"}, "frame count differs")
    require({row["seed"] for row in rows} == {"4"}, "seed differs")
    require({float(row["snr_db"]) for row in rows} == EXPECTED_SNRS,
            "aggregate SNR set differs")
    keys = {(row["channel"], int(row["lane"]), row["algorithm_id"],
             float(row["snr_db"])) for row in rows}
    require(len(keys) == 960, "aggregate keys are duplicated")
    for row in rows:
        require(tuple(row[key] for key in GEOMETRY_KEYS) == EXPECTED_GEOMETRY,
                "an aggregate row has the wrong geometry")
        require(int(row["payload_bits_per_frame"]) ==
                EXPECTED_PAYLOAD_BITS_PER_FRAME,
                "an aggregate row does not realize the approved K=4 payload")
        bits = int(row["payload_bits"])
        errors = int(row["bit_errors"])
        require(bits == EXPECTED_PAYLOAD_BITS_PER_FRAME * 60,
                "payload-bit arithmetic differs")
        require(math.isclose(float(row["ber"]), errors / bits,
                             rel_tol=0, abs_tol=1e-15), "BER arithmetic differs")
        require(math.isclose(float(row["psr"]),
                             int(row["successful_frames"]) / 60,
                             rel_tol=0, abs_tol=1e-15), "PSR arithmetic differs")

    trace_total = 0
    zero_iterations = {receiver: 0 for receiver in PROFILED_RECEIVERS}
    source_paths = set()
    canonical_rows = []
    for channel, lane in EXPECTED_PATHS:
        source = source_name(channel, lane)
        source_path = os.path.join(HERE, source)
        source_rows = read_csv(source_path)
        require(len(source_rows) == 80, f"{source} does not have 80 rows")
        canonical_rows.extend(source_rows)
        source_paths.add(source)
        trace = read_csv(os.path.join(HERE, trace_name(channel, lane)))
        require(len(trace) == 1920,
                f"{channel} hydrophone {lane} trace does not have 1920 rows")
        trace_total += len(trace)
        require({row["algorithm_id"] for row in trace} == PROFILED_RECEIVERS,
                f"{channel} hydrophone {lane} trace receiver set differs")
        require({float(row["snr_db"]) for row in trace} == EXPECTED_SNRS,
                f"{channel} hydrophone {lane} trace SNR set differs")
        require({int(row["frame"]) for row in trace} == set(range(1, 61)),
                f"{channel} hydrophone {lane} trace frame set differs")
        require({row["selection_reason"] for row in trace} == {"gradient_only"},
                f"{channel} hydrophone {lane} selection reason differs")
        require(all(
            row["workload_id"] ==
            f"{channel}:lane{lane}:snr{float(row['snr_db'])}:seed4:"
            f"frame{int(row['frame'])}"
            for row in trace
        ), f"{channel} hydrophone {lane} trace workload provenance differs")
        require(all(int(row["selected_iteration"]) >= 0 for row in trace),
                f"{channel} hydrophone {lane} selected iteration differs")
        trace_keys = {(row["algorithm_id"], float(row["snr_db"]),
                       int(row["frame"])) for row in trace}
        require(len(trace_keys) == 1920,
                f"{channel} hydrophone {lane} trace keys are duplicated")
        for receiver in PROFILED_RECEIVERS:
            zero_iterations[receiver] += sum(
                int(row["selected_iteration"]) == 0 for row in trace
                if row["algorithm_id"] == receiver)
            for snr in EXPECTED_SNRS:
                frames = [row for row in trace
                          if row["algorithm_id"] == receiver
                          and float(row["snr_db"]) == snr]
                aggregate = next(row for row in source_rows
                                 if row["algorithm_id"] == receiver
                                 and float(row["snr_db"]) == snr)
                require(sum(int(row["bit_errors"]) for row in frames) ==
                        int(aggregate["bit_errors"]), "trace errors differ")
                require(sum(row["success"] == "true" for row in frames) ==
                        int(aggregate["successful_frames"]),
                        "trace successes differ")
                require(sum(row["decode_failure"] == "true" for row in frames) ==
                        int(aggregate["decode_failures"]),
                        "trace failures differ")
    require(trace_total == 23040,
            f"expected 23040 trace rows, found {trace_total}")
    canonical_rows.sort(key=lambda row: (
        int(row["channel"][3:]), int(row["lane"]),
        float(row["snr_db"]), row["algorithm_id"]))
    require(rows == canonical_rows,
            "aggregate CSV differs from its twelve source CSVs")

    require(manifest["schema_version"] == 2, "manifest schema differs")
    require(set(manifest.get("decisions", [])) == EXPECTED_DECISIONS,
            "manifest decision set differs")
    require(manifest["experiment_id"] == EXPERIMENT_ID,
            "manifest experiment ID differs")
    require(manifest["row_count"] == 960, "manifest row count differs")
    require(set(manifest["receivers"]) == EXPECTED_RECEIVERS,
            "manifest receiver set differs")
    require(manifest["result_group"] == "configuration",
            "manifest result group differs")
    require(tuple(manifest["geometry"][key] for key in GEOMETRY_KEYS) ==
            EXPECTED_GEOMETRY, "manifest geometry differs")
    require(manifest["geometry_display"]["horizon"] == "4",
            "manifest does not display K=4")
    require(len(manifest["sources"]) == 12, "manifest source count differs")
    require({source["path"] for source in manifest["sources"]} == source_paths,
            "manifest source paths differ")
    for source in manifest["sources"]:
        path = os.path.join(HERE, source["path"])
        require(source["sha256"] == sha256(path),
                f"manifest hash differs: {source['path']}")
        require(source["rows"] == source["retained_rows"] == 80,
                f"manifest row count differs: {source['path']}")
    expected_trace_paths = {trace_name(channel, lane)
                            for channel, lane in EXPECTED_PATHS}
    require(len(manifest.get("trace_sources", [])) == 12,
            "manifest trace source count differs")
    require({source["path"] for source in manifest["trace_sources"]} ==
            expected_trace_paths, "manifest trace source paths differ")
    for source in manifest["trace_sources"]:
        path = os.path.join(HERE, source["path"])
        require(source["sha256"] == sha256(path),
                f"manifest trace hash differs: {source['path']}")
        require(source["rows"] == 1920,
                f"manifest trace row count differs: {source['path']}")

    require(page.count('<figure class="panel">') == 12,
            "rendered panel count differs")
    require(page.count('<path class="series"') == 60,
            "rendered series count differs")
    require(page.count("K=4") == 12, "not every panel displays K=4")
    require("Data table — 960 rows over 12 paths" in page,
            "rendered table count differs")
    require(all(label in page for label in EXPECTED_LABELS),
            "an approved receiver label is missing")
    for text in ("min-BER", "max-rate", "lowest 20 dB BER",
                 "highest 20 dB effective rate"):
        require(text not in page, f"rendered page contains {text}")
    caption = "N=2048 · CP=128 · rate=0.25 · pilots=3/4 · dc=8 · K=4"
    for channel, lane in EXPECTED_PATHS:
        start = (f'<figure class="panel"><figcaption><b>{channel} '
                 f'hydrophone {lane}</b><span>{caption}</span>')
        require(start in page, f"{channel} hydrophone {lane} panel differs")

    experiments_dir = os.path.dirname(os.path.dirname(HERE))
    view_builder = os.path.join(
        experiments_dir, "2026-08-04-red-snr-sweep", "results",
        "build_sweep_view.py")
    namespace = {
        "__file__": view_builder,
        "__name__": "_n2048_rate025_p3_4_view_builder",
    }
    with open(view_builder, encoding="utf-8") as handle:
        exec(compile(handle.read(), view_builder, "exec"), namespace)
    expected_page = namespace["render"](rows, configuration_only=True)
    require(page == expected_page,
            "rendered page is not the deterministic view of the aggregate CSV")

    prior_results = (
        ("N512", "2026-08-04-red-snr-sweep-n512-cp16-rate05-p3-4-dc10-kfill",
         N512_HASHES),
        ("N2048 rate-0.5",
         "2026-08-04-red-snr-sweep-n2048-cp128-rate05-p5-10-dc8-k4",
         N2048_RATE05_HASHES),
        ("N1024", "2026-08-05-red-snr-sweep-n1024-cp16-rate05-p5-10-dc10-kfill",
         N1024_HASHES),
        ("N2048 rate-0.25 pilots=5/10",
         "2026-08-05-red-snr-sweep-n2048-cp128-rate025-p5-10-dc8-k4",
         N2048_RATE025_P5_10_HASHES),
        ("N1024 rate-0.25 pilots=10/3",
         "2026-08-05-red-snr-sweep-n1024-cp16-rate025-p10-3-dc10-k4",
         N1024_RATE025_P10_3_HASHES),
        ("N1024 rate-0.25 pilots=3/10",
         "2026-08-05-red-snr-sweep-n1024-cp16-rate025-p3-10-dc10-k4",
         N1024_RATE025_P3_10_HASHES),
        ("N1024 rate-0.25 pilots=5/5",
         "2026-08-05-red-snr-sweep-n1024-cp16-rate025-p5-5-dc10-k4",
         N1024_RATE025_P5_5_HASHES),
        ("N2048 CP0 rate-0.25 pilots=2/3",
         "2026-08-05-red-snr-sweep-n2048-cp0-rate025-p2-3-dc10-k4",
         N2048_CP0_P2_3_HASHES),
        ("N2048 CP16 rate-0.25 pilots=3/5",
         "2026-08-05-red-snr-sweep-n2048-cp16-rate025-p3-5-dc10-k4",
         N2048_CP16_P3_5_HASHES),
    )
    for label, experiment, expected_hashes in prior_results:
        require_pinned_results(
            os.path.join(experiments_dir, experiment, "results"),
            expected_hashes,
            label,
        )

    print("N2048 rate=0.25 pilots=3/4 validation passed: "
          "960 aggregate rows, 23040 trace rows, 12 panels, 60 series")
    print("selected_iteration=0", json.dumps(zero_iterations, sort_keys=True))


if __name__ == "__main__":
    main()
