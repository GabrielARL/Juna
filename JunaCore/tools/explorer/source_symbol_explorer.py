#!/usr/bin/env python3
"""JunaCore function and symbol explorer.

This is the repository-owned integration of the standalone Symbol Explorer.
The launcher pins it to the package ``JunaCore/src`` tree so its live
inventory, definitions, sources, and inferred call edges always come from the
active checkout.

dep_tracker shows *files/modules* and how they include each other. This shows
*functions* (and structs/consts): what each module defines, which function calls
which, and -- click any function -- its full source and real usage examples.

Two ways to use it:

  # 1) static -- scan a folder, write an HTML you open in a browser
  python3 symbol_explorer.py --repo /path/to/project
  python3 symbol_explorer.py --repo /path/to/project --root src --out sym.html

  # 2) server -- launch once, then load ANY folder from the UI
  python3 symbol_explorer.py --serve              # http://localhost:8754
  python3 symbol_explorer.py --serve --port 9000
  python3 symbol_explorer.py --serve --repo /path # preload a folder

What it understands:
  * one-function-per-file layouts (functions/foo.jl, functions/bar.js) -- the
    whole file is one symbol; the symbol NAME is parsed from the code, not the
    filename (so lwlsc_rls_bang.jl -> lwlsc_rls_bands!).
  * monolithic files (many defs in one .jl/.js) -- each top-level def is a symbol.
  * Julia: function / short-form f(x)=... / struct / @kwdef struct / const / macro
  * JS:    function / async function / const f = (...)=> / const f = function

Call edges: a symbol "calls" another when it references that symbol's name (with
comments/strings stripped first). Same-name calls resolve to the same module when
possible, else fan out. "Used by" = reverse edges = where to find usage examples.
"""
import argparse, json, os, re, sys, threading, webbrowser, http.server
from urllib.parse import urlparse, parse_qs, unquote

SRC_EXT = (".jl", ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs")
EXCLUDE = {".git", "node_modules", "__pycache__", ".venv", "venv", "env",
           "build", "dist", "target", ".mypy_cache", ".pytest_cache",
           ".idea", ".vscode", ".tox", ".next", "results", "figure_data"}
KEYWORDS = {
    "function", "end", "return", "if", "elseif", "else", "for", "while", "do",
    "let", "begin", "struct", "mutable", "const", "macro", "module", "import",
    "using", "export", "quote", "try", "catch", "finally", "where", "in",
    "true", "false", "nothing", "missing", "abstract", "type", "primitive",
    "global", "local", "and", "or", "not", "var", "new", "this", "async",
    "await", "yield", "throw", "typeof", "instanceof", "void", "delete",
    "default", "class", "extends", "super", "null", "undefined",
}


def read(f):
    try:
        return open(f, encoding="utf-8", errors="ignore").read()
    except OSError:
        return ""


def scan_files(root):
    out = []
    for dp, dirs, fs in os.walk(root):
        dirs[:] = [d for d in dirs if d not in EXCLUDE and not d.startswith(".")]
        for fn in fs:
            if fn.endswith(SRC_EXT):
                out.append(os.path.join(dp, fn))
    return out


# ---- definition patterns (matched per line) -------------------------------
JULIA_DEFS = [
    (re.compile(r'^(\s*)module\s+([A-Za-z_]\w*)'), "module"),
    (re.compile(
        r'^(\s*)(?:@[A-Za-z_]\w*\s+)*function\s+'
        r'(?:[A-Za-z_]\w*\.)*([A-Za-z_]\w*!?)'
        r'(?:\s*[({]|\s+(?:where\b|end\b)|\s*$)'
    ), "function"),
    (re.compile(r'^(\s*)(?:Base\.)?@kwdef\s+(?:mutable\s+)?struct\s+([A-Za-z_]\w*)'), "struct"),
    (re.compile(r'^(\s*)(?:mutable\s+)?struct\s+([A-Za-z_]\w*)'), "struct"),
    (re.compile(r'^(\s*)abstract\s+type\s+([A-Za-z_]\w*)'), "type"),
    (re.compile(r'^(\s*)macro\s+([A-Za-z_]\w*)'), "macro"),
    (re.compile(r'^(\s*)const\s+([A-Za-z_]\w*)'), "const"),
    (re.compile(
        r'^(\s*)(?:@[A-Za-z_]\w*\s+)*(?:[A-Za-z_]\w*\.)*'
        r'([A-Za-z_]\w*!?)\s*\(.*\)\s*(?:::[^=]+?)?\s*=(?!=)'
    ), "function"),
]
JS_DEFS = [
    (re.compile(r'^(\s*)(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)\s*\('), "function"),
    (re.compile(r'^(\s*)(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?(?:function\b|\([^)]*\)\s*=>|[A-Za-z_$][\w$]*\s*=>)'), "function"),
    (re.compile(r'^(\s*)(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*='), "const"),
]
JULIA_MODULE = re.compile(r'^\s*module\s+([A-Za-z_]\w*)', re.M)


def _super_of(line):
    """Supertype from `struct X <: Super` / `abstract type X <: Super` (base name)."""
    m = re.search(r'<:\s*([A-Za-z_][\w.]*)', line)
    return m.group(1).split(".")[-1] if m else None


def _qual_of(line):
    """Module qualifier of a `Mod.name(...)` definition (long or short form), e.g. Modulations / Base."""
    m = re.match(r'\s*(?:@\w+\s+)*(?:function\s+)?((?:[A-Za-z_]\w*\.)+)[A-Za-z_]\w*!?\s*\(', line)
    return m.group(1).rstrip(".").split(".")[-1] if m else None


def _first_arg_type(line):
    """Base type of a method's FIRST argument (the dispatch receiver), or None."""
    i = line.find("(")
    if i < 0:
        return None
    depth, arg = 0, []
    for c in line[i + 1:]:
        if c in "([{":
            depth += 1
        elif c in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif c in ",;" and depth == 0:
            break
        arg.append(c)
    m = re.search(r'::\s*([A-Za-z_][\w.]*)', "".join(arg))
    return m.group(1).split(".")[-1] if m else None


def _multiline_julia_short_def(lines, start):
    """Recognize a top-level Julia short-form method whose signature wraps.

    Julia commonly formats these as::

        f(first::T,
          second::U) =
          expression

    The original one-line regex omitted them. Calls are not accepted: after
    the balanced argument list the next token must be the definition ``=``.
    """
    first = lines[start]
    match = re.match(
        r'^(\s*)(?:@[A-Za-z_]\w*\s+)*'
        r'(?:(?:[A-Za-z_]\w*)\.)*([A-Za-z_]\w*!?)\s*\(',
        first,
    )
    if not match:
        return None

    depth = 0
    opened = False
    for offset in range(0, min(40, len(lines) - start)):
        line = lines[start + offset]
        for index, char in enumerate(line):
            if char == "(":
                depth += 1
                opened = True
            elif char == ")" and opened:
                depth -= 1
                if depth == 0:
                    tail = line[index + 1:]
                    if re.match(r'^\s*(?:::[^=]+?)?\s*=(?!=)', tail):
                        signature = " ".join(
                            part.strip() for part in lines[start:start + offset + 1]
                        )
                        return {
                            "line": start + 1,
                            "indent": len(match.group(1)),
                            "name": match.group(2),
                            "kind": "function",
                            "sig": signature,
                            "super": None,
                            "recv": _first_arg_type(signature),
                            "qual": _qual_of(signature),
                        }
                    return None
        if opened and depth == 0:
            return None
    return None


def find_defs(text, lang):
    pats = JULIA_DEFS if lang == "jl" else JS_DEFS
    defs = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        matched = False
        for pat, kind in pats:
            m = pat.match(line)
            if m:
                d = {"line": i + 1, "indent": len(m.group(1)),
                     "name": m.group(2), "kind": kind, "sig": line.strip(),
                     "super": None, "recv": None, "qual": None}
                if lang == "jl":
                    if kind in ("struct", "type"):
                        d["super"] = _super_of(line)
                    elif kind == "function":
                        d["qual"] = _qual_of(line)
                        d["recv"] = _first_arg_type(line)
                defs.append(d)
                matched = True
                break
        if lang == "jl" and not matched:
            multiline = _multiline_julia_short_def(lines, i)
            if multiline is not None:
                defs.append(multiline)
    return defs


def _julia_structural_tokens(text):
    """Yield ``(token, line, bracket_depth)`` outside Julia comments/strings.

    The explorer only needs enough lexical structure to pair a block
    definition with its matching ``end``. Tracking bracket depth avoids
    mistaking generator ``for`` tokens or indexing ``end`` tokens for blocks.
    """
    index = 0
    line = 1
    brackets = 0
    block_comment_depth = 0
    length = len(text)
    while index < length:
        char = text[index]
        if block_comment_depth:
            if text.startswith("#=", index):
                block_comment_depth += 1
                index += 2
            elif text.startswith("=#", index):
                block_comment_depth -= 1
                index += 2
            else:
                line += char == "\n"
                index += 1
            continue
        if text.startswith("#=", index):
            block_comment_depth = 1
            index += 2
            continue
        if char == "#":
            newline = text.find("\n", index)
            if newline < 0:
                break
            index = newline
            continue
        if char in ('"', "`"):
            triple = char == '"' and text.startswith('"""', index)
            delimiter = '"""' if triple else char
            index += len(delimiter)
            while index < length:
                if text.startswith(delimiter, index):
                    index += len(delimiter)
                    break
                if text[index] == "\\" and not triple:
                    if index + 1 < length:
                        line += text[index + 1] == "\n"
                    index += 2
                    continue
                line += text[index] == "\n"
                index += 1
            continue
        if char == "'":
            # Treat a same-line closing quote as a character literal. A lone
            # apostrophe is Julia's adjoint operator and is left as punctuation.
            probe = index + 1
            escaped = False
            while probe < length and text[probe] != "\n":
                if text[probe] == "'" and not escaped:
                    index = probe + 1
                    break
                escaped = text[probe] == "\\" and not escaped
                if text[probe] != "\\":
                    escaped = False
                probe += 1
            else:
                index += 1
            continue
        if char == "\n":
            line += 1
            index += 1
            continue
        if char in "([{":
            brackets += 1
            index += 1
            continue
        if char in ")]}":
            brackets = max(0, brackets - 1)
            index += 1
            continue
        if char.isalpha() or char == "_":
            stop = index + 1
            while stop < length and (
                text[stop].isalnum() or text[stop] in "_!"
            ):
                stop += 1
            yield text[index:stop], line, brackets
            index = stop
            continue
        index += 1


def _julia_block_end(text, start_line, opening_kind):
    """Return the one-based line of a Julia block definition's matching end."""
    expected = "module" if opening_kind == "module" else opening_kind
    openers = {
        "module", "baremodule", "function", "macro", "struct",
        "if", "for", "while", "let", "begin", "try", "quote", "do",
    }
    started = False
    depth = 0
    previous = None
    for token, line, bracket_depth in _julia_structural_tokens(text):
        if line < start_line or bracket_depth:
            continue
        if not started:
            if line > start_line:
                return None
            if token == expected or (
                opening_kind == "module" and token == "baremodule"
            ):
                started = True
                depth = 1
            previous = token
            continue
        if token == "end":
            depth -= 1
            if depth == 0:
                return line
        elif token in openers or (
            token == "type" and previous in ("abstract", "primitive")
        ):
            depth += 1
        previous = token
    return None


def _julia_block_ends(text):
    """Map each structural Julia block opener to its matching end line."""
    pairs = {}
    stack = []
    previous = None
    openers = {
        "module", "baremodule", "function", "macro", "struct",
        "if", "for", "while", "let", "begin", "try", "quote", "do",
    }
    for token, line, bracket_depth in _julia_structural_tokens(text):
        if bracket_depth:
            continue
        if token == "end":
            if stack:
                kind, start = stack.pop()
                pairs[(start, kind)] = line
        elif token in openers:
            kind = "module" if token == "baremodule" else token
            stack.append((kind, line))
        elif token == "type" and previous in ("abstract", "primitive"):
            stack.append(("type", line))
        previous = token
    return pairs


def _mask_julia_noncode(text):
    """Blank Julia comments/literals while preserving line and column counts."""
    def blank(match, keep_value=False):
        chars = ["\n" if char == "\n" else " " for char in match.group(0)]
        if keep_value:
            for index, char in enumerate(chars):
                if char != "\n":
                    chars[index] = "x"
                    break
        return "".join(chars)

    text = re.sub(
        r"#=.*?=#", lambda match: blank(match), text, flags=re.S
    )
    text = re.sub(
        r'(?:[A-Za-z_]\w*)?"""(?:\\.|[^\\])*?"""',
        lambda match: blank(match, keep_value=True),
        text,
        flags=re.S,
    )
    text = re.sub(
        r'"(?:\\.|[^"\\])*"',
        lambda match: blank(match, keep_value=True),
        text,
        flags=re.S,
    )
    text = re.sub(
        r"`(?:\\.|[^`\\])*`",
        lambda match: blank(match, keep_value=True),
        text,
        flags=re.S,
    )
    text = re.sub(
        r"'(?:\\.|[^'\\\n])'",
        lambda match: blank(match, keep_value=True),
        text,
    )
    text = re.sub(r"#[^\n]*", lambda match: blank(match), text)
    return text


def _julia_short_expression_end(
    text, start_line, maximum_line, masked_lines=None, source_lines=None
):
    """Best lexical end line for a Julia short-form function or const.

    The definition ``=`` is recognized only outside its argument delimiters.
    From there, balanced delimiters, explicit ``begin``/``if``-style blocks,
    and trailing operators determine whether the expression continues.
    """
    masked = (
        masked_lines
        if masked_lines is not None
        else _mask_julia_noncode(text).splitlines()
    )
    source = source_lines if source_lines is not None else text.splitlines()
    brackets = 0
    block_depth = 0
    saw_definition_equals = False
    saw_rhs = False
    previous_token = None
    rhs_openers = {
        "begin", "if", "for", "while", "let", "try", "quote", "do",
    }
    continuation = re.compile(
        r"(?:[=+\-*/^%&|<>?:.,\\]|\&\&|\|\|)\s*$"
    )
    for line_index in range(start_line - 1, min(maximum_line, len(masked))):
        code = masked[line_index]
        raw = source[line_index]
        index = 0
        definition_column = None
        while index < len(code):
            char = code[index]
            if char in "([{":
                brackets += 1
                index += 1
                continue
            if char in ")]}":
                brackets = max(0, brackets - 1)
                index += 1
                continue
            if (
                char == "="
                and not saw_definition_equals
                and brackets == 0
                and (index == 0 or code[index - 1] not in "<>!=:.")
                and (index + 1 == len(code) or code[index + 1] not in "=>")
            ):
                saw_definition_equals = True
                definition_column = index
                index += 1
                continue
            if char.isalpha() or char == "_":
                stop = index + 1
                while stop < len(code) and (
                    code[stop].isalnum() or code[stop] in "_!"
                ):
                    stop += 1
                token = code[index:stop]
                if saw_definition_equals and brackets == 0:
                    if token == "end" and block_depth:
                        block_depth -= 1
                    elif token in rhs_openers or (
                        token == "type"
                        and previous_token in ("abstract", "primitive")
                    ):
                        block_depth += 1
                previous_token = token
                index = stop
                continue
            index += 1

        if not saw_definition_equals:
            continue
        raw_rhs = (
            raw[definition_column + 1:]
            if definition_column is not None
            else raw
        )
        code_rhs = (
            code[definition_column + 1:]
            if definition_column is not None
            else code
        )
        if raw_rhs.strip() and not raw_rhs.lstrip().startswith("#"):
            saw_rhs = True
        effective_tail = code_rhs.rstrip()
        if not effective_tail and raw_rhs.strip():
            effective_tail = "value"
        if (
            saw_rhs
            and brackets == 0
            and block_depth == 0
            and not continuation.search(effective_tail)
        ):
            return line_index + 1
    return None


def strip_code(code, lang):
    """Remove comments and string literals so name matching counts real calls."""
    if lang == "jl":
        code = re.sub(r'#=.*?=#', ' ', code, flags=re.S)
        code = re.sub(r'#[^\n]*', ' ', code)
        code = re.sub(r'"(?:\\.|[^"\\])*"', ' ', code, flags=re.S)
        return code
    code = re.sub(r'/\*.*?\*/', ' ', code, flags=re.S)
    code = re.sub(r'//[^\n]*', ' ', code)
    code = re.sub(r'`(?:\\.|[^`\\])*`', ' ', code, flags=re.S)
    code = re.sub(r'"(?:\\.|[^"\\])*"', ' ', code)
    code = re.sub(r"'(?:\\.|[^'\\])*'", ' ', code)
    return code


def lang_of(f):
    return "jl" if f.endswith(".jl") else "js"


def module_of(f, root, lang, text):
    """Group label. Bundle layout (functions/ or parts/) -> the module dir above
    it; included Juna implementation fragments -> Juna; monolithic -> the
    Julia `module` name, else the file stem."""
    parent = os.path.basename(os.path.dirname(f))
    if parent in ("functions", "parts"):
        return os.path.basename(os.path.dirname(os.path.dirname(f)))
    if lang == "jl":
        rel_parts = os.path.relpath(f, root).split(os.sep)
        # Juna.jl includes every src/juna/*.jl fragment inside `module Juna`.
        # Those filenames are source groups, not Julia modules.
        if len(rel_parts) > 1 and rel_parts[0] == "juna":
            return "Juna"
        m = JULIA_MODULE.search(text)
        if m:
            return m.group(1)
    return os.path.splitext(os.path.basename(f))[0]


def definition_module(f, text, default_module, line):
    """Attribute a definition to its nested Julia module when one is explicit.

    JunaCore.jl contains small facade modules at top level. Their exported
    ``Modulation`` aliases must not be collapsed into the outer JunaCore group.
    The facade bodies contain no nested blocks, so the closest declaration
    before the alias is its exact owner. Other source files use their file
    module (or the Juna include owner selected by :func:`module_of`).
    """
    if os.path.basename(f) != "JunaCore.jl":
        return default_module
    declarations = [
        (index, match.group(1))
        for index, source_line in enumerate(text.splitlines(), 1)
        if (match := re.match(r"^\s*module\s+([A-Za-z_]\w*)", source_line))
    ]
    owners = [name for start, name in declarations if start <= line]
    return owners[-1] if owners else default_module


def build_symbols(files, root):
    syms = []   # each: name,kind,module,file,line,sig,src,_strip,_idx
    for f in files:
        text = read(f)
        if not text.strip():
            continue
        lang = lang_of(f)
        rel = os.path.relpath(f, root)
        parent = os.path.basename(os.path.dirname(f))
        mod = module_of(f, root, lang, text)
        defs = find_defs(text, lang)
        lines = text.splitlines()
        bundle = parent in ("functions", "parts")
        block_ends = _julia_block_ends(text) if lang == "jl" else {}
        masked_lines = (
            _mask_julia_noncode(text).splitlines() if lang == "jl" else None
        )

        if bundle or not defs:
            # whole file = one symbol
            if parent == "parts" or not defs:
                name = os.path.splitext(os.path.basename(f))[0]
                kind = "part" if parent == "parts" else "file"
                sig = name
                line = 1
                d0 = None
            else:
                d0 = defs[0]
                name, kind, sig, line = d0["name"], d0["kind"], d0["sig"], d0["line"]
            syms.append({"name": name, "kind": kind, "module": mod, "file": rel,
                         "line": line, "sig": sig, "src": text,
                         "super": d0["super"] if d0 else None,
                         "recv": d0["recv"] if d0 else None,
                         "qual": d0["qual"] if d0 else None,
                         "also": sorted({d["name"] for d in defs} - {name})})
        else:
            # JunaCore.jl keeps its facade aliases indented inside explicit
            # child modules. Preserve those definitions alongside the module
            # declarations so the facade inventory remains complete.
            top = (
                defs
                if os.path.basename(f) == "JunaCore.jl"
                else ([d for d in defs if d["indent"] == 0] or defs)
            )
            for j, d in enumerate(top):
                start = d["line"]
                end = top[j + 1]["line"] - 1 if j + 1 < len(top) else len(lines)
                block_kind = None
                if lang == "jl":
                    if d["kind"] in ("module", "struct", "type", "macro"):
                        block_kind = d["kind"]
                    elif (
                        d["kind"] == "function"
                        and re.search(r"\bfunction\b", lines[start - 1])
                    ):
                        block_kind = "function"
                if block_kind is not None:
                    block_end = block_ends.get((start, block_kind))
                    if block_end is not None:
                        end = block_end
                elif lang == "jl" and d["kind"] in ("function", "const"):
                    expression_end = _julia_short_expression_end(
                        text, start, end, masked_lines, lines
                    )
                    if expression_end is not None:
                        end = expression_end
                src = "\n".join(lines[start - 1:end]).rstrip()
                owner = definition_module(f, text, mod, start)
                syms.append({"name": d["name"], "kind": d["kind"], "module": owner,
                             "file": rel, "line": start, "sig": d["sig"], "src": src,
                             "super": d["super"], "recv": d["recv"], "qual": d["qual"],
                             "also": []})
    for i, s in enumerate(syms):
        s["id"] = i
        # Module bodies contain definitions, not calls made by a function.
        # Keeping their full source for inspection while excluding it from the
        # lexical call scan avoids invented module-to-every-child call edges.
        s["_strip"] = (
            "" if s["kind"] == "module"
            else strip_code(s["src"], lang_of(s["file"]))
        )
    return syms


WORD = re.compile(r'[A-Za-z_$][\w$]*!?')


def link_symbols(syms):
    name2ids = {}
    for s in syms:
        name2ids.setdefault(s["name"], []).append(s["id"])
    for s in syms:
        toks = set(WORD.findall(s["_strip"]))
        calls = set()
        for t in toks:
            if t == s["name"] or t in KEYWORDS or len(t) < 3:
                continue
            cand = name2ids.get(t)
            if not cand:
                continue
            same = [c for c in cand if syms[c]["module"] == s["module"]]
            for c in (same or cand):
                if c != s["id"]:
                    calls.add(c)
        s["calls"] = sorted(calls)
    callers = {s["id"]: set() for s in syms}
    for s in syms:
        for c in s["calls"]:
            callers[c].add(s["id"])
    for s in syms:
        s["callers"] = sorted(callers[s["id"]])


def add_examples(syms, cap=8):
    by_id = {s["id"]: s for s in syms}
    for s in syms:
        ex = []
        pat = re.compile(r'\b' + re.escape(s["name"].rstrip("!")) + r'!?\b')
        for cid in s["callers"]:
            caller = by_id[cid]
            for k, line in enumerate(caller["src"].splitlines(), caller["line"]):
                if pat.search(line):
                    ex.append({"from": cid, "lineno": k, "text": line.strip()[:200]})
                    break
            if len(ex) >= cap:
                break
        s["examples"] = ex


MAX_FILES = 4000   # guard against accidentally scanning a giant tree


def _clean_tex(s):
    """Strip LaTeX commands/braces/math from a macro argument, leaving plain text."""
    s = re.sub(r'\\[A-Za-z]+\s*', ' ', s)          # drop \code, \detokenize, \texttt, ...
    s = s.replace('{', ' ').replace('}', ' ').replace('$', ' ').replace('\\', ' ')
    return re.sub(r'\s+', ' ', s).strip()


def _macro_args(text, start, n):
    """Read n consecutive balanced {..} groups starting at/after `start`."""
    args, i, L = [], start, len(text)
    for _ in range(n):
        while i < L and text[i] in " \t\r\n":
            i += 1
        if i >= L or text[i] != "{":
            return None
        depth, j = 0, i
        while j < L:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if j >= L:
            return None
        args.append(text[i + 1:j])
        i = j + 1
    return args


def parse_walkthrough(text):
    """Parse \\fnslide{file}{name}{role}{reads}{returns} and \\objslide{...} macros
    into {(file_basename, symbol_name): {kind, a, b, c}}."""
    ann = {}
    for m in re.finditer(r'\\(fnslide|objslide)\b', text):
        args = _macro_args(text, m.end(), 5)
        if not args:
            continue
        f, name = _clean_tex(args[0]), _clean_tex(args[1])
        key = (os.path.basename(f), name.split(".")[-1])
        ann[key] = {"kind": "obj" if m.group(1) == "objslide" else "fn",
                    "a": _clean_tex(args[2]), "b": _clean_tex(args[3]), "c": _clean_tex(args[4])}
    return ann


def load_annotations(folder):
    """Find a *walkthrough*.tex (or annotations.json) in `folder` and parse it."""
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return {}, None
    for fn in names:
        if re.search(r'walkthrough.*\.tex$', fn, re.I):
            return parse_walkthrough(read(os.path.join(folder, fn))), fn
    if "annotations.json" in names:
        try:
            data = json.loads(read(os.path.join(folder, "annotations.json")))
            ann = {(os.path.basename(d["file"]), d["name"].split(".")[-1]):
                   {"kind": d.get("kind", "fn"), "a": d.get("role", ""),
                    "b": d.get("reads", ""), "c": d.get("returns", "")} for d in data}
            return ann, "annotations.json"
        except Exception:
            return {}, None
    return {}, None


def analyze(folder):
    folder = os.path.abspath(folder)
    files = scan_files(folder)
    if not files:
        raise ValueError(f"no source files ({', '.join(SRC_EXT)}) found under {folder}")
    total = len(files)
    truncated = 0
    if total > MAX_FILES:                       # cap, but report it -- never silently drop
        files = sorted(files)[:MAX_FILES]
        truncated = total - MAX_FILES
    syms = build_symbols(files, folder)
    if not syms:
        raise ValueError(f"found {total} source files but parsed no source definitions under {folder}")
    link_symbols(syms)
    add_examples(syms)
    ann, ann_src = load_annotations(folder)
    documented = 0
    for s in syms:
        s["doc"] = ann.get((os.path.basename(s["file"]), s["name"]))
        if s["doc"]:
            documented += 1
    mods = {}
    for s in syms:
        mods.setdefault(s["module"], 0)
        mods[s["module"]] += 1
    modules = [{"name": k, "count": v} for k, v in sorted(mods.items(), key=lambda kv: (-kv[1], kv[0]))]
    nedges = sum(len(s["calls"]) for s in syms)
    out = [{k: s[k] for k in ("id", "name", "kind", "module", "file", "line", "sig", "src",
                               "calls", "callers", "examples", "also", "doc",
                               "super", "recv", "qual")}
           for s in syms]
    stats = {"symbols": len(syms), "modules": len(modules), "edges": nedges,
             "files": len({s["file"] for s in syms}), "scanned": len(files),
             "total_files": total, "truncated": truncated,
             "documented": documented, "doc_source": ann_src or ""}
    return {"root": folder, "symbols": out, "modules": modules, "stats": stats}


def vis_script():
    """Inline the vendored vis-network so the UI works offline; fall back to CDN."""
    vendor = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor", "vis-network.min.js")
    if os.path.isfile(vendor) and os.path.getsize(vendor) > 0:
        js = read(vendor).replace("</script>", "<\\/script>")
        return "<script>/* vendored vis-network (offline-safe) */\n" + js + "\n</script>"
    return ('<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>')


def render_html(serve, data, default_repo="", locked=False):
    cfg = {"serve": serve, "data": data, "defaultRepo": default_repo,
           "locked": locked, "lockedRoot": default_repo if locked else "",
           # Cross-link target for the standalone page; when the same page is
           # served inside the workbench at /source, its shared nav rules and
           # these links stay hidden.
           "workbench": os.environ.get(
               "JUNA_WORKBENCH_URL", "http://127.0.0.1:8771")}
    # Escape "<"/">" so scanned source containing "</script>" cannot terminate the inline <script>.
    cfgjson = json.dumps(cfg).replace("<", r"\u003c").replace(">", r"\u003e")
    page = HTML.replace("/*CONFIG*/", cfgjson)
    return page.replace("<!--VISLIB-->", vis_script())


def pick_folder():
    import subprocess, shutil
    start = os.path.expanduser("~")
    try:
        if shutil.which("zenity"):
            r = subprocess.run(["zenity", "--file-selection", "--directory",
                                "--title=Select project folder", f"--filename={start}/"],
                               capture_output=True, text=True, timeout=600)
            return {"path": r.stdout.strip()} if r.returncode == 0 and r.stdout.strip() else {"cancelled": True}
        if shutil.which("kdialog"):
            r = subprocess.run(["kdialog", "--getexistingdirectory", start],
                               capture_output=True, text=True, timeout=600)
            return {"path": r.stdout.strip()} if r.returncode == 0 and r.stdout.strip() else {"cancelled": True}
        import tkinter, tkinter.filedialog
        root = tkinter.Tk(); root.withdraw()
        p = tkinter.filedialog.askdirectory()
        root.destroy()
        return {"path": p} if p else {"cancelled": True}
    except Exception as e:
        return {"error": f"folder picker unavailable: {e}"}


def serve(port, default_repo, locked=False, open_browser=True):
    page = render_html(True, None, default_repo, locked=locked)
    locked_root = os.path.abspath(default_repo) if locked else None

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, ctype, body):
            b = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(b)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            u = urlparse(self.path)
            if u.path == "/":
                self._send(200, "text/html; charset=utf-8", page)
            elif u.path == "/api/restart":
                self._send(200, "application/json", '{"ok":true}')
                threading.Timer(0.3, lambda: os.execv(
                    sys.executable, [sys.executable, os.path.abspath(__file__)] + sys.argv[1:])).start()
            elif u.path == "/api/pick":
                if locked_root:
                    self._send(200, "application/json", json.dumps({"error": "locked to the project root"}))
                else:
                    self._send(200, "application/json", json.dumps(pick_folder()))
            elif u.path == "/api/scan":
                q = parse_qs(u.query)
                p = locked_root or unquote(q.get("path", [""])[0]).strip()
                try:
                    if not p:
                        raise ValueError("no folder given")
                    p = os.path.expanduser(p)
                    if not os.path.isdir(p):
                        raise ValueError(f"not a folder: {p}")
                    self._send(200, "application/json", json.dumps(analyze(p)))
                except Exception as e:
                    self._send(400, "application/json", json.dumps({"error": str(e)}))
            else:
                self._send(404, "text/plain", "not found")

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), H)
    url = f"http://127.0.0.1:{port}"
    print(f"JunaCore source definition explorer -> {url}   root={default_repo}   (Ctrl-C to stop)")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


