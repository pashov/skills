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
## Optional External Corroboration

If the user provides any of the following, treat them as **optional corroborating inputs** only:

- proxy or implementation addresses
- tx hashes
- block numbers
- trace snippets
- balance diff artifacts
- root-cause writeups
- named attacker/helper/orchestrator addresses

These artifacts may help confirm or falsify a source-derived exploit path, but they must never replace source-level exploit reconstruction. The default objective is preventive auditing: determine what the code allows before relying on any historical evidence.

## Preventive-audit rule (MANDATORY)

The baseline job is still **preventive exploit detection**, not post-mortem matching.

That means:

- You MUST try to find and validate public exploit paths from source, dependency closure, and live state even when the user provides **no** transaction hash.
- A user-supplied exploit tx is only an accelerator for confidence and live-status refinement; it is never a prerequisite for discovering or reporting the bug.
- If a source-derived public exploit candidate is high-signal and the live deployment is discoverable, you MUST proactively perform live exploitability checks before finalizing. Do not wait for the user to supply a tx.

Mandatory proactive validation for every high-signal public candidate:

1. resolve the live deployment address if it is provided or discoverable from the target bundle
2. inspect the live config, reserves, balances, pair addresses, roles, and thresholds that control the candidate path
3. model whether the path is economically positive under live state
4. if the path is AMM / reserve / fee / liquidation / pricing sensitive, reconcile the modeled extraction against live reserves and threshold logic
5. if the path looks immediately live, search for corroborating recent exploit evidence or suspicious matching transactions before finalizing severity

You must not leave a finding at a weakly supported middle state like:

- "root cause found but exploitability unclear"
- "likely live but not checked"
- "unknown live status"

when the missing work is simply live-state or explorer validation that you could have done yourself.

### Mandatory upgrade when a live exploit transaction is supplied

If the user provides a concrete exploit transaction hash, explorer link, trace, or step-by-step live RCA for the same target, that artifact stops being "nice to have" context and becomes **mandatory corroboration work before finalizing severity, confidence, and live status**.

In that case you MUST:

1. Fetch the transaction / trace / explorer record.
2. Reconstruct the exact live call chain and state transitions.
3. Reconcile the live path against the source-derived root cause.
4. Update the final finding so that:
   - `Live on this deployment` is **Yes** if the tx proves the same source bug was exploited live.
   - confidence is upgraded when the tx arithmetic and call sequence match the source path.
   - the finding text explicitly names every live-only exploit leg that mattered (for example: day rollover branches, threshold crossing, helper realization, fee-processing side effects, reserve sync points).

It is NOT acceptable to leave a finding at `Live on this deployment: Unknown` once a supplied exploit tx has been source-reconciled and confirms the same bug family.
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
   - If the requested contract calls external contracts that hold balances, compute prices, mint/burn claims, settle withdrawals, process deposits, or otherwise move value, those external dependencies are **in scope by default** even if they are referenced only by stored addresses or low-level calls.
   - Stored-address dependencies are not optional. If the named contract calls a `bank`, `storage`, `payment`, `oracle`, `vault`, `escrow`, `distributor`, `router`, `helper`, `executor`, or similarly stateful external contract during any value-moving path, you must fetch and analyze that dependency or explicitly mark the audit incomplete.
   - If the user provides live proxy addresses or implementation addresses, resolving those live contracts is **mandatory critical-path work**, not optional enrichment. Fetch proxy implementations, verified source, ABI/function names, and linked dependencies before allowing the audit to conclude “dependency unresolved”.
   - If a value-path dependency is referenced only by a selector-only low-level call, you must still resolve it from the live deployment context when addresses are available. A selector-only dependency on the live path is not grounds to stop at the wrapper.
   - If execution price, reserve mutation, fee application, or invariant enforcement is split across wrapper + hook + helper + math library files, that split path is **critical path** and must be treated as the primary exploit surface, not optional supporting context.
   - If the requested contract or a coupled file uses `receive()`, `fallback()`, `tx.origin`, contract/EOA checks, or reward/claim side effects, those contracts are **in scope** even if they look like periphery.
   - If the codebase is a fork or near-fork of a known protocol, import-paths, naming, storage layout, comments, and copied function signatures must be used to identify the parent protocol lineage. Once lineage is identified, inherited issue classes from that parent protocol and its common forks are **in scope by default** unless clearly removed by source changes.

