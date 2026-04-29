# Local Audit Guardrails

These rules apply to every exploit-hunting audit in this workspace.

## Completion Rules

Do not issue a final audit report while any critical public value path is unresolved.

Critical paths include:
- deposit
- withdraw
- claim
- reward settlement
- mint
- burn
- liquidation
- sync
- swap-back / reserve maintenance
- helper-triggered payout paths
- `receive()` / `fallback()` entrypoints

For each exploit family, classify status as exactly one of:
- `completed`
- `disproved`
- `blocked`
- `irrelevant`

If any top-value public exploit family is still `blocked`, the audit is not complete.

## Dependency Closure Rules

If a critical path depends on:
- a proxy
- a selector-only call
- a stored external contract address
- a helper contract
- a reward/mining/distributor contract
- a router/pair/oracle/pricing component

then resolve and analyze that dependency before finalizing.

If live addresses are available, resolve:
- proxy implementation
- ABI or function identities
- downstream dependencies on the same value path

Do not stop at the wrapper contract.

## Ask-The-User Rules

If critical-path completion is blocked after reasonable local resolution attempts, ask for the missing artifact before producing the final report.

Ask for whichever is needed:
- proxy addresses
- implementation addresses
- tx hashes
- traces
- balance diffs
- attacker/helper addresses
- verified source
- deployment context

Do not convert a critical unresolved path into a low-priority lead just to finish the report.

## Primitive-to-Exploit Rules

Finding a dangerous primitive is not enough.

Before ranking a finding as primary, reconstruct:

`public trigger -> helper/dependency path -> state mutation -> extraction leg -> profit`

If that chain is incomplete, keep tracing or mark coverage incomplete.

## Reward Path Rules

Treat these as critical exploit surfaces by default:
- `claim`
- `claimReward`
- `sendMining`
- `updatePool`
- `updatePrice`
- `harvest`
- `distribute`
- dust-trigger branches
- callback-trigger branches
- `tx.origin` gated reward flows

## Final Report Rules

Before sending the final report, explicitly confirm:
- the main public exploit path is completed or disproved
- all value-path dependencies were resolved or explicitly blocked
- any blocked path is disclosed as incomplete coverage, not silently downgraded
