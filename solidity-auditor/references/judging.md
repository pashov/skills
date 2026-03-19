# Finding Validation

Every finding must pass through four sequential gates. Gates are evaluated in order — if a finding fails any gate, it is immediately **rejected** or **demoted** to a lead. Later gates are never evaluated for a failed finding. A finding that clears all four gates is **confirmed**.

## Gate 1 — Refutation

Before anything else, construct the strongest possible argument that the finding is wrong. This is mandatory — no finding skips this gate.

- **Search for the kill shot.** Find the single guard, check, modifier, or structural constraint that makes the claimed attack impossible. Quote the exact line. Trace how it blocks the specific claimed attack step.
- **Check execution context.** Is the caller restricted? Is the function unreachable in the claimed state? Does an earlier operation in the same flow already close the gap?
- **Trace downstream.** If the finding claims state corruption, check every reader of that state. If every reader either reverts safely or recalculates independently, the corruption has no impact.

**Outcome:**
- Refutation is **concrete** (quotes a specific guard and traces how it blocks the exact claimed step) → **REJECTED**. If a code smell remains despite the refutation, **DEMOTE** to lead instead.
- Refutation is **speculative** ("this probably wouldn't happen", "the deployer would likely configure it safely") → finding **clears** Gate 1. Continue to Gate 2.

## Gate 2 — Reachability

Can the vulnerable state actually exist in a live deployment?

- Identify the precondition the attack requires (specific storage state, parameter range, token behavior, timing window).
- Trace whether any code path — including deployment, configuration, and normal user operations — can produce that precondition.
- Check whether an invariant structurally prevents the precondition from ever holding.

**Outcome:**
- Precondition is **structurally impossible** (an enforced invariant prevents it, not just unlikely usage) → **REJECTED**.
- Precondition requires a **sequence of privileged actions that would not occur in normal operation** → **DEMOTE** to lead.
- Precondition is **achievable** through normal protocol usage or common token behaviors → finding **clears** Gate 2. Continue to Gate 3.

## Gate 3 — Trigger

Can an external, unprivileged actor execute the attack?

- Determine who can call the vulnerable function. If restricted to a trusted role (owner, admin, governance), the attack requires a compromised or malicious privileged actor — this is a trust assumption, not a vulnerability.
- Check whether the attacker needs to control transaction ordering (front-running, sandwich). If so, verify the ordering is actually controllable (public mempool, no commit-reveal, no batch auction).
- Check whether the attack requires capital. If it costs more to execute than it extracts (even with borrowed capital), it is economically irrational.

**Outcome:**
- Only a trusted privileged role can trigger it → **DEMOTE** to lead.
- Attack is economically irrational (costs exceed extraction) → **REJECTED**.
- An unprivileged actor can trigger it profitably → finding **clears** Gate 3. Continue to Gate 4.

## Gate 4 — Impact

Does the attack cause material harm to an identifiable victim?

- Trace the full attack path to its final state. Identify who loses value and how much.
- If the damage is limited to the attacker's own funds (self-harm), it is not a vulnerability.
- If the damage is bounded to dust or rounding artifacts with no compounding path, it is not material.

**Outcome:**
- No victim other than the attacker → **REJECTED**.
- Damage is immaterial (dust-level, no compounding) → **DEMOTE** to lead.
- Identifiable victim suffers material loss → finding is **CONFIRMED**.

## Confidence

Confirmed findings start at **100**. Apply deductions:

- Attack path is partial (general direction is sound but cannot trace exact entry → state change → value extraction) → **-20**.
- Impact is bounded and does not compound across users or over time → **-15**.
- Requires specific but achievable protocol state (not the default/common state) → **-10**.

Confidence indicator: `[score]` (e.g., `[95]`, `[80]`, `[65]`).

Findings with confidence ≥ 80 get a description and a fix. Below 80 get description only, no fix.

## Safe patterns (do not flag)

These patterns look dangerous but are intentionally safe. If a finding matches one, verify the match is exact before rejecting:

- **Unchecked arithmetic in Solidity 0.8+**: `unchecked` blocks are intentional — but verify the developer's overflow/underflow reasoning is actually correct. If the reasoning is wrong, that IS a finding.
- **Explicit narrowing casts in Solidity 0.8+**: `uint112(x)` reverts at runtime if `x > type(uint112).max`. This is NOT silent truncation — it's a built-in guard. Do not report unless the code is 0.7 or earlier.
- **MINIMUM_LIQUIDITY burn on first deposit**: Prevents share inflation attacks. Not a vulnerability.
- **SafeERC20 wrapping**: `safeTransfer`/`safeTransferFrom` handles void-return tokens. If present, do not report missing return value checks on that token call.
- **ReentrancyGuard on the function**: `nonReentrant` prevents same-contract reentrancy. Only flag if the attack path is cross-contract (different pool, different contract).
- **Two-step admin transfer**: `setPendingAdmin → acceptAdmin` is safe — do not flag as "admin can be transferred."
- **Consistent rounding direction**: If deposits round shares DOWN and withdrawals round assets DOWN (protocol-favoring), do not flag as rounding error unless you can show compounding or zero-rounding.

## Leads

Leads are NOT false positives — they are high-signal trails that need deeper manual investigation. Not given a confidence score or fix — just a title, the code smells found, and a 1-2 sentence description of what remains unverified.

## Do Not Report

- Anything a linter, compiler, or seasoned developer would dismiss — INFO-level notes, gas micro-optimizations, naming, NatSpec, redundant comments.
- Owner/admin can set fees, parameters, or pause — these are by-design privileges, not vulnerabilities.
- Missing event emissions or insufficient logging.
- Centralization observations without a concrete exploit path (e.g., "owner could rug" with no specific mechanism beyond trust assumptions).
- Theoretical issues requiring implausible preconditions (e.g., compromised compiler, corrupt block producer, >50% token supply held by attacker). Note: common ERC20 behaviors (fee-on-transfer, rebasing, blacklisting, pausing) are NOT implausible — if the code accepts arbitrary tokens, these are valid attack surfaces.
