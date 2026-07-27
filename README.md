# Inferrex adversarial review skills

AI-assisted review workflows for the Inferrex specification and its T0–T4
implementation stages.

The production skills in this repository treat the canonical specification as
the source of normative claims. They distinguish specification defects,
implementation defects, evidence gaps, residual risks, gate state and
deployment state instead of translating Solidity exploit heuristics into an
off-chain system.

## Install and run

```text
Install https://github.com/inferrex-ai/pashov-skills-inferrex and run inferrex-x-ray on the repository
Install https://github.com/inferrex-ai/pashov-skills-inferrex and red-team Inferrex for T0 through T4
Install https://github.com/inferrex-ai/pashov-skills-inferrex and verify Inferrex closure evidence for T0
```

Each skill also accepts a narrower stage:

```text
run inferrex-x-ray --stage T3
run inferrex-redteam --stage T1
run inferrex-closure-check --stage T4
```

## Specification evolution preflight

Every production skill must check the current canonical
`inferrex-ai/core-specification` source tree before beginning its normal
workflow. The preflight compares that tree with the skill-specific reviewed
baseline in `compatibility/spec-baseline.json`.

- `COMPATIBLE`: continue normally.
- `REWRITE_REQUIRED`: stop before reviewing. Inspect the specification diff
  for new or changed capabilities—including stitching, composition, new
  modalities, protocol objects, endpoints, markets or stage obligations—and
  rewrite the invoked skill's roles, references, scripts and judging rules as
  necessary. Validate the revised skill, update only its reviewed baseline,
  rerun the preflight, then continue.
- `SEALED`: remove specification drift from consideration for that invocation
  and continue normally. This status is valid only when the canonical
  specification contains an explicit, committed and unchanged machine-readable
  specification seal that names a gate and binds the current canonical
  source-tree hash.

Ordinary artifact completeness, objective validation, finding closure, user
acceptance, gate passage and deployment activation are not specification seals.
A stale or prose-only seal must not disable the preflight. If the check is
missing, cannot resolve the specification, or returns an unknown result, the
agent must not silently proceed.

## Production skills

| Skill | Purpose |
|---|---|
| [inferrex-x-ray](inferrex-x-ray/) | Map normative authority, trust boundaries, stages, invariants, attack surfaces and available evidence before review |
| [inferrex-redteam](inferrex-redteam/) | Run a multi-role adversarial review of the T0 specification and T1–T4 implementation/evidence |
| [inferrex-closure-check](inferrex-closure-check/) | Challenge finding dispositions, evidence provenance and the independence of gate and deployment states |

## Stage scope

| Stage | Review target |
|---|---|
| T0 | Protocol correctness packets, schemas, models, vectors, checkers, architecture, closure and MVI-0 constraints |
| T1 | Protocol kernel, migrations, database roles, real-PostgreSQL enforcement and required concurrency tests |
| T2 | Mocked MVI-0 economic loop, durable failpoints, replay and duplicate-value prevention |
| T3 | Text Chat Completions and receipt API, streaming/output barriers and unsupported-semantics handling |
| T4 | Seller agent, credential boundary, proof adapters and concrete provider conformance |

Solidity remains relevant where an Inferrex stage actually owns chain code
(principally later production-rail work). The original Solidity-oriented
skills are retained, but are not part of the production Inferrex review path.
See [unused/README.md](unused/README.md) for the inventory and restoration
procedure.

## Review standard

- Cite exact artifacts, sections, identifiers and test cases.
- Treat assertion counts as metadata, not proof.
- Separate normative rules from implementation and independent evidence.
- Attempt a concrete counterexample, failure schedule, mutation or bypass
  before returning `PASS`.
- Never infer user acceptance, gate passage or deployment activation from an
  objective checker result.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Report security-sensitive defects using
the private reporting route described in [SECURITY.md](SECURITY.md).