2. **Discovery phase is mandatory before validation.**
   - Before spawning agents, build a `# Discovery Checklist` that explicitly records:
     - **Lending / market enumeration pass**:
       - if the target is a lending market, money market, CDP, vault-router, reserve protocol, or fork/near-fork of Aave, Compound, Morpho, Euler, Maker, Venus, Radiant, Silo, or similar systems, enumerate **all** pools / markets / reserves before narrowing to one path
       - enumerate every pool, market, reserve, collateral type, debt asset, wrapper token, debt token, interest-rate strategy, configurator, provider, oracle source, data provider, and reserve registry on the active path
       - treat each market/config pair as a distinct attack surface even when implementations are shared
       - explicitly record zero-supply, dust-supply, zero-debt, dust-debt, newly-listed, paused, frozen, isolated, siloed, or cap-constrained markets as top-priority exploit candidates rather than edge cases to skip
       - record per market:
         - underlying asset and decimals
         - collateral enabled / disabled
         - borrow enabled / disabled
         - supply cap / borrow cap / debt ceiling
         - total supply / total debt / cash / reserves / exchange rate / indexes
         - oracle source and oracle decimals
         - wrapper implementation and debt-token implementations
     - **Public surface inventory**:
       - every `external` / `public` state mutator
       - every `payable` function
       - every `receive()` / `fallback()`
       - every meta-tx / trusted-forwarder / `execute` / relay entrypoint
       - every callback / hook / router callback / ERC721 receiver / token receiver
       - every `claim`, `claimFor`, `refund`, `refundFor`, `withdraw`, `sweep`, `rescue`, `execute`, `deposit`, `mint`, `burn`, `liquidate`
       - every user-controlled approval, referrer, recipient, treasury, helper, or target parameter
     - **Value-out-first pass**:
       - identify every function that can move value out of the protocol first: `withdraw`, `unstake`, `redeem`, `claim`, `removeLiquidity`, `borrow`, `sweep`, `refund`, `rescue`, native coin transfer, token transfer, LP removal, or router-assisted asset exit
       - for each such function, trace in order:
         - what assets leave
         - what user record or entitlement authorizes the exit
         - whether the record is invalidated before or after any external call
         - whether custody is pooled at contract level or segregated per user
         - which external dependencies are called along the value path
       - if a value-out path uses a raw external call, token transfer hook, router call, LP removal, or native coin send before invalidating the authorizing record, treat it as a top-priority reentrancy candidate immediately
     - **Approval / allowance abuse pass**:
       - identify every path that can move ERC20 value via `transferFrom`, `permit`, Permit2-style helpers, allowance-consuming routers, vault pull patterns, token sweep helpers, arbitrary call executors, or spender-controlled adapters
       - record every contract that can become an approval holder or effective spender for user funds, vault funds, pair funds, or third-party funds
       - for each spender path, verify:
         - who is assumed to have granted approval
         - whether the spender can choose `from`, `to`, `token`, or `amount`
         - whether the code proves that `from` is the caller, the credited owner, or an explicitly authorized account rather than any address with standing allowance
         - whether approvals granted for one purpose can be reused on another path such as `withdraw`, `sweep`, `rescue`, `claim`, `rebalance`, `router`, `liquidation`, or arbitrary `execute`
         - whether a contract can pull tokens from any external account or contract that previously approved it, even if that approver is not the current caller
         - whether a contract-held token balance plus an arbitrary token-withdraw path creates a direct public drain
         - whether an arbitrary external-call path can be combined with pre-existing approvals to withdraw tokens from users, vaults, routers, pairs, escrows, or helper contracts
       - if any public or weakly-gated path can withdraw tokens from `address(this)` or from an arbitrary approved `from` address without tightly binding ownership/intent, treat it as a top-priority exploit candidate and complete the full profit chain
     - **Dependency-closure pass**:
       - identify every external contract address stored in state or returned by another contract that is used during deposit, withdraw, mint, burn, claim, settlement, pricing, reward, liquidation, or upgrade logic
       - for each such dependency, record whether it was:
         - resolved to a live implementation and analyzed directly
         - analyzed directly
         - fetched but blocked by missing source / missing verification / tooling failure
         - proven irrelevant to value movement
       - if a dependency remains unresolved and it is part of a value-moving or price-setting path, mark the audit as incomplete and do not present the result as full coverage
       - treat low-level `call`, `delegatecall`, selector-only calls, and decompiled external references as mandatory coupling evidence, not optional context
       - if the user supplied addresses, tx hashes, or traces for that dependency path, record the exact fetch attempts you made before accepting “blocked”, including explorer pages, proxy implementation lookups, and selector-resolution attempts
     - **Optional corroboration pass**:
       - if the user supplied a tx hash, trace, block number, or RCA, use it only to corroborate or falsify a source-derived exploit path before finalizing
       - record the exact contract chain used by the corroborating material, including proxy -> implementation hops and helper/orchestrator contracts when relevant
       - reconcile source-level formulas against the provided arithmetic or trace values when they exist
       - do not require external corroboration to report a finding; source-level exploit reconstruction remains sufficient when the path is complete
     - **Assumption inversion**:
       - what assumptions the code appears to rely on
       - whether custom policy logic lives only in `transfer()` while `transferFrom()` or `_transfer()` remains inherited or differently guarded
       - whether standard router / allowance / permit / helper flows therefore bypass the advertised trading or fee logic
       - what happens if caller is a contract instead of an EOA
       - what happens if the caller is a contract in construction, where `extcodesize` / `code.length` may still be zero
       - what happens if the caller is an EOA using delegated code / account-abstraction semantics (including EIP-7702-style behavior) rather than a plain legacy wallet
       - what happens if the call arrives through a trusted forwarder and the code mixes `msg.sender` with `_msgSender()`
       - what happens if a forwarder-aware contract composes with a non-forwarder-aware token or helper, so allowance owner, burned account, callback user, credited account, refund recipient, and payout recipient can diverge
       - what happens if recipient rejects ETH / token receipt
       - what happens if helper contracts are called directly, before, after, or instead of the intended wrapper path
       - what happens if first caller / first deposit / first NFT / first registration / first config write is malicious
       - what happens if external tokens are fee-on-transfer, rebasing, blacklisting, or non-standard
     - **Unusual sequence checks**:
       - call before init
       - claim before settle
       - settle before register
       - deposit then burn then claim
       - poison global pending state in one call, then realize it from a later unrelated call
       - seed state from one helper address and consume it from a different helper or constructor-time contract
       - receive ETH directly
       - transfer NFT directly
       - repeat tiny actions many times
       - reverse intended operation order
       - mix helper + main contract entrypoints in one path
       - self-liquidate / self-seize / self-refund / self-withdraw where caller and target are the same address
       - same-market / same-asset paths where borrow asset, collateral asset, payout asset, or accounting bucket collapse to the same value
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
     - **Lending rounding / state-delta checks**:
       - for every lending market, compare state deltas across `deposit/mint`, `withdraw/redeem`, `borrow`, `repay`, `liquidate`, `accrueInterest`, `mintToTreasury`, `handleRepayment`, `sync`, and reserve update helpers
       - explicitly test:
         - first mint into an empty market
         - first redeem after a direct donation
         - dust share balances and dust debt balances
         - full-cash withdraw / redeem
         - full-debt repay with sentinel values such as `type(uint256).max`
         - close-factor and liquidation bonus boundaries
         - same-block index update then withdraw / borrow / liquidate
       - verify whether any path lets the user receive more assets than burned shares justify, preserve more collateral than repaid debt justifies, or reduce more debt than transferred assets justify because different rounding directions are used across the same path
     - **Reserve bucket / sync checks**:
       - whether the protocol tracks more than one balance bucket such as priced reserve, locked reserve, claimable reserve, treasury reserve, or raw contract balance
       - whether any public `sync`, `reconcile`, `refresh`, `skim`, `settle`, `updatePoolBalance`, or unlabeled selector-style function rewrites one reserve bucket from raw `address(this).balance` or token balance
       - whether that rewrite can temporarily reclassify locked or unsellable assets into the priced / sellable reserve used by mint, burn, swap, redeem, or withdrawal math
       - whether a later function restores accounting only after the pricing or payout step has already consumed the corrupted reserve state
       - whether a profitable loop exists of the form `mint/buy -> sync/update -> burn/sell -> repeat`
     - **LP reserve destruction / pair-burn checks**:
       - if any contract can move inventory directly out of a pair / vault / market / reserve-holding address without a normal priced swap, LP burn, or user-authorized withdrawal, treat that primitive as a top-priority exploit candidate immediately
       - explicitly search for internal token-side reserve extraction patterns such as `super._transfer(pair, sink, amount)`, raw `transferFrom(pair, ...)`, pair `skim`, pair `burn`, helper-mediated pair withdrawals, or any equivalent mutation that removes inventory from the reserve-holding address without paying the quote side
       - if such a primitive is followed by `sync()`, reserve refresh, NAV update, settlement update, or any other state-finalization step, treat the reserve mutation plus finalization as the real value-out leg even if later payout code looks unrelated or inert
       - never clear a pair/vault/market inventory-drain primitive just because a downstream reward / claim / settle function appears broken, zeroed, or decompiler-ambiguous; first prove or disprove the full chain `public trigger -> cross-contract bridge -> inventory drain -> sync/update/finalization -> unwind to attacker profit`
       - when a public or permissionless path reaches a privileged helper, bridge, token, proof, vault, distributor, or settlement contract that can realize the primitive, treat that helper path as part of the same exploit chain rather than as a separate benign subsystem
       - explicitly test whether public `claim`, `claimReward`, `release`, `settle`, `sendMining`, `proof`, `reward`, `rebate`, or helper flows can be the unprivileged bridge into the reserve-extraction primitive even when the final reserve-touching function itself is role-gated
       - decompiler uncertainty on downstream settlement logic lowers confidence, but it is not sufficient reason to stop before testing whether the upstream inventory drain already gives the attacker extractable inventory or reserve asymmetry
       - whether the intended sell / buy / fee / anti-bot policy is attached only to `transfer()` while normal router flow uses `transferFrom()`
       - whether a public actor can use `transferFrom()` or other inherited paths to source inventory, bypass fees, or avoid trading restrictions before or after the pair-burn step
       - whether any public transfer hook, sell hook, pending-burn variable, fee bucket, or maintenance path can burn tokens directly from the LP/pair address
       - whether the amount burned from the pair is fed by public user flow such as sells, transfers, or swaps rather than privileged-only admin calls
       - whether the contract calls `sync()` after burning pair inventory, making the reserve distortion immediately exploitable
       - whether a sell or transfer both credits the pair with tokens and separately records those same tokens into a deferred burn / fee / extraction bucket that can later remove pair inventory again
       - whether a profitable loop exists of the form `buy -> trigger sell/transfer hook -> accumulate pair-burn debt -> burn pair balance -> sync -> extract opposite reserve`
       - whether the code destroys the token-side reserve of the pair without correspondingly removing the quote-side reserve, making the opposite asset drainable
       - whether any apparently privileged pair-burn / extraction path is reachable from a public upstream trigger such as `claim`, `distribute`, `process`, `harvest`, `rebalance`, `withdraw`, router flow, or keeperless maintenance call
       - whether attacker inventory can be sourced indirectly through router-held output, pair-to-router transfers, router-mediated liquidity removal, helper custody, or any sentinel-address branch even when direct buys are blocked
       - whether the review produced a full exploit chain covering `inventory source -> queued reserve mutation -> public/helper realization -> sync/update -> final extraction leg`
       - whether constructor-time helpers can bypass `isContract` / `code.length` anti-bot checks and act as the realization leg for a queued reserve mutation
       - whether a simpler direct bug elsewhere in the codebase is distracting from a stronger reserve-burn exploit; pair-burn plus `sync()` must still be completed and ranked if the trigger chain remains live or unresolved
       - do not clear or demote a public pair-burn / reserve-destruction path from one negative fixed-size round-trip sample; vary buy size, sell size, threshold-crossing size, flashloan bankroll, helper path, and multi-step sequence before concluding the path is uneconomic
       - if the source path can shrink the token-side reserve toward dust and then trade against the refreshed reserve ratio, explicitly test the "buy enough to make the later pair-burn dominate remaining token reserves, then dump" sequence rather than only symmetric buy/sell loops
       - if a user-supplied tx hash or live trace exists for the same pair, treat it as mandatory corroboration work before final ranking; reconcile the source-level arithmetic against that trace instead of leaving the path as an unresolved lead
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
       - explicitly test collusion / role-collapse variants where the same economic actor controls two or more addresses that play different protocol roles, such as payer + griefer, buyer + receiver, liquidator + beneficiary, distributor + recipient, or claimer + referrer
       - explicitly test malicious-obligor variants where the attacker's profit comes from avoiding an owed payout, distribution, refund, settlement payment, collateral top-up, debt repayment, or delivery obligation while still flipping protocol state to `distributed`, `settled`, `completed`, `paid`, `filled`, or equivalent
       - if the bug can advance status, totals, checkpoints, epochs, vesting, distribution progress, or settlement flags without moving the intended assets, test whether any onchain or offchain component would treat that state as final and release value, reputation, inventory, unlock rights, or future payouts elsewhere
       - if the attacker does not directly receive protocol-held funds, still test whether the attacker profits by retaining inventory, escaping liabilities, avoiding fees, preserving collateral, shifting losses to recipients, or creating a free option that can be monetized later
     - **State-finality / obligation-evasion checks**:
       - whether any public or weakly-gated function can mark work as done (`distributed`, `settled`, `fulfilled`, `cancelled`, `paid`, `completed`, `claimed`, `processed`) before the intended asset movement is proven
       - whether the state transition is keyed off requested amount, rounded amount, counters, indexes, hashes, signatures, or booleans rather than actual transferred value
       - whether the actor who can trigger finality is the same actor economically obligated to provide assets, or can collude with that actor through another address
       - whether a malicious payer, distributor, seller, borrower, liquidator, or order maker can use two addresses so one satisfies the business role and the other triggers the buggy public completion path
       - whether recipients, counterparties, offchain operators, or downstream contracts lose the ability to recover once the bad finality bit is set
       - whether retries, top-ups, cancellations, or alternative settlement paths are blocked once the protocol believes the action is complete
       - whether a zero-transfer, partial-transfer, fee-on-transfer, or floor-rounded transfer can still consume the full entitlement or mark the full obligation as satisfied
       - whether later logic trusts cumulative totals or status flags without reconciling actual token/ETH deltas
     - **Reward / solvency accounting pass**:
        - whether a new deposit, fee, or `netValue` is counted both as immediately distributable reward and as fully withdrawable principal / share value
        - whether reward accrual increases liabilities without creating segregated backing assets or reserves
        - whether reward withdrawal reduces the same accounting bucket from which the reward was derived, or only spends cash while leaving liabilities unchanged
        - whether `claim`, `withdraw`, `reinvest`, `harvest`, or similar flows can realize rewards sourced from later deposits while the depositor's own principal remains fully withdrawable
        - whether two attacker-controlled accounts can cycle `deposit -> reward accrual -> withdraw -> principal exit` in one transaction or one short sequence
        - whether insolvency or low cash balance converts a circular reward model into an immediate drain
        - whether public state variables such as `totalContributed`, `accRewardPerShare`, `rewardDebt`, `claimedSoFar`, `principal`, `shares`, `assets`, or similar remain overstated after cash leaves the contract
        - whether direct ETH/token donations, flash-loaned deposits, or attacker-listed worthless assets make the accounting exploit cheaper without changing permissions
        - whether qualification thresholds use properly scaled token units (for example `1000 * 1e18` for an 18-decimal stablecoin) rather than raw literals like `1000`
        - whether a one-time reward / pool / rank / bonus latch is checked but never consumed after payout
        - whether many cheap helper accounts can repeatedly satisfy the same threshold and mint treasury-backed rewards for one referrer
        - whether synthetic `availableReward` / `pendingReward` balances can be turned into real treasury outflows through a public claim function
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
       - explicitly test allowance-sensitive variants:
         - caller pulls from itself
         - caller pulls from a different approved account
         - caller pulls from a contract that has approved the protocol/helper/router
         - caller routes payout to a different receiver after pulling from an approved third party
         - permit / meta-tx / forwarder flow where signer, `msg.sender`, `_msgSender()`, payer, owner, and receiver differ
         - first-user / tiny-supply / tiny-share states
       - explicitly test transient-state variants:
         - mutate reserve/accounting state with a public sync/update function
         - immediately consume that mutated state in the next pricing / withdrawal / burn step
         - verify whether final state appears restored even though value was extracted during the intermediate bad state
       - explicitly test sentinel-address variants:
         - `address(0)`, dead address, pair, router, staking, treasury, distributor, helper, and escrow recipients/senders
         - whether any early return, bypass, or special-case branch for those addresses skips fee logic, buy/sell restrictions, claim gating, or accounting hooks
         - whether a swap or router path can legally force tokens to one of those sentinel addresses and thereby bypass intended restrictions
       - explicitly test stale-global-state ordering:
         - whether old pending buckets, fee buckets, burn debt, cached reserves, or prior-user state are consumed before the current user's action is accounted
         - whether the protocol mutates pair/vault/market balances from stale global state, calls `sync()` / update, and only afterward books the current order
         - whether the attacker can choose the current action amount or recipient to leave a target residual reserve and exploit the post-sync price
       - explicitly test forwarder-identity variants:
         - whether any path uses `msg.sender` for funding, allowance, burn source, callback source, refund recipient, or external call target while using `_msgSender()` for accounting credit, authorization, or payout recipient
         - whether a trusted forwarder can make one address fund/burn/approve while a different appended signer receives rewards, fees, or claim credit
         - whether a fresh signer with stale `lastActiveCycle`, `lastFeeUpdateCycle`, reward debt, or similar lifecycle state can replay historical reward or fee math using assets supplied by the forwarder
       - explicitly test reentrancy-before-invalidation variants:
         - whether a value-out path performs `call`, token transfer, router interaction, LP removal, NFT transfer, or any external interaction before clearing `isStaking`, `claimed`, `amount`, `lpAmount`, share balance, or similar authorizing state
         - whether `hasStaked`, `hasPosition`, `isActive`, balance checks, or entitlement checks still succeed during the external call window
         - whether pooled custody makes repeat use of the same stale record spend shared inventory rather than reverting against isolated user balances
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
     - **Critical-surface completion pass**:
       - do not stop after the first severe-looking issue
       - enumerate every critical value-moving family before finalizing:
         - `withdraw`, `unstake`, `redeem`, `claim`, `borrow`, `repay`, `liquidate`, `seize`, `mint`, `burn`, `deposit`, `removeLiquidity`, `sync`, `settle`, `execute`, `rescue`, `refund`
       - for each family, record whether review is complete, incomplete, blocked, or irrelevant
       - if one major finding is found early, continue auditing all remaining critical paths before ranking findings or writing the report
       - if a later path shows public pair-balance destruction, deferred pair-burn realization, or reserve mutation followed by `sync()`, rank that exploit above softer accounting, DoS, or owner-takeover issues unless the user explicitly asked for a different emphasis
       - if the code exposes all pieces of an exploit chain across different files or helper contracts, the audit is not complete until those pieces are synthesized into one end-to-end attack path or concretely disproven
       - for lending systems specifically, do not finalize before checking at least:
         - complete pool / market / reserve enumeration
         - empty-market / thin-market / first-depositor cases
         - exchange-rate / index / donation inflation cases
         - rounding and state-delta checks on thin markets
         - supply / deposit
         - withdraw / redeem
         - borrow
         - repay
         - liquidate / seize
         - self-liquidation / same-account liquidation
         - same-asset borrow-vs-collateral liquidation
         - admin / init / configuration takeover
         - oracle / pricing / collateral valuation
       - explicitly test attacker-chosen aliasing cases:
         - same address on both sides of an operation
         - same asset on both sides of an operation
         - different local storage references resolving to the same slot
         - same id / same record / same bucket / same role value on both sides of an operation
         - attacker-controlled equality conditions that collapse two logically distinct roles, accounts, assets, ids, records, or buckets into one storage target
         - sequential writes where the second write can overwrite the first, break netting assumptions, or mint / preserve value incorrectly
         - borrower and liquidator resolving to the same account in liquidation code
         - borrower collateral and liquidator collateral resolving to the same `(account, asset)` slot
         - helper-temporary account sequences that seed liquidity in one account and realize the aliased gain in another
       - these aliasing checks are source-level requirements and must be performed even without any exploit hint, trace, or onchain incident context
       - if any critical family is left unchecked, the audit is incomplete and must not be presented as fully covered
       - if any value-moving external dependency remains unchecked, the audit is incomplete and must not be presented as fully covered
     - **Weird-machine candidates**:
       - partial failure / `catch` / fallback branches
       - stale cached state vs live state
       - first-write-wins state
       - early-return branches for sentinel addresses (`address(0)`, dead, pair, router, staking, treasury)
       - “consume old global state first, then process current user action” orderings
       - trusted-forwarder identity splits where funding/burning/refunding uses `msg.sender` but accounting/payout uses `_msgSender()`
       - value-out functions that call out before clearing the record that authorizes withdrawal
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
     - asymmetric accounting where deposit/mint uses `amount * price`, `amount / price`, or equivalent one way, while withdraw/redeem/burn uses the same mutable price source in the opposite direction later
     - whether the same user claim, share, receipt, or ledger balance is first expanded by multiplying through price and later redeemed by dividing through a later mutable price, or vice versa
     - whether the same price path is read once during claim creation and again during claim redemption inside the same transaction or same short exploit loop
     - helper-contract math called by the hook/core but not defined there
     - repeated alternating swaps over many iterations, not just one sample round trip
     - whether a tiny directional bias compounds inside a callback, unlock, multicall, or router-driven loop
     - whether one swap direction gets consistently better pricing and the reverse leg does not fully cancel the edge
     - whether the approximated execution price differs from the true curve integral or exact invariant solution
     - whether the exact exploit path requires a sentinel recipient or sender such as `address(0)`, dead address, pair, router, or staking contract to bypass a guarded branch
     - whether the exploit relies on consuming stale pending state before the current swap/order is accounted, rather than on the current action alone
   - When a wrapper delegates the real pricing logic, the checklist must name both the wrapper and the delegated files.
   - For any custom curve or nonlinear helper-priced system, one agent must explicitly search for profit from repeated alternating swaps and compounding micro-edges rather than only one-shot drains.
   - For any token / AMM system that can touch pair balances, one agent must explicitly reconstruct the full chain `public user flow -> pending bucket / deferred mutation -> pair-side burn or reserve mutation -> sync/update -> final extraction trade`, even if a simpler direct bug has already been found elsewhere in the codebase.
   - For any token / AMM system with a public or permissionless helper/distributor/mining/reward contract, one agent must explicitly test whether that helper can be the unprivileged trigger for the reserve-mutation chain, even if the final reserve-touching function is role-gated on the token itself.
   - For any token / AMM system where rewards or settlements route through an intermediate `proof`, `power`, `mining`, `distributor`, or helper contract, one agent must explicitly test the exact chain `claim/reward/settlement trigger -> helper transfer/top-up -> pair inventory extraction -> sync/update -> quote-asset unwind`, and the audit must not conclude before that chain is either completed or concretely blocked.
   - For any token / AMM system that records deferred burn / pending burn / fee bucket / sell bucket state, one agent must explicitly test the exact chain `inventory accumulation -> sell or transfer creates deferred bucket -> public helper or maintenance call realizes pair-side mutation -> sync/update -> attacker dumps inventory`, and must not clear the system until that sequence is either proved profitable or concretely refuted.
   - If a token claims buys are blocked or wallet-only, one agent must explicitly search for router-held, pair-held, or helper-held inventory paths that still let an attacker accumulate inventory indirectly before the final extraction leg.
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
     - whether any unresolved external dependency still sits on the critical value path, and if so, which exploit families remain blocked pending that dependency review

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

