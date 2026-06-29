# Handler Patterns

Use this guide during Step 7.

## Shape

Each handler file should have two sections:

- `Unclamped`: raw protocol-action functions that perform the target call with unrestricted parameters
- `Clamped`: handlers that restrict arbitrary fuzz input into sensible, high-signal calls

Both sections may be called by the fuzzer. The unclamped section is not just an internal helper layer: unclamped handlers are also direct fuzz entry points, specifically so the campaign can still hit edge cases that the clamped layer intentionally filters out.

The clamped layer should stay thin and usually forward into the corresponding unclamped function. The unclamped layer should usually just perform the target call with the appropriate acting modifier.

## Unclamped

The `Unclamped` section is the raw-call layer.

Use it to:

- perform the real target function call with unrestricted parameters
- expose edge-case behavior that clamped variants intentionally avoid
- apply the correct acting modifier or caller role
- stay as close as possible to a raw call wrapper

These functions are meant to be called both:

- directly by the fuzzer, with unrestricted parameters
- indirectly by the clamped handlers, after those handlers have prepared sensible inputs

Unclamped handlers should stay close to the actual protocol surface. They should usually be thin raw calls plus the necessary role modifier and call to internal specific properties, if applicable. "Unclamped" describes their role in the handler structure, not their Solidity visibility.

### Caller Context

Use the acting context that matches the real role here:

- `asActor` for users
- `asAdmin` for owner or admin operations
- role-specific modifiers for keepers, operators, reward distributors, or liquidators

If the scaffold lacks a needed role modifier, add it.

This is required even for raw unclamped handlers. Unrestricted parameters do not mean unrestricted caller identity.

## Clamped

The `Clamped` section is the restricted-input layer of the handler.

Use it to:

- expose the small set of high-signal protocol actions that the fuzzer should call
- normalize arbitrary fuzz inputs into values that can reach meaningful code paths
- prepare derived values before dispatching into the unclamped implementation
- prepare preconditions that the target action expects, then forward into the corresponding unclamped function whenever practical

### Clamped Design

Do not mirror the ABI mechanically if a higher-signal handler shape is better.

Good transformations:

- merge preparatory steps and the main user action into one handler if the protocol expects them together
- split one overloaded or ambiguous flow into clearer variants if that improves coverage
- derive parameters from current state when raw fuzzed values mostly cause trivial reverts

### Clamped Input Handling

Prefer semantic bounds over arbitrary caps. Clamp toward values that are realistic for the protocol and likely to reach meaningful state transitions.

Use the helper functions from `utils/Clamp.sol` for this layer. Those helpers are part of the scaffold specifically so clamped handlers can bound fuzz inputs consistently with functions such as `clampBetween`, `clampLte`, `clampLt`, `clampGte`, and `clampGt`.

Examples:

- map arbitrary addresses to known actors with `toActor(...)` and `toActorNotCurrent(...)`
- if a function expects a valid identifier such as an order id, position id, market id, or pool id, pick from known valid values instead of passing arbitrary garbage
- if a function will pull ERC20s from the caller, bound the amount by the caller's token balance and set the needed approval before calling the unclamped function
- bound spend amounts by balances or allowances
- bound share burns by owned shares
- bound deadlines so the call can reach meaningful code paths
- use source constants and require guards when they expose real bounds

Clamped handlers should usually avoid doing the raw protocol call inline. Prefer to finish argument preparation and then call the unclamped version.

If the correct bound is unclear, keep the clamp loose and leave a targeted `// TODO: tighten bound`.

### Donation Handlers

- If the protocol manages native tokens, include a special `<Contract>_donateETH` handler that accepts an arbitrary amount and sends it to the protocol using `Actor.forceSendETH(...)`.
- If the protocol manages ERC20 tokens, include a special `<Contract>_donateERC20` handler that accepts an arbitrary amount and (optionally) token address and sends it to the protocol.

## Boundary-Value Stress Handlers

For every clamped handler, generate **stress variants** that target the extremes of the input domain. Clamped handlers focus on "sensible" ranges to maximize meaningful state transitions, but bugs cluster at the boundaries those clamps filter out. Stress handlers exist to hit those boundaries.

The approach is always the same: read the function's code path, identify where the math can degenerate, and write a handler that drives input to that boundary. There are four directions to check.

### 1. Near-Zero / Sub-Unit Values

When a code path involves division or decimal conversion, values near or below the divisor truncate to zero. This creates free-value bugs (user pays nothing, receives tokens) or division-by-zero reverts.

