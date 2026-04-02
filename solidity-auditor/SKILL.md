---
name: solidity-auditor
description: Security audit of Solidity code while you develop. Trigger on "audit", "check this contract", "review for security". Modes - default (full repo) or a specific filename.
---

# Smart Contract Security Audit

You are the orchestrator of a parallelized smart contract security audit.

## Mode Selection

**Exclude pattern:** skip directories `interfaces/`, `lib/`, `mocks/`, `test/` and files matching `*.t.sol`, `*Test*.sol` or `*Mock*.sol`.

- **Default** (no arguments): scan all `.sol` files using the exclude pattern. Use Bash `find` (not Glob).
- **`$filename ...`**: start from the specified file(s), then expand scope to local high-coupling dependencies before bundling. Never treat a wrapper/periphery file as sufficient scope if pricing, oracle, curve, reserve, or fee logic is delegated elsewhere.

**Flags:**

- `--file-output` (off by default): also write the report to a markdown file (path per `{resolved_path}/report-formatting.md`). Never write a report file unless explicitly passed.
## Orchestration

**Turn 1 — Discover.** Print the banner, then make these parallel tool calls in one message:

a. Bash `find` for in-scope `.sol` files per mode selection
b. Glob for `**/references/attack-vectors/attack-vectors.md` — extract the `references/` directory (two levels up) as `{resolved_path}`. `{resolved_path}` must be the directory that directly contains `report-formatting.md`, `judging.md`, `attack-vectors/`, and `hacking-agents/`. Never strip the `solidity-auditor/` component or fall back to a broader repo root.
c. ToolSearch `select:Agent`
d. Read the local `VERSION` file from the same directory as this skill
e. Bash `curl -sf https://raw.githubusercontent.com/pashov/skills/main/solidity-auditor/VERSION`
f. Bash `mktemp -d /tmp/audit-XXXXXX` → store as `{bundle_dir}`

If the remote VERSION fetch succeeds and differs from local, print `⚠️ You are not using the latest version. Please upgrade for best security coverage. See https://github.com/pashov/skills`. If it fails, skip silently.

**Turn 2 — Prepare.** In one message, make parallel tool calls: (a) Read `{resolved_path}/report-formatting.md`, (b) Read `{resolved_path}/judging.md`.

Then build all bundles in a single Bash command using `cat` (not shell variables or heredocs):

Before bundling, expand the audit scope and write a hotspot checklist:

1. **Scope expansion is mandatory.**
   - In **Default** mode, use all in-scope `.sol` files per exclude rules.
   - In **`$filename ...`** mode, start from the requested files, then pull in all directly imported files plus clearly coupled same-subsystem files. Coupling includes:
     - helper / hook / library / math / oracle / pricing / quoter files in the same local subtree
     - contracts reached by interface calls from the requested file
     - sibling files whose names match `*Hook*`, `*Helper*`, `*Oracle*`, `*Curve*`, `*Math*`, `*Quoter*`, `*Pricing*`
     - files defining or mutating symbols matched by `getAmountOut`, `getUnspecifiedAmount`, `price`, `reserve`, `sync`, `ln`, `exp`, `pow`, `curve`, `oracle`, or fee-adjusted amount variables
   - If the requested contract delegates pricing or reserve accounting, the helper/hook/library files are **in scope** even if the user named only the wrapper.
   - If execution price, reserve mutation, fee application, or invariant enforcement is split across wrapper + hook + helper + math library files, that split path is **critical path** and must be treated as the primary exploit surface, not optional supporting context.
   - If the requested contract or a coupled file uses `receive()`, `fallback()`, `tx.origin`, contract/EOA checks, or reward/claim side effects, those contracts are **in scope** even if they look like periphery.
   - If the codebase is a fork or near-fork of a known protocol, import-paths, naming, storage layout, comments, and copied function signatures must be used to identify the parent protocol lineage. Once lineage is identified, inherited issue classes from that parent protocol and its common forks are **in scope by default** unless clearly removed by source changes.

