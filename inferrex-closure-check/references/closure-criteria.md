# Inferrex closure criteria

## Closure object

Closure is a relationship between:

- an authoritative claim or finding;
- exact source/specification/implementation bytes;
- a corrective mechanism;
- independent regression or mutation evidence;
- a recorded result bound to those bytes;
- current authority and stage ownership.

No individual file is closure by itself.

## T0 source/evidence binding

Require:

1. complete ordinary-text source; archives are derived only;
2. a source commit containing normative artifacts, reviews, schemas, models,
   vectors, DDL and checkers;
3. a direct-child evidence anchor adding only `validation/*.json`;
4. closure record hashes matching manifest, review registry, checker results,
   clean-install transcript and gate state;
5. unchanged canonical source and validation bytes in any accepted merge
   descendant;
6. every tracked path classified as source, validation or explicitly
   non-normative;
7. exact identifier/path sets, not subset validation;
8. canonical review and historical review status unambiguous.

## Six independent T0 axes

| Axis | Allowed states | Closure rule |
|---|---|---|
| artifact completeness | complete / incomplete | Detached evidence only |
| objective validation | passed / failed / not_run | Fresh bound execution |
| review findings | closed / open | Canonical registry and counterexample regressions |
| user acceptance | accepted / pending / rejected | Explicit user authority only |
| gate | passed / blocked | Requires independent prerequisites including acceptance |
| deployment | active / inactive | Separate live-value activation authority |

A checker must not mutate or infer user acceptance, gate or deployment state.

## Finding evidence

Require exact:

- finding ID and canonical review authority;
- source commit/tree;
- artifact path and SHA-256;
- semantic locator and assertion;
- test case ID and expected result;
- executable output digest;
- independent counterexample regression;
- mutation showing the corrective control is live.

`objectively_validated` may describe remediation evidence while acceptance
remains pending. Keep those states separate.

## T1

Require T0 vector/database negatives plus pinned real PostgreSQL evidence for:

- `T1-CONC-LEDGER-001`;
- `T1-CONC-LOCK-002`;
- `T1-CONC-CAPACITY-003`;
- `T1-CONC-REVOCATION-004`;
- `T1-CONC-OUTBOX-005`;
- `T1-CONC-SAFETY-006`.

Reference DDL, PGlite and deterministic models cannot close these obligations.
Migration, privilege and restore state must be identified.

## T2

Require durable failpoint evidence across the mocked MVI-0 economic loop.
Every crash/retry schedule must converge without duplicate value or execution.
Record authoritative state, external/mock side effects and outbox/ledger
effects at each failpoint.

## T3

Require exact HTTP/SSE conformance, output-barrier and unsupported-semantics
evidence, plus cross-tenant authorization, retry/loss and buffering-boundary
tests. Unit handlers alone do not close proxy/kernel/client delivery claims.

## T4

Require credential and content canaries, authenticated seller-job negatives,
proof rebinding/replay negatives and concrete provider/runtime conformance.
Mocks cannot close real provider evidence, billing, identity or idempotency
claims.

## Verdict calibration

- `CLOSED`: current bytes and owning dependency pass the original
  counterexample and an effective mutation.
- `OPEN`: correction or required evidence fails or is missing.
- `STALE`: recorded evidence binds other bytes/configuration/dependency.
- `NOT_EVIDENCED`: status/claim lacks required independent evidence.
- `INDETERMINATE`: reviewer cannot obtain required history or external
  authority.
