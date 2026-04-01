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
- whether the path depends on crossing a threshold such as `minDispatch`, `swapBack`, `rebalance`, `burnPool`, `liquidate`, `harvest`, or any fee accumulator
- whether a large-capital or flashloan actor can cross that threshold in one transaction
- whether live reserves, balances, and taxes make the path economically meaningful rather than merely reachable
- whether the protocol is a fork / close derivative of a known design and whether known parent-protocol attack classes were checked
- whether an empty or near-empty market / pool / vault / share system could be bootstrapped into a profitable mispricing state
- whether Morpho / MetaMorpho / lending-vault specific risk classes were checked: allocator/curator routing, downstream empty markets, oracle/collateral weakness, cap misconfiguration, withdrawal-liquidity starvation, and vault share bootstrap
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
- If the exploit depends on configurable parameters or reserve ratios, test reachable defaults, allowed config bounds, and normal reserve skews before rejecting
- If the system is a fork of a known protocol, do not reject inherited issue classes until the source diff proves the critical invariant changed
- For live audits, verify the actual onchain config values before treating a code bug as active
- If live role holders are EOAs / multisigs with no public takeover path, keep the issue in `Privileged / Centralization`, not `Public Exploitable`
- Achievable through normal usage or common token behaviors → **clears**, continue
- Payable `receive()` / `fallback()` entrypoints, flash loans, router callbacks, and helper-contract claims are normal reachable behavior when the code exposes them
- Unusual but legal call ordering, first-write-wins poisoning, direct helper entry, and purpose-built exploit wallets are normal reachable behavior when public functions permit them
- EOA-only assumptions are not enough to demote reachability when delegated-EOA or account-abstraction semantics could exercise the same public path
- Empty-market / first-depositor / share-inflation / donation-boosted bootstrap states are normal reachable behavior if the protocol can launch or interact while depth is near zero
- Allocator / curator / cap / withdrawal-queue states are normal reachable behavior in Morpho/MetaMorpho-style vaults and must be checked before rejecting those issue classes
- When a system is a close fork of a historically exploited lending/vault design, unchanged critical assumptions should be presumed inherited until the source diff proves otherwise

## Gate 3 — Trigger

Prove an unprivileged actor executes the attack.

- Only trusted roles can trigger → **DEMOTE**
- If the value is redirected to protocol treasury / feeRecipient / owner rather than the caller, this is **not** outsider profit unless attacker control or collusion is proven
- Costs exceed extraction → **REJECTED** only after evaluating realistic repeated execution and compounding, not just a single iteration
- A single loss-making sample at one parameter point is not enough to reject a pricing exploit with a complete source-level trace
- Unprivileged actor triggers profitably → **clears**, continue
- If a purpose-built exploit contract can trigger the path with public entrypoints and borrowed capital, treat it as unprivileged even when the protocol expected EOAs or wallets
- If the path only activates after a threshold is crossed, do not reject until you test whether realistic capital or a flash loan can cross it
- If a helper/router/vault/distributor performs the real swap or payout, the helper's live balances, approvals, and recipients are part of the same trigger analysis
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
- Is the path dead, dormant, or immediately live?
- Is the market / pool / vault currently empty or near-empty, and does that change exchange-rate, collateral, liquidation, or share-pricing assumptions?

If reserve depth, threshold reachability, and realistic round-trip costs were not checked, attacker profitability is **not confirmed**.

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
- **Fork-sensitive economics.** If the code is a near-fork of a historically exploited design, do not reject the inherited issue class until the source diff proves the critical bootstrap or accounting assumption was actually changed.

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

## Exploit-Tx Priority

If the user provides a concrete exploit transaction, treat that transaction as a first-class validation artifact:

- Reconstruct the observed path from the receipt and map it back to local source
- Prefer the observed exploit path over cleaner speculative theories
- If the exploit used a helper contract, flash loan, payable entrypoint, or claim path, do not downgrade the issue just because the wrapper token path looked restricted
- If the exploit depends on a large trade, threshold crossing, or reserve manipulation, do not mark it profitable until reserve depth and round-trip economics were checked on realistic live state
