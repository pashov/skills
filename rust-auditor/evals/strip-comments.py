#!/usr/bin/env python3
"""Strip Rust comments from benchmark source so comments cannot leak the answers.

Benchmark templates mark their bugs in comments (`// VULN: ...`,
`/// CHECK: VULNERABLE - ...`). A run that keeps them is not blind. Run this on a
scratch COPY of the target before the audit, never on the original checkout.

Removes `//`, `///`, `//!`, `/* */`, `/** */`, `/*! */` (block comments nest, as in
Rust). Keeps string, byte-string, C-string and raw-string literals (`"…"`, `b"…"`,
`c"…"`, `r#"…"#`, `br##"…"##`), char and byte literals (`'x'`, `'\\''`, `b'\\n'`) and
lifetimes / labels (`'a`, `'static`) byte for byte. Every newline is kept, so line
numbers in the stripped file match the original. Trailing whitespace left behind on
a line is removed. `#[doc = "…"]` attributes are code, not comments, and are kept.

Python 3.8+ standard library only.

  strip-comments.py FILE.rs                      # print the stripped file to stdout
  strip-comments.py --in-place FILE.rs ...       # rewrite each file (scratch copy only!)
  strip-comments.py --out-dir DIR FILE.rs ...    # write DIR/<same relative path>
  strip-comments.py --list files.txt --in-place  # read the file list from a file ('-' = stdin)
  strip-comments.py --keep-check ...             # keep Anchor `/// CHECK` doc comments
                                                 # (they may leak too — default strips them)
  strip-comments.py --check FILE.rs ...          # exit 1 if any file still has a comment

Exit status: 0 on success; 1 when --check finds a comment; 2 on a usage error or an
unterminated literal / comment (the file is then left unchanged).
"""
import os
import re
import sys

IDENT = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


class StripError(Exception):
    pass


def _raw_string_end(src, i):
    """src[i] is the `r` of a raw string prefix; return index after it, or -1."""
    j = i + 1
    hashes = 0
    while j < len(src) and src[j] == "#":
        hashes += 1
        j += 1
    if j >= len(src) or src[j] != '"':
        return -1
    close = '"' + "#" * hashes
    k = src.find(close, j + 1)
    if k < 0:
        raise StripError("unterminated raw string at offset %d" % i)
    return k + len(close)


def _quoted_end(src, j, q):
    """src[j] is the opening quote q; return index after the closing quote."""
    k = j + 1
    n = len(src)
    while k < n:
        c = src[k]
        if c == "\\":
            k += 2
            continue
        if c == q:
            return k + 1
        k += 1
    raise StripError("unterminated %s literal at offset %d" % ("string" if q == '"' else "char", j))


def _char_end(src, j):
    """src[j] == "'": return the end of a char literal, or -1 for a lifetime / label."""
    n = len(src)
    if j + 1 < n and src[j + 1] == "\\":
        return _quoted_end(src, j, "'")
    if j + 2 < n and src[j + 2] == "'" and src[j + 1] != "\n":
        return j + 3
    return -1


