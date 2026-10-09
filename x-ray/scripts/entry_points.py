#!/usr/bin/env python3
"""List Solidity entry points for the x-ray skill (Step 2 entry point scan).

An entry point is a non-view, non-pure `external` or `public` function, plus
`receive` and `fallback`. Each function header is read as a whole, from
`function` (or `receive` / `fallback`) to its opening `{`, after comments and
string literals are blanked. Line breaks therefore cannot hide an entry point:
line-oriented grep misses headers that formatters wrap, such as `external` on
its own line (`forge fmt`'s default `multiline_func_header = "attributes_first"`)
or one-parameter-per-line headers whose `function` keyword sits far above the
`) external` line. Pre-0.5 code is handled too: a missing visibility counts as
`public`, `constant` counts as `view`, `function () ... {` is the fallback, and a
function named exactly like its contract is a constructor (a misspelled one is
still listed, since it is callable).

Output (stdout), one line per entry point, whitespace collapsed:
    path:line: [abstract|library] Container.name(params) attributes
followed by a `# N entry point(s) in M of K .sol file(s)` summary line. An
ordinary function that is merely named `receive` or `fallback` ends with a
`// ordinary function named ...` note, since it is not the special function.
Unreadable files and directories are reported on stderr, skipped, and counted
in the summary.

Skipped: interfaces, bodiless declarations (ending in `;`), internal/private
functions, view/pure functions, free functions, and any path containing
`/interfaces/` or `/mock/`. `[abstract]` marks functions defined in abstract
contracts; they are entry points of every concrete contract that inherits them,
unless a contract lower in the hierarchy overrides them. `[library]` marks
library functions, which are reached only through the contracts that call them.

Usage:
    python3 entry_points.py src
    python3 entry_points.py contracts other/contracts
"""

from __future__ import annotations

import argparse
import os
import re
import sys

EXCLUDED_PATH_PARTS = ("/interfaces/", "/mock/")

IDENT = r"[A-Za-z_$][A-Za-z0-9_$]*"
# Keyword boundaries. `\b` would treat `$` as a boundary, but `$` is part of Solidity identifiers.
B = r"(?<![A-Za-z0-9_$])"
E = r"(?![A-Za-z0-9_$])"
CONTAINER_RE = re.compile(B + r"(abstract\s+)?(contract|interface|library)\s+(" + IDENT + r")")
FUNCTION_RE = re.compile(B + r"function\s+(" + IDENT + r")\s*\(")
SPECIAL_RE = re.compile(B + r"(receive|fallback)\s*\(")
LEGACY_FALLBACK_RE = re.compile(B + r"function\s*\(")
VISIBILITY_RE = re.compile(B + r"(external|public|internal|private)" + E)
VIEW_OR_PURE_RE = re.compile(B + r"(view|pure|constant)" + E)


def blank_comments_and_strings(src: str, strings: bool = True) -> str:
    """Replace comments (and, if `strings`, string literal contents) with spaces, keeping offsets."""
    out = list(src)
    i, n = 0, len(src)
    while i < n:
        ch = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "/":
            while i < n and src[i] != "\n":
                out[i] = " "
                i += 1
        elif ch == "/" and nxt == "*":
            end = src.find("*/", i + 2)
            end = n if end == -1 else end + 2
            for j in range(i, end):
                if src[j] != "\n":
                    out[j] = " "
            i = end
        elif ch in "\"'":
            j = i + 1
            while j < n and src[j] != ch and src[j] != "\n":
                j += 2 if src[j] == "\\" else 1
            if strings:
                for k in range(i + 1, min(j, n)):
                    if src[k] != "\n":
                        out[k] = " "
            i = j + 1
        else:
            i += 1
    return "".join(out)


def matching_close(text: str, open_idx: int, open_ch: str, close_ch: str) -> int:
    """Index of the bracket closing the one at open_idx, or -1 if unbalanced."""
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == open_ch:
            depth += 1
        elif text[i] == close_ch:
            depth -= 1
            if depth == 0:
                return i
    return -1


def header_end(text: str, start: int) -> int:
    """Index of the first `{` or `;` at parenthesis depth 0 from start, or -1."""
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0 and ch in "{;":
            return i
    return -1


def previous_token(text: str, pos: int) -> str:
    """The identifier or `.` that ends right before pos, skipping whitespace."""
    i = pos - 1
    while i >= 0 and text[i].isspace():
        i -= 1
    if i >= 0 and text[i] == ".":
        return "."
    j = i
    while j >= 0 and (text[j].isalnum() or text[j] in "_$"):
        j -= 1
    return text[j + 1 : i + 1]


def strip_parenthesized(text: str) -> str:
    """Drop every parenthesized group (returns lists, modifier arguments, override lists)."""
    out, depth = [], 0
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(depth - 1, 0)
        elif depth == 0:
            out.append(ch)
    return "".join(out)


