#!/usr/bin/env python3
"""rust-auditor account-map pre-scan.

Reads the in-scope .rs files and writes a Markdown account map: one entry per
instruction handler (accounts, signer/mut/owner/type, PDA seeds and bump source,
init/close, constraints, CPIs, state written, gating) plus an auto-highlighted
"Review leads" section. The map is a list of LEADS for the hacking agents, never a
list of findings.

Python 3.8+ standard library only. No network, no writes except --out.

  python3 account-map.py --out .rust-auditor/runs/STAMP/account-map.md FILE...

Anchor (#[derive(Accounts)] + #[program]) is parsed structurally. Native
solana-program and Pinocchio handlers are parsed heuristically; any cell the
script cannot settle is written as `?`, and the handler is listed under
"Needs completion" so a model can finish it from the source.

Global singletons are folded so they do not drown the per-user leads: a writable
PDA whose seeds are only constants (`[b"config"]`, `[GLOBAL_SEED]`) is raised once
as `singleton-init` on the instruction that creates it (or once as
`singleton-write` when nothing in scope creates it), a child PDA keyed only by a
validated parent (`[b"lp", config.key()]`) or owned by another program
(`seeds::program`) is not raised, and constant CPI signer seeds are raised once
per program as `global-signer`. Seeds that carry any variable value keep the
per-instruction `pda-no-user-key` / `signer-seeds-no-user-key` leads (seeds
built from a validated parent's key or stored fields are folded into
`global-signer` too).
Native/Pinocchio handlers also get `offset-mismatch` (a hand-coded byte range on
account data that misses every field boundary of the matching `#[repr(C)]` /
`#[repr(packed)]` struct) and `key-compared-no-signer` (an account's key is
compared against stored data but `is_signer` is never checked on it).
Raw writes through borrowed account data (`copy_from_slice`, `v[..] =`,
`copy_nonoverlapping`, `serialize(&mut v)`, typed `load_mut`) count as state
changes, so native initialisers without a signer or init guard are raised.
Anchor exit paths (withdraw / redeem / claim / close / unwrap ...) that require
an account owned by another program get `foreign-dependency`, and a `close =`
whose destination is an unconstrained raw account gets `close-to-unchecked`.

Native/Pinocchio idioms the map follows so it does not raise false leads:
- Program names come from the nearest Cargo.toml `[lib] name` / `[package] name`
  (hyphens become underscores), so one workspace with many crates does not
  collapse every handler into one `program::` prefix. `declare_id!` carries no
  name and is not used. Generic handler names (`process`, `handler`, `run`) are
  qualified with their module (`claim::process`).
- Signer and owner checks done inside a helper count: a helper whose parameter
  reaches `is_signer()` / `signer_key()` / `*Signer*::try_from(..)` or an owner
  check (`p.owner`, `p.owned_by(..)`, `check_owner(p, ..)`) marks the argument at
  every call site, through helper-to-helper and `self.` calls (fixpoint). The
  row then reads `checked (helper)`.
- Typed account structs validated in a constructor (`impl TryFrom<&[AccountView]>`
  / `impl TryFrom<&[AccountInfo]>`, or `fn try_from/new/parse/load/validate(accounts)
  -> Result<Self>`) are merged into the handler that builds them, so the
  checks done there are seen, and the constructor is not listed as a handler.
- A helper that creates and initialises an account counts as an init guard;
  `remaining_accounts`-style bindings (`rest @ ..`, a struct field of slice type)
  are not raised as uses.
- An account whose owner is checked only in a helper and that is decoded with no
  key or PDA binding keeps a `raw-deserialize` lead worded for substitution by
  another account of the same type.
"""
import os
import re
import sys

# --------------------------------------------------------------------------
# Lexing helpers
# --------------------------------------------------------------------------

def mask(text):
    """Blank comments and string/char literal contents (same length, newlines
    kept) so brace matching and regexes never see code inside them."""
    out = list(text)
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = " "
            i = j
        elif text.startswith("/*", i):
            depth, j = 1, i + 2
            while j < n and depth:
                if text.startswith("/*", j):
                    depth += 1; j += 2
                elif text.startswith("*/", j):
                    depth -= 1; j += 2
                else:
                    j += 1
            for k in range(i, j):
                if out[k] != "\n":
                    out[k] = " "
            i = j
        elif c in "rbc" and re.match(r'[bc]?r#*"', text[i:i + 11]) and (i == 0 or not (text[i - 1].isalnum() or text[i - 1] == "_")):
            m = re.match(r'[bc]?r(#*)"', text[i:])
            hashes = m.group(1)
            end = text.find('"' + hashes, i + len(m.group(0)))
            end = n if end < 0 else end
            for k in range(i + len(m.group(0)), end):
                if out[k] != "\n":
                    out[k] = " "
            i = end + 1 + len(hashes)
        elif c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            for k in range(i + 1, min(j, n)):
                if out[k] != "\n":
                    out[k] = " "
            i = j + 1
        elif c == "'":
            # char literal vs lifetime: 'a' or '\n' is a literal, 'info is a lifetime
            m = re.match(r"'(\\.|[^\\'])'", text[i:i + 6])
            if m:
                for k in range(i + 1, i + len(m.group(0)) - 1):
                    out[k] = " "
                i += len(m.group(0))
            else:
                i += 1
        else:
            i += 1
    return "".join(out)


PAIRS = {"(": ")", "[": "]", "{": "}"}


def match_close(s, open_idx):
    """Index of the bracket closing s[open_idx] (on masked text)."""
    o = s[open_idx]
    c = PAIRS[o]
    depth = 0
    for k in range(open_idx, len(s)):
        if s[k] == o:
            depth += 1
        elif s[k] == c:
            depth -= 1
            if depth == 0:
                return k
    return len(s) - 1


def split_top(s, sep=",", angle=False):
    """Split on sep at bracket depth 0. angle=True also counts <> (types)."""
    parts, depth, cur = [], 0, []
    opens, closes = "([{", ")]}"
    if angle:
        opens += "<"; closes += ">"
    prev = ""
    for ch in s:
        if ch in opens:
            depth += 1
        elif ch in closes and not (ch == ">" and prev == "-"):
            depth -= 1
        if ch == sep and depth == 0:
            parts.append("".join(cur)); cur = []
        else:
            cur.append(ch)
        prev = ch
    if "".join(cur).strip():
        parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def squash(s, limit=110):
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= limit else s[: limit - 1] + "…"


def cell(s, limit=110):
    return squash(s, limit).replace("|", "\\|") if s else "—"


def line_of(text, idx):
    return text.count("\n", 0, idx) + 1


# --------------------------------------------------------------------------
# Source model
# --------------------------------------------------------------------------

class Src:
    def __init__(self, path):
        self.path = path
        with open(path, encoding="utf-8", errors="replace") as fh:
            self.text = fh.read()
        self.m = mask(self.text)
        self._drop_test_mods()
        self.crate = crate_name(path)

    def _drop_test_mods(self):
        for mt in list(re.finditer(r"#\s*\[\s*cfg\s*\(\s*test\s*\)\s*\]\s*(pub\s+)?mod\s+\w+\s*\{", self.m)):
            ob = mt.end() - 1
            cb = match_close(self.m, ob)
            blank = "".join("\n" if ch == "\n" else " " for ch in self.m[mt.start():cb + 1])
            self.m = self.m[:mt.start()] + blank + self.m[cb + 1:]

    def loc(self, idx):
        return "%s:%d" % (self.path, line_of(self.text, idx))


_PKG = {}


def cargo_package(path):
    """Name of the Cargo package that owns `path`: `[lib] name`, else `[package] name`
    (hyphens to underscores, as rustc names the crate) from the nearest Cargo.toml
    with a `[package]` table. A workspace-only manifest ends the walk: the file is
    not inside a package, so the caller falls back to the directory name."""
    d = os.path.dirname(os.path.abspath(path))
    while True:
        if d in _PKG:
            return _PKG[d]
        man = os.path.join(d, "Cargo.toml")
        if os.path.isfile(man):
            name = None
            try:
                with open(man, encoding="utf-8", errors="replace") as fh:
                    txt = fh.read()
            except OSError:
                txt = ""
            tables = {}
            cur = None
            for line in txt.splitlines():
                line = line.split("#", 1)[0].strip()
                hm = re.match(r"^\[\s*([\w.\-]+)\s*\]$", line)
                if hm:
                    cur = hm.group(1); tables.setdefault(cur, {}); continue
                km = re.match(r'''^(\w+)\s*=\s*(?:"([^"]+)"|'([^']+)')''', line)
                if km and cur is not None:
                    tables[cur].setdefault(km.group(1), km.group(2) or km.group(3))
            if "package" in tables:
                name = tables.get("lib", {}).get("name") or tables["package"].get("name")
                name = name.replace("-", "_") if name else None
            if name or "workspace" in tables or "package" in tables:
                _PKG[d] = name
                return name
        parent = os.path.dirname(d)
        if parent == d:
            _PKG[d] = None
            return None
        d = parent


def crate_name(path):
    pkg = cargo_package(path)
    if pkg:
        return pkg
    parts = path.replace("\\", "/").split("/")
    for i in range(len(parts) - 1, 0, -1):
        if parts[i] == "src" and parts[i - 1] not in ("", "."):
            return parts[i - 1]
    return os.path.splitext(os.path.basename(path))[0]


class Body:
    """A function body: original text, masked text, where it came from."""
    def __init__(self, src, start, end, name):
        self.src, self.start, self.end, self.name = src, start, end, name
        self.text = src.text[start:end]
        self.m = src.m[start:end]

    def loc(self, rel):
        return self.src.loc(self.start + rel)


FN_RE = re.compile(r"\bfn\s+(\w+)\s*(<[^{;]*?>)?\s*\(")


def functions(src, start=0, end=None):
    """Yield (name, params_text, body_start, body_end, fn_idx) for fns with a body."""
    end = len(src.m) if end is None else end
    for mt in FN_RE.finditer(src.m, start, end):
        po = mt.end() - 1
        pc = match_close(src.m, po)
        j = pc + 1
        while j < end and src.m[j] not in "{;":
            j += 1
        if j >= end or src.m[j] == ";":
            continue
        bc = match_close(src.m, j)
        yield mt.group(1), src.text[po + 1:pc], j + 1, bc, mt.start()


# --------------------------------------------------------------------------
# Anchor: #[derive(Accounts)] structs
# --------------------------------------------------------------------------

RAW_TYPES = ("AccountInfo", "UncheckedAccount")
# A /// CHECK note that defers validation to another program/CPI/callee is a frequent
# false assumption (e.g. GLAM audit E20: a sibling CPI path did not actually validate it).
DEFER_CHECK = re.compile(r"(validated|checked|verified|constrained|enforced|handled)\b.*\b(by|in|via|through)\b|(target|downstream|callee|external|cpi|invoked|drift|kamino)\b.*\bprogram\b|by the (target|callee|cpi|downstream|invoked)", re.I)
AUTH_NAME = re.compile(r"(^|_)(authority|admin|owner|signer|creator|manager|operator|governor|maker|taker|depositor|withdrawer|delegate)($|_)", re.I)
USER_NAME = re.compile(r"(user|owner|authority|payer|maker|taker|depositor|signer|creator|wallet|player|buyer|seller|staker|borrower|lender|member|voter|destination|recipient|beneficiary|receiver)", re.I)
SYSVAR_NAME = re.compile(r"^(rent|clock|instructions?|ix_sysvar|instruction_sysvar|sysvar_\w+|recent_blockhashes|slot_hashes|stake_history|epoch_schedule)$", re.I)


class Field:
    def __init__(self, name, ty, attrs, docs, idx):
        self.name, self.ty, self.docs, self.idx = name, ty, docs, idx
        self.items = []          # (key, value) from #[account(...)]
        for a in attrs:
            am = re.match(r"\s*account\s*\((.*)\)\s*$", a, re.S)
            if am:
                for it in split_top(am.group(1)):
                    if "=" in it and not re.match(r"^\w+\s*(==|!=)", it):
                        k, v = it.split("=", 1)
                        self.items.append((k.strip(), v.strip()))
                    else:
                        self.items.append((it.strip(), ""))
        self.keys = {k for k, _ in self.items}

    def val(self, key):
        return [v for k, v in self.items if k == key]

    # type helpers
    @property
    def base(self):
        t = re.sub(r"\s+", "", self.ty)
        t = re.sub(r"^(Option|Box)<(.*)>$", r"\2", t)
        t = re.sub(r"^(Option|Box)<(.*)>$", r"\2", t)
        return t

    @property
    def kind(self):
        return re.split(r"[<:]", self.base.split("::")[-1] if "<" not in self.base else self.base.split("<")[0].split("::")[-1])[0]

    @property
    def inner(self):
        mt = re.search(r"<(?:'\w+,)*([^<>]+(?:<[^<>]*>)?)>$", self.base)
        return mt.group(1) if mt else ""

    @property
    def is_signer(self):
        return self.kind == "Signer" or "signer" in self.keys

    @property
    def is_mut(self):
        return bool(self.keys & {"mut", "init", "init_if_needed", "zero", "close", "realloc"})

    @property
    def is_raw(self):
        return self.kind in RAW_TYPES

    @property
    def has_check_doc(self):
        return any(re.match(r"\s*CHECK\b", d) for d in self.docs)

    @property
    def check_doc(self):
        for i, d in enumerate(self.docs):
            if re.match(r"\s*CHECK\b", d):
                return re.sub(r"^\s*CHECK\s*:?\s*", "", " ".join(x.strip() for x in self.docs[i:]))
        return ""

    def owner_desc(self):
        k = self.kind
        if self.val("owner"):
            return "owner = " + self.val("owner")[0]
        if "init" in self.keys or "init_if_needed" in self.keys:
            return "created here"
        if k in ("Account", "AccountLoader", "LazyAccount"):
            if re.search(r"(TokenAccount|Mint)$", self.inner):
                return "SPL Token (by type)"
            return "this program (by type)"
        if k == "InterfaceAccount":
            return "Token or Token-2022 (by type)"
        if k in ("Program", "Interface"):
            return "executable, ID by type"
        if k == "SystemAccount":
            return "System program (by type)"
        if k == "Sysvar":
            return "sysvar ID (by type)"
        if k == "Signer":
            return "any"
        if self.val("address"):
            return "address-pinned"
        return "NOT CHECKED"

    def type_desc(self):
        k = self.kind
        if k in ("Account", "AccountLoader", "InterfaceAccount", "LazyAccount", "Program", "Interface", "Sysvar"):
            return "%s<%s>" % (k, self.inner.split("::")[-1])
        return k or squash(self.ty, 40)

    def seeds(self):
        v = self.val("seeds")
        return v[0] if v else ""

    def bump_desc(self):
        if "bump" not in self.keys:
            return ""
        v = [x for x in self.val("bump") if x]
        return ("bump = " + v[0]) if v else "canonical (bump found by Anchor)"

    def constraints(self):
        skip = {"mut", "init", "init_if_needed", "zero", "close", "seeds", "bump", "payer", "space", "signer", "owner"}
        out = []
        for k, v in self.items:
            if k in skip:
                continue
            out.append(k + (" = " + v if v else ""))
        return out


