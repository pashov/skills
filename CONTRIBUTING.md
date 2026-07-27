# Contributing

## Pull request process

1. Branch from `main`.
2. Identify the affected Inferrex stage and normative artifacts.
3. Make the smallest role, workflow, script or reporting change that closes
   the stated gap.
4. Run every modified script and validate every modified skill.
5. Keep `VERSION` changes to the automated version workflow.
6. Explain how the change was tested and which false-positive or
   false-negative risk it addresses.

## Checklist

- [ ] Exact artifact, invariant, finding and test identifiers are preserved
- [ ] Normative claims, implementation facts and evidence are distinguished
- [ ] T0–T4 scope is explicit
- [ ] Counterexample and mutation attempts are required before `PASS`
- [ ] The six gate/deployment axes cannot be conflated
- [ ] Specification drift preflight passes, or the invoked skill was updated
      and its compatibility baseline advanced after validation
- [ ] A `SEALED` result is backed by an explicit current-tree-bound
      machine-readable specification seal
- [ ] No API keys, credentials, private evidence or customer content
- [ ] Scripts have been executed on representative input
- [ ] Modified skill folders pass `quick_validate.py`
- [ ] Archived Solidity material remains under `unused/` unless the pull
      request follows the restoration procedure

## What to contribute

- New attack roles for a concrete Inferrex trust boundary or cross-stage seam
- Better negative, concurrency, fault, mutation or provider-conformance probes
- Tighter finding validation and evidence-independence checks
- Safer deterministic inventory and closure-inspection tooling
- Report-format improvements that preserve machine-actionable identifiers