2. **Discovery phase is mandatory before validation.**
   - Before spawning agents, build a `# Discovery Checklist` that explicitly records:
     - **Public surface inventory**:
       - every `external` / `public` state mutator
       - every `payable` function
       - every `receive()` / `fallback()`
       - every callback / hook / router callback / ERC721 receiver / token receiver
       - every `claim`, `claimFor`, `refund`, `refundFor`, `withdraw`, `sweep`, `rescue`, `execute`, `deposit`, `mint`, `burn`, `liquidate`
       - every user-controlled approval, referrer, recipient, treasury, helper, or target parameter
     - **Assumption inversion**:
       - what assumptions the code appears to rely on
       - what happens if caller is a contract instead of an EOA
       - what happens if the caller is an EOA using delegated code / account-abstraction semantics (including EIP-7702-style behavior) rather than a plain legacy wallet
       - what happens if recipient rejects ETH / token receipt
       - what happens if helper contracts are called directly, before, after, or instead of the intended wrapper path
       - what happens if first caller / first deposit / first NFT / first registration / first config write is malicious
       - what happens if external tokens are fee-on-transfer, rebasing, blacklisting, or non-standard
     - **Unusual sequence checks**:
       - call before init
       - claim before settle
       - settle before register
       - deposit then burn then claim
       - receive ETH directly
       - transfer NFT directly
       - repeat tiny actions many times
       - reverse intended operation order
       - mix helper + main contract entrypoints in one path
     - **Fork-lineage / inherited-bug checks**:
       - whether the code is a fork / close derivative of Aave, Compound, Uniswap, MasterChef, ERC4626 vaults, lending markets, CDPs, gauges, or common staking vaults
       - whether the fork retained known attack surfaces from the parent design even if the current diff looks unrelated
       - whether a modification touches a non-critical path while leaving the known critical empty-market / share-inflation / collateral-bootstrap assumptions unchanged
     - **Empty market / bootstrap checks**:
       - whether any market, pool, vault, tokenized share system, cToken/aToken-style market, or ERC4626 vault can start with near-zero liquidity or supply
       - whether first depositor / first borrower / first supplier / first LP can set an exchange rate, share price, utilization regime, or oracle anchor
       - whether donations, direct transfers, forced reserves, or manipulative bootstrap deposits can distort the initial exchange rate or collateral factor
       - whether an empty or near-empty market can be used as collateral, debt asset, liquidation target, or pricing reference before it has meaningful depth
       - whether a fork inherited known empty-pool / empty-market / first-depositor / share-inflation attacks from its parent protocol
       - whether low-liquidity reserves can amplify any reserve index, accumulator, or fee-distribution variable because the denominator collapses to dust
       - whether public flashloan premiums, fee accrual, or reserve updates can be compounded repeatedly against dust liquidity
       - whether Aave-style `liquidityIndex`, `variableBorrowIndex`, normalized income, or scaled-balance accounting can be manipulated by first pushing reserve liquidity near zero
       - whether scaled mint/burn/withdraw/borrow paths round against attacker-amplified indices in a way that lets tiny deposits or scaled balances support larger withdrawals or borrow power
       - whether a fork inherited Aave-style reserve-index inflation or flashloan-premium amplification issues even if wrapper/periphery diffs look unrelated
     - **Reserve bucket / sync checks**:
       - whether the protocol tracks more than one balance bucket such as priced reserve, locked reserve, claimable reserve, treasury reserve, or raw contract balance
       - whether any public `sync`, `reconcile`, `refresh`, `skim`, `settle`, `updatePoolBalance`, or unlabeled selector-style function rewrites one reserve bucket from raw `address(this).balance` or token balance
       - whether that rewrite can temporarily reclassify locked or unsellable assets into the priced / sellable reserve used by mint, burn, swap, redeem, or withdrawal math
       - whether a later function restores accounting only after the pricing or payout step has already consumed the corrupted reserve state
       - whether a profitable loop exists of the form `mint/buy -> sync/update -> burn/sell -> repeat`
     - **LP reserve destruction / pair-burn checks**:
       - whether any public transfer hook, sell hook, pending-burn variable, fee bucket, or maintenance path can burn tokens directly from the LP/pair address
       - whether the amount burned from the pair is fed by public user flow such as sells, transfers, or swaps rather than privileged-only admin calls
       - whether the contract calls `sync()` after burning pair inventory, making the reserve distortion immediately exploitable
       - whether a profitable loop exists of the form `buy -> trigger sell/transfer hook -> accumulate pair-burn debt -> burn pair balance -> sync -> extract opposite reserve`
       - whether the code destroys the token-side reserve of the pair without correspondingly removing the quote-side reserve, making the opposite asset drainable
     - **Morpho / MetaMorpho / lending-vault checks**:
       - whether the vault or wrapper allocates into underlying markets that can be empty or near-empty
       - whether allocator / curator / owner can route funds into risky long-tail markets before users can react
       - whether vault caps, market caps, supply caps, or withdrawal queues can create liquidity starvation or trapped-withdraw conditions
       - whether underlying oracle, LLTV, liquidation, or collateral settings in downstream markets are manipulable or weak
       - whether share bootstrap, donation inflation, or first-depositor attacks exist at the vault layer even if the underlying market is sound
       - whether the system is mostly a fork with only unrelated changes, in which case parent-protocol issue classes must be actively disproven rather than assumed absent
       - explicitly test the common Morpho / MetaMorpho exploit families and state the result for each:
         - **empty / near-empty downstream market attack**: vault allocates into a market whose liquidity/debt is too small, so collateral / debt / liquidation assumptions can be manipulated cheaply
         - **bad curation / cap attack**: curator/allocator enables or over-caps a risky market, allowing vault funds to be routed into a manipulable or insolvent venue
         - **oracle / collateral misconfiguration attack**: downstream oracle, price source, LLTV, collateral factor, liquidation incentive, or market parameters let an attacker extract value once the vault is exposed to that market
         - **withdrawal-liquidity starvation**: users can no longer exit because funds are parked in illiquid or fully-utilized downstream markets
         - **ERC4626 / share-price bootstrap or donation inflation**: first depositor, donor, or bootstrapper can distort share price / exchange rate in an empty or near-empty vault
         - **fork-with-minimal-diff inheritance**: if the fork changed only unrelated or non-critical paths, inherited parent-protocol issues must be treated as still live candidates until disproven
       - for each of the above, record the conditions that would make it live:
         - which market/pool must be empty or thin
         - which role or config must enable it
         - whether it needs a flash loan / large capital / first depositor / direct donation
         - whether the victim is the vault, downstream market, withdrawer set, or vault share holders
     - **Compound / Venus donation-inflation checks**:
       - whether a pre-existing cToken / vToken holder can increase borrow power by donating underlying directly to the market contract without minting new shares
       - whether `exchangeRateStored`, `exchangeRateStoredInternal`, `getCash`, `cashPlusBorrowsMinusReserves`, or similar logic reads raw underlying balance in a way that treats unsolicited donations as backing
       - whether liquidity / borrow checks multiply an unchanged share balance by the inflated exchange rate, oracle price, and collateral factor to create new borrow capacity
       - whether the exploit needs an empty market, or only a pre-existing share position plus a large enough direct donation
       - whether recursive `borrow -> swap -> donate underlying -> borrow again` loops can ratchet collateral value upward until shortfall or bad debt appears
       - whether direct donations mint offsetting collateral shares; if not, treat unchanged share count with increased borrow power as a first-class exploit path
     - **Profit conversion attempts**:
       - if the initial issue looks like griefing, list ways it could become profit via front-run/back-run, self-referral, attacker-controlled sink, temporary role capture, flash loan, or purpose-built contract wallet
       - if value is redirected to protocol sinks, test whether attacker can first become or influence that sink
     - **Reward / solvency accounting pass**:
       - whether a new deposit, fee, or `netValue` is counted both as immediately distributable reward and as fully withdrawable principal / share value
       - whether reward accrual increases liabilities without creating segregated backing assets or reserves
       - whether reward withdrawal reduces the same accounting bucket from which the reward was derived, or only spends cash while leaving liabilities unchanged
       - whether `claim`, `withdraw`, `reinvest`, `harvest`, or similar flows can realize rewards sourced from later deposits while the depositor's own principal remains fully withdrawable
       - whether two attacker-controlled accounts can cycle `deposit -> reward accrual -> withdraw -> principal exit` in one transaction or one short sequence
       - whether insolvency or low cash balance converts a circular reward model into an immediate drain
       - whether public state variables such as `totalContributed`, `accRewardPerShare`, `rewardDebt`, `claimedSoFar`, `principal`, `shares`, `assets`, or similar remain overstated after cash leaves the contract
       - whether direct ETH/token donations, flash-loaned deposits, or attacker-listed worthless assets make the accounting exploit cheaper without changing permissions
     - **One-time claim / invalidation pass**:
       - whether a completed `claim`, `withdraw`, `redeem`, `unlock`, `cancel`, `collect`, or `settle` path invalidates the primary storage record, not just an auxiliary index/list/lookup helper
       - whether the authorization check reads from the same primary record that settlement clears
       - whether cleanup only removes an entry from an owner array, enumerable set, queue, bitmap, or helper mapping while the source-of-truth record still authorizes payout
       - whether the same record can be claimed, withdrawn, redeemed, or unlocked twice in the same transaction or across transactions
       - whether user-controlled zero-duration / immediate-maturity / fully-finished states let the attacker test repeat-withdraw immediately
     - **Value-moving state delta pass**:
       - for every `mint`, `redeem`, `redeemUnderlying`, `withdraw`, `deposit`, `borrow`, `repay`, `liquidate`, `claim`, `burn`, `seize`, or share-conversion path, compare:
         - user balance delta
         - global supply / total assets / total debt / total shares delta
         - transferred asset amount
       - verify the same effective amount is used consistently across:
         - quoting
         - allowance / solvency / liquidity checks
         - global state mutation
         - per-user state mutation
         - final transfer
       - explicitly test whether any clamp, cap, sentinel handling, rounding, or balance check happens only after one side of accounting has already been mutated
       - explicitly test dust-position variants:
         - dust mint then oversized redeem
         - dust collateral then max borrow
         - full-cash redeem / withdraw
         - full claim / withdraw / unlock then repeat the same call on the same id
         - `type(uint256).max` / sentinel-value branches
         - first-user / tiny-supply / tiny-share states
       - explicitly test transient-state variants:
         - mutate reserve/accounting state with a public sync/update function
         - immediately consume that mutated state in the next pricing / withdrawal / burn step
         - verify whether final state appears restored even though value was extracted during the intermediate bad state
       - for forked lending or vault systems, do not assume “standard Compound/Aave/ERC4626 logic” is safe; prove the local state-delta invariant on the actual modified code
     - **Large Capital / Threshold Pass**:
       - every threshold such as `minDispatch`, `swapBack`, `rebalance`, `burnPool`, `liquidate`, `harvest`, `claim`, `process`, `autoSwap`, or fee accumulator
       - whether a large trade or flash loan can cross the threshold in one transaction
       - what branch or recipient changes once the threshold is crossed
       - whether threshold activation itself creates a front-run, back-run, or sandwich opportunity
     - **Reserve / Profitability Pass**:
       - current reserves for every touched pool
       - current balances for every touched token/escrow/helper/vault/distributor
       - rough output of any forced swap, rebalance, dispatch, liquidation, or dump at live reserves
       - rough round-trip cost from token taxes, AMM fees, slippage, and price impact
       - whether the move is large enough to matter economically
       - whether pair-side token destruction plus `sync()` can collapse one reserve enough to extract the opposite reserve after realistic flashloan and trade costs
     - **Helper Economic Pass**:
       - helper/router/distributor/vault approvals
       - helper balances and recipients
       - whether value actually reaches attacker, founder, treasury, sink, or stays inert
       - whether the helper path is dead, dormant, threshold-gated, or immediately reachable
     - **Weird-machine candidates**:
       - partial failure / `catch` / fallback branches
       - stale cached state vs live state
       - first-write-wins state
       - poisoned registries / subscribers / escrows / approvals
       - mismatches between docs, comments, and actual live behavior

   - For every public surface found, record at least one abuse idea, even if it is later rejected.
   - One agent must be tasked to prefer ugly, indirect, non-standard exploit paths over clean intended-flow analysis.

