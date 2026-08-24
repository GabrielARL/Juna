#!/usr/bin/env python3
"""Seed a results_manifest.json for a NEW Blue experiment.

Both Blue builders update an existing manifest; neither creates one, so a
brand-new FFT length has nothing to build against. This copies a sibling
manifest that shares pilot spacing, cyclic prefix, budget and seed, drops
the records that belong to that sibling's own reruns, and sets only the
FFT-length-dependent fields. The builder and validator then govern.
"""
import json, os, sys

MODEM_FS = 4882.8125
DROP = ("cfo_rerun", "blue1_refresh", "gate",
        "acquisition_source_commit", "acquisition_source_sha256")


def main():
    if not (6 <= len(sys.argv) <= 8):
        raise SystemExit("usage: seed_blue_manifest.py TEMPLATE TARGET "
                         "NFFT PAYLOAD_BITS FRAME_SAMPLES [CP] [SEED] [BUDGET]")
    template, target = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    nfft, payload, samples = int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
    cp = int(sys.argv[6]) if len(sys.argv) >= 7 else None
    seed = int(sys.argv[7]) if len(sys.argv) >= 8 else None
    src = os.path.join(template, "results", "results_manifest.json")
    dst = os.path.join(target, "results", "results_manifest.json")
    if not os.path.isfile(src):
        raise SystemExit("missing template manifest " + src)
    if os.path.exists(dst):
        raise SystemExit("refusing to overwrite existing manifest " + dst)
    with open(src, encoding="utf-8") as handle:
        manifest = json.load(handle)
    for key in DROP:
        manifest.pop(key, None)
    budget_env = os.environ.get("JUNA_BLUE_NATIVE_FRAME_BUDGET")
    budget = float(budget_env) if budget_env else None
    manifest["experiment_id"] = os.path.basename(target)
    manifest["payload_bits_per_frame"] = payload
    manifest["frame_samples"] = samples
    manifest["frame_duration_seconds"] = samples / MODEM_FS
    if seed is not None:
        manifest["seed"] = seed
    if budget is not None and budget != 1.0:
        manifest["frame_duration_budget_seconds"] = budget
    for block in ("geometry", "geometry_display", "full_configuration"):
        if block in manifest and "nfft" in manifest[block]:
            manifest[block]["nfft"] = nfft
        if cp is not None and block in manifest and "cp" in manifest[block]:
            manifest[block]["cp"] = cp
        if seed is not None and block in manifest and "seed" in manifest[block]:
            manifest[block]["seed"] = seed
        if (budget is not None and block in manifest
                and "frame_duration_budget_seconds" in manifest[block]):
            manifest[block]["frame_duration_budget_seconds"] = budget
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(f"SEEDED MANIFEST id={manifest['experiment_id']} nfft={nfft} "
          f"payload={payload} frame_samples={samples} "
          f"frame_duration_s={manifest['frame_duration_seconds']:.6f} "
          f"template={os.path.basename(template)}")


if __name__ == "__main__":
    main()
