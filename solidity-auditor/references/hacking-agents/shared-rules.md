# Shared Scan Rules

## Reading

Your bundle has two sections:

1. **Core source** (inline) — read in parallel chunks (offset + limit), compute offsets from the line count in your prompt.
2. **Peripheral file manifest** — file paths under `# Peripheral Files (read on demand)`. Read only those relevant to your specialty.

If the target contract delegates pricing, reserve accounting, or oracle logic to a helper / hook / library / sibling module, those files are mandatory reading, not optional periphery. A wrapper-only read is an audit failure.

When matching function names, check both `functionName` and `_functionName` (Solidity convention).

## Cross-contract patterns

When you find a bug in one contract, **weaponize that pattern across every other contract in the bundle.** Search by function name AND by code pattern. Finding native/ERC20 confusion in `ContractA.onRevert` means you check every other contract's `onRevert` — missing a repeat instance is an audit failure.

For pricing systems, search across contract boundaries: helper returns, hook callbacks, library math, and reserve/state writers are one exploit surface. If a wrapper uses `getAmountOut`, `getUnspecifiedAmount`, custom `price`, `ln`, `pow`, or direct reserve writes, inspect every defining file before deciding there is no bug.
If a token / hook system can queue a reserve mutation in one function and realize it later in another, collapse the queueing path, the realization path, and any public upstream trigger into one exploit surface. Do not leave the end-to-end path fragmented across multiple softer findings.
If a contract can mutate pair inventory and then call `sync()` / reserve refresh, treat it as a public reserve-destruction exploit candidate until a concrete reachability or profitability refutation is found.

After scanning: escalate every finding to its worst exploitable variant (DoS may hide fund theft). Then revisit every function where you found something and attack the other branches.
Equality conditions are attack surface. If two roles, accounts, assets, ids, or buckets can be attacker-chosen to the same value, assume aliasing until the code proves otherwise. For any mint / redeem / borrow / repay / liquidate path, explicitly test whether two local storage references can resolve to the same slot and whether sequential writes still net correctly.
For hook-driven tokens and router/pair systems, reconstruct this exploit chain before dropping or demoting a candidate: `how inventory is sourced -> how bad state is queued -> how queued state is realized -> how the final reserve distortion is monetized`.
Compose weak signals before dropping them. If two leads share an id, asset, status flag, role, approval, helper, dependency, time boundary, or storage bucket, synthesize one combined exploit attempt.
False finality is value-relevant: if code can mark `paid`, `distributed`, `settled`, `completed`, `cancelled`, or `claimed` without reconciling actual token/ETH/NFT movement, test payer-caller collusion and recovery/retry behavior before demotion.

## Do not report

Admin-only functions doing admin things. Standard DeFi tradeoffs (MEV, rounding dust, first-depositor with MINIMUM_LIQUIDITY). Self-harm-only bugs. "Admin can rug" without a concrete mechanism.

## Output

Return structured blocks only — no preamble, no narration. Exception: vector scan agent outputs its classification block first.

FINDINGs have concrete, unguarded, exploitable attack paths. LEADs have real code smells with partial paths — default to LEAD over dropping.

**Every FINDING must have a `proof:` field** — concrete values, traces, or state sequences from the actual code. No proof = LEAD, no exceptions.
For queued reserve-mutation / pair-burn findings, `proof:` must include the queueing write, the realization write, the public or helper-triggerable entrypoint that reaches realization, and the post-`sync()` extraction leg or a concrete reason that extraction is impossible.

**One vulnerability per item.** Same root cause = one item. Different fixes needed = separate items.

```
FINDING | contract: Name | function: func | bug_class: kebab-tag | group_key: Contract | function | bug-class
path: caller → function → state change → impact
proof: concrete values/trace demonstrating the bug
description: one sentence
fix: one-sentence suggestion

LEAD | contract: Name | function: func | bug_class: kebab-tag | group_key: Contract | function | bug-class
code_smells: what you found
description: one sentence explaining trail and what remains unverified
```

The `group_key` enables deduplication: `ContractName | functionName | bug_class`. Agents may add custom fields.