3. **Pricing / invariant hotspot checklist is mandatory for pricing systems.**
   - Before spawning agents, identify and record:
     - where execution price is computed
     - where reserves / pool state are updated
     - where fees are applied
     - whether pricing uses gross input, net-after-fee input, or a different effective amount than reserve accounting
     - whether execution relies on an approximation, interpolation, midpoint, averaging rule, or cached quote instead of an exact integral / exact invariant solve
     - which file contains the real pricing math versus which file only wraps it
   - Explicitly test and note:
     - round-trip profitability under repeated alternation (`A -> B -> A`)
     - midpoint / average pricing on nonlinear curves
     - reserve updates using gross input while output pricing uses net-after-fee input
     - helper-contract math called by the hook/core but not defined there
     - repeated alternating swaps over many iterations, not just one sample round trip
     - whether a tiny directional bias compounds inside a callback, unlock, multicall, or router-driven loop
     - whether one swap direction gets consistently better pricing and the reverse leg does not fully cancel the edge
     - whether the approximated execution price differs from the true curve integral or exact invariant solution
   - When a wrapper delegates the real pricing logic, the checklist must name both the wrapper and the delegated files.
   - For any custom curve or nonlinear helper-priced system, one agent must explicitly search for profit from repeated alternating swaps and compounding micro-edges rather than only one-shot drains.
   - For any mint / redeem / borrow / repay / liquidation system, one agent must explicitly search for state-delta mismatches where:
     - global accounting is mutated before per-user accounting is clamped or validated
     - per-user accounting is mutated using a different amount than global accounting
     - transfer amount is derived from a pre-clamp or pre-rounding quote while user burn/mint uses a post-clamp or post-rounding amount
   - Also explicitly record:
     - every payable `receive()` / `fallback()` / zero-calldata entrypoint
     - every path that reaches reward minting, claiming, mining, withdrawal, or pool updates without going through `_transfer`
     - whether any `tx.origin` / EOA restriction can be bypassed by entering through a different function than the one that contains the check
     - whether any `msg.sender == tx.origin`, `code.length == 0`, `Address.isContract == false`, or similar EOA-only restriction should be treated as weak because EIP-7702-style delegated EOAs and account-abstraction flows can violate the intended assumption
     - whether a “non-transferable” or “wallet-only” token still exposes contract-triggerable reward, deposit, or claim surfaces through helper contracts
     - whether a dormant feature can become active only after a threshold-crossing whale or flashloan trade
     - whether an empty or near-empty market, vault, or share system can be inflated, donated-to, or otherwise bootstrapped into a mispriced state before normal liquidity arrives
     - whether an empty or near-empty reserve can amplify `liquidityIndex`, `borrowIndex`, normalized income, or any accumulator later used in scaled-balance math
     - whether public flashloans or fee repayment paths can be looped repeatedly to compound those indices
     - whether a public sync/reconcile path can transiently make pricing read from the wrong reserve bucket even if storage is restored later in the same transaction