def parse_accounts_structs(src):
    out = {}
    for mt in re.finditer(r"#\s*\[\s*derive\s*\(([^)]*)\)\s*\]", src.m):
        if not re.search(r"\bAccounts\b", mt.group(1)):
            continue
        sm = re.compile(r"\bstruct\s+(\w+)\s*(<[^>{]*>)?\s*(where[^{]*)?\{").search(src.m, mt.end())
        if not sm or sm.start() - mt.end() > 600:
            continue
        ix_args = []
        hdr = src.m[mt.end():sm.start()]
        im = re.search(r"#\s*\[\s*instruction\s*\(", hdr)
        if im:
            o = mt.end() + im.end() - 1
            c = match_close(src.m, o)
            for a in split_top(src.text[o + 1:c], angle=True):
                ix_args.append(a.split(":")[0].strip())
        ob = sm.end() - 1
        cb = match_close(src.m, ob)
        fields = parse_fields(src, ob + 1, cb)
        out[(src.crate, src.path, sm.group(1))] = {"fields": fields, "src": src, "idx": sm.start(), "ix_args": ix_args}
    return out


def find_struct(structs, src, name):
    """Same file first, then same crate, then a unique match anywhere."""
    for k, v in structs.items():
        if k[1] == src.path and k[2] == name:
            return v
    same = [v for k, v in structs.items() if k[0] == src.crate and k[2] == name]
    if same:
        return same[0]
    anyw = [v for k, v in structs.items() if k[2] == name]
    return anyw[0] if len(anyw) == 1 else None


def parse_fields(src, start, end):
    fields, attrs, docs = [], [], []
    i = start
    m, t = src.m, src.text
    while i < end:
        if m[i].isspace() or m[i] == ",":
            # doc comments live in the original text, masked out in m
            if t.startswith("///", i):
                j = t.find("\n", i)
                docs.append(t[i + 3:j].strip())
                i = j
                continue
            i += 1
            continue
        if t.startswith("///", i) or t.startswith("//", i):
            j = t.find("\n", i)
            if t.startswith("///", i):
                docs.append(t[i + 3:j].strip())
            i = j if j > 0 else end
            continue
        if m.startswith("#[", i) or m.startswith("#", i):
            ob = m.find("[", i)
            cb = match_close(m, ob)
            attrs.append(t[ob + 1:cb])
            i = cb + 1
            continue
        fm = re.compile(r"(pub(\s*\([^)]*\))?\s+)?(\w+)\s*:").match(m, i)
        if not fm:
            i += 1
            continue
        name = fm.group(3)
        j, depth = fm.end(), 0
        while j < end:
            ch = m[j]
            if ch in "<([":
                depth += 1
            elif ch in ">)]":
                depth -= 1
            elif ch == "," and depth == 0:
                break
            j += 1
        ty = t[fm.end():j].strip()
        fields.append(Field(name, ty, attrs, docs, i))
        attrs, docs = [], []
        i = j + 1
    return fields


# --------------------------------------------------------------------------
# Body analysis (shared by Anchor and native)
# --------------------------------------------------------------------------

CPI_HELPER = re.compile(r"\b((?:anchor_spl::)?(?:token|token_2022|token_interface|associated_token|system_program|anchor_lang::system_program|spl_token|spl_token_2022|metadata|mpl_token_metadata)::(?:\w+::)*\w+)\s*\(")
INVOKE = re.compile(r"\b(invoke_signed_unchecked|invoke_signed|invoke_unchecked|invoke)\s*\(")
CPICTX = re.compile(r"\bCpiContext\s*::\s*(new_with_signer|new)\s*\(")
WITH_SIGNER = re.compile(r"\.\s*with_signer\s*\(")
PINO_CPI = re.compile(r"\}\s*\.\s*(invoke_signed|invoke)\s*\(")
VIEW_BORROW = r"(?:try_borrow_mut_data|try_borrow_data|try_borrow_mut|try_borrow|borrow_mut_data_unchecked|borrow_data_unchecked|borrow_mut_unchecked|borrow_unchecked_mut|borrow_unchecked|data\s*\.\s*borrow_mut|data\s*\.\s*borrow)"
GATE = re.compile(r"\b(require(?:_keys)?(?:_eq|_neq|_gt|_gte)?|assert(?:_eq|_ne)?)\s*!\s*\(")
IF_ERR = re.compile(r"\bif\s+([^{};]{3,200}?)\s*\{\s*(?:msg!\([^;]*\);\s*)*return\s+Err")


def call_args(body_m, body_t, open_idx):
    c = match_close(body_m, open_idx)
    return split_top(body_m[open_idx + 1:c]), body_t[open_idx + 1:c], c


def orig_args(body, open_idx):
    """Split call args on masked text, return original-text slices."""
    c = match_close(body.m, open_idx)
    inner_m = body.m[open_idx + 1:c]
    pieces, depth, last = [], 0, 0
    for k, ch in enumerate(inner_m):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            pieces.append((last, k)); last = k + 1
    pieces.append((last, len(inner_m)))
    t = body.text[open_idx + 1:c]
    return [t[a:b].strip() for a, b in pieces if t[a:b].strip()], c


def resolve_let(body, name, before):
    """Text of `let name = ...;` (last one before index), else ''."""
    best = ""
    for mt in re.finditer(r"\blet\s+(?:mut\s+)?" + re.escape(name) + r"\s*(?::[^=]+)?=\s*", body.m[:before]):
        e = body.m.find(";", mt.end())
        best = body.text[mt.end():e if e > 0 else len(body.text)]
    return best


def expand_seeds(body, seeds, at, depth=3):
    """Inline one level of `let` bindings named inside a signer-seeds expression
    (`&[Signer::from(&seeds)]` -> the `seeds` array), so the user-key and bump
    checks see the real seed list."""
    out = seeds
    for w in dict.fromkeys(re.findall(r"\b([a-z_]\w*)\b", seeds)):
        if w in ("from", "as_ref", "as_slice", "to_le_bytes", "to_bytes", "key", "mut"):
            continue
        let = resolve_let(body, w, at)
        if USER_NAME.search(w) and not re.search(r"seed", w, re.I) and not re.search(r"\b(Signer|Seed)\s*::|\[\s*Seed\b|^\s*&?\s*\[\s*&?\s*(\w*seed|\[)", let or ""):
            continue    # keep a name that already says "user key" (but expand `signer = Signer::from(&seeds)`, `signer = &[&seeds[..]]`, `signer_seeds = &[..]`)
        if re.search(r"next_account_info", let or "") or \
           re.match(r"^\s*&?\s*(?:mut\s+)?(?:ctx\.accounts\.\w+|self\.\w+|accounts\s*(?:\[|\.\s*(?:get|first|last|iter)\b))(?:\s*\.\s*\w+\s*\([^)]*\))*\s*\??\s*$", let or ""):
            continue    # an account binding, not a seed value
        if let and len(let) < 300 and not re.search(r"\b%s\b" % re.escape(w), let):
            if depth > 1:
                let = expand_seeds(body, let, at, depth - 1)
            out = re.sub(r"\b%s\b" % re.escape(w), lambda _m: "{" + squash(let, 200) + "}", out, count=1)
    return out


def program_of_ix(body, expr, at):
    """Best effort: which expression is the program id of an Instruction value."""
    e = expr.strip().lstrip("&").strip()
    if re.match(r"^\w+$", e):
        let = resolve_let(body, e, at)
        if let:
            e = let.strip().lstrip("&").strip()
    mt = re.match(r"([\w:]+)::instruction::(\w+)\s*\(", e)
    if mt:
        crate = mt.group(1)
        if crate.endswith("system_instruction") or crate.startswith("solana_system_interface") or crate == "system_program":
            return "System program (constant)", True, mt.group(0)
        args = split_top(mask(e[e.find("(") + 1:e.rfind(")")]))
        a = args[0] if args else "?"
        return a, False, mt.group(0)
    mt = re.match(r"(?:solana_program::)?system_instruction::(\w+)\s*\(", e)
    if mt:
        return "System program (constant)", True, mt.group(0)
    mt = re.search(r"program_id\s*:\s*([^,}]+)", e)
    if mt:
        return mt.group(1).strip(), False, "Instruction { .. }"
    mt = re.match(r"Instruction\s*::\s*new\w*\s*\(\s*([^,]+),", e)
    if mt:
        return mt.group(1).strip(), False, "Instruction::new"
    return "?", False, squash(e, 50)


def classify_program(expr, fields, body_all, native_names=()):
    """-> (desc, validated: True/False/None)."""
    e = expr.strip().lstrip("&*").strip()
    if e.startswith("System program") or e == "?":
        return e, (True if e.startswith("System") else None)
    fm = re.search(r"(?:ctx\.accounts\.|self\.|accounts\.)?(\w+)\s*\.\s*(?:key|to_account_info|address|clone|as_ref)\b", e)
    fname = fm.group(1) if fm else (e if re.match(r"^\w+$", e) and (e in fields or e in native_names) else None)
    if fname and (fname in fields or fname in native_names):
        f = fields.get(fname)
        if f is not None and f.kind in ("Program", "Interface"):
            return "`%s` (%s — ID checked by type)" % (fname, f.type_desc()), True
        if f is not None and (f.val("address") or any("key()" in v and ("ID" in v or "id()" in v) for v in f.val("constraint"))):
            return "`%s` (address constraint)" % fname, True
        n = re.escape(fname)
        if re.search(r"\b%s\s*\.\s*(key|address)\s*(\(\s*\))?\s*(!=|==)" % n, body_all) or \
           re.search(r"(!=|==)\s*&?\*?\s*(ctx\.accounts\.)?%s\s*\.\s*(key|address)\b" % n, body_all) or \
           re.search(r"require_keys_(eq|neq)\s*!\s*\([^;]*\b%s\b" % n, body_all) or \
           re.search(r"check_id\s*\([^)]*\b%s\b" % n, body_all) or \
           re.search(r"check_program_account\s*\([^)]*\b%s\b" % n, body_all):
            return "`%s` (key compared in code)" % fname, True
        return "`%s` (account-supplied, NO ID check seen)" % fname, False
    if re.search(r"(::ID\b|::id\(\)|\bID\b|crate::id|program::ID|pinocchio_\w+::ID)", e):
        return "`%s` (constant)" % squash(e, 50), True
    return "`%s`" % squash(e, 60), None


