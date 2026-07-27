# X-ray output templates

Keep the files factual and cross-linked. Use `N/A` or `NOT PRESENT` when input
is absent.

## `overview.md`

```markdown
# Inferrex X-Ray — {stage}

## Inputs
| Root | Commit | Working tree | Role |
|---|---|---|---|

## Review boundary
- Included:
- Excluded:
- Normative dependency:

## System summary

## Stage objective and exit condition

## Highest-priority seams
1. [surface](attack-surfaces.md#...)

## Coverage summary
| Map | Count | Unresolved |
|---|---:|---:|
```

## `authority-map.md`

```markdown
# Normative authority map

## Precedence

## Artifact register
| Artifact | Kind | Authority | Supersedes / depends on | Duplicated definitions |
|---|---|---|---|---|

## Semantic-diff queue
| ID | Definition | Artifact A | Artifact B | Status |
|---|---|---|---|---|

## Historical and derived material
```

## `stage-matrix.md`

```markdown
# T0–T4 stage matrix

| Stage | Objective | Normative inputs | Implementation owner | Required evidence | Status |
|---|---|---|---|---|---|

## Selected-stage obligations
| ID | Obligation | Enforcement owner | Evidence owner | Artifact |
|---|---|---|---|---|

## Dependency and deferral risks
```

## `trust-boundaries.md`

```markdown
# Trust and data boundaries

| Boundary | From → to | Data / authority | Credential or signer | Spec trust | Required resistance |
|---|---|---|---|---|---|

## Plaintext and secret flow

## Durable authority

## External dependencies
```

## `invariants.md`

```markdown
# Invariant map

| ID | Rule | Normative source | Enforcement owner | Evidence owner | Specification | Implementation | Evidence |
|---|---|---|---|---|---|---|---|

## Contradictions and unknowns
```

Use only `SPECIFIED`, `IMPLEMENTED`, `EVIDENCED`, `CONTRADICTED`,
`NOT PRESENT` and `UNKNOWN`. Do not collapse the last three columns.

## `attack-surfaces.md`

```markdown
# Attack surfaces

## AS-{N}: {surface}
- **Stage:**
- **Adversary control:**
- **Trust boundary:**
- **Normative claims at risk:**
- **Artifacts / locations:**
- **Counterexample class:**
- **Existing evidence:**
- **Priority:** critical | high | medium | low
```

## `evidence-map.md`

```markdown
# Evidence map

| Claim / invariant | Required evidence | Present artifact | Backend / oracle | Negative or mutation case | Independence | Result |
|---|---|---|---|---|---|---|

## Evidence that cannot close its claim

## Missing independent or real-backend checks
```
