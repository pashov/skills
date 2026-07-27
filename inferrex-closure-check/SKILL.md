---
name: inferrex-closure-check
description: Verify Inferrex adversarial-review closure, source/evidence provenance and stage gate evidence for T0-T4. Use for "check Inferrex closure", "verify dispositions", "validate Gate T0 evidence", "is this finding closed", "check stage evidence", or requests to challenge manifests, review registries, detached evidence anchors, gate axes, acceptance or deployment state.
---

# Inferrex Closure Check

Verify that a finding or stage obligation is closed against exact source bytes
and independent evidence. Do not red-team the complete protocol here; use
`inferrex-redteam` for new attack discovery.

Resolve `$SKILL_DIR` to this skill's directory.

## Phase 0 — Specification compatibility (mandatory)

Resolve the specification root, then run before inspecting closure:

```text
python3 $SKILL_DIR/../compatibility/check_spec_compatibility.py \
  --skill inferrex-closure-check \
  --project-root {project-root} \
  --spec-root {spec-root}
```

- `COMPATIBLE`: continue.
- `SEALED`: record the named, current-tree-bound specification seal, remove
  drift from consideration and continue.
- `REWRITE_REQUIRED`: stop. Inspect the changed specification for new feature,
  gate, manifest or evidence semantics, rewrite this skill's inspection,
  closure criteria and verdict rules as necessary, validate the skill, advance
  only its compatibility baseline and rerun Phase 0 before continuing.

If the shared checker is unavailable, apply the root README policy manually.
Never silently skip this phase.

## Inputs

Accept:

- `--stage T0|T1|T2|T3|T4` (default `T0`);
- `--spec-root PATH`;
- `--project-root PATH` (default current working directory);
- `--finding ID` to narrow to one or more review findings;
- `--structural-only` to avoid executing repository validators.

Write:

`{project-root}/.inferrex-review/closure/{stage-lower}/inspection.json`
and `report.md`.

Never edit source, registries, dispositions, gate state or validation evidence.

## Phase 1 — Structural inspection

Run:

```text
python3 $SKILL_DIR/scripts/inspect_closure.py \
  --project-root {project-root} \
  --spec-root {spec-root} \
  --stage {stage} \
  --output {output-dir}/inspection.json
```

Read the inspection and `references/closure-criteria.md`.

Resolve every `FAIL`, `WARN`, `UNKNOWN` and `NOT_PRESENT`. A shallow clone or
missing history produces `UNKNOWN`, not a pass. Fetch/read the necessary
history when authorized and available.

## Phase 2 — Execute bound validation

Skip only with `--structural-only`.

Use a clean temporary checkout of the exact source/evidence identity. Do not
run closure commands in a dirty working tree or let package installation alter
reviewed bytes.

For T0:

1. verify exact Node/npm/dependency pins and the committed lockfile;
2. run `npm ci`;
3. run `npm run check:source`;
4. run `npm run evidence:verify`;
5. capture exit status and SHA-256 of stdout/stderr;
6. compare the executed checker, manifest, registry, gate state and result
   digests with the closure record.

For T1–T4:

1. locate the stage evidence manifest and validate it against
   `inferrex-stage-evidence-manifest.schema.json`;
2. verify source/spec/implementation commit identities;
3. run every command named by the manifest in a clean pinned environment;
4. confirm required test layers and named stage obligations are present;
5. confirm a real backend/provider is used where the claim owns one;
6. compare fresh output digests with recorded evidence.

Do not substitute PGlite/models for T1 real PostgreSQL, mock adapters for T4
provider behavior, or unit-level streaming for T3 proxy/wire semantics.

## Phase 3 — Finding closure

For each selected finding:

1. locate the canonical current review entry;
2. verify exact finding ID, severity, source identity and remediation state;
3. inspect every semantic evidence locator, assertion, test ID, expected result,
   artifact hash and executable output digest;
4. replay the original counterexample or an equivalent independent regression;
5. mutation-test the corrective control;
6. verify no later source change invalidates the closure;
7. keep user acceptance separate from objective remediation.

An older disposition, prose claim or `objectively_validated` label does not
close a finding without bound evidence that survives the counterexample.

## Phase 4 — Verdict

Use one verdict per finding and one per stage:

- `CLOSED`: exact current bytes, independent evidence and regression all pass;
- `OPEN`: correction or required evidence is absent/failing;
- `STALE`: evidence was valid for different source/dependency/config bytes;
- `NOT_EVIDENCED`: a claim or disposition exists without sufficient evidence;
- `INDETERMINATE`: required history, dependency or external authority is
  unavailable.

Report the six T0 axes independently:

- artifact completeness;
- objective validation;
- review-finding closure;
- user acceptance;
- gate passage;
- deployment activation.

Never synthesize one from another. For T1–T4, report stage evidence separately
from Gate T0 and activation.

Follow `references/report-formatting.md`. Include exact commands, environments,
commit/tree identities, digests, counterexample regressions and unresolved
dependencies.

## Hard rules

- No closure on assertion count alone.
- No closure from self-generated expected values without mutation or an
  independent oracle.
- No closure against dirty, uncommitted or unidentified bytes.
- No closure when a required real backend/provider is replaced by a mock.
- No direct edits to make a checker, disposition or gate state pass.
- Missing evidence is not an accepted residual risk unless a current authority
  explicitly owns and gates it.
