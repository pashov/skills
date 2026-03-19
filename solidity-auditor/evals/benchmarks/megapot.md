---
repo_url: https://github.com/code-423n4/2025-11-megapot
repo_ref: main
---

# Ground Truth — Megapot

Source: https://code4rena.com/reports/2025-11-megapot

## Findings

FINDING | id: H-1 | severity: High | contract: JackpotBridgeManager | function: _bridgeFunds | bug_class: unsafe-external-call
description: Attacker can steal JackpotTicketNFTs from JackpotBridgeManager by exploiting an unsafe external call pattern during the bridge funds process, enabling NFT theft from the contract.

FINDING | id: H-2 | severity: High | contract: TicketComboTracker | function: _countSubsetMatches | bug_class: gas-limit-dos
description: Unoptimized subset match counting implementation will exceed the transaction gas limit on Base chain, preventing drawing settlement from completing when ticket counts are non-trivial.

FINDING | id: H-3 | severity: High | contract: JackpotLPManager | function: processDrawingSettlement | bug_class: missing-cap-enforcement
description: LP pool cap may be exceeded during drawing settlement because the value calculation does not enforce the cap, allowing LP value to grow beyond the intended maximum.

FINDING | id: M-1 | severity: Medium | contract: Jackpot | function: multiple_setters | bug_class: state-modification-mid-draw
description: Global governance variables (ticket price, number count, etc.) can be modified during an active draw, altering the end result of the current drawing's settlement and payout calculations.

FINDING | id: M-2 | severity: Medium | contract: JackpotBridgeManager | function: buyTickets | bug_class: stale-price-reference
description: Bridge manager uses the current ticket price instead of the drawing-specific price when buying tickets, causing user overpayment after price updates occur mid-drawing.

FINDING | id: M-3 | severity: Medium | contract: Jackpot | function: parameter_updates | bug_class: governance-dos
description: Deliberately increasing liquidity can DoS updates to the protocol's governance parameters by making the change thresholds impossible to meet.

FINDING | id: M-4 | severity: Medium | contract: JackpotLPManager | function: emergency_mode | bug_class: stuck-funds
description: LP earnings generated during emergency mode become permanently stuck on the contract due to incomplete state cleanup when transitioning out of emergency mode.

FINDING | id: M-5 | severity: Medium | contract: Jackpot | function: entropy_callback | bug_class: insufficient-randomness
description: Randomness can be exploited in some cases due to insufficient validation of the entropy source, enabling partial prediction or manipulation of jackpot results.

FINDING | id: M-6 | severity: Medium | contract: ScaledEntropyProvider | function: provider_swap | bug_class: entropy-manipulation
description: Changes to the Pyth entropy provider used by ScaledEntropyProvider allow an attacker to fix the jackpot result by manipulating which provider fulfills the entropy request.

FINDING | id: M-7 | severity: Medium | contract: Jackpot | function: setEntropy | bug_class: provider-change-mid-draw
description: Changing the entropy provider during an active drawing causes permanent protocol lock and callback failure because the new provider cannot fulfill the pending request from the old provider.

FINDING | id: M-8 | severity: Medium | contract: Jackpot | function: setPayoutCalculator | bug_class: calculator-change-mid-draw
description: Changing the payout calculator during an active drawing causes loss of unclaimed winnings because the new calculator does not have the previous drawing's payout data.
