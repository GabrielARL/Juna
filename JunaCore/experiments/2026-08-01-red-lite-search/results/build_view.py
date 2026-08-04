#!/usr/bin/env python3
"""Build and check the self-contained confirmation-results view."""
import argparse
import csv
import hashlib
import html as html_module
import json
import os
import re
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
EXPERIMENT_ID = os.path.basename(EXP)
CONFIRMATION_DIR = os.path.join(EXP, "cz_refinement_confirmation")
CONFIRMATION_MANIFEST_PATH = os.path.join(
    CONFIRMATION_DIR, "confirmation_manifest.json")
RANKING_REFERENCE_PATH = os.path.join(
    CONFIRMATION_DIR, "confirmed_receiver_ranking.json")

# JCM-056: only the 60-frame confirmation inputs remain reader-visible.
# JCM-055: adaptive_lite remains in the source CSV as run history, but is not
# part of the retained receiver set. The C,z confirmation reran JUNA-Lite on
# the same package and harness, so those rows replace the earlier Lite timing
# rows and supply the tie-breaking decode time (JCM-151b).
EXPECTED_RECEIVERS = {
    "ofdm_fec", "lite", "pfft", "cz_refinement", "joint_cwz",
}
SOURCES = [
    {
        "path": "results/red_config_finalists_20db_seeds6to7.csv",
        "run": "ofdm_fec_search",
        "include": {"standard"},
    },
    {
        "path": "results_partial_fft/red_config_finalists_20db_seeds6to7.csv",
        "run": "partial_fft_search",
        "include": {"pfft"},
    },
    {
        "path": (
            "cz_refinement_confirmation/"
            "red_cz_refinement_confirmation_20db_seeds6to7.csv"
        ),
        "run": "cz_refinement_confirmation",
        "include": {"lite", "cz_refinement", "joint_cwz"},
    },
]
CONFIG_KEYS = (
    "nfft", "cp", "code_rate", "outer_spacing", "inner_spacing",
    "check_degree", "horizon",
)
EXPECTED_WINNERS = {
    ("red1", 1): "ofdm_fec",
    ("red1", 2): "joint_cwz",
    ("red1", 3): "lite",
    ("red2", 1): "joint_cwz",
    ("red2", 2): "ofdm_fec",
    ("red2", 3): "ofdm_fec",
    ("red3", 1): "ofdm_fec",
    ("red3", 2): "ofdm_fec",
    ("red3", 3): "ofdm_fec",
    ("red4", 1): "ofdm_fec",
    ("red4", 2): "ofdm_fec",
    ("red4", 3): "ofdm_fec",
}
EXPECTED_RATE_TIES = {
    ("red1", 2): ["joint_cwz", "cz_refinement"],
    ("red1", 3): ["lite", "joint_cwz", "cz_refinement"],
}

# JCM-064 and JCM-067: keep every source column in row details and downloads,
# while the compact table begins with the two requested outcome measures.
DISPLAY_COLUMNS = [
    "psr", "ber", "channel", "lane", "algorithm_id", "nfft", "cp",
    "code_rate", "outer_spacing", "inner_spacing", "check_degree",
    "payload_bits_per_frame", "successful_frames", "decode_failures",
    "decode_seconds", "effective_rate_bps", "run",
]
HIDDEN_TABLE_COLUMNS = {
    "phase", "start_index", "horizon", "seed", "frames", "frame_blocks",
    "payload_bits", "bit_errors", "refinement_selected_frames",
    "joint_cwz_accepted_steps", "joint_cwz_rejected_steps",
    "selection_reasons",
}


def canonical_receiver_id(receiver):
    """Map the historical source ID to the package's canonical ID."""
    return "ofdm_fec" if receiver == "standard" else receiver

