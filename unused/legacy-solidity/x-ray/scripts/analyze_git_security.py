#!/usr/bin/env python3
"""Git history security analysis for Solidity repositories.

Analyzes git history from a security researcher's perspective: fix commits,
dangerous area changes, forked dependencies, technical debt, and developer
patterns. Outputs structured JSON consumed by the x-ray skill.

Usage:
    python3 analyze_git_security.py --repo . --src-dir contracts
    python3 analyze_git_security.py --repo . --src-dir contracts --json /tmp/out.json
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path


# ═══════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════

@dataclass
class FileChange:
    path: str
    added: int
    deleted: int
    is_source: bool = False
    is_test: bool = False


@dataclass
class Commit:
    sha: str
    short_sha: str
    date: str
    author: str
    subject: str
    files: list[FileChange] = field(default_factory=list)
    is_merge: bool = False

    @property
    def source_files(self) -> list[FileChange]:
        return [f for f in self.files if f.is_source]

    @property
    def test_files(self) -> list[FileChange]:
        return [f for f in self.files if f.is_test]

    @property
    def total_churn(self) -> int:
        return sum(f.added + f.deleted for f in self.files)

    @property
    def source_churn(self) -> int:
        return sum(f.added + f.deleted for f in self.files if f.is_source)


# ═══════════════════════════════════════════════════════════════
# COMMIT CLASSIFICATION — Intent + Structural Impact model
#
# Two-phase approach:
#   Phase 1: Classify commit MESSAGE into a single intent category
#            (first match wins from priority-ordered rules)
#   Phase 2: Analyze DIFF structure for directional code changes
#            (net addition of guards, removal of code paths, etc.)
#
# Final score = intent_base + structural_impact + shape_modifier
#               + security_domain_overlap
# ═══════════════════════════════════════════════════════════════

# Phase 1: Intent classification
# The commit gets ONE primary intent (highest-priority match), plus
# optional topic tags from secondary matches. The primary intent sets
# the base score; topic tags add smaller bonuses for cross-cutting
# concerns (e.g. a "bug fix" that also mentions "oracle" pricing).
#
# This avoids pure additive keyword scoring (every word = points) while
# still capturing the nuance that "fix oracle reentrancy" is more
# interesting than just "fix bug".

# Primary intent: first match wins, sets the base score
_INTENT_RULES: list[tuple[str, list[re.Pattern], int, str]] = [
    # (category, patterns, base_score, reason_label)
    ("security_explicit", [
        re.compile(r"\b(security|vulnerab|exploit|attack|CVE-\d)\b", re.I),
        re.compile(r"\b(reentran|overflow|underflow|front.?run|malleab)\w*", re.I),
    ], 8, "explicit security language"),

    ("urgent_fix", [
        re.compile(r"\b(hotfix|emergency|critical|IMPT)\b", re.I),
    ], 6, "urgent/critical fix"),

    ("bug_fix", [
        re.compile(r"\bfix(es|ed)?\b", re.I),
        re.compile(r"\bbug\b", re.I),
        re.compile(r"\bpatch\b", re.I),
        re.compile(r"\bbroken\b", re.I),
    ], 4, "bug fix"),

    ("hardening", [
        re.compile(r"\b(harden|mitigat|protect|restrict|sanitiz|validat)\w*", re.I),
    ], 2, "hardening/validation"),

    ("feature", [
        re.compile(r"^\s*(feat|add|implement|introduce|support)\b", re.I),
    ], -1, "feature addition"),

    ("maintenance", [
        re.compile(r"^\s*(docs?|chore|ci|test|style|build)\s*:", re.I),
        re.compile(r"\b(readme|typo|format|lint|rename|refactor|cleanup|comment)\b", re.I),
        re.compile(r"\bchange\s+\w+\s+to\s+\w+\b", re.I),
    ], -3, "maintenance/cosmetic"),
]

# Topic tags: checked independently of primary intent. Each adds a
# small bonus (+2) if matched, capturing cross-cutting domain signals.
# E.g. a "bug fix" mentioning "oracle" gets +2 for the oracle topic.
_TOPIC_TAGS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(oracle|price|liquidat|slippage|MEV)\w*", re.I),
     "involves oracle/pricing"),
    (re.compile(r"\b(reentran|overflow|underflow|front.?run)\w*", re.I),
     "involves known vulnerability pattern"),
    (re.compile(r"\b(ecrecover|permit|signature|nonce)\w*", re.I),
     "involves signatures/auth"),
]


def _classify_intent(subject: str) -> tuple[int, list[str]]:
    """Classify commit message: one primary intent + topic tag bonuses.

    Returns (total_score, list_of_reasons).
    Primary intent = first matching category (categorical).
    Topic tags = independent checks for domain relevance (small bonuses).
    """
    # Primary intent (first match wins)
    primary_score = 0
    reasons: list[str] = []
    primary_cat = None
    for cat, patterns, base_score, reason in _INTENT_RULES:
        if any(p.search(subject) for p in patterns):
            primary_score = base_score
            reasons.append(reason)
            primary_cat = cat
            break

    if primary_cat is None:
        reasons.append("unclassified")

    # Topic tags: small bonuses for domain signals not captured by
    # the primary intent. Only applied if primary intent is not
    # already negative (maintenance/feature).
    if primary_score >= 0:
        for pattern, tag_reason in _TOPIC_TAGS:
            if pattern.search(subject) and tag_reason not in reasons:
                # Don't double-count if primary already captured this
                if primary_cat != "security_explicit" or "vulnerability pattern" not in tag_reason:
                    primary_score += 2
                    reasons.append(tag_reason)

    return primary_score, reasons


# Phase 2: Structural diff analysis
# Instead of scanning for keyword presence in diff text, this
# phase counts ADDED vs REMOVED instances of code constructs
# to determine the DIRECTION of change. A commit that adds
# 3 require() and removes 1 is structurally different from one
# that just moves them around.

_GUARD_ADD = re.compile(r"^\+[^+].*\b(require|revert|assert)\s*\(", re.M)
_GUARD_REM = re.compile(r"^-[^-].*\b(require|revert|assert)\s*\(", re.M)
_MOD_ADD = re.compile(
    r"^\+[^+].*\b(onlyOwner|onlyRole|onlyAdmin|nonReentrant|whenNotPaused"
    r"|initializer|modifier\s+only)\b", re.M)
_MOD_REM = re.compile(
    r"^-[^-].*\b(onlyOwner|onlyRole|onlyAdmin|nonReentrant|whenNotPaused"
    r"|initializer|modifier\s+only)\b", re.M)
_XFER_CHANGE = re.compile(
    r"^[+-][^+-].*\b(safeTransfer\w*|\.transfer\(|transferFrom|\.call\{value)", re.M)
_SIG_CHANGE = re.compile(
    r"^[+-][^+-].*\b(ecrecover|permit|ECDSA|EIP.?712|nonce\b)", re.M)
_ACCT_CHANGE = re.compile(
    r"^[+-][^+-].*\b(balance\w*|totalSupply|exchangeRate|index\b|reserve)", re.M)


def _analyze_diff_structure(diff_text: str) -> list[tuple[int, str]]:
    """Detect structural changes in a unified diff.

    Counts added (+) vs removed (-) lines for each construct category.
    Both adding and removing guards are equally security-interesting —
    adding guards may fix a vulnerability, removing guards may introduce
    one. The direction is reported so auditors know what to look for,
    but the score weights both equally.

    Returns list of (score_delta, reason).
    """
    results: list[tuple[int, str]] = []

    # Guards: require/revert/assert — any change is security-relevant
    guards_added = len(_GUARD_ADD.findall(diff_text))
    guards_removed = len(_GUARD_REM.findall(diff_text))
    if guards_added > 0 or guards_removed > 0:
        if guards_added > guards_removed:
            results.append((3, f"adds runtime guards (+{guards_added}/-{guards_removed})"))
        elif guards_removed > guards_added:
            results.append((3, f"removes runtime guards (+{guards_added}/-{guards_removed})"))
        else:
            results.append((2, f"rewrites runtime guards (+{guards_added}/-{guards_removed})"))

    # Access modifiers — tightening and loosening both matter
    mods_added = len(_MOD_ADD.findall(diff_text))
    mods_removed = len(_MOD_REM.findall(diff_text))
    if mods_added > 0 or mods_removed > 0:
        if mods_added > mods_removed:
            results.append((3, f"tightens access control (+{mods_added}/-{mods_removed})"))
        elif mods_removed > mods_added:
            results.append((3, f"loosens access control (+{mods_added}/-{mods_removed})"))
        else:
            results.append((2, f"rewrites access control (+{mods_added}/-{mods_removed})"))

    # Transfer logic changes
    if _XFER_CHANGE.search(diff_text):
        results.append((2, "changes token transfer logic"))

    # Signature/auth changes
    if _SIG_CHANGE.search(diff_text):
        results.append((2, "changes signature/auth handling"))

    # Accounting/balance changes
    if _ACCT_CHANGE.search(diff_text):
        results.append((1, "changes accounting/balance logic"))

    return results

# ═══════════════════════════════════════════════════════════════
# SECURITY AREA CLASSIFICATION
# ═══════════════════════════════════════════════════════════════

SECURITY_AREAS = {
    "access_control": [
        r"onlyOwner", r"onlyRole", r"modifier\s+only", r"OwnableRoles",
        r"AccessControl", r"require\(msg\.sender", r"Ownable2Step",
        r"_checkOwner", r"hasRole", r"_checkRole", r"onlyAdmin",
    ],
    "fund_flows": [
        r"\.deposit\(", r"\.withdraw\(", r"\.transfer\(", r"\.mint\(",
        r"\.burn\(", r"collateral", r"safeTransfer", r"balanceOf",
        r"allowance", r"approve", r"_pay\b", r"_collect\b",
        r"function\s+deposit", r"function\s+withdraw",
    ],
    "oracle_price": [
        r"oracle", r"[Pp]rice", r"[Ff]eed", r"TWAP", r"markPrice",
        r"indexPrice", r"latestRoundData", r"getPrice", r"EMA",
        r"[Pp]rice[Hh]istory",
    ],
    "liquidation": [
        r"liquidat", r"backstop", r"ADL", r"[Dd]eleverage",
        r"[Ii]nsurance", r"insolvenc", r"bankruptcy", r"badDebt",
        r"isLiquidatable",
    ],
    "signatures": [
        r"ecrecover", r"permit", r"[Ss]ignature", r"EIP.?712",
        r"ECDSA", r"nonce", r"digest", r"_hashTypedData", r"v,\s*r,\s*s",
    ],
    "state_machines": [
        r"[Ss]tatus\s*=", r"[Ss]tate\s*=", r"Phase\b", r"Stage\b",
        r"[Ll]ifecycle", r"[Tt]ransition", r"[Pp]aused", r"[Ff]rozen",
        r"isActive", r"onlyActive", r"whenNotPaused",
    ],
}

_AREA_COMPILED = {
    area: [re.compile(p) for p in patterns]
    for area, patterns in SECURITY_AREAS.items()
}

# ═══════════════════════════════════════════════════════════════
# KNOWN LIBRARIES
# ═══════════════════════════════════════════════════════════════

KNOWN_LIBS = {
    "openzeppelin": {
        "patterns": ["openzeppelin-contracts", "openzeppelin"],
        "upstream_pragma": ["0.8."],
        "label": "OpenZeppelin",
    },
    "solady": {
        "patterns": ["solady"],
        "upstream_pragma": ["0.8."],
        "label": "Solady",
    },
    "uniswap_v2": {
        "patterns": ["uniswap", "univ2", "gte-univ2", "v2-core", "v2-periphery"],
        "upstream_pragma": [">=0.5.", "=0.5.", ">=0.6.", "=0.6."],
        "label": "Uniswap V2",
    },
    "uniswap_v3": {
        "patterns": ["v3-core", "v3-periphery", "uniswap-v3"],
        "upstream_pragma": [">=0.5.", "=0.7.", ">=0.7."],
        "label": "Uniswap V3",
    },
    "aave": {
        "patterns": ["aave"],
        "upstream_pragma": ["0.8."],
        "label": "Aave",
    },
    "chainlink": {
        "patterns": ["chainlink"],
        "upstream_pragma": ["0.8.", "0.6."],
        "label": "Chainlink",
    },
    "permit2": {
        "patterns": ["permit2"],
        "upstream_pragma": ["0.8."],
        "label": "Permit2",
    },
}

SKIP_LIB_ANALYSIS = {"forge-std", "ds-test", "forge-std-1"}

# ═══════════════════════════════════════════════════════════════
# PATH CLASSIFICATION
# ═══════════════════════════════════════════════════════════════

SOURCE_SUFFIXES = (".sol", ".vy", ".rs", ".cairo", ".move")
TEST_HINTS = ("test/", "tests/", "spec/", ".t.sol", ".spec.", "__tests__", "fuzz/")
EXCLUDE_DIRS = (
    "/lib/", "/node_modules/", "/forge-std/", "/out/",
    "/broadcast/", "/artifacts/", "/cache/",
)


def classify_path(path: str, src_dir: str) -> tuple[bool, bool]:
    """Classify a path as (is_source, is_test)."""
    lowered = path.lower()
    is_test = any(hint in lowered for hint in TEST_HINTS)

    if not any(path.endswith(s) for s in SOURCE_SUFFIXES):
        return False, is_test

    if any(exc in f"/{path}" for exc in EXCLUDE_DIRS):
        return False, is_test

    is_source = path.startswith(src_dir) and not is_test
    return is_source, is_test


def find_source_files(repo: str, src_dir: str) -> list[str]:
    """Walk filesystem for current .sol files in src_dir."""
    result = []
    src_path = os.path.join(repo, src_dir)
    if not os.path.isdir(src_path):
        return result
    for root, dirs, files in os.walk(src_path):
        # Prune excluded directories
        dirs[:] = [d for d in dirs if d not in (
            "test", "tests", "lib", "node_modules", "forge-std",
            "out", "broadcast", "artifacts", "cache", "script",
        )]
        for fname in files:
            if fname.endswith(".sol"):
                rel = os.path.relpath(os.path.join(root, fname), repo)
                result.append(rel)
    return sorted(result)


# ═══════════════════════════════════════════════════════════════
# GIT DATA COLLECTION
# ═══════════════════════════════════════════════════════════════

def run_git(repo: str, *args: str, allow_fail: bool = False) -> str:
    cmd = ["git", "-C", repo] + list(args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError:
        if allow_fail:
            return ""
        raise


def parse_git_log(repo: str, src_dir: str) -> list[Commit]:
    """Parse full git history in a single call."""
    sep = "<<SEP>>"
    # Use %x00 in git format to produce null bytes in output (not in args)
    fmt = f"COMMIT_START{sep}%H{sep}%h{sep}%aI{sep}%aN{sep}%P{sep}%s"
    raw = run_git(repo, "log", "--numstat", f"--format={fmt}")

    commits = []
    current: Commit | None = None
    for line in raw.splitlines():
        if line.startswith(f"COMMIT_START{sep}"):
            if current is not None:
                commits.append(current)
            parts = line.split(sep)
            if len(parts) < 7:
                current = None
                continue
            _, sha, short, date, author, parents, subject = parts[:7]
            is_merge = " " in parents.strip()
            current = Commit(
                sha=sha, short_sha=short, date=date[:10],
                author=author, subject=subject, is_merge=is_merge,
            )
        elif current is not None and line.strip():
            parts = line.split("\t")
            if len(parts) >= 3:
                try:
                    added = int(parts[0]) if parts[0] != "-" else 0
                    deleted = int(parts[1]) if parts[1] != "-" else 0
                except ValueError:
                    continue
                path = parts[2]
                is_src, is_tst = classify_path(path, src_dir)
                current.files.append(FileChange(
                    path=path, added=added, deleted=deleted,
                    is_source=is_src, is_test=is_tst,
                ))

    if current is not None:
        commits.append(current)
    return commits


# ═══════════════════════════════════════════════════════════════
# SECTION 1: REPO SHAPE
# ═══════════════════════════════════════════════════════════════

def analyze_repo_shape(commits: list[Commit], src_dir: str) -> dict:
    if not commits:
        return {
            "classification": "empty",
            "total_commits": 0,
            "source_touching_commits": 0,
            "bulk_import_sha": None,
            "date_spread_days": 0,
            "first_commit_date": None,
            "last_commit_date": None,
            "signals": ["Empty repository"],
        }

    source_commits = [c for c in commits if c.source_files]
    dates = sorted(c.date for c in commits)
    first = dates[0]
    last = dates[-1]

    try:
        d1 = datetime.strptime(first, "%Y-%m-%d")
        d2 = datetime.strptime(last, "%Y-%m-%d")
        spread = (d2 - d1).days
    except ValueError:
        spread = 0

    # Detect bulk import
    bulk_sha = None
    signals = []
    total_source_added = sum(
        sum(f.added for f in c.source_files)
        for c in source_commits
    )
    if source_commits:
        # Sort by source lines added, descending
        biggest = max(source_commits, key=lambda c: sum(f.added for f in c.source_files))
        biggest_added = sum(f.added for f in biggest.source_files)
        if total_source_added > 0 and biggest_added / total_source_added > 0.85:
            bulk_sha = biggest.short_sha
            signals.append(
                f"~{biggest_added} source lines arrived in 1 commit ({bulk_sha})"
            )

    # Classification
    classification = "normal_dev"
    if len(source_commits) <= 1:
        classification = "squashed_import"
        signals.append("Only 1 commit touches source files")
    elif len(source_commits) <= 3 and spread < 7:
        classification = "squashed_import"
        signals.append(f"Only {len(source_commits)} source commits in {spread} days")

    if bulk_sha and classification == "normal_dev":
        # Has bulk import but also real development after
        signals.append("Bulk import detected with subsequent development")

    signals.append(f"Date spread: {spread} days")
    signals.append(f"{len(source_commits)} commits touch source files out of {len(commits)} total")

    return {
        "classification": classification,
        "total_commits": len(commits),
        "source_touching_commits": len(source_commits),
        "bulk_import_sha": bulk_sha,
        "date_spread_days": spread,
        "first_commit_date": first,
        "last_commit_date": last,
        "signals": signals,
    }


# ═══════════════════════════════════════════════════════════════
# SECTION 2: FIX CANDIDATES
# ═══════════════════════════════════════════════════════════════

def score_commit(
    commit: Commit,
    src_dir: str,
    diff_text: str = "",
    file_areas_cache: dict[str, list[str]] | None = None,
) -> tuple[int, list[str]]:
    """Score a commit for security-fix likelihood.

    Uses a multi-phase approach:
      1. Classify message intent (categorical, first-match)
      2. Analyze diff structure (directional: added vs removed guards)
      3. Check security domain overlap (cross-ref with SECURITY_AREAS)
      4. Apply shape modifiers (focus, churn)

    The final score is the sum of phase contributions, floored at 0.
    """
    reasons: list[str] = []

    # ── Phase 1: Intent classification ──────────────────────────
    # Primary intent (categorical) + topic tag bonuses
    intent_score, intent_reasons = _classify_intent(commit.subject)
    reasons.extend(intent_reasons)

    src_files = commit.source_files
    if not src_files:
        return max(intent_score, 0), reasons

    # ── Phase 2: Structural diff analysis ───────────────────────
    # Counts added vs removed code constructs to determine the
    # direction of change, not just presence of keywords
    structural_score = 0
    if diff_text:
        for delta, reason in _analyze_diff_structure(diff_text):
            structural_score += delta
            reasons.append(reason)

    # ── Phase 3: Security domain overlap ────────────────────────
    # Cross-references changed files against SECURITY_AREAS
    # classification. A commit touching multiple security domains
    # (e.g. access_control + fund_flows) is more interesting.
    domain_score = 0
    if file_areas_cache is not None:
        touched_domains: set[str] = set()
        for fc in src_files:
            for area in file_areas_cache.get(fc.path, []):
                touched_domains.add(area)
        if len(touched_domains) >= 2:
            domain_score = 3
            reasons.append(
                f"spans {len(touched_domains)} security domains "
                f"({', '.join(sorted(touched_domains))})"
            )
        elif len(touched_domains) == 1:
            domain_score = 1
            reasons.append(f"touches {next(iter(touched_domains))} code")

    # ── Phase 4: Shape modifiers ────────────────────────────────
    shape_score = 0

    # Focused changes (few files) are more likely targeted fixes
    if 1 <= len(src_files) <= 3:
        shape_score += 2
        reasons.append(f"focused change ({len(src_files)} source files)")

    # Net code removal suggests removing vulnerable paths
    net_deleted = sum(f.deleted - f.added for f in src_files)
    if net_deleted > 0:
        shape_score += 1
        reasons.append("net code removal")

    # Large bulk changes are likely features or refactors
    src_churn = commit.source_churn
    if src_churn > 2000:
        shape_score -= 4
        reasons.append("very large change (>2000 source lines)")
    elif src_churn > 500:
        shape_score -= 2
        reasons.append("large change (>500 source lines)")

    # Test co-change is informative (either direction)
    if commit.test_files:
        shape_score += 1
        reasons.append("includes test changes")

    total = intent_score + structural_score + domain_score + shape_score
    return max(total, 0), _unique(reasons)


def find_fix_candidates(
    commits: list[Commit],
    src_dir: str,
    repo: str,
    limit: int,
    file_areas_cache: dict[str, list[str]] | None = None,
) -> list[dict]:
    """Score all commits, return top N fix candidates.

    Uses intent classification + structural diff analysis + security
    domain cross-referencing to identify likely security fixes.
    """
    candidates = []
    for commit in commits:
        if commit.is_merge:
            continue
        # Get diff text for source-touching commits only
        diff_text = ""
        if commit.source_files:
            diff_text = run_git(
                repo, "show", "--format=", "--unified=0",
                "--no-ext-diff", commit.sha,
                allow_fail=True,
            )
        sc, reasons = score_commit(
            commit, src_dir, diff_text, file_areas_cache,
        )
        if sc > 0:
            candidates.append({
                "sha": commit.short_sha,
                "full_sha": commit.sha,
                "date": commit.date,
                "author": commit.author,
                "subject": commit.subject,
                "score": sc,
                "reasons": reasons,
                "source_files_touched": [f.path for f in commit.source_files],
                "test_changed": bool(commit.test_files),
                "lines_changed": commit.source_churn,
            })

    candidates.sort(key=lambda c: (c["score"], c["date"]), reverse=True)
    if limit > 0:
        candidates = candidates[:limit]
    return candidates


# ═══════════════════════════════════════════════════════════════
# SECTION 3: DANGEROUS AREA CHANGES
# ═══════════════════════════════════════════════════════════════

def _read_file_safe(path: str) -> str:
    try:
        with open(path, "r", errors="replace") as f:
            return f.read()
    except (OSError, IOError):
        return ""


def classify_file_areas(content: str) -> list[str]:
    """Determine which security areas a file's content touches."""
    areas = []
    for area, patterns in _AREA_COMPILED.items():
        for pat in patterns:
            if pat.search(content):
                areas.append(area)
                break
    return areas