4. **Reserve-index hotspot checklist is mandatory for lending markets.**
   - Before clearing any Aave-style or scaled-balance lending system, identify and record:
     - where reserve indices (`liquidityIndex`, `variableBorrowIndex`, normalized income, normalized debt) are updated
     - the exact denominator used in those updates
     - whether public actions can shrink that denominator to dust
     - whether public flashloan, fee, repay, or reserve-update paths can increase the index
     - where scaled mint/burn/balance conversions divide by the manipulated index and where later valuation multiplies by it
   - Explicitly test and note:
     - dust supply / dust reserve state before index update
     - repeated self-flashloans or fee-generating loops
     - whether the same actor can first inflate the index and then exploit scaled-balance rounding in deposit/withdraw/borrow paths
     - whether collateral value or borrow power becomes larger than economically supplied capital after index manipulation
   - Treat this as a required inherited issue class for Aave/L2Pool/AToken-style forks, not an optional edge case.

5. **Compound / Venus donation-inflation checklist is mandatory for lending forks that price collateral through share balance × exchange rate.**
   - Identify every market where collateral value depends on `share balance * exchange rate * price * collateral factor`.
   - Identify whether direct underlying transfers to the market contract increase `getCash`, exchange rate, or equivalent reserve-backed share price without minting new shares.
   - Explicitly test the pre-existing-holder path:
     - attacker starts with a positive share balance
     - attacker donates underlying directly to the market
     - attacker share count stays unchanged
     - exchange rate rises
     - borrow power rises
   - Test both empty-market and non-empty-market variants. Do not assume this issue requires a fresh market if a large direct donation can still reprice existing shares.
   - Test recursive loops such as `borrow -> swap -> donate to collateral market -> borrow again`.
   - Record whether bad debt remains after liquidation or only appears transiently during the loop.