def analyse_body(bodies, fields, native_names=()):
    """Collect CPIs, writes, gates, remaining_accounts from a list of Body."""
    res = {"cpis": [], "writes": [], "gates": [], "remaining": [], "lamports": [],
           "rawwrite": [], "deser": [], "reads_after_cpi": [], "reloads": set(),
           "init_checks": False, "any_is_signer": False, "derive": [], "slices": []}
    allm = "\n".join(b.m for b in bodies)
    names = set(fields) | set(native_names)
    aliases = {}
    for b in bodies:
        for mt in re.finditer(r"\blet\s+(?:mut\s+)?(\w+)\s*(?::[^=]+)?=\s*&\s*mut\s+(?:\*\s*)?(?:ctx\.accounts\.|self\.)(\w+)", b.m):
            aliases[mt.group(1)] = mt.group(2)
        for mt in re.finditer(r"\blet\s+(?:mut\s+)?(\w+)\s*(?::[^=]+)?=\s*&\s*(?:mut\s+)?(?:ctx\.accounts\.|self\.)(\w+)\s*;", b.m):
            aliases.setdefault(mt.group(1), mt.group(2))
    # typed mutable loaders (`let cfg = Config::load_mut(acct)?`, `from_bytes_mut(&mut data)`)
    # make `cfg.field = x` a write to the account
    for b in bodies:
        vw = {}
        for mt in re.finditer(r"\blet\s+(?:mut\s+)?(\w+)\s*(?::[^=]+)?=\s*(?:unsafe\s*\{\s*)?&?\s*(?:mut\s+)?(?:ctx\.accounts\.|self\.)?(\w+)\s*(?:\.\s*to_account_info\s*\(\s*\))?\s*\.\s*" + VIEW_BORROW + r"\s*\(\s*\)", b.m):
            vw[mt.group(1)] = mt.group(2)
        for mt in re.finditer(r"\blet\s+(?:mut\s+)?(\w+)\s*(?::[^=]+)?=\s*(?:unsafe\s*\{\s*)?(?:[\w:]+\s*::\s*)?(?:load_mut|load_mut_unchecked|from_account_info_mut|from_account_view_mut|from_account_info_mut_unchecked|from_bytes_mut|try_from_bytes_mut)\s*(?:::\s*<[^>]*>\s*)?\(\s*&?\s*(?:mut\s+)?(?:ctx\.accounts\.|self\.)?(\w+)\b", b.m):
            src = mt.group(2) if mt.group(2) in names else vw.get(mt.group(2))
            if src in names:
                aliases.setdefault(mt.group(1), aliases.get(src, src))
    res["any_is_signer"] = bool(re.search(r"\bis_signer\b", allm))
    res["init_checks"] = bool(re.search(r"is_initialized|initialized\b|DISCRIMINATOR|discriminator|AccountAlreadyInitialized|lamports\(\)\s*[!=]=\s*0|data_is_empty|data_len\(\)\s*[!=]=\s*0|create_account|CreateAccount\b|allocate\s*\(", allm)) or \
        any(g in INIT_HELPERS for g in re.findall(r"\b([a-z_]\w*)\s*(?:::\s*<[^>]*>\s*)?\(", allm))
    seen_w = set()
    for b in bodies:
        m, t = b.m, b.text
        # ---- CPIs
        cpi_pos = []
        cpi_sys = {}     # position -> True when the CPI targets the System program
        for mt in INVOKE.finditer(m):
            if re.search(r"(fn|\.)\s*$", m[max(0, mt.start() - 4):mt.start()]):
                continue
            args, c = orig_args(b, mt.end() - 1)
            if not args:
                continue
            prog, const, via = program_of_ix(b, args[0], mt.start())
            desc, ok = classify_program(prog, fields, allm, native_names) if not const else (prog, True)
            seeds = expand_seeds(b, args[2], mt.start()) if mt.group(1).startswith("invoke_signed") and len(args) > 2 else ""
            res["cpis"].append({"how": "%s(%s)" % (mt.group(1), via), "prog": desc, "ok": ok, "seeds": seeds, "loc": b.loc(mt.start())})
            cpi_pos.append(mt.start())
            cpi_sys[mt.start()] = bool(re.search(r"system_instruction|system_program", args[0] + " " + desc))
        for mt in CPICTX.finditer(m):
            args, c = orig_args(b, mt.end() - 1)
            if not args:
                continue
            pexpr = args[0]
            if re.match(r"^\w+$", pexpr.strip()) and pexpr.strip() not in fields and pexpr.strip() not in native_names:
                pexpr = resolve_let(b, pexpr.strip(), mt.start()) or pexpr
            desc, ok = classify_program(pexpr, fields, allm, native_names)
            seeds = args[2] if mt.group(1) == "new_with_signer" and len(args) > 2 else ""
            if seeds:
                seeds = expand_seeds(b, seeds, mt.start())
            before = m[max(0, mt.start() - 160):mt.start()]
            hm = list(CPI_HELPER.finditer(before))
            via = hm[-1].group(1) if hm else ""
            if not via:
                after = CPI_HELPER.search(m, c, min(len(m), c + 400))
                via = after.group(1) if after else ""
            res["cpis"].append({"how": "CpiContext::%s%s" % (mt.group(1), (" → " + via) if via else ""), "prog": desc, "ok": ok, "seeds": seeds, "loc": b.loc(mt.start())})
            cpi_pos.append(mt.start())
            cpi_sys[mt.start()] = bool(re.search(r"system_program", pexpr + " " + via))
        for mt in WITH_SIGNER.finditer(m):
            args, c = orig_args(b, mt.end() - 1)
            seeds = expand_seeds(b, args[0], mt.start()) if args else ""
            hm = list(CPI_HELPER.finditer(m[max(0, mt.start() - 200):mt.start()]))
            res["cpis"].append({"how": ".with_signer%s" % ((" → " + hm[-1].group(1)) if hm else ""), "prog": "(program from the CpiContext it signs — see the CpiContext line)", "ok": True, "seeds": seeds, "loc": b.loc(mt.start())})
            cpi_pos.append(mt.start())
            cpi_sys[mt.start()] = bool(hm and "system_program" in hm[-1].group(1))
        for mt in PINO_CPI.finditer(m):
            # struct-literal CPI: Transfer { .. }.invoke()
            depth, k = 0, mt.start()
            while k >= 0:
                if m[k] == "}":
                    depth += 1
                elif m[k] == "{":
                    depth -= 1
                    if depth == 0:
                        break
                k -= 1
            nm = re.search(r"([\w:]+)\s*$", m[:k])
            name = nm.group(1) if nm else "?"
            args, c = orig_args(b, mt.end() - 1)
            seeds = expand_seeds(b, args[0], mt.start()) if args and mt.group(1) == "invoke_signed" else ""
            res["cpis"].append({"how": "%s { .. }.%s()" % (name, mt.group(1)), "prog": "fixed by the CPI crate (`%s`) — confirm the crate pins the program ID" % name, "ok": True, "seeds": seeds, "loc": b.loc(mt.start())})
            cpi_pos.append(mt.start())
            cpi_sys[mt.start()] = bool(re.search(r"pinocchio_system|system_program|(^|::)(CreateAccount|CreateAccountWithSeed|Allocate|Assign)$", name))
        # ---- writes
        for mt in re.finditer(r"(?:ctx\.accounts\.|self\.)?\b(\w+)((?:\s*\.\s*\w+)+)\s*([+\-*/%|&^]|<<|>>)?=(?!=)", m):
            base = mt.group(1)
            pre = m[max(0, mt.start() - 3):mt.start()]
            if re.search(r"[=!<>]$", pre.strip()) or re.search(r"\blet\s+$", m[max(0, mt.start() - 8):mt.start()]):
                continue
            acct = aliases.get(base, base)
            if acct not in names:
                continue
            path = re.sub(r"\s+", "", mt.group(2))
            if path.startswith(".key") or "(" in path:
                continue
            w = acct + path
            if w not in seen_w:
                seen_w.add(w); res["writes"].append(w)
        for mt in re.finditer(r"\*{1,2}\s*(?:ctx\.accounts\.|self\.)?(\w+)(?:\s*\.\s*to_account_info\s*\(\s*\))?\s*\.\s*(?:try_borrow_mut_lamports\s*\(\s*\)\s*\?|lamports\s*\.\s*borrow_mut\s*\(\s*\))\s*([+\-]?=)\s*([^;]*)", m):
            acct = aliases.get(mt.group(1), mt.group(1))
            res["lamports"].append((acct, mt.group(2), squash(t[mt.start(3):mt.end(3)], 40), b.loc(mt.start())))
            w = "lamports of " + acct
            if w not in seen_w:
                seen_w.add(w); res["writes"].append(w)
        for mt in re.finditer(r"(?:ctx\.accounts\.|self\.)?\b(\w+)\s*\.\s*(sub_lamports|add_lamports|set_lamports|assign|realloc|resize|close)\s*\(", m):
            acct = aliases.get(mt.group(1), mt.group(1))
            if acct in names:
                w = "%s of %s" % ({"assign": "owner", "realloc": "size", "resize": "size", "close": "closed:"}.get(mt.group(2), "lamports"), acct)
                if w not in seen_w:
                    seen_w.add(w); res["writes"].append(w)
                if mt.group(2) in ("sub_lamports", "set_lamports"):
                    res["lamports"].append((acct, mt.group(2), "", b.loc(mt.start())))
        for mt in re.finditer(r"(?:ctx\.accounts\.|self\.)?\b(\w+)\s*(?:\.\s*to_account_info\s*\(\s*\))?\s*\.\s*(?:try_borrow_mut_data|data\s*\.\s*borrow_mut|try_borrow_mut|borrow_mut_data_unchecked|borrow_mut_unchecked|borrow_unchecked_mut)\s*\(", m):
            acct = aliases.get(mt.group(1), mt.group(1))
            if acct in names:
                res["rawwrite"].append((acct, b.loc(mt.start())))
                w = "raw data of " + acct
                if w not in seen_w:
                    seen_w.add(w); res["writes"].append(w)
        # ---- writes through a borrowed data view or a typed mutable loader. A view
        # bound from ANY borrow (`borrow_unchecked()` included — Pinocchio code casts
        # it to `*mut u8`) is a state change once something writes into it:
        # `v[..] = x`, `v.copy_from_slice(..)`, `x.serialize(&mut *v)`,
        # `from_bytes_mut(&mut v ..)`, or a pointer copy whose DESTINATION is the view
        # (`copy_nonoverlapping(src, v.as_ptr() as *mut u8, n)`, also through a
        # `let p = v.as_mut_ptr()` alias). Copying OUT of a view is a read.
        views = {}
        for mt in re.finditer(r"\blet\s+(?:mut\s+)?(\w+)\s*(?::[^=]+)?=\s*(?:unsafe\s*\{\s*)?&?\s*(?:mut\s+)?(?:ctx\.accounts\.|self\.)?(\w+)\s*(?:\.\s*to_account_info\s*\(\s*\))?\s*\.\s*" + VIEW_BORROW + r"\s*\(\s*\)", m):
            acct = aliases.get(mt.group(2), mt.group(2))
            if acct in names:
                views[mt.group(1)] = (acct, mt.end())
        for var, (acct, at) in views.items():
            v = re.escape(var)
            wpats = [r"\b%s\s*\[[^\]]*\]\s*(?:[+\-*/%%|&^]|<<|>>)?=(?!=)" % v,
                     r"\b%s\s*(?:\[[^\]]*\]\s*)?\.\s*(?:copy_from_slice|clone_from_slice|fill|swap_with_slice|copy_within)\s*\(" % v,
                     r"\b(?:serialize|pack|pack_into_slice|try_serialize|write_all)\s*\([^;]*&\s*mut\s+(?:\*\s*|&\s*mut\s+)?%s\b" % v,
                     r"\b(?:from_bytes_mut|try_from_bytes_mut|cast_slice_mut|from_mut|load_mut)\s*(?:::\s*<[^>]*>\s*)?\(\s*&\s*mut\s+%s\b" % v]
            wm = None
            for wp in wpats:
                wm = re.search(wp, m[at:])
                if wm:
                    break
            if not wm:
                ptrs = [v] + [re.escape(pm.group(1)) for pm in re.finditer(r"\blet\s+(?:mut\s+)?(\w+)\s*(?::[^=]+)?=\s*(?:unsafe\s*\{\s*)?%s\s*\.\s*(?:as_mut_ptr\s*\(\s*\)|as_ptr\s*\(\s*\)\s*as\s*\*\s*mut\b)" % v, m[at:])]
                into_view = r"^\W*(?:%s\s*\.\s*(?:as_mut_ptr\b|as_ptr\s*\(\s*\)\s*as\s*\*\s*mut\b)|(?:%s)\b)" % (v, "|".join(ptrs[1:]) or r"(?!x)x")
                for cm in re.finditer(r"\b(copy_nonoverlapping|copy|write_bytes|write|write_unaligned|write_volatile)\s*(?:::\s*<[^>]*>\s*)?\(", m[at:]):
                    o = at + cm.end() - 1
                    args = split_top(m[o + 1:match_close(m, o)])
                    dst = args[1] if cm.group(1) in ("copy_nonoverlapping", "copy") and len(args) > 1 else args[0] if args else ""
                    if re.search(into_view, dst):
                        wm = cm
                        break
            if wm:
                res["rawwrite"].append((acct, b.loc(at + wm.start())))
                w = "raw data of " + acct
                if w not in seen_w:
                    seen_w.add(w); res["writes"].append(w)
        # ---- manual deserialisation of raw accounts
        for mt in re.finditer(r"\b([A-Z]\w*)\s*::\s*(unpack|unpack_unchecked|unpack_from_slice|try_from_slice|deserialize|try_deserialize|try_deserialize_unchecked|load|load_mut|from_account_info|from_account_view|from_bytes|try_from_bytes|load_unchecked)\s*\(\s*&?\s*(?:mut\s+)?\*?\s*(?:ctx\.accounts\.|self\.)?(\w+)", m):
            acct = aliases.get(mt.group(3), mt.group(3))
            if acct in names:
                res["deser"].append((acct, mt.group(1), mt.group(2), b.loc(mt.start())))
        # ---- hand-coded byte ranges on borrowed account data (offset-mismatch)
        for mt in re.finditer(r"\blet\s+(?:mut\s+)?(\w+)\s*(?::[^=]+)?=\s*(?:unsafe\s*\{\s*)?&?\s*(?:mut\s+)?(?:ctx\.accounts\.|self\.)?(\w+)\s*\.\s*(?:try_borrow_mut_data|try_borrow_data|try_borrow_mut|try_borrow|borrow_mut_data_unchecked|borrow_data_unchecked|borrow_mut_unchecked|borrow_unchecked|data\s*\.\s*borrow_mut|data\s*\.\s*borrow)\s*\(\s*\)", m):
            var, acct = mt.group(1), aliases.get(mt.group(2), mt.group(2))
            if acct not in names:
                continue
            for sm in re.finditer(r"\b%s\s*\[\s*(\d*)\s*\.\.\s*(=?)\s*(\d*)\s*\]|\b%s\s*\[\s*(\d+)\s*\]" % (re.escape(var), re.escape(var)), m[mt.end():]):
                if sm.group(4) is not None:
                    a, e = int(sm.group(4)), int(sm.group(4)) + 1
                else:
                    if not sm.group(3):
                        continue
                    a = int(sm.group(1) or 0)
                    e = int(sm.group(3)) + (1 if sm.group(2) else 0)
                res["slices"].append((acct, var, a, e, b.loc(mt.end() + sm.start())))
        # ---- PDA derivations
        for mt in re.finditer(r"\b(find_program_address|create_program_address|derive_address)\s*\(", m):
            args, c = orig_args(b, mt.end() - 1)
            lhs = re.search(r"let\s+(?:\(\s*(\w+)\s*,\s*(\w+)\s*\)|(\w+))\s*(?::[^=]+)?=\s*[^;]*$", m[max(0, mt.start() - 120):mt.start()])
            var = (lhs.group(1) or lhs.group(3)) if lhs else ""
            res["derive"].append({"fn": mt.group(1), "seeds": args[0] if args else "", "var": var, "loc": b.loc(mt.start()), "body": b})
        # ---- gates
        for mt in GATE.finditer(m):
            args_t, c = orig_args(b, mt.end() - 1)
            res["gates"].append("%s!(%s)" % (mt.group(1), squash(", ".join(args_t), 90)))
        for mt in IF_ERR.finditer(m):
            res["gates"].append("if %s → Err" % squash(t[mt.start(1):mt.end(1)], 90))
        # ---- remaining accounts
        for mt in re.finditer(r"\bremaining_accounts\b", m):
            # a rest binding (`remaining_accounts @ ..`), a field declaration or a
            # shorthand struct field moves the slice; it is not a use of its elements
            if re.match(r"\s*@", m[mt.end():]) or re.match(r"\s*:\s*&", m[mt.end():]) or \
               (re.match(r"\s*[,}]", m[mt.end():]) and re.search(r"[{,]\s*$", m[:mt.start()])):
                continue
            res["remaining"].append(b.loc(mt.start()))
        # ---- reads after CPI without reload (Anchor)
        for mt in re.finditer(r"\breload\s*\(", m):
            pre = re.search(r"(\w+)\s*\.\s*$", m[:mt.start()])
            if pre:
                res["reloads"].add(aliases.get(pre.group(1), pre.group(1)))
        if cpi_pos:
            first = min(cpi_pos)
            for mt in re.finditer(r"(?:ctx\.accounts\.|self\.)\b(\w+)\s*\.\s*(amount|supply|lamports\s*\(\s*\))", m[first:]):
                acct = mt.group(1)
                f = fields.get(acct)
                rd = first + mt.start()
                touching = [p for p in cpi_pos if p < rd and re.search(r"\b%s\b" % re.escape(acct), m[max(0, p - 500):min(rd, p + 300)])]
                # `lamports()` reads the live AccountInfo (never stale); a System-program
                # CPI (transfer / create / allocate) cannot change a program-owned
                # account's data, so it cannot leave a deserialized field stale.
                if mt.group(2).startswith("lamports") or all(cpi_sys.get(p) for p in touching):
                    continue
                if f is not None and f.kind in ("Account", "InterfaceAccount", "AccountLoader") and touching:
                    res["reads_after_cpi"].append((acct, re.sub(r"\s+", "", mt.group(2)), b.loc(rd)))
    return res