def _build_file_areas_cache(repo: str, src_dir: str) -> dict[str, list[str]]:
    """Build a mapping of file paths to their security area classifications.

    Shared by both fix candidate scoring (Phase 3: domain overlap) and
    dangerous area analysis.
    """
    cache: dict[str, list[str]] = {}
    src_path = os.path.join(repo, src_dir)
    if os.path.isdir(src_path):
        for root, dirs, files in os.walk(src_path):
            dirs[:] = [d for d in dirs if d not in (
                "test", "tests", "lib", "node_modules", "script",
            )]
            for fname in files:
                if fname.endswith(".sol"):
                    full = os.path.join(root, fname)
                    rel = os.path.relpath(full, repo)
                    content = _read_file_safe(full)
                    cache[rel] = classify_file_areas(content)

    # Also classify files in lib/ that are source-like
    lib_path = os.path.join(repo, "lib")
    if os.path.isdir(lib_path):
        for root, dirs, files in os.walk(lib_path):
            dirs[:] = [d for d in dirs if d not in (
                "test", "tests", "node_modules", "forge-std",
            )]
            for fname in files:
                if fname.endswith(".sol"):
                    full = os.path.join(root, fname)
                    rel = os.path.relpath(full, repo)
                    if rel not in cache:
                        content = _read_file_safe(full)
                        cache[rel] = classify_file_areas(content)

    return cache


