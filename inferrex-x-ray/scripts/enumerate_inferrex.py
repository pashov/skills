#!/usr/bin/env python3
"""Create a deterministic inventory for an Inferrex T0-T4 review."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

TEXT_SUFFIXES = {
    ".c",
    ".cc",
    ".cjs",
    ".cpp",
    ".css",
    ".go",
    ".graphql",
    ".h",
    ".html",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".mjs",
    ".py",
    ".rs",
    ".sh",
    ".sol",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
EXCLUDED_DIRS = {
    ".git",
    ".inferrex-review",
    ".next",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "out",
    "target",
    "unused",
    "vendor",
}
STAGE_RE = re.compile(r"(?<![A-Za-z0-9])T([0-4])(?:\.(\d+))?(?![A-Za-z0-9])", re.I)
AUTHORITY_NAMES = {
    "README.md",
    "inferrex-implementation-tracker.md",
    "inferrex-mvi-0-launch-profile.md",
    "inferrex-mvi-0-profile.json",
    "inferrex-source-files.json",
    "inferrex-t0-mvi0-adversarial-review-questions.md",
    "inferrex-t0-protocol-correctness-spec.md",
}


def run_git(root: Path, *args: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def git_state(root: Path) -> dict[str, Any]:
    commit = run_git(root, "rev-parse", "HEAD")
    tree = run_git(root, "rev-parse", "HEAD^{tree}")
    branch = run_git(root, "branch", "--show-current")
    porcelain = run_git(root, "status", "--porcelain=v1", "--untracked-files=all")
    changes = [] if not porcelain else porcelain.splitlines()
    return {
        "root": str(root),
        "commit": commit,
        "tree": tree,
        "branch": branch,
        "dirty": bool(changes),
        "changeCount": len(changes),
        "changes": changes,
    }


def read_probe(path: Path, limit: int = 2_000_000) -> str:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return ""
    try:
        return path.read_bytes()[:limit].decode("utf-8", errors="replace")
    except OSError:
        return ""


def classify(path: Path) -> str:
    lowered = path.as_posix().lower()
    name = path.name.lower()
    if "/reviews/" in f"/{lowered}" or "adversarial-review" in name or "disposition" in name:
        return "review"
    if "/validation/" in f"/{lowered}" or "evidence" in name or "closure-record" in name or "gate-state" in name:
        return "evidence"
    if "checker" in name or name.endswith("-check.cjs"):
        return "checker"
    if "vector" in name or "fixture" in lowered:
        return "vector"
    if "schema" in name or path.suffix.lower() == ".sql" and "reference" in name:
        return "schema"
    if "model" in name:
        return "model"
    if "spec" in name or "profile" in name or "tracker" in name:
        return "specification"
    if "test" in lowered or path.name.endswith((".spec.ts", ".test.ts", "_test.go")):
        return "test"
    if path.name in {"package.json", "package-lock.json", "go.mod", "go.sum"} or path.suffix.lower() in {".toml", ".yaml", ".yml"}:
        return "configuration"
    if path.suffix.lower() == ".md":
        return "documentation"
    return "implementation"


def stages_for(path: Path, probe: str) -> list[str]:
    matches = {f"T{match.group(1)}" for match in STAGE_RE.finditer(path.as_posix())}
    matches.update(f"T{match.group(1)}" for match in STAGE_RE.finditer(probe))
    if path.name.startswith("inferrex-t0"):
        matches.add("T0")
    return sorted(matches)


def is_authoritative(relative: Path, kind: str, source_label: str) -> bool:
    if source_label != "spec":
        return False
    path = relative.as_posix()
    return (
        relative.name in AUTHORITY_NAMES
        or path.startswith("validation/")
        or path.startswith("reviews/")
        or relative.name.startswith("inferrex-t0")
        or kind in {"checker", "model", "schema", "vector"}
    )


def walk(root: Path, label: str, selected_stage: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            continue
        probe = read_probe(path)
        stages = stages_for(relative, probe)
        kind = classify(relative)
        foundational = label == "spec" and (
            is_authoritative(relative, kind, label)
            or kind in {"specification", "review", "evidence"}
        )
        in_scope = (
            selected_stage == "all"
            or selected_stage in stages
            or (selected_stage != "T0" and "T0" in stages)
            or (label == "project" and not stages)
            or foundational
        )
        data = path.read_bytes()
        records.append(
            {
                "id": f"{label}:{relative.as_posix()}",
                "source": label,
                "path": relative.as_posix(),
                "kind": kind,
                "stages": stages,
                "authoritativeCandidate": is_authoritative(relative, kind, label),
                "inScope": in_scope,
                "bytes": len(data),
                "lines": data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    return records


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--spec-root")
    parser.add_argument(
        "--stage",
        default="all",
        choices=["T0", "T1", "T2", "T3", "T4", "all"],
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    project_root = Path(args.project_root).expanduser().resolve()
    if not project_root.is_dir():
        raise SystemExit(f"project root is not a directory: {project_root}")
    spec_root = resolve_spec_root(project_root, args.spec_root)

    records = walk(spec_root, "spec", args.stage)
    if project_root != spec_root:
        records.extend(walk(project_root, "project", args.stage))
    records.sort(key=lambda item: item["id"])

    in_scope = [record for record in records if record["inScope"]]
    kinds = Counter(record["kind"] for record in in_scope)
    stages = Counter(stage for record in in_scope for stage in record["stages"])
    authorities = [
        record["id"] for record in in_scope if record["authoritativeCandidate"]
    ]
    roots = {"spec": git_state(spec_root)}
    if project_root != spec_root:
        roots["project"] = git_state(project_root)

    payload = {
        "schemaVersion": 1,
        "stage": args.stage,
        "roots": roots,
        "summary": {
            "totalFiles": len(records),
            "inScopeFiles": len(in_scope),
            "inScopeBytes": sum(record["bytes"] for record in in_scope),
            "authoritativeCandidates": len(authorities),
            "kinds": dict(sorted(kinds.items())),
            "stages": dict(sorted(stages.items())),
        },
        "authoritativeCandidateIds": authorities,
        "files": records,
    }

    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(
        f"Inventory written: {output} "
        f"({len(in_scope)} in-scope files, {len(authorities)} authority candidates)"
    )


if __name__ == "__main__":
    main()