# --------------------------------------------------------------------------
# Anchor instructions
# --------------------------------------------------------------------------

def anchor_instructions(srcs, structs):
    insts = []
    ctx_fns = {}     # struct -> [Body] for fns taking Context<Struct> outside #[program]
    impls = {}       # struct -> [Body] for impl blocks
    prog_ranges = []
    for s in srcs:
        for mt in re.finditer(r"#\s*\[\s*program\s*\]\s*(?:#\s*\[[^\]]*\]\s*)*(pub\s+)?mod\s+(\w+)\s*\{", s.m):
            ob = mt.end() - 1
            cb = match_close(s.m, ob)
            prog_ranges.append((s, ob, cb, mt.group(2)))
    for s in srcs:
        for name, params, bs, be, fi in functions(s):
            cm = re.search(r"Context\s*<\s*(?:'\w+\s*,\s*)*(\w+)", params)
            if cm and not any(ps is s and ob < fi < cb for ps, ob, cb, _ in prog_ranges):
                ctx_fns.setdefault((s.crate, cm.group(1)), []).append(Body(s, bs, be, name))
        snames = {k[2] for k in structs}
        for mt in re.finditer(r"\bimpl\s*(<[^>]*>)?\s*(\w+)\s*(<[^>{]*>)?\s*\{", s.m):
            if mt.group(2) in snames:
                ob = mt.end() - 1
                cb = match_close(s.m, ob)
                for name, params, bs, be, fi in functions(s, ob, cb):
                    impls.setdefault((s.crate, mt.group(2)), []).append(Body(s, bs, be, name))
    for s, ob, cb, prog in prog_ranges:
        for name, params, bs, be, fi in functions(s, ob, cb):
            cm = re.search(r"Context\s*<\s*(?:'\w+\s*,\s*)*(\w+)", params)
            if not cm:
                continue
            st = cm.group(1)
            bodies = [Body(s, bs, be, name)] + ctx_fns.get((s.crate, st), []) + impls.get((s.crate, st), [])
            args = [a.split(":")[0].strip() for a in split_top(params, angle=True)[1:]]
            insts.append({"program": prog, "name": name, "struct": st, "src": s, "idx": fi,
                          "bodies": bodies, "args": args, "framework": "Anchor"})
    return insts


# --------------------------------------------------------------------------
# Native / Pinocchio handlers
# --------------------------------------------------------------------------

LOCAL_FNS = set()
TRAIT_FNS = {"from", "into", "new", "try_from", "try_into", "as_ref", "as_mut", "default", "fmt", "eq", "clone", "len",
             "deserialize", "serialize", "pack", "unpack", "from_bytes", "to_bytes", "load", "process", "main"}

ACCT_PARAM = re.compile(r"&\s*(?:'\w+\s+)?(?:mut\s+)?\[\s*(?:[\w:]+::)?(AccountInfo|AccountView)\b")


class NAcct:
    def __init__(self, name, how, idx):
        self.name, self.how, self.idx = name, how, idx


# Account-check helpers. Native and Pinocchio code rarely writes `acct.is_signer()` in
# the handler: it calls `verify_signer(acct)`, `check_owner(acct, &ID)`, or a method
# `acct.assert_signer()`. A helper is classified by which of its PARAMETERS it checks
# (`p.is_signer()`, `p.owner()`, `owned_by(p, ..)`), followed through helper-to-helper
# calls to a fixpoint, so only the account in that argument position counts as
# checked: `validate_ata(vault, owner.address(), ..)` checks `vault`, not `owner`.
HELPERS = {}      # fn name -> {"signer": set(param idx), "owner": set(param idx)}; idx -1 = self
SIGNER_EXTERNAL = re.compile(r"\b(?:verify|check|assert|require|expect|ensure|validate)_\w*signer\w*\s*\(\s*&?\s*(?:mut\s+)?\*?\s*(\w+)\b")
SIGNER_METHOD = re.compile(r"\b(\w+)\s*\.\s*signer_key\s*\(\s*\)")   # solana-program: Some(key) only for a signer
SIGNER_WRAPPER = re.compile(r"\b\w*Signer\w*\s*(?:::\s*<[^>]*>\s*)?::\s*(?:try_from|new|check|from_account_info|from_account_view)\s*\(\s*&?\s*(?:mut\s+)?(\w+)\b")
CALL_RE = re.compile(r"\b([a-z_]\w*)\s*\(([^;{}]*)\)")


def _params(params):
    out = []
    for p in split_top(params, angle=True):
        nm = p.split(":")[0].strip().lstrip("&").replace("mut ", "").strip()
        out.append("self" if nm.endswith("self") else nm)
    return out


def _arg_is(arg, name):
    return re.match(r"^&?\s*(?:mut\s+)?\*?\s*%s\s*(?:\.\s*(?:clone|as_ref)\s*\(\s*\))?$" % re.escape(name), arg.strip())


INIT_RE = r"is_initialized|initialized\b|DISCRIMINATOR|discriminator|AccountAlreadyInitialized|lamports\(\)\s*[!=><]=?\s*0|data_is_empty|data_len\(\)\s*[!=]=\s*0|create_account|CreateAccount\b|allocate\s*\("
INIT_HELPERS = set()   # local fns whose body (or a helper they call) carries an init guard


def collect_helpers(srcs):
    defs = []
    for s in srcs:
        for name, params, bs, be, fi in functions(s):
            defs.append((name, _params(params), s.m[bs:be]))
    for _ in range(5):
        grew = False
        for name, _ps, body in defs:
            if name not in INIT_HELPERS and name not in TRAIT_FNS and (re.search(INIT_RE, body) or any(g in INIT_HELPERS for g, _a in CALL_RE.findall(body))):
                INIT_HELPERS.add(name); grew = True
        if not grew:
            break
    for name, _ps, _b in defs:
        HELPERS.setdefault(name, {"signer": set(), "owner": set()})
    direct = {
        "signer": lambda p: r"\b%s\s*\.\s*(?:is_signer|signer_key)\b" % p,
        "owner": lambda p: r"\b%s\s*\.\s*(?:owner|owned_by|is_owned_by)\b|\b(?:owned_by|is_owned_by|check_owner|assert_owner\w*)\s*\(\s*&?\s*%s\b" % (p, p),
    }
    for _ in range(5):
        changed = False
        for name, ps, body in defs:
            h = HELPERS[name]
            for kind in ("signer", "owner"):
                for i, p in enumerate(ps):
                    idx = -1 if p == "self" else i
                    if idx in h[kind] or not re.match(r"^\w+$", p):
                        continue
                    hit = bool(re.search(direct[kind](p), body))
                    if not hit:
                        for g, args in CALL_RE.findall(body):
                            gi = HELPERS.get(g, {}).get(kind, ())
                            al = split_top(args)
                            if any(0 <= j < len(al) and _arg_is(al[j], p) for j in gi):
                                hit = True
                                break
                    if not hit:
                        hit = any(-1 in hh[kind] and re.search(r"\b%s\s*\.\s*%s\s*\(" % (p, re.escape(g)), body) for g, hh in HELPERS.items())
                    if hit:
                        h[kind].add(idx)
                        changed = True
        if not changed:
            break


def helper_checked(m, name, kind):
    """Helpers that check `kind` ("signer" / "owner") on account `name` in masked text `m`."""
    n = re.escape(name)
    hits = []
    for g, args in CALL_RE.findall(m):
        idxs = HELPERS.get(g, {}).get(kind, ())
        al = split_top(args)
        if any(0 <= j < len(al) and _arg_is(al[j], name) for j in idxs):
            hits.append(g)
    for g, hh in HELPERS.items():
        if -1 in hh[kind] and re.search(r"\b%s\s*\.\s*%s\s*\(" % (n, re.escape(g)), m):
            hits.append(g)
    if kind == "signer":
        hits += [mt.group(0).split("(")[0].strip() for mt in SIGNER_EXTERNAL.finditer(m) if mt.group(1) == name]
        hits += [mt.group(0).split("(")[0].strip() for mt in SIGNER_WRAPPER.finditer(m) if mt.group(1) == name]
        hits += ["signer_key" for mt in SIGNER_METHOD.finditer(m) if mt.group(1) == name]
    return sorted(set(hits))


def any_signer_check(m):
    """A signature is checked somewhere in masked text `m`: `is_signer`, a signer helper
    (by parameter analysis or by name), or a typed signer wrapper."""
    if re.search(r"\bis_signer\b", m) or SIGNER_EXTERNAL.search(m) or SIGNER_WRAPPER.search(m) or SIGNER_METHOD.search(m):
        return True
    if any(HELPERS.get(g, {}).get("signer") for g, _a in CALL_RE.findall(m)):
        return True
    return any(-1 in hh["signer"] and re.search(r"\.\s*%s\s*\(" % re.escape(g), m) for g, hh in HELPERS.items())


# Typed account structs. Pinocchio and modern native programs validate accounts in a
# constructor (`impl TryFrom<&[AccountView]> for DepositAccounts`, or any associated fn
# that takes the account slice and returns `Self`), and the processor only calls
# `DepositAccounts::try_from(accounts)`, or a wrapper type built by a macro or holding
# a `DepositAccounts` field. The constructor's body is merged into every processor that
# reaches it, so its signer, owner and key checks count for that instruction, and the
# constructor is not mapped a second time on its own.
ACCT_IMPLS = {}   # (crate, Type) -> [Body]
ACCT_ALIAS = {}   # (crate, Type) -> Type whose constructor validates the accounts
CTOR_NAMES = ("try_from", "new", "parse", "from_accounts", "from_account_infos", "from_account_views", "load", "validate")