def strip(src, keep_check=False):
    out = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        prev = src[i - 1] if i else ""
        # ---- comments
        if src.startswith("//", i):
            j = src.find("\n", i)
            j = n if j < 0 else j
            text = src[i:j]
            if keep_check and text.startswith("///") and text[3:].lstrip().startswith("CHECK"):
                out.append(text)
            i = j
            continue
        if src.startswith("/*", i):
            depth, k = 1, i + 2
            while k < n and depth:
                if src.startswith("/*", k):
                    depth += 1
                    k += 2
                elif src.startswith("*/", k):
                    depth -= 1
                    k += 2
                else:
                    k += 1
            if depth:
                raise StripError("unterminated block comment at offset %d" % i)
            out.append("\n" * src.count("\n", i, k))
            # keep tokens apart: `a/* x */b` must not become `ab`
            if not src.count("\n", i, k) and out and k < n and (prev in IDENT) and (src[k] in IDENT):
                out.append(" ")
            i = k
            continue
        # ---- literals with a prefix (r, br, cr, b, c) — only at an identifier start
        if prev not in IDENT and c in "brc":
            p = i
            if src.startswith("br", i) or src.startswith("cr", i):
                p = i + 1
            if src[p] == "r":
                e = _raw_string_end(src, p)
                if e > 0:
                    out.append(src[i:e]); i = e
                    continue
            if c in "bc" and i + 1 < n and src[i + 1] == '"':
                e = _quoted_end(src, i + 1, '"')
                out.append(src[i:e]); i = e
                continue
            if c == "b" and i + 1 < n and src[i + 1] == "'":
                e = _char_end(src, i + 1)
                if e > 0:
                    out.append(src[i:e]); i = e
                    continue
        if c == '"':
            e = _quoted_end(src, i, '"')
            out.append(src[i:e]); i = e
            continue
        if c == "'":
            e = _char_end(src, i)
            if e > 0:
                out.append(src[i:e]); i = e
                continue
            out.append(c); i += 1          # lifetime or loop label
            continue
        # copy a run of ordinary characters (fast path)
        j = i + 1
        while j < n and src[j] not in "/\"'brc":
            j += 1
        out.append(src[i:j]); i = j
    text = "".join(out)
    return "\n".join(line.rstrip() for line in text.split("\n"))


def has_comment(src, keep_check=False):
    return strip(src, keep_check) != "\n".join(line.rstrip() for line in src.split("\n"))


def out_path(out_dir, f):
    """Mirror `f` under `out_dir`. A drive, a leading separator or `..` never escapes it."""
    rel = os.path.splitdrive(os.path.normpath(f))[1]
    parts = [p for p in re.split(r"[\\/]+", rel) if p not in ("", ".", "..")]
    return os.path.join(out_dir, *parts)


def main(argv):
    mode, out_dir, keep, files, lst = "stdout", None, False, [], None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-h", "--help"):
            print(__doc__); return 0
        if a == "--in-place":
            mode = "inplace"
        elif a == "--check":
            mode = "check"
        elif a == "--keep-check":
            keep = True
        elif a in ("--out-dir", "--list") and i + 1 >= len(argv):
            print("%s needs a value (see --help)" % a, file=sys.stderr); return 2
        elif a == "--out-dir":
            mode, out_dir = "outdir", argv[i + 1]; i += 1
        elif a == "--list":
            lst = argv[i + 1]; i += 1
        elif a.startswith("-"):
            print("unknown option %s (see --help)" % a, file=sys.stderr); return 2
        else:
            files.append(a)
        i += 1
    if lst:
        fh = sys.stdin if lst == "-" else open(lst, encoding="utf-8")
        files += [l.strip() for l in fh if l.strip()]
    files = [f for f in files if f.endswith(".rs")]
    if not files:
        print("no .rs files given (see --help)", file=sys.stderr); return 2
    if mode == "stdout" and len(files) > 1:
        print("several files: use --in-place or --out-dir", file=sys.stderr); return 2
    status, changed = 0, 0
    for f in files:
        with open(f, encoding="utf-8", errors="surrogateescape") as fh:
            src = fh.read()
        try:
            res = strip(src, keep)
        except StripError as e:
            print("%s: %s — left unchanged" % (f, e), file=sys.stderr)
            status = 2
            continue
        if mode == "check":
            if has_comment(src, keep):
                print("%s: has comments" % f); status = max(status, 1)
            continue
        if res.endswith("\n") is False and src.endswith("\n"):
            res += "\n"
        if mode == "stdout":
            sys.stdout.buffer.write(res.encode("utf-8", "surrogateescape")); continue
        dest = f if mode == "inplace" else out_path(out_dir, f)
        if mode == "outdir" and os.path.abspath(dest) == os.path.abspath(f):
            print("%s: --out-dir would overwrite the source — left unchanged" % f, file=sys.stderr)
            status = 2
            continue
        if mode == "outdir":
            os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        if res != src or mode == "outdir":
            with open(dest, "w", encoding="utf-8", errors="surrogateescape") as fh:
                fh.write(res)
            changed += res != src
    if mode in ("inplace", "outdir"):
        print("strip-comments: %d file(s) read, %d had comments removed" % (len(files), changed), file=sys.stderr)
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
