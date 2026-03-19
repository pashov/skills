---
repo_url: https://github.com/sherlock-audit/2025-05-dodo-cross-chain-dex
repo_ref: main
contracts_dir: omni-chain-contracts/contracts
---

# Ground Truth — DODO Cross-Chain DEX

Source: https://audits.sherlock.xyz/contests/991?filter=results

## Findings

FINDING | id: H-1 | severity: High | contract: GatewayCrossChain | function: onCall | bug_class: missing-validation
description: Attacker crafts cross-chain transactions with mismatched swap parameters — swapping to one token but withdrawing accumulated balances of a different token. No validation ensures the swap output token matches the target withdrawal token, enabling drainage of accumulated contract balances.

FINDING | id: H-2 | severity: High | contract: GatewayTransferNative | function: withdrawToNativeChain | bug_class: missing-msg-value-validation
description: When zrc20 equals the ETH placeholder address, the function bypasses transferFrom validation but does not verify msg.value matches the claimed amount. Attackers claim arbitrary native token amounts without sending them, stealing accumulated ZRC20 tokens from the contract.

FINDING | id: H-3 | severity: High | contract: GatewayTransferNative | function: _doMixSwap | bug_class: missing-swap-enforcement
description: When swapData is empty, the function returns the original amount without validating that the input token matches the target token. Attackers bypass swaps and drain higher-value assets held by the contract by specifying different input and target tokens.

FINDING | id: H-4 | severity: High | contract: GatewayTransferNative | function: withdrawToNativeChain | bug_class: missing-input-token-validation
description: Users deposit low-value tokens while crafting messages specifying different valuable tokens for swap. The contract approves its own balance of the attacker-specified token, allowing drainage of high-value holdings without legitimate deposits.

FINDING | id: H-5 | severity: High | contract: GatewayCrossChain | function: claimRefund | bug_class: access-control-bypass
description: Authorization check fails for non-EVM addresses (Bitcoin, etc.). When walletAddress length != 20 bytes, receiver defaults to msg.sender, making the require statement always pass for any caller. This enables theft of all non-EVM refunds.

FINDING | id: M-1 | severity: Medium | contract: GatewayTransferNative | function: _handleEvmOrSolanaWithdraw | bug_class: over-approval
description: Contract approves outputAmount + gasFee to GatewayZEVM but only withdraws outputAmount. Excess gasFee remains in allowance, exploitable via the public withdraw() function when the contract has refund balances.

FINDING | id: M-2 | severity: Medium | contract: GatewayTransferNative | function: _doMixSwap | bug_class: invalid-address-approval
description: Attempting approve() on ETH placeholder address causes transaction reverts since the placeholder is not a valid contract. All users attempting ETH swaps experience DOS.

FINDING | id: M-3 | severity: Medium | contract: GatewayTransferNative | function: onCall | bug_class: wrong-amount-in-swap
description: Platform fees are deducted from the amount before swap, but the swap still uses the original full amount. Causes guaranteed revert due to insufficient funds. Can also enable theft of accumulated refunds if the contract has stored balances.

FINDING | id: M-4 | severity: Medium | contract: AccountEncoder | function: decompressAccounts | bug_class: incorrect-byte-extraction
description: When parsing boolean account permissions, code reads 32 bytes instead of 1 byte via assembly, mixing permission bits with the next account's public key bytes. All account permissions are corrupted, enabling unauthorized token transfers on Solana.

FINDING | id: M-5 | severity: Medium | contract: GatewayTransferNative | function: withdrawToNativeChain | bug_class: msg-value-mismatch
description: When swapping native ZETA with non-zero fees, full msg.value is passed to mixSwap despite fees already being deducted. Creates mismatch between msg.value and fromTokenAmount, causing swap failure.

FINDING | id: M-6 | severity: Medium | contract: GatewayTransferNative | function: _handleFeeTransfer | bug_class: native-erc20-confusion
description: When bridging native ETH, fee collection attempts ERC20 transfer on placeholder address. Low-level call succeeds without moving funds, allowing users to bypass platform fees entirely.

FINDING | id: M-7 | severity: Medium | contract: GatewayTransferNative | function: onRevert | bug_class: refund-overwrite
description: Function overwrites refundInfo without checking if an entry already exists. Attacker triggers intentional reverts with crafted messages to poison refund records intended for legitimate users, blocking their withdrawals.

FINDING | id: M-8 | severity: Medium | contract: GatewayCrossChain | function: _existsPairPool | bug_class: false-pool-detection
description: Pool existence is determined by checking balanceOf() at the computed pair address rather than verifying deployed contract code or actual reserves. False positives occur when tokens are transferred to non-existent pool addresses, causing downstream swap reverts.

FINDING | id: M-9 | severity: Medium | contract: GatewaySend | function: onRevert | bug_class: native-erc20-confusion
description: Function uses TransferHelper.safeTransfer() (ERC20) to refund native ETH from failed cross-chain transactions. Attempt to call transfer() on placeholder address fails, trapping ETH in the contract permanently.

FINDING | id: M-10 | severity: Medium | contract: GatewayCrossChain | function: _handleBitcoinWithdraw | bug_class: address-truncation
description: Bitcoin addresses are cast to 20 bytes in revertMessage, corrupting original bech32 addresses. Failed withdrawals send refunds to wrong addresses, causing permanent loss of user funds.

FINDING | id: M-11 | severity: Medium | contract: GatewaySend | function: depositAndCall | bug_class: non-standard-erc20-return
description: Uses require(IERC20.transferFrom()) expecting boolean return, but void-return tokens like USDT fail even when transfers succeed. Makes the contract incompatible with major non-standard tokens despite TransferHelper imports being available.
