#!/usr/bin/env python3
"""Fail-closed contract for the approved JCM-386 explanatory note."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
RESULTS = HERE / "frame_results.csv"
MANIFEST = HERE / "demo_manifest.json"
DEMO_CONTRACT = HERE / "demo_contract.py"
BUILDER = HERE / "build_jcm386_figures.py"
TEX = HERE / "jcm386_one_frame_note.tex"
PDF = HERE / "jcm386_one_frame_note.pdf"
TABLE = HERE / "jcm386_results_table.tex"
SUMMARY = HERE / "jcm386_results_summary.tex"
SOURCE_DISCLOSURE = HERE / "jcm386_source_disclosure.tex"
FIGURE_DIR = HERE / "figures"
FIGURES = (
    FIGURE_DIR / "fig1_physical_configuration.pdf",
    FIGURE_DIR / "fig2_bit_error_rate.pdf",
    FIGURE_DIR / "fig3_effective_payload_rate.pdf",
)

TITLE = "Channel, OFDM Configuration, and Receiver Choice: A One-Frame Illustration"
SOURCE_COMMIT = "827bbb217e717291090b014b8aba8ea2df4c6dbf"
ACQUISITION_COMMIT = "261a4418327b2bbef77eeaad9e621d280f4617d3"
DIRECT_SOURCE_SHA256 = "6004c01aac1d98c685f204ac4b065e91af0d6307940dab9444a0b8014d8e7342"
SECTIONS = ("Experiment", "Physical configuration", "Results", "Limits", "Conclusion")
RECEIVERS = {
    "ofdm_fec": "OFDM+LDPC",
    "pfft": "Partial-FFT+LDPC",
    "lite": "JUNA-Iterative",
    "profiled_cz": "profiled JUNA-(C,z)",
    "direct_cz": "JUNA-Direct-(C,z)",
}
CONDITIONS = {
    ("red", 512): 9_600.0,
    ("red", 1024): 9_600.0,
    ("blue", 512): 4_882.8125,
    ("blue", 1024): 4_882.8125,
}
FIELDS = {
    "dataset",
    "channel",
    "hydrophone",
    "configuration",
    "nfft",
    "cp",
    "code_rate",
    "outer_spacing",
    "inner_spacing",
    "partial_fft_bands",
    "snr_db",
    "frame",
    "receiver_id",
    "receiver_label",
    "bandwidth_hz",
    "useful_symbol_seconds",
    "cp_seconds",
    "subcarrier_spacing_hz",
    "frame_duration_seconds",
    "payload_bits",
    "bit_errors",
    "ber",
    "success",
    "configured_rate_bit_per_s_hz",
    "decode_failure",
    "selection_reason",
    "standard_crc_valid",
    "rescue_executed",
    "rescue_crc_valid",
    "gradient_checkpoints",
    "accepted_steps",
    "rejected_steps",
}
BANNED_WORDS = (
    "novel",
    "state-of-the-art",
    "framework",
    "paradigm",
    "leverage",
    "utilize",
    "in order to",
    "crucial",
    "vital",
    "clearly",
    "obviously",
    "it is worth noting",
    "natural",
    "elegant",
    "principled",
    "lifting",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def regular(path: Path) -> None:
    require(path.is_file() and not path.is_symlink(), f"missing regular file: {path}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def integer(row: dict[str, str], field: str) -> int:
    value = float(row[field])
    require(value.is_integer(), f"{field} is not an integer: {row[field]}")
    return int(value)


def close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-11, abs_tol=1e-12)


def read_results() -> list[dict[str, str]]:
    regular(RESULTS)
    with RESULTS.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames is not None, "results header is missing")
        require(FIELDS <= set(reader.fieldnames), f"missing result fields: {sorted(FIELDS - set(reader.fieldnames))}")
        return list(reader)


def validate_provenance() -> None:
    regular(MANIFEST)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    require(manifest.get("correction_approval_id") == "JCM-386", "correction approval ID differs")
    source = manifest.get("source", {})
    require(source.get("commit") == SOURCE_COMMIT, "full source commit differs")
    require(source.get("acquisition_base_commit") == ACQUISITION_COMMIT, "full acquisition commit differs")
    require(source.get("clean") is True, "source tree was not recorded clean")
    identity = manifest.get("direct_receiver_identity", {})
    require(identity.get("public_constructor") == "JunaCore.JunaDirectCzFrame.Modulation", "Direct public constructor differs")
    require(identity.get("concrete_receiver_type") == "JunaCore.Juna.DirectCzFrameModulation", "Direct concrete type differs")
    require(identity.get("descriptor_profile") == "lite", "Direct descriptor profile differs")
    require(identity.get("decode_adapter") == "frame_decode_function", "Direct decode adapter differs")
    require(identity.get("objective_identity") == "direct_cz_frame", "Direct objective identity differs")
    require(identity.get("trace_accessor") == "JunaCore.Juna._direct_cz_last_trace", "Direct trace accessor differs")
    direct_source = Path(identity.get("source_path", ""))
    regular(direct_source)
    require(identity.get("source_sha256") == DIRECT_SOURCE_SHA256, "Direct source hash in manifest differs")
    require(sha256(direct_source) == DIRECT_SOURCE_SHA256, "Direct source file hash differs")


def validate_results(rows: list[dict[str, str]]) -> None:
    require(len(rows) == 20, f"expected 20 receiver rows, found {len(rows)}")
    expected = {
        (dataset, nfft, receiver)
        for dataset, nfft in CONDITIONS
        for receiver in RECEIVERS
    }
    seen: set[tuple[str, int, str]] = set()
    ranks: set[tuple[str, ...]] = set()
    success_sets: set[tuple[str, ...]] = set()

    for row in rows:
        dataset = row["dataset"]
        nfft = integer(row, "nfft")
        receiver = row["receiver_id"]
        key = (dataset, nfft, receiver)
        require(key in expected, f"unexpected result row: {key}")
        require(key not in seen, f"duplicate result row: {key}")
        seen.add(key)

        bandwidth = CONDITIONS[(dataset, nfft)]
        require(row["receiver_label"] == RECEIVERS[receiver], f"{key}: receiver label differs")
        require(integer(row, "hydrophone") == 1, f"{key}: hydrophone differs")
        require(integer(row, "cp") == 64, f"{key}: cyclic-prefix length differs")
        require(integer(row, "outer_spacing") == 6, f"{key}: outer-pilot spacing differs")
        require(integer(row, "inner_spacing") == 8, f"{key}: inner-pilot spacing differs")
        expected_bands = 6 if dataset == "red" else 16
        require(integer(row, "partial_fft_bands") == expected_bands, f"{key}: Partial-FFT band count differs")
        require(close(float(row["code_rate"]), 0.25), f"{key}: code rate differs")
        require(close(float(row["snr_db"]), 20.0), f"{key}: SNR differs")
        require(integer(row, "frame") == 1, f"{key}: frame number differs")
        require(close(float(row["bandwidth_hz"]), bandwidth), f"{key}: bandwidth differs")
        require(close(float(row["useful_symbol_seconds"]), nfft / bandwidth), f"{key}: useful-symbol duration differs")
        require(close(float(row["cp_seconds"]), 64 / bandwidth), f"{key}: cyclic-prefix duration differs")
        require(close(float(row["subcarrier_spacing_hz"]), bandwidth / nfft), f"{key}: subcarrier spacing differs")
        frame_duration = float(row["frame_duration_seconds"])
        require(0 < frame_duration < 1.0, f"{key}: waveform duration is not below one second")

        payload = integer(row, "payload_bits")
        errors = integer(row, "bit_errors")
        require(payload > 0 and 0 <= errors <= payload, f"{key}: bit-error count differs")
        require(close(float(row["ber"]), errors / payload), f"{key}: BER arithmetic differs")
        decode_failure = row["decode_failure"].lower() == "true"
        success = row["success"].lower() == "true"
        require(success == (errors == 0 and not decode_failure), f"{key}: success arithmetic differs")
        expected_rate = payload / bandwidth if success else 0.0
        require(close(float(row["configured_rate_bit_per_s_hz"]), expected_rate), f"{key}: effective-rate arithmetic differs")

    require(seen == expected, "the four-condition receiver grid is incomplete")
    for dataset, nfft in CONDITIONS:
        condition = [row for row in rows if row["dataset"] == dataset and integer(row, "nfft") == nfft]
        ranks.add(tuple(row["receiver_id"] for row in sorted(condition, key=lambda item: (float(item["ber"]), item["receiver_id"]))))
        success_sets.add(tuple(sorted(row["receiver_id"] for row in condition if row["success"].lower() == "true")))
    require(len(ranks) > 1, "receiver BER ordering does not change across the four conditions")
    require(len(success_sets) > 1, "receiver success sets do not change across the four conditions")


def validate_direct_trace(rows: list[dict[str, str]]) -> None:
    indexed = {
        (row["dataset"], integer(row, "nfft"), row["receiver_id"]): row
        for row in rows
    }
    expected_trace = {
        ("red", 512): ("standard_crc_valid", "true", "false", "false", 0, 0, 0),
        ("red", 1024): ("standard_fallback", "false", "true", "false", 8, 8, 0),
        ("blue", 512): ("standard_crc_valid", "true", "false", "false", 0, 0, 0),
        ("blue", 1024): ("standard_crc_valid", "true", "false", "false", 0, 0, 0),
    }
    for condition, expected in expected_trace.items():
        direct = indexed[(*condition, "direct_cz")]
        standard = indexed[(*condition, "ofdm_fec")]
        require(integer(direct, "bit_errors") == integer(standard, "bit_errors"), f"{condition}: Direct does not match OFDM+LDPC")
        observed = (
            direct["selection_reason"],
            direct["standard_crc_valid"].lower(),
            direct["rescue_executed"].lower(),
            direct["rescue_crc_valid"].lower(),
            integer(direct, "gradient_checkpoints"),
            integer(direct, "accepted_steps"),
            integer(direct, "rejected_steps"),
        )
        require(observed == expected, f"{condition}: Direct trace differs")


def validate_tex() -> None:
    regular(TEX)
    regular(SUMMARY)
    regular(SOURCE_DISCLOSURE)
    source = TEX.read_text(encoding="utf-8")
    summary = re.sub(r"\s+", " ", SUMMARY.read_text(encoding="utf-8").lower())
    require(TITLE in source, "approved title is missing")
    positions = []
    for section in SECTIONS:
        token = rf"\section{{{section}}}"
        require(token in source, f"missing approved section: {section}")
        positions.append(source.index(token))
    require(positions == sorted(positions), "approved sections are out of order")
    require(r"\input{jcm386_results_table.tex}" in source, "generated results table is not included")
    require(r"\input{jcm386_results_summary.tex}" in source, "generated condition summary is not included")
    require(r"\input{jcm386_source_disclosure.tex}" in source, "source-history disclosure is not included")
    for figure in FIGURES:
        token = "figures/" + figure.name
        require(token in source, f"figure is not included in TeX: {figure.name}")
    lowered = re.sub(r"\s+", " ", source.lower())
    for phrase in (
        "one frame",
        "rule for selecting a receiver",
        "error floor",
        "cannot establish",
        "six partial-fft bands",
        "16 partial-fft bands",
        "cannot explain the change",
        "configured one-second payload budget",
        "less than one second",
        "results differed between red-1 and blue-1",
    ):
        require(phrase in lowered, f"required evidence limit is missing: {phrase}")
    for word in BANNED_WORDS:
        require(re.search(rf"(?<![A-Za-z]){re.escape(word)}(?![A-Za-z])", lowered) is None, f"banned wording in TeX: {word}")
    for phrase in (
        "matched ofdm+ldpc in all four conditions",
        "retained the ofdm+ldpc (standard) result",
        "cyclic redundancy check (crc)",
        "eight direct steps ran",
        "no crc-valid candidate replaced standard",
        "no direct rescue",
    ):
        require(phrase in summary, f"required Direct interpretation is missing: {phrase}")
    require("/home/" not in source, "TeX contains an absolute local path")


def regenerate_and_compare() -> None:
    regular(BUILDER)
    regular(TABLE)
    regular(SUMMARY)
    regular(SOURCE_DISCLOSURE)
    for figure in FIGURES:
        regular(figure)

    with tempfile.TemporaryDirectory(prefix="jcm386-note-contract-") as temporary:
        root = Path(temporary)
        regenerated_figures = root / "figures"
        regenerated_table = root / TABLE.name
        regenerated_summary = root / SUMMARY.name
        regenerated_disclosure = root / SOURCE_DISCLOSURE.name
        environment = dict(os.environ)
        environment["SOURCE_DATE_EPOCH"] = "0"
        subprocess.run(
            [
                "python3",
                str(BUILDER),
                "--input",
                str(RESULTS),
                "--manifest",
                str(MANIFEST),
                "--output-dir",
                str(regenerated_figures),
                "--table",
                str(regenerated_table),
                "--summary",
                str(regenerated_summary),
                "--disclosure",
                str(regenerated_disclosure),
            ],
            check=True,
            cwd=HERE,
            env=environment,
        )
        require(sha256(regenerated_table) == sha256(TABLE), "generated results table is stale")
        require(sha256(regenerated_summary) == sha256(SUMMARY), "generated condition summary is stale")
        require(sha256(regenerated_disclosure) == sha256(SOURCE_DISCLOSURE), "generated source disclosure is stale")
        for figure in FIGURES:
            regenerated = regenerated_figures / figure.name
            regular(regenerated)
            require(sha256(regenerated) == sha256(figure), f"generated figure is stale: {figure.name}")


def compile_tex() -> None:
    regular(PDF)
    require(shutil.which("latexmk") is not None, "latexmk is unavailable")
    require(shutil.which("pdfinfo") is not None, "pdfinfo is unavailable")
    with tempfile.TemporaryDirectory(prefix="jcm386-tex-contract-") as temporary:
        subprocess.run(
            [
                "latexmk",
                "-pdf",
                "-interaction=nonstopmode",
                "-halt-on-error",
                f"-outdir={temporary}",
                TEX.name,
            ],
            check=True,
            cwd=HERE,
            stdout=subprocess.DEVNULL,
        )
        compiled = Path(temporary) / PDF.name
        regular(compiled)
        require(compiled.stat().st_size > 10_000, "compiled PDF is unexpectedly small")
        information = subprocess.run(
            ["pdfinfo", str(compiled)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        match = re.search(r"^Pages:\s+(\d+)$", information, flags=re.MULTILINE)
        require(match is not None and int(match.group(1)) == 4, "compiled note is not four pages")


def main() -> None:
    regular(DEMO_CONTRACT)
    subprocess.run(["python3", str(DEMO_CONTRACT)], check=True, cwd=HERE)
    validate_provenance()
    rows = read_results()
    validate_results(rows)
    validate_direct_trace(rows)
    regenerate_and_compare()
    validate_tex()
    compile_tex()
    print("JCM386_NOTE_VALID conditions=4 rows=20 figures=3 one_column=true illustration_only=true")


if __name__ == "__main__":
    main()