**How to detect**: grep the target contracts for division (`/`), `mulDiv`, decimal scaling (`10**`, `1eN`), or conversion functions. Note the divisor. Any input smaller than that divisor will truncate.

```solidity
// Generic pattern: if the function divides by SCALE_FACTOR, test below it
function contract_action_smallAmount(uint256 amount) public {
    // Clamp to values near the truncation boundary
    amount = clampBetween(amount, 1, SCALE_FACTOR);
    contract_action(amount);
}
```

### 2. Full-Amount / Max-State Operations

Protocols often work fine for partial operations but break when the entire balance, debt, or supply flows through a single path. Generate handlers that use the maximum available amount from current state:

```solidity
function contract_fullWithdraw() public {
    uint256 fullBalance = contract.balanceOf(actor);
    if (fullBalance == 0) return;
    contract_withdraw(fullBalance);
}

function contract_fullAction(uint256 auxParam) public {
    uint256 maxAmount = contract.totalAvailable();
    if (maxAmount == 0) return;
    contract_action(maxAmount, auxParam);
}
```

### 3. Type-Boundary Values

Before writing handlers, grep the target contracts for storage variables that use types narrower than uint256 — `uint8`, `uint80`, `uint96`, `uint128`, `uint160`, or packed struct fields. When a value accumulates via uint256 arithmetic but is stored or cast to a narrower type, the truncation is invisible until the accumulated value exceeds the type's max.

For each narrow-typed accumulator, create a handler that pushes values large enough to approach or exceed the type boundary through the accumulation path. Derive the bound from the type max (e.g., `type(uint80).max` is ~1.2e24), not from hardcoded protocol-specific constants.

### How to Apply

For each clamped handler, ask:
1. Does this path involve division or scaling? → add a **near-zero** variant
2. Can this be called with the full available amount? → add a **full-amount** variant
3. Does this path write to a narrow-typed storage variable? → add a **type-boundary** variant

Not every handler needs all three — only add variants where the code path has the relevant pattern.

### Admin Handlers

For admin/owner functions, always use the correct caller context:

```solidity
function protocol_setFee(uint256 fee) public asAdmin {
    protocol.setFee(fee);
}
```

Admin handlers must use `asAdmin` (or the appropriate role modifier) — not `asActor`. If no `asAdmin` modifier exists in the scaffold, add one that pranks as the contract owner.

## Dispatcher for Secondary-Tier Functions

Secondary-tier functions appear as `internal` stubs (prefixed `_`) in the Unclamped section, and a single public dispatcher at the end of the Clamped section. The dispatcher is a single clamped entry point that uses a `uint8 selector` parameter to pick which secondary function to call:


```solidity
function vault_secondary(uint8 selector, uint256 arg0, address arg1) public {
    selector = uint8(selector % 3);
    if (selector == 0) _vault_setPaused(arg0 > 0);
    else if (selector == 1) _vault_setFee(arg0);
    else _vault_setAdmin(arg1);
}
```

The unclamped secondary functions are all `internal` and not direct fuzz entry points.

This reduces the secondary functions' call frequency naturally — the fuzzer reaches them only when it happens to pick the matching selector value.

Primary-tier functions get their own individual clamped + unclamped handlers as normal.

## Example

```solidity
// SPDX-License-Identifier: MIT
pragma solidity >=0.6.2 <0.9.0;

import "../Base.sol";
import {Properties} from "../Properties.sol";

/// @notice Handles the interaction with a specific contract
abstract contract VaultHandler is Properties {

    // ――――――――――――――――――――――――― Clamped ――――――――――――――――――――――――――

    function vault_deposit_clamped(uint256 amount) public {
        uint256 balance = token.balanceOf(actor);
        if (balance == 0) return;
        amount = clampBetween(amount, 1, balance);

        vault_deposit(amount);
    }

	function vault_donateETH(uint256 amount) public {
		if (actor.balance == 0) return;
		amount = clampBetween(amount, 1, actor.balance);

        Actor(actor).forceSendETH{value: amount}(address(vault));
    }

	function vault_donateERC20(uint256 amount) public {
        uint256 balance = token.balanceOf(actor);
        if (balance == 0) return;
        amount = clampBetween(amount, 1, balance);

		vm.prank(actor);
        token.transfer(address(vault), amount);
    }

    // ―――――――――――――――――――――――― Unclamped ―――――――――――――――――――――――――

    function vault_deposit(uint256 amount) public asActor {
        vault.deposit(amount);
    }
}
```