#!/usr/bin/env python3
"""Record the 30 dB Standard OFDM gate over all twelve Blue paths.

The rerun harness records cfo_rerun.gate for its nine refreshed paths only.
Configurations created by queue_blue_native_awgn_pilot_percent.ps1 have no
gate step at all, so this records the same 0.1 verdict over twelve paths.
Structural problems are hard failures; a breach is recorded, not fatal.
"""
import csv, json, os, sys

CHANNELS = ("blue1", "blue2", "blue3", "blue4")
LANES = (1, 2, 3)
PER_PATH = "blue_snr_sweep_awgn_native_first47s_frames32_configuration.csv"
LIMIT = 0.1


def fail(message):
    raise SystemExit("Blue 12-path gate failed: " + message)


def main():
    if len(sys.argv) != 3:
        fail("usage: gate_blue_12paths.py EXPERIMENT COMMIT")
    experiment, commit = os.path.abspath(sys.argv[1]), sys.argv[2]
    runs = os.path.join(experiment, "results", "runs")
    failures, values = [], []
    for channel in CHANNELS:
        for lane in LANES:
            stem = f"{channel}_hydrophone{lane}"
            path = os.path.join(runs, stem, PER_PATH)
            if not os.path.isfile(path):
                fail("missing per-path aggregate " + path)
            with open(path, newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            selected = [r for r in rows
                        if r["algorithm_id"] == "ofdm_fec"
                        and float(r["snr_db"]) == 30.0]
            if len(selected) != 1:
                fail(stem + " 30 dB OFDM row differs")
            ber = float(selected[0]["ber"])
            if ber < 0.0:
                fail(f"{stem} 30 dB OFDM BER is negative: {ber}")
            values.append(ber)
            if ber >= LIMIT:
                failures.append({"path": stem, "ber": ber})
                print(f"BLUE_GATE_FAIL path={stem} ber={ber!r} limit={LIMIT}")
    manifest_path = os.path.join(experiment, "results", "results_manifest.json")
    if not os.path.isfile(manifest_path):
        fail("missing manifest " + manifest_path)
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    manifest["gate"] = {
        "limit": LIMIT,
        "mode": "record_only",
        "path_count": 12,
        "high_snr_ofdm_ber_max": max(values),
        "failures": failures,
        "source_commit": commit,
    }
    with open(manifest_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    verdict = "VALID" if not failures else "RECORDED-WITH-GATE-FAILURES"
    print(f"{verdict} BLUE 12-PATH GATE paths=12 "
          f"max_30db_ofdm_ber={max(values):.9g} "
          f"gate_failures={len(failures)} commit={commit[:12]}")


if __name__ == "__main__":
    main()