6. **Transient reserve-desync checklist is mandatory for reserve-priced systems.**
   - Before clearing any reserve-priced bonding-curve, AMM-like, mint/burn, or legacy treasury system, identify and record:
     - the storage variables that represent priced reserve versus locked / unsellable / treasury reserve
     - every public function or selector that mutates those variables
     - whether any path derives priced reserve from raw contract balance without subtracting locked funds
     - whether mint/burn/sell/buy logic reads those buckets before they are recomputed canonically
   - Explicitly test and note:
     - public `sync/update -> sell/burn` in the same transaction
     - repeated `mint/buy -> sync/update -> burn/sell -> repeat`
     - whether final end-of-tx storage looks consistent even though the intermediate pricing state was corrupted
   - Treat “restored by end of tx” as irrelevant if value can be extracted during the temporary bad state.
7. `{bundle_dir}/source.md` — a short `# Audit Scope` section listing the expanded source set, then a `# Discovery Checklist` section, then a `# Pricing / Invariant Hotspots` section capturing the checklist above, then ALL expanded in-scope `.sol` files, each with a `### path` header and fenced code block.
8. Agent bundles = `source.md` + agent-specific files:

| Bundle               | Appended files (relative to `{resolved_path}`)                                                                  |
| -------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `agent-1-bundle.md`  | `attack-vectors/attack-vectors.md` + `hacking-agents/vector-scan-agent.md` + `hacking-agents/shared-rules.md`   |
| `agent-2-bundle.md`  | `hacking-agents/math-precision-agent.md` + `hacking-agents/shared-rules.md`                                     |
| `agent-3-bundle.md`  | `hacking-agents/access-control-agent.md` + `hacking-agents/shared-rules.md`                                     |
| `agent-4-bundle.md`  | `hacking-agents/economic-security-agent.md` + `hacking-agents/shared-rules.md`                                  |
| `agent-5-bundle.md`  | `hacking-agents/execution-trace-agent.md` + `hacking-agents/shared-rules.md`                                    |
| `agent-6-bundle.md`  | `hacking-agents/invariant-agent.md` + `hacking-agents/shared-rules.md`                                          |
| `agent-7-bundle.md`  | `hacking-agents/periphery-agent.md` + `hacking-agents/shared-rules.md`                                          |
| `agent-8-bundle.md`  | `hacking-agents/first-principles-agent.md` + `hacking-agents/shared-rules.md`                                   |
| `agent-9-bundle.md`  | `hacking-agents/deployment-payload-agent.md` + `hacking-agents/shared-rules.md`                                 |

