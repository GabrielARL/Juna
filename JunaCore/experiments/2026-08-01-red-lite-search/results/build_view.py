#!/usr/bin/env python3
"""Build and check the self-contained confirmation-results view."""
import argparse
import csv
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
EXPERIMENT_ID = os.path.basename(EXP)

# JCM-056: only the 60-frame confirmation inputs remain reader-visible.
# JCM-055: adaptive_lite remains in the source CSV as run history, but is not
# part of the retained receiver set.
DROPPED_RECEIVERS = {"adaptive_lite"}
SOURCES = [
    ("results/red_config_finalists_20db_seeds6to7.csv", "3arm"),
    ("results_pfft/red_config_finalists_20db_seeds6to7.csv", "pfft"),
    ("results_cz/red_profiled_cz_confirm_20db_seeds6to7.csv", "cz"),
]

# CL-26(c): the Profiled C,z run measures four things the other runs have no
# counterpart for, and they are reader-visible. A source may therefore carry
# the base schema or the base schema plus these four, and nothing else — the
# earlier "every source has identical columns" rule is kept as a two-shape
# rule rather than dropped. Rows from a base-schema source read blank here.
MECHANISM_COLUMNS = [
    "gradient_accepted_frames", "conditioned_accepted_steps",
    "conditioned_rejected_steps", "selection_reasons",
]

# JCM-064 and JCM-067: keep every source column in row details and downloads,
# while the compact table begins with the two requested outcome measures.
DISPLAY_COLUMNS = [
    "psr", "ber", "channel", "lane", "algorithm_id", "nfft", "cp",
    "code_rate", "outer_spacing", "inner_spacing", "check_degree",
    "payload_bits_per_frame", "successful_frames", "decode_failures",
    "decode_seconds", "effective_rate_bps", "run",
] + MECHANISM_COLUMNS
HIDDEN_TABLE_COLUMNS = {
    "phase", "start_index", "horizon", "seed", "frames", "frame_blocks",
    "payload_bits", "bit_errors",
}


def canonical_receiver_id(receiver):
    """Map the historical source ID to the package's canonical ID."""
    return "ofdm_fec" if receiver == "standard" else receiver

REQUIRED_READER_TEXT = (
    "Selected channel and hydrophone",
    "Winner geometry by channel and hydrophone",
)
FORBIDDEN_READER_TEXT = (
    "Path dossier",
    "paths confirmed",
    "Winner geometry per path",
    "Path coverage:",
)


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _num(text):
    """Parse for plotting without rounding; source text is kept separately."""
    try:
        if not any(mark in text.lower() for mark in (".", "e")):
            return int(text)
        return float(text)
    except ValueError:
        return text


