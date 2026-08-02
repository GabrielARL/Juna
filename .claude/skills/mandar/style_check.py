#!/usr/bin/env python3
"""Mechanical checks for the house style skill (.claude/skills/mandar/SKILL.md).

Instructions are followed by an agent only if it reads them and chooses to
comply. This script checks the part of the style that a machine can check, so
a violation is caught whether the text was written by a person, by this
model, or by a different tool entirely.

Usage:
    python3 style_check.py FILE.tex [FILE.tex ...]
    python3 style_check.py --list-terms FILE.tex     # terms needing a source

Exit status 0 if every check passes, 1 otherwise.

What this checks (mechanical only):
    banned words, contractions, exclamation marks in prose, sentence length,
    forbidden abstract content (numbers, citations, equations), colon used as
    a logical connective, and mid-sentence "yet" as a pivot.

What this CANNOT check, and a human must:
    whether a term is traceable to a source, whether a deficiency names its
    regime, whether an alternative was granted its virtue before being
    defeated, and whether an equation's following sentence introduces no new
    symbol. Rules R1-R3 of the skill are human-verified by design.
"""
import re
import sys

BANNED = ["novel", "state-of-the-art", "framework", "paradigm", "leverage",
          "utilize", "in order to", "crucial", "vital", "clearly",
          "obviously", "it is worth noting", "natural", "elegant",
          "principled", "lifting"]
CONTRACTIONS = r"\b\w+(?:n't|'re|'ve|'ll|'d)\b|\bisn't\b|\bdon't\b"
MAX_WORDS = 35


def strip_latex(text):
    """Remove comments, math, and LaTeX/Markdown markup so prose can be read."""
    text = re.sub(r"(?<!\\)%.*", "", text)
    # Markdown code blocks and tables are not prose sentences.  Headings and
    # list items are prose, but each begins a new unit and therefore needs a
    # sentence boundary before the length check.
    text = re.sub(r"```.*?```", " BLOCK . ", text, flags=re.S)
    text = re.sub(r"(?m)^\s*\|.*\|\s*$", " . ", text)
    text = re.sub(r"(?m)^\s*(?:[-*+]|\d+\.)\s+", " . ", text)
    text = re.sub(r"(?m)^\s*#{1,6}\s+(.+)$", r" . \1 . ", text)
    # The preamble is configuration, not prose. Nested brace groups in
    # \setbeamertemplate and \tikzset defeat any single-pass macro strip, so
    # drop everything before \begin{document} when there is one.
    body = re.split(r"\\begin\{document\}", text, maxsplit=1)
    if len(body) == 2:
        text = body[1]
    # Keywords are an index, not prose.  Keep section titles for the term
    # inventory, but put boundaries around them so they cannot join the next
    # paragraph into a false long sentence.
    text = re.sub(r"\\begin\{IEEEkeywords\}.*?\\end\{IEEEkeywords\}",
                  " . ", text, flags=re.S)
    text = re.sub(r"\\(?:sub)*section\*?\{([^}]*)\}", r" . \1 . ", text)
    text = re.sub(r"\\(?:begin|end)\{(?:abstract|document)\}", " . ", text)
    # Spacing macros leak their arguments into the prose otherwise.
    text = re.sub(r"\\(?:vspace|hspace|vskip|hskip)\*?\s*\{[^}]*\}", " ", text)
    # Slide rule 3 requires bullets to be fragments with no full stop, which
    # leaves the sentence splitter no boundary and makes a whole frame read as
    # one long sentence. Mark list items and line breaks as boundaries first.
    text = re.sub(r"\\item\b", " . ", text)
    text = re.sub(r"\\\\", " . ", text)
    text = re.sub(r"\\par\b", " . ", text)
    text = re.sub(r"\\(?:begin|end)\{frame\}(\[[^\]]*\])?(\{[^}]*\})?",
                  " . ", text)
    text = re.sub(r"\\(?:begin|end)\{columns?\}(\[[^\]]*\])?(\{[^}]*\})?",
                  " . ", text)
    # A displayed equation ends the sentence that introduces it; the house
    # style then requires a fresh sentence after it. Treat it as a boundary.
    text = re.sub(r"\$\$.*?\$\$", " MATH . ", text, flags=re.S)
    text = re.sub(r"\\\[.*?\\\]", " MATH . ", text, flags=re.S)
    text = re.sub(r"\$[^$]*\$", " MATH ", text)
    text = re.sub(r"\\\(.*?\\\)", " MATH ", text, flags=re.S)
    # Displayed-equation environments also close the sentence that introduces
    # them, so they end with a boundary; floats and code blocks do not.
    for env in ["equation", "align", "gather", "eqnarray"]:
        text = re.sub(r"\\begin\{" + env + r"\*?\}.*?\\end\{" + env + r"\*?\}",
                      " BLOCK . ", text, flags=re.S)
    for env in ["figure", "table", "tabular", "longtable", "algorithm",
                "algorithmic", "lstlisting", "verbatim", "tikzpicture"]:
        text = re.sub(r"\\begin\{" + env + r"\*?\}.*?\\end\{" + env + r"\*?\}",
                      " BLOCK ", text, flags=re.S)
    # Inline code is not prose.  Its operators may contain punctuation such
    # as Julia's !==, and its identifiers belong in the source rather than in
    # the reader-vocabulary inventory.
    text = re.sub(r"\\(?:code|texttt)\s*\{[^}]*\}", " CODE ", text)
    # lstset and friends carry xcolor syntax such as teal!70!black, which the
    # exclamation-mark check would otherwise report as prose.
    text = re.sub(r"\\lst(?:set|definestyle|definelanguage)\s*\{.*?\n\}",
                  " ", text, flags=re.S)
    # Brace groups may be separated by whitespace for alignment, as in
    # \definecolor{paper}    {HTML}{FAF1D8}; allow it so the value does not
    # survive into the prose.
    text = re.sub(r"\\(?:label|ref|eqref|cite|includegraphics|input|usepackage"
                  r"|documentclass|newcommand|hypersetup|setlist|setlength"
                  r"|graphicspath|definecolor|usetikzlibrary|arrayrulecolor"
                  r"|setbeamercolor|setbeamertemplate|usefonttheme"
                  r"|renewcommand|columncolor|rowcolor)\s*(\[[^\]]*\])?"
                  r"(\s*\{[^}]*\})*", " ", text)
    text = re.sub(r"\\[A-Za-z]+\*?", " ", text)
    text = re.sub(r"[{}]", " ", text)
    return text