def collect_account_impls(srcs):
    for s in srcs:
        for mt in re.finditer(r"\bimpl\b", s.m):
            j = s.m.find("{", mt.end())
            if j < 0 or ";" in s.m[mt.end():j]:
                continue
            head = s.m[mt.end():j]
            fm = re.search(r"\bfor\s+(\w+)\s*(?:<[^{]*>)?\s*(?:where\b[^{]*)?$", head)
            if fm:
                if not re.search(r"TryFrom\s*<[^{]*\b(AccountView|AccountInfo)\b", head[:fm.start()]):
                    continue
                ty, is_tf = fm.group(1), True
            else:
                im = re.match(r"\s*(?:<[^{]*?>)?\s*(\w+)\s*(?:<[^{]*>)?\s*(?:where\b[^{]*)?$", head)
                if not im:
                    continue
                ty, is_tf = im.group(1), False
            cb = match_close(s.m, j)
            for name, params, bs, be, fi in functions(s, j, cb):
                if not ACCT_PARAM.search(params):
                    continue
                if is_tf or re.search(r"->\s*(?:Result\s*<\s*)?Self\b", s.m[fi:bs]):
                    ACCT_IMPLS.setdefault((s.crate, ty), []).append(Body(s, bs, be, name))
    for s in srcs:
        for mt in re.finditer(r"\b\w+\s*!\s*\(([^;]*?)\)", s.m):
            ids = re.findall(r"\b([A-Z]\w*)\b", mt.group(1))
            for i, x in enumerate(ids):
                if (s.crate, x) in ACCT_IMPLS:
                    continue
                for y in ids[i + 1:]:
                    if (s.crate, y) in ACCT_IMPLS:
                        ACCT_ALIAS.setdefault((s.crate, x), y)
                        break
        for mt in re.finditer(r"\bstruct\s+(\w+)\s*(?:<[^>{;]*>)?\s*\{", s.m):
            ob = mt.end() - 1
            cb = match_close(s.m, ob)
            if (s.crate, mt.group(1)) in ACCT_IMPLS:
                continue
            for ft in re.findall(r"\b\w+\s*:\s*([A-Z]\w*)\b", s.m[ob:cb]):
                if (s.crate, ft) in ACCT_IMPLS:
                    ACCT_ALIAS.setdefault((s.crate, mt.group(1)), ft)
                    break


def resolve_account_impl(crate, ty, depth=0):
    if (crate, ty) in ACCT_IMPLS:
        return ty, ACCT_IMPLS[(crate, ty)]
    if depth < 3 and (crate, ty) in ACCT_ALIAS:
        return resolve_account_impl(crate, ACCT_ALIAS[(crate, ty)], depth + 1)
    return None, []


def unpack_accounts(body):
    accts = []
    for mt in re.finditer(r"\blet\s+(?:mut\s+)?(\w+)\s*(?::[^=]+)?=\s*next_account_info\s*\(", body.m):
        accts.append(NAcct(mt.group(1), "next_account_info", mt.start()))
    for mt in re.finditer(r"\blet\s+\[([^\]]*)\]\s*=\s*([^;{]*?)(?:else|;)", body.m):
        if "accounts" not in mt.group(2):
            continue
        for nm in split_top(mt.group(1)):
            nm = nm.strip().lstrip("&").replace("ref ", "").replace("mut ", "").strip()
            if re.match(r"^\w+$", nm):
                accts.append(NAcct(nm, "slice pattern", mt.start()))
    for mt in re.finditer(r"\blet\s+(?:mut\s+)?(\w+)\s*(?::[^=]+)?=\s*&?\s*accounts\s*(?:\[\s*(\d+)\s*\]|\.get\s*\(\s*(\d+)\s*\)|\.(first)\s*\(\s*\))", body.m):
        accts.append(NAcct(mt.group(1), "accounts[%s]" % (mt.group(2) or mt.group(3) or "0"), mt.start()))
    return accts


GENERIC_FN = {"process", "handler", "handle", "run", "execute", "invoke_handler"}


def qualified_name(src, name):
    """`process` / `handler` written once per instruction module is not a name: two
    instructions would share one key. Prefix the module (`claim::process`)."""
    if name not in GENERIC_FN:
        return name
    stem = os.path.splitext(os.path.basename(src.path))[0]
    if stem == "mod":
        stem = os.path.basename(os.path.dirname(src.path))
    if stem in ("lib", "main", "processor", "entrypoint", "instruction", "instructions", "src"):
        return name
    return "%s::%s" % (stem, name)


def native_handlers(srcs, anchor_struct_names):
    out = []
    for s in srcs:
        if re.search(r"#\s*\[\s*program\s*\]", s.m):
            continue
        fw = "Pinocchio" if re.search(r"\bpinocchio\b|AccountView\b", s.m) else "native solana-program"
        for name, params, bs, be, fi in functions(s):
            if not ACCT_PARAM.search(params):
                continue
            pnames = [p.split(":")[0].strip().lstrip("_") for p in split_top(params, angle=True)]
            body = Body(s, bs, be, name)
            accts = unpack_accounts(body)
            bodies, via = [body], []
            if not accts:
                for tm in re.finditer(r"\b([A-Z]\w*)\s*(?:::\s*<[^>]*>\s*)?::\s*(\w+)\s*\(", body.m):
                    if tm.group(2) not in CTOR_NAMES:
                        continue
                    args = body.m[tm.end():match_close(body.m, tm.end() - 1)]
                    if not re.search(r"\baccounts\b", args):
                        continue
                    ty, impl_bodies = resolve_account_impl(s.crate, tm.group(1))
                    for ib in impl_bodies:
                        if all(ib.start != b.start or ib.src is not b.src for b in bodies):
                            bodies.append(ib)
                            accts.extend(unpack_accounts(ib))
                    if impl_bodies:
                        via.append("%s::%s" % (ty, impl_bodies[0].name))
            dispatch = re.findall(r"\b(\w+)\s*\(\s*(?:program_id\s*,\s*)?&?\s*(?:mut\s+)?accounts\b", body.m)
            dispatch = [d for d in dispatch if d not in ("next_account_info", "iter", "len", "get", "Ok", "Some")]
            if via:
                dispatch = [d for d in dispatch if d not in CTOR_NAMES]
            if not accts and dispatch:
                out.append({"dispatcher": True, "name": name, "src": s, "idx": fi, "calls": dispatch, "framework": fw,
                            "program": s.crate})
                continue
            out.append({"dispatcher": False, "program": s.crate, "name": qualified_name(s, name), "src": s, "idx": fi,
                        "bodies": bodies, "accts": accts, "framework": fw, "via": via,
                        "delegates": dispatch, "params": pnames})
    # A constructor merged into a processor is not mapped again as a handler of its own.
    merged = {(b.src.path, b.start) for h in out if not h["dispatcher"] for b in h["bodies"][1:]}
    return [h for h in out if h["dispatcher"] or len(h["bodies"]) > 1 or (h["src"].path, h["bodies"][0].start) not in merged]




def native_account_rows(h, res):
    m = "\n".join(b.m for b in h["bodies"])
    rows, unresolved = [], []
    helper_calls = re.findall(r"\b([a-z_]\w*)\s*\(([^;]*)\)", m)
    for a in h["accts"]:
        n = re.escape(a.name)
        if a.name.startswith("_"):
            used = len(re.findall(r"\b%s\b" % n, m)) > 1
        else:
            used = True
        signer = "checked" if re.search(r"\b%s\s*\.\s*is_signer\b" % n, m) else "—"
        if signer == "—":
            hs = helper_checked(m, a.name, "signer")
            if hs:
                signer = "checked (%s)" % ", ".join(hs[:2])
        writable = "checked" if re.search(r"\b%s\s*\.\s*is_writable\b" % n, m) else ""
        owner = "checked" if (re.search(r"\b%s\s*\.\s*owner\b" % n, m) or re.search(r"(owned_by|is_owned_by|check_owner|assert_owner\w*)\s*\([^;]*\b%s\b" % n, m) or re.search(r"\b%s\s*\.\s*(is_owned_by|owned_by)\s*\(" % n, m)) else "—"
        owner_via = []
        if owner == "—":
            owner_via = helper_checked(m, a.name, "owner")
            if owner_via:
                owner = "checked (%s)" % ", ".join(owner_via[:2])
        KREF = r"\b%s\s*\.\s*(?:key|address)\s*(?:\(\s*\))?(?:\s*\.\s*(?:as_ref|as_array|to_bytes)\s*\(\s*\))?" % n
        partners = [x.strip() for x in re.findall(KREF + r"\s*(?:!=|==)\s*([^{};|&]+)", m)] + \
                   [x.strip() for x in re.findall(r"([\w.\[\]()&*:]+(?:\s*\.\s*\w+\s*\(\s*\))*)\s*(?:!=|==)\s*&?\*?\s*" + KREF[2:], m)]
        key = bool(partners or re.search(r"check_id\s*\(\s*&?\*?\s*%s\b" % n, m))
        ty = ""
        for acct, t, how, loc in res["deser"]:
            if acct == a.name:
                ty = t
        written = any(w.endswith(" " + a.name) or w.startswith(a.name + ".") for w in res["writes"])
        seeds, bump = "", ""
        for d in res["derive"]:
            if d["var"] and re.search(r"\b%s\b[^;\n]{0,80}\b%s\s*\.\s*(key|address)|\b%s\s*\.\s*(key|address)[^;\n]{0,80}\b%s\b" % (re.escape(d["var"]), n, n, re.escape(d["var"])), m):
                seeds = d["seeds"]
                bump = "canonical (find_program_address)" if d["fn"] == "find_program_address" else "supplied: " + bump_source(d, h)
        passed = [f for f, args in helper_calls if f in LOCAL_FNS and f not in TRAIT_FNS and re.search(r"\b%s\b" % n, args) and f not in ("msg", "Ok", "Err", "Some", "invoke", "invoke_signed", "next_account_info", "clone", "key", "require", "assert", "map_err", "ok_or")]
        wallet = signer.startswith("checked") and not written and not ty
        if owner == "—" and passed and not a.name.endswith("_program") and not wallet:
            owner = "? (passed to %s)" % ", ".join(sorted(set(passed))[:3])
            unresolved.append(a.name)
        if signer == "—" and passed and AUTH_NAME.search(a.name):
            signer = "? (passed to %s)" % ", ".join(sorted(set(passed))[:3])
            unresolved.append(a.name)
        rows.append({"name": a.name, "how": a.how, "signer": signer, "mut": ("written" if written else "") + ((" · is_writable " + writable) if writable else ""),
                     "owner": owner, "key": "key compared" if key else "—", "type": ty or ("?" if used else "unused"),
                     "seeds": seeds, "bump": bump, "written": written, "used": used, "partners": partners, "owner_via": owner_via})
    return rows, sorted(set(unresolved))


def bump_source(d, h):
    s = d["seeds"]
    for mt in re.finditer(r"\b(\w*(?:bump|nonce)\w*)\b", s):
        let = resolve_let(d["body"], mt.group(1), len(d["body"].m))
        if let and re.search(r"\.\s*(bump|nonce)\w*\b", let):
            return "stored field (`%s` = `%s`)" % (mt.group(1), squash(let, 40))
    if re.search(r"\.\s*bump\b", s):
        return "stored field (`%s`)" % squash(re.search(r"[\w.]*\.\s*bump\w*", s).group(0), 40)
    if re.search(r"\b(bump|seed)\w*\b", s):
        return "`bump` from instruction data or caller — verify"
    return "inside seeds"


# --------------------------------------------------------------------------
# #[repr(C)] / #[repr(packed)] layouts (offset-mismatch)
# --------------------------------------------------------------------------

LAYOUTS = {}     # (crate, Name) -> {"repr", "fields": [(name, start, end)], "size"} or None
CONSTS = {}
PRIM = {"u8": 1, "i8": 1, "bool": 1, "u16": 2, "i16": 2, "u32": 4, "i32": 4, "f32": 4, "u64": 8, "i64": 8, "f64": 8,
        "u128": 16, "i128": 16, "Pubkey": 32, "Address": 32}


def collect_layouts(srcs):
    raw = {}
    for s in srcs:
        for mt in re.finditer(r"\bconst\s+([A-Z_][A-Z0-9_]*)\s*:\s*usize\s*=\s*(\d+)\s*;", s.m):
            CONSTS[mt.group(1)] = int(mt.group(2))
        for mt in re.finditer(r"#\s*\[\s*repr\s*\(([^)]*)\)\s*\]((?:\s*#\s*\[[^\]]*\])*)\s*(?:pub(?:\s*\([^)]*\))?\s+)?struct\s+(\w+)\s*\{", s.m):
            reprs = mt.group(1).replace(" ", "")
            if not re.search(r"(^|,)(C|packed|transparent)(,|$)", reprs):
                continue
            ob = mt.end() - 1
            cb = match_close(s.m, ob)
            raw[(s.crate, mt.group(3))] = ("packed" if "packed" in reprs else "C", s.m[ob + 1:cb])
    def size_align(crate, ty, depth=0):
        ty = re.sub(r"\s+", "", ty).split("::")[-1]
        if ty in PRIM:
            return PRIM[ty], (1 if ty in ("Pubkey", "Address") else PRIM[ty])
        am = re.match(r"^\[(.+);(\w+)\]$", ty)
        if am:
            n = int(am.group(2)) if am.group(2).isdigit() else CONSTS.get(am.group(2))
            inner = size_align(crate, am.group(1), depth + 1)
            if n is None or inner is None:
                return None
            return inner[0] * n, inner[1]
        if (crate, ty) in raw and depth < 4:
            lay = layout_of(crate, ty, depth + 1)
            return (lay["size"], lay["align"]) if lay else None
        return None
    def layout_of(crate, name, depth=0):
        if (crate, name) in LAYOUTS:
            return LAYOUTS[(crate, name)]
        repr_, body = raw[(crate, name)]
        off, fields, maxal = 0, [], 1
        for part in split_top(body, angle=True):
            fm = re.match(r"^\s*(?:pub(?:\s*\([^)]*\))?\s+)?(\w+)\s*:\s*(.+?)\s*$", part, re.S)
            if not fm:
                continue
            sa = size_align(crate, fm.group(2), depth)
            if sa is None:
                LAYOUTS[(crate, name)] = None
                return None
            sz, al = sa
            if repr_ == "packed":
                al = 1
            off = (off + al - 1) // al * al
            fields.append((fm.group(1), off, off + sz))
            off += sz
            maxal = max(maxal, al)
        size = (off + maxal - 1) // maxal * maxal
        LAYOUTS[(crate, name)] = {"repr": repr_, "fields": fields, "size": size, "align": maxal} if fields else None
        return LAYOUTS[(crate, name)]
    for crate, name in raw:
        layout_of(crate, name)


