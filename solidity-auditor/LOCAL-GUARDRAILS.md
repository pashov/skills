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
- transient reserve/balance skew paths that can write queued or deferred global state
- pair / AMM inventory discount hooks such as `balanceOf(pair)` overrides
- any preview, quote, snapshot, cached-price, pending, or finalized-status path that later influences a value-moving action
- any path where one actor creates entitlement and a later same or different actor realizes it against shared inventory

For each exploit family, classify status as exactly one of:
- `completed`
- `disproved`
- `blocked`
- `irrelevant`

If any top-value public exploit family is still `blocked`, the audit is not complete.

## Dependency Closure Rules

The scope root is the **entire folder tree** the user points at, not just detected Solidity source directories.

Before finalizing, inventory bundle artifact families such as:
- `main-project/`
- `related-contracts/`
- `abi/`
- `bytecode/`
- `decompiled/`
- `project.json`
- `contract-list.json`
- `contract-variables.json`

If any runtime-relevant artifact family inside that tree is unclassified, coverage is incomplete.

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
- decompiled source
- ABI / selector map
- deployment context

Distinguish artifact absence from artifact insufficiency.

If a local file exists but it contains only raw runtime / creation bytecode, do not describe it as a "missing artifact". Label it explicitly as:

- `bytecode-only artifact present`

and then ask only for the missing quality needed to continue, such as:

- verified source
- decompiled source
- ABI
- selector/function map
- live dependency mapping

Do not convert a critical unresolved path into a low-priority lead just to finish the report.

## Primitive-to-Exploit Rules

Finding a dangerous primitive is not enough.

Before ranking a finding as primary, reconstruct:

`public trigger -> helper/dependency path -> state mutation -> extraction leg -> profit`

If that chain is incomplete, keep tracing or mark coverage incomplete.

Also reconstruct the generic lifecycle whenever value is not paid out immediately:

`temporary assumption or source-of-truth split -> persistent artifact / entitlement / finality bit -> later realization or obligation release -> profit or insolvency`

For reserve-priced or AMM-like systems, also reconstruct this family explicitly before clearing it:

`temporary donation/skew -> classifier or bucket write -> donation recovery -> stale-state realization -> final extraction trade`

Do not keep component bugs as separate Leads if they compose into a single public exploit path.

If:
- Lead A creates the state precondition
- Lead B realizes it
- and the combined path reaches outsider extraction or escaped liability

then merge them and report one Finding that describes the full composition.

## Mainnet-Fork Proof Rules

If the user asks for `poc-mainnet-fork`, the artifact must validate the real deployment, not an abstract mechanism.

The fork script must:
- use the same live addresses as mainnet for the critical path
- use a real fork block and real fork balances/config
- state the exact live reserves, balances, or value ceilings that bound extraction
- prove either:
  - `exploit closes on live fork`, or
  - `live fork blocker prevents profit`

The fork script must not:
- replace the live protocol path with mocks
- patch storage to force exploit success
- mint fake assets that an attacker cannot obtain from the forked state
- present a synthetic success case as a live mainnet result

If a mainnet-fork PoC does not close into profit on the real deployment, the report must be downgraded accordingly.

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
- small live proceeds were not used as the sole reason to demote a real public issue to a Lead
- the audit checked for source-of-truth vs derived-state splits, deferred realization artifacts, and false finality rather than only named bug families
- fuzz / invariant testing was run when practical for the core accounting paths, or the exact blocker was stated
- any lead that could plausibly compose with another case was explicitly tested for promotion into a Finding
- every live-status statement names the concrete addresses involved, including proxy / implementation / facet / diamond / router / pool / helper mappings where relevant