def containers(clean: str) -> list[tuple[int, int, str, str]]:
    """(body_open, body_close, kind, name) for every contract/interface/library."""
    found = []
    for m in CONTAINER_RE.finditer(clean):
        brace = header_end(clean, m.end())
        if brace == -1 or clean[brace] != "{":
            continue
        close = matching_close(clean, brace, "{", "}")
        if close == -1:
            continue
        kind = "abstract" if m.group(1) else m.group(2)
        found.append((brace, close, kind, m.group(3)))
    return found


def entry_points(path: str) -> list[tuple[int, str]]:
    with open(path, encoding="utf-8", errors="replace") as f:
        source = f.read()
    clean = blank_comments_and_strings(source)  # parsed: no comments, no string contents
    display = blank_comments_and_strings(source, strings=False)  # printed: strings kept
    scopes = containers(clean)
    results = []
    for regex in (FUNCTION_RE, SPECIAL_RE, LEGACY_FALLBACK_RE):
        for m in regex.finditer(clean):
            start = m.start()
            if regex is SPECIAL_RE and previous_token(clean, start) in (".", "function"):
                continue  # a member call (`x.receive(`), or an ordinary function named receive/fallback
            enclosing = [s for s in scopes if s[0] < start < s[1]]
            if not enclosing:
                continue  # free function: cannot be external or public
            body_open, _, kind, name = max(enclosing, key=lambda s: s[0])
            between = clean[body_open + 1 : start]
            if kind == "interface" or between.count("{") != between.count("}"):
                continue  # interface member, or not declared at contract level
            if between.count("(") != between.count(")"):
                continue  # function type inside a parameter list or mapping
            params_open = m.end() - 1
            params_close = matching_close(clean, params_open, "(", ")")
            if params_close == -1:
                continue
            end = header_end(clean, params_close + 1)
            if end == -1 or clean[end] == ";":
                continue  # bodiless declaration, or a function-type state variable
            attributes = strip_parenthesized(clean[params_close + 1 : end])
            visibility = VISIBILITY_RE.search(attributes)
            if visibility and visibility.group(1) not in ("external", "public"):
                continue  # no visibility only compiles before 0.5, where it means public
            if VIEW_OR_PURE_RE.search(attributes):
                continue
            if regex is FUNCTION_RE and m.group(1) == name:
                continue  # pre-0.5 constructor
            if regex is LEGACY_FALLBACK_RE:
                header = "fallback" + display[params_open:end]
            else:
                header = display[m.start(1) : end]
            header = re.sub(r"\s+", " ", header).strip()
            header = re.sub(r"\(\s+", "(", re.sub(r"\s+\)", ")", header))
            header = re.sub(r"^([^\s(]+)\s+\(", r"\1(", header)  # `receive ()` -> `receive()`
            if regex is FUNCTION_RE and m.group(1) in ("receive", "fallback"):
                header += f" // ordinary function named {m.group(1)}, not the special {m.group(1)} function"
            tag = f"[{kind}] " if kind in ("abstract", "library") else ""
            results.append((clean.count("\n", 0, start) + 1, f"{tag}{name}.{header}"))
    return sorted(results)


def solidity_files(paths: list[str], problems: list[str]) -> list[str]:
    files = []
    for root_path in paths:
        if os.path.isfile(root_path):
            files.append(root_path)
            continue
        on_error = lambda e: problems.append(f"{e.filename}: {e.strerror or e}")  # noqa: E731
        for root, dirs, names in os.walk(root_path, onerror=on_error):
            dirs.sort()
            files.extend(os.path.join(root, n) for n in sorted(names) if n.endswith(".sol"))
    normalized = [os.path.normpath(f).replace(os.sep, "/") for f in files]
    kept = [f for f in normalized if not any(part in "/" + f for part in EXCLUDED_PATH_PARTS)]
    return list(dict.fromkeys(kept))  # drop duplicates from overlapping arguments


def main() -> int:
    parser = argparse.ArgumentParser(description="List Solidity entry points for the x-ray skill.")
    parser.add_argument("paths", nargs="+", help="source directories or .sol files (e.g. src)")
    args = parser.parse_args()
    missing = [p for p in args.paths if not os.path.exists(p)]
    if missing:
        print(f"error: path not found: {', '.join(missing)}", file=sys.stderr)
        return 2
    problems: list[str] = []
    files = solidity_files(args.paths, problems)
    total, files_with_entries = 0, 0
    for path in files:
        try:
            found = entry_points(path)
        except OSError as e:
            problems.append(f"{path}: {e.strerror or e}")
            continue
        if found:
            files_with_entries += 1
        for line, text in found:
            print(f"{path}:{line}: {text}")
        total += len(found)
    for problem in problems:
        print(f"warning: skipped {problem}", file=sys.stderr)
    if not files:
        print("warning: no .sol files to scan (paths containing /interfaces/ or /mock/ are excluded)", file=sys.stderr)
    summary = f"# {total} entry point(s) in {files_with_entries} of {len(files)} .sol file(s)"
    if problems:
        summary += f"; {len(problems)} unreadable path(s) skipped, see stderr"
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