Print line counts for every bundle and `source.md`. Do NOT inline file content into agent prompts.

**Turn 3 — Spawn.** Use all available agent capacity.

- If the runtime can host all 9 agents concurrently, spawn all 9 in parallel.
- If the runtime supports fewer concurrent agents, spawn as many as available, wait for completions, then reuse or batch the remaining agent roles until all 9 bundles have been analyzed.
- Do not fail or silently skip roles just because the environment has fewer threads than the ideal bundle count.

Prompt template (substitute real values):

```
Your bundle file is {bundle_dir}/agent-N-bundle.md (XXXX lines).
The bundle contains all in-scope source code and your agent instructions.
Read the bundle fully before producing findings.
You must include at least one non-standard / unusual exploit attempt from the discovery checklist, even if it is later rejected.
```

**Turn 4 — Deduplicate, validate & output.** Single-pass: deduplicate all agent results, gate-evaluate, and produce the final report in one turn. Do NOT print an intermediate dedup list — go straight to the report.

1. **Deduplicate.** Parse every FINDING and LEAD from all 9 agents. Group by `group_key` field (format: `Contract | function | bug-class`). Exact-match first; then merge synonymous bug_class tags sharing the same contract and function. Keep the best version per group, number sequentially, annotate `[agents: N]`.

   Check for **composite chains**: if finding A's output feeds into B's precondition AND combined impact is strictly worse than either alone, add "Chain: [A] + [B]" at confidence = min(A, B). Most audits have 0–2.

