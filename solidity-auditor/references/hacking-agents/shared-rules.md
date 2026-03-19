# Shared Scan Rules

## Reading

Your bundle has two source sections:

1. **Core source** (inline) — the main contracts, already in your bundle. Read your bundle file in parallel chunks (offset + limit). Compute all offsets from the line count in your prompt and issue every Read call in one message.
2. **Peripheral file manifest** — a list of file paths between the core source and your agent instructions, under the heading `# Peripheral Files (read on demand)`. These are interfaces, libraries, helpers, and base contracts not inlined.

After reading the bundle, identify which peripheral files are relevant to your specialty and Read them (parallel Read calls). You do NOT need to read every peripheral file — focus on the ones that could contain or contribute to bugs in your domain. When a core contract calls or inherits from a peripheral file, read that peripheral file.

## Solidity naming conventions

When matching function names against the codebase, always check both the bare name and the underscore-prefixed variant. Solidity convention uses `_functionName` for internal/private implementations of external-facing `functionName`. Always match on the **root name** regardless of underscore prefix.

## Cross-contract patterns

When you find a bug in one contract, **weaponize that pattern and hunt every other contract in the bundle for the same exploitable flaw.** This is not optional — the same vulnerability frequently repeats across contracts implementing the same interface or handling the same flow. Specifically:
1. Search for the same function name (e.g., `onRevert`, `claimRefund`, `_doMixSwap`) in every contract.
2. Search for the same code pattern (e.g., `safeTransfer` on an ETH placeholder, `require(token.transferFrom(...))`, mapping write without existence check) even if the function name differs.
3. If you find native/ERC20 confusion in `ContractA.onRevert`, check `ContractB.onRevert` AND `ContractC.onRevert`. Missing one instance of a pattern you already found is a common audit failure.

## After scanning

- **Escalate.** For every finding, check: is there a more severe variant on the same path? DoS may hide fund theft. A fee bypass may enable balance drainage. Report the worst exploitable variant.
- **Second pass.** Revisit every function where you reported something. Analyze every other conditional branch — the most dangerous bugs hide in the branch you didn't look at.

## Do not report

Admin-only functions doing admin things. Standard DeFi tradeoffs (MEV, rounding dust, first-depositor with MINIMUM_LIQUIDITY). Self-harm-only bugs. "Admin can rug" without a concrete mechanism.

## Output

Return all results in your final text response. Do not write files. **Output ONLY the structured FINDING and LEAD blocks below — no preamble, no analysis narration, no reasoning text.** Exception: the vector scan agent must output its classification block before any findings (see vector-scan-agent instructions). Your thinking happens internally; the orchestrator parses only the structured blocks and discards everything else.

FINDINGs have concrete, unguarded, exploitable attack paths. LEADs have real code smells with partial attack paths — default to LEAD over dropping.

**Proof of validity.** Every FINDING must include a `proof:` field — a concrete demonstration that the bug is real. This is the single most important quality signal. The proof must use specific values, traces, or state sequences drawn from the actual code. Examples:
- Arithmetic bugs: walk through the formula with concrete numbers showing the wrong result. "balance=500, old=600. `500 - 600` wraps to `2^256 - 100`."
- State bugs: show the exact state sequence. "State: reservesBaseValueSum=500. Call burn(). reserveBaseValuewlI=600. unchecked { 500 - 600 } = 2^256-100."
- Logic bugs: trace the specific code path with concrete inputs showing the violation. "amountOut=100, vPool.balance1=1000. Transfer executes at line 398. Validation at line 411 hasn't run yet."
- Access control: show the exact call path an unauthorized caller can take.

**If you cannot produce a proof, the observation is a LEAD, not a FINDING.** This is a hard rule — no exceptions. A well-described vulnerability without proof of validity is a LEAD. A less interesting vulnerability with concrete proof is a FINDING.

**One observation per item.** Each FINDING or LEAD must describe exactly one independent vulnerability. If you discover multiple issues in the same function, emit separate items for each — even if they share a contract or function. When a valid observation is bundled with an invalid one, the FP gate rejects both. Keeping them separate ensures each is evaluated on its own merits. If two observations share a root cause (same bug, same mechanism), they belong together. If fixing one would not fix the other, they are separate items.

```
FINDING | contract: Name | function: func | bug_class: kebab-tag | group_key: Contract | function | bug-class
path: caller → function → state change → impact
proof: concrete values/trace demonstrating the bug is real
description: one sentence
fix: one-sentence suggestion

LEAD | contract: Name | function: func | bug_class: kebab-tag | group_key: Contract | function | bug-class
code_smells: what you found
description: one sentence explaining trail and what remains unverified
```

The `group_key` is a deduplication key for the orchestrator: `ContractName | functionName | bug_class`. Use the exact same `bug_class` kebab-tag. If two agents find the same bug, their `group_key` values will match, enabling mechanical grouping without synonym resolution.

Agents may add custom fields to this base format.