def analyze_dangerous_areas(
    commits: list[Commit],
    src_dir: str,
    repo: str,
    file_areas_cache: dict[str, list[str]] | None = None,
) -> dict:
    """Group commits by security area they affect."""
    if file_areas_cache is None:
        file_areas_cache = _build_file_areas_cache(repo, src_dir)

    # Map commits to areas
    result: dict[str, dict] = {}
    for area in SECURITY_AREAS:
        result[area] = {"commit_count": 0, "files": set(), "commits": []}

    for commit in commits:
        if commit.is_merge:
            continue
        commit_areas: set[str] = set()
        for fc in commit.files:
            areas = file_areas_cache.get(fc.path, [])
            for a in areas:
                commit_areas.add(a)
                result[a]["files"].add(fc.path)

        for a in commit_areas:
            result[a]["commit_count"] += 1
            result[a]["commits"].append({
                "sha": commit.short_sha,
                "date": commit.date,
                "subject": commit.subject[:80],
            })

    # Convert sets to sorted lists, remove empty areas
    final = {}
    for area, data in result.items():
        if data["commit_count"] > 0:
            data["files"] = sorted(data["files"])
            # Cap commit list at 15
            if len(data["commits"]) > 15:
                data["commits"] = data["commits"][:15]
                data["truncated"] = True
            final[area] = data

    return final