def _stem(name):
    s = re.sub(r"(_account|_acct|_acc|_info|_data|_state|_pda|_view)$", "", name.lower())
    return s.replace("_", "")


def offset_mismatch(crate, acct, a, e):
    """Describe the struct the byte range [a, e) misses, or '' when it lines up
    (or no layout can be matched to the account)."""
    lays = {n: l for (c, n), l in LAYOUTS.items() if c == crate and l}
    if not lays:
        return ""
    named = [n for n in lays if n.lower() == _stem(acct)]
    if named:
        cands = named
    elif len(lays) == 1:
        cands = list(lays)
    else:
        return ""    # cannot tell which struct this account holds
    for n in cands:
        l = lays[n]
        starts = {f[1] for f in l["fields"]}
        ends = {f[2] for f in l["fields"]}
        if a in starts and (e in ends or (e == a + 1 and any(f[1] == a for f in l["fields"]))) and e <= l["size"]:
            return ""
    l = lays[cands[0]]
    return "`%s` (#[repr(%s)], %d bytes: %s)" % (cands[0], l["repr"], l["size"], ", ".join("%s@%d..%d" % f for f in l["fields"][:8]))


# --------------------------------------------------------------------------
# Red flags
# --------------------------------------------------------------------------

def seeds_have_user(seeds, fields, extra_user=()):
    if not seeds:
        return True
    seeds = re.sub(r'b?r?(#*)"(?:[^"\\]|\\.)*"\1', " ", seeds)    # a literal `b"user"` is not a user key
    for mt in re.finditer(r"\b(\w+)\b", seeds):
        w = mt.group(1)
        f = fields.get(w)
        if f is not None and f.is_signer:
            return True
        if w in extra_user:
            return True
        if w[:1].isupper() or w in ("from", "as_ref", "key", "to_le_bytes", "to_bytes"):
            continue    # type / constructor names (`Signer::from`, `Seed`) are not seed values
        if USER_NAME.search(w):
            return True
    return False


SEED_NOISE = {"from", "as_ref", "as_slice", "as_bytes", "to_le_bytes", "to_be_bytes", "to_bytes", "to_vec", "key",
              "mut", "ref", "ctx", "accounts", "self", "crate", "address", "as_array", "to_account_info", "u8"}


def seed_kind(seeds, fields):
    """'const' when every seed value is a literal / CONSTANT / stored bump (one
    address for the whole program), 'parent' when the only non-constant values
    are the key or a stored field of another seeds- or address-validated account
    (one per parent), else 'var'."""
    s = re.sub(r'b?r?(#*)"(?:[^"\\]|\\.)*"\1', " ", seeds)
    s = re.sub(r"\b(?:[a-z_]\w*\s*::\s*)*id\s*\(\s*\)", " ID ", s)            # crate::id() / program id()
    s = re.sub(r"\b[a-z_]\w*\s*::\s*", "", s)                          # lowercase path prefixes
    s = re.sub(r"\b(?:ctx\s*\.\s*accounts|self)\s*\.\s*", "", s)
    kind = "const"
    for mt in re.finditer(r"(?<![\w.])[A-Za-z_]\w*(?:\s*\.\s*[A-Za-z_]\w*)*", s):
        segs = [x for x in re.split(r"\s*\.\s*", mt.group(0)) if x not in SEED_NOISE]
        if not segs:
            continue
        head = segs[0]
        if head[:1].isupper():
            continue                                    # CONSTANT, Type::from, crate::ID
        if re.search(r"bump|nonce", segs[-1]) or head == "bumps":
            continue                                    # bump byte: not an identity
        f = fields.get(head)
        if f is not None and (f.seeds() or f.val("address")):
            kind = "parent"     # `config.key()` or a stored field of a validated `config`
            continue
        return "var"
    return kind


def st_has_one(fields):
    return [v for f in fields.values() for v in f.val("has_one")]


def in_code_checks(inst, fields):
    """Which raw accounts the handler checks by hand: {name: set('signer','owner','key')}."""
    body_all = "\n".join(b.m for b in inst["bodies"])
    out = {}
    for name in fields:
        n = re.escape(name)
        got = set()
        # a `let token = Type::unpack(..)` shadows the account: then only
        # `ctx.accounts.token.owner` / `self.token.owner` name the account itself
        if re.search(r"\blet\s+(?:mut\s+)?%s\s*(?::[^=]+)?=" % n, body_all):
            n = r"(?:ctx\.accounts\.|self\.)" + n
        if re.search(r"\b%s\s*\.\s*is_signer\b" % n, body_all):
            got.add("signer")
        if re.search(r"\b%s\s*(?:\.\s*to_account_info\s*\(\s*\))?\s*\.\s*owner\b(?!\s*=[^=])" % n, body_all) or \
           re.search(r"(owned_by|is_owned_by|check_owner|assert_owner\w*)\s*\([^;]*\b%s\b" % n, body_all):
            got.add("owner")
        if re.search(r"\b%s\s*\.\s*(key|address)\s*(\(\s*\))?\s*(!=|==)" % n, body_all) or \
           re.search(r"(!=|==)\s*&?\*?\s*(ctx\.accounts\.)?%s\s*\.\s*(key|address)\b" % n, body_all) or \
           re.search(r"require_keys_(eq|neq)\s*!\s*\([^;]*\b%s\b" % n, body_all) or \
           re.search(r"require_eq\s*!\s*\([^;]*\b%s\s*\.\s*key\b" % n, body_all):
            got.add("key")
        if got:
            out[name] = got
    return out


EXIT_NAME = re.compile(r"^(?:withdraw|redeem|unwrap|unstake|claim|close|exit|repay|liquidat\w*|settle|refund|cancel|unlock|release|remove_liquidity|burn)(?:_|$)", re.I)
LOCAL_ROOTS = {"crate", "self", "super", "std", "core", "anchor_lang", "anchor_spl", "solana_program", "solana_sdk", "pinocchio",
               "spl_token", "spl_token_2022", "spl_token_interface", "spl_associated_token_account", "mpl_token_metadata"}
LOCAL_IDS = re.compile(r"^(?:crate\s*::\s*)?(?:ID|id\s*\(\s*\)|program_id|__private::\w+)$|token|system_program|associated", re.I)


_DEPS = {}


def crate_deps(path):
    """Dependency crate names (`-` -> `_`) from the nearest Cargo.toml, or None."""
    d = os.path.dirname(os.path.abspath(path))
    while True:
        m = os.path.join(d, "Cargo.toml")
        if os.path.isfile(m):
            if m not in _DEPS:
                names, sec = set(), ""
                try:
                    with open(m, encoding="utf-8", errors="replace") as fh:
                        lines = fh.read().splitlines()
                    for line in lines:
                        line = line.split("#", 1)[0].strip()
                        hm = re.match(r"^\[(.*)\]$", line)
                        if hm:
                            sec = hm.group(1).strip()
                            dm = re.match(r"^(?:target\..*\.)?(?:dev-|build-)?dependencies\.([\w-]+)$", sec)
                            if dm:
                                names.add(dm.group(1).replace("-", "_"))
                            continue
                        if re.match(r"^(?:target\..*\.)?(?:dev-|build-)?dependencies$", sec):
                            km = re.match(r'^"?([\w-]+)"?\s*(?:=|\.)', line)
                            if km:
                                names.add(km.group(1).replace("-", "_"))
                                pm = re.search(r'package\s*=\s*"([\w-]+)"', line)
                                if pm:
                                    names.add(pm.group(1).replace("-", "_"))
                except OSError:
                    pass
                _DEPS[m] = names
            return _DEPS[m]
        nd = os.path.dirname(d)
        if nd == d:
            return None
        d = nd


def foreign_owner(f, src):
    """The crate (or program-ID expression) that owns an account field, when it
    is plainly another program: `Account<'info, other::T>` / `InterfaceAccount`,
    a type imported with `use other::...::T` (or a single `use other::...::*`),
    `owner = other::ID`, or `constraint = x.owner == other::ID`. A path root
    counts as another crate only when the nearest Cargo.toml lists it as a
    dependency (without a manifest: when no `mod root` is declared in the file).
    A `seeds::program` PDA is usually passed straight through to that program's
    CPI and is not raised. Token/Mint types and the program's own crate are
    never foreign."""
    if f.val("seeds::program"):
        return ""
    for v in f.val("owner"):
        v = re.sub(r"\s+", "", v)
        if v and not LOCAL_IDS.search(v):
            return v
    for v in f.val("constraint"):
        # a program ID only (`other::ID`, `other::id()`, `OTHER_PROGRAM_ID`) — a token
        # account's `.owner == user.key()` is a wallet check, not a foreign owner
        cm = re.search(r"\.\s*owner\s*(?:\(\s*\))?\s*==\s*&?\s*\*?\s*((?:\w+\s*::\s*)+(?:ID|id\s*\(\s*\))|[A-Z][A-Z0-9_]*PROGRAM_ID)\b", v)
        if cm and not LOCAL_IDS.search(re.sub(r"\s+", "", cm.group(1))):
            return re.sub(r"\s+", "", cm.group(1))
    if f.kind not in ("Account", "AccountLoader", "LazyAccount", "InterfaceAccount"):
        return ""
    inner = re.sub(r"\s+", "", f.inner)
    name = inner.split("::")[-1]
    if re.search(r"(TokenAccount|Mint)$", name):
        return ""
    deps = crate_deps(src.path)
    if "::" in inner:
        root = inner.split("::")[0]
    else:
        mt = re.search(r"\buse\s+(?:::)?(\w+)\s*::[^;]*\b%s\b[^;]*;" % re.escape(name), src.m)
        root = mt.group(1) if mt else ""
        if not root:
            globs = {g.group(1) for g in re.finditer(r"\buse\s+(?:::)?(\w+)\s*::[\w:\s]*::\s*\*\s*;", src.m)}
            globs = {g for g in globs if g not in LOCAL_ROOTS and (deps is None or g in deps)}
            root = globs.pop() if len(globs) == 1 else ""
    own = (getattr(src, "crate", "") or "").replace("-", "_")
    if not root or root in LOCAL_ROOTS or root == own:
        return ""
    if deps is not None:
        return root if root in deps else ""
    return "" if re.search(r"\bmod\s+%s\b" % re.escape(root), src.m) else root

