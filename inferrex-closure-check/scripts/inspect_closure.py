#!/usr/bin/env python3
"""Inspect Inferrex closure structure without executing repository checkers."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

AXES = {
    "artifactComplete": {"complete", "incomplete"},
    "objectiveValidation": {"passed", "failed", "not_run"},
    "reviewFindings": {"closed", "open"},
    "userAcceptance": {"accepted", "pending", "rejected"},
    "gate": {"passed", "blocked"},
    "deployment": {"active", "inactive"},
}
REQUIRED_T0 = {
    "closureRecord": "validation/closure-record.json",
    "gateState": "validation/gate-state.json",
    "reviewRegistry": "validation/review-resolution-registry.json",
    "sourceManifest": "validation/source-manifest.json",
    "checkResults": "validation/check-results.json",
    "cleanInstallTranscript": "validation/clean-install-transcript.json",
    "sourceFiles": "inferrex-source-files.json",
}
HASH_BINDINGS = {
    "manifestSha256": "validation/source-manifest.json",
    "reviewRegistrySha256": "validation/review-resolution-registry.json",
    "checkResultsSha256": "validation/check-results.json",
    "cleanInstallTranscriptSha256": "validation/clean-install-transcript.json",
    "gateStateSha256": "validation/gate-state.json",
    "checkerSha256": "inferrex-evidence-checker.cjs",
}
ARCHIVE_SUFFIXES = {".zip", ".tar", ".tgz", ".gz", ".7z", ".rar"}


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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_tree_sha(root: Path, paths: set[str]) -> tuple[str | None, str | None]:
    try:
        with tempfile.TemporaryDirectory(prefix="inferrex-closure-tree-") as temporary:
            target_root = Path(temporary)
            for relative in sorted(paths):
                source = root / relative
                if not source.is_file():
                    return None, f"missing canonical source file: {relative}"
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
                ["git", "add", "-f", "--", *sorted(paths)],
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
            return result.stdout.strip(), None
    except (OSError, subprocess.CalledProcessError) as exc:
        return None, str(exc)


def read_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)


def add(
    checks: list[dict[str, Any]],
    check_id: str,
    status: str,
    evidence: Any,
) -> None:
    checks.append({"id": check_id, "status": status, "evidence": evidence})


def identity(obj: Any) -> dict[str, Any] | None:
    if isinstance(obj, dict) and isinstance(obj.get("source"), dict):
        source = obj["source"]
        return {
            "repository": source.get("repository"),
            "commitSha": source.get("commitSha"),
            "treeSha": source.get("treeSha"),
        }
    return None


def resolve_spec(project: Path, supplied: str | None) -> Path:
    if supplied:
        path = Path(supplied).expanduser().resolve()
        if not path.is_dir():
            raise SystemExit(f"spec root is not a directory: {path}")
        return path
    if (project / "inferrex-t0-protocol-correctness-spec.md").is_file():
        return project
    sibling = project.parent / "core-specification"
    if sibling.is_dir():
        return sibling.resolve()
    raise SystemExit("could not locate core-specification; pass --spec-root")


def inspect_history(
    root: Path,
    source_identity: dict[str, Any] | None,
    source_paths: set[str],
    validation_paths: set[str],
    non_normative: set[str],
    checks: list[dict[str, Any]],
) -> None:
    if not source_identity or not source_identity.get("commitSha"):
        add(checks, "source-history", "UNKNOWN", "missing source commit identity")
        return
    source_commit = str(source_identity["commitSha"])
    exists, _ = run_git(root, "cat-file", "-e", f"{source_commit}^{{commit}}")
    if not exists:
        add(
            checks,
            "source-history",
            "UNKNOWN",
            "source commit is unavailable locally; fetch full history",
        )
        return

    diff_ok, source_drift = run_git(
        root,
        "diff",
        "--name-only",
        f"{source_commit}..HEAD",
        "--",
        *sorted(source_paths),
    )
    drift = source_drift.splitlines() if diff_ok and source_drift else []
    add(
        checks,
        "source-commit-canonical-paths",
        "PASS" if diff_ok and not drift else "FAIL",
        {"changedCanonicalPaths": drift},
    )

    ok, head = run_git(root, "rev-parse", "HEAD")
    if not ok:
        add(checks, "current-head", "UNKNOWN", head)
        return
    if head == source_commit:
        add(
            checks,
            "detached-evidence-anchor",
            "NOT_PRESENT",
            "HEAD is the source commit; no descendant evidence anchor",
        )
        return

    ancestor, _ = run_git(root, "merge-base", "--is-ancestor", source_commit, head)
    if not ancestor:
        add(
            checks,
            "source-ancestry",
            "FAIL",
            {"sourceCommit": source_commit, "head": head},
        )
        return
    add(
        checks,
        "source-ancestry",
        "PASS",
        {"sourceCommit": source_commit, "head": head},
    )

    ok, descendants = run_git(root, "rev-list", "--reverse", f"{source_commit}..{head}")
    commits = descendants.splitlines() if ok and descendants else []
    anchor = None
    for commit in commits:
        parents_ok, parents = run_git(root, "show", "-s", "--format=%P", commit)
        if parents_ok and source_commit in parents.split():
            changed_ok, changed = run_git(
                root, "diff-tree", "--no-commit-id", "--name-only", "-r", commit
            )
            paths = set(changed.splitlines()) if changed_ok and changed else set()
            if paths and all(path.startswith("validation/") for path in paths):
                anchor = commit
                break
    add(
        checks,
        "detached-evidence-anchor",
        "PASS" if anchor else "FAIL",
        {"anchor": anchor, "searchedCommits": len(commits)},
    )

    if anchor:
        changed_ok, changed = run_git(root, "diff", "--name-only", f"{anchor}..{head}")
        changed_paths = set(changed.splitlines()) if changed_ok and changed else set()
        protected = source_paths | validation_paths
        drift = sorted((changed_paths & protected) - non_normative)
        add(
            checks,
            "descendant-source-validation-drift",
            "PASS" if not drift else "FAIL",
            {"changedProtectedPaths": drift},
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--spec-root")
    parser.add_argument(
        "--stage",
        default="T0",
        choices=["T0", "T1", "T2", "T3", "T4"],
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    project = Path(args.project_root).expanduser().resolve()
    if not project.is_dir():
        raise SystemExit(f"project root is not a directory: {project}")
    spec = resolve_spec(project, args.spec_root)
    checks: list[dict[str, Any]] = []
    objects: dict[str, Any] = {}

    for key, relative in REQUIRED_T0.items():
        path = spec / relative
        if not path.is_file():
            add(checks, f"present:{key}", "NOT_PRESENT", relative)
            continue
        value, error = read_json(path)
        if error:
            add(checks, f"json:{key}", "FAIL", {"path": relative, "error": error})
        else:
            objects[key] = value
            add(checks, f"json:{key}", "PASS", relative)

    closure = objects.get("closureRecord")
    for field, relative in HASH_BINDINGS.items():
        path = spec / relative
        expected = closure.get(field) if isinstance(closure, dict) else None
        if not path.is_file() or expected is None:
            add(
                checks,
                f"hash:{field}",
                "NOT_PRESENT",
                {"path": relative, "expected": expected},
            )
            continue
        actual = sha256(path)
        add(
            checks,
            f"hash:{field}",
            "PASS" if actual == expected else "FAIL",
            {"path": relative, "expected": expected, "actual": actual},
        )

    identities = {
        key: identity(objects.get(key))
        for key in ("closureRecord", "gateState", "reviewRegistry", "sourceManifest")
    }
    present_identities = [value for value in identities.values() if value]
    same_identity = bool(present_identities) and all(
        value == present_identities[0] for value in present_identities
    )
    add(
        checks,
        "source-identity-consistency",
        "PASS" if same_identity else "FAIL",
        identities,
    )

    gate = objects.get("gateState")
    if isinstance(gate, dict):
        actual_axes = {key for key in gate if key in AXES}
        exact = actual_axes == set(AXES)
        values_valid = all(gate.get(key) in allowed for key, allowed in AXES.items())
        add(
            checks,
            "gate-axes-exact-and-valid",
            "PASS" if exact and values_valid else "FAIL",
            {key: gate.get(key) for key in AXES},
        )
        if gate.get("userAcceptance") != "accepted":
            independent = gate.get("gate") == "blocked" and gate.get("deployment") == "inactive"
            add(
                checks,
                "pending-acceptance-does-not-activate",
                "PASS" if independent else "FAIL",
                {
                    "userAcceptance": gate.get("userAcceptance"),
                    "gate": gate.get("gate"),
                    "deployment": gate.get("deployment"),
                },
            )

    registry = objects.get("reviewRegistry")
    if isinstance(registry, dict) and isinstance(registry.get("findings"), list):
        findings = registry["findings"]
        ids = [item.get("id") for item in findings if isinstance(item, dict)]
        duplicate_ids = sorted({item for item in ids if ids.count(item) > 1})
        missing_evidence = [
            item.get("id")
            for item in findings
            if isinstance(item, dict)
            and item.get("remediationState") == "objectively_validated"
            and not item.get("evidence")
        ]
        add(
            checks,
            "review-finding-registry-shape",
            "PASS" if not duplicate_ids and not missing_evidence else "FAIL",
            {
                "findingCount": len(findings),
                "duplicateIds": duplicate_ids,
                "validatedWithoutEvidence": missing_evidence,
            },
        )

    source_files = objects.get("sourceFiles")
    source_paths: set[str] = set()
    non_normative: set[str] = set()
    if isinstance(source_files, dict):
        source_paths = set(source_files.get("paths", []))
        non_normative = set(source_files.get("nonNormativePaths", []))
    tracked_ok, tracked_text = run_git(spec, "ls-files")
    tracked = set(tracked_text.splitlines()) if tracked_ok and tracked_text else set()
    validation_paths = {
        relative
        for relative in REQUIRED_T0.values()
        if relative.startswith("validation/")
    }
    classified = source_paths | non_normative | validation_paths
    unexpected = sorted(tracked - classified)
    missing = sorted(path for path in source_paths | non_normative if not (spec / path).is_file())
    archives = sorted(path for path in tracked if Path(path).suffix.lower() in ARCHIVE_SUFFIXES)
    add(
        checks,
        "open-world-path-classification",
        "PASS" if tracked_ok and not unexpected and not missing else "FAIL",
        {"unexpected": unexpected, "missing": missing, "trackedCount": len(tracked)},
    )
    add(
        checks,
        "no-canonical-archives",
        "PASS" if not archives else "FAIL",
        {"archivePaths": archives},
    )

    source_identity = next((value for value in present_identities if value), None)
    actual_tree, tree_error = canonical_tree_sha(spec, source_paths)
    expected_tree = source_identity.get("treeSha") if source_identity else None
    add(
        checks,
        "canonical-source-tree-identity",
        "PASS"
        if actual_tree is not None and expected_tree is not None and actual_tree == expected_tree
        else "FAIL",
        {"expected": expected_tree, "actual": actual_tree, "error": tree_error},
    )
    inspect_history(
        spec,
        source_identity,
        source_paths,
        validation_paths,
        non_normative,
        checks,
    )

    stage_manifests = []
    for root, label in ((spec, "spec"), (project, "project")):
        if root != spec or label == "spec":
            for path in sorted(root.rglob("*.json")):
                if ".git" in path.parts or ".inferrex-review" in path.parts:
                    continue
                name = path.name.lower()
                try:
                    probe = path.read_bytes()[:4096]
                except OSError:
                    continue
                named_candidate = "stage" in name and "evidence" in name
                typed_candidate = b"inferrex.stage-evidence" in probe
                if (not named_candidate and not typed_candidate) or "schema" in name:
                    continue
                value, error = read_json(path)
                if (
                    error is None
                    and isinstance(value, dict)
                    and value.get("schemaVersion") != "inferrex.stage-evidence.v2"
                ):
                    continue
                stage_manifests.append(
                    {
                        "source": label,
                        "path": path.relative_to(root).as_posix(),
                        "stage": value.get("stage") if isinstance(value, dict) else None,
                        "validJson": error is None,
                    }
                )
    if args.stage != "T0":
        matching = [
            item for item in stage_manifests if str(item.get("stage")).upper() == args.stage
        ]
        add(
            checks,
            f"stage-evidence-manifest:{args.stage}",
            "PASS" if matching else "NOT_PRESENT",
            {"matching": matching, "allCandidates": stage_manifests},
        )

    spec_status_ok, spec_status = run_git(
        spec, "status", "--porcelain=v1", "--untracked-files=all"
    )
    project_status_ok, project_status = run_git(
        project, "status", "--porcelain=v1", "--untracked-files=all"
    )
    add(
        checks,
        "spec-working-tree-clean",
        "PASS" if spec_status_ok and not spec_status else "FAIL",
        spec_status.splitlines() if spec_status else [],
    )
    if project != spec:
        add(
            checks,
            "project-working-tree-clean",
            "PASS" if project_status_ok and not project_status else "FAIL",
            project_status.splitlines() if project_status else [],
        )

    status_counts: dict[str, int] = {}
    for check in checks:
        status_counts[check["status"]] = status_counts.get(check["status"], 0) + 1

    payload = {
        "schemaVersion": 1,
        "stage": args.stage,
        "roots": {
            "spec": {
                "path": str(spec),
                "dirty": bool(spec_status) if spec_status_ok else None,
                "changes": spec_status.splitlines() if spec_status else [],
            },
            "project": {
                "path": str(project),
                "dirty": bool(project_status) if project_status_ok else None,
                "changes": project_status.splitlines() if project_status else [],
            },
        },
        "sourceIdentities": identities,
        "recordedGateAxes": {key: gate.get(key) for key in AXES}
        if isinstance(gate, dict)
        else None,
        "stageEvidenceManifests": stage_manifests,
        "checks": checks,
        "statusCounts": dict(sorted(status_counts.items())),
    }
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"Closure inspection written: {output} ({status_counts})")


if __name__ == "__main__":
    main()
