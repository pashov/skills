# Finding validation

Apply the gates once, in order.

## Gate 1 — Authority

Identify the exact normative claim or current stage obligation.

- no authoritative claim and no material public-claim conflict → reject;
- historical/superseded text only → lead unless it can affect current closure;
- current rule, enforcement obligation or gate contract → continue.

## Gate 2 — Concrete counterexample

Prove that the counterexample, mutation, bypass or schedule is allowed by the
reviewed artifacts and selected stage.

- contradicted by an exact guard, transition, constraint or trust boundary →
  reject;
- one unresolved factual prerequisite → lead;
- legal and complete through the claimed violation → continue.

## Gate 3 — Evidence

Determine whether present evidence exercises this mechanism with an
independent expected result.

- independent evidence rejects the attack on the bound bytes/backend →
  reject or record `PASS-CHECK`;
- evidence is missing, self-referential, mocked where real behavior matters,
  stale or bound to different bytes → `EVIDENCE_GAP` or `STALE_CLOSURE`;
- evidence proves the implementation violates the rule →
  `IMPLEMENTATION_DEFECT`;
- the rule itself permits the violation → `SPEC_DEFECT`.

## Gate 4 — Stage ownership

- obligation belongs to the selected/current stage → continue;
- expressly deferred to a later stage with no earlier claim → out of scope;
- a later deferral leaves an earlier invariant or activation claim exposed →
  keep as cross-stage finding.

## Gate 5 — Materiality

Evaluate the strongest reachable impact:

- duplicate or lost value/execution;
- cross-tenant authority or data exposure;
- replay, forgery or proof rebinding;
- credential loss;
- non-convergent economic state or deadline failure;
- false specification/evidence/gate claim;
- unavailable or unsafe required API behavior.

No material effect and no closure integrity impact → reject or low lead.

## Severity

- `blocker`: permits false gate/activation, unbounded value/execution,
  credential compromise, systemic cross-tenant breach or failure of a
  non-negotiable safety invariant.
- `high`: breaks a named system invariant or required stage exit condition
  under realistic control.
- `medium`: bounded failure, incomplete negative space or evidence weakness
  that can hide a material defect.
- `low`: narrow ambiguity or residual weakness with a concrete correction.

## Confidence

Start at 100. Deduct 20 for one unresolved trace step, 15 for unverified real
dependency behavior, 10 for a specific but reachable configuration and 10 for
ambiguous authority. Below 75 remains a lead.

Reviewer convergence never repairs a failed gate.