HTML = r"""<!doctype html><html><head><meta charset="utf-8"><title>JunaCore source definition explorer</title>
<!--VISLIB-->
<style>
 :root{--bg:#0f172a;--panel:#1e293b;--ink:#e2e8f0;--mut:#94a3b8;--acc:#38bdf8;--line:#334155}
 *{box-sizing:border-box} body{margin:0;font:14px/1.4 system-ui,sans-serif;background:var(--bg);color:var(--ink);height:100vh;display:flex;flex-direction:column}
 #bar{display:flex;gap:8px;align-items:center;padding:8px 12px;background:#0b1220;border-bottom:1px solid var(--line)}
 #bar input{padding:7px;background:#0f172a;color:var(--ink);border:1px solid var(--line);border-radius:6px}
 #path{flex:1;min-width:200px}
 #bar button{padding:7px 12px;background:#1e293b;color:var(--ink);border:1px solid var(--line);border-radius:6px;cursor:pointer}
 #bar button:hover{border-color:#64748b} #msg{color:#f87171;font-size:12px}
 #wrap{flex:1;display:flex;min-height:0}
 #side{width:270px;flex:0 0 270px;background:var(--panel);padding:12px;overflow:auto;border-right:1px solid var(--line)}
 #net{flex:1;min-width:0} #detail{width:430px;flex:0 0 430px;background:#0b1220;border-left:1px solid var(--line);overflow:auto;padding:14px}
 h1{font-size:15px;margin:0} h2{font-size:11px;text-transform:uppercase;color:var(--mut);margin:14px 0 6px;letter-spacing:.06em}
 .stat{display:flex;justify-content:space-between;padding:2px 0;border-bottom:1px solid var(--line)} .stat b{font-variant-numeric:tabular-nums}
 #q{width:100%;padding:7px;margin:4px 0;background:#0f172a;color:var(--ink);border:1px solid var(--line);border-radius:6px}
 #side button{width:100%;padding:6px;margin:3px 0;background:#0f172a;color:var(--ink);border:1px solid var(--line);border-radius:6px;cursor:pointer;text-align:left}
 #side .tg{width:auto;flex:1;padding:5px 6px;font-size:11px;text-align:center}
 #side .tg.on{outline:1px solid var(--acc);color:#fff;background:#0b2536;border-color:var(--acc)}
 .mod{display:flex;align-items:center;gap:7px;padding:3px 5px;border-radius:4px;font-size:12px;cursor:pointer}
 .mod:hover{background:#334155} .mod.on{background:#334155;outline:1px solid var(--acc)}
 .mod .c{display:flex;justify-content:space-between;flex:1} .mod .n{color:#cbd5e1} .mod .ct{color:var(--mut);font-variant-numeric:tabular-nums}
 .dot{width:11px;height:11px;border-radius:50%;flex:0 0 11px}
 #hits{font-size:12px;max-height:240px;overflow:auto} #hits div{padding:2px 5px;cursor:pointer;border-radius:4px;color:#cbd5e1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
 #hits div:hover{background:#334155} #hits .k{color:var(--mut)}
 #detail h3{margin:0 0 2px;font-size:16px} #detail .meta{color:var(--mut);font-size:12px;margin-bottom:8px;word-break:break-all}
 .kind{display:inline-block;font-size:10px;padding:1px 6px;border-radius:9px;background:#0f172a;border:1px solid var(--line);color:var(--mut);margin-left:6px;vertical-align:middle}
 pre{background:#0f172a;border:1px solid var(--line);border-radius:8px;padding:10px;overflow:auto;font:12px/1.45 ui-monospace,Menlo,Consolas,monospace;color:#e2e8f0;white-space:pre;max-height:46vh}
 .chips{display:flex;flex-wrap:wrap;gap:5px;margin:4px 0 2px}
 .chip{font-size:12px;padding:2px 9px;border-radius:12px;background:#0f172a;border:1px solid var(--line);cursor:pointer;color:#cbd5e1}
 .chip:hover{border-color:var(--acc);color:#fff}
 .ex{font:11.5px/1.4 ui-monospace,Menlo,Consolas,monospace;background:#0f172a;border:1px solid var(--line);border-left:3px solid var(--acc);border-radius:6px;padding:6px 8px;margin:5px 0;cursor:pointer;white-space:pre-wrap;word-break:break-word}
 .ex:hover{border-color:var(--acc)} .ex .src{color:var(--mut)}
 .empty{color:var(--mut)}
 #algo .atitle{font-size:15px;color:var(--ink);margin:2px auto 2px;max-width:880px}
 #algo .sub{max-width:880px;margin:0 auto 14px;color:var(--mut);font-size:12px}
 .stage{background:var(--panel);border:1px solid var(--line);border-radius:10px;max-width:880px;margin:0 auto;overflow:hidden}
 .stage-h{display:flex;align-items:center;gap:10px;padding:8px 13px;background:#0b1220;border-bottom:1px solid var(--line)}
 .stage-n{flex:0 0 22px;width:22px;height:22px;border-radius:50%;background:#0f172a;border:1px solid var(--acc);color:var(--acc);font-size:12px;text-align:center;line-height:21px;font-variant-numeric:tabular-nums}
 .stage-h b{font-size:14px;color:var(--ink)}
 .stage-b{padding:10px 13px}
 .stage-b .d{color:#94a3b8;font-size:12.5px;margin-bottom:7px}
 .fnchip{display:inline-block;font:12px ui-monospace,Menlo,Consolas,monospace;padding:2px 9px;margin:3px 4px 0 0;border-radius:12px;background:#0f172a;border:1px solid var(--line);color:#cbd5e1;cursor:pointer}
 .fnchip:hover{border-color:var(--acc);color:#fff}
 .fnchip.dead{opacity:.4;cursor:default}
 canvas.art{width:100%;height:158px;margin-top:10px;background:#0f172a;border:1px solid var(--line);border-radius:8px;display:block}
 .arrow{max-width:880px;margin:1px auto;text-align:center;color:#475569;font-size:17px;line-height:1.15}
 .loopbox{max-width:902px;margin:1px auto;border:1.5px solid #7c5ccb;border-radius:12px;padding:8px 10px 6px;background:rgba(124,92,203,0.06)}
 .loophdr{color:#c4b5fd;font-size:12px;font-weight:600;text-align:center;margin-bottom:6px}
 .loopback{margin-top:7px;text-align:center;color:#c4b5fd;font-size:11px;border-top:1px dashed #7c5ccb;padding-top:6px}
 .stage-n.cidx{background:#0b1220;border-color:#64748b;color:#94a3b8}
 canvas.art.tall{height:210px}
 .variant{border:1px solid var(--line);border-left:3px solid #7c5ccb;border-radius:8px;padding:8px 10px;margin:8px 0 0;background:#0b1220}
 .variant .vh{font-size:12.5px;font-weight:600;color:#c4b5fd;margin-bottom:4px}
 .leg{display:flex;align-items:center;gap:7px;font-size:12px;color:#cbd5e1;margin:5px 2px}
 .leg .sw{flex:0 0 auto} .note{font-size:11px;color:var(--mut);margin:7px 2px;line-height:1.45}
 .note code{background:#0f172a;border:1px solid var(--line);border-radius:3px;padding:0 4px;font-size:11px}
 #hits .prev{display:block;color:#94a3b8;font:11px ui-monospace,Menlo,Consolas,monospace;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
 .tw{font-size:12px} .tw-node{margin:3px 0}
 .tw-kids{margin-left:14px;border-left:1px solid var(--line);padding-left:9px}
 .tw-tog{display:inline-block;width:13px;cursor:pointer;color:var(--acc);user-select:none}
 .tw-leaf{display:inline-block;width:13px;color:#475569}
 .tw-why{color:var(--mut);margin-left:4px} .tw-n{color:#475569;font-size:11px}
 .tw-rep{color:#fbbf24;font-size:10px;margin-left:4px}
 .tw-cs{color:#64748b;font:10.5px ui-monospace,Menlo,Consolas,monospace;margin:1px 0 2px 30px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
 .doc{background:#0f172a;border:1px solid var(--line);border-left:3px solid var(--acc);border-radius:8px;padding:9px 11px;margin:8px 0;font-size:12.5px;line-height:1.5}
 .doc div{margin:2px 0;color:#cbd5e1} .doc b{color:var(--acc)} .doc.empty{border-left-color:#475569;color:var(--mut);font-size:12px}
 .trunc{color:#fbbf24;font-size:11px;margin:4px 2px}
 #focus{display:none;flex:1;min-width:0;flex-direction:column}
 #focusnet{flex:3 1 0;min-height:0;border-bottom:1px solid var(--line)}
 #focusinfo{flex:2 1 0;min-height:0;overflow:auto;padding:13px 16px;background:#0b1220}
 #focusinfo h3{margin:2px 0;font-size:16px} #focusinfo .meta{color:var(--mut);font-size:12px;margin-bottom:8px;word-break:break-all}
 .fhead{margin-bottom:2px;display:flex;gap:6px;flex-wrap:wrap;align-items:center} .fhead .bk{color:var(--acc);cursor:pointer;font-size:12px}
 .panetog{font-size:11px;font-weight:700;padding:5px 11px;background:#0f172a;color:#cbd5e1;border:1px solid var(--line);border-radius:7px;cursor:pointer}
 .panetog:hover{border-color:var(--acc);color:#fff}
 #focus.info-max #focusnet{display:none}
 #focus.info-max #focusinfo{flex:1}
 .fchips{display:flex;flex-direction:column;gap:3px;margin:4px 0}
 .fchip{display:flex;align-items:baseline;gap:8px;cursor:pointer;padding:1px 0}
 .fchip .chip{flex:0 0 auto} .fchip:hover .chip{border-color:var(--acc);color:#fff}
 .frole{color:var(--mut);font-size:11.5px;line-height:1.35}
 .backbtn{font-size:12px;font-weight:700;padding:5px 13px;background:#0b2536;color:#e2e8f0;border:1px solid var(--acc);border-radius:7px;cursor:pointer}
 .backbtn:hover{background:#0f3346}
 .concept{border:1px solid var(--line);border-left:3px solid var(--acc);border-radius:8px;background:#0f172a;padding:10px 12px;margin:10px 0}
 .concept .ctitle{font-size:13px;font-weight:700;color:var(--acc);margin-bottom:5px}
 .concept .cintro{font-size:12.5px;color:#cbd5e1;line-height:1.5;margin-bottom:4px}
 .csteps{margin:6px 0 4px;padding-left:20px} .csteps li{font-size:12px;color:#cbd5e1;line-height:1.5;margin:3px 0}
 .csteps b{color:#e2e8f0}
 .ceq{font:11px ui-monospace,Menlo,Consolas,monospace;background:#0b1220;border:1px solid var(--line);border-radius:4px;padding:0 4px;color:var(--acc);white-space:nowrap}
 .cfig{margin:9px 0 4px} .cfig figcaption{font-size:10.5px;color:var(--mut);text-align:center;margin-top:3px}
 .cnote{font-size:12px;color:#cbd5e1;line-height:1.5;background:#0b1220;border:1px dashed #475569;border-radius:6px;padding:7px 9px;margin:7px 0}
 .cnote b{color:var(--acc)}
 .ccredit{font-size:10px;color:var(--mut);margin-top:5px;font-style:italic}
 .flow{border:1px solid var(--line);border-left:3px solid #34d399;border-radius:8px;background:#0f172a;padding:10px 12px;margin:10px 0}
 .flow .ctitle{font-size:13px;font-weight:700;color:#34d399;margin-bottom:4px}
 .flow .flowcap{font-size:10.5px;color:var(--mut);line-height:1.45;margin-bottom:9px}
 .flowchart{display:flex;flex-direction:column;align-items:center}
 .fnode{font-size:11px;padding:3px 11px;border:1px dashed var(--line);border-radius:14px;background:#0b1220;color:var(--mut);max-width:100%;text-align:center}
 .fstart{color:#34d399;border-color:rgba(52,211,153,.5)} .fend{color:var(--acc);border-color:rgba(56,189,248,.5)}
 .fmuted{font-size:10px;opacity:.8}
 .fconn{color:#475569;font-size:15px;line-height:1.05;margin:3px 0}
 .fstep{display:flex;gap:8px;flex-wrap:wrap;justify-content:center;width:100%}
 .fstep.multi{outline:1px dashed #3b4a5e;border-radius:10px;padding:7px;background:rgba(71,85,105,.07)}
 .fblk{display:inline-flex;flex-direction:row;align-items:center;gap:8px;min-width:200px;max-width:360px;cursor:pointer;background:#0b1220;border:1px solid var(--line);border-radius:8px;padding:6px 10px;text-align:left}
 .fcol{display:flex;flex-direction:column;gap:2px;min-width:0}
 canvas.mini{flex:0 0 46px;width:46px;height:30px;border-radius:4px;background:#0a0f1a;border:1px solid var(--line)}
 .fblk:hover{border-color:var(--acc);background:#0c1a2b}
 .fname{font:12px ui-monospace,Menlo,Consolas,monospace;color:#e2e8f0;font-weight:700}
 .fblk .frole{font-size:10.5px;color:var(--mut);line-height:1.3}
 .fbadge{display:inline-block;font-size:9.5px;font-weight:700;padding:0 6px;border-radius:8px;width:fit-content}
 .fbadge.loop{color:#f59e0b;background:rgba(245,158,11,.14)} .fbadge.par{color:#34d399;background:rgba(52,211,153,.16)}
 .fsame{font-size:9.5px;color:var(--mut);width:100%;text-align:center;margin-top:1px}
 .fmini{cursor:pointer;color:#cbd5e1;border-bottom:1px dotted var(--line)} .fmini:hover{color:#fff;border-color:var(--acc)}
 .flowbtn{display:inline-block;margin-top:9px;font-size:11px;font-weight:700;padding:6px 12px;background:#10241f;color:#e2e8f0;border:1px solid #34d399;border-radius:7px;cursor:pointer}
 .flowbtn:hover{background:#143029}
 #flowpage{flex:1;min-width:0;overflow:auto;padding:16px 22px;background:var(--bg)}
 .flowpage-h{max-width:1040px;margin:0 auto 12px}
 .flowpage-h .backbtn{margin-bottom:6px}
 .fp-title{font-size:18px;font-weight:700;color:var(--ink);margin:6px 0 2px}
 .fp-title code{background:#0f172a;border:1px solid var(--line);border-radius:5px;padding:1px 6px;font-size:15px;color:var(--acc)}
 .fp-sub{font-size:12px;color:var(--mut);line-height:1.5}
 .rwrap{max-width:1040px;margin:0 auto}
 .rblk{display:inline-flex;align-items:baseline;gap:7px;background:#0b1220;border:1px solid var(--line);border-radius:8px;padding:5px 10px;max-width:100%}
 .rblk.rroot{background:#0c1a2b;border-color:var(--acc)}
 .rname{font:12.5px ui-monospace,Menlo,Consolas,monospace;color:#e2e8f0;font-weight:700;cursor:pointer}
 .rname:hover{color:var(--acc);text-decoration:underline} .rootname{cursor:default} .rootname:hover{color:#e2e8f0;text-decoration:none}
 .rrole{font-size:11px;color:var(--mut)}
 .rtog{cursor:pointer;color:var(--acc);width:13px;display:inline-block;user-select:none}
 .rtog.rrep{color:#fbbf24;cursor:default} .rdot{color:#475569;width:13px;display:inline-block}
 .rkids{margin-left:15px;border-left:1px solid var(--line);padding-left:14px}
 .rstep{margin:4px 0} .rconn{color:#475569;font-size:12px;line-height:1;margin:0 0 0 4px}
 .rsub.collapsed{display:none}
 .fp-explain{max-width:1040px;margin:18px auto 0;border-top:1px solid var(--line);padding-top:12px}
 .fp-exh{font-size:13px;font-weight:700;color:var(--ink);margin-bottom:8px} .fp-concept{margin-bottom:10px}
 .pwrap{max-width:1100px;margin:0 auto}
 .psec{font-size:15px;font-weight:700;color:var(--ink);margin:18px 0 8px;border-bottom:1px solid var(--line);padding-bottom:4px}
 .pgrp{font-size:12px;font-weight:700;color:var(--acc);margin:12px 0 4px}
 .ptab{width:100%;border-collapse:collapse;font-size:12px;margin:2px 0 6px}
 .ptab th{text-align:left;color:var(--mut);font-weight:600;font-size:10px;text-transform:uppercase;letter-spacing:.05em;padding:3px 8px;border-bottom:1px solid var(--line)}
 .ptab td{padding:4px 8px;border-bottom:1px solid #1e293b;color:#cbd5e1;vertical-align:top;line-height:1.45}
 .ptab code{font:11.5px ui-monospace,Menlo,Consolas,monospace;background:#0f172a;border:1px solid var(--line);border-radius:4px;padding:0 4px;color:var(--acc)}
 .ptab .ptype{color:#94a3b8;font:11px ui-monospace,Menlo,Consolas,monospace;white-space:nowrap} .ptab .pdef{color:#e2e8f0;font:11px ui-monospace,Menlo,Consolas,monospace;white-space:nowrap}
 .pio td:first-child{white-space:nowrap}
 .pmeth{font:12.5px ui-monospace,Menlo,Consolas,monospace;color:#e2e8f0;font-weight:700;cursor:pointer} .pmeth:hover{color:var(--acc);text-decoration:underline}
 .psig{font:10.5px ui-monospace,Menlo,Consolas,monospace;color:var(--mut);margin-top:2px} .pnote{color:var(--mut);font-size:11px;margin-top:3px;line-height:1.4}
 .pimpl{border:1px solid var(--line);border-left:3px solid var(--acc);border-radius:8px;background:#0f172a;padding:10px 13px;margin:10px 0}
 .pimpl-h{font-size:14px;font-weight:700;color:var(--ink)} .pimpl-b{font-size:12px;color:#cbd5e1;line-height:1.5;margin:3px 0 4px}
 .facades{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0 14px}
 .facade-name{font:12px ui-monospace,Menlo,Consolas,monospace;padding:4px 9px;border:1px solid var(--line);border-radius:12px;background:#0f172a;color:#cbd5e1;cursor:pointer}
 .facade-name:hover{border-color:var(--acc);color:#fff}
 .pmut{color:var(--mut)}
 .pmodbox{border:1px solid var(--line);border-radius:8px;background:#0f172a;margin:6px 0;padding:0 12px}
 .pmodbox>summary{cursor:pointer;font-size:13px;font-weight:700;color:var(--ink);padding:8px 0;outline:none;list-style:none;display:flex;align-items:center;gap:7px}
 .pmodbox>summary::-webkit-details-marker{display:none}
 .pmodbox>summary::before{content:"▸";color:var(--acc);font-size:11px} .pmodbox[open]>summary::before{content:"▾"}
 .pmodbox .dot{width:9px;height:9px;border-radius:50%;flex:0 0 9px}
 .crumb{font-size:12px;color:#94a3b8;margin:6px 0 2px} .crumb .bk{color:var(--acc);cursor:pointer}
 /* object viewer */
 .objtabs{display:flex;gap:6px;flex-wrap:wrap;margin:4px 0 14px}
 .objtab{font:12px ui-monospace,Menlo,Consolas,monospace;font-weight:700;padding:6px 13px;background:#0f172a;color:var(--mut);border:1px solid var(--line);border-radius:8px;cursor:pointer}
 .objtab:hover{color:#fff;border-color:var(--acc)} .objtab.on{color:#fff;background:#0b2536;border-color:var(--acc);box-shadow:inset 0 0 0 1px var(--acc)}
 .objhdr{border:1px solid var(--line);border-left:3px solid var(--acc);border-radius:10px;background:#0f172a;padding:12px 14px;margin:4px 0 14px}
 .objdecl{font:13px ui-monospace,Menlo,Consolas,monospace;color:#e2e8f0;white-space:pre-wrap;word-break:break-word}
 .objdecl .kw{color:#c084fc} .objdecl .ty{color:var(--acc)} .objdecl .sup{color:#34d399}
 .objbadges{display:flex;gap:7px;flex-wrap:wrap;margin-top:9px}
 .objbadge{font-size:10.5px;font-weight:700;color:#cbd5e1;background:#0b1220;border:1px solid var(--line);border-radius:20px;padding:2px 10px;letter-spacing:.02em}
 .objbadge b{color:var(--acc)}
 .ogrp{margin:14px 0} .ogrp-h{font-size:12px;font-weight:700;color:var(--acc);margin:0 0 7px;display:flex;align-items:center;gap:6px}
 .ogrp-h::before{content:"";width:7px;height:7px;border-radius:2px;background:var(--acc);flex:0 0 7px}
 .ofields{display:grid;grid-template-columns:repeat(auto-fill,minmax(262px,1fr));gap:8px}
 .ofield{border:1px solid var(--line);border-radius:8px;background:#0b1220;padding:8px 10px;display:flex;flex-direction:column;gap:3px}
 .ofield:hover{border-color:var(--acc)}
 .ofrow{display:flex;align-items:baseline;gap:7px;flex-wrap:wrap}
 .ofname{font:12.5px ui-monospace,Menlo,Consolas,monospace;font-weight:700;color:#e2e8f0}
 .oftype{font:10.5px ui-monospace,Menlo,Consolas,monospace;color:var(--acc);background:#0f172a;border:1px solid var(--line);border-radius:4px;padding:0 5px}
 .ofdef{margin-left:auto;font:11px ui-monospace,Menlo,Consolas,monospace;color:#34d399;background:#0f172a;border:1px solid rgba(52,211,153,.4);border-radius:4px;padding:0 6px;white-space:nowrap}
 .ofdesc{font-size:11px;color:var(--mut);line-height:1.45}
 .otier{font-size:8.5px;font-weight:700;padding:1px 6px;border-radius:7px;text-transform:uppercase;letter-spacing:.04em}
 .otier.ot-knob{color:var(--acc);background:rgba(56,189,248,.14)} .otier.ot-adv{color:#f59e0b;background:rgba(245,158,11,.14)}
 .otier.ot-cache{color:#64748b;background:rgba(100,116,139,.18)} .otier.ot-const{color:#a78bfa;background:rgba(167,139,250,.16)}
 .otier.ot-field{color:var(--acc);background:rgba(56,189,248,.14)}
 .ofield.ot-knob{border-left:3px solid rgba(56,189,248,.55)} .ofield.ot-adv{border-left:3px solid rgba(245,158,11,.55)}
 .ofield.ot-cache{border-left:3px solid rgba(100,116,139,.5)} .ofield.ot-const{border-left:3px solid rgba(167,139,250,.55);opacity:.9}
 .ofield.ot-field{border-left:3px solid rgba(56,189,248,.55)}
 .objlegend{font-size:11px;color:var(--mut);margin:0 0 12px;display:flex;align-items:center;gap:6px;flex-wrap:wrap}
 .cachenote{font-size:11px;color:var(--mut);margin:8px 0 4px;padding:7px 10px;border:1px dashed var(--bd);border-radius:6px;line-height:1.5;font-style:italic}
 .cachenote code{font-style:normal}
 .objex-h{font-size:12px;font-weight:600;color:var(--acc);margin:4px 0 6px}
 .objex{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:11.5px;line-height:1.5;color:var(--fg);background:var(--panel2,#1b1f27);border:1px solid var(--bd);border-radius:8px;padding:11px 13px;margin:0 0 16px;overflow-x:auto;white-space:pre}
 .objcount{font-size:11px;color:var(--mut)}
 .objlink{color:var(--acc);cursor:pointer;text-decoration:underline;white-space:nowrap}
 #overlay{position:fixed;inset:0;display:none;align-items:center;justify-content:center;background:rgba(8,14,28,.6);z-index:60}
 #overlay.on{display:flex}
 #overlay .card{max-width:480px;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:22px 26px;box-shadow:0 12px 48px rgba(0,0,0,.55)}
 #overlay h3{margin:0 0 10px;font-size:17px;color:var(--ink)} #overlay .b{color:#cbd5e1;font-size:13px;line-height:1.55}
 #overlay ol{margin:8px 0 0;padding-left:20px;color:#cbd5e1;font-size:13px;line-height:1.7}
 #overlay .b code{background:#0f172a;border:1px solid var(--line);border-radius:4px;padding:1px 5px;font-size:12px}
 @media (max-width:700px){
  body{height:auto;min-height:100vh}
  #bar{flex-wrap:wrap}
  #path{min-width:0;flex:1 1 100%}
  #wrap{flex-direction:column}
  #side,#detail{width:100%;flex:0 0 auto}
  #side{max-height:36vh;border-right:0;border-bottom:1px solid var(--line)}
  #net{width:100%;min-height:52vh;flex:0 0 52vh}
  #algo,#focus{width:100%;min-height:70vh}
  #detail{max-height:46vh;border-left:0;border-top:1px solid var(--line)}
  #flowpage{width:100%}
 }
</style></head><body>
<div id="bar">
  <h1>🔬 JunaCore source definitions</h1>
  <span id="pin" style="display:none;flex:1;min-width:0;color:#94a3b8;font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">📌 <b id="pinname" style="color:#e2e8f0"></b> <span id="pinpath"></span></span>
  <input id="path" placeholder="/path/to/project folder" autocomplete="off">
  <button id="load" title="open a folder picker, then scan it">📁 Load…</button>
  <button id="viewtog" title="toggle between the OOP type view and the source-backed JunaCore pipeline">▦ JunaCore pipeline</button>
  <button id="paramstog" title="reference page: the current Modulations interface, Juna implementation, and public facades">📥 interface I/O</button>
  <button id="objtog" title="object viewer: all fields of the current Juna.Modulation source type">🧩 object fields</button>
  <button id="reload" title="rescan the project (picks up code changes)">🔄 reload</button>
  <button id="restart" title="restart the server, then reload this page">⟳ restart</button>
  <span id="msg"></span>
  <span id="wblinks" style="display:none;font-size:12px;white-space:nowrap"></span>
</div>
<div id="wrap">
  <div id="side">
    <div id="root" class="empty" style="font-size:11px;word-break:break-all"></div>
    <div id="crumb" class="crumb"></div>
    <h2>stats</h2><div id="stats"></div>
    <div id="trunc" class="trunc" style="display:none"></div>
    <h2>find</h2><input id="q" placeholder="name — or mod: / file: / src:">
    <div class="note">name search, or prefix with <code>mod:</code> <code>file:</code> <code>src:</code> <code>doc:</code> (<code>doc:!</code> = undocumented)</div>
    <div id="hits"></div>
    <h2>modules <span id="modn" class="empty"></span></h2>
    <div id="mods"></div>
  </div>
  <div id="net"></div>
  <div id="algo" style="display:none;flex:1;min-width:0;overflow:auto;padding:16px 20px"></div>
  <div id="focus"><div id="focusnet"></div><div id="focusinfo"></div></div>
  <div id="detail"><div class="empty">Load a folder, click a module to see its functions, then click any function to read its source and usage examples.</div></div>
</div>
<div id="flowpage" style="display:none"></div>
<div id="overlay"><div class="card"><h3 id="ovh"></h3><div class="b" id="ovb"></div></div></div>
<script>
const CFG=/*CONFIG*/;
const PAL=['#38bdf8','#34d399','#f59e0b','#a78bfa','#f472b6','#fb7185','#4ade80','#facc15','#22d3ee','#c084fc','#fca5a5','#2dd4bf','#fbbf24','#60a5fa','#f97316','#a3e635'];
let net=null,DATA=null,SYM={},MODCOL={},LASTFOCUS=null,IFACEFOCUS=null,PREVFOCUSMODE=null,FOCUSSTACK=[];
let NDS=null,EDS=null,BASEOP={},MODE='oop',ALGO_OK=false,ALGO_HITS=[0,0];
const $=id=>document.getElementById(id);
function showOverlay(title,bodyHtml){$('ovh').textContent=title;$('ovb').innerHTML=bodyHtml;$('overlay').classList.add('on');}
function hideOverlay(){$('overlay').classList.remove('on');}

function modColor(m){if(!(m in MODCOL)){const k=Object.keys(MODCOL).length;MODCOL[m]=PAL[k%PAL.length];}return MODCOL[m];}
function esc(s){return (s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}

function render(D){
  if(MODE==='focus'){MODE='oop';$('focus').style.display='none';$('detail').style.display='';$('net').style.display='block';$('algo').style.display='none';}
  DATA=D;SYM={};MODCOL={};LASTFOCUS=null;IFACEFOCUS=null;PREVFOCUSMODE=null;FOCUSSTACK=[];
  D.symbols.forEach(s=>SYM[s.id]=s);
  D.modules.forEach(m=>modColor(m.name));
  $('root').textContent='root: '+D.root;
  const s=D.stats;
  $('stats').innerHTML=[['source definitions',s.symbols],['modules',s.modules],['call edges',s.edges],['files',s.files],['documented',(s.documented||0)+'/'+s.symbols]]
    .map(([k,v])=>`<div class="stat"><span>${k}</span><b>${v}</b></div>`).join('');
  $('trunc').style.display=s.truncated?'block':'none';
  if(s.truncated)$('trunc').textContent=`⚠ large tree: scanned ${s.scanned} of ${s.total_files} files (capped). Point at a subfolder for full coverage.`;
  // only offer the algorithm view when this project actually matches the curated pipeline
  const pipelineNames=pipelineFunctionNames();
  const need=pipelineNames.length,got=pipelineNames.filter(n=>resolveSym(n)).length;
  ALGO_OK=need>0&&got===need;ALGO_HITS=[got,need];
  $('viewtog').style.display=ALGO_OK?'':'none';
  if(!ALGO_OK&&MODE==='algo')MODE='oop';
  $('modn').textContent='('+D.modules.length+')';
  $('mods').innerHTML='';
  D.modules.forEach(m=>{
    const d=document.createElement('div');d.className='mod';
    d.dataset.module=m.name;d.tabIndex=0;
    d.innerHTML=`<span class="dot" style="background:${modColor(m.name)}"></span><span class="c"><span class="n">${esc(m.name)}</span><span class="ct">${m.count}</span></span>`;
    d.onclick=()=>selectModule(m.name);
    d.onkeydown=ev=>{if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();selectModule(m.name);}};
    $('mods').appendChild(d);
  });
  setView(MODE==='algo'?'algo':'oop');     // land in the OOP type view (default)
  $('detail').innerHTML=MODE==='algo'
    ? '<div class="empty">Source-backed pipeline — click any function chip to inspect its exact current definition and lexical relationships.</div>'
    : '<div class="empty">OOP view — click a type ◇ or an interface method in the graph. Click a method to open its call-focus sphere; use search on the left to jump to any source definition.</div>';
  ROUTE_HASH();
}

// Re-runnable hash router. Called once after a scan and again on every
// hashchange, so a deep link followed while already on this page (or a hash
// typed by hand) routes immediately instead of needing a full reload.
function ROUTE_HASH(){
  const fh=(location.hash||'').match(/flow=(\d+)/);   // deep-link: a new tab opened at #flow=<id> shows the recursive call-flow
  const ih=(location.hash||'').match(/iface=([A-Za-z_]\w*!?)/);
  const mh=(location.hash||'').match(/module=([^&]+)/);
  const sh=(location.hash||'').match(/sym=([^&]+)/);
  const sf=(location.hash||'').match(/file=([^&]+)/);
  const sl=(location.hash||'').match(/line=(\d+)/);
  if(fh&&SYM[+fh[1]])openFlowPage(+fh[1]);
  else if(sh){ // #sym=name[&module=M&file=F&line=L] → one exact definition card
    const w=decodeURIComponent(sh[1]);
    const wm=mh?decodeURIComponent(mh[1]):'';
    const wf=sf?decodeURIComponent(sf[1]).replace(/^src\//,''):'';
    const wl=sl?+sl[1]:0;
    const list=(typeof DATA!=='undefined'&&DATA&&DATA.symbols)?DATA.symbols:[];
    const named=list.filter(s=>s.name===w||s.name.replace(/!$/,'')===w.replace(/!$/,''));
    const exact=s=> (!wm||s.module===wm)&&(!wf||s.file===wf)&&(!wl||s.line===wl);
    const qualified=!!(wm||wf||wl);
    const matches=named.filter(exact);
    if(qualified&&matches.length===0){
      const requested=[wm,wf,wl].filter(Boolean).join(' · ');
      $('detail').innerHTML=`<div class="empty"><b>Exact source definition not found.</b><br>`+
        `The requested identity <code>${esc(w)}</code> · ${esc(requested)} is stale or does not exist in this source scan. `+
        `No same-name fallback was opened.</div>`;
    }else if(qualified&&matches.length>1){
      $('detail').innerHTML=`<h3>${esc(w)}<span class="kind">overload family</span></h3>`+
        `<div class="meta">${matches.length} definitions match this partial identity. Choose an exact file and line:</div>`+
        `<div class="chips">${matches.map(s=>`<span class="chip" data-sym="${s.id}">${esc(s.module)} · ${esc(s.file)}:${s.line}</span>`).join('')}</div>`;
    }else{
      const hit=matches[0]||(!qualified?named[0]:null);
      if(hit)select(hit.id);
      else $('detail').innerHTML='<div class="empty"><b>Source definition not found.</b></div>';
    }}
  else if(sf)selectFile(decodeURIComponent(sf[1]).replace(/^src\//,'')); // #file=src/path.jl
  else if(ih)openFocusIface(ih[1]);                         // #iface=name → concrete override/helper focus
  else if(/params/.test(location.hash||''))openParamsPage();   // #params → interface I/O reference page
  else if(/object/.test(location.hash||''))openObjPage();       // #object → object viewer (modulation fields)
  else if(mh)selectModule(decodeURIComponent(mh[1]));            // #module=name → all definitions attributed to that module
  else if(/algorithm/.test(location.hash||''))setView('algo');  // #algorithm → current source-backed pipeline
  else $('flowpage').style.display='none';
}
if(!window.__junaHashBound){window.__junaHashBound=1;
  window.addEventListener('hashchange',function(){if(typeof DATA!=='undefined'&&DATA)ROUTE_HASH();});}

function selectModule(name){
  if(!DATA)return;
  const members=DATA.symbols.filter(s=>s.module===name);
  if(!members.length)return;
  if(MODE!=='oop')setView('oop');
  document.querySelectorAll('#mods .mod').forEach(d=>d.classList.toggle('on',d.dataset.module===name));
  const ordered=members.slice().sort((a,b)=>
    a.kind.localeCompare(b.kind)||a.name.localeCompare(b.name)||a.file.localeCompare(b.file)||a.line-b.line);
  const functions=ordered.filter(s=>s.kind==='function'||s.kind==='macro');
  const declarations=ordered.filter(s=>s.kind!=='function'&&s.kind!=='macro');
  const chips=arr=>arr.length?arr.map(s=>
    `<span class="chip" data-sym="${s.id}" title="${esc(s.file)}:${s.line}">${esc(s.name)} <span style="color:#64748b">· ${esc(s.file)}:${s.line}</span></span>`
  ).join(''):'<span class="empty">none</span>';
  $('detail').innerHTML=
    `<h3>${esc(name)}<span class="kind">module</span></h3>`+
    `<div class="meta">${members.length} source definitions attributed to this Julia module. Click one to inspect its exact source and lexical relationships.</div>`+
    `<div style="display:flex;gap:6px;flex-wrap:wrap;margin:2px 0 8px">`+
    `<a href="${wbBase()}/coverage?module=${encodeURIComponent(name)}" title="show registered suites and testsets linked to this source module" style="font-size:11px;padding:3px 8px;background:#132615;color:#e2e8f0;border:1px solid #3fb950;border-radius:6px;text-decoration:none">🧪 tests for this module</a></div>`+
    `<h2>functions and macros (${functions.length})</h2><div class="chips">${chips(functions)}</div>`+
    `<h2>types, constants, and module declarations (${declarations.length})</h2><div class="chips">${chips(declarations)}</div>`;
  $('detail').scrollTop=0;
  try{history.replaceState(null,'',location.pathname+location.search+'#module='+encodeURIComponent(name));}catch(e){}
}

function selectFile(file){
  if(!DATA)return;
  const clean=String(file||'').replace(/^src\//,'');
  const members=DATA.symbols.filter(s=>s.file===clean);
  if(!members.length)return;
  if(MODE!=='oop')setView('oop');
  document.querySelectorAll('#mods .mod').forEach(d=>d.classList.remove('on'));
  const ordered=members.slice().sort((a,b)=>a.line-b.line||a.name.localeCompare(b.name));
  const modules=[...new Set(ordered.map(s=>s.module))];
  const chips=ordered.map(s=>
    `<span class="chip" data-sym="${s.id}" title="${esc(s.module)} · line ${s.line}">${esc(s.name)} <span style="color:#64748b">· ${esc(s.module)}:${s.line}</span></span>`
  ).join('');
  $('detail').innerHTML=
    `<h3>${esc(clean)}<span class="kind">source file</span></h3>`+
    `<div class="meta">${members.length} definitions in ${modules.map(esc).join(', ')}. Click one to inspect its exact source and lexical relationships.</div>`+
    `<h2>definitions (${members.length})</h2><div class="chips">${chips}</div>`;
  $('detail').scrollTop=0;
  try{history.replaceState(null,'',location.pathname+location.search+'#file='+encodeURIComponent(clean));}catch(e){}
}

const TYPEKINDS=new Set(['struct','type','const']);
const isType=id=>TYPEKINDS.has(SYM[id].kind);
function setCrumb(){
  const c=$('crumb');
  if(!DATA){c.textContent='';return;}
  if(MODE==='oop'){c.innerHTML='<b>OOP view</b> — ◇ types · solid ↗ <code style="background:#0f172a;padding:0 3px;border-radius:3px">&lt;:</code> subtype · dashed ↗ implements interface method. Click a type or method.';return;}
  if(MODE==='algo'){c.innerHTML='<b>JUNA pipeline</b> — concept + code walkthrough';return;}
  if(MODE==='focus'){const lbl=IFACEFOCUS?esc(IFACEFOCUS)+'()':(SYM[LASTFOCUS]?esc(SYM[LASTFOCUS].name):'');c.innerHTML='<span class="bk">‹ back</span> ▸ <b>call-focus</b>'+(lbl?' · <code style="background:#0f172a;padding:0 3px;border-radius:3px">'+lbl+'</code>':'');c.querySelector('.bk').onclick=exitFocus;return;}
}

// ---- OOP view: abstract types, <: subtyping, interface implementations -------
const IFACE_MODS=new Set(['Modulations','Base']);
function isIfaceMethod(s){return s.kind==='function'&&s.recv&&IFACE_MODS.has(s.qual);}
function drawOOP(){
  if(!DATA)return;
  const allTypes=DATA.symbols.filter(s=>s.kind==='struct'||s.kind==='type');
  const byName={}; allTypes.forEach(t=>(byName[t.name]=byName[t.name]||[]).push(t));
  const impl={};   // 'module|name' -> Set(ifaceName)
  const ifaceNames=new Set();
  DATA.symbols.forEach(s=>{if(isIfaceMethod(s)){const k=s.module+'|'+s.recv;
    (impl[k]=impl[k]||new Set()).add(s.name); ifaceNames.add(s.name);}});
  // show abstract types, concrete subtypes (super resolves to a known type), and any type that implements an interface
  const show=allTypes.filter(t=> t.kind==='type' || (t.super&&byName[t.super]) || impl[t.module+'|'+t.name]);
  const shownKeys=new Set(show.map(t=>t.module+'|'+t.name));
  const nodes=[],edges=[]; let ei=0;
  show.forEach(t=>{const abs=t.kind==='type';
    nodes.push({id:'t:'+t.module+'|'+t.name,label:t.module+'.'+t.name,shape:'diamond',
      size:abs?24:17,
      color:{background:abs?'#a78bfa':modColor(t.module),border:'#1e293b',
             highlight:{background:abs?'#a78bfa':modColor(t.module),border:'#fff'},hover:{border:'#fff'}},
      font:{color:'#e2e8f0',size:12,face:'ui-monospace',strokeWidth:3,strokeColor:'#0f172a'},
      title:`${t.module}.${t.name}  [${abs?'abstract type':'struct'}]`+(t.super?`\n<: ${t.super}`:'')});});
  [...ifaceNames].sort().forEach(n=>nodes.push({id:'i:'+n,label:n+'()',shape:'dot',size:10,
    color:{background:'#1e293b',border:'#64748b',highlight:{background:'#334155',border:'#fff'},hover:{border:'#fff'}},
    font:{color:'#94a3b8',size:11,face:'ui-monospace',strokeWidth:3,strokeColor:'#0f172a'},
    title:`interface method ${n}()  (Modulations contract)`}));
  // resolve a supertype NAME to a type node, preferring the abstract type (several
  // modulations share the name "Modulation"), never the type itself.
  const resolveSuper=(nm,self)=>{const c=byName[nm]||[];return c.find(x=>x.kind==='type')||c.find(x=>x!==self)||null;};
  show.forEach(t=>{if(t.super){const sup=resolveSuper(t.super,t);
    if(sup&&shownKeys.has(sup.module+'|'+sup.name))
      edges.push({id:'e'+(ei++),from:'t:'+t.module+'|'+t.name,to:'t:'+sup.module+'|'+sup.name,arrows:'to',
        width:2,color:{color:'#a78bfa',highlight:'#c4b5fd'},label:'<:',
        font:{size:11,color:'#c4b5fd',background:'#0f172a',strokeWidth:0}});}});
  Object.keys(impl).forEach(k=>impl[k].forEach(n=>edges.push({id:'e'+(ei++),from:'t:'+k,to:'i:'+n,
    arrows:{to:{scaleFactor:0.5}},dashes:true,width:1,color:{color:'#475569',highlight:'#38bdf8',opacity:0.8}})));
  NDS=new vis.DataSet(nodes);EDS=new vis.DataSet(edges);BASEOP={};nodes.forEach(n=>BASEOP[n.id]=1);
  const opts={physics:{stabilization:{iterations:220},barnesHut:{gravitationalConstant:-13000,springLength:140,centralGravity:0.25,avoidOverlap:0.7}},
    interaction:{hover:true,tooltipDelay:110},nodes:{borderWidth:1.5},edges:{smooth:{type:'continuous',roundness:0.2}}};
  if(net)net.destroy();
  net=new vis.Network($('net'),{nodes:NDS,edges:EDS},opts);
  net.on('click',p=>{if(p.nodes.length){const id=String(p.nodes[0]);
    id.slice(0,2)==='t:'?selectType(id.slice(2)):openFocusIface(id.slice(2));}});
  net.once('afterDrawing',()=>net.fit({animation:false}));
}
function selectType(key){
  const i=key.indexOf('|'),mod=key.slice(0,i),name=key.slice(i+1);
  const t=DATA.symbols.find(s=>(s.kind==='struct'||s.kind==='type')&&s.module===mod&&s.name===name);
  if(!t){return;}
  const fields=[]; t.src.split('\n').forEach(l=>{const m=l.match(/^\s*([A-Za-z_]\w*)\s*::/);if(m)fields.push(m[1]);});
  const ifaceM=DATA.symbols.filter(s=>s.kind==='function'&&s.module===mod&&s.recv===name&&IFACE_MODS.has(s.qual));
  const ownM=DATA.symbols.filter(s=>s.kind==='function'&&s.module===mod&&s.recv===name&&!IFACE_MODS.has(s.qual));
  const subs=DATA.symbols.filter(s=>s.kind==='struct'&&s.super===name);
  const symchips=arr=>arr.length?arr.map(s=>`<span class="chip" data-focus="${s.id}" title="open the call-focus sphere view for ${esc(s.name)}">${esc(s.name)}</span>`).join(''):'<span class="empty">none</span>';
  const tchips=arr=>arr.length?arr.map(s=>`<span class="chip" data-sym="${s.id}">${esc(s.module)}.${esc(s.name)}</span>`).join(''):'<span class="empty">none</span>';
  $('detail').innerHTML=
    `<h3>${esc(mod)}.${esc(name)}<span class="kind">${t.kind==='type'?'abstract type':'struct'}</span></h3>`+
    (t.super?`<div class="meta">subtype of <b>${esc(t.super)}</b> (<code>&lt;: ${esc(t.super)}</code>)</div>`:'<div class="meta">root type (no supertype)</div>')+
    docBlock(t)+
    (t.kind==='type'?`<h2>subtypes (${subs.length})</h2><div class="chips">${tchips(subs)}</div>`:'')+
    (fields.length?`<h2>fields (${fields.length})</h2><div class="chips">${fields.map(f=>`<span class="chip" style="cursor:default;border-style:dashed">${esc(f)}</span>`).join('')}</div>`:'')+
    (ifaceM.length?`<h2>implements interface (${ifaceM.length})</h2><div class="chips">${symchips(ifaceM)}</div>`:'')+
    (ownM.length?`<h2>own methods (${ownM.length})</h2><div class="chips">${symchips(ownM)}</div>`:'')+
    `<h2>source</h2><pre>${esc(t.src.length>1400?t.src.slice(0,1400)+'\n…':t.src)}</pre>`;
  $('detail').scrollTop=0;
}
function selectIface(name){
  const impls=DATA.symbols.filter(s=>s.kind==='function'&&s.name===name&&isIfaceMethod(s));
  const chips=impls.length?impls.map(s=>`<span class="chip" data-focus="${s.id}" title="open the call-focus sphere view">${esc(s.module)}.${esc(s.recv)}</span>`).join(''):'<span class="empty">none</span>';
  $('detail').innerHTML=
    `<h3>${esc(name)}()<span class="kind">interface method</span></h3>`+
    `<div class="meta">A function in the Modulations contract. The list below contains the concrete overrides found in this source tree; the generic may also provide shared or default behavior.</div>`+
    `<h2>concrete overrides (${impls.length})</h2><div class="chips">${chips}</div>`+
    `<div class="note">Click a modulation to open the <b>call-focus sphere view</b> of its <code>${esc(name)}()</code> — the method as a hub with the functions it calls around it.</div>`;
  $('detail').scrollTop=0;
}
// Role/Reads/Returns (or Object/Holds/Why for structs) from the walkthrough deck.
function docBlock(s){
  if(!s.doc) return '<div class="doc empty">no walkthrough annotation for this source definition</div>';
  const L=s.doc.kind==='obj'?['Object','Holds','Why it matters']:['Role','Reads','Returns'];
  return `<div class="doc"><div><b>${L[0]}.</b> ${esc(s.doc.a)}</div>`+
         `<div><b>${L[1]}.</b> ${esc(s.doc.b)}</div>`+
         `<div><b>${L[2]}.</b> ${esc(s.doc.c)}</div></div>`;
}

// ---- recursive call tree: which sub-functions a function calls, and why ------
function callSiteLine(parent,name){
  const pat=new RegExp('\\b'+name.replace(/[.*+?^${}()|[\]\\]/g,'\\$&').replace(/!$/,'')+'!?\\b');
  for(const l of parent.src.split('\n')){if(pat.test(l))return l.trim().slice(0,96);}
  return '';
}
function treeNode(id,site,seen,depth){
  const s=SYM[id]; if(!s)return '';
  const why=s.doc?esc(s.doc.a):('<i>'+esc(s.kind)+'</i>');
  const cs=site?`<div class="tw-cs">↳ ${esc(site)}</div>`:'';
  if(seen.has(id))
    return `<div class="tw-node"><span class="tw-leaf">↩</span><span class="chip" data-sym="${id}">${esc(s.name)}</span> <span class="tw-why">${why}</span><span class="tw-rep">↑ shown above</span>${cs}</div>`;
  seen.add(id);
  const callees=s.calls.filter(c=>SYM[c]&&!isType(c));
  const collapsed=depth>=2&&callees.length;
  const tog=callees.length?`<span class="tw-tog">${collapsed?'▸':'▾'}</span>`:`<span class="tw-leaf">•</span>`;
  const kids=callees.length?`<div class="tw-kids"${collapsed?' style="display:none"':''}>`+
    callees.map(c=>treeNode(c,callSiteLine(s,SYM[c].name),seen,depth+1)).join('')+`</div>`:'';
  return `<div class="tw-node">${tog}<span class="chip" data-sym="${id}">${esc(s.name)}</span>`+
    `${callees.length?`<span class="tw-n"> ${callees.length}↓</span>`:''} <span class="tw-why">${why}</span>${cs}${kids}</div>`;
}
function callTreeHtml(rootId){
  const root=SYM[rootId]; const top=root.calls.filter(c=>SYM[c]&&!isType(c));
  if(!top.length)return '<div class="empty">calls no in-tree functions — this is a leaf (edge of the tree).</div>';
  const seen=new Set([rootId]);
  return '<div class="tw">'+top.map(c=>treeNode(c,callSiteLine(root,SYM[c].name),seen,0)).join('')+'</div>';
}

// Base URL of the test workbench: same origin when this page is served at
// /source inside the workbench, CFG.workbench when standalone.
function wbBase(){return location.pathname.indexOf('/source')===0?'':((CFG.workbench||'').replace(/\/+$/,''));}
// Highlight the selected symbol in the type diagram when it has a node there.
// The OOP diagram shows only types ('t:module|name') and interface methods
// ('i:name'); internal functions have no node, and `net` may currently be a
// focus network without these ids, so probe NDS and swallow vis errors.
function highlightDiagramNode(s){
  try{
    if(MODE!=='oop'||!net||!NDS)return false;
    const cand=(s.kind==='struct'||s.kind==='type')?('t:'+s.module+'|'+s.name)
      :(isIfaceMethod(s)?('i:'+s.name):null);
    if(!cand||!NDS.get(cand))return false;
    net.selectNodes([cand]);
    return true;
  }catch(e){return false;}
}
function select(id){
  if(id==null||SYM[id]==null){$('detail').innerHTML='<div class="empty">click a function…</div>';return;}
  const s=SYM[id];
  const callLink=arr=>arr.length?arr.map(c=>`<span class="chip" onclick="select(${c})">${esc(SYM[c].name)}<span style="color:#64748b"> ·${esc(SYM[c].module)}</span></span>`).join(''):'<span class="empty">none</span>';
  const examples=s.examples.length?s.examples.map(e=>{const f=SYM[e.from];
      return `<div class="ex" onclick="select(${e.from})">${esc(e.text)}<div class="src">↳ ${esc(f.name)} — ${esc(f.file)}:${e.lineno}</div></div>`;}).join('')
    :'<div class="empty">no in-tree callers found (entry point, or called dynamically).</div>';
  const also=s.also&&s.also.length?`<div class="meta">also defines: ${s.also.map(esc).join(', ')}</div>`:'';
  const fns=s.calls.filter(c=>!isType(c)), tys=s.calls.filter(c=>isType(c));
  const docHtml=docBlock(s);
  // Either highlight this symbol's node in the type diagram, or say plainly
  // why the diagram did not react (internal functions have no node there).
  const inDiagram=highlightDiagramNode(s);
  const diagramNote=(!inDiagram&&MODE==='oop'&&s.kind==='function'&&!isIfaceMethod(s))
    ?'<div class="note">not shown in the type diagram &mdash; it maps types and interface methods only; use the &#128309; sphere view for this function&#39;s call graph.</div>'
    :'';
  $('detail').innerHTML=
    `<div class="meta"><b>Code name</b></div>`+
    `<h3>${esc(s.name)}<span class="kind">${s.kind}</span></h3>`+
    `<div class="meta"><span class="dot" style="display:inline-block;width:9px;height:9px;border-radius:50%;background:${modColor(s.module)}"></span> ${esc(s.module)} &nbsp;·&nbsp; ${esc(s.file)}:${s.line}</div>`+also+docHtml+
    `<div style="display:flex;gap:6px;flex-wrap:wrap;margin:2px 0 4px">`+
    `<button onclick="openFocus(${id})" style="font-size:11px;padding:3px 8px;background:#0b2536;color:#e2e8f0;border:1px solid var(--acc);border-radius:6px;cursor:pointer">🔵 call-focus sphere view</button>`+
    `<a href="${wbBase()}/symbol/${encodeURIComponent(s.name)}?module=${encodeURIComponent(s.module)}&file=${encodeURIComponent('src/'+s.file)}&line=${s.line}" title="workbench source-definition view: static test references for this code name; overloaded methods may be family-level" style="font-size:11px;padding:3px 8px;background:#132615;color:#e2e8f0;border:1px solid #3fb950;border-radius:6px;text-decoration:none">🧪 tests linked to this source</a></div>`+
    diagramNote+
    `<h2>calls (${fns.length})</h2><div class="chips">${callLink(fns)}</div>`+
    (tys.length?`<h2>uses types (${tys.length})</h2><div class="chips">${callLink(tys)}</div>`:'')+
    `<h2>used by (${s.callers.length})</h2><div class="chips">${callLink(s.callers)}</div>`+
    `<div class="note">calls / used-by are inferred by an approximate static name scan.</div>`+
    `<h2>implementation</h2><pre>${esc(s.src)}</pre>`+
    `<h2>call tree — what it calls &amp; why (recursive)</h2>`+
    `<div class="note">each child = a sub-function it calls · grey text = that function's role (why it's called) · ↳ = the call site · ▸/▾ expand to the leaves · ↩ = already shown</div>`+
    callTreeHtml(id)+
    `<h2>usage examples</h2>${examples}`;
  $('detail').scrollTop=0;
}

// ---- call-focus sphere view: one function as a hub, its callees radiating out ----
// toggle the lower info pane between the split (graph + panel) and full-window (panel only)
function toggleInfoPane(){
  const max=$('focus').classList.toggle('info-max');
  const b=$('infotog');if(b)b.textContent=max?'▼ Restore split':'▲ Expand panel';
  if(!max&&net&&MODE==='focus')requestAnimationFrame(()=>{try{net.setSize('100%','100%');net.redraw();net.fit({animation:false});}catch(e){}});
}
function showFocusShell(){
  $('net').style.display='none';$('algo').style.display='none';$('detail').style.display='none';
  $('focus').style.display='flex';
  $('viewtog').textContent='▦ JUNA pipeline';
}
// a focus level is either {sym:id} (call-sphere) or {iface:name} (implements-sphere)
function focusState(){return IFACEFOCUS?{iface:IFACEFOCUS}:{sym:LASTFOCUS};}
function ifaceImpls(name){return DATA.symbols.filter(s=>s.kind==='function'&&s.name===name&&isIfaceMethod(s));}
function stateValid(st){return st.iface?ifaceImpls(st.iface).length>0:(st.sym!=null&&!!SYM[st.sym]);}
// draw one focus level; touches no stack/prev state, so it is reusable by "back"
function renderFocusState(st){
  if(!stateValid(st))return false;
  if(st.iface){const impls=ifaceImpls(st.iface);LASTFOCUS=null;IFACEFOCUS=st.iface;
    showFocusShell();setCrumb();drawFocusIface(st.iface,impls);
    $('focusinfo').innerHTML=focusIfaceInfoHtml(st.iface,impls);$('focusinfo').scrollTop=0;drawFocusArts();return true;}
  const id=st.sym;LASTFOCUS=id;IFACEFOCUS=null;
  showFocusShell();setCrumb();drawFocus(id);
  $('focusinfo').innerHTML=focusInfoHtml(id);$('focusinfo').scrollTop=0;drawFocusArts();return true;
}
// going to a new sphere: if already in focus, push the current level so "back" walks up one step
function pushFocus(st){
  if(!DATA||!stateValid(st))return;             // ignore stale/invalid targets (current view stays usable)
  if(MODE==='focus')FOCUSSTACK.push(focusState()); else {PREVFOCUSMODE=MODE;FOCUSSTACK=[];}
  MODE='focus';renderFocusState(st);
}
function openFocus(id){pushFocus({sym:id});}
// interface method (generic, multiple dispatch) → hub = the contract method, spokes = the modulations that implement it
function openFocusIface(name){if(!DATA)return;
  if(!ifaceImpls(name).length){
    // Shared helpers such as payload_rate have a concrete body in
    // Modulations.jl rather than one override per modulation.
    const shared=DATA.symbols.find(s=>s.kind==='function'&&s.name===name&&s.module==='Modulations');
    if(shared){openFocus(shared.id);return;}
    selectIface(name);return;
  }
  pushFocus({iface:name});
}
function exitFocus(){
  while(FOCUSSTACK.length){if(renderFocusState(FOCUSSTACK.pop()))return;}   // back = up one focus level (skip stale)
  IFACEFOCUS=null;FOCUSSTACK=[];setView(PREVFOCUSMODE||'oop');              // then back to the view we came from (OOP/pipeline)
}
function drawFocus(id){
  const s=SYM[id];if(!s)return;
  const ring=s.calls.filter(c=>SYM[c]);   // functions it calls + types it uses
  const nodes=[{id:'C',label:s.name,shape:'dot',size:48,x:0,y:0,physics:false,borderWidth:4,
    color:{background:modColor(s.module),border:'#ffffff',highlight:{background:modColor(s.module),border:'#ffffff'},hover:{border:'#ffffff'}},
    font:{color:'#f8fafc',size:17,face:'ui-monospace',strokeWidth:5,strokeColor:'#0b1220'},
    title:`${esc(s.name)} — ${esc(s.module)}\nthe function you are exploring\ncalls ${ring.length}, used by ${s.callers.length}`}];
  const edges=[];const n=ring.length;const R=Math.min(390,150+n*15);
  ring.forEach((c,i)=>{const cs=SYM[c],ty=isType(c);
    const a=-Math.PI/2+i*2*Math.PI/Math.max(1,n);
    nodes.push({id:'n:'+c,label:cs.name,shape:ty?'diamond':'dot',size:ty?15:18,physics:false,
      x:Math.round(Math.cos(a)*R),y:Math.round(Math.sin(a)*R),
      color:{background:modColor(cs.module),border:'#1e293b',highlight:{background:modColor(cs.module),border:'#fff'},hover:{border:'#fff'}},
      font:{color:'#e2e8f0',size:12,face:'ui-monospace',strokeWidth:3,strokeColor:'#0f172a'},
      title:`${esc(cs.name)} — ${esc(cs.module)}`+(ty?'  [type]':'')+(cs.doc?`\n${esc(cs.doc.a)}`:'')+'\nclick to re-center on this function'});
    edges.push({id:'e'+i,from:'C',to:'n:'+c,arrows:{to:{enabled:true,scaleFactor:0.75}},dashes:ty,
      color:{color:ty?'#475569':'#38bdf8',highlight:'#7dd3fc',opacity:0.85},width:ty?1:2});});
  const opts={physics:false,interaction:{hover:true,tooltipDelay:110,dragNodes:true,dragView:true,zoomView:true},
    nodes:{borderWidth:2},edges:{smooth:false}};
  if(net)net.destroy();
  net=new vis.Network($('focusnet'),{nodes:new vis.DataSet(nodes),edges:new vis.DataSet(edges)},opts);
  net.on('click',p=>{if(p.nodes.length){const nid=String(p.nodes[0]);if(nid.slice(0,2)==='n:')openFocus(+nid.slice(2));}});
  net.once('afterDrawing',()=>net.fit({animation:false}));
}
function focusInfoHtml(id){
  const s=SYM[id];
  const callees=s.calls.filter(c=>SYM[c]&&!isType(c));
  const tys=s.calls.filter(c=>SYM[c]&&isType(c));
  const roleChip=c=>{const cs=SYM[c];return `<div class="fchip" onclick="openFocus(${c})"><span class="chip">${esc(cs.name)}</span><span class="frole">${cs.doc?esc(cs.doc.a):esc(cs.module+' · '+cs.kind)}</span></div>`;};
  const flat=c=>{const cs=SYM[c];return `<span class="chip" onclick="openFocus(${c})">${esc(cs.name)}<span style="color:#64748b"> ·${esc(cs.module)}</span></span>`;};
  return `<div class="fhead"><button class="backbtn" onclick="exitFocus()" title="go back one step (up the focus stack, then to the graph)">‹ Back</button>`+
    `<button class="flowbtn" onclick="openFlowTab(${id})" title="open a full-page, recursive call-flow (every level, to the leaves) in a new tab">↗ Recursive call-flow (new tab)</button>`+
    `<button class="panetog" id="infotog" onclick="toggleInfoPane()" title="expand this panel to fill the window, or restore the split with the graph">${$('focus').classList.contains('info-max')?'▼ Restore split':'▲ Expand panel'}</button></div>`+
    `<h3>${esc(s.name)}<span class="kind">${esc(s.kind)}</span></h3>`+
    `<div class="meta"><span class="dot" style="display:inline-block;width:9px;height:9px;border-radius:50%;background:${modColor(s.module)}"></span> ${esc(s.module)} · ${esc(s.file)}:${s.line} · calls ${callees.length}, used by ${s.callers.length}</div>`+
    docBlock(s)+
    focusConcept(s)+
    callSeqHtml(s)+
    `<div class="note">Center sphere = <b>${esc(s.name)}</b>. Each spoke is a function it <b>calls</b> (◇ dashed = a type it uses); the arrow shows call direction (hub → callee). Click any spoke — here or in the graph — to make it the new center and walk the call chain to the edge.</div>`+
    `<h2>calls — what it depends on (${callees.length})</h2>`+
    (callees.length?`<div class="fchips">${callees.map(roleChip).join('')}</div>`:'<div class="empty">leaf — calls no in-tree functions (edge of the tree).</div>')+
    (tys.length?`<h2>uses types (${tys.length})</h2><div class="chips">${tys.map(flat).join('')}</div>`:'')+
    `<h2>used by — who calls it (${s.callers.length})</h2><div class="chips">${s.callers.length?s.callers.map(flat).join(''):'<span class="empty">none in-tree (entry point / dynamic dispatch)</span>'}</div>`+
    `<h2>implementation</h2><pre>${esc(s.src)}</pre>`;
}
function drawFocusIface(name,impls){
  const nodes=[{id:'C',label:name+'()',shape:'dot',size:46,x:0,y:0,physics:false,borderWidth:4,
    color:{background:'#a78bfa',border:'#ffffff',highlight:{background:'#a78bfa',border:'#ffffff'},hover:{border:'#ffffff'}},
    font:{color:'#0b1220',size:16,face:'ui-monospace',strokeWidth:4,strokeColor:'#ede9fe'},
    title:`${esc(name)}() — interface method (Modulations contract)\nimplemented by ${impls.length} modulations via multiple dispatch`}];
  const edges=[];const n=impls.length;const R=Math.min(360,150+n*30);
  impls.forEach((s,i)=>{const a=-Math.PI/2+i*2*Math.PI/Math.max(1,n);
    nodes.push({id:'n:'+s.id,label:s.module+'.'+s.recv,shape:'diamond',size:18,physics:false,
      x:Math.round(Math.cos(a)*R),y:Math.round(Math.sin(a)*R),
      color:{background:modColor(s.module),border:'#1e293b',highlight:{background:modColor(s.module),border:'#fff'},hover:{border:'#fff'}},
      font:{color:'#e2e8f0',size:12,face:'ui-monospace',strokeWidth:3,strokeColor:'#0f172a'},
      title:`${esc(s.module)}.${esc(s.recv)} implements ${esc(name)}()\nclick to open its call-sphere`});
    edges.push({id:'e'+i,from:'n:'+s.id,to:'C',arrows:{to:{enabled:true,scaleFactor:0.6}},dashes:true,
      color:{color:'#7c5ccb',highlight:'#c4b5fd',opacity:0.9},width:1.5});});
  const opts={physics:false,interaction:{hover:true,tooltipDelay:110,dragNodes:true,dragView:true,zoomView:true},nodes:{borderWidth:2},edges:{smooth:false}};
  if(net)net.destroy();
  net=new vis.Network($('focusnet'),{nodes:new vis.DataSet(nodes),edges:new vis.DataSet(edges)},opts);
  net.on('click',p=>{if(p.nodes.length){const nid=String(p.nodes[0]);if(nid.slice(0,2)==='n:')openFocus(+nid.slice(2));}});
  net.once('afterDrawing',()=>net.fit({animation:false}));
}
function focusIfaceInfoHtml(name,impls){
  const chip=s=>`<div class="fchip" onclick="openFocus(${s.id})"><span class="chip">${esc(s.module)}.${esc(s.recv)}</span><span class="frole">${s.doc?esc(s.doc.a):'implements '+esc(name)+'()'}</span></div>`;
  return `<div class="fhead"><button class="backbtn" onclick="exitFocus()" title="go back one step (up the focus stack, then to the graph)">‹ Back</button>`+
    `<button class="panetog" id="infotog" onclick="toggleInfoPane()" title="expand this panel to fill the window, or restore the split with the graph">${$('focus').classList.contains('info-max')?'▼ Restore split':'▲ Expand panel'}</button></div>`+
    `<h3>${esc(name)}()<span class="kind">interface method</span></h3>`+
    `<div class="meta">Function in the Modulations contract. ${impls.length} concrete overrides found in this source tree; a generic definition may also supply shared or default behavior.</div>`+
    `<div class="note">Center sphere = the contract function <b>${esc(name)}()</b>; each spoke is a concrete override discovered in this tree (dashed arrow points into the contract). Click an override to open its call-sphere.</div>`+
    `<h2>concrete overrides (${impls.length})</h2><div class="fchips">${impls.map(chip).join('')}</div>`;
}
// Per-symbol detail stays source-backed: exact source, lexical call edges, and
// call sequences. Authored teaching cards were removed because receiver modes
// and framing profiles can evolve independently of prose embedded in this UI.
const FOCUS_CONCEPTS={};
function focusConcept(s){const c=FOCUS_CONCEPTS[s.module+'.'+s.name];if(!c)return '';
  const steps=c.steps.map(st=>`<li><b>${esc(st.t)}</b> — ${st.d}</li>`).join('');
  const arts=c.arts.map(a=>`<figure class="cfig"><canvas class="art" data-art="${a.art}"></canvas><figcaption>${esc(a.cap)}</figcaption></figure>`).join('');
  return `<div class="concept"><div class="ctitle">▸ ${esc(c.title)}</div><div class="cintro">${c.intro}</div>`+
    `<ol class="csteps">${steps}</ol>${arts}`+(c.note?`<div class="cnote">${c.note}</div>`:'')+
    (c.credit?`<div class="ccredit">${esc(c.credit)}</div>`:'')+`</div>`;
}
function drawArtsIn(root){requestAnimationFrame(()=>{
  root.querySelectorAll('canvas.art').forEach(cv=>
   ({ofdmtx:artOfdmTx,ofdmrx:artOfdmRx,cstl:artCstl,ici:artIci,layout:artLayout,frame:artFrame,framepacket:artFramePacket,message:artMessage,packet:artPacket,pfft:artPfft,tanner:artTanner,families:artFamilies,gradient:artGradient}[cv.dataset.art]||(()=>{}))(cv));
  root.querySelectorAll('canvas.mini').forEach(cv=>{try{drawMini(cv,cv.dataset.mini);}catch(e){}});});}
function drawFocusArts(){drawArtsIn($('focusinfo'));}
// classify a function into a schematic family by name keywords (a best-effort visual hint per flow block)
function miniKind(s){const n=s.name.toLowerCase();
  if(/valid/.test(n))return 'check';
  if(/scratch|initial|^_?init$|_init\b|alloc|zeros/.test(n))return 'alloc';
  if(/adam|loss_and_grad|gradient_solve|_grad!|\bgrad\b|descent|loss/.test(n))return 'grad';
  if(/candidate|better|select/.test(n))return 'select';
  if(/posterior|confidence|tie_mse|\binitial/.test(n))return 'conf';
  if(/build_message|_message\b|inner_bit|inner/.test(n))return 'msg';
  if(/encode|ldpc|bp_decode|syndrome|tanner|build_graph|create_code|_code\b|decode\b/.test(n))return 'tanner';
  if(/layout|pilot|carrier_grid|active_indices|_bands|tone/.test(n))return 'comb';
  if(/equaliz|combine|branch|fit_branch|_weights|residual|\brls\b/.test(n))return 'combine';
  if(/fft|ifft/.test(n))return 'fft';
  if(/psk|carrier_symbol|constellation|data_metrics|data_symbols|_metrics|\bllr/.test(n))return 'cstl';
  if(/modulate_block|_block\b|frame|sync|chirp/.test(n))return 'packet';
  if(/waveform|complex|resampl|doppler|corr/.test(n))return 'wave';
  if(/blocklen|bitspersymbol|signallength|ndata|_n_inner|nblocks|nframes|length|count/.test(n))return 'count';
  return 'fn';}
// tiny per-block schematics (~46x30)
function drawMini(cv,k){const[x,w,h]=hd(cv);const m=4,iw=w-2*m,ih=h-2*m,cx=w/2,cy=h/2;
  x.lineWidth=1.4;
  const bars=(arr,col)=>{const bw=iw/arr.length;arr.forEach((v,i)=>{x.fillStyle=col(i);x.fillRect(m+i*bw+0.5,h-m-v*ih,Math.max(1.5,bw-1.5),v*ih);});};
  if(k==='comb'){bars([1,.4,.4,1,.4,.4,1],i=>i%3===0?AC.gold:AC.acc);}
  else if(k==='fft'){bars([.5,.9,.4,.75,.3,.6],()=>AC.acc);}
  else if(k==='msg'){const n=8,bw=iw/n;for(let i=0;i<n;i++){x.fillStyle=i%2===0?AC.vio:AC.teal;x.fillRect(m+i*bw+0.5,cy-5,Math.max(1.5,bw-1.5),10);}}
  else if(k==='grad'){x.strokeStyle=AC.gold;x.beginPath();for(let i=0;i<=24;i++){const t=i/24;x.lineTo(m+i*iw/24,m+ih*(0.12+0.85*(1-t)*(1-t)));}x.stroke();x.fillStyle=AC.gold;x.beginPath();x.arc(w-m,m+ih*0.12,2.2,0,7);x.fill();}
  else if(k==='conf'){x.strokeStyle=AC.teal;x.beginPath();for(let i=0;i<=24;i++){const t=(i/24-0.5)*8;x.lineTo(m+i*iw/24,h-m-ih/(1+Math.exp(-t)));}x.stroke();}
  else if(k==='tanner'){const sq=[m+iw*0.3,m+iw*0.7],ci=[m+iw*0.2,m+iw*0.5,m+iw*0.8];x.strokeStyle=AC.line;[[0,0],[0,1],[1,1],[1,2]].forEach(e=>{x.beginPath();x.moveTo(sq[e[0]],m+6);x.lineTo(ci[e[1]],h-m-5);x.stroke();});x.strokeStyle=AC.vio;sq.forEach(s=>x.strokeRect(s-3,m,6,6));x.strokeStyle=AC.teal;ci.forEach(c=>{x.beginPath();x.arc(c,h-m-3,3,0,7);x.stroke();});}
  else if(k==='combine'){x.strokeStyle=AC.teal;[0.2,0.5,0.8].forEach(fy=>{x.beginPath();x.moveTo(m,m+ih*fy);x.lineTo(w-m-5,cy);x.stroke();});x.fillStyle=AC.vio;x.beginPath();x.arc(w-m-4,cy,3,0,7);x.fill();}
  else if(k==='select'){x.strokeStyle=AC.line;x.strokeRect(m,cy-6,14,12);x.strokeStyle=AC.teal;x.strokeRect(w-m-14,cy-6,14,12);x.fillStyle=AC.teal;x.font='bold 11px system-ui';x.textAlign='center';x.fillText('✓',w-m-7,cy+4);}
  else if(k==='alloc'){x.strokeStyle=AC.mut;x.setLineDash([2,2]);for(let i=0;i<3;i++)for(let j=0;j<2;j++)x.strokeRect(m+i*(iw/3)+1,m+j*(ih/2)+1,iw/3-2,ih/2-2);x.setLineDash([]);}
  else if(k==='packet'){x.fillStyle='rgba(245,158,11,.5)';x.fillRect(m,cy-6,10,12);x.fillStyle='rgba(56,189,248,.4)';x.fillRect(m+11,cy-6,iw-11,12);x.strokeStyle=AC.line;x.strokeRect(m,cy-6,iw,12);}
  else if(k==='wave'){x.strokeStyle=AC.acc;x.beginPath();for(let i=0;i<=28;i++)x.lineTo(m+i*iw/28,cy-7*Math.sin(i/28*Math.PI*3));x.stroke();}
  else if(k==='cstl'){[[0.3,0.3],[0.7,0.3],[0.3,0.7],[0.7,0.7]].forEach(p=>{x.fillStyle=AC.gold;x.beginPath();x.arc(m+p[0]*iw,m+p[1]*ih,2,0,7);x.fill();});x.strokeStyle=AC.line;x.beginPath();x.moveTo(cx,m);x.lineTo(cx,h-m);x.moveTo(m,cy);x.lineTo(w-m,cy);x.stroke();}
  else if(k==='check'){x.strokeStyle=AC.teal;x.lineWidth=2.2;x.beginPath();x.moveTo(cx-7,cy);x.lineTo(cx-1,cy+6);x.lineTo(cx+8,cy-6);x.stroke();}
  else if(k==='count'){x.strokeStyle=AC.mut;for(let i=0;i<5;i++){const px=m+i*(iw/5)+2;x.beginPath();x.moveTo(px,h-m);x.lineTo(px,h-m-(i%2?ih*0.5:ih*0.85));x.stroke();}}
  else{x.fillStyle=AC.mut;x.font='italic 13px ui-monospace,monospace';x.textAlign='center';x.fillText('ƒ',cx,cy+5);}}

// ---- call-sequence flowchart: the ORDER a function calls its sub-functions (seq / loop / parallel) ----
function _callSite(parent,name){
  const pat=new RegExp('\\b'+name.replace(/[.*+?^${}()|[\]\\]/g,'\\$&').replace(/!$/,'')+'!?\\b');
  const ls=parent.src.split('\n');
  for(let i=0;i<ls.length;i++){if(pat.test(ls[i]))return {li:i,text:ls[i]};}
  return null;
}
// approximate: is line li inside a for/while/do(map) block within this function body?
function _insideLoop(src,li){
  const ls=src.split('\n');let loopDepth=0;const stack=[];
  for(let i=0;i<=li&&i<ls.length;i++){const t=ls[i].trim();
    if(/^end\b/.test(t)){const k=stack.pop();if(k==='loop')loopDepth--;continue;}
    const m=t.match(/^(for|while|function|if|let|begin|quote|try|struct|module|macro)\b/);
    if(m){const lp=(m[1]==='for'||m[1]==='while');stack.push(lp?'loop':'blk');if(lp)loopDepth++;}
    if(/\)\s*do\b|\bdo\b\s*(#.*)?$/.test(t)){stack.push('loop');loopDepth++;}
  }
  return loopDepth>0;
}
function _callKind(src,li,t){
  if(/@(threads|spawn|distributed|async)\b|\bpmap\(|\basyncmap\(/.test(t))return 'parallel';
  if(_insideLoop(src,li))return 'loop';
  if(/\bfor\b|\bwhile\b|\bmap\(|\bmapreduce\(|\bforeach\(|\bbroadcast\(|\.\(|\[[^\]]*\bfor\b/.test(t))return 'loop';
  return 'seq';
}
// shared: order a function's in-tree callees by first call-site line; group same-line; classify seq/loop/parallel
function callSteps(s){
  const callees=s.calls.filter(c=>SYM[c]&&!isType(c));
  const found=[],missing=[];
  callees.forEach(c=>{const cs=_callSite(s,SYM[c].name);
    if(cs)found.push({id:c,li:cs.li,kind:_callKind(s.src,cs.li,cs.text)});else missing.push(c);});
  found.sort((a,b)=>a.li-b.li);
  const steps=[];found.forEach(f=>{const last=steps[steps.length-1];
    if(last&&last.li===f.li){last.items.push(f);if(f.kind!=='seq')last.kind=f.kind;}
    else steps.push({li:f.li,kind:f.kind,items:[f]});});
  return {steps,missing};
}
function callSeqHtml(s){
  const callees=s.calls.filter(c=>SYM[c]&&!isType(c));
  if(callees.length<2)return '';
  const {steps,missing}=callSteps(s);
  if(!steps.length)return '';
  const bdg=k=>k==='parallel'?'<span class="fbadge par" title="concurrency macro (@threads/@spawn/…)">⇉ parallel</span>'
              :k==='loop'?'<span class="fbadge loop" title="inside a loop / map / comprehension — runs once per element">⟳ per-element</span>':'';
  const blk=f=>{const cs=SYM[f.id];return `<span class="fblk" onclick="openFocus(${f.id})" style="border-left:3px solid ${modColor(cs.module)}">`+
    `<canvas class="mini" data-mini="${miniKind(cs)}" title="schematic hint of what this step does"></canvas>`+
    `<span class="fcol"><span class="fname">${esc(cs.name)}</span>${bdg(f.kind)}<span class="frole">${cs.doc?esc(cs.doc.a):esc(cs.module)}</span></span></span>`;};
  let chart=`<div class="fnode fstart">▸ enter ${esc(s.name)}()</div>`;
  steps.forEach(st=>{chart+='<div class="fconn">↓</div>'+
    `<div class="fstep${st.items.length>1?' multi':''}">${st.items.map(blk).join('')}${st.items.length>1?'<div class="fsame">same source line — evaluated together</div>':''}</div>`;});
  if(missing.length)chart+=`<div class="fconn">↓</div><div class="fnode fmuted">+ ${missing.length} call${missing.length>1?'s':''} via dispatch/macro (call site not located): ${missing.map(c=>`<span class="fmini" onclick="openFocus(${c})">${esc(SYM[c].name)}</span>`).join(' · ')}</div>`;
  chart+='<div class="fconn">↓</div><div class="fnode fend">↩ return</div>';
  return `<div class="flow"><div class="ctitle">▸ Call sequence — the order ${esc(s.name)} runs (click a step to drill in)</div>`+
    `<div class="flowcap">Top → bottom in source order · <span class="fbadge loop">⟳ per-element</span> = inside a loop/map · <span class="fbadge par">⇉ parallel</span> = concurrency macro · best-effort static scan, runtime control flow may differ.</div>`+
    `<div class="flowchart">${chart}</div>`+
    `<button class="flowbtn" onclick="openFlowTab(${s.id})" title="open a full-page, recursive call-flow (every level, to the leaves) in a new tab">↗ Open full recursive call-flow (new tab)</button></div>`;
}
function openFlowTab(id){try{window.open(location.pathname+location.search+'#flow='+id,'_blank');}catch(e){openFlowPage(id);}}
// ---- recursive call-flow (new-tab full page): every level to the leaves, in call order ----
function reachableFns(rootId){const seen=new Set(),stack=[rootId];
  while(stack.length){const id=stack.pop();if(seen.has(id))continue;seen.add(id);
    const s=SYM[id];if(!s)continue;s.calls.forEach(c=>{if(SYM[c]&&!isType(c)&&!seen.has(c))stack.push(c);});}
  return seen;}
function recursiveFlowHtml(id,seen,depth){
  const s=SYM[id];if(!s)return '';
  const {steps,missing}=callSteps(s);
  const blocks=[];
  steps.forEach(st=>st.items.forEach(f=>blocks.push({id:f.id,kind:f.kind})));
  missing.forEach(c=>blocks.push({id:c,kind:'seq',missing:true}));
  if(!blocks.length)return '';
  let html='<div class="rkids">';
  blocks.forEach((b,i)=>{const cs=SYM[b.id];
    if(i)html+='<div class="rconn">↓</div>';
    const childHas=cs.calls.some(x=>SYM[x]&&!isType(x));
    const rep=seen.has(b.id);
    const expandable=childHas&&!rep;
    if(expandable)seen.add(b.id);
    const collapsed=depth>=1;
    const tog=expandable?`<span class="rtog">${collapsed?'▸':'▾'}</span>`
              :rep?'<span class="rtog rrep" title="expanded elsewhere above">↩</span>'
              :'<span class="rdot">•</span>';
    const badge=b.kind==='parallel'?'<span class="fbadge par" title="concurrency macro">⇉</span>'
               :b.kind==='loop'?'<span class="fbadge loop" title="inside a loop / map">⟳</span>':'';
    const nmTitle=esc(rep?(cs.name+' is expanded above — click to re-root the flow here'):('re-root the flow at '+cs.name));
    html+=`<div class="rstep"><div class="rblk" style="border-left:3px solid ${modColor(cs.module)}">`+
      `${tog}<span class="rname" data-foc="${b.id}" title="${nmTitle}">${esc(cs.name)}</span>${badge}`+
      `<span class="rrole">${cs.doc?esc(cs.doc.a):(b.missing?'(reached via dispatch/macro)':esc(cs.module))}</span></div>`+
      (expandable?`<div class="rsub${collapsed?' collapsed':''}">${recursiveFlowHtml(b.id,seen,depth+1)}</div>`:'')+
      `</div>`;
  });
  return html+'</div>';
}
function flowPageHtml(rootId){
  const s=SYM[rootId];
  const tree=recursiveFlowHtml(rootId,new Set([rootId]),0);
  const reach=[...reachableFns(rootId)].filter(id=>FOCUS_CONCEPTS[SYM[id].module+'.'+SYM[id].name]);
  const order={'_layout':0,'_bp_decode':1},ord=n=>order[n]===undefined?9:order[n];
  reach.sort((a,b)=>ord(SYM[a].name)-ord(SYM[b].name));
  const explain=reach.map(id=>`<div class="fp-concept">${focusConcept(SYM[id])}</div>`).join('');
  return `<div class="flowpage-h"><button class="backbtn" onclick="closeFlow()" title="return to the explorer">✕ close</button>`+
    `<div class="fp-title">Recursive call-flow — <code>${esc(s.module)}.${esc(s.name)}</code></div>`+
    `<div class="fp-sub">Every function <b>${esc(s.name)}</b> reaches, in call order, down to the leaves. ▸/▾ expands a step · <span class="fbadge loop">⟳</span> per-element (loop/map) · <span class="fbadge par">⇉</span> parallel · ↩ = already expanded above · click a name to re-root. Static-scan approximation.</div></div>`+
    `<div class="rwrap"><div class="rblk rroot" style="border-left:3px solid ${modColor(s.module)}"><span class="rdot">▸</span><span class="rname rootname">${esc(s.name)}()</span><span class="rrole">${s.doc?esc(s.doc.a):esc(s.module)}</span></div>${tree||'<div class="rkids"><div class="rstep"><div class="rblk"><span class="rdot">•</span><span class="rrole">leaf — calls no in-tree functions</span></div></div></div>'}</div>`+
    (explain?`<div class="fp-explain"><div class="fp-exh">Key steps explained — layout &amp; decoder</div>${explain}</div>`:'');
}
function openFlowPage(id){if(!DATA||!SYM[id])return;
  $('wrap').style.display='none';
  const fp=$('flowpage');fp.style.display='block';
  fp.innerHTML=flowPageHtml(id);fp.scrollTop=0;
  drawArtsIn(fp);
  try{location.hash='flow='+id;}catch(e){}
  document.title='call-flow: '+SYM[id].name;
}
function reRoot(id){if(SYM[id])openFlowPage(id);}
function closeFlow(){$('flowpage').style.display='none';$('wrap').style.display='flex';
  try{if(location.hash)history.replaceState(null,'',location.pathname+location.search);}catch(e){}
  document.title='source definition explorer';}

// ---- interface I/O + per-implementation reference page ----------------------
const IFACE_IO=[
 {m:'init',sig:'init(m, fc, fs)',args:[['m','the modulation object'],['fc','carrier frequency (Hz)'],['fs','baseband sample rate (Hz)']],out:'nothing — initializes defaults and receiver state',note:'The Juna implementation clears caches and restores any profile-specific identity required by its selected receiver.'},
 {m:'modulate',sig:'modulate(m, bits, fc, fs)',args:[['m','modulation'],['bits','payload bits (0/1)'],['fc','carrier Hz'],['fs','sample rate Hz']],out:'a complex-baseband Vector{ComplexF64}',note:'Encodes bits into a baseband waveform (length = signallength).'},
 {m:'demodulate',sig:'demodulate(m, nbits, x, fc, fs)',args:[['m','modulation'],['nbits','expected payload bit count'],['x','received complex baseband'],['fc','carrier Hz'],['fs','sample rate Hz']],out:'a tuple (metrics, cfo)',note:'metrics: one soft value per bit, sign = decision (positive ⇒ bit 1). cfo: coarse carrier/Doppler-offset estimate, 0 if none.'},
 {m:'isvalid',sig:'isvalid(m, fc, fs)',args:[['m','modulation'],['fc','carrier Hz'],['fs','sample rate Hz']],out:'Bool',note:'Are the modulation parameters valid for (fc, fs)? Checked at the top of modulate / demodulate.'},
 {m:'bitspersymbol',sig:'bitspersymbol(m)',args:[['m','modulation']],out:'Int',note:'Information bits carried in ONE block / OFDM symbol.'},
 {m:'signallength',sig:'signallength(m, nbits, fc, fs)',args:[['m','modulation'],['nbits','payload bit count'],['fc','carrier Hz'],['fs','sample rate Hz']],out:'Int — a sample COUNT (not the signal)',note:'How many baseband samples carry at least nbits bits.'},
 {m:'payload_rate',sig:'payload_rate(m, nbits, fc, fs)',args:[['m','modulation'],['nbits','payload bit count'],['fc','carrier Hz'],['fs','sample rate Hz']],out:'Float — useful bits / second',note:'Derived helper = nbits·fs / signallength; includes every overhead, so always ≤ fs.'},
 {m:'frameblockcount',sig:'frameblockcount(m, fs)',args:[['m','modulation'],['fs','sample rate Hz']],out:'Int',note:'Largest number of complete blocks that fit the configured frame-duration budget, including synchronization overhead.'},
 {m:'framepayloadbits',sig:'framepayloadbits(m, fs)',args:[['m','modulation'],['fs','sample rate Hz']],out:'Int',note:'Maximum user-payload bits carried by frameblockcount(m, fs) blocks.'},
 {m:'refinement_objective',sig:'refinement_objective(m)',args:[['m','modulation']],out:'Symbol',note:'Declares the executable receiver-refinement capability; the interface default is :none.'},
];
const IMPLS=[
 {key:'Juna.Modulation',label:'Juna.Modulation',blurb:'The one concrete JunaCore modem type. Receiver behavior is selected by its source fields and the constructor facades declared in JunaCore.jl.',
  realize:[
   ['init','Modulations.init(m::Juna.Modulation, fc, fs) in juna/common.jl'],
   ['bitspersymbol','Modulations.bitspersymbol(m::Juna.Modulation) in juna/common.jl'],
   ['signallength','Modulations.signallength(m::Juna.Modulation, nbits, fc, fs) in juna/common.jl'],
   ['frameblockcount','Modulations.frameblockcount(m::Juna.Modulation, fs) in juna/common.jl'],
   ['framepayloadbits','Modulations.framepayloadbits(m::Juna.Modulation, fs) in juna/common.jl'],
   ['refinement_objective','Modulations.refinement_objective(m::Juna.Modulation) in juna/common.jl'],
   ['modulate','Modulations.modulate(m::Juna.Modulation, bits, fc, fs) in juna/common.jl'],
   ['demodulate','Modulations.demodulate(m::Juna.Modulation, nbits, x, fc, fs) in juna/common.jl'],
   ['isvalid','Base.isvalid(m::Juna.Modulation, fc, fs) in juna/common.jl'],
  ]},
];
const PARAM_DOC={
 nc:'FFT size / number of OFDM subcarriers (even and greater than two)',
 np:'cyclic-prefix length in samples (zero is allowed; must be shorter than nc)',
 bw:'occupied-bandwidth fraction — fraction of the nc−1 non-DC carriers that are active (1.0 = full band)',
 dc0:'RF-centre offset from the 24 kHz reference, in kHz; it does not shift the baseband carrier layout',
 sync:'enable LFM acquisition, the only profile this package builds',
 ldpc_k:'LDPC message length — information bits per codeword (includes inner pilots)',
 ldpc_n:'LDPC codeword length — coded bits per block (rate = ldpc_k / ldpc_n)',
 partial_fft_parts:'number of partial-FFT branches',
 pilot_ratio:'outer comb-pilot density — fraction of active tones that are pilots; snapped to the nearest 1/k spacing',
 inner_pilot_ratio:'inner-pilot density among message bits (0 = off); snapped to the nearest 1/k spacing',
 code:'internal cache — the built LDPC code (rebuilt when the LDPC params change)',
 layout:'internal cache — the tone layout (rebuilt when geometry / dc0 / fs change)',
 bp_scratch:'internal cache — preallocated belief-propagation buffers',
};
// Source-order display is deliberate: the struct itself is the authority.
// Hand-maintained knob/advanced groupings had drifted as new receiver fields
// were added, so every current source field is now shown without reclassification.
const PARAM_GROUPS={};
const _HIDE_FIELDS=new Set();
const TIER={};
const TIER_LABEL={field:'source field'};
const JUNA_CONSTS=[];
function _structFields(typename){
  const i=typename.indexOf('.'),mod=typename.slice(0,i),nm=typename.slice(i+1);
  const t=DATA.symbols.find(s=>(s.kind==='struct'||s.kind==='type')&&s.module===mod&&s.name===nm);
  const map={},order=[];
  let nhidden=0;
  if(t)t.src.split('\n').forEach(l=>{const m=l.match(/^\s*([A-Za-z_]\w*)\s*::\s*([^=#]+?)\s*=\s*([^#]+?)\s*(?:#\s*(.*))?\s*$/);
    if(m){if(_HIDE_FIELDS.has(m[1])){nhidden++;return;}
      map[m[1]]={type:m[2].trim(),def:m[3].trim(),desc:(m[4]||'').trim()||PARAM_DOC[m[1]]||'—'};order.push(m[1]);}});
  return {map,order,nhidden};
}
// trim a stored signature to just the call form (drop leading `function ` and any ` = body`)
function cleanSig(sig){if(!sig)return '';
  let s=sig.replace(/^function\s+/,'').trim();
  const open=s.indexOf('('); if(open<0){const eq=s.indexOf('=');return (eq>=0?s.slice(0,eq):s).trim();}
  let depth=0,end=-1;
  for(let i=open;i<s.length;i++){const c=s[i];if(c==='(')depth++;else if(c===')'){if(--depth===0){end=i;break;}}}
  if(end<0)return s;
  const rest=s.slice(end+1),eq=rest.indexOf('=');
  return (eq>=0?s.slice(0,end+1)+rest.slice(0,eq):s).trim();
}
// every function, grouped by module: signature + Reads (inputs) + Returns (output) from the walkthrough doc
function allFnsHtml(){
  const fns=DATA.symbols.filter(s=>s.kind==='function');
  const byMod={}; fns.forEach(s=>(byMod[s.module]=byMod[s.module]||[]).push(s));
  const prio=['Juna','FixedPathChannel','LDPC','Modulations','JunaCore'],open=new Set(prio);
  const mods=Object.keys(byMod).sort((a,b)=>{const ia=prio.indexOf(a),ib=prio.indexOf(b);return (ia<0?99:ia)-(ib<0?99:ib)||a.localeCompare(b);});
  return mods.map(mod=>{
    const list=byMod[mod].slice().sort((a,b)=>a.name.localeCompare(b.name));
    const rows=list.map(s=>{const d=s.doc,sig=cleanSig(s.sig);
      return `<tr><td><span class="pmeth" data-foc="${s.id}" title="open ${esc(s.name)}'s call-focus sphere">${esc(s.name)}</span>`+
        (sig?`<div class="psig">${esc(sig)}</div>`:'')+(d?`<div class="pnote">${esc(d.a)}</div>`:'')+`</td>`+
        `<td>${d?esc(d.b):'<span class="pmut">— (no annotation)</span>'}</td>`+
        `<td>${d?esc(d.c):'<span class="pmut">—</span>'}</td></tr>`;}).join('');
    return `<details class="pmodbox"${open.has(mod)?' open':''}><summary><span class="dot" style="background:${modColor(mod)}"></span> ${esc(mod)} <span class="pmut">(${list.length})</span></summary>`+
      `<table class="ptab"><tr><th>function</th><th>reads (inputs)</th><th>returns (output)</th></tr>${rows}</table></details>`;
  }).join('');
}
function paramsPageHtml(){
  const ifaceRows=IFACE_IO.map(x=>
    `<tr><td><span class="pmeth" data-iface="${esc(x.m)}" title="open ${esc(x.m)}'s interface sphere">${esc(x.m)}</span><div class="psig">${esc(x.sig)}</div></td>`+
    `<td>${x.args.map(a=>`<div><code>${esc(a[0])}</code> — ${esc(a[1])}</div>`).join('')}</td>`+
    `<td><b>${esc(x.out)}</b>${x.note?`<div class="pnote">${esc(x.note)}</div>`:''}</td></tr>`).join('');
  const fieldTable=key=>{const {map,order,nhidden}=_structFields(key);
    const groups=PARAM_GROUPS[key]||[{t:'',f:order}];
    const tbl=groups.map(g=>{const rows=g.f.filter(n=>map[n]).map(n=>
        `<tr><td><code>${esc(n)}</code></td><td class="ptype">${esc(map[n].type)}</td><td class="pdef">${esc(map[n].def)}</td><td>${esc(map[n].desc)}</td></tr>`).join('');
      return rows?(g.t?`<div class="pgrp">${esc(g.t)}</div>`:'')+`<table class="ptab"><tr><th>field</th><th>type</th><th>default</th><th>what it controls</th></tr>${rows}</table>`:'';}).join('');
    return tbl+(nhidden?`<div class="cachenote">+ ${nhidden} internal memoization cache${nhidden>1?'s':''} (code, layout, bp_scratch) — mutable scratch built on first use &amp; reused, not configuration — hidden</div>`:'');};
  const implCards=IMPLS.map(im=>
    `<div class="pimpl"><div class="pimpl-h">${esc(im.label)}</div><div class="pimpl-b">${esc(im.blurb)}</div>`+
    `<div class="pgrp">how it implements the interface</div>`+
    `<table class="ptab">${im.realize.map(r=>`<tr><td><code>${esc(r[0])}</code></td><td>${esc(r[1])}</td></tr>`).join('')}</table>`+
    `<div class="pgrp">configuration — its struct fields</div>${fieldTable(im.key)}</div>`).join('');
  const facades=DATA.symbols.filter(s=>s.file==='JunaCore.jl'&&s.kind==='const'&&s.name==='Modulation'&&s.module!=='JunaCore')
    .sort((a,b)=>a.line-b.line);
  const facadeHtml=facades.length
    ? `<div class="psec">Public constructor facades from JunaCore.jl</div>`+
      `<div class="fp-sub" style="margin-bottom:8px">Each facade exports <code>Modulation</code> as an alias to a Juna constructor; all return the single concrete <code>Juna.Modulation</code> type.</div>`+
      `<div class="facades">${facades.map(s=>`<span class="facade-name" data-foc="${s.id}">${esc(s.module)}</span>`).join('')}</div>`
    : '';
  return `<div class="flowpage-h"><button class="backbtn" onclick="closeFlow()" title="return to the explorer">✕ close</button>`+
    `<div class="fp-title">Modulations interface — inputs, outputs &amp; implementations</div>`+
    `<div class="fp-sub">The current contract in <code>Modulations.jl</code>, followed by the one concrete modem type in this pinned source tree and its constructor facades. Click a method name to open its interface sphere. For a field-by-field breakdown, open the <span class="objlink" data-goobj="1">🧩 object viewer</span>.</div></div>`+
    `<div class="pwrap"><div class="psec">The interface contract</div>`+
    `<table class="ptab pio"><tr><th>method</th><th>inputs</th><th>output</th></tr>${ifaceRows}</table>`+
    `<div class="psec">Concrete implementation</div>${implCards}${facadeHtml}`+
    `<div class="psec">Every function — inputs &amp; outputs</div>`+
    `<div class="fp-sub" style="margin-bottom:8px">Drilling below the interface: every function from each function's signature and its Role / Reads / Returns annotation. Click a name to open its call-focus sphere; expand a module to see its functions.</div>`+
    `${allFnsHtml()}</div>`;
}
function openParamsPage(){if(!DATA)return;
  $('wrap').style.display='none';const fp=$('flowpage');fp.style.display='block';
  fp.innerHTML=paramsPageHtml();fp.scrollTop=0;
  fp.querySelectorAll('[data-iface]').forEach(el=>el.onclick=()=>{const n=el.getAttribute('data-iface');closeFlow();openFocusIface(n);});
  fp.querySelectorAll('[data-foc]').forEach(el=>el.onclick=()=>{const id=+el.getAttribute('data-foc');closeFlow();openFocus(id);});
  const go=fp.querySelector('[data-goobj]'); if(go)go.onclick=()=>openObjPage();
  try{location.hash='params';}catch(e){}document.title='interface I/O';}
function openParamsTab(){try{window.open(location.pathname+location.search+'#params','_blank');}catch(e){openParamsPage();}}

// ---- object viewer: every field of the modulation object ------------------
const OBJ_KEYS=['Juna.Modulation'];
// Package-level calling example for the concrete source type.
const OBJ_EXAMPLES={
 'Juna.Modulation':
`using JunaCore
fc = fs = 24_000.0
m = JunaCore.Juna.LiteModulation()
JunaCore.Modulations.init(m, fc, fs)
bits = rand(Bool, JunaCore.Modulations.bitspersymbol(m))
x = JunaCore.Modulations.modulate(m, bits, fc, fs)
metrics, cfo = JunaCore.Modulations.demodulate(m, length(bits), x, fc, fs)`,
};
function _structMeta(key){
  const i=key.indexOf('.'),mod=key.slice(0,i),nm=key.slice(i+1);
  const t=DATA.symbols.find(s=>(s.kind==='struct'||s.kind==='type')&&s.module===mod&&s.name===nm);
  const decl=t?((t.src.split('\n')[0]||'').trim()):(mod+'.'+nm);
  const sm=decl.match(/<:\s*([\w.]+)/);
  return {sym:t,decl,mod,nm,mutable:/\bmutable\b/.test(decl),kwdef:/@kwdef/.test(decl),sup:sm?sm[1]:''};
}
function _hlDecl(decl){let h=esc(decl);
  h=h.replace(/(struct\s+)([A-Za-z_]\w*)/,'$1<span class="ty">$2</span>');
  h=h.replace(/(&lt;:\s*)([\w.]+)/,'$1<span class="sup">$2</span>');
  h=h.replace(/\b(Base\.@kwdef|mutable|struct|abstract|primitive)\b/g,'<span class="kw">$1</span>');
  return h;}
function objPageHtml(active){
  active=OBJ_KEYS.indexOf(active)>=0?active:'Juna.Modulation';
  const meta=_structMeta(active),{map,order,nhidden}=_structFields(active);
  const tabs=OBJ_KEYS.map(k=>`<button class="objtab${k===active?' on':''}" data-obj="${esc(k)}">${esc(k)}</button>`).join('');
  const groups=PARAM_GROUPS[active]||[{t:'all fields',f:order}];
  const inG=new Set(); groups.forEach(g=>g.f.forEach(n=>inG.add(n)));
  const leftover=order.filter(n=>!inG.has(n));
  const allG=leftover.length?groups.concat([{t:'other fields',f:leftover}]):groups;
  const card=n=>{const f=map[n];if(!f)return '';const tr=TIER[n]||'field';
    return `<div class="ofield ot-${tr}"><div class="ofrow"><span class="ofname">${esc(n)}</span><span class="otier ot-${tr}">${TIER_LABEL[tr]}</span><span class="oftype">${esc(f.type)}</span><span class="ofdef">= ${esc(f.def)}</span></div><div class="ofdesc">${esc(f.desc)}</div></div>`;};
  const groupsHtml=allG.map(g=>{const fs=g.f.filter(n=>map[n]);if(!fs.length)return '';
    return `<div class="ogrp"><div class="ogrp-h">${esc(g.t||'fields')} <span class="objcount">(${fs.length})</span></div><div class="ofields">${fs.map(card).join('')}</div></div>`;}).join('');
  const constsHtml='';
  const cacheNote=nhidden?`<div class="cachenote">+ ${nhidden} internal memoization cache${nhidden>1?'s':''} — <code>code</code> (built LDPC code), <code>layout</code> (tone layout), <code>bp_scratch</code> (BP buffers): mutable scratch built on first use &amp; reused across calls, not configuration — hidden here.</div>`:'';
  const nf=order.length;
  const badges=`<div class="objbadges"><span class="objbadge">📦 <b>${nf}</b> fields</span>`+
    `<span class="objbadge">${meta.mutable?'✎ mutable':'🔒 immutable'}</span>`+
    (meta.kwdef?`<span class="objbadge">Base.@kwdef · keyword constructor</span>`:'')+
    (meta.sup?`<span class="objbadge">&lt;: <b>${esc(meta.sup)}</b></span>`:'')+
    (meta.sym?`<span class="objbadge" style="cursor:pointer" data-objsrc="${esc(meta.mod)}|${esc(meta.nm)}" title="open this type in the OOP graph (fields, methods, source)">📄 view in OOP graph</span>`:'')+`</div>`;
  return `<div class="flowpage-h"><button class="backbtn" onclick="closeFlow()" title="return to the explorer">✕ close</button>`+
    `<div class="fp-title">Object viewer — the modulation object’s fields</div>`+
    `<div class="fp-sub">All ${nf} fields of the current <code>Juna.Modulation</code> struct, in source order: type, default value, and inline source comment where present. For the methods and constructor facades, see the <span class="objlink" data-goparams="1">📥 interface I/O</span> page.</div></div>`+
    `<div class="pwrap"><div class="objtabs">${tabs}</div>`+
    `<div class="objhdr"><div class="objdecl">${_hlDecl(meta.decl)}</div>${badges}</div>`+
    `<div class="objlegend"><span class="otier ot-field">source field</span> parsed directly from <code>juna/common.jl</code>; no fields are hidden.</div>`+
    (OBJ_EXAMPLES[active]?`<div class="objex-h">Calling it — modulate / demodulate</div><pre class="objex">${esc(OBJ_EXAMPLES[active])}</pre>`:'')+
    `${groupsHtml}${cacheNote}${constsHtml}</div>`;
}
function _wireObjPage(){const fp=$('flowpage');
  fp.querySelectorAll('.objtab').forEach(el=>el.onclick=()=>openObjPage(el.getAttribute('data-obj')));
  fp.querySelectorAll('[data-objsrc]').forEach(el=>el.onclick=()=>{const k=el.getAttribute('data-objsrc');closeFlow();setView('oop');try{selectType(k);}catch(e){}});
  const gp=fp.querySelector('[data-goparams]'); if(gp)gp.onclick=()=>openParamsPage();
}
function openObjPage(active){if(!DATA)return;
  active=OBJ_KEYS.indexOf(active)>=0?active:'Juna.Modulation';
  $('wrap').style.display='none';const fp=$('flowpage');fp.style.display='block';
  fp.innerHTML=objPageHtml(active);fp.scrollTop=0;_wireObjPage();
  try{location.hash='object';}catch(e){}document.title='object viewer';}
function openObjTab(){try{window.open(location.pathname+location.search+'#object','_blank');}catch(e){openObjPage();}}

// ---- algorithm pipeline view (inspired by the OFDM probe workbench) --------
const PIPELINE=[
 {t:'API entry and receiver configuration',
  d:'Initialize defaults and receiver state, validate the concrete modulation, normalize the selected receiver profile, and enter the current transmit or receive implementation.',
  f:['receiver_profile','init','isvalid','modulate','demodulate']},
 {t:'Message, code, and OFDM transmit path',art:'packet',
  d:'Build the current tone layout and LDPC code, insert inner pilots, encode, map carrier symbols, and construct each OFDM block.',
  f:['_layout','_code','_build_message','_encode','_carrier_symbol','_modulate_block'],
  variants:[
   {name:'Frame-wide transmitter',
    d:'When a frame-wide code is selected, build one frame message and modulate the complete frame. When frame_crc_bits=16, append the CRC; when it is 0, preserve the payload unchanged.',
    f:['_frame_crc_append','_build_frame_message','_modulate_frame_wide_ldpc']}]},
 {t:'Top-level whole-frame/window dispatch',
  d:'At demodulate entry, frame-wide LDPC, fully-coupled, and guarded-physical profiles return through receivers that process the requested frame or coherence window before the ordinary per-block loop. Other profiles continue below.',
  f:['_demodulate_frame_wide_ldpc','_demodulate_fully_coupled','_demodulate_guarded_physical']},
 {t:'Receive validation and acquisition',
  d:'Prepare the waveform and enforce block lengths; when sync is enabled, take the coarse-Doppler path. When sync is disabled, use the prepared waveform directly. Physical replay and AWGN generation live outside JunaCore/src and are intentionally not shown here.',
  f:['_prepare_demodulation','_prepare_frame_observations','_require_block_samples','_coarse_doppler']},
 {t:'Partial-FFT observations and initial-candidate equalization',art:'pfft',
  d:'Form partial-FFT branches from contiguous time windows for every carrier, build standard and partial-FFT initial candidates, fit combiner weights, and remove residual pilot response.',
  f:['_branch_observations','_standard_candidate','_initial_candidate','_equalize_from_targets','_fit_branch_weights!','_residual_pilot_equalize']},
 {t:'Soft metrics and LDPC belief propagation',art:'tanner',
  d:'Convert equalized carriers to channel metrics, clamp known inner bits, run the selected BP check update, and measure the parity syndrome.',
  f:['_candidate_from_equalized','_channel_metrics_from_equalized','_decode_candidate','_apply_inner_clamps!','_bp_decode_impl','_syndrome_weight']},
 {t:'Per-block receiver dispatch',
  d:'Choose the standard/Partial-FFT initial candidate and dispatch the selected packet-local refinement path.',
  f:['_demodulate_block_candidate','_front_end_initial_candidate','_juna_candidate'],
  variants:[
   {name:'Lite posterior-anchor refinement',
    d:'Construct source-backed anchors and take the current Lite update.',
    f:['_juna_lite_candidate','_juna_anchor_targets','_juna_step']},
   {name:'Reduced W,z refinement',
    d:'Run the current reduced-gradient solve and its explicit loss/gradient.',
    f:['_juna_wz_candidate','_wz_loss_and_grad!'],art:'gradient'},
   {name:'Coupled C,W,z refinement',
    d:'Build a coupled candidate and evaluate its joint objective and gradient.',
    f:['_juna_wcz_candidate','_coupled_objective_and_gradient!']},
   {name:'Retained packet-local refiners',
    d:'Entry points for Turbo-MAP, guarded-gradient, and profiled-gradient candidate families that run inside the ordinary per-block path.',
    f:['_turbo_map_candidate','_gradient_guarded_candidate','_profiled_gradient_candidate']}]},
 {t:'Frame-wide global-code dispatch',
  d:'Build one frame code and route its observations through the exact frame receiver branch selected by the current modulation fields.',
  f:['_frame_code','_frame_candidate','_frame_bp_decode','_frame_receiver_trace'],
  variants:[
   {name:'Frame receiver branches',
    d:'Standard/Partial-FFT, Lite, W,z, C,W,z, fully-coupled, Turbo-MAP, profiled-gradient, profiled-C,z, and stateful band-RLS branches.',
    f:['_frame_static_trace','_frame_lite_refine','_frame_wz_refine','_frame_wcz_refine','_frame_fully_coupled_refine','_frame_turbo_map_refine','_frame_profiled_gradient_refine','_frame_profiled_cz_refine','_frame_juna_refine','_frame_stateful_band_rls']}]},
 {t:'Candidate selection and payload output',
  d:'Compare source-backed candidates, record the selection reason, remove inner/frame overhead, and return public metrics.',
  f:['_juna_better','_juna_selection_reason','_payload_from_metrics','_frame_payload_metrics','_write_payload_metrics!','demodulate_methods']},
];
const MODPRI=['Juna','FixedPathChannel','LDPC','Modulations'];
function pipelineFunctionNames(){
  const names=[];
  PIPELINE.forEach(st=>{(st.f||[]).forEach(n=>names.push(n));
    (st.variants||[]).forEach(v=>(v.f||[]).forEach(n=>names.push(n)));});
  return [...new Set(names)];
}
function resolveSym(name){let best=null,bp=999;DATA.symbols.forEach(s=>{if(s.name===name){let p=MODPRI.indexOf(s.module);if(p<0)p=50;if(p<bp){bp=p;best=s;}}});return best;}
function renderAlgo(){
  const host=$('algo');
  if(!DATA){host.innerHTML='<div class="empty">load a project first…</div>';return;}
  const missing=pipelineFunctionNames().filter(n=>!resolveSym(n));
  host.dataset.missing=String(missing.length);
  const chipsFor=f=>f.map(n=>{const r=resolveSym(n);
      return r?`<span class="fnchip" onclick="select(${r.id})">${esc(n)}</span>`
              :`<span class="fnchip dead" title="not found in this project">${esc(n)}</span>`;}).join('');
  const concept=(badge,title,desc,art)=>
    `<div class="stage"><div class="stage-h"><span class="stage-n cidx">${badge}</span><b>${esc(title)}</b></div>`+
    `<div class="stage-b"><div class="d">${desc}</div><canvas class="art tall" data-art="${art}"></canvas></div></div>`;
  const variantsHtml=st=>!st.variants?'':st.variants.map(v=>
    `<div class="variant"><div class="vh">${esc(v.name)}</div>`+
    (v.d?`<div class="d">${esc(v.d)}</div>`:'')+chipsFor(v.f)+
    (v.art?`<canvas class="art" data-art="${v.art}"></canvas>`:'')+'</div>').join('');
  let html='<div class="atitle">JunaCore receiver — current source pipeline</div>'+
    `<div class="sub">Every function chip below resolves inside the pinned <code>JunaCore/src</code> tree. Click a chip to inspect its exact current source. Matched ${ALGO_HITS[0]}/${ALGO_HITS[1]} source functions.</div>`;
  // concept 1 — WHY (the motivation: residual Doppler -> ICI -> non-diagonal channel)
  html+=concept('?','Why: residual Doppler breaks subcarrier orthogonality → ICI',
    'Residual time variation / Doppler can break subcarrier orthogonality, so neighbouring subcarriers produce ICI. The frequency-domain channel stops being diagonal (the one-tap OFDM model) and becomes <b>banded</b>. That intercarrier interference is what the partial-FFT front end and JUNA are built to address.',
    'ici');
  html+='<div class="arrow">↓</div>';
  // concept 2 — WHERE JUNA sits in this source tree
  html+=concept('≡','Where JUNA sits: current receiver-family dispatch',
    'The source contains standard and Partial-FFT baselines plus packet-local and frame-wide refinement families. The stages below follow their shared transmit, acquisition, front-end, decoding, dispatch, and selection entry points.',
    'families');
  html+='<div class="arrow">↓</div>';
  PIPELINE.forEach((st,i)=>{
    const art=st.art?`<canvas class="art" data-art="${st.art}"></canvas>`:'';
    html+=`<div class="stage"><div class="stage-h"><span class="stage-n">${i+1}</span><b>${esc(st.t)}</b></div>`+
          `<div class="stage-b"><div class="d">${esc(st.d)}</div>${chipsFor(st.f)}${art}${variantsHtml(st)}</div></div>`;
    if(i<PIPELINE.length-1)html+='<div class="arrow">↓</div>';
  });
  host.innerHTML=html;
  requestAnimationFrame(()=>host.querySelectorAll('canvas.art').forEach(cv=>
    ({packet:artPacket,pfft:artPfft,cstl:artCstl,tanner:artTanner,ici:artIci,families:artFamilies,gradient:artGradient}[cv.dataset.art]||(()=>{}))(cv)));
}
function setView(m){MODE=(m==='algo')?'algo':'oop';
  const algo=MODE==='algo';
  $('focus').style.display='none';$('detail').style.display='';
  $('algo').style.display=algo?'block':'none';
  $('net').style.display=algo?'none':'block';     // #net hosts the OOP graph
  $('viewtog').textContent=algo?'⬡ OOP view':'▦ JUNA pipeline';
  if(algo){
    renderAlgo();
    $('detail').innerHTML='<div class="empty">Source-backed pipeline — click any function chip to inspect its exact current definition and lexical relationships.</div>';
  }else if(DATA)drawOOP();
  setCrumb();
}
$('viewtog').onclick=()=>setView(MODE==='algo'?'oop':'algo');
$('paramstog').onclick=openParamsPage;
$('objtog').onclick=()=>openObjPage();

// ---- mini schematics (themed after the workbench drawing functions) --------
const AC={ink:'#e2e8f0',mut:'#64748b',line:'#334155',acc:'#38bdf8',teal:'#34d399',gold:'#f59e0b',vio:'#a78bfa',bg:'#0f172a'};
function hd(cv){const d=window.devicePixelRatio||1,r=cv.getBoundingClientRect();
  cv.width=Math.max(1,r.width*d);cv.height=Math.max(1,r.height*d);const x=cv.getContext('2d');x.setTransform(d,0,0,d,0,0);
  x.clearRect(0,0,r.width,r.height);x.textAlign='center';return[x,r.width,r.height];}
function artPacket(cv){const[x,w,h]=hd(cv);const L=14,top=20,bh=30,fw=w-28;
  const cpW=fw*0.20,payW=fw-cpW;
  const box=(bx,bw,fill,lab,sub)=>{x.fillStyle=fill;x.fillRect(bx,top,bw,bh);x.strokeStyle=AC.line;x.strokeRect(bx,top,bw,bh);
    x.fillStyle=AC.ink;x.font='11px system-ui';x.fillText(lab,bx+bw/2,top+15);
    if(sub){x.fillStyle=AC.mut;x.font='9px system-ui';x.fillText(sub,bx+bw/2,top+26);}};
  box(L,cpW,'rgba(245,158,11,.22)','cyclic prefix','np samples');
  box(L+cpW,payW,'rgba(56,189,248,.16)','OFDM symbol','nc samples from IFFT');
  const ty=top+bh+22,tx0=L+cpW,n=36,cw=payW/n;
  x.fillStyle=AC.mut;x.font='9px system-ui';x.textAlign='left';x.fillText('subcarriers',L,ty-4);
  for(let i=0;i<n;i++){x.fillStyle=i%3===0?AC.gold:AC.acc;x.fillRect(tx0+i*cw+1,ty,Math.max(1,cw-2),13);}
  x.fillStyle=AC.gold;x.fillRect(L,ty+24,10,10);x.fillStyle=AC.mut;x.fillText('outer pilots (configurable spacing)',L+15,ty+33);
  x.fillStyle=AC.acc;x.fillRect(L+190,ty+24,10,10);x.fillStyle=AC.mut;x.fillText('coded BPSK / QPSK',L+205,ty+33);
  x.textAlign='center';x.fillText('when sync=true, framing adds LFM sync before and after the OFDM blocks',w/2,ty+55);}
function artPfft(cv){const[x,w,h]=hd(cv);const L=16,top=16,bw=w-32,bh=24,parts=4;
  x.fillStyle='rgba(56,189,248,.14)';x.fillRect(L,top,bw,bh);x.strokeStyle=AC.line;x.strokeRect(L,top,bw,bh);
  x.fillStyle=AC.ink;x.font='10px system-ui';x.fillText('OFDM symbol after CP removal — P=4 schematic; partial_fft_parts is configurable',L+bw/2,top+15);
  x.setLineDash([4,3]);x.strokeStyle=AC.teal;
  for(let i=1;i<parts;i++){const px=L+bw*i/parts;x.beginPath();x.moveTo(px,top);x.lineTo(px,top+bh);x.stroke();}
  x.setLineDash([]);
  const wy=top+bh+30,ww=bw/parts-12;
  for(let i=0;i<parts;i++){const wx=L+bw*i/parts+6;
    x.strokeStyle=AC.teal;x.strokeRect(wx,wy,ww,22);x.fillStyle=AC.teal;x.font='10px system-ui';x.fillText('FFT'+(i+1),wx+ww/2,wy+15);
    x.strokeStyle=AC.mut;x.beginPath();x.moveTo(L+bw*(i+0.5)/parts,top+bh);x.lineTo(wx+ww/2,wy);x.stroke();}
  const cy=wy+22+24,cx=L+bw/2;
  x.fillStyle='rgba(167,139,250,.22)';x.fillRect(cx-78,cy,156,22);x.strokeStyle=AC.vio;x.strokeRect(cx-78,cy,156,22);
  x.fillStyle=AC.ink;x.font='11px system-ui';x.fillText('bandwise ridge-LS combiner → ŝ',cx,cy+15);
  x.strokeStyle=AC.mut;for(let i=0;i<parts;i++){const wx=L+bw*i/parts+6;x.beginPath();x.moveTo(wx+ww/2,wy+22);x.lineTo(cx,cy);x.stroke();}}
function artTanner(cv){const[x,w,h]=hd(cv);const checks=5,vars=7,cy=30,vy=h-30,cxs=[],vxs=[];
  for(let i=0;i<checks;i++)cxs.push((i+1)*w/(checks+1));
  for(let i=0;i<vars;i++)vxs.push((i+1)*w/(vars+1));
  x.strokeStyle=AC.line;x.lineWidth=1;
  [[0,0],[0,3],[1,1],[1,4],[2,2],[2,5],[3,0],[3,6],[4,3],[4,5]].forEach(([c,v])=>{
    x.beginPath();x.moveTo(cxs[c],cy);x.lineTo(vxs[v],vy);x.stroke();});
  cxs.forEach(cx=>{x.fillStyle=AC.bg;x.strokeStyle=AC.vio;x.fillRect(cx-9,cy-9,18,18);x.strokeRect(cx-9,cy-9,18,18);
    x.fillStyle=AC.vio;x.font='12px system-ui';x.fillText('+',cx,cy+4);});
  vxs.forEach((vx,i)=>{const an=i%2===1;x.beginPath();x.arc(vx,vy,8,0,7);x.fillStyle=an?'rgba(245,158,11,.3)':AC.bg;x.fill();
    x.strokeStyle=an?AC.gold:AC.teal;x.stroke();});
  x.fillStyle=AC.mut;x.font='10px system-ui';x.textAlign='left';
  x.fillText('check nodes (parity)',8,cy-14);x.fillText('bit nodes — gold = clamped inner pilots',8,vy+20);}
function artCstl(cv){const[x,w,h]=hd(cv);const cx=w/2,cy=h/2,R=Math.min(w,h)/2-18,s=R*0.6;
  x.strokeStyle=AC.line;x.beginPath();x.moveTo(cx-R,cy);x.lineTo(cx+R,cy);x.moveTo(cx,cy-R);x.lineTo(cx,cy+R);x.stroke();
  const P=[[1,1],[1,-1],[-1,1],[-1,-1]];
  P.forEach(([a,b])=>{for(let k=0;k<26;k++){const nx=cx+a*s+(Math.random()-.5)*s*0.55,ny=cy-b*s+(Math.random()-.5)*s*0.55;
    x.fillStyle='rgba(56,189,248,.28)';x.fillRect(nx,ny,2,2);}});
  P.forEach(([a,b])=>{x.fillStyle=AC.gold;x.beginPath();x.arc(cx+a*s,cy-b*s,4,0,7);x.fill();});
  x.fillStyle=AC.mut;x.font='10px system-ui';x.textAlign='left';x.fillText('QPSK — ideal (gold) vs equalized samples (blue)',8,14);}
function artIci(cv){const[x,w,h]=hd(cv);const N=10,my=30;
  const sz=Math.min((w-60)/2-30,h-58),m1x=30,m2x=w-sz-30;
  const mat=(mx,banded,title)=>{const cell=sz/N;
    for(let r=0;r<N;r++)for(let c=0;c<N;c++){const d=Math.abs(r-c);
      let v=0;if(d===0)v=0.9;else if(banded&&d===1)v=0.4;else if(banded&&d===2)v=0.16;
      x.fillStyle=v>0?`rgba(56,189,248,${v})`:'rgba(100,116,139,0.07)';
      x.fillRect(mx+c*cell,my+r*cell,cell-1,cell-1);}
    x.strokeStyle=AC.line;x.strokeRect(mx,my,sz,sz);
    x.fillStyle=AC.ink;x.font='11px system-ui';x.textAlign='center';x.fillText(title,mx+sz/2,my-10);};
  mat(m1x,false,'clean OFDM — diagonal');
  mat(m2x,true,'+ Doppler — banded ICI');
  x.fillStyle=AC.mut;x.font='10px system-ui';x.textAlign='center';
  x.fillText('rows/cols = subcarriers · colour = |H| coupling strength',w/2,my+sz+18);}
function _chain(x,w,labs,fills){const n=labs.length,gap=12,bw=(w-20-gap*(n-1))/n,top=18,bh=38;
  for(let i=0;i<n;i++){const bx=10+i*(bw+gap);
    x.fillStyle=fills[i];x.fillRect(bx,top,bw,bh);x.strokeStyle=AC.line;x.strokeRect(bx,top,bw,bh);
    x.fillStyle=AC.ink;x.font='600 11px system-ui';x.textAlign='center';x.fillText(labs[i][0],bx+bw/2,top+16);
    x.fillStyle=AC.mut;x.font='9px system-ui';x.fillText(labs[i][1],bx+bw/2,top+30);
    if(i<n-1){const ax=bx+bw,ay=top+bh/2;x.strokeStyle=AC.mut;x.lineWidth=1;x.beginPath();x.moveTo(ax,ay);x.lineTo(ax+gap,ay);x.stroke();
      x.beginPath();x.moveTo(ax+gap,ay);x.lineTo(ax+gap-4,ay-3);x.lineTo(ax+gap-4,ay+3);x.closePath();x.fillStyle=AC.mut;x.fill();}}
  return top+bh;}
function artOfdmTx(cv){const[x,w,h]=hd(cv);
  _chain(x,w,[['bits','message + pad'],['PSK map','b bits → point'],['differential','dₖ = dₖ₋₁·sₖ'],['IFFT','carriers → time'],['+ CP','copy last L']],
    ['#1e293b','rgba(52,211,153,.14)','rgba(167,139,250,.18)','rgba(56,189,248,.16)','rgba(245,158,11,.18)']);
  const dy=92;x.fillStyle=AC.mut;x.font='10px system-ui';x.textAlign='left';
  x.fillText('Data rides the phase STEP between neighbouring carriers:',12,dy-12);
  const cN=9,c0=22,cw=(w-44)/cN;let ang=-0.4;
  for(let i=0;i<cN;i++){const cx2=c0+i*cw+cw/2;ang+=0.55;
    x.strokeStyle=i===0?AC.gold:AC.teal;x.lineWidth=2;x.beginPath();x.moveTo(cx2,dy+28);x.lineTo(cx2+13*Math.cos(ang),dy+28-13*Math.sin(ang));x.stroke();
    x.fillStyle=i===0?AC.gold:AC.teal;x.beginPath();x.arc(cx2,dy+28,2.2,0,7);x.fill();}
  x.lineWidth=1;x.fillStyle=AC.mut;x.font='9px system-ui';x.textAlign='center';
  x.fillText('carrier 0 = random reference (gold) · each next = previous × data symbol',w/2,dy+50);}
function artOfdmRx(cv){const[x,w,h]=hd(cv);
  _chain(x,w,[['rx blocks','split N+L'],['− CP, FFT','→ carriers'],['differential','dₖ·conj(dₖ₋₁)'],['derotate','BPSK/QPSK align'],['LLR','soft bits → FEC']],
    ['#1e293b','rgba(56,189,248,.16)','rgba(167,139,250,.18)','rgba(52,211,153,.14)','rgba(245,158,11,.18)']);
  const dy=98;x.fillStyle=AC.mut;x.font='10px system-ui';x.textAlign='center';
  x.fillText('Dividing out the previous carrier cancels a common (slow) channel phase —',w/2,dy);
  x.fillText('no pilots or explicit equalizer needed when the channel varies slowly.',w/2,dy+16);}
function artLayout(cv){const[x,w,h]=hd(cv);
  const L=14,top=36,bh=26,gw=w-28,n=40,cw=gw/n,dc=n/2,spacing=4,nbands=4;
  x.textAlign='center';x.fillStyle=AC.ink;x.font='600 11px system-ui';x.fillText('JUNA subcarrier grid — one OFDM symbol (frequency axis)',w/2,16);
  x.fillStyle=AC.mut;x.font='9px system-ui';x.fillText('DC null at centre · gold = comb pilots · blue = data tones · dashed teal = RLS band edges',w/2,29);
  for(let i=0;i<n;i++){const cx=L+i*cw;
    if(Math.abs(i-dc)<0.5){x.fillStyle='rgba(100,116,139,.22)';x.fillRect(cx,top,Math.max(1,cw-1),bh);continue;}
    const act=Math.abs(Math.round(i-dc)),pilot=(act%spacing)===0;
    x.fillStyle=pilot?'rgba(245,158,11,.85)':'rgba(56,189,248,.5)';x.fillRect(cx,top,Math.max(1,cw-1),bh);}
  x.strokeStyle=AC.line;x.strokeRect(L,top,gw,bh);
  x.setLineDash([3,3]);x.strokeStyle=AC.teal;
  for(let b=1;b<nbands;b++){const bx=L+gw*b/nbands;x.beginPath();x.moveTo(bx,top-4);x.lineTo(bx,top+bh+4);x.stroke();}
  x.setLineDash([]);
  x.fillStyle=AC.mut;x.font='9px system-ui';x.fillText('DC',L+dc*cw,top+bh+12);
  const ly=top+bh+24;x.textAlign='left';
  x.fillStyle='rgba(245,158,11,.85)';x.fillRect(L,ly,11,11);x.fillStyle=AC.mut;x.font='9px system-ui';x.fillText('comb pilots — ±1 BPSK channel/phase reference (every k tones, k from pilot_ratio)',L+15,ly+9);
  x.fillStyle='rgba(56,189,248,.5)';x.fillRect(L,ly+16,11,11);x.fillStyle=AC.mut;x.fillText('data tones — carry LDPC-coded BPSK / QPSK symbols according to bpc',L+15,ly+25);
  x.textAlign='center';}
function artFrame(cv){const[x,w,h]=hd(cv);
  const L=126,R=w-14,top=28,bh=25,gap=8;
  x.textAlign='center';x.fillStyle=AC.ink;x.font='600 11px system-ui';x.fillText('frame layout selected by sync',w/2,15);
  const row=(label,y,segments)=>{
    x.textAlign='right';x.fillStyle=AC.mut;x.font='9px system-ui';x.fillText(label,L-8,y+16);
    const total=segments.reduce((n,s)=>n+s[1],0);let bx=L;
    segments.forEach(s=>{const bw=(R-L)*s[1]/total;
      x.fillStyle=s[2];x.fillRect(bx,y,bw,bh);x.strokeStyle=s[3];x.strokeRect(bx,y,bw,bh);
      x.textAlign='center';x.fillStyle=AC.ink;x.font='9px system-ui';x.fillText(s[0],bx+bw/2,y+16);bx+=bw;});};
  const block=['OFDM block(s): np CP + nc samples',5,'rgba(56,189,248,.16)',AC.acc];
  row('sync = false',top,[block]);
  row(':lfm',top+bh+gap,[['LFM sync',1,'rgba(52,211,153,.2)',AC.teal],block,['LFM sync',1,'rgba(52,211,153,.2)',AC.teal]]);
  x.textAlign='center';x.fillStyle=AC.mut;x.font='9px system-ui';x.fillText('These are the two transmit cases in Modulations.modulate.',w/2,top+2*(bh+gap)+8);}
function artFramePacket(cv){artFrame(cv);}
function artMessage(cv){const[x,w,h]=hd(cv);
  const L=12,top=30,bh=26,gw=w-24,n=24,cw=gw/n,ip=2;   // ip = inner-pilot spacing (default 2, from inner_pilot_ratio=1/2)
  x.textAlign='center';x.fillStyle=AC.ink;x.font='600 11px system-ui';x.fillText('the LDPC message (k bits) — payload interleaved with inner-pilot anchors',w/2,15);
  for(let i=0;i<n;i++){const cx=L+i*cw,inner=(i%ip)===0;
    x.fillStyle=inner?'rgba(167,139,250,.85)':'rgba(52,211,153,.5)';x.fillRect(cx,top,Math.max(1,cw-1),bh);}
  x.strokeStyle=AC.line;x.strokeRect(L,top,gw,bh);
  const ly=top+bh+22;x.textAlign='left';x.font='9px system-ui';
  x.fillStyle='rgba(167,139,250,.85)';x.fillRect(L,ly,11,11);x.fillStyle=AC.mut;x.fillText('inner pilot — a KNOWN bit every k-th message position, k from inner_pilot_ratio (clamped at the receiver)',L+15,ly+9);
  x.fillStyle='rgba(52,211,153,.5)';x.fillRect(L,ly+16,11,11);x.fillStyle=AC.mut;x.fillText('payload bit — the actual user data',L+15,ly+25);
  x.textAlign='center';x.fillStyle=AC.gold;x.fillText('→ LDPC-encoded into the codeword → mapped onto DATA tones (not on dedicated carriers like the comb pilots)',w/2,ly+44);}
function artFamilies(cv){const[x,w,h]=hd(cv);
  const groups=[
    {n:'baselines',facades:['JunaStandard','JunaPartialFFT']},
    {n:'packet-local',facades:['JunaLite']},
    {n:'frame-wide',facades:['JunaProfiledCzFrame','JunaCrcProfiledCzFrame']},
    {n:'conditioned joint',facades:['JunaCrcConditionedJointCwzFrame']},
  ];
  const L=86,rowH=(h-26)/groups.length;
  x.textAlign='center';x.fillStyle=AC.ink;x.font='600 10px system-ui';x.fillText('public receiver facades declared in JunaCore.jl',w/2,12);
  groups.forEach((group,i)=>{const y=20+i*rowH+rowH/2,gap=8,bw=(w-L-12-gap*(group.facades.length-1))/group.facades.length;
    x.textAlign='right';x.fillStyle=AC.mut;x.font='9px system-ui';x.fillText(group.n,L-8,y+3);
    group.facades.forEach((facade,j)=>{const bx=L+j*(bw+gap);
      x.fillStyle='rgba(56,189,248,.09)';x.strokeStyle=AC.line;x.fillRect(bx,y-12,bw,24);x.strokeRect(bx,y-12,bw,24);
      x.textAlign='center';x.fillStyle=AC.ink;x.font='8px system-ui';x.fillText(facade,bx+bw/2,y+3);});});}
function artGradient(cv){const[x,w,h]=hd(cv);
  // left: the loss terms that make up L(W,z)
  const terms=[
    ['data tie',AC.acc],
    ['pilot fit',AC.gold],
    ['soft parity',AC.vio],
    ['W anchor ‖W-W0‖²',AC.teal],
    ['z ridge ‖z‖²',AC.gold],
    ['z trust ‖z-z0‖²',AC.teal],
  ];
  const bx=12,bw=138,by=20,bh=14;
  x.textAlign='left';x.fillStyle=AC.mut;x.font='10px system-ui';x.fillText('minimise  L(W,z) =',bx,by-9);
  terms.forEach((t,i)=>{const yy=by+i*(bh+4);
    x.globalAlpha=0.65;x.fillStyle=t[1];x.fillRect(bx,yy,bw,bh);x.globalAlpha=1;
    x.strokeStyle=AC.line;x.strokeRect(bx,yy,bw,bh);
    x.fillStyle=AC.ink;x.font='9px system-ui';x.fillText('+ '+t[0],bx+6,yy+11);});
  x.fillStyle=AC.mut;x.font='9px system-ui';x.fillText('vars: W (combiner) · z (bit logits)',bx,by+terms.length*(bh+4)+5);
  // right: Adam snapshots need not be monotonic; decode ranking can retain an
  // earlier iteration independently of the minimum smooth loss.
  const gx0=bx+bw+46,gx1=w-16,gy0=22,gy1=h-26;
  x.strokeStyle=AC.line;x.beginPath();x.moveTo(gx0,gy0);x.lineTo(gx0,gy1);x.lineTo(gx1,gy1);x.stroke();
  x.fillStyle=AC.mut;x.font='9px system-ui';x.textAlign='left';x.fillText('loss',gx0+2,gy0+8);
  x.textAlign='right';x.fillText('Adam steps',gx1,gy1+14);x.textAlign='left';
  const losses=[0.92,0.68,0.75,0.51,0.60,0.42,0.48,0.37,0.44],bestIndex=5;
  const N=losses.length-1;let px=null,py=null,bestX=null,bestY=null;
  for(let i=0;i<=N;i++){const t=i/N,cx=gx0+t*(gx1-gx0),cy=gy1-(gy1-gy0)*(0.10+0.80*losses[i]);
    if(px!=null){x.strokeStyle=AC.vio;x.beginPath();x.moveTo(px,py);x.lineTo(cx,cy);x.stroke();}
    x.fillStyle=i===bestIndex?AC.teal:AC.acc;x.beginPath();x.arc(cx,cy,i===bestIndex?4:3,0,7);x.fill();
    if(i===bestIndex){bestX=cx;bestY=cy;}px=cx;py=cy;}
  x.fillStyle=AC.teal;x.font='9px system-ui';x.textAlign='right';x.fillText('best-ranked decode',bestX-6,bestY-6);
  x.fillStyle=AC.mut;x.textAlign='left';x.fillText('each ● = snapshot → decode; ranking may retain an earlier step',gx0+4,gy0+20);}

function srcPreview(src,q){const ls=src.split('\n');for(let i=0;i<ls.length;i++){if(ls[i].toLowerCase().includes(q))return {off:i,text:ls[i].trim().slice(0,120)};}return null;}
$('q').oninput=e=>{
  const raw=e.target.value.trim();const host=$('hits');host.innerHTML='';
  if(!raw||!DATA)return;
  let field='name',q=raw.toLowerCase();
  const mm=raw.match(/^(mod|file|src|doc)\s*:\s*(.*)$/i);
  if(mm){field=mm[1].toLowerCase();q=mm[2].toLowerCase();}
  if(!q){host.innerHTML='<div class="empty">type text after the prefix…</div>';return;}
  const doctext=s=>s.doc?((s.doc.a||'')+' '+(s.doc.b||'')+' '+(s.doc.c||'')).toLowerCase():'';
  const pick = field==='doc'
    ? (q==='!' ? s=>!s.doc : s=>doctext(s).includes(q))
    : {name:s=>s.name.toLowerCase().includes(q),
       mod:s=>s.module.toLowerCase().includes(q),
       file:s=>s.file.toLowerCase().includes(q),
       src:s=>s.src.toLowerCase().includes(q)}[field];
  const hit=DATA.symbols.filter(pick).slice(0,80);
  hit.forEach(s=>{const d=document.createElement('div');
    let meta=`<span class="k">· ${esc(s.module)} <i>${s.kind}</i></span>`;
    if(field==='file')meta=`<span class="k">· ${esc(s.file)}</span>`;
    let prev='';
    if(field==='src'){const r=srcPreview(s.src,q);if(r)prev=`<span class="prev"><span style="color:#475569">${esc(s.file)}:${s.line+r.off}</span>  ${esc(r.text)}</span>`;}
    if(field==='doc'&&s.doc)prev=`<span class="prev">${esc(s.doc.a)}</span>`;
    d.innerHTML=`${esc(s.name)} ${meta}${prev}`;
    d.onclick=()=>select(s.id);
    host.appendChild(d);});
  if(!hit.length)host.innerHTML='<div class="empty">no match</div>';
};
// detail chips + call-tree navigate via delegation; tw-tog expands the tree.
$('detail').addEventListener('click',ev=>{
  const tg=ev.target.closest('.tw-tog');
  if(tg){const n=tg.closest('.tw-node'),k=n&&n.querySelector(':scope > .tw-kids');
    if(k){const open=k.style.display!=='none';k.style.display=open?'none':'block';tg.textContent=open?'▸':'▾';}
    ev.stopPropagation();return;}
  const t=ev.target.closest('[data-sym],[data-focus]');if(!t)return;
  if(t.hasAttribute('data-focus'))openFocus(+t.getAttribute('data-focus'));
  else select(+t.getAttribute('data-sym'));});
// recursive call-flow page (new tab): triangle expands/collapses a step; clicking a name re-roots the flow.
$('flowpage').addEventListener('click',ev=>{
  const tg=ev.target.closest('.rtog');
  if(tg){if(!tg.classList.contains('rrep')){const step=tg.closest('.rstep'),sub=step&&step.querySelector(':scope > .rsub');
    if(sub){const collapsed=sub.classList.toggle('collapsed');tg.textContent=collapsed?'▸':'▾';}}
    ev.stopPropagation();return;}
  const nm=ev.target.closest('.rname[data-foc]');if(nm)reRoot(+nm.getAttribute('data-foc'));});

async function load(){
  const msg=$('msg');
  if(!CFG.serve){msg.textContent='static file: re-run with --serve to load folders';return;}
  let url='/api/scan';
  if(CFG.locked){msg.style.color='#94a3b8';msg.textContent='scanning project …';}
  else{
    const path=$('path').value.trim();
    if(!path){msg.textContent='enter a folder path';return;}
    url+='?path='+encodeURIComponent(path);
    msg.style.color='#94a3b8';msg.textContent='scanning '+path+' …';
  }
  try{
    const r=await fetch(url);
    const d=await r.json();
    if(d.error){msg.style.color='#f87171';msg.textContent=d.error;
      showOverlay('Could not scan that folder',`<div class="b">${esc(d.error)}</div>`);return;}
    msg.textContent='';hideOverlay();render(d);
    if(!CFG.locked){try{localStorage.setItem('se_path',$('path').value.trim());}catch(e){}}
  }catch(e){msg.style.color='#f87171';msg.textContent=String(e);
    showOverlay('Scan failed',`<div class="b">${esc(String(e))}</div>`);}
}
function emptyState(){
  if(CFG.locked)return showOverlay('Scanning pinned project…',`<div class="b">Reading <code>${esc((CFG.lockedRoot||'').replace(/\/+$/,''))}</code> … this runs automatically; nothing to load.</div>`);
  showOverlay('Source Definition Explorer',
    '<div class="b">Explore a codebase by its OOP structure: abstract types, subtyping, and which type implements which interface method — then drill into any method.</div>'+
    '<ol><li>Click <b>📁 Load…</b> and pick a project folder (or type a path + Enter).</li>'+
    '<li>In the <b>OOP view</b>, click a type ◇ or an interface method.</li>'+
    '<li>Click a method to open its <b>call-focus sphere</b>, or search on the left to jump to any source definition.</li></ol>');
}
async function browse(){
  const msg=$('msg');
  if(!CFG.serve){msg.textContent='folder picker needs --serve mode';return;}
  msg.style.color='#94a3b8';msg.textContent='opening file picker…';
  try{
    const d=await(await fetch('/api/pick')).json();
    if(d.path){$('path').value=d.path;msg.textContent='';load();}
    else if(d.cancelled){msg.textContent='';}
    else{msg.style.color='#f87171';msg.textContent=d.error||'type a path + Enter';}
  }catch(e){msg.style.color='#f87171';msg.textContent=String(e);}
}
$('load').onclick=browse;
$('reload').onclick=load;
$('restart').onclick=async()=>{const msg=$('msg');if(!CFG.serve){msg.textContent='restart needs --serve';return;}
  msg.style.color='#94a3b8';msg.textContent='restarting…';try{await fetch('/api/restart');}catch(e){}setTimeout(()=>location.reload(),1700);};
$('path').addEventListener('keydown',e=>{if(e.key==='Enter')load();});

if(CFG.locked){
  $('path').style.display='none';$('load').style.display='none';
  $('pin').style.display='inline';
  const r=(CFG.lockedRoot||'').replace(/\/+$/,'');
  $('pinname').textContent=r.split('/').pop()||r;$('pinpath').textContent=r;
  $('detail').innerHTML='<div class="empty">📌 Pinned to <b>'+esc(r.split('/').pop()||r)+'</b>. This is the <b>OOP view</b> — click a type ◇ or an interface method in the graph (a method opens its call-focus sphere), or search on the left.</div>';
}
if(typeof vis==='undefined'){
  showOverlay('Graph library could not load',
    '<div class="b">The <code>vis-network</code> visualization library is missing. Put a copy at '+
    '<code>Tools/vendor/vis-network.min.js</code> (it is normally vendored there) or restore network access, then reload.</div>');
}else if(CFG.data){render(CFG.data);}
else if(CFG.locked){emptyState();load();}
else if(CFG.serve){const lp=localStorage.getItem('se_path')||CFG.defaultRepo||'';if(lp){$('path').value=lp;load();}else{emptyState();}}
if(!CFG.serve&&typeof vis!=='undefined'&&!CFG.data)$('msg').textContent='static snapshot — use --serve for live reload';
// Workbench cross-links: standalone pages link to the test workbench; when
// this page is served inside the workbench at /source, the injected shared
// nav already navigates and these stay hidden.
(function(){
  const el=$('wblinks');if(!el)return;
  if(location.pathname.indexOf('/source')===0)return;
  const base=(CFG.workbench||'').replace(/\/+$/,'');if(!base)return;
  const items=[['/','Workbench'],['/explorer','Tests'],['/docs/receiver_chain.html','Chain']];
  el.innerHTML=items.map(function(it){
    return '<a href="'+base+it[0]+'" style="color:#94a3b8;text-decoration:none;margin-left:8px"'+
      ' onmouseover="this.style.color=\'#e2e8f0\'" onmouseout="this.style.color=\'#94a3b8\'">'+it[1]+'</a>';
  }).join('');
  el.style.display='inline';
})();
</script></body></html>"""