# ═══════════════════════════════════════════════════════════════
# SECTION 4: LATE CHANGES
# ═══════════════════════════════════════════════════════════════

def analyze_late_changes(
    commits: list[Commit], src_dir: str, days: int
) -> dict:
    """Find commits touching source in the last N days of repo activity."""
    if not commits:
        return {
            "window_days": days,
            "cutoff_date": None,
            "latest_commit_date": None,
            "late_commits": [],
            "source_without_test_count": 0,
            "total_late_source_commits": 0,
        }

    # Find latest date
    dates = []
    for c in commits:
        try:
            dates.append(datetime.strptime(c.date, "%Y-%m-%d"))
        except ValueError:
            pass

    if not dates:
        return {
            "window_days": days,
            "cutoff_date": None,
            "latest_commit_date": None,
            "late_commits": [],
            "source_without_test_count": 0,
            "total_late_source_commits": 0,
        }

    latest = max(dates)
    cutoff = latest - timedelta(days=days)
    cutoff_str = cutoff.strftime("%Y-%m-%d")
    latest_str = latest.strftime("%Y-%m-%d")

    late = []
    no_test_count = 0
    for c in commits:
        try:
            cdate = datetime.strptime(c.date, "%Y-%m-%d")
        except ValueError:
            continue
        if cdate < cutoff:
            continue
        if not c.source_files:
            continue
        has_test = bool(c.test_files)
        if not has_test:
            no_test_count += 1
        late.append({
            "sha": c.short_sha,
            "date": c.date,
            "author": c.author,
            "subject": c.subject[:80],
            "source_files": [f.path for f in c.source_files][:10],
            "test_changed": has_test,
            "lines_changed": c.source_churn,
        })

    return {
        "window_days": days,
        "cutoff_date": cutoff_str,
        "latest_commit_date": latest_str,
        "late_commits": late,
        "source_without_test_count": no_test_count,
        "total_late_source_commits": len(late),
    }