def anchor_flags(inst, st, res):
    fl = []
    fields = {f.name: f for f in st["fields"]}
    key = "%s::%s" % (inst["program"], inst["name"])
    hand = in_code_checks(inst, fields)
    signs = lambda f: f.is_signer or "signer" in hand.get(f.name, ())
    has_signer = any(signs(f) for f in fields.values())
    state_change = bool(res["writes"] or res["cpis"] or res["lamports"] or any(f.is_mut for f in fields.values()))
    if not has_signer and state_change:
        fl.append((key, "no-signer", "state-changing instruction with no `Signer` account and no `signer` constraint — anyone can call it with any accounts", inst))
    for f in fields.values():
        relied_on = any(v.split("@")[0].strip() == f.name for v in st_has_one(fields)) or \
            re.search(r"\b%s\s*\.\s*key\b[^;{]*(==|!=)|(==|!=)[^;{]*\b%s\s*\.\s*key\b" % (f.name, f.name), "\n".join(b.m for b in inst["bodies"])) or \
            any(re.search(r"\b%s\b" % f.name, v) for g in fields.values() for v in g.val("constraint"))
        if AUTH_NAME.search(f.name) and not signs(f) and f.kind in RAW_TYPES + ("SystemAccount",) and (relied_on or not has_signer):
            fl.append((key, "authority-not-signer", "`%s` (%s) is named like an authority and %s, but nothing makes it sign" % (f.name, f.type_desc(), "a check relies on its key" if relied_on else "the instruction has no signer at all"), inst))
        if f.is_raw and not (f.val("address") or f.val("owner") or f.val("seeds") or f.val("constraint") or "init" in f.keys or "zero" in f.keys):
            by_hand = hand.get(f.name, set())
            if by_hand:
                fl.append((key, "raw-checked-in-code", "`%s: %s` has no constraint; the handler checks its %s by hand — confirm every instruction that takes it does the same" % (f.name, f.kind, " and ".join(sorted(by_hand))), inst))
            elif not f.has_check_doc:
                fl.append((key, "unchecked-account", "`%s: %s` has no `/// CHECK` comment and no owner/address/seeds/constraint" % (f.name, f.kind), inst))
            elif DEFER_CHECK.search(f.check_doc or ""):
                fl.append((key, "check-deferred", "`%s: %s` has a `/// CHECK` that defers validation to another program/CPI (\"%s\") — confirm that program actually checks it on THIS path; a sibling path (e.g. deposit) validating it does not mean this one (e.g. withdraw) does" % (f.name, f.kind, squash(f.check_doc, 70)), inst))
            else:
                fl.append((key, "check-comment-only", "`%s: %s` relies on its `/// CHECK` comment alone (\"%s\") — verify the claim holds in code" % (f.name, f.kind, squash(f.check_doc, 70)), inst))
        if f.is_raw and SYSVAR_NAME.match(f.name) and not f.val("address") and "key" not in hand.get(f.name, ()):
            fl.append((key, "sysvar-unchecked", "`%s` looks like a sysvar but is a raw `%s` with no `address = ` — use `Sysvar<'info, T>` or pin the ID" % (f.name, f.kind), inst))
        sd = f.seeds()
        if sd and (f.is_mut) and not seeds_have_user(sd, fields):
            sk = seed_kind(sd, fields)
            if sk == "var":
                fl.append((key, "pda-no-user-key", "`%s` is a writable PDA whose seeds `%s` name no signer or user key — fine for a global singleton, a bug when it holds per-user state" % (f.name, squash(sd, 60)), inst))
            elif sk == "const" and not f.val("seeds::program"):
                # folded per program in fold_singletons(); a foreign PDA (seeds::program)
                # or a child keyed only by a validated parent is not raised
                fl.append((key, "_singleton", {"field": f.name, "seeds": sd, "init": bool(f.keys & {"init", "init_if_needed"})}, inst))
        bump = [v for v in f.val("bump") if v]
        if bump and (bump[0] in st["ix_args"] or bump[0] in inst["args"]):
            fl.append((key, "user-bump", "`%s` takes `bump = %s` from instruction data — a non-canonical bump gives a second valid address" % (f.name, bump[0]), inst))
        for dest in [re.sub(r"\s+", "", v) for v in f.val("close") if v]:
            t = fields.get(dest)
            # an undocumented raw destination is already `unchecked-account`, and an
            # instruction with no signer is already `no-signer`: raise only the case those miss
            if t is not None and t.is_raw and t.has_check_doc and has_signer and not (t.val("address") or t.val("seeds") or t.val("constraint") or t.val("owner")) \
                    and dest not in [v.split("@")[0].strip() for v in st_has_one(fields)] and "key" not in hand.get(dest, ()) \
                    and not any(re.search(r"\b%s\b" % re.escape(dest), v) for g in fields.values() for v in g.val("constraint")):
                fl.append((key, "close-to-unchecked", "`%s` is closed to `%s` (%s), which has no address / seeds / has_one / constraint — the caller picks who receives every lamport; a drain when the closed account holds more than its own rent (escrow, SOL vault, rent someone else paid)" % (f.name, dest, t.kind), inst))
        if "init_if_needed" in f.keys:
            fl.append((key, "init-if-needed", "`%s` uses `init_if_needed` — check that a second call cannot reset state on an existing account" % f.name, inst))
    if EXIT_NAME.search(inst["name"]):
        for f in fields.values():
            if f.keys & {"init", "init_if_needed"}:
                continue
            who = foreign_owner(f, st["src"])
            if who:
                fl.append((key, "foreign-dependency", "exit path requires `%s` (%s), an account owned by another program (`%s`) — if that program or its admin closes, migrates or re-keys it, this instruction fails for every caller (Anchor: the account no longer loads); check for a fallback, and whether that party can also decide who may exit" % (f.name, f.type_desc(), squash(who, 40)), inst))
    muts = {}
    for f in fields.values():
        written = any(w == f.name or w.startswith(f.name + ".") or w.endswith(" " + f.name) for w in res["writes"])
        if (f.is_mut or written) and f.kind in ("Account", "AccountLoader", "InterfaceAccount") and not (f.keys & {"init", "init_if_needed"}) and not f.seeds():
            pin = tuple(sorted((k.split("::")[-1], v) for k, v in f.items if k.split("::")[-1] in ("mint", "authority") and "::" in k))
            muts.setdefault((f.inner, pin), []).append(f.name)
    allc = " ".join(v for f in fields.values() for v in f.val("constraint")) + " " + " ".join(res["gates"])
    for (ty, _pin), names in muts.items():
        if len(names) > 1:
            pair = names[:2]
            if not re.search(r"%s[^,;]*(!=|==)[^,;]*%s|%s[^,;]*(!=|==)[^,;]*%s" % (pair[0], pair[1], pair[1], pair[0]), allc):
                fl.append((key, "duplicate-mutable", "`%s` are all mutable (or written) `%s` with no constraint that their keys differ — the same account can be passed twice" % ("`, `".join(names), ty.split("::")[-1]), inst))
    common_flags(fl, key, inst, res, fields)
    for acct, op, val, loc in res["lamports"]:
        f = fields.get(acct)
        if f is not None and "close" not in f.keys and op in ("=", "set_lamports") and val.strip() == "0" and f.kind in ("Account", "AccountLoader"):
            if any(a == acct for a, _l in res["rawwrite"]):
                fl.append((key, "manual-close", "`%s` is drained by hand and its data is rewritten in code (%s) — confirm the closed marker is checked by every instruction that accepts the account, and that it cannot be re-funded and reused in the same transaction" % (acct, loc), inst))
                continue
            fl.append((key, "manual-close", "`%s` is drained by hand (lamports set to 0) without `close = …` — data and discriminator stay; the account can be revived in the same transaction (%s)" % (acct, loc), inst))
    for acct, attr, loc in res["reads_after_cpi"]:
        if acct not in res["reloads"]:
            fl.append((key, "stale-after-cpi", "`%s.%s` is read after a CPI with no `.reload()` — Anchor does not refresh deserialized accounts (%s)" % (acct, attr, loc), inst))
    return fl


def common_flags(fl, key, inst, res, fields, native_names=()):
    for c in res["cpis"]:
        if c["ok"] is False:
            fl.append((key, "arbitrary-cpi", "%s calls program %s (%s)" % (c["how"], c["prog"], c["loc"]), inst))
        if c["seeds"]:
            if not seeds_have_user(c["seeds"], fields) and seed_kind(c["seeds"], fields) in ("const", "parent"):
                fl.append((key, "_global-signer", {"seeds": c["seeds"], "loc": c["loc"], "kind": seed_kind(c["seeds"], fields)}, inst))
            elif not seeds_have_user(c["seeds"], fields):
                fl.append((key, "signer-seeds-no-user-key", "CPI signs with seeds `%s` that name no signer or user key — any two callers that share these seed values share the authority (%s)" % (squash(c["seeds"], 70), c["loc"]), inst))
        if c["seeds"] and re.search(r"\b(bump|nonce)\b", c["seeds"]) and not re.search(r"\.\s*(bump|nonce)\w*\b|bumps\s*\.", c["seeds"]):
            m_all = "\n".join(b.m for b in inst["bodies"])
            if re.search(r"\blet\s+(?:mut\s+)?(bump|nonce)\s*(?::[^=]+)?=\s*[^;]*\b(data|ix_data|instruction_data|args|params)\b", m_all) or \
               re.search(r"\b(bump|nonce)\s*:\s*u8\b", "\n".join(b.src.text[max(0, b.start - 400):b.start] for b in inst["bodies"][:1])):
                fl.append((key, "user-bump", "CPI signer seeds `%s` use a bump taken from instruction data, not a stored or derived bump (%s)" % (squash(c["seeds"], 70), c["loc"]), inst))
    if res["remaining"]:
        checks = re.findall(r"\b(owner|is_signer|key\s*\(\s*\)\s*[!=]=|Account\s*::\s*try_from|try_from|find_program_address|create_program_address|address\s*\(\s*\)\s*[!=]=)", "\n".join(b.m for b in inst["bodies"]))
        if not checks:
            fl.append((key, "remaining-accounts", "`remaining_accounts` is used (%s) and no owner/key/type check appears in the handler" % res["remaining"][0], inst))
        else:
            fl.append((key, "remaining-accounts", "`remaining_accounts` is used (%s); checks seen: %s — verify every element is covered" % (res["remaining"][0], ", ".join(sorted(set(re.sub(r"\s+", "", x) for x in checks)))), inst))
    for d in res["derive"]:
        if d["fn"] == "create_program_address" and re.search(r"\b(bump|nonce)\b", d["seeds"]) and not re.search(r"\.\s*(bump|nonce)\b", d["seeds"]):
            fl.append((key, "user-bump", "`create_program_address` with seeds `%s` takes a bump that is not a stored field — a caller-chosen bump gives a second valid address (%s)" % (squash(d["seeds"], 60), d["loc"]), inst))
    for acct, ty, how, loc in res["deser"]:
        f = fields.get(acct)
        if f is not None and f.is_raw and not (f.val("owner") or f.val("address")):
            body_all = "\n".join(b.m for b in inst["bodies"])
            a = re.escape(acct)
            shadowed = re.search(r"\blet\s+(?:mut\s+)?%s\s*(?::[^=]+)?=\s*[A-Z]\w*\s*::" % a, body_all)
            pat = (r"(ctx\.accounts\.|self\.)%s\s*\.\s*(to_account_info\s*\(\s*\)\s*\.\s*)?owner\b" % a) if shadowed else (r"\b%s\s*\.\s*owner\b" % a)
            if not re.search(pat, body_all):
                fl.append((key, "raw-deserialize", "`%s` is a raw account decoded by hand as `%s::%s` with no owner check — a look-alike account from another program decodes the same (%s)" % (acct, ty, how, loc), inst))
    body_all = "\n".join(b.m for b in inst["bodies"])
    for acct, ty, how, loc in res["deser"]:
        f = fields.get(acct)
        raw = (f is not None and f.is_raw) or (f is None and acct in native_names)
        if raw and how in ("try_from_slice", "deserialize", "unpack_unchecked", "from_bytes", "try_from_bytes", "load_unchecked", "try_deserialize_unchecked") and \
           not re.search(r"discrimin|DISCRIMINATOR|account_type|AccountType|\bkind\b|\btag\b|\bkey\s*!=\s*\w+::|Key::", body_all):
            fl.append((key, "type-cosplay", "`%s` is decoded as `%s` by `%s` with no discriminator or type-tag check — another account type with the same layout passes (%s)" % (acct, ty, how, loc), inst))
    if native_names:
        seen_off = set()
        for acct, var, a, e, loc in res["slices"]:
            hit = offset_mismatch(inst["src"].crate, acct, a, e)
            if hit and (acct, a, e) not in seen_off:
                seen_off.add((acct, a, e))
                fl.append((key, "offset-mismatch", "`%s[%s]` (data of `%s`) does not line up with %s — a hand offset that misses the layout reads the wrong bytes: check whether a check built on it can never pass (the instruction always fails) or compares attacker-chosen bytes (%s)" % (var, ("%d" % a) if e == a + 1 else ("%d..%d" % (a, e)), acct, hit, loc), inst))
    if res["rawwrite"] and not res["init_checks"] and re.search(r"init|create|setup|register|open|^new", inst["name"], re.I):
        for acct, loc in res["rawwrite"][:1]:
            f = fields.get(acct)
            if f is None or f.is_raw:
                fl.append((key, "reinit", "raw data of `%s` is written with no is-initialized / discriminator check in the handler — a second call may overwrite live state (%s)" % (acct, loc), inst))


def partner_is_stored(expr, h, rows):
    """True when the other side of a key comparison reads account data: a slice /
    field / getter of state, or a `let` bound to one — not a constant, a program
    ID, another account's key, or a derived address."""
    e = re.sub(r"^[&*\s]+|\s+$", "", expr)
    if not e or re.search(r"(^|::)[A-Z][A-Z0-9_]+\b|::ID\b|\bid\s*\(\s*\)|program_id|crate::", e):
        return False
    acct_names = {r["name"] for r in rows}
    head = re.match(r"(\w+)", e)
    if head and head.group(1) in acct_names and re.search(r"^\w+\s*\.\s*(key|address)\b", e):
        return False
    m = h["bodies"][0].m
    if re.match(r"^\w+$", e):
        let = resolve_let(h["bodies"][0], e, len(m))
        if not let or re.search(r"find_program_address|create_program_address|derive_address|get_associated_token_address|\.\s*(key|address)\s*\(", let):
            return False
        return bool(re.search(r"\[|\.\s*\w+\s*\(\s*\)|\.\s*[a-z_]\w*\b", let))
    return bool(re.search(r"\[|\.\s*[a-z_]\w*", e))


def native_flags(h, rows, res):
    fl = []
    key = "%s::%s" % (h["program"], h["name"])
    names = [r["name"] for r in rows]
    state_change = bool(res["writes"] or res["cpis"] or res["lamports"])
    if state_change and not res["any_is_signer"] and not h.get("delegates") and \
       not any(r["signer"].startswith("checked") for r in rows) and not any_signer_check("\n".join(b.m for b in h["bodies"])):
        fl.append((key, "no-signer", "handler changes state and checks `is_signer` on no account", h))
    for r in rows:
        if AUTH_NAME.search(r["name"]) and r["signer"] == "—" and r["used"] and r["key"] != "—" and not r["seeds"]:
            fl.append((key, "authority-not-signer", "`%s` is named like an authority and its key is compared, but `is_signer` is never checked on it here — anyone can pass the right key without the signature" % r["name"], h))
        # An owner check found only inside a helper keeps the decode lead, re-worded: the
        # helper proves the account is this program's, not WHICH one of its accounts it is,
        # and a substituted read-only config is the classic shape. A written account with a
        # helper owner check is treated like a direct owner check (no write-unbound).
        via = r.get("owner_via")
        if r["type"] not in ("?", "unused", "") and (r["owner"] == "—" or via) and r["key"] == "—":
            if via:
                fl.append((key, "raw-deserialize", "`%s` is decoded as `%s`; its owner is checked in `%s`, but no key or PDA check binds it — another account of the same type passes" % (r["name"], r["type"], via[0]), h))
            else:
                fl.append((key, "raw-deserialize", "`%s` is decoded as `%s` with no owner check and no key check — a look-alike account decodes the same" % (r["name"], r["type"]), h))
        if r["written"] and r["owner"] == "—" and r["key"] == "—" and not r["seeds"] and r["name"] not in ("payer", "fee_payer"):
            fl.append((key, "write-unbound", "`%s` is written with no owner, key or PDA check — the runtime only blocks writes to accounts this program does not own, so any account it does own (another user's, another type) can be passed here" % r["name"], h))
        if r["signer"] == "—" and r["used"] and not r["seeds"] and not AUTH_NAME.search(r["name"]) and \
           not r["name"].endswith("_program") and not SYSVAR_NAME.match(r["name"]):
            data_partners = [x for x in r.get("partners", []) if partner_is_stored(x, h, rows)]
            if data_partners:
                fl.append((key, "key-compared-no-signer", "`%s`'s key is compared against stored data (`%s`), but `is_signer` is never checked on it here — if that comparison is what authorizes the caller, anyone who passes the stored key passes the check" % (r["name"], squash(data_partners[0], 50)), h))
        if SYSVAR_NAME.match(r["name"]) and r["key"] == "—" and r["used"] and r["type"] in ("?", ""):
            fl.append((key, "sysvar-unchecked", "`%s` looks like a sysvar; no address check is visible — `Sysvar::from_account_info` checks it, a hand decode does not" % r["name"], h))
    fake_fields = {}
    common_flags(fl, key, h, res, fake_fields, tuple(names))
    return fl