def abstract_of(text):
    m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", text, re.S)
    return m.group(1) if m else None


def sentences(prose):
    """Split on terminal punctuation.

    A following capital is not required. List items and slide bullets are
    fragments that legitimately begin in lower case, and failing to split
    there reports one long sentence that nobody wrote. Over-splitting only
    shortens the measured sentences, so it can never raise a false alarm on
    the length check.
    """
    prose = re.sub(r"\s+", " ", prose)
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", prose)
            if s.strip()]


def check(path):
    with open(path) as fh:
        raw = fh.read()
    problems = []
    prose = strip_latex(raw)

    for word in BANNED:
        for m in re.finditer(r"\b" + re.escape(word) + r"\b", prose, re.I):
            line = prose[:m.start()].count("\n") + 1
            problems.append(f"banned word '{m.group(0)}' (near prose line {line})")

    for m in re.finditer(CONTRACTIONS, prose):
        problems.append(f"contraction '{m.group(0)}'")

    for m in re.finditer(r"!", prose):
        ctx = prose[max(0, m.start() - 40):m.start() + 10].replace("\n", " ")
        problems.append(f"exclamation mark in prose: ...{ctx.strip()}")

    for s in sentences(prose):
        n = len(s.split())
        if n > MAX_WORDS:
            problems.append(f"sentence of {n} words (limit {MAX_WORDS}): "
                            f"{s[:90]}...")

    for m in re.finditer(r",\s+yet\s+", prose):
        problems.append("mid-sentence 'yet' used as a pivot; start a sentence "
                        "with 'However,'")

    abstract = abstract_of(raw)
    if abstract is not None:
        a_prose = strip_latex(abstract)
        if re.search(r"\d", a_prose):
            problems.append("abstract contains a number")
        if re.search(r"\\cite", abstract):
            problems.append("abstract contains a citation")
        if "MATH" in a_prose or re.search(r"\\begin\{equation", abstract):
            problems.append("abstract contains mathematics")
        for phrase in ["to the best of our knowledge", "state-of-the-art",
                       "first "]:
            if phrase in a_prose.lower():
                problems.append(f"abstract contains '{phrase.strip()}'")
    return problems


def list_terms(path):
    """Print capitalised and hyphenated terms, so a human can confirm each one
    is traceable to a source. This does not decide anything; it only makes the
    manual check of rule R1/R2 practical."""
    with open(path) as fh:
        prose = strip_latex(fh.read())
    terms = set()
    terms |= set(re.findall(r"\b[A-Z]{2,}(?:-[A-Z]+)?\b", prose))
    terms |= set(re.findall(r"\b[a-z]+-[a-z]+(?:-[a-z]+)?\b", prose))
    terms -= {"BLOCK", "CODE", "MATH"}
    print(f"{path}: {len(terms)} terms to confirm against a source")
    for t in sorted(terms):
        print("   ", t)


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    if argv[0] == "--list-terms":
        for p in argv[1:]:
            list_terms(p)
        return 0
    failed = False
    for path in argv:
        problems = check(path)
        if problems:
            failed = True
            print(f"{path}: {len(problems)} issue(s)")
            for p in problems:
                print("   -", p)
        else:
            print(f"{path}: OK")
    if failed:
        print("\nMechanical checks only. Rules R1 (source vocabulary), "
              "R2 (no coined terms) and R3 (explain before writing) are not "
              "checkable here and must be confirmed by a human.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
