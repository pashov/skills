# Finding Validation

Every finding passes four sequential gates. Fail any gate → **rejected** or **demoted** to lead. Later gates are not evaluated for failed findings.

## Mandatory Pre-Check

Before Gate 1, every candidate issue must be labeled as one of:

- **Public Exploitable** — unprivileged actor can trigger it
- **Privileged / Centralization** — only owner / admin / oracle / approved role can trigger it
- **Code-Level / Config-Dependent** — source bug exists but live exploitability depends on config or unresolved external state

Anything not first labeled **Public Exploitable** must not be described as attacker-profitable.

For any issue that may be economic or profitable, fill this mini-table before gating:

- `value source`
- `trigger function`
- `permission required`
- `recipient of value`
- `why attacker gets paid`

If any row is missing or unclear, profitability is **not confirmed**.

Before Gate 1, discovery must also answer:

- what assumption is being inverted
- what non-standard path is being tested
- whether the path uses helper / fallback / receiver / registry / subscriber / unusual ordering instead of the intended wrapper flow
- whether the code relies on `tx.origin`, `msg.sender == tx.origin`, `code.length == 0`, `isContract`, or similar EOA-only assumptions that should be treated as weak because delegated-EOA / account-abstraction behavior (including EIP-7702-style models) can violate the intended trust model
- whether any trusted-forwarder / relay / `execute` path can make funding, allowance ownership, burn source, callback user, accounting credit, refund recipient, and payout recipient diverge because the code mixes `msg.sender` and `_msgSender()`
- whether a forwarder-aware contract composes with a non-forwarder-aware token/helper in a way that lets a fresh signer inherit stale reward or fee math using assets supplied by the forwarder
- whether any value-out function (`withdraw`, `unstake`, `redeem`, `claim`, `removeLiquidity`, `refund`, `rescue`, native send, token transfer`) makes an external interaction before invalidating the record or entitlement that authorizes the exit
- whether custody for the withdrawn asset is pooled at contract level, so repeated use of one stale record can spend shared inventory instead of isolated user balances
- whether the path depends on crossing a threshold such as `minDispatch`, `swapBack`, `rebalance`, `burnPool`, `liquidate`, `harvest`, or any fee accumulator
- whether a large-capital or flashloan actor can cross that threshold in one transaction
- whether live reserves, balances, and taxes make the path economically meaningful rather than merely reachable
- whether the protocol is a fork / close derivative of a known design and whether known parent-protocol attack classes were checked
- whether an empty or near-empty market / pool / vault / share system could be bootstrapped into a profitable mispricing state
- whether a Compound/Venus-style market lets a pre-existing share holder donate underlying directly to the market, keep the same share count, and still gain borrow power through a higher exchange rate
- whether an empty or near-empty reserve could amplify `liquidityIndex`, `variableBorrowIndex`, normalized income, or any other accumulator used later in scaled-balance accounting
- whether public flashloan premiums, fee updates, or reserve-update paths can be looped repeatedly against a dust denominator
- whether the protocol separates priced reserve, locked reserve, treasury reserve, raw balance, or other reserve buckets, and whether a public path can reclassify one bucket into another
- whether any public sync/reconcile/update function can transiently make pricing or payout logic read from the wrong reserve bucket
- whether Morpho / MetaMorpho / lending-vault specific risk classes were checked: allocator/curator routing, downstream empty markets, oracle/collateral weakness, cap misconfiguration, withdrawal-liquidity starvation, and vault share bootstrap
- whether a deposit / fee / `netValue` / principal contribution is being counted both as distributable reward and as fully withdrawable principal
- whether reward payout reduces the same liability bucket from which the reward was derived, or only spends cash while liabilities remain overstated
- whether two attacker-controlled accounts can cycle deposits, reward accrual, withdrawals, and principal exits to realize the accounting mismatch
- whether insolvency or low live balance turns an otherwise circular reward model into an immediate public drain
- whether every value-moving path preserves state-delta equality between:
  - user mint/burn/borrow/repay amount
  - global supply / debt / shares / assets mutation
  - transferred underlying amount
- whether any clamp, sentinel branch, balance cap, or rounding adjustment is applied only after global state has already been mutated
- whether dust-position variants (`dust mint -> large redeem`, `dust collateral -> large borrow`, `redeemUnderlying(getCash())`, `type(uint256).max`) were checked
- for Morpho / MetaMorpho style systems, whether each specific issue family was explicitly considered and either validated or disproven:
  - empty / near-empty downstream market attack
  - bad curation / cap attack
  - oracle / collateral misconfiguration attack
  - withdrawal-liquidity starvation
  - ERC4626 / donation / first-depositor share inflation
  - fork-with-minimal-diff inherited issue class

Do not reject an issue just because the standard path looks safe if the unusual path has not been checked.

## Gate 1 — Refutation

Construct the strongest argument that the finding is wrong. Find the guard, check, or constraint that kills the attack — quote the exact line and trace how it blocks the claimed step.

- Concrete refutation (specific guard blocks exact claimed step) → **REJECTED** (or **DEMOTE** if code smell remains)
- Speculative refutation ("probably wouldn't happen") → **clears**, continue
- A `tx.origin` / EOA / wallet-only check does **not** refute a finding if the same state change is reachable through `receive()`, `fallback()`, deposit, claim, helper, or any other externally callable path
- A `msg.sender == tx.origin`, `code.length == 0`, or `isContract == false` check is a **flagged anti-pattern**, not a strong refutation, because delegated EOAs / account-abstraction behavior (including EIP-7702-style models) weakens the intended “EOA-only” guarantee
- A safe intended UX flow does **not** refute a finding if an uglier legal sequence can still reach the same value movement

## Gate 2 — Reachability

Prove the vulnerable state exists in a live deployment.

- Structurally impossible (enforced invariant prevents it) → **REJECTED**
- Requires privileged actions outside normal operation → **DEMOTE**
- Cross-contract helper / hook / library logic that the target contract actually calls is the same exploit surface, not an optional dependency review
- If execution price, reserve updates, or invariant enforcement are delegated, those delegated files are the critical path even when the named wrapper looks safe in isolation
- If the exploit depends on configurable parameters or reserve ratios, test reachable defaults, allowed config bounds, and normal reserve skews before rejecting
- If the system is a fork of a known protocol, do not reject inherited issue classes until the source diff proves the critical invariant changed
- For live audits, verify the actual onchain config values before treating a code bug as active
- If live role holders are EOAs / multisigs with no public takeover path, keep the issue in `Privileged / Centralization`, not `Public Exploitable`
- Achievable through normal usage or common token behaviors → **clears**, continue
- Payable `receive()` / `fallback()` entrypoints, flash loans, router callbacks, and helper-contract claims are normal reachable behavior when the code exposes them
- Unusual but legal call ordering, first-write-wins poisoning, direct helper entry, and purpose-built exploit wallets are normal reachable behavior when public functions permit them
- EOA-only assumptions are not enough to demote reachability when delegated-EOA or account-abstraction semantics could exercise the same public path
- Empty-market / first-depositor / share-inflation / donation-boosted bootstrap states are normal reachable behavior if the protocol can launch or interact while depth is near zero
- Direct underlying donation into a collateral market is normal reachable behavior if the market contract can receive the token and exchange-rate logic reads raw balance without minting offsetting shares
- Reserve-index amplification on dust liquidity is normal reachable behavior if public actions can both shrink reserve liquidity and later update the index through flashloans, fees, or repayments
- Transient reserve-bucket corruption is normal reachable behavior if a public sync/update path can be called immediately before a burn/sell/redeem step, even if final storage is restored later in the same transaction
- Allocator / curator / cap / withdrawal-queue states are normal reachable behavior in Morpho/MetaMorpho-style vaults and must be checked before rejecting those issue classes
- When a system is a close fork of a historically exploited lending/vault design, unchanged critical assumptions should be presumed inherited until the source diff proves otherwise

## Gate 3 — Trigger

Prove an unprivileged actor executes the attack.

- Only trusted roles can trigger → **DEMOTE**
- If the value is redirected to protocol treasury / feeRecipient / owner rather than the caller, this is **not** outsider profit unless attacker control or collusion is proven
- Costs exceed extraction → **REJECTED** only after evaluating realistic repeated execution and compounding, not just a single iteration
- A single loss-making sample at one parameter point is not enough to reject a pricing exploit with a complete source-level trace
- A single harmless sample does **not** refute approximation bias, midpoint/average pricing, or micro-edge compounding on a nonlinear curve; repeated iterations and callback-loop execution must be checked
- Unprivileged actor triggers profitably → **clears**, continue
- If a purpose-built exploit contract can trigger the path with public entrypoints and borrowed capital, treat it as unprivileged even when the protocol expected EOAs or wallets
- If the path only activates after a threshold is crossed, do not reject until you test whether realistic capital or a flash loan can cross it
- If a helper/router/vault/distributor performs the real swap or payout, the helper's live balances, approvals, and recipients are part of the same trigger analysis
- A circular reward model is not “just design” if a public attacker can use temporary capital or multiple addresses to withdraw more cash than the protocol can safely back
- If the initial effect is griefing, you must still test common profit-conversion pivots before rejecting profitability:
  - attacker-controlled recipient / sink / referrer / helper
  - front-run / back-run
  - repeated micro-extraction
  - state poisoning followed by later extraction

## Gate 3.5 — Reserve Reality Check

For AMM-, vault-, liquidation-, or reserve-facing issues, ask:

- What are the live reserves and balances?
- How large is the forced move relative to those reserves?
- What are the round-trip costs from swap fees, token taxes, slippage, and price impact?
- Does the edge only become positive after repeated iterations rather than a single round trip?
- Is the pricing function exact, or is it a midpoint / average / interpolated / cached approximation of a nonlinear curve?
- Do reserve updates use gross input while output pricing uses net-after-fee input, or any other mismatched effective amount?
- Is the path dead, dormant, or immediately live?
- Is the market / pool / vault currently empty or near-empty, and does that change exchange-rate, collateral, liquidation, or share-pricing assumptions?

If reserve depth, threshold reachability, and realistic round-trip costs were not checked, attacker profitability is **not confirmed**.

## Gate 3.55 — Reserve Index Check

For Aave-style or scaled-balance lending markets, ask:

- Can a public actor first reduce reserve liquidity to dust or near dust?
- Does any public flashloan, fee, repay, or reserve-update path increase `liquidityIndex`, `variableBorrowIndex`, normalized income, or a related accumulator using that dust liquidity as denominator?
- Can repeated self-flashloans or fee-generating loops compound the index materially?
- After index manipulation, do scaled mint/burn/balance conversions round in a way that lets tiny deposits or balances support larger withdrawals, collateral value, or borrow power?
- Does the exploit require only public lending-core paths, even if wrappers/periphery look unrelated?

If these questions were not checked, attacker profitability for Aave-style reserve systems is **not confirmed**.

## Gate 3.56 — Compound / Venus Donation Check

For Compound-style or exchange-rate-backed lending markets, ask:

- Can a user with a pre-existing cToken/vToken balance donate underlying directly to the market without minting new shares?
- Does `exchangeRateStored`, `exchangeRateStoredInternal`, `getCash`, or equivalent reserve-backed accounting treat that donation as additional backing for all existing shares?
- Do liquidity / borrow checks then multiply the unchanged share balance by the inflated exchange rate, oracle price, and collateral factor to create new borrow capacity?
- Can the attacker loop `borrow -> swap -> donate underlying -> borrow again` until shortfall or bad debt appears?
- Does the exploit work only in an empty market, or also in a non-empty market with a sufficiently large direct donation?

If these questions were not checked, attacker profitability for Compound/Venus-style collateral markets is **not confirmed**.

## Gate 3.57 — Reserve Bucket Check

For reserve-priced mint/burn/swap/treasury systems, ask:

- Does the protocol distinguish between priced reserve, locked reserve, treasury reserve, claimable reserve, and raw balance?
- Can any public `sync`, `reconcile`, `refresh`, `skim`, `settle`, or selector-level function rewrite priced reserve from raw balance without excluding locked funds?
- Can a user call that function and then immediately invoke burn/sell/redeem/withdraw logic before the protocol restores canonical accounting?
- Is the exploit profitable even if the final end-of-tx state looks consistent again?

If these questions were not checked, attacker profitability for bucketed-reserve systems is **not confirmed**.

## Gate 3.58 — LP Reserve Destruction Check

For token / AMM systems that can touch pair balances, ask:

- Can any public sell hook, transfer hook, pending-burn bucket, fee bucket, or maintenance path burn or otherwise destroy tokens directly from the LP/pair address?
- Is that pair-side destruction fed by public user actions rather than only privileged admin calls?
- Does the contract call `sync()` after pair-side destruction, making the reserve skew immediately tradable?
- Can an attacker loop `buy -> trigger sell/transfer hook -> accumulate pair-burn debt -> burn pair reserve -> sync -> extract opposite reserve`?
- Can any sentinel recipient/sender such as `address(0)`, dead address, pair, router, staking contract, treasury, or distributor bypass a guarded buy/sell/fee branch through an early return or special-case path?
- Does the protocol consume stale global pending state (fee bucket, burn debt, cached reserve mutation) before the current user's action is accounted, letting the attacker choose the current action to exploit the already-mutated reserves?
- After realistic flashloan size, taxes, fees, and slippage, does collapsing the token-side reserve leave the opposite reserve profitably drainable?

If these questions were not checked, attacker profitability for pair-burn / LP-reserve-destruction systems is **not confirmed**.

## Gate 3.59 — Sentinel Address / Sequence Reconstruction Check

For hook-driven tokens, routers, vaults, and reserve-mutating systems, ask:

- Do any branches special-case `address(0)`, dead address, pair, router, staking, treasury, distributor, escrow, or helper addresses?
- Can one of those sentinel addresses bypass a restriction only because the code returns early before the guarded path or accounting hook runs?
- Can a router or pair legally force assets to that sentinel address during a public swap/mint/burn path?
- Is there at least one concrete exploit sequence that goes beyond the bug family and specifies the actual order, including seed action, state mutation, bypass branch, dust trigger if needed, and final extraction leg?
- Does the path rely on consuming stale global state before the current action, rather than on the current action alone?

If these questions were not checked, attacker profitability for sentinel-address / exact-sequence exploits is **not confirmed**.

## Gate 3.60 — Forwarder Identity Split Check

For ERC2771 / relay / trusted-forwarder systems, ask:

- Does any value-moving path use raw `msg.sender` for funding, allowance ownership, burn source, callback source, or refund destination while using `_msgSender()` for accounting credit, authorization, or payout?
- Can a forwarder-aware contract interact with a non-forwarder-aware token or helper so that the forwarder supplies assets or approvals while the appended signer receives credit, rewards, fees, or claims?
- After the forwarder-mediated action, do lifecycle variables such as `lastActiveCycle`, `lastFeeUpdateCycle`, `rewardDebt`, `nonce`, `claimed`, or similar remain stale for the credited signer?
- Can a fresh or stale signer replay old reward/fee/cycle math using assets burned, approved, or funded by the forwarder?

If these questions were not checked, attacker profitability for forwarder-identity-split exploits is **not confirmed**.

## Gate 3.61 — Value-Out Reentrancy Check

For withdrawal / unstake / redeem / claim / liquidity-removal systems, ask:

- Does the function perform any external interaction before clearing or invalidating the user record that authorizes the withdrawal?
- During that interaction window, do `hasStaked`, `hasPosition`, `isActive`, balance/entitlement checks, or similar still pass on the same record?
- Can a fallback or hook reenter the same function or a sibling value-out function before the record is cleared?
- If pooled assets are used, does the repeated call spend shared contract inventory rather than isolated user custody?

If these questions were not checked, attacker profitability for value-out reentrancy exploits is **not confirmed**.

## Gate 3.6 — Reward Solvency Check

For reward-, staking-, dividend-, yield-, referral-, or principal-tracking systems, ask:

- Is newly deposited or newly accrued value counted twice: once as distributable reward and again as fully withdrawable principal / share value?
- Does `claim`, `withdraw`, `harvest`, `reinvest`, or equivalent reduce the same liability accounting that created the reward?
- Can an attacker use two or more controlled addresses to seed principal, inflate pending rewards, withdraw reward from one side, and then exit principal from the other?
- Does the exploit need real external yield, or can it be funded entirely by later deposits, temporary capital, or flash-loaned liquidity?
- Does the protocol become immediately drainable once cash-on-hand is lower than reported contributed principal / assets / shares / liabilities?
- Are public variables such as `totalContributed`, `accRewardPerShare`, `rewardDebt`, `claimedSoFar`, `shares`, `assets`, `principal`, or equivalent left overstated after cash leaves the contract?
- Are deposit, rank, or qualification thresholds scaled to the token's actual decimals, or can a tiny deposit satisfy a whole-token requirement because the code compares against a raw literal?
- Is a one-time reward / pool / rank latch checked but never flipped after the payout, allowing the same reward path to fire repeatedly?
- Can a referrer or sponsor use many cheap helper accounts to repeatedly satisfy the same threshold and mint treasury-backed rewards?
- Does the public claim path convert synthetic accounting balances into real treasury outflows without an independent reserve-backing check?

If these questions were not checked, attacker profitability for reward/accounting systems is **not confirmed**.

## Gate 3.7 — Value-Moving Invariant Check

For mint/redeem/borrow/repay/liquidate/claim/withdraw/share-conversion systems, ask:

- Does the global state delta equal the per-user state delta for the same economic action?
- Is the transferred amount derived from the same effective quantity that is burned/minted/borrowed/repaid in storage?
- Are clamps, caps, sentinel values, dust handling, or balance checks applied before both global and per-user mutations, rather than after one side has already changed?
- Can a dust position trigger a large quoted transfer while only a tiny user balance is burned or locked?
- Does any path reduce `totalSupply`, `totalBorrows`, `totalAssets`, `shares`, or similar global values by a larger amount than is actually removed from the attacker account?
- After a full `claim`, `withdraw`, `redeem`, `unlock`, `cancel`, `collect`, or `settle`, is the primary source-of-truth record actually invalidated rather than only an auxiliary index/list/lookup helper?
- Can the same id / record be used twice because the payout authorization still reads from an uncleared primary record?

If these questions were not checked, attacker profitability for value-moving accounting systems is **not confirmed**.

## Gate 4 — Impact

Prove material harm to an identifiable victim.

- Self-harm only → **REJECTED**
- Dust-level, no compounding → **DEMOTE**
- Repeated micro-bias that compounds into measurable pool or vault loss is **not** dust
- Material loss to identifiable victim → **CONFIRMED**

## Confidence

Start at **100**, deduct: partial attack path **-20**, bounded non-compounding impact **-15**, requires specific (but achievable) state **-10**. Confidence ≥ 80 gets description + fix. Below 80 gets description only.

## Safe patterns (do not flag)

- `unchecked` in 0.8+ (but verify the reasoning is correct)
- Explicit narrowing casts in 0.8+ (reverts on overflow)
- MINIMUM_LIQUIDITY burn on first deposit
- SafeERC20 (`safeTransfer`/`safeTransferFrom`)
- `nonReentrant` (only flag cross-contract attacks)
- Two-step admin transfer
- Consistent protocol-favoring rounding unless compounding or zero-rounding

## Lead promotion

Before finalizing leads, promote where warranted:

- **Cross-contract echo.** Same root cause confirmed as FINDING in one contract → promote in every contract where the identical pattern appears.
- **Multi-agent convergence.** 2+ agents flagged same area, lead was demoted (not rejected) → promote to FINDING at confidence 75.
- **Partial-path completion.** Only weakness is incomplete trace but path is reachable and unguarded → promote to FINDING at confidence 75, description only.
- **Parameter-sensitive economics.** If the source trace is complete and the only open question is which reachable configuration or reserve regime turns it profitable, do not reject on one default sample. Demote to LEAD only after searching the reachable parameter space.
- **Threshold-sensitive economics.** If the source trace is complete and the only open question is whether a whale/flashloan can wake a dormant thresholded path, do not reject until that threshold reachability is checked.
- **Approximation-sensitive economics.** If the source trace shows midpoint bias, average-price execution, nonlinear approximation, or gross/net reserve mismatch, do not reject until repeated-iteration and callback/multicall compounding has been checked.
- **Fork-sensitive economics.** If the code is a near-fork of a historically exploited design, do not reject the inherited issue class until the source diff proves the critical bootstrap or accounting assumption was actually changed.
- **Reserve-index economics.** If the source trace shows dust-liquidity denominators feeding public index updates and later scaled-balance valuation, do not demote it to “empty-market smell” until repeated flashloan/fee compounding and post-index rounding have been checked.
- **Donation-inflation economics.** If the source trace shows direct underlying donations can raise exchange rate or collateral value for an unchanged share balance, do not demote it to “design” or “non-empty market” until pre-existing-holder, recursive-borrow, and post-liquidation bad-debt variants have been checked.
- **Transient reserve economics.** If the source trace shows a public sync/update path can temporarily reclassify locked or unsellable funds into the priced reserve, do not demote it to “eventual consistency” until a same-tx `sync -> burn/sell/redeem` extraction loop has been checked.
- **Pair-burn economics.** If the source trace shows public user flow feeds a pending burn bucket or other path that can burn LP/pair inventory and then `sync()`, do not demote it to “tokenomics” until `buy -> hook -> pair-burn -> sync -> opposite-reserve extraction` has been checked.
- **Sentinel-bypass economics.** If the source trace shows an early return or special-case branch for `address(0)`, dead address, pair, router, staking, treasury, or distributor, do not demote it to “edge case” until buy/sell/claim bypass and exact exploit-sequence variants have been checked.
- **Stale-global-state economics.** If the source trace shows stale pending state is consumed before the current user action is accounted, do not stop at the bug family; complete one exact exploit sequence showing how the attacker chooses amount/recipient/order to realize the skew.
- **Forwarder-identity economics.** If the source trace shows mixed `msg.sender` / `_msgSender()` usage across funding, burn, callback, accounting, or payout, do not demote it to “meta-tx integration issue” until a forwarder-supplied / signer-credited exploit sequence has been checked.
- **Value-out reentrancy economics.** If the source trace shows a value-out function performing an external call or LP removal before invalidating the authorizing record, do not demote it to “missing nonReentrant” or “theoretical reentrancy” until pooled-custody and same-record repeat-withdraw variants have been checked.
- **Reward-solvency economics.** If the source trace shows a deposit being booked both as reward source and withdrawable principal, do not demote it to “economic design” until a two-account / temporary-capital extraction attempt has been checked.
- **Reward-threshold economics.** If the source trace shows a reward threshold using raw literals against decimal-scaled token amounts, or a one-time reward latch checked but never consumed, do not demote it to “logic bug” until helper-farmed reward amplification and treasury claim-out have been checked.
- **State-delta economics.** If the source trace shows global mint/burn/supply/debt mutation using a different amount than the per-user mutation or final transfer, do not demote it as “standard fork logic” until dust-position, sentinel-value, and full-cash variants have been checked.
- **One-time-claim economics.** If the source trace shows settlement clears only an owner index / helper list / enumerable set while the primary record still authorizes payout, do not demote it to “bookkeeping” until same-id repeat-claim / repeat-withdraw has been checked.

## Leads

High-signal trails for manual investigation. No confidence score, no fix — title, code smells, and what remains unverified.

Leads should be favored over rejection when:

- the path is unusual but legal and has not been fully stress-tested
- the bug is clearly real but monetization is incomplete
- the standard flow is safe but helper / fallback / receiver / first-write / sequence variants remain open

## Final Conclusion

The report must end with an explicit attacker-profitability conclusion for a **non-owner / unprivileged attacker**:

- **Yes**: at least one surviving finding proves a complete profitable path for an unprivileged actor.
- **No**: no surviving finding proves attacker profit, even if the contract still contains honeypot logic, griefing, freezing, or owner-only abuse.
- **Inconclusive**: the best remaining evidence is a lead or demoted finding with incomplete profitability proof.

Also explicitly distinguish:

- **code bug exists**
- **live on this deployment**
- **publicly exploitable**
- **attacker profitable**
- **privileged-only risk**

## Do Not Report

Linter/compiler issues, gas micro-opts, naming, NatSpec. Admin privileges by design. Missing events. Centralization without exploit path. Implausible preconditions (but fee-on-transfer, rebasing, blacklisting ARE plausible for contracts accepting arbitrary tokens).