6. **Donation / exchange-rate inflation checklist is mandatory for lending, vault, and wrapper systems.**
   - Before clearing any lending market, ERC4626 vault, wrapper, cToken/vToken-style market, or share-priced collateral system, identify and record:
     - where formal deposits / mints / supplies are accounted
     - where caps are enforced
     - where exchange rate / NAV / collateral value is computed
     - whether those computations use raw passive balances such as `IERC20(asset).balanceOf(address(this))`, `getCash`, or `totalAssets`
     - whether direct underlying transfers can reach the contract without minting offsetting shares
   - Explicitly test and note:
     - passive-donation path: `direct transfer -> priced assets increase -> share count unchanged`
     - whether supply caps or deposit caps are enforced only on formal mint/deposit paths
     - whether borrow power, redeemable value, or liquidation math trusts the inflated exchange rate
     - whether the exploit requires an empty market, or only a pre-existing share position plus a large donation
     - whether a loop exists of the form `deposit/mint -> donate underlying -> borrow/redeem -> repeat`
     - whether realizable market liquidity is materially below the inflated onchain collateral value
   - If passive donations can increase exchange rate or collateral value without minting offsetting shares, treat that as a first-class exploit candidate and complete the extraction path before clearing the system.

7. **Transient reserve-desync checklist is mandatory for reserve-priced systems.**
   - Before clearing any reserve-priced bonding-curve, AMM-like, mint/burn, or legacy treasury system, identify and record:
     - the storage variables that represent priced reserve versus locked / unsellable / treasury reserve
     - every public function or selector that mutates those variables
     - whether any path derives priced reserve from raw contract balance without subtracting locked funds
     - whether mint/burn/sell/buy logic reads those buckets before they are recomputed canonically
   - Explicitly test and note:
     - public `sync/update -> sell/burn` in the same transaction
     - repeated `mint/buy -> sync/update -> burn/sell -> repeat`
     - whether final end-of-tx storage looks consistent even though the intermediate pricing state was corrupted
     - whether a deferred maintenance path such as `distribute`, `process`, `harvest`, `rebalance`, `claim`, or mining/reward distribution can be called by an unprivileged user and thereby realize the corrupting reserve mutation on demand
   - Treat “restored by end of tx” as irrelevant if value can be extracted during the temporary bad state.