2. **Gate evaluation.** Run each deduplicated finding through the four gates in `judging.md` (do not skip or reorder). Evaluate each finding exactly once — do not revisit after verdict.

   **Finding classification is mandatory before gating.** For every candidate issue, classify it into exactly one primary bucket before writing the report:
   - `Public Exploitable` — any unprivileged actor can trigger the harmful state transition
   - `Privileged / Centralization` — only owner / admin / authority / oracle / approved role can trigger it
   - `Code-Level / Config-Dependent` — source bug exists, but live exploitability depends on onchain config, missing dependencies, or unresolved state
   Do not describe a finding as attacker-profitable unless it is first classified as `Public Exploitable`.

   **Live-state validation is mandatory for economic findings.** Before calling any fee, pricing, oracle, reward, escrow, or treasury issue a live exploit, explicitly verify where possible:
   - the current onchain config values that the exploit depends on
   - whether compared values actually differ onchain
   - the current role holders for privileged setters / executors
   - whether those role holders are EOAs, multisigs, or contracts
   - the live recipient of extracted value
   - whether the issue only activates after a threshold is crossed, and whether an unprivileged actor can cross it with realistic capital or a flash loan
   - whether live reserve depth and round-trip costs still leave attacker profit after taxes, fees, and slippage
   If any of these remain unresolved, downgrade to `Code-Level / Config-Dependent` or `LEAD`.

   **Profit path table is mandatory for any issue that may be attacker-profitable.** For each such finding, explicitly fill:
   - `value source`
   - `trigger function`
   - `permission required`
   - `recipient of value`
   - `why attacker gets paid`
   If any field cannot be completed from source and live state, do not mark the issue as attacker-profitable.

   **Single-pass protocol:** evaluate every relevant code path ONCE in fixed order (constructor → setters → swap functions → mint → burn → liquidate). One-line verdict per path: `BLOCKS`, `ALLOWS`, `IRRELEVANT`, or `UNCERTAIN`. Commit after all paths — do not re-examine. `UNCERTAIN` = `ALLOWS`.

   **Pricing-system minimum checks:** for any finding touching swap math, hooks, or reserves, the validation pass must explicitly answer:
   - Does any repeated alternating round-trip (`A -> B -> A`) increase attacker value?
   - Does profit appear only after many repeated iterations even if one sample round trip looks neutral or slightly loss-making?
   - Do pricing and reserve accounting consume the same effective input amount?
   - Is the real attack surface split across wrapper + helper/hook/library files?
   - Is execution price derived from an approximation (midpoint, average, interpolation, linearization, cached quote) rather than the exact curve / invariant?
   - If the curve is nonlinear, did you compare the implementation against the exact integral / invariant instead of assuming the approximation is close enough?
   - If profitability depends on parameters or reserve ratios, did you test defaults, allowed configuration bounds, and realistic reserve skews rather than one default sample?
   - If profitability depends on a threshold or dormant path, did you test whether a whale or flashloan can cross it in one transaction?
   - Did you compare the forced move size against live reserves and realistic execution costs?
   If yes to any, treat the helper/hook/library path as part of the same exploit surface, not a separate optional review.

   **Non-transfer / reward-system minimum checks:** for any finding touching rewards, staking, mining, claims, wallet-only restrictions, or payable entrypoints, the validation pass must explicitly answer:
   - Can a contract trigger the same reward or claim side effect through `receive()`, `fallback()`, deposit, or helper calls even if `_transfer` tries to restrict to EOAs?
   - Does the code rely on `tx.origin`, `msg.sender == tx.origin`, `code.length == 0`, or `isContract` checks that should be treated as flagged anti-patterns because EIP-7702-style delegated EOAs and account-abstraction flows weaken the intended “EOA-only” guarantee?
   - Does the vulnerable path require owning the token, or can it be reached with flash-loaned assets and a purpose-built contract?
   - Are trusted helper contracts (`MAIN`, `STAKE`, `PROOF`, distributor, vault, etc.) part of the same exploit surface because the target contract calls them during the attack?
   - Is newly deposited value being used twice: once as withdrawable principal and again as distributable reward or yield?
   - Does reward payout reduce the protocol's liability accounting, or only its cash balance?
   - Can two attacker-controlled accounts manufacture claimable rewards for one another from temporary capital and then withdraw both reward and principal?
   - If the system looks circular, did you test whether insolvency or low live balance turns it into an immediate profitable drain rather than a vague design smell?

   **Protocol audit minimum checks:** when the user asks to audit a protocol, docs-listed contracts, or a contract set, you must:
   - map user-facing docs/contracts to the actual live deployed contracts
   - trace all state-variable-held external dependencies that can move value
   - include manager / escrow / registry / oracle / subscriber / treasury dependencies that are actually called in the live flow
   - distinguish wrapper/periphery issues from the contracts where value is actually controlled
   - check whether docs-promised liquidity / reward / burn / rebalance / mining features are live, dead, or only threshold-dormant onchain
   - determine whether the system is a fork or close derivative of a known protocol, and if so, explicitly investigate the parent protocol's historically exploited issue classes
   - for lending / vault / market protocols, explicitly investigate empty-market, empty-pool, share-inflation, first-depositor, and donation-based bootstrap attacks before clearing the system
   - for lending / vault / market protocols, explicitly trace every redeem / mint / borrow / repay path and prove that user deltas, global deltas, and transfer amounts stay equal under clamping, sentinel values, and dust positions before clearing the system
   - for Morpho / MetaMorpho / lending-vault style systems, explicitly investigate allocator/curator misrouting, downstream market emptiness, oracle/collateral weakness, cap misconfiguration, withdrawal liquidity starvation, and ERC4626/share-bootstrap risks before clearing the system
   - the final notes for Morpho / MetaMorpho style systems must say which of these were checked and under what conditions they would become live: empty-market attack, bad curation/cap attack, oracle/collateral attack, withdrawal-liquidity starvation, share-bootstrap/donation inflation, fork-with-minimal-diff inheritance

   **Large-capital adversary modeling is mandatory** for token / AMM / fee systems:
   - can a large-capital actor or flash loan cross the next relevant threshold immediately?
   - if crossed, what exact branch executes and who receives value?
   - can the resulting move be sandwiched, backrun, or otherwise monetized?
   - if value is redirected to a non-attacker sink, can induced price movement still be monetized separately?

   **Dead vs dormant distinction is mandatory**:
   - `Dead`: unreachable under allowed live state or impossible relative to supply/reserve bounds
   - `Dormant`: inactive now, but reachable if a user/whale/flashloan crosses a threshold
   Do not clear an issue merely because the path is currently inactive if it is only dormant.

   **Do not refute parameter-sensitive pricing bugs with one sample.** If the source trace shows midpoint bias, nonlinear-curve approximation, gross/net accounting mismatch, or repeated-loop compounding potential, a single loss-making simulation at default parameters is not enough to reject. Search reachable configuration ranges, reserve ratios, repeated iteration counts, and callback/multicall loop structures before clearing the finding.

