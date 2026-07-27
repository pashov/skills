# Inferrex T0–T4 stage model

Use the current canonical `inferrex-ai/core-specification` checkout as the
authority. This reference is a routing aid, not a substitute for reading it.

## T0 — protocol correctness and closure

| Packet | Primary review surface |
|---|---|
| T0.1 | trust, threat, data classes, retention, privacy and lock-safe external work |
| T0.2 | bounded primitives, canonical representation, time and numeric storage |
| T0.3 | signed object schemas, domain separation, purpose, environment, replay and authority |
| T0.4 | execution/economic state machines, transitions, deadlines and capacity |
| T0.5 | pricing, metering, maximum authorisation and reservation |
| T0.6 | receipt validity, evidence tiers, provenance and exclusive cutoffs |
| T0.7 | immutable balanced ledger, clearing and customer-asset coverage |
| T0.8 | database invariants, roles, grants, transaction bundles and retention |
| T0.9 | error classes, retries, idempotency, recovery and deterministic lock order |
| T0.10 | deployable units, module boundaries, test layers, source closure and evidence contracts |

T0 review must include the umbrella specification, implementation tracker,
MVI-0 profile, reviews/dispositions, source allowlist, schemas, vectors, models,
reference DDL, executable checkers and detached validation artifacts.

## T1 — protocol kernel and PostgreSQL enforcement

Objective: implement the protocol kernel, migrations, accepted database roles
and versioned write contracts against pinned real PostgreSQL.

Required concurrency contracts:

- `T1-CONC-LEDGER-001`: unique gap-free ledger sequencing with rollback reuse;
- `T1-CONC-LOCK-002`: complete deterministic lock order without deadlock;
- `T1-CONC-CAPACITY-003`: no shared concurrency or TPM oversubscription;
- `T1-CONC-REVOCATION-004`: signer intake/revocation serial order;
- `T1-CONC-OUTBOX-005`: same-transaction constrained append and direct-DML denial;
- `T1-CONC-SAFETY-006`: hard-deadline disposition cannot be blocked by an
  ordinary quarantined predecessor.

Required test layers: TL0 static/reproducibility, TL1 unit/vector, TL2
property/model, TL3 PostgreSQL integration and TL6 security/privacy.

## T2 — mocked MVI-0 economic loop

Objective: exercise the accepted economic lifecycle through deterministic
local adapters and mocked external rails.

Primary attacks:

- crash after external acceptance but before durable acknowledgement;
- retry, replay or failpoint creates duplicate execution or value;
- holds never converge to settlement/release;
- outbox and authoritative state disagree;
- post-output reroute or invalid evidence changes an already-fixed economic
  outcome;
- mock behavior silently proves a property that real adapters do not offer.

Required test layers: TL2 property/model, TL3 PostgreSQL integration, TL4
component/conformance and TL5 system fault/recovery.

## T3 — Text Chat Completions and receipt API

Objective: implement the text Chat Completions and receipt surface with exact
wire, streaming and unsupported-semantics behavior.

Primary attacks:

- cross-tenant authorization, visibility or idempotency collisions;
- ambiguous price consent or stale account policy;
- SSE/proxy/buffer boundaries disagree with `OUTPUT_COMMITTED`;
- disconnect, cancellation and cutoff races alter the billable prefix;
- lost response cannot be replayed but economic effect persists;
- unsupported fields or semantics degrade silently;
- prompt, response, secrets or content-derived telemetry escape allowed
  boundaries;
- resource exhaustion bypasses backpressure or deadline progress.

Required test layers: TL0, TL1, TL4, TL5, TL6 and TL7.

## T4 — seller agent and proof adapters

Objective: implement the seller agent, authenticated execution protocol and
concrete proof/provider adapters while keeping reusable provider credentials
inside the seller boundary.

Primary attacks:

- credential exfiltration through logs, errors, telemetry, child processes or
  control-plane messages;
- unsigned, expired, replayed or unauthorised jobs reach an upstream;
- provider evidence is rebound to another request, service, environment or
  output;
- proof tier claims facts the concrete provider cannot attest;
- content canaries leak through the provider or seller boundary;
- ambiguous provider acceptance causes duplicate upstream work;
- provider billing/tokenization diverges from Inferrex metering;
- adapter fallback weakens signed tier policy or fail-closed behavior.

Required test layers: TL0, TL1, TL4, TL5, TL6 and TL7.

## Cross-stage invariant routing

Use the canonical `SYS-*` table. At minimum:

- T1 owns enforcement for economic, replay, atomicity, signed-object,
  capacity and deadline-progress invariants.
- T2 owns end-to-end convergence, duplicate-effect and mocked-loop evidence.
- T3 owns replay, unsupported-semantics and post-output reroute behavior.
- T4 owns durable upstream eligibility, credential containment, signed-object
  verification and exact proof-tier evidence.

Never close a T0 rule solely because a later stage is planned. Never claim a
later stage passes solely because the T0 model contains its obligation.