# ═══════════════════════════════════════════════════════════════
# SECTION 5: FORKED DEPENDENCIES
# ═══════════════════════════════════════════════════════════════

def _detect_lib_identity(dirname: str) -> str | None:
    """Match a lib directory name to a known library."""
    lower = dirname.lower()
    for lib_id, info in KNOWN_LIBS.items():
        for pattern in info["patterns"]:
            if pattern.lower() in lower:
                return lib_id
    return None


def _extract_pragmas(sol_dir: str) -> list[str]:
    """Extract unique pragma versions from .sol files in a directory."""
    pragmas = set()
    if not os.path.isdir(sol_dir):
        return []
    for root, _, files in os.walk(sol_dir):
        for fname in files:
            if not fname.endswith(".sol"):
                continue
            try:
                with open(os.path.join(root, fname), "r", errors="replace") as f:
                    for line in f:
                        m = re.match(r"\s*pragma\s+solidity\s+(.+?)\s*;", line)
                        if m:
                            pragmas.add(m.group(1).strip())
                            break
            except (OSError, IOError):
                continue
    return sorted(pragmas)


def _count_sol_files(dirpath: str) -> int:
    count = 0
    if not os.path.isdir(dirpath):
        return 0
    for root, _, files in os.walk(dirpath):
        for f in files:
            if f.endswith(".sol"):
                count += 1
    return count