3. **Lead promotion & rejection guardrails.**
   - Promote LEAD → FINDING (confidence 75) if: complete exploit chain traced in source, OR `[agents: 2+]` demoted (not rejected) the same issue.
   - `[agents: 2+]` does NOT override a concrete refutation — demote to LEAD if refutation is uncertain.
   - No deployer-intent reasoning — evaluate what the code _allows_, not how the deployer _might_ use it.

4. **Fix verification** (confidence ≥ 80 only): trace the attack with fix applied; verify no new DoS, reentrancy, or broken invariants (use `safeTransfer` not `require(token.transfer(...))`); list all locations if the pattern repeats. If no safe fix exists, omit it with a note.

5. **Attacker profitability conclusion is mandatory.** Before formatting the report, add one final conclusion that answers whether a **non-owner / unprivileged attacker** has a confirmed profitable path.
   - `Yes` only if at least one final finding survives all gates with a complete profitable exploit path for an unprivileged actor.
   - `No` if no surviving finding proves profitable attacker extraction or profit, even if there are confirmed honeypots, griefing, DoS, or owner-only abuse paths.
   - `Inconclusive` if the strongest remaining item is a LEAD or a demoted finding where profitability could not be completed end-to-end.
   - Keep the conclusion focused on attacker profit, not generic protocol risk.
   - If `Yes`, cite the finding number(s). If `Inconclusive`, cite the lead title(s) that block certainty.

6. **Per-finding status line is mandatory.** Each final finding or lead must internally resolve these flags before report formatting:
   - `Code bug:` Yes / No
   - `Live on this deployment:` Yes / No / Unknown
   - `Publicly exploitable:` Yes / No / Unknown
   - `Attacker profitable:` Yes / No / Unknown
   - `Privileged only:` Yes / No
   If `Live on this deployment` or `Attacker profitable` is `Unknown`, do not present it as a confirmed profitable exploit.

7. **Format and print** per `report-formatting.md`. Exclude rejected items. If `--file-output`: also write to file.

## Banner

Before doing anything else, print this exactly:

```

██████╗  █████╗ ███████╗██╗  ██╗ ██████╗ ██╗   ██╗     ███████╗██╗  ██╗██╗██╗     ██╗     ███████╗
██╔══██╗██╔══██╗██╔════╝██║  ██║██╔═══██╗██║   ██║     ██╔════╝██║ ██╔╝██║██║     ██║     ██╔════╝
██████╔╝███████║███████╗███████║██║   ██║██║   ██║     ███████╗█████╔╝ ██║██║     ██║     ███████╗
██╔═══╝ ██╔══██║╚════██║██╔══██║██║   ██║╚██╗ ██╔╝     ╚════██║██╔═██╗ ██║██║     ██║     ╚════██║
██║     ██║  ██║███████║██║  ██║╚██████╔╝ ╚████╔╝      ███████║██║  ██╗██║███████╗███████╗███████║
╚═╝     ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝ ╚═════╝   ╚═══╝       ╚══════╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝╚══════╝

```
