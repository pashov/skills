# Closure report format

```markdown
# Inferrex closure review — {stage}

## Review identity
| Item | Value |
|---|---|
| Specification source commit/tree | |
| Evidence anchor / current commit | |
| Implementation commit | |
| Working tree | |
| Validation environment | |

## Stage verdict
**{CLOSED|OPEN|STALE|NOT_EVIDENCED|INDETERMINATE}**

## T0 independent state axes
| Axis | Recorded state | Authority | Verified | Notes |
|---|---|---|---|---|

For T1–T4, retain this table and add:

## Stage evidence state
| Obligation | Required backend/layer | Evidence | Fresh result | Verdict |
|---|---|---|---|---|

## Structural checks
| Check | Result | Evidence |
|---|---|---|

## Executed validation
| Command | Environment | Exit | Output SHA-256 | Bound record |
|---|---|---:|---|---|

## Finding closure

### {finding ID}: {title}
- **Verdict:**
- **Canonical authority:**
- **Bound source:**
- **Correction:**
- **Original counterexample replay:**
- **Mutation result:**
- **Evidence and independence:**
- **Outstanding requirement:**

## Stale, missing or unbound evidence

## Limitations
```

Do not replace a recorded state with the reviewer's preferred state. Report
the recorded state and verification result separately.
