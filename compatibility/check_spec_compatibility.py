#!/usr/bin/env python3
"""Detect whether an Inferrex review skill lags the canonical specification."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

FEATURE_SIGNAL = re.compile(
    r"(?i)\b("
    r"stitch(?:ing|ed)?|compos(?:e|ed|ing|ition|itional|ability)|"
    r"new feature|new capability|introduc(?:e|es|ed|ing)|"
    r"workflow|multi[- ]step|modality|endpoint|protocol object|"
    r"signed type|service identity|market type|artifact market"
    r")\b"
)
SEAL_SCHEMA_PREFIX = "inferrex.specification-seal."
SEAL_FILENAMES = {
    "inferrex-specification-seal.json",
    "validation/specification-seal.json",
}


def run_git(root: Path, *args: str) -> tuple[bool, str]:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    output = result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
    return result.returncode == 0, output


def resolve_spec_root(project_root: Path, supplied: str | None) -> Path:
    if supplied:
        candidate = Path(supplied).expanduser().resolve()
        if not candidate.is_dir():
            raise SystemExit(f"spec root is not a directory: {candidate}")
        return candidate
    if (project_root / "inferrex-t0-protocol-correctness-spec.md").is_file():
        return project_root
    sibling = project_root.parent / "core-specification"
    if sibling.is_dir():
        return sibling.resolve()
    raise SystemExit(
        "could not locate core-specification; pass --spec-root explicitly"
    )


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_tree_sha(root: Path, paths: list[str]) -> str:
    with tempfile.TemporaryDirectory(prefix="inferrex-compatibility-tree-") as temp:
        target_root = Path(temp)
        for relative in paths:
            source = root / relative
            if not source.is_file():
                raise RuntimeError(f"missing canonical source file: {relative}")
            target = target_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            target.chmod(0o644)
        subprocess.run(
            ["git", "init", "--quiet"],
            cwd=target_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        subprocess.run(
            ["git", "config", "core.fileMode", "false"],
            cwd=target_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        subprocess.run(
            ["git", "add", "-f", "--", *paths],
            cwd=target_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        result = subprocess.run(
            ["git", "write-tree"],
            cwd=target_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return result.stdout.strip()


def seal_candidates(root: Path) -> list[Path]:
    candidates = {root / relative for relative in SEAL_FILENAMES}
    candidates.update(root.glob("*specification*seal*.json"))
    candidates.update((root / "validation").glob("*specification*seal*.json"))
    return sorted(path for path in candidates if path.is_file())


def inspect_seals(root: Path, current_tree: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    inspected: list[dict[str, Any]] = []
    for path in seal_candidates(root):
        relative = path.relative_to(root).as_posix()
        try:
            value = read_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            inspected.append({"path": relative, "valid": False, "reason": str(exc)})
            continue
        if not isinstance(value, dict):
            inspected.append(
                {"path": relative, "valid": False, "reason": "not a JSON object"}
            )
            continue
        seal = value.get("specificationSeal", value)
        schema = value.get("schemaVersion", seal.get("schemaVersion"))
        source = seal.get("source", {})
        tree = source.get("treeSha", seal.get("canonicalTreeSha"))
        gate = seal.get("gate", seal.get("sealedAtGate"))
        committed, _ = run_git(root, "cat-file", "-e", f"HEAD:{relative}")
        unchanged, _ = run_git(root, "diff", "--quiet", "HEAD", "--", relative)
        valid = (
            isinstance(schema, str)
            and schema.startswith(SEAL_SCHEMA_PREFIX)
            and seal.get("sealed") is True
            and isinstance(gate, str)
            and bool(gate.strip())
            and tree == current_tree
            and committed
            and unchanged
        )
        record = {
            "path": relative,
            "valid": valid,
            "schemaVersion": schema,
            "gate": gate,
            "treeSha": tree,
            "committed": committed,
            "unchangedFromHead": unchanged,
        }
        if not valid:
            record["reason"] = (
                "seal must use inferrex.specification-seal.*, set sealed=true, "
                "name a gate, bind the current canonical tree and be committed "
                "unchanged in HEAD"
            )
        inspected.append(record)
        if valid:
            return record, inspected
    return None, inspected


def git_changes(
    root: Path, baseline_commit: str, canonical_paths: list[str]
) -> tuple[list[str], list[str], str | None]:
    exists, _ = run_git(root, "cat-file", "-e", f"{baseline_commit}^{{commit}}")
    if not exists:
        return [], [], "baseline source commit is unavailable in local history"
    ok, names = run_git(
        root,
        "diff",
        "--name-only",
        baseline_commit,
        "--",
        *canonical_paths,
    )
    if not ok:
        return [], [], names
    changed = names.splitlines() if names else []
    ok, patch = run_git(
        root,
        "diff",
        "--unified=0",
        baseline_commit,
        "--",
        *canonical_paths,
    )
    signals: list[str] = []
    if ok:
        for line in patch.splitlines():
            if (
                line.startswith("+")
                and not line.startswith("+++")
                and FEATURE_SIGNAL.search(line[1:])
            ):
                signals.append(line[1:].strip())
                if len(signals) == 100:
                    break
    return changed, signals, None


def unexpected_paths(
    root: Path, canonical_paths: set[str], non_normative: set[str]
) -> tuple[list[str], list[str]]:
    ok, tracked_text = run_git(root, "ls-files")
    tracked = set(tracked_text.splitlines()) if ok and tracked_text else set()
    allowed = canonical_paths | non_normative
    unexpected_tracked = sorted(
        path
        for path in tracked - allowed
        if not path.startswith("validation/")
    )
    ok, status_text = run_git(root, "status", "--porcelain=v1", "--untracked-files=all")
    untracked: list[str] = []
    if ok and status_text:
        for line in status_text.splitlines():
            if line.startswith("?? "):
                path = line[3:]
                if path not in allowed and not path.startswith("validation/"):
                    untracked.append(path)
    return unexpected_tracked, sorted(untracked)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--spec-root")
    parser.add_argument(
        "--baseline",
        default=str(Path(__file__).with_name("spec-baseline.json")),
    )
    parser.add_argument("--output")
    args = parser.parse_args()

    project_root = Path(args.project_root).expanduser().resolve()
    spec_root = resolve_spec_root(project_root, args.spec_root)
    baseline_path = Path(args.baseline).expanduser().resolve()
    baseline = read_json(baseline_path)
    skill_baseline = baseline.get("skills", {}).get(args.skill)
    if not isinstance(skill_baseline, dict):
        raise SystemExit(f"no compatibility baseline for skill: {args.skill}")

    registry_path = spec_root / "inferrex-source-files.json"
    registry = read_json(registry_path)
    canonical_paths = sorted(set(registry.get("paths", [])))
    non_normative = set(registry.get("nonNormativePaths", []))
    current_tree = canonical_tree_sha(spec_root, canonical_paths)
    baseline_tree = skill_baseline.get("canonicalTreeSha")
    valid_seal, inspected_seals = inspect_seals(spec_root, current_tree)
    reviewed_source_commit = skill_baseline.get(
        "reviewedSourceCommit", baseline.get("reviewedSourceCommit")
    )
    changed, feature_signals, history_warning = git_changes(
        spec_root,
        str(reviewed_source_commit),
        canonical_paths,
    )
    unexpected_tracked, unexpected_untracked = unexpected_paths(
        spec_root, set(canonical_paths), non_normative
    )
    head_ok, head = run_git(spec_root, "rev-parse", "HEAD")

    if valid_seal:
        status = "SEALED"
        rewrite_required = False
        reason = (
            f"canonical specification is explicitly sealed at "
            f"{valid_seal['gate']} for the current source tree"
        )
    elif (
        current_tree == baseline_tree
        and not unexpected_tracked
        and not unexpected_untracked
    ):
        status = "COMPATIBLE"
        rewrite_required = False
        reason = "canonical source tree matches this skill's reviewed baseline"
    else:
        status = "REWRITE_REQUIRED"
        rewrite_required = True
        reason = (
            "canonical source or open-world path set changed without a "
            "current-tree-bound specification seal"
        )

    result = {
        "schemaVersion": 1,
        "status": status,
        "rewriteRequired": rewrite_required,
        "reason": reason,
        "skill": args.skill,
        "specification": {
            "root": str(spec_root),
            "head": head if head_ok else None,
            "canonicalTreeSha": current_tree,
            "canonicalPathCount": len(canonical_paths),
        },
        "baseline": {
            "path": str(baseline_path),
            "canonicalTreeSha": baseline_tree,
            "reviewedSourceCommit": reviewed_source_commit,
            "scope": skill_baseline.get("scope"),
        },
        "changedCanonicalPaths": changed,
        "candidateFeatureSignals": feature_signals,
        "unexpectedTrackedPaths": unexpected_tracked,
        "unexpectedUntrackedPaths": unexpected_untracked,
        "historyWarning": history_warning,
        "validSpecificationSeal": valid_seal,
        "inspectedSealCandidates": inspected_seals,
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered)
    print(rendered, end="")
    raise SystemExit(2 if rewrite_required else 0)


if __name__ == "__main__":
    main()
