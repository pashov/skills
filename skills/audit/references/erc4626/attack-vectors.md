# ERC4626 Attack Vectors

8 attack vectors specific to ERC4626 tokens. For each: detection pattern (what to look for in code) and false-positive signals (what makes it NOT a vulnerability even if the pattern matches).

---

**1. ERC4626 Inflation Attack (First Depositor)**

- **Detect:** Vault shares math: `shares = assets * totalSupply / totalAssets`. When `totalSupply == 0`, attacker deposits 1 wei, donates large amount to vault, victim's deposit rounds to 0 shares. No virtual offset or dead shares protection.
- **FP:** OpenZeppelin ERC4626 with `_decimalsOffset()` override. Dead shares minted to `address(0)` at init.

**2. Rounding in Favor of the Attacker**

- **Detect:** `shares = assets / pricePerShare` rounds down for the user but up for shares redeemed. First-depositor vault manipulation: when `totalSupply == 0`, attacker donates to inflate `totalAssets`, subsequent deposits round to 0 shares. Division without explicit rounding direction.
- **FP:** `Math.mulDiv(a, b, c, Rounding.Up)` used with explicit rounding direction appropriate for the operation. Virtual offset (OpenZeppelin ERC4626 `_decimalsOffset()`) prevents first-depositor attack. Dead shares minted to `address(0)` at init.

**3. ERC4626 Preview Rounding Direction Violation**

- **Detect:** `previewDeposit(a)` returns more shares than `deposit(a)` actually mints; `previewRedeem(s)` returns more assets than `redeem(s)` actually transfers; `previewMint(s)` returns fewer assets than `mint(s)` actually charges; `previewWithdraw(a)` returns fewer shares than `withdraw(a)` actually burns. EIP-4626 mandates that preview functions round in the vault's favor — they must never overstate what the user receives or understate what the user pays. Custom `_convertToShares`/`_convertToAssets` implementations that apply the wrong `Math.mulDiv` rounding direction (e.g., `Rounding.Ceil` when `Rounding.Floor` is required) violate this. Integrators that use preview return values for slippage checks will pass with an incorrect expectation and receive less than they planned for.
- **FP:** OpenZeppelin ERC4626 base used without overriding `_convertToShares`/`_convertToAssets`. Custom implementation explicitly passes `Math.Rounding.Floor` for share issuance (deposit/previewDeposit) and `Math.Rounding.Ceil` for share burning (withdraw/previewWithdraw).

**4. ERC4626 Round-Trip Profit Extraction**

- **Detect:** A full operation cycle yields strictly more than the starting amount: `redeem(deposit(a)) > a`, `deposit(redeem(s)) > s`, `mint(withdraw(a)) > a`, or `withdraw(mint(s)) > s`. Possible when rounding errors in `_convertToShares` and `_convertToAssets` both truncate in the user's favor, so no value is lost in either direction and a net gain emerges with large inputs or a manipulated share price. Combined with the first-depositor inflation attack (Vector 1), the share price can be engineered so that round-trip profit scales with the amount — enabling systematic value extraction.
- **FP:** Rounding directions satisfy EIP-4626: shares issued on deposit/mint round down (vault-favorable), shares burned on withdraw/redeem round up (vault-favorable). OpenZeppelin ERC4626 with `_decimalsOffset()` used.

**5. ERC4626 Caller-Dependent Conversion Functions**

- **Detect:** `convertToShares()` or `convertToAssets()` branches on `msg.sender`-specific state — per-user fee tiers, whitelist status, individual balances, or allowances — causing identical inputs to return different outputs for different callers. EIP-4626 requires these functions to be caller-independent. Downstream aggregators, routers, and on-chain interfaces call these functions to size positions before routing; a caller-dependent result silently produces wrong sizing for some users.
- **FP:** Implementation reads only global vault state (`totalSupply()`, `totalAssets()`, protocol-wide fee constants) with no `msg.sender`-dependent branching.

**6. ERC4626 Missing Allowance Check in withdraw() / redeem()**

- **Detect:** `withdraw(assets, receiver, owner)` or `redeem(shares, receiver, owner)` where `msg.sender != owner` but no allowance validation or decrement is performed before burning shares. EIP-4626 requires that if `caller != owner`, the caller must hold sufficient share approval; the allowance must be consumed atomically. Missing this check lets any address burn shares from an arbitrary owner and redirect the assets to any receiver — equivalent to an unchecked `transferFrom`.
- **FP:** `_spendAllowance(owner, caller, shares)` called unconditionally before the share burn when `caller != owner`. OpenZeppelin ERC4626 used without custom overrides of `withdraw`/`redeem`.

**7. ERC4626 Deposit/Withdraw Share-Count Asymmetry**

- **Detect:** For the same asset amount `a`, `withdraw(a)` burns fewer shares than `deposit(a)` minted — meaning a user can deposit, immediately withdraw the same assets, and retain surplus shares for free. Equivalently, `deposit(withdraw(a).assets)` returns more shares than `withdraw(a)` burned, manufacturing shares from nothing. Root cause: `_convertToShares` applies `Rounding.Floor` (rounds down) for both the deposit path (shares issued) and the withdraw path (shares required to burn), when EIP-4626 requires deposit to round down and withdraw to round up. The gap between the two floors is the free share. Pattern: a single `_convertToShares(assets, Rounding.Floor)` helper called on both code paths without distinct rounding arguments. (Covers `prop_RT_deposit_withdraw` and `prop_RT_withdraw_deposit` from the a16z ERC4626 property test suite.)
- **FP:** `deposit`/`previewDeposit` call `_convertToShares(assets, Math.Rounding.Floor)` and `withdraw`/`previewWithdraw` call `_convertToShares(assets, Math.Rounding.Ceil)` — opposite directions, vault-favorable in each case. OpenZeppelin ERC4626 used without custom conversion overrides.

**8. ERC4626 Mint/Redeem Asset-Cost Asymmetry**

- **Detect:** For the same share count `s`, `redeem(s)` returns more assets than `mint(s)` costs — so cycling redeem → remint yields a net profit on every loop. Equivalently, `mint(redeem(s).shares)` costs fewer assets than `redeem(s)` returned. Root cause: `_convertToAssets` rounds up in `redeem` (user receives more) and rounds down in `mint` (user pays less), the opposite of what EIP-4626 requires. The spec mandates that `redeem` rounds down (vault keeps the rounding error) and `mint` rounds up (user pays the rounding error). Pattern: `previewRedeem` and `redeem` call `_convertToAssets(shares, Rounding.Ceil)` while `previewMint` and `mint` call `_convertToAssets(shares, Rounding.Floor)`. The delta between the two is extractable per cycle. (Covers `prop_RT_mint_redeem` and `prop_RT_redeem_mint` from the a16z ERC4626 property test suite.)
- **FP:** `redeem`/`previewRedeem` call `_convertToAssets(shares, Math.Rounding.Floor)` and `mint`/`previewMint` call `_convertToAssets(shares, Math.Rounding.Ceil)`. OpenZeppelin ERC4626 used without custom conversion overrides.