def _check_pragma_mismatch(
    found_pragmas: list[str], expected_prefixes: list[str]
) -> list[str]:
    """Check if pragmas differ from expected upstream versions."""
    notes = []
    for pragma in found_pragmas:
        matches_expected = any(
            pragma.startswith(prefix) or prefix in pragma
            for prefix in expected_prefixes
        )
        if not matches_expected:
            notes.append(f"Pragma '{pragma}' differs from expected upstream versions")
    return notes


def analyze_forked_deps(repo: str) -> dict:
    """Detect internalized/forked libraries."""
    lib_dir = os.path.join(repo, "lib")
    detected = []

    # Check current .gitmodules for active submodules
    gitmodules_path = os.path.join(repo, ".gitmodules")
    active_submodules = set()
    if os.path.isfile(gitmodules_path):
        try:
            with open(gitmodules_path, "r") as f:
                for line in f:
                    m = re.match(r"\s*path\s*=\s*(.+)", line)
                    if m:
                        active_submodules.add(m.group(1).strip())
        except (OSError, IOError):
            pass

    # Scan lib/ directories
    if os.path.isdir(lib_dir):
        for entry in sorted(os.listdir(lib_dir)):
            entry_path = os.path.join(lib_dir, entry)
            if not os.path.isdir(entry_path):
                continue
            if entry in SKIP_LIB_ANALYSIS:
                continue

            lib_rel = f"lib/{entry}"
            lib_id = _detect_lib_identity(entry)
            sol_count = _count_sol_files(entry_path)

            if sol_count == 0:
                continue

            is_submodule = lib_rel in active_submodules
            is_internalized = not is_submodule and not os.path.isdir(
                os.path.join(entry_path, ".git")
            )
            # Also check for submodule pointer file (single-line file with commit hash)
            gitfile = os.path.join(entry_path, ".git")
            if os.path.isfile(gitfile):
                is_submodule = True
                is_internalized = False

            pragmas = _extract_pragmas(entry_path)
            notes = []

            if lib_id and lib_id in KNOWN_LIBS:
                label = KNOWN_LIBS[lib_id]["label"]
                expected = KNOWN_LIBS[lib_id]["upstream_pragma"]
                pragma_notes = _check_pragma_mismatch(pragmas, expected)
                notes.extend(pragma_notes)
                if is_internalized:
                    notes.append(f"Internalized (not a submodule) — may contain modifications from upstream {label}")
            else:
                label = entry
                if is_internalized:
                    notes.append("Internalized (not a submodule) — unknown upstream")

            detected.append({
                "name": entry,
                "path": lib_rel,
                "known_upstream": label if lib_id else None,
                "is_submodule": is_submodule,
                "is_internalized": is_internalized,
                "sol_file_count": sol_count,
                "pragma_versions": pragmas,
                "notes": notes,
            })

    # Check git history for removed submodules
    removed = []
    gitmodules_log = run_git(
        repo, "log", "-p", "--", ".gitmodules",
        allow_fail=True,
    )
    if gitmodules_log:
        current_sha = None
        current_subject = None
        for line in gitmodules_log.splitlines():
            m = re.match(r"^commit\s+([a-f0-9]+)", line)
            if m:
                current_sha = m.group(1)[:7]
                current_subject = None
                continue
            if line.startswith("    ") and current_subject is None:
                current_subject = line.strip()[:80]
                continue
            # Detect removed submodule path lines
            m = re.match(r"^-\s*path\s*=\s*(.+)", line)
            if m and current_sha:
                removed_path = m.group(1).strip()
                removed.append({
                    "path": removed_path,
                    "removed_in_sha": current_sha,
                    "subject": current_subject or "",
                })

    return {
        "detected_libs": detected,
        "removed_submodules": removed,
    }


