# Finding Validation

Each finding passes a false-positive gate, then gets a confidence score (how certain you are it is real).

## FP Gate

Every finding must pass all three checks. If check 2 or 3 fails, drop the finding. If only check 1 fails but concrete code smells are present (missing guards, unsafe arithmetic, unvalidated input), move the finding to the **Leads** section instead of dropping it.

1. You can trace a concrete attack path: caller → function call → state change → loss/impact. Evaluate what the code _allows_, not what the deployer _might choose_. For any finding involving token transfers or swaps, verify which token moves IN and which moves OUT before concluding direction of impact.
2. The entry point is reachable by the attacker (check modifiers, `msg.sender` guards, `onlyOwner`, access control).
3. No existing guard already prevents the attack (`require`, `if`-revert, reentrancy lock, allowance check, structural invariant like MINIMUM_LIQUIDITY preventing zero state, etc.).

## Confidence Score

Confidence measures certainty that the finding is real and exploitable — not how severe it is. Every finding that passes the FP gate starts at **100**.

**Deductions (apply all that fit):**

- Privileged caller required (owner, admin, multisig, governance) → **-25**.
- Attack path is partial (general idea is sound but cannot write exact caller → call → state change → outcome) → **-20**.
- Impact is self-contained (only affects the attacker's own funds, no spillover to other users) → **-15**.

Confidence indicator: `[score]` (e.g., `[95]`, `[75]`, `[60]`).

Findings below the confidence threshold (default 75) are still included in the report table but do not get a **Fix** section — description only.

## Leads

Vulnerability trails where the scanning agent found concrete code smells (missing guards, unsafe arithmetic, unvalidated external input) and traced a partial attack path, but ran out of analysis budget to fully confirm exploitation. Leads are NOT false positives — they are high-signal trails that need deeper manual investigation. Not scored or given a Fix — just a title, the code smells found, and a 1-2 sentence description of the vulnerability trail and what remains unverified.

## Do Not Report

- Anything a linter, compiler, or seasoned developer would dismiss — INFO-level notes, gas micro-optimizations, naming, NatSpec, redundant comments.
- Owner/admin can set fees, parameters, or pause — these are by-design privileges, not vulnerabilities.
- Missing event emissions or insufficient logging.
- Centralization observations without a concrete exploit path (e.g., "owner could rug" with no specific mechanism beyond trust assumptions).
- Theoretical issues requiring implausible preconditions (e.g., compromised compiler, corrupt block producer, >50% token supply held by attacker). Note: common ERC20 behaviors (fee-on-transfer, rebasing, blacklisting, pausing) are NOT implausible — if the code accepts arbitrary tokens, these are valid attack surfaces.