def load_configs():
    base_columns = None
    numeric_rows, raw_rows, row_ids, sources = [], [], [], []
    for relative, run in SOURCES:
        path = os.path.join(EXP, relative)
        if not os.path.isfile(path):
            raise SystemExit("missing input: " + relative)
        with open(path, newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fields = list(reader.fieldnames or [])
            if base_columns is None:
                base_columns = [column for column in fields
                                if column not in MECHANISM_COLUMNS]
                columns = base_columns + MECHANISM_COLUMNS
            if fields not in (base_columns, columns):
                raise SystemExit("source columns differ: " + relative)
            source_count = included_count = 0
            excluded = {}
            for source_row, record in enumerate(reader, start=2):
                source_count += 1
                receiver = record["algorithm_id"]
                if receiver in DROPPED_RECEIVERS:
                    excluded[receiver] = excluded.get(receiver, 0) + 1
                    continue
                raw = [record.get(column, "") for column in columns] + [run]
                numeric = [_num(value) for value in raw]
                numeric[columns.index("algorithm_id")] = canonical_receiver_id(
                    receiver)
                identity = (relative + "\0" + str(source_row) + "\0" +
                            "\0".join(raw)).encode()
                row_ids.append(hashlib.sha256(identity).hexdigest())
                raw_rows.append(raw)
                numeric_rows.append(numeric)
                included_count += 1
        sources.append({
            "path": relative,
            "sha256": _sha256(path),
            "source_rows": source_count,
            "included_rows": included_count,
            "excluded_rows": excluded,
        })
    return columns + ["run"], numeric_rows, raw_rows, row_ids, sources


def coverage(columns, rows):
    index = {column: i for i, column in enumerate(columns)}
    seen = {}
    for row in rows:
        seen.setdefault(row[index["run"]], set()).add(
            (row[index["channel"]], row[index["lane"]]))
    return {run: sorted(f"{channel} {lane}" for channel, lane in paths)
            for run, paths in sorted(seen.items())}


def strip_dropped(winners):
    """Remove the retired receiver from comparison markers, never winners."""
    for path in winners["paths"]:
        path["winner"]["algorithm_id"] = canonical_receiver_id(
            path["winner"]["algorithm_id"])
        for other in path["others"]:
            other["algorithm_id"] = canonical_receiver_id(
                other["algorithm_id"])
        if path.get("pfft"):
            path["pfft"]["algorithm_id"] = canonical_receiver_id(
                path["pfft"]["algorithm_id"])
        path["others"] = [other for other in path["others"]
                          if other["algorithm_id"] not in DROPPED_RECEIVERS]
        if path["winner"]["algorithm_id"] in DROPPED_RECEIVERS:
            raise SystemExit("a removed receiver won a path")
    return winners


def validate_payload(columns, rows, raw_rows, row_ids, manifest):
    index = {column: i for i, column in enumerate(columns)}
    problems = []
    if len(rows) != 384:
        problems.append(f"expected 384 rows, found {len(rows)}")
    if not (len(rows) == len(raw_rows) == len(row_ids)):
        problems.append("numeric rows, source rows, and row IDs differ")
    if len(set(row_ids)) != len(row_ids):
        problems.append("row IDs are not unique")
    receivers = {row[index["algorithm_id"]] for row in rows}
    if receivers != {"ofdm_fec", "lite", "pfft", "profiled_cz"}:
        problems.append(f"receiver set differs: {sorted(receivers)}")
    if {row[index["frames"]] for row in rows} != {60}:
        problems.append("a retained row is not a 60-frame confirmation")
    if {row[index["seed"]] for row in rows} != {6, 7}:
        problems.append("confirmation seeds are not exactly 6 and 7")
    if any(row[index["decode_failures"]] != 0 for row in rows):
        problems.append("a retained row has a decode failure")
    if any(len(paths) != 12 for paths in manifest["coverage"].values()):
        problems.append("a retained run does not cover all 12 paths")
    if DISPLAY_COLUMNS[:2] != ["psr", "ber"]:
        problems.append("displayed columns do not begin with PSR and BER")
    if not set(DISPLAY_COLUMNS).issubset(columns):
        problems.append("a displayed column is absent from the source")
    if set(DISPLAY_COLUMNS) & HIDDEN_TABLE_COLUMNS:
        problems.append("a hidden source column remains in the compact table")
    if set(columns) - set(DISPLAY_COLUMNS) != HIDDEN_TABLE_COLUMNS:
        problems.append("compact-table exclusions differ from the approved set")
    if problems:
        raise SystemExit("results completeness failure: " + "; ".join(problems))


def render():
    with open(os.path.join(HERE, "viewdata.json"), encoding="utf-8") as handle:
        winners = strip_dropped(json.load(handle))
    columns, rows, raw_rows, row_ids, sources = load_configs()
    paths = sorted({(row[0], row[1]) for row in rows})
    covered = coverage(columns, rows)
    manifest = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "result_scope": "60-frame confirmation",
        "row_count": len(rows),
        "columns": columns,
        "display_columns": DISPLAY_COLUMNS,
        "coverage": covered,
        "sources": sources,
        "numeric_policy": (
            "raw_rows preserves every source cell exactly; rows contains "
            "unrounded numeric values for sorting and plotting"
        ),
    }
    payload = {
        "cols": columns,
        "display_cols": DISPLAY_COLUMNS,
        "rows": rows,
        "raw_rows": raw_rows,
        "row_ids": row_ids,
        "coverage": covered,
        "channels": sorted({channel for channel, _ in paths}),
        "hydrophones": sorted({lane for _, lane in paths}),
    }
    validate_payload(columns, rows, raw_rows, row_ids, manifest)
    with open(os.path.join(HERE, "view_template.html"), encoding="utf-8") as handle:
        template = handle.read()
    missing = [text for text in REQUIRED_READER_TEXT if text not in template]
    stale = [text for text in FORBIDDEN_READER_TEXT if text in template]
    if missing or stale:
        raise SystemExit("reader wording failure: missing " + repr(missing) +
                         "; stale " + repr(stale))
    replacements = {
        "/*__WINNERS__*/": json.dumps(winners, separators=(",", ":")),
        "/*__CONFIGS__*/": json.dumps(payload, separators=(",", ":")),
        "/*__MANIFEST__*/": json.dumps(manifest, separators=(",", ":")),
    }
    html = template
    for marker, value in replacements.items():
        if marker not in html:
            raise SystemExit("template marker missing: " + marker)
        html = html.replace(marker, value)
    return html, manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="fail when generated results are stale")
    args = parser.parse_args()
    html, manifest = render()
    out = os.path.join(HERE, "results_view.html")
    manifest_path = os.path.join(HERE, "results_manifest.json")
    manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if args.check:
        expected = [(out, html), (manifest_path, manifest_text)]
        stale = [os.path.basename(path) for path, text in expected
                 if not os.path.isfile(path) or
                 open(path, encoding="utf-8").read() != text]
        if stale:
            raise SystemExit("stale generated result: " + ", ".join(stale))
        print(f"results view contract: PASS ({manifest['row_count']} rows, "
              f"{len(manifest['columns'])} columns)")
        return
    with open(out, "w", encoding="utf-8") as handle:
        handle.write(html)
    with open(manifest_path, "w", encoding="utf-8") as handle:
        handle.write(manifest_text)
    print(f"wrote {out} ({len(html) / 1e6:.2f} MB, "
          f"{manifest['row_count']} configurations)")


if __name__ == "__main__":
    main()