8. `{bundle_dir}/source.md` — a short `# Audit Scope` section listing the expanded source set, then a `# Discovery Checklist` section, then a `# Pricing / Invariant Hotspots` section capturing the checklist above, then ALL expanded in-scope `.sol` files, each with a `### path` header and fenced code block.
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
If the bundle contains any mint / redeem / borrow / repay / liquidate logic, you must explicitly test same-address and same-asset aliasing cases and report the outcome, even if no bug is found.
For liquidation systems specifically, test `borrower == liquidator` and `assetBorrow == assetCollateral` as mandatory source-level cases before concluding the path is safe.
Do not stop at isolated bugs. Try to compose weak signals across contracts, roles, status flags, time delays, offchain finality, and helper calls. For at least one candidate, model a malicious obligor or colluding two-address actor, then either complete the profit/obligation-evasion path or state the exact guard that blocks it.
```

**Turn 4 — Deduplicate, validate & output.** Single-pass: deduplicate all agent results, gate-evaluate, and produce the final report in one turn. Do NOT print an intermediate dedup list — go straight to the report.

Before report formatting, perform a **Critical Surface Completion Review**:

- confirm every critical value-moving family from discovery has been marked complete, blocked, irrelevant, or rejected with reasoning
- do not finalize the report just because one high-severity issue already exists
- if a stronger direct public exploit is found later in another critical path, it must replace weaker earlier findings as the primary finding
- if a public `claim/reward/helper -> pair/vault reserve extraction -> sync/update/finalization -> unwind` chain is still unresolved, the audit is incomplete and must not be finalized as if coverage were complete
- if review of any critical family remained incomplete, say so explicitly and do not imply full audit coverage
- when multiple findings exist, rank the more direct live public cash-out / solvency break above setup, config, or takeover issues unless the user asked for a different emphasis

1. **Deduplicate.** Parse every FINDING and LEAD from all 9 agents. Group by `group_key` field (format: `Contract | function | bug-class`). Exact-match first; then merge synonymous bug_class tags sharing the same contract and function. Keep the best version per group, number sequentially, annotate `[agents: N]`.

   Check for **composite chains** before any rejection:
   - if finding A's output feeds into B's precondition AND combined impact is strictly worse than either alone, add "Chain: [A] + [B]" at confidence = min(A, B)
   - if two LEADs share an id, asset, role, finality flag, accounting bucket, helper, oracle, allowance holder, or time boundary, attempt one combined exploit reconstruction before leaving both as separate leads
   - if the combined chain turns a griefing/DoS symptom into inventory retention, debt escape, false settlement, bad liquidation, borrow-power creation, claim replay, or reserve reclassification, evaluate the combined chain as its own candidate
   - if a malicious payer / distributor / maker / borrower / liquidator using two addresses makes the economics profitable, do not describe the issue as non-profitable outsider griefing without also recording that conditional profit model
   Most audits have 0-2 confirmed composite chains, but every audit must perform the synthesis pass.

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
   - `who was supposed to pay / deliver / repay / settle`
   - `whether profit is extracted funds or avoided obligation`
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
   - Did you test whether the attacker can first accumulate inventory indirectly through router-held output, helper-held output, LP-removal output, or other non-standard “buy blocked but inventory still accumulates” paths before the final dump?
   - If the exploit uses deferred burn / pending burn / fee buckets, did you identify the exact public function that realizes that deferred state and the exact transaction ordering needed to monetize it?
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

   **Do not refute pair-burn economics with one sample.** If public flow can burn pair inventory and then call `sync()`, a single negative round-trip at one size is not enough to demote the issue. Search attacker-controlled sizing that makes the pair-side burn dominate remaining reserves, include flashloan bankroll and threshold wake-up effects, and test the exact `inventory source -> pair burn -> sync -> opposite-reserve extraction` sequence before clearing or downgrading.

   **Optional external corroboration.** If the user supplies supporting artifacts, before clearing or demoting a candidate exploit, explicitly answer:
   - does the source-level call chain match the supplied transaction trace?
   - do the arithmetic formulas in code match the supplied balances / trace values / RCA math?
   - were the live proxy implementations and value-path dependencies fetched and checked?
   - if something could not be fetched, does the remaining source evidence still complete the exploit chain strongly enough to report the issue?
   Do not require external corroboration to promote a source-complete exploit.

3. **Lead promotion & rejection guardrails.**
   - Promote LEAD → FINDING (confidence 75) if: complete exploit chain traced in source, OR `[agents: 2+]` demoted (not rejected) the same issue.
   - `[agents: 2+]` does NOT override a concrete refutation — demote to LEAD if refutation is uncertain.
   - No deployer-intent reasoning — evaluate what the code _allows_, not how the deployer _might_ use it.
   - If source-level exploit reconstruction is complete and no concrete code-level refutation survives, do not leave the issue as a dependency-only LEAD merely because some supporting dependencies were fetched from explorers rather than the local repo.
   - If a public pair-burn / reserve-destruction path remains unresolved after source reconstruction, do not finalize the audit as complete; either complete the economics and trigger analysis or explicitly mark the audit incomplete on that family.

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

7. **Format and print** per `report-formatting.md`. Exclude rejected items. The final answer must be the report itself, not a prose summary. Every surviving finding must keep its bracketed confidence score, Status block, and PoC Concept block. If `--file-output`: also write to file.

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