# ═══════════════════════════════════════════════════════════════
# SECTION 6: TECH DEBT
# ═══════════════════════════════════════════════════════════════

_DEBT_RE = re.compile(
    r"(?://|/\*)\s*(TODO|FIXME|HACK|XXX)\b[:\s]*(.*)",
    re.IGNORECASE,
)

BLAME_CAP = 20  # Max files to blame (performance guard)


def find_tech_debt(source_files: list[str], repo: str) -> dict:
    """Find TODO/FIXME/HACK/XXX in source files with git blame."""
    items = []
    files_with_debt = set()

    for rel_path in source_files:
        full_path = os.path.join(repo, rel_path)
        try:
            with open(full_path, "r", errors="replace") as f:
                lines = f.readlines()
        except (OSError, IOError):
            continue

        for i, line in enumerate(lines, 1):
            m = _DEBT_RE.search(line)
            if m:
                files_with_debt.add(rel_path)
                items.append({
                    "file": rel_path,
                    "line": i,
                    "type": m.group(1).upper(),
                    "text": m.group(2).strip()[:120] if m.group(2) else "",
                    "blame_author": None,
                    "blame_date": None,
                })

    # Git blame for attribution (capped)
    blame_files = sorted(files_with_debt)[:BLAME_CAP]
    capped = len(files_with_debt) > BLAME_CAP

    # Build a lookup: file -> {line: (author, date)}
    blame_lookup: dict[str, dict[int, tuple[str, str]]] = {}
    for rel_path in blame_files:
        blame_out = run_git(
            repo, "blame", "--porcelain", rel_path,
            allow_fail=True,
        )
        if not blame_out:
            continue
        file_blame: dict[int, tuple[str, str]] = {}
        current_author = ""
        current_date = ""
        current_line = 0
        for bline in blame_out.splitlines():
            # First line of each block: <sha> <orig_line> <final_line> [<count>]
            m = re.match(r"^[a-f0-9]{40}\s+\d+\s+(\d+)", bline)
            if m:
                current_line = int(m.group(1))
                continue
            if bline.startswith("author "):
                current_author = bline[7:].strip()
            elif bline.startswith("author-time "):
                try:
                    ts = int(bline[12:].strip())
                    current_date = datetime.fromtimestamp(
                        ts, tz=timezone.utc
                    ).strftime("%Y-%m-%d")
                except (ValueError, OSError):
                    current_date = ""
            elif bline.startswith("\t"):
                # Content line — save blame for this line number
                if current_line > 0:
                    file_blame[current_line] = (current_author, current_date)

        blame_lookup[rel_path] = file_blame

    # Enrich items with blame
    for item in items:
        bl = blame_lookup.get(item["file"], {})
        info = bl.get(item["line"])
        if info:
            item["blame_author"] = info[0]
            item["blame_date"] = info[1]

    return {
        "total_count": len(items),
        "items": items,
        "files_with_debt": len(files_with_debt),
        "capped": capped,
    }


# ═══════════════════════════════════════════════════════════════
# SECTION 7: DEV PATTERNS
# ═══════════════════════════════════════════════════════════════