def main():
    ap = argparse.ArgumentParser(description="JunaCore source definition explorer + UI")
    ap.add_argument("--serve", action="store_true", help="launch the interactive UI server")
    ap.add_argument("--no-browser", action="store_true",
                    help="serve without opening a browser (for tests and automation)")
    ap.add_argument("--port", type=int, default=8754)
    ap.add_argument("--repo", default=".", help="project root (default cwd; preloaded in --serve)")
    ap.add_argument("--root", default=None, help="subtree to scan (default the repo)")
    ap.add_argument("--out", default=None, help="output html (static mode; default <repo>/symbol_graph.html)")
    ap.add_argument("--lock", action="store_true",
                    help="pin the UI to --repo/--root only: no folder picker, no other paths")
    a = ap.parse_args()
    if a.serve:
        pre = os.path.abspath(a.root or a.repo) if (a.root or a.repo != ".") else ""
        if a.lock and not pre:
            ap.error("--lock requires --repo (or --root) to set the pinned project root")
        serve(a.port, pre, locked=a.lock, open_browser=not a.no_browser)
        return
    folder = a.root or a.repo
    data = analyze(folder)
    out = a.out or os.path.join(os.path.abspath(folder), "symbol_graph.html")
    open(out, "w").write(render_html(False, data))
    s = data["stats"]
    print(f"wrote {out}")
    print(f"  source definitions {s['symbols']}  modules {s['modules']}  call edges {s['edges']}  files {s['files']}")


if __name__ == "__main__":
    main()