def fold_singletons(flags):
    """Replace per-instruction `_singleton` / `_global-signer` markers with one
    lead per (program, seeds)."""
    out, groups = [], {}
    for f in flags:
        if f[1] in ("_singleton", "_global-signer"):
            prog = f[0].split("::", 1)[0]
            groups.setdefault((f[1], prog, re.sub(r"\s+", "", f[2]["seeds"])), []).append(f)
        else:
            out.append(f)
    for (typ, prog, _sd), items in groups.items():
        items = sorted(items, key=lambda x: x[0])
        insts = list(dict.fromkeys(k.split("::", 1)[1] for k, _t, _p, _i in items))
        sd = squash(items[0][2]["seeds"], 60)
        if typ == "_global-signer":
            out.append((items[0][0], "global-signer", "CPIs sign as %s (seeds `%s`) at %d site(s) in %d instruction(s): %s — every caller who reaches one of these CPIs acts with that PDA's authority; confirm each path is gated and every account it passes is pinned" % (
                "a program-wide PDA" if items[0][2].get("kind") == "const" else "a PDA keyed only by a validated parent account", sd, len(items), len(insts), ", ".join("`%s` (%s)" % (k.split("::", 1)[1], p["loc"]) for k, _t, p, _i in items[:6]) + (" …" if len(items) > 6 else ""), ), items[0][3]))
            continue
        field = items[0][2]["field"]
        inits = [it for it in items if it[2]["init"]]
        for it in inits:
            name = it[0].split("::", 1)[1]
            others = [i for i in insts if i != name]
            out.append((it[0], "singleton-init", "`%s` (seeds `%s`) is a global singleton created here — check who may call this first (front-run / first-caller-wins) and that it never holds per-user state%s" % (
                it[2]["field"], sd, ("; also written by " + ", ".join("`%s`" % o for o in others[:8]) + (" …" if len(others) > 8 else "")) if others else ""), it[3]))
        if not inits:
            out.append((items[0][0], "singleton-write", "`%s` (seeds `%s`) is a global singleton written by %d instruction(s) (%s) and created outside the scanned files — confirm it never holds per-user state" % (
                field, sd, len(insts), ", ".join("`%s`" % i for i in insts[:8]) + (" …" if len(insts) > 8 else "")), items[0][3]))
    return out


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def render(srcs, entries, flags, dispatchers, needs):
    n_anchor = sum(1 for e in entries if e["framework"] == "Anchor")
    out = []
    out.append("# Account map — leads, not findings\n")
    out.append("Generated by `account-map.py` from %d in-scope file(s): %d Anchor instruction(s), %d native/Pinocchio handler(s). "
               "Every line below is a **lead**: a place to look, produced by pattern matching. It is never a finding by itself — "
               "confirm each one in the source, and do not report anything this map says without your own path to it. "
               "`?` = the script could not settle the cell; `—` = no such check was seen in the handler (a helper it calls may still do it).\n"
               % (len(srcs), n_anchor, len(entries) - n_anchor))
    out.append("## Review leads (%d)\n" % len(flags))
    if not flags:
        out.append("_None raised by the script. That is not a clean bill: the script cannot see logic bugs._\n")
    else:
        order = ["no-signer", "authority-not-signer", "key-compared-no-signer", "arbitrary-cpi", "check-deferred", "unchecked-account", "raw-deserialize", "write-unbound", "sysvar-unchecked",
                 "offset-mismatch", "user-bump", "pda-no-user-key", "signer-seeds-no-user-key", "singleton-init", "global-signer", "duplicate-mutable", "manual-close", "close-to-unchecked", "reinit",
                 "init-if-needed", "type-cosplay", "remaining-accounts", "stale-after-cpi", "foreign-dependency", "check-comment-only", "raw-checked-in-code", "singleton-write"]
        flags = sorted(flags, key=lambda x: (order.index(x[1]) if x[1] in order else 99, x[0]))
        out.append("| # | Where | Flag | Detail |\n| --- | --- | --- | --- |")
        for i, (k, tag, msg, inst) in enumerate(flags, 1):
            out.append("| %d | `%s` | %s | %s |" % (i, k, tag, cell(msg, 320)))
        out.append("")
    if needs:
        out.append("## Needs completion (%d)\n" % len(needs))
        out.append("The script could not resolve these handlers' accounts. Read the handler (and the helpers it passes accounts to) and fill the `?` cells before relying on the entry.\n")
        for k, why in needs:
            out.append("- `%s` — %s" % (k, why))
        out.append("")
    if dispatchers:
        out.append("## Dispatchers\n")
        for d in dispatchers:
            out.append("- `%s::%s` (`%s`) → %s" % (d["program"], d["name"], d["src"].loc(d["idx"]), ", ".join("`%s`" % c for c in dict.fromkeys(d["calls"]))))
        out.append("")
    out.append("## Instructions\n")
    for e in entries:
        out.extend(e["md"])
    return "\n".join(out).rstrip() + "\n"


def render_anchor(inst, st, res):
    md = []
    key = "%s::%s" % (inst["program"], inst["name"])
    md.append("### `%s` — Anchor, accounts `%s` (`%s`)\n" % (key, inst["struct"], inst["src"].loc(inst["idx"])))
    if st is None:
        md.append("_Accounts struct `%s` not found in scope — read it before trusting anything below._\n" % inst["struct"])
        fields = []
    else:
        fields = st["fields"]
        if st["ix_args"]:
            md.append("`#[instruction(%s)]`\n" % ", ".join(st["ix_args"]))
        hand = in_code_checks(inst, {f.name: f for f in fields})
        md.append("| Account | Type | Signer | Mut | Owner | PDA seeds · bump | Init / close | Constraints |")
        md.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for f in fields:
            ic = []
            for k in ("init", "init_if_needed", "zero"):
                if k in f.keys:
                    ic.append(k + (" payer=" + f.val("payer")[0] if f.val("payer") else ""))
            if f.val("close"):
                ic.append("close → " + f.val("close")[0])
            if f.val("realloc"):
                ic.append("realloc")
            pda = ""
            if f.seeds():
                pda = squash(f.seeds(), 60) + " · " + (f.bump_desc() or "no bump")
                sp = f.val("seeds::program")
                if sp:
                    pda += " · program " + sp[0]
            cons = f.constraints()
            if f.is_raw:
                cons = cons + ["CHECK: " + squash(f.check_doc, 60) if f.has_check_doc else "no /// CHECK"]
            md.append("| `%s` | %s | %s | %s | %s | %s | %s | %s |" % (
                f.name, cell(f.type_desc()),
                "yes" if f.is_signer else ("checked in code" if "signer" in hand.get(f.name, ()) else "—"),
                "mut" if f.is_mut else "—",
                cell(f.owner_desc() + (" · owner checked in code" if f.owner_desc() == "NOT CHECKED" and "owner" in hand.get(f.name, ()) else "")
                     + (" · key checked in code" if f.is_raw and "key" in hand.get(f.name, ()) else "")),
                cell(pda), cell("; ".join(ic)), cell("; ".join(cons))))
        md.append("")
    render_common(md, res)
    return md


def render_native(h, rows, res, unresolved):
    md = []
    key = "%s::%s" % (h["program"], h["name"])
    md.append("### `%s` — %s handler (`%s`)\n" % (key, h["framework"], h["src"].loc(h["idx"])))
    if h.get("via"):
        md.append("Accounts validated in %s (merged below).\n" % ", ".join("`%s` (`%s`)" % (v, b.loc(0)) for v, b in zip(h["via"], h["bodies"][1:])))
    if not rows:
        md.append("_Accounts: `?` — this handler does not unpack accounts itself%s. Needs completion._\n" % (
            (" (passes them to %s)" % ", ".join("`%s`" % d for d in dict.fromkeys(h["delegates"]))) if h.get("delegates") else ""))
    else:
        md.append("| Account | Unpacked by | Signer | Mut / written | Owner | Key check | Decoded as | PDA seeds · bump |")
        md.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for r in rows:
            pda = (squash(r["seeds"], 60) + " · " + r["bump"]) if r["seeds"] else ""
            md.append("| `%s` | %s | %s | %s | %s | %s | %s | %s |" % (
                r["name"], cell(r["how"]), cell(r["signer"]), cell(r["mut"]), cell(r["owner"]), cell(r["key"]), cell(r["type"]), cell(pda)))
        md.append("")
    render_common(md, res)
    return md


def render_common(md, res):
    if res["cpis"]:
        md.append("**CPIs**")
        for c in res["cpis"]:
            md.append("- %s → program %s%s · `%s`" % (squash(c["how"], 80), c["prog"],
                      (" · signer seeds `%s`" % squash(c["seeds"], 80)) if c["seeds"] else "", c["loc"]))
    else:
        md.append("**CPIs** — none")
    md.append("")
    md.append("**State written** — " + (", ".join("`%s`" % w for w in res["writes"][:25]) if res["writes"] else "none seen") + "\n")
    gates = list(dict.fromkeys(res["gates"]))
    md.append("**Gating in code** — " + ("; ".join("`%s`" % g.replace("`", "'") for g in gates[:10]) + (" …(+%d)" % (len(gates) - 10) if len(gates) > 10 else "") if gates else "none seen") + "\n")
    if res["remaining"]:
        md.append("**remaining_accounts** — used at %s\n" % ", ".join("`%s`" % r for r in res["remaining"][:3]))
    md.append("")


def main(argv):
    out_path, files = None, []
    i = 0
    while i < len(argv):
        if argv[i] == "--out":
            if i + 1 >= len(argv):
                print("account-map.py: --out needs a path", file=sys.stderr); return 2
            out_path = argv[i + 1]; i += 2
        elif argv[i] in ("-h", "--help"):
            print(__doc__); return 0
        else:
            files.append(argv[i]); i += 1
    if not files and not sys.stdin.isatty():
        files = [l.strip() for l in sys.stdin if l.strip()]
    missing = [f for f in files if f.endswith(".rs") and not os.path.isfile(f)]
    if missing:
        print("account-map.py: skipped %d missing file(s): %s" % (len(missing), ", ".join(missing[:5])), file=sys.stderr)
    files = [f for f in files if f.endswith(".rs") and os.path.isfile(f)]
    srcs = [Src(f) for f in files]
    for s_ in srcs:
        LOCAL_FNS.update(mt.group(1) for mt in FN_RE.finditer(s_.m))
    collect_helpers(srcs)
    collect_account_impls(srcs)
    collect_layouts(srcs)
    structs = {}
    for s in srcs:
        structs.update(parse_accounts_structs(s))
    entries, flags, needs = [], [], []
    for inst in anchor_instructions(srcs, structs):
        st = find_struct(structs, inst["src"], inst["struct"])
        fields = {f.name: f for f in st["fields"]} if st else {}
        res = analyse_body(inst["bodies"], fields)
        md = render_anchor(inst, st, res)
        if st:
            flags.extend(anchor_flags(inst, st, res))
        else:
            needs.append(("%s::%s" % (inst["program"], inst["name"]), "Accounts struct `%s` is outside the scanned files" % inst["struct"]))
        entries.append({"framework": "Anchor", "md": md})
    dispatchers = []
    for h in native_handlers(srcs, {k[2] for k in structs}):
        if h["dispatcher"]:
            dispatchers.append(h); continue
        names = [a.name for a in h["accts"]]
        res = analyse_body(h["bodies"], {}, names)
        rows, unresolved = native_account_rows(h, res)
        key = "%s::%s" % (h["program"], h["name"])
        if not rows:
            needs.append((key, "accounts are not unpacked in this function"))
        elif unresolved:
            needs.append((key, "owner/signer of %s decided in a helper" % ", ".join("`%s`" % u for u in unresolved)))
        if any(r["how"].startswith("accounts[") for r in rows):
            needs.append((key, "accounts read by index — confirm the index → role mapping"))
        flags.extend(native_flags(h, rows, res))
        entries.append({"framework": h["framework"], "md": render_native(h, rows, res, unresolved)})
    flags = fold_singletons(flags)
    # de-duplicate identical flags; two handlers that share a name stay apart
    def home(f):
        h = f[3]
        return h["src"].loc(h["idx"]) if isinstance(h, dict) and "src" in h else ""
    seen, uniq = set(), []
    for f in flags:
        k = (f[0], f[1], f[2], home(f))
        if k not in seen:
            seen.add(k); uniq.append(f)
    homes = {}
    for f in uniq:
        homes.setdefault(f[0], set()).add(home(f))
    uniq = [(("%s` @ `%s" % (f[0], home(f))) if len(homes[f[0]]) > 1 and home(f) else f[0],) + tuple(f[1:]) for f in uniq]
    text = render(srcs, entries, uniq, dispatchers, list(dict.fromkeys(needs)))
    if out_path:
        d = os.path.dirname(out_path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        sys.stdout.buffer.write(text.encode("utf-8"))
    print("account map: %d instruction(s), %d review lead(s), %d need completion" % (len(entries), len(uniq), len(dict.fromkeys(needs))), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
