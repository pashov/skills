---
repo_url: https://github.com/code-423n4/2024-03-pooltogether
repo_ref: main
contracts_dir: pt-v5-vault/src
---

# Ground Truth — PoolTogether V5 PrizeVault

Source: https://code4rena.com/reports/2024-03-pooltogether

## Findings

FINDING | id: H-1 | severity: High | contract: PrizeVault | function: claimYieldFeeShares | bug_class: incorrect-balance-update
description: claimYieldFeeShares deducts the entire cached yieldFeeBalance instead of only the claimed amount, causing any unclaimed portion of accrued yield fees to be permanently lost.

FINDING | id: M-1 | severity: Medium | contract: Claimable | function: claimPrize | bug_class: hook-reentrancy
description: A malicious winner can use the beforeClaimPrize hook to reenter the Claimer contract and claim their own prize without paying claimer fees, forcing the original caller to waste gas with no fee compensation.

FINDING | id: M-2 | severity: Medium | contract: PrizeVault | function: _maxYieldVaultWithdraw | bug_class: erc4626-noncompliance
description: _maxYieldVaultWithdraw uses yieldVault.convertToAssets which per EIP-4626 may overstate available assets, causing maxWithdraw and maxRedeem to return values that exceed actually withdrawable amounts.

FINDING | id: M-3 | severity: Medium | contract: PrizeVault | function: maxDeposit | bug_class: erc4626-noncompliance
description: maxDeposit queries yieldVault.maxDeposit but actual deposits use yieldVault.mint which may have stricter limits, violating ERC-4626 guarantees and causing deposit reverts at the reported maximum.

FINDING | id: M-4 | severity: Medium | contract: PrizeVault | function: withdraw | bug_class: missing-slippage-protection
description: withdraw and redeem lack slippage parameters, exposing users to unfavorable exchange rates if the underlying yield vault experiences losses while their transaction is pending in the mempool.

FINDING | id: M-5 | severity: Medium | contract: PrizeVault | function: liquidatableBalanceOf | bug_class: stuck-funds
description: liquidatableBalanceOf ignores yield fee shares when checking the TWAB supply cap, so accumulated yield fees can become permanently unclaimable once regular deposits fill the remaining supply.

FINDING | id: M-6 | severity: Medium | contract: PrizeVault | function: _withdraw | bug_class: unchecked-return-value
description: _withdraw uses transfer without checking the return value; non-reverting ERC20 tokens like BAT can silently fail, burning the user's vault shares while leaving their assets locked in the vault.

FINDING | id: M-7 | severity: Medium | contract: PrizeVault | function: maxDeposit | bug_class: incorrect-accounting
description: maxDeposit fails to account for yieldFeeBalance when computing remaining capacity under the TWAB supply limit, allowing deposits that consume the entire cap and make accumulated fees unclaimable.

FINDING | id: M-8 | severity: Medium | contract: PrizeVault | function: depositWithPermit | bug_class: token-incompatibility
description: depositWithPermit uses the standard ERC-2612 permit signature which is incompatible with DAI's non-standard permit implementation that requires a nonce parameter, preventing DAI deposits via permit.