def analyze_dev_patterns(
    commits: list[Commit],
    source_files: list[str],
    repo: str,
    src_dir: str,
    fix_candidates: list[dict],
    bulk_import_sha: str | None,
) -> dict:
    """Compute developer pattern metrics."""
    # Filter out merge commits and optionally bulk import
    non_merge = [c for c in commits if not c.is_merge]
    source_commits = [c for c in non_merge if c.source_files]
    analysis_commits = source_commits
    if bulk_import_sha:
        analysis_commits = [
            c for c in source_commits
            if c.short_sha != bulk_import_sha
        ]

    # 1. Test co-change rate
    if source_commits:
        with_tests = sum(1 for c in source_commits if c.test_files)
        test_co_change = with_tests / len(source_commits)
    else:
        test_co_change = 0.0

    # 2. Fix without test rate
    fix_without_test = None
    if fix_candidates:
        no_test = sum(1 for f in fix_candidates if not f["test_changed"])
        fix_without_test = no_test / len(fix_candidates)

    # 4. Avg commit size (excluding bulk import)
    if analysis_commits:
        avg_size = sum(c.source_churn for c in analysis_commits) / len(analysis_commits)
    else:
        avg_size = 0.0
    size_note = "excluding bulk import" if bulk_import_sha and len(analysis_commits) != len(source_commits) else None

    # 5. Single developer percentage
    author_lines: dict[str, int] = {}
    for c in source_commits:
        added = sum(f.added for f in c.source_files)
        author_lines[c.author] = author_lines.get(c.author, 0) + added

    total_lines = sum(author_lines.values())
    breakdown = []
    if total_lines > 0:
        for author, lines in sorted(
            author_lines.items(), key=lambda x: x[1], reverse=True
        ):
            breakdown.append({
                "author": author,
                "lines_added": lines,
                "pct": round(lines / total_lines, 3),
            })

    top_contributor = breakdown[0]["author"] if breakdown else "unknown"
    single_dev_pct = breakdown[0]["pct"] if breakdown else 0.0

    return {
        "test_co_change_rate": round(test_co_change, 3),
        "fix_without_test_rate": round(fix_without_test, 3) if fix_without_test is not None else None,
        "avg_commit_size": round(avg_size, 1),
        "avg_commit_size_note": size_note,
        "single_developer_pct": round(single_dev_pct, 3),
        "top_contributor": top_contributor,
        "contributor_breakdown": breakdown[:10],
    }


# ═══════════════════════════════════════════════════════════════
# UTILITY
# ═══════════════════════════════════════════════════════════════

def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result


def detect_src_dir(repo: str) -> str:
    """Auto-detect source directory from foundry.toml or common patterns."""
    toml_path = os.path.join(repo, "foundry.toml")
    if os.path.isfile(toml_path):
        try:
            with open(toml_path, "r") as f:
                for line in f:
                    m = re.match(r'\s*src\s*=\s*["\'](.+?)["\']', line)
                    if m:
                        return m.group(1).rstrip("/") + "/"
        except (OSError, IOError):
            pass

    # Fallback: check common directories
    for candidate in ["contracts/", "src/"]:
        if os.path.isdir(os.path.join(repo, candidate)):
            return candidate
    return "src/"


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Git history security analysis for Solidity repositories",
    )
    parser.add_argument("--repo", default=".", help="Path to git repository")
    parser.add_argument("--json", default=None, help="Output JSON to file (default: stdout)")
    parser.add_argument("--days", type=int, default=30, help="Late change window (days)")
    parser.add_argument("--limit", type=int, default=10, help="Max fix candidates")
    parser.add_argument("--src-dir", default=None, help="Source directory (auto-detected)")
    args = parser.parse_args()

    repo = os.path.abspath(args.repo)
    src_dir = args.src_dir or detect_src_dir(repo)
    # Ensure trailing slash for consistent prefix matching
    if not src_dir.endswith("/"):
        src_dir += "/"

    t0 = time.monotonic()

    # Verify git repo
    try:
        head = run_git(repo, "rev-parse", "--short", "HEAD").strip()
    except subprocess.CalledProcessError:
        err = {"error": f"{repo} is not a git repository"}
        _write_output(err, args.json)
        return 2

    # Detect current branch name
    try:
        branch = run_git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
    except subprocess.CalledProcessError:
        branch = "unknown"

    # Phase 1: Collect git data
    commits = parse_git_log(repo, src_dir)

    # Phase 2: Find source files
    source_files = find_source_files(repo, src_dir)

    # Phase 3: Run analyzers
    repo_shape = analyze_repo_shape(commits, src_dir)

    # Build file→security-area cache once, shared by fix detection
    # and dangerous area analysis
    file_areas_cache = _build_file_areas_cache(repo, src_dir)

    fix_cands = find_fix_candidates(
        commits, src_dir, repo, args.limit, file_areas_cache,
    )
    dangerous = analyze_dangerous_areas(
        commits, src_dir, repo, file_areas_cache,
    )
    late = analyze_late_changes(commits, src_dir, args.days)
    forked = analyze_forked_deps(repo)
    debt = find_tech_debt(source_files, repo)
    patterns = analyze_dev_patterns(
        commits, source_files, repo, src_dir,
        fix_cands, repo_shape.get("bulk_import_sha"),
    )

    elapsed_ms = int((time.monotonic() - t0) * 1000)

    result = {
        "meta": {
            "repo": repo,
            "src_dir": src_dir.rstrip("/"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "git_head": head,
            "git_branch": branch,
            "total_commits": len(commits),
            "total_source_files": len(source_files),
            "analysis_time_ms": elapsed_ms,
        },
        "repo_shape": repo_shape,
        "fix_candidates": fix_cands,
        "dangerous_area_changes": dangerous,
        "late_changes": late,
        "forked_deps": forked,
        "tech_debt": debt,
        "dev_patterns": patterns,
    }

    _write_output(result, args.json)
    return 0


def _write_output(data: dict, filepath: str | None) -> None:
    text = json.dumps(data, indent=2)
    if filepath:
        with open(filepath, "w") as f:
            f.write(text)
            f.write("\n")
    else:
        print(text)


if __name__ == "__main__":
    raise SystemExit(main())
