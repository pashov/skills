# Entry-Point Selection Policy

Use this policy when creating the initial `entry-point-selection.json`.

## Goal

Select the smallest handler surface that still exercises the protocol's real state machine.

## Prefer By Default

- core user flows such as `deposit`, `withdraw`, `mint`, `redeem`, `borrow`, `repay`, `stake`, `unstake`, `swap`, `claim`
- recurring permissioned flows such as `harvest`, `liquidate`, `rollover`, `notifyRewardAmount`, `rebalance`, `settle`
- edge-case actions that plausibly break accounting, mode transitions, or fund safety

## Exclude By Default

- `view` and `pure` functions
- one-time migration and bootstrap functions
- internal plumbing exposed as `external` only for contract-to-contract calls
- routine parameter setters that mostly tune config without creating meaningful state-machine pressure

## Include Carefully

Keep a permissioned or config-like action when one of these is true:

- it changes fund routing, fee accounting, caps, oracle state, or collateral rules
- it toggles pause, shutdown, or mode flags
- sequencing it against user flows is plausibly dangerous
- it is part of normal operations for keepers, liquidators, or reward distributors

## Decision Heuristics

For each candidate function, ask:

1. Would a real user, admin, keeper, operator, or liquidator call this directly?
2. Does this function create or unlock important state transitions?
3. Would omitting it make the fuzz campaign miss an important lifecycle edge?
4. Is it mostly internal wiring that should instead be exercised indirectly through another entry point?

If confidence is low, prefer excluding protocol-internal plumbing and keeping the higher-signal external flows.

## Tier Classification

After selection, classify each included function as **primary** or **secondary**:

- **Primary**: core user flows that the fuzzer should call frequently (deposit, withdraw, mint, redeem, borrow, repay, swap, stake, unstake, claim, liquidate, etc.)
- **Secondary**: less common functions that are still useful but should be called less often (admin setters, configuration changes, pause/unpause, role grants, parameter tuning, etc.)

Secondary functions are grouped into a dispatcher handler in Step 7, reducing their call frequency without excluding them entirely.
