# Adversarial review report

## Markdown structure

```markdown
# Inferrex adversarial review — {stage}

## Review identity
| Item | Value |
|---|---|
| Specification commit/tree | |
| Implementation/evidence commit | |
| Working tree | |
| Review mode | independent roles / single context |
| Roles completed | |
| Scope and exclusions | |

## Verdict
One paragraph. State blockers without implying acceptance, gate passage or
deployment activation.

## Finding summary
| ID | Severity | Disposition | Stage | Invariant / axis | Title |
|---|---|---|---|---|---|

## Findings

### IRX-{STAGE}-{NNN}: {title}
- **Severity:**
- **Disposition:**
- **Stage / owner:**
- **Contributing roles:**
- **Authoritative claim:** `path:line` — identifier
- **Affected invariants / axes:**
- **Counterexample:**
- **Trace:**
- **Evidence present:**
- **Evidence independence:**
- **Smallest correction:**
- **Required closure evidence:**
- **Confidence:**

## Leads

## Independent pass checks

## Cross-stage chains

## Coverage
| Role | Claims attacked | Findings | Leads | Pass checks |
|---|---:|---:|---:|---:|

## Disposition counts
| Disposition | Count |
|---|---:|

## Limitations
```

Sort by severity, then stable ID. Preserve raw mechanism detail when
deduplicating. Do not recommend editing a disposition or gate state before the
corrected source and independent evidence exist.

## `findings.json`

Use:

```json
{
  "schemaVersion": 1,
  "stage": "T0|T1|T2|T3|T4|all",
  "reviewIdentity": {},
  "findings": [],
  "leads": [],
  "passChecks": [],
  "counts": {}
}
```

Each finding object must carry every field shown in the Markdown finding
block plus `id`, `groupKey` and `roles`.
