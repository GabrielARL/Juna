#!/usr/bin/env python3
"""Build the three JCM-386 figures and numerical results table from CSV."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path


os.environ.setdefault("SOURCE_DATE_EPOCH", "0")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


HERE = Path(__file__).resolve().parent
DEFAULT_INPUT = HERE / "frame_results.csv"
DEFAULT_MANIFEST = HERE / "demo_manifest.json"
DEFAULT_OUTPUT_DIR = HERE / "figures"
DEFAULT_TABLE = HERE / "jcm386_results_table.tex"
DEFAULT_SUMMARY = HERE / "jcm386_results_summary.tex"
DEFAULT_DISCLOSURE = HERE / "jcm386_source_disclosure.tex"

CONDITIONS = (
    ("red", 512, "Red-1"),
    ("red", 1024, "Red-1"),
    ("blue", 512, "Blue-1"),
    ("blue", 1024, "Blue-1"),
)
RECEIVERS = (
    ("ofdm_fec", "OFDM", "OFDM"),
    ("pfft", "PFFT", "PFFT"),
    ("lite", "Iterative", "Iterative"),
    ("profiled_cz", "Profiled", "Profiled"),
    ("direct_cz", "Direct", "Direct"),
)
RECEIVER_COLORS = {
    "ofdm_fec": "#4c72b0",
    "pfft": "#dd8452",
    "lite": "#55a868",
    "profiled_cz": "#c44e52",
    "direct_cz": "#8172b2",
}
CHANNEL_COLORS = {"red": "#c44e52", "blue": "#4c72b0"}
PDF_METADATA = {
    "Title": "JCM-386 one-frame illustration",
    "Author": "",
    "Subject": "",
    "Keywords": "",
    "Creator": "build_jcm386_figures.py",
    "Producer": "Matplotlib",
    "CreationDate": None,
    "ModDate": None,
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--disclosure", type=Path, default=DEFAULT_DISCLOSURE)
    return parser.parse_args()


def read_rows(path: Path) -> list[dict[str, str]]:
    require(path.is_file(), f"missing input CSV: {path}")
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
    require(len(rows) == 20, f"expected 20 rows, found {len(rows)}")
    return rows


def integer(row: dict[str, str], field: str) -> int:
    value = float(row[field])
    require(value.is_integer(), f"{field} is not integral: {row[field]}")
    return int(value)


def index_rows(rows: list[dict[str, str]]) -> dict[tuple[str, int, str], dict[str, str]]:
    indexed: dict[tuple[str, int, str], dict[str, str]] = {}
    for row in rows:
        key = (row["dataset"], integer(row, "nfft"), row["receiver_id"])
        require(key not in indexed, f"duplicate result row: {key}")
        indexed[key] = row
    expected = {
        (dataset, nfft, receiver)
        for dataset, nfft, _ in CONDITIONS
        for receiver, _, _ in RECEIVERS
    }
    require(set(indexed) == expected, "the expected four-condition receiver grid is incomplete")
    return indexed


def read_provenance(path: Path) -> tuple[str, str]:
    require(path.is_file(), f"missing manifest: {path}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    source = manifest.get("source", {})
    identity = manifest.get("direct_receiver_identity", {})
    source_commit = str(source.get("commit", ""))
    acquisition_commit = str(source.get("acquisition_base_commit", ""))
    require(source.get("clean") is True, "manifest does not record a clean source tree")
    require(len(source_commit) == 40, "manifest source commit is not full length")
    require(len(acquisition_commit) == 40, "manifest acquisition commit is not full length")
    require(identity.get("objective_identity") == "direct_cz_frame", "manifest Direct receiver identity differs")
    require(identity.get("public_constructor") == "JunaCore.JunaDirectCzFrame.Modulation", "manifest Direct constructor differs")
    return source_commit, acquisition_commit


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 8.5,
            "axes.titlesize": 9.5,
            "axes.labelsize": 9,
            "xtick.labelsize": 7.5,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.axisbelow": True,
            "axes.grid": True,
            "grid.color": "#d8d8d8",
            "grid.linewidth": 0.55,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def save_pdf(figure: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        path,
        format="pdf",
        bbox_inches="tight",
        pad_inches=0.03,
        metadata=PDF_METADATA,
    )
    plt.close(figure)


def plot_physical_configuration(
    indexed: dict[tuple[str, int, str], dict[str, str]], path: Path
) -> None:
    representative = "ofdm_fec"
    labels = [f"{channel}\n$N={nfft}$" for _, nfft, channel in CONDITIONS]
    useful_ms = [
        1000 * float(indexed[(dataset, nfft, representative)]["useful_symbol_seconds"])
        for dataset, nfft, _ in CONDITIONS
    ]
    cp_ms = [
        1000 * float(indexed[(dataset, nfft, representative)]["cp_seconds"])
        for dataset, nfft, _ in CONDITIONS
    ]
    colors = [CHANNEL_COLORS[dataset] for dataset, _, _ in CONDITIONS]

    figure, axes = plt.subplots(2, 1, figsize=(5.7, 4.0), sharex=True)
    for axis, values, title in (
        (axes[0], useful_ms, "Useful symbol"),
        (axes[1], cp_ms, "Cyclic prefix"),
    ):
        bars = axis.bar(range(4), values, color=colors, width=0.62, edgecolor="#333333", linewidth=0.45)
        axis.set_ylabel("Duration (ms)")
        axis.text(0.01, 0.96, title, transform=axis.transAxes, ha="left", va="top", fontsize=9.5)
        axis.set_ylim(0, max(values) * 1.24)
        axis.grid(axis="x", visible=False)
        for bar, value in zip(bars, values):
            axis.text(
                bar.get_x() + bar.get_width() / 2,
                value + max(values) * 0.025,
                f"{value:.2f}",
                ha="center",
                va="bottom",
                fontsize=8,
            )
    axes[1].set_xticks(range(4), labels)
    figure.subplots_adjust(hspace=0.12)
    save_pdf(figure, path)


def plot_four_panels(
    indexed: dict[tuple[str, int, str], dict[str, str]],
    path: Path,
    field: str,
    ylabel: str,
    label_value,
    figure_height: float = 4.8,
) -> None:
    values = [float(row[field]) for row in indexed.values()]
    upper = max(values)
    upper = (upper * 1.28) if upper > 0 else 1.0
    figure, axes = plt.subplots(2, 2, figsize=(6.3, figure_height), sharex=True, sharey=True)

    for axis, (dataset, nfft, channel) in zip(axes.flat, CONDITIONS):
        condition_rows = [indexed[(dataset, nfft, receiver)] for receiver, _, _ in RECEIVERS]
        condition_values = [float(row[field]) for row in condition_rows]
        bars = axis.bar(
            range(len(RECEIVERS)),
            condition_values,
            color=[RECEIVER_COLORS[receiver] for receiver, _, _ in RECEIVERS],
            width=0.72,
            edgecolor="#333333",
            linewidth=0.4,
        )
        axis.set_title(f"{channel}, $N={nfft}$")
        axis.set_ylim(0, upper)
        axis.grid(axis="x", visible=False)
        axis.set_xticks(range(len(RECEIVERS)), [short for _, short, _ in RECEIVERS], rotation=28, ha="right")
        for bar, row, value in zip(bars, condition_rows, condition_values):
            axis.text(
                bar.get_x() + bar.get_width() / 2,
                value + upper * 0.025,
                label_value(row),
                ha="center",
                va="bottom",
                fontsize=7,
            )
    figure.supylabel(ylabel, x=0.015, fontsize=9)
    figure.subplots_adjust(hspace=0.30, wspace=0.12, bottom=0.16, left=0.15)
    save_pdf(figure, path)


def tex_bold_if_success(row: dict[str, str]) -> str:
    value = str(integer(row, "bit_errors"))
    return rf"\textbf{{{value}}}" if row["success"].lower() == "true" else value


def write_table(
    indexed: dict[tuple[str, int, str], dict[str, str]], path: Path
) -> None:
    lines = [
        "% Generated by build_jcm386_figures.py from frame_results.csv.",
        r"\begin{table}[H]",
        r"\centering",
        r"\caption{Payload bit errors in the one-frame experiment. Bold entries indicate an error-free frame.}",
        r"\label{tab:one-frame-results}",
        r"\setlength{\tabcolsep}{2.2pt}",
        r"\resizebox{\columnwidth}{!}{%",
        r"\begin{tabular}{lrrrrrrr}",
        r"\toprule",
        r"Capture & $N$ & Payload & OFDM & PFFT & Iterative & Profiled & Direct \\",
        r"\midrule",
    ]
    for dataset, nfft, channel in CONDITIONS:
        rows = [indexed[(dataset, nfft, receiver)] for receiver, _, _ in RECEIVERS]
        payloads = {integer(row, "payload_bits") for row in rows}
        require(len(payloads) == 1, f"{dataset}, N={nfft}: payload differs across receivers")
        errors = " & ".join(tex_bold_if_success(row) for row in rows)
        lines.append(f"{channel} & {nfft} & {payloads.pop()} & {errors} " + r"\\")
    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}%",
            r"}",
            r"\end{table}",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def join_labels(labels: list[str]) -> str:
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} and {labels[1]}"
    return ", ".join(labels[:-1]) + f", and {labels[-1]}"


def write_summary(
    indexed: dict[tuple[str, int, str], dict[str, str]], path: Path
) -> None:
    sentences: list[str] = [
        "% Generated by build_jcm386_figures.py from frame_results.csv."
    ]
    for dataset, nfft, channel in CONDITIONS:
        rows = [indexed[(dataset, nfft, receiver)] for receiver, _, _ in RECEIVERS]
        payloads = {integer(row, "payload_bits") for row in rows}
        require(len(payloads) == 1, f"{dataset}, N={nfft}: payload differs across receivers")
        payload = payloads.pop()
        successful = [row["receiver_label"] for row in rows if row["success"].lower() == "true"]
        failed = [row for row in rows if row["success"].lower() != "true"]
        prefix = rf"At {channel} with $N={nfft}$,"
        if not successful:
            sentences.append(f"{prefix} no receiver decoded the {payload}-bit payload without an error.")
        elif len(successful) == len(rows):
            sentences.append(f"{prefix} all five receivers decoded the {payload}-bit payload without an error.")
        else:
            sentences.append(
                f"{prefix} {join_labels(successful)} decoded the {payload}-bit payload without an error."
            )
        if failed:
            labels = [row["receiver_label"] for row in failed]
            counts = [str(integer(row, "bit_errors")) for row in failed]
            if len(failed) == 1:
                sentences.append(f"The error count was {counts[0]} for {labels[0]}.")
            else:
                sentences.append(
                    f"The error counts were {join_labels(counts)} for {join_labels(labels)}, respectively."
                )
    direct_rows = {
        (dataset, nfft): indexed[(dataset, nfft, "direct_cz")]
        for dataset, nfft, _ in CONDITIONS
    }
    for dataset, nfft, _ in CONDITIONS:
        direct = direct_rows[(dataset, nfft)]
        standard = indexed[(dataset, nfft, "ofdm_fec")]
        require(
            integer(direct, "bit_errors") == integer(standard, "bit_errors"),
            f"{dataset}, N={nfft}: Direct does not match OFDM+LDPC",
        )
    expected_trace = {
        ("red", 512): ("standard_crc_valid", "true", "false", "false", 0, 0, 0),
        ("red", 1024): ("standard_fallback", "false", "true", "false", 8, 8, 0),
        ("blue", 512): ("standard_crc_valid", "true", "false", "false", 0, 0, 0),
        ("blue", 1024): ("standard_crc_valid", "true", "false", "false", 0, 0, 0),
    }
    for condition, expected in expected_trace.items():
        row = direct_rows[condition]
        observed = (
            row["selection_reason"],
            row["standard_crc_valid"].lower(),
            row["rescue_executed"].lower(),
            row["rescue_crc_valid"].lower(),
            integer(row, "gradient_checkpoints"),
            integer(row, "accepted_steps"),
            integer(row, "rejected_steps"),
        )
        require(observed == expected, f"{condition}: Direct trace differs")
    sentences.extend(
        [
            "JUNA-Direct-(C,z) matched OFDM+LDPC in all four conditions because it retained the OFDM+LDPC (Standard) result.",
            "The Standard result passed the cyclic redundancy check (CRC) in Red-1 at $N=512$ and in both Blue-1 conditions.",
            "In Red-1 at $N=1024$, eight Direct steps ran, but no CRC-valid candidate replaced Standard.",
            "This run therefore contains no Direct rescue.",
        ]
    )
    sentences.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(sentences), encoding="utf-8")


def write_source_disclosure(
    source_commit: str, acquisition_commit: str, path: Path
) -> None:
    lines = [
        "% Generated by build_jcm386_figures.py from demo_manifest.json.",
        "All five receivers use the same clean JunaCore source tree at commit "
        rf"\texttt{{{source_commit[:12]}}}. That tree retains the shared "
        "carrier-offset and duration acquisition from commit "
        rf"\texttt{{{acquisition_commit[:12]}}} and adds the tested Direct "
        r"$C,z$ receiver.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    arguments = parse_args()
    rows = read_rows(arguments.input)
    indexed = index_rows(rows)
    source_commit, acquisition_commit = read_provenance(arguments.manifest)
    configure_style()
    arguments.output_dir.mkdir(parents=True, exist_ok=True)

    plot_physical_configuration(
        indexed, arguments.output_dir / "fig1_physical_configuration.pdf"
    )
    plot_four_panels(
        indexed,
        arguments.output_dir / "fig2_bit_error_rate.pdf",
        "ber",
        "Bit error rate",
        lambda row: str(integer(row, "bit_errors")),
    )
    plot_four_panels(
        indexed,
        arguments.output_dir / "fig3_effective_payload_rate.pdf",
        "configured_rate_bit_per_s_hz",
        "Configured one-second effective payload rate\n(bit s$^{-1}$ Hz$^{-1}$)",
        lambda row: f'{float(row["configured_rate_bit_per_s_hz"]):.3f}',
        figure_height=3.2,
    )
    write_table(indexed, arguments.table)
    write_summary(indexed, arguments.summary)
    write_source_disclosure(source_commit, acquisition_commit, arguments.disclosure)
    print(
        "JCM386_FIGURES_BUILT conditions=4 rows=20 figures=3 table=1 summary=1 disclosure=1 "
        f"input={arguments.input}"
    )


if __name__ == "__main__":
    main()