REQUIRED_READER_TEXT = (
    "Selected channel and hydrophone",
    "Winner geometry by channel and hydrophone",
    "OFDM+FEC",
    "JUNA-Lite",
    "Partial-FFT + FEC",
    "C,z refinement",
    "joint C,W,z",
    "lower pooled bit error rate",
    "not a separate configuration search",
    "call-level counts",
    "linear chirp synchronization",
    "FFT length",
    "Cyclic-prefix length",
    "Outer/inner pilot spacing",
    "LDPC check degree",
    "Frame-code component block count",
    "confirmation rows, 60 frames each",
    "zeroPsrRows.length",
    "Orthogonal frequency-division multiplexing with forward error correction",
    "Partial fast Fourier transform with forward error correction",
    "Packet success ratio (PSR)",
    "bit error rate (BER)",
    "Cyclic prefix (CP)",
    "low-density parity-check (LDPC)",
    "cyclic redundancy check (CRC)",
    "C,z refinement confirmation evidence",
)
FORBIDDEN_READER_TEXT = (
    "Path dossier",
    "paths confirmed",
    "Winner geometry per path",
    "Path coverage:",
    "Profiled C,z",
    "Conditioned Joint",
    "gradient accepted",
    "Partial FFT+FEC",
    "LFM-sync",
    "confirmed configurations, 60 frames each",
    "All 69 rows",
    "outer pilot ratio",
    "inner pilot ratio",
    "FFT size N",
    "K — horizon",
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


def validate_reader_prose(template):
    """Check prose blocks without treating CSS and JavaScript as prose."""
    reader_template = re.sub(
        r"<(script|style)(?:\s[^>]*)?>.*?</\1>", "", template,
        flags=re.DOTALL | re.IGNORECASE)
    blocks = []
    for tag in ("p", "dd"):
        for body in re.findall(
                rf"<{tag}(?:\s[^>]*)?>(.*?)</{tag}>", reader_template,
                flags=re.DOTALL | re.IGNORECASE):
            text = re.sub(r"<[^>]+>", " ", body)
            blocks.append(" ".join(html_module.unescape(text).split()))
    sentences = [
        sentence.strip()
        for block in blocks
        for sentence in re.split(r"(?<=[.!?])\s+", block)
        if sentence.strip()
    ]
    long_sentences = []
    for sentence in sentences:
        words = re.findall(r"[A-Za-z0-9]+(?:[-+,][A-Za-z0-9]+)*", sentence)
        if len(words) > 35:
            long_sentences.append((len(words), sentence))
    banned = (
        "novel", "state-of-the-art", "framework", "paradigm", "leverage",
        "utilize", "in order to", "crucial", "vital", "clearly",
        "obviously", "it is worth noting", "natural", "elegant",
        "principled", "lifting",
    )
    prose = " ".join(blocks).lower()
    banned_hits = [
        word for word in banned
        if re.search(rf"\b{re.escape(word)}\b", prose)
    ]
    contractions = re.findall(
        r"\b(?:[A-Za-z]+n't|(?:I'm|we're|we've|we'll|we'd|it's))\b",
        " ".join(blocks), flags=re.IGNORECASE)
    problems = []
    if long_sentences:
        problems.append("reader sentence exceeds 35 words: " +
                        repr(long_sentences))
    if banned_hits:
        problems.append("banned reader words present: " + repr(banned_hits))
    if contractions:
        problems.append("reader contractions present: " +
                        repr(sorted(set(contractions))))
    if "!" in " ".join(blocks):
        problems.append("reader prose contains an exclamation mark")
    if problems:
        raise SystemExit("reader prose failure: " + "; ".join(problems))


def load_configs():
    columns = []
    source_columns = []
    for source in SOURCES:
        relative = source["path"]
        path = os.path.join(EXP, relative)
        if not os.path.isfile(path):
            raise SystemExit("missing input: " + relative)
        with open(path, newline="", encoding="utf-8") as handle:
            fields = list(csv.DictReader(handle).fieldnames or [])
        source_columns.append(fields)
        for column in fields:
            if column not in columns:
                columns.append(column)

    numeric_rows, raw_rows, row_ids, sources = [], [], [], []
    for source, fields in zip(SOURCES, source_columns):
        relative, run = source["path"], source["run"]
        path = os.path.join(EXP, relative)
        with open(path, newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            source_count = included_count = 0
            excluded = {}
            for source_row, record in enumerate(reader, start=2):
                source_count += 1
                receiver = record["algorithm_id"]
                if receiver not in source["include"]:
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
            "source_columns": fields,
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


def _winner_tuple(result):
    """JCM-151b: rate, then lower pooled BER, then lower decode time."""
    return (
        result["mean_effective_rate_bps"],
        -result["ber"],
        -result["mean_decode_seconds"],
    )


def _selection_reason_counts(text):
    counts = {}
    for item in filter(None, text.split(";")):
        name, separator, value = item.partition(":")
        if not separator:
            raise SystemExit("invalid selection_reasons cell: " + text)
        counts[name] = counts.get(name, 0) + int(value)
    return counts


def build_results_view_data(columns, rows):
    index = {column: i for i, column in enumerate(columns)}
    groups = defaultdict(list)
    for row in rows:
        config = tuple(row[index[key]] for key in CONFIG_KEYS)
        key = (
            row[index["channel"]], row[index["lane"]],
            row[index["algorithm_id"]], config,
        )
        groups[key].append(row)

    finalists = defaultdict(list)
    problems = []
    for (channel, hydrophone, receiver, config), confirmed in groups.items():
        seeds = {row[index["seed"]] for row in confirmed}
        if len(confirmed) != 2 or seeds != {6, 7}:
            problems.append(
                f"{channel} hydrophone {hydrophone} {receiver} {config} "
                "does not contain seeds 6 and 7 exactly once"
            )
            continue
        attempted_bits = sum(row[index["payload_bits"]] for row in confirmed)
        summary = {
            "algorithm_id": receiver,
            **dict(zip(CONFIG_KEYS, config)),
            "mean_effective_rate_bps": sum(
                row[index["effective_rate_bps"]] for row in confirmed
            ) / 2,
            "min_effective_rate_bps": min(
                row[index["effective_rate_bps"]] for row in confirmed
            ),
            "mean_psr": sum(row[index["psr"]] for row in confirmed) / 2,
            "ber": (
                sum(row[index["bit_errors"]] for row in confirmed) /
                attempted_bits if attempted_bits else 0.0
            ),
            "mean_decode_seconds": sum(
                row[index["decode_seconds"]] for row in confirmed
            ) / 2,
            "confirmation_seeds": [6, 7],
        }
        finalists[(channel, hydrophone, receiver)].append(summary)

    paths = []
    receiver_order = [
        "ofdm_fec", "lite", "pfft", "cz_refinement", "joint_cwz",
    ]
    channel_hydrophones = sorted({(key[0], key[1]) for key in finalists})
    for channel, hydrophone in channel_hydrophones:
        receiver_results = []
        for receiver in receiver_order:
            candidates = finalists.get((channel, hydrophone, receiver), [])
            if len(candidates) != 4:
                problems.append(
                    f"{channel} hydrophone {hydrophone} {receiver} has "
                    f"{len(candidates)} confirmed finalists, expected 4"
                )
                continue
            receiver_results.append(max(candidates, key=_winner_tuple))
        if len(receiver_results) != len(receiver_order):
            continue
        ranked = sorted(receiver_results, key=_winner_tuple, reverse=True)
        highest_rate = ranked[0]["mean_effective_rate_bps"]
        paths.append({
            "channel": channel,
            "hydrophone": hydrophone,
            "label": f"{channel} hydrophone {hydrophone}",
            "winner": ranked[0],
            "rate_tie_ids": [
                result["algorithm_id"] for result in ranked
                if result["mean_effective_rate_bps"] == highest_rate
            ],
            "receiver_results": receiver_results,
        })

    mechanism = {}
    for receiver in ("lite", "cz_refinement", "joint_cwz"):
        selected = accepted = rejected = total_frames = 0
        weighted_seconds = 0.0
        reasons = {}
        receiver_rows = [
            row for row in rows if row[index["algorithm_id"]] == receiver
        ]
        for row in receiver_rows:
            frame_count = row[index["frames"]]
            total_frames += frame_count
            weighted_seconds += row[index["decode_seconds"]] * frame_count
            selected_value = row[index["refinement_selected_frames"]]
            accepted_value = row[index["joint_cwz_accepted_steps"]]
            rejected_value = row[index["joint_cwz_rejected_steps"]]
            selected += int(selected_value or 0)
            accepted += int(accepted_value or 0)
            rejected += int(rejected_value or 0)
            for name, count in _selection_reason_counts(
                    str(row[index["selection_reasons"]] or "")).items():
                reasons[name] = reasons.get(name, 0) + count
        mechanism[receiver] = {
            "confirmed_frames": total_frames,
            "refinement_selected_frames": selected,
            "joint_cwz_accepted_steps": accepted,
            "joint_cwz_rejected_steps": rejected,
            "selection_reasons": reasons,
            "mean_decode_seconds_per_frame": (
                weighted_seconds / total_frames if total_frames else 0.0
            ),
        }

    if problems:
        raise SystemExit("five-arm ranking failure: " + "; ".join(problems))
    wins = {receiver: 0 for receiver in receiver_order}
    for path in paths:
        wins[path["winner"]["algorithm_id"]] += 1
    return {
        "schema_version": 2,
        "ranking_tuple": [
            "mean_effective_rate_bps", "lower_pooled_ber",
            "lower_mean_decode_seconds",
        ],
        "wins": wins,
        "mechanism": mechanism,
        "paths": paths,
    }


def validate_confirmation_evidence(winners):
    for path in (CONFIRMATION_MANIFEST_PATH, RANKING_REFERENCE_PATH):
        if not os.path.isfile(path):
            raise SystemExit("missing input: " + os.path.relpath(path, EXP))
    with open(CONFIRMATION_MANIFEST_PATH, encoding="utf-8") as handle:
        evidence = json.load(handle)
    with open(RANKING_REFERENCE_PATH, encoding="utf-8") as handle:
        reference = json.load(handle)

    problems = []
    for file_key in ("confirmation_csv", "ranking"):
        record = evidence["files"][file_key]
        path = os.path.join(CONFIRMATION_DIR, record["path"])
        if not os.path.isfile(path) or _sha256(path) != record["sha256"]:
            problems.append(f"{file_key} hash differs from confirmation manifest")
    if set(reference["receiver_ids"]) != EXPECTED_RECEIVERS:
        problems.append("ranking-reference receiver IDs differ")
    if reference["winner_counts"] != winners["wins"]:
        problems.append("ranking-reference winner counts differ")

    computed_paths = {
        (path["channel"], path["hydrophone"]): path
        for path in winners["paths"]
    }
    for reference_path in reference["paths"]:
        key = (reference_path["channel"], reference_path["hydrophone"])
        computed = computed_paths.get(key)
        if computed is None:
            problems.append(f"ranking-reference result missing for {key}")
            continue
        if reference_path["winner_id"] != computed["winner"]["algorithm_id"]:
            problems.append(f"ranking-reference winner differs for {key}")
        if reference_path["rate_tie_ids"] != computed["rate_tie_ids"]:
            problems.append(f"ranking-reference rate tie differs for {key}")
        computed_results = {
            result["algorithm_id"]: result
            for result in computed["receiver_results"]
        }
        for reference_result in reference_path["receiver_results"]:
            receiver = reference_result["receiver_id"]
            result = computed_results.get(receiver)
            if result is None:
                problems.append(f"ranking-reference receiver {receiver} missing for {key}")
                continue
            expected_values = {
                "mean_effective_rate_bps": result["mean_effective_rate_bps"],
                "minimum_effective_rate_bps": result["min_effective_rate_bps"],
                "mean_packet_success_rate": result["mean_psr"],
                "pooled_ber": result["ber"],
                "mean_decode_seconds_per_frame": result["mean_decode_seconds"],
            }
            if reference_result["configuration"] != {
                    key: result[key] for key in CONFIG_KEYS}:
                problems.append(
                    f"ranking-reference configuration differs for {key} {receiver}")
            for field, value in expected_values.items():
                if reference_result[field] != value:
                    problems.append(
                        f"ranking-reference {field} differs for {key} {receiver}")

    if problems:
        raise SystemExit("confirmation evidence failure: " + "; ".join(problems))
    winners["provenance"] = {
        "manifest_path": os.path.relpath(CONFIRMATION_MANIFEST_PATH, EXP),
        "manifest_sha256": _sha256(CONFIRMATION_MANIFEST_PATH),
        "historical_run": evidence["historical_run"],
        "limitations": evidence["limitations"],
    }
    return evidence


def validate_payload(columns, rows, raw_rows, row_ids, manifest, winners):
    index = {column: i for i, column in enumerate(columns)}
    problems = []
    if len(rows) != 480:
        problems.append(f"expected 480 rows, found {len(rows)}")
    if not (len(rows) == len(raw_rows) == len(row_ids)):
        problems.append("numeric rows, source rows, and row IDs differ")
    if len(set(row_ids)) != len(row_ids):
        problems.append("row IDs are not unique")
    receivers = {row[index["algorithm_id"]] for row in rows}
    if receivers != EXPECTED_RECEIVERS:
        problems.append(f"receiver set differs: {sorted(receivers)}")
    receiver_counts = {
        receiver: sum(row[index["algorithm_id"]] == receiver for row in rows)
        for receiver in receivers
    }
    if set(receiver_counts.values()) != {96}:
        problems.append(f"receiver row counts differ: {receiver_counts}")
    if {row[index["frames"]] for row in rows} != {60}:
        problems.append("a retained row is not a 60-frame confirmation")
    if {row[index["seed"]] for row in rows} != {6, 7}:
        problems.append("confirmation seeds are not exactly 6 and 7")
    if any(row[index["decode_failures"]] != 0 for row in rows):
        problems.append("a retained row has a decode failure")
    if sum(row[index["psr"]] == 0 for row in rows) != 143:
        problems.append("zero-packet-success row count differs from 143")
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
    actual_winners = {
        (path["channel"], path["hydrophone"]):
            path["winner"]["algorithm_id"]
        for path in winners["paths"]
    }
    if actual_winners != EXPECTED_WINNERS:
        problems.append(f"confirmed-winner tuple differs: {actual_winners}")
    actual_ties = {
        (path["channel"], path["hydrophone"]): path["rate_tie_ids"]
        for path in winners["paths"] if len(path["rate_tie_ids"]) > 1
    }
    if actual_ties != EXPECTED_RATE_TIES:
        problems.append(f"mean-rate tie provenance differs: {actual_ties}")
    cz_mechanism = winners["mechanism"]["cz_refinement"]
    joint_mechanism = winners["mechanism"]["joint_cwz"]
    if cz_mechanism["refinement_selected_frames"] != 14:
        problems.append("C,z refinement selected-frame count differs")
    if cz_mechanism["selection_reasons"] != {
            "crc_rescue": 14, "lite_crc_valid_skip": 891,
            "crc_fallback": 4855}:
        problems.append("C,z refinement selection-reason counts differ")
    if joint_mechanism["refinement_selected_frames"] != 17:
        problems.append("joint C,W,z selected-frame count differs")
    if joint_mechanism["selection_reasons"] != {
            "crc_rescue": 17, "lite_crc_valid_skip": 891,
            "crc_fallback": 4852}:
        problems.append("joint C,W,z selection-reason counts differ")
    if (joint_mechanism["joint_cwz_accepted_steps"],
            joint_mechanism["joint_cwz_rejected_steps"]) != (38952, 0):
        problems.append("joint C,W,z call-level step counts differ")
    if problems:
        raise SystemExit("results completeness failure: " + "; ".join(problems))


def render():
    columns, rows, raw_rows, row_ids, sources = load_configs()
    winners = build_results_view_data(columns, rows)
    confirmation_evidence = validate_confirmation_evidence(winners)
    index = {column: i for i, column in enumerate(columns)}
    paths = sorted({
        (row[index["channel"]], row[index["lane"]]) for row in rows
    })
    covered = coverage(columns, rows)
    manifest = {
        "schema_version": 2,
        "experiment_id": EXPERIMENT_ID,
        "result_scope": "60-frame confirmation",
        "row_count": len(rows),
        "receiver_ids": sorted(EXPECTED_RECEIVERS),
        "ranking_tuple": winners["ranking_tuple"],
        "columns": columns,
        "display_columns": DISPLAY_COLUMNS,
        "coverage": covered,
        "sources": sources,
        "confirmation_evidence": {
            "path": os.path.relpath(CONFIRMATION_MANIFEST_PATH, EXP),
            "sha256": _sha256(CONFIRMATION_MANIFEST_PATH),
            "artifact_id": confirmation_evidence["artifact_id"],
            "historical_run": confirmation_evidence["historical_run"],
            "limitations": confirmation_evidence["limitations"],
        },
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
    validate_payload(columns, rows, raw_rows, row_ids, manifest, winners)
    with open(os.path.join(HERE, "view_template.html"), encoding="utf-8") as handle:
        template = handle.read()
    validate_reader_prose(template)
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
    return html, manifest, winners


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="fail when generated results are stale")
    args = parser.parse_args()
    html, manifest, winners = render()
    out = os.path.join(HERE, "results_view.html")
    manifest_path = os.path.join(HERE, "results_manifest.json")
    data_path = os.path.join(HERE, "results_view_data.json")
    manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    winners_text = json.dumps(winners, indent=2, sort_keys=True) + "\n"
    if args.check:
        expected = [
            (out, html), (manifest_path, manifest_text),
            (data_path, winners_text),
        ]
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
    with open(data_path, "w", encoding="utf-8") as handle:
        handle.write(winners_text)
    print(f"wrote {out} ({len(html) / 1e6:.2f} MB, "
          f"{manifest['row_count']} configurations)")


if __name__ == "__main__":
    main()
