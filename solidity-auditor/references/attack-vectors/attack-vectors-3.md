# Attack Vectors Reference (3/4)

173 total attack vectors

---

**85. Assembly Arithmetic Silent Overflow and Division-by-Zero**

- **D:** Arithmetic inside `assembly {}` (Yul) does not revert on overflow/underflow (wraps like `unchecked`) and division by zero returns 0 instead of reverting. Developers accustomed to Solidity 0.8 checked math may not expect this.
- **FP:** Manual overflow checks in assembly (`if gt(result, x) { revert(...) }`). Denominator checked before `div`. Assembly block is read-only (`mload`/`sload` only, no arithmetic).

**86. Flash Loan-Assisted Price Manipulation**

- **D:** Function reads price from on-chain source (AMM reserves, vault `totalAssets()`) manipulable atomically via flash loan + swap in same tx.
- **FP:** TWAP with >= 30min window. Multi-block cooldown between price reads. Separate-block enforcement.

**87. Non-Standard Approve Behavior (Zero-First / Max-Approval Revert)**

- **D:** (a) USDT-style: `approve()` reverts when changing from non-zero to non-zero allowance, requiring `approve(0)` first. (b) Some tokens (UNI, COMP) revert on `approve(type(uint256).max)`. Protocol calls `token.approve(spender, amount)` directly without these accommodations.
- **FP:** OZ `SafeERC20.forceApprove()` or `safeIncreaseAllowance()` used. Allowance always set from zero (fresh per-tx approval). Token whitelist excludes non-standard tokens.

**88. Missing Chain ID Validation in Deployment Configuration**

- **D:** Deploy script reads `$RPC_URL` from `.env` without `eth_chainId` assertion. Foundry script without `--chain-id` flag or `block.chainid` check. No dry-run before broadcast.
- **FP:** `require(block.chainid == expectedChainId)` at script start. CI validates chain ID before deployment.

**89. Array `delete` Leaves Zero-Value Gap Instead of Removing Element**

- **D:** `delete array[index]` resets element to zero but does not shrink the array or shift subsequent elements. Iteration logic treats the zeroed slot as a valid entry — phantom zero-address recipients, skipped distributions, or inflated `length`.
- **FP:** Swap-and-pop pattern used (`array[index] = array[length - 1]; array.pop()`). Iteration skips zero entries explicitly. EnumerableSet or similar library used.

**90. Governance Flash-Loan Upgrade Hijack**

- **D:** Proxy upgrades via governance using current-block vote weight (`balanceOf` or `getPastVotes(block.number)`). No voting delay or timelock. Flash-borrow, vote, execute upgrade in one tx.
- **FP:** `getPastVotes(block.number - 1)`. Timelock 24-72h. High quorum thresholds. Staking lockup required.

**91. Write to Arbitrary Storage Location**

- **D:** (1) `sstore(slot, value)` where `slot` derived from user input without bounds. (2) Solidity <0.6: direct `arr.length` assignment + indexed write at crafted large index wraps slot arithmetic.
- **FP:** Assembly is read-only (`sload` only). Slot is compile-time constant or non-user-controlled. Solidity >= 0.6 used.

**92. Insufficient Return Data Length Validation**

- **D:** Assembly `staticcall`/`call` writes return data into a fixed-size buffer (e.g., `staticcall(gas(), token, ptr, 4, ptr, 32)`) then reads `mload(ptr)` without checking `returndatasize() >= 32`. If the target is an EOA (no code, zero return data) or a non-compliant contract returning fewer bytes, `mload` reads stale memory at `ptr`, which may decode as a truthy value — silently treating a failed/absent call as success.
- **FP:** `if lt(returndatasize(), 32) { revert(0,0) }` checked before reading return data. `extcodesize(target)` verified > 0 before call. Safe ERC20 pattern that handles both zero-length and 32-byte returns. Ref: Consensys Diligence — 0x Exchange bug (real exploit from missing return data length check).

**93. Chainlink Feed Deprecation / Wrong Decimal Assumption**

- **D:** (a) Chainlink aggregator address hardcoded/immutable with no update path — deprecated feed returns stale/zero price. (b) Assumes `feed.decimals() == 8` without runtime check — some feeds return 18 decimals, causing 10^10 scaling error.
- **FP:** Feed address updatable via governance. `feed.decimals()` called and used for normalization. Secondary oracle deviation check.

**94. Upgrade Race Condition / Front-Running**

- **D:** `upgradeTo(V2)` and post-upgrade config calls are separate txs in public mempool. Window for front-running (exploit old impl) or sandwiching between upgrade and config.
- **FP:** `upgradeToAndCall()` bundles upgrade + init. Private mempool (Flashbots Protect). V2 safe with V1 state from block 0. Timelock makes execution predictable.

---

---

**95. Missing or Expired Deadline on Swaps**

- **D:** `deadline = block.timestamp` (always valid), `deadline = type(uint256).max`, or no deadline. Tx holdable in mempool indefinitely.
- **FP:** Deadline is calldata parameter validated as `require(deadline >= block.timestamp)`, not derived from `block.timestamp` internally.

**96. Deployment Transaction Front-Running (Ownership Hijack)**

- **D:** Deployment tx sent to public mempool without private relay. Attacker extracts bytecode and deploys first (or front-runs initialization). Pattern: `eth_sendRawTransaction` via public RPC, constructor sets `owner = msg.sender`.
- **FP:** Private relay used (Flashbots Protect, MEV Blocker). Owner passed as constructor arg, not `msg.sender`. Chain without public mempool. CREATE2 salt tied to deployer.

**97. Duplicate Items in User-Supplied Array**

- **D:** Function accepts array parameter (e.g., `claimRewards(uint256[] calldata tokenIds)`) without checking for duplicates. User passes same ID multiple times, claiming rewards/voting/withdrawing repeatedly in one call.
- **FP:** Duplicate check via mapping (`require(!seen[id]); seen[id] = true`). Sorted-unique input enforced (`require(ids[i] > ids[i-1])`). State zeroed on first claim (second iteration reverts naturally).

**98. Transient Storage Low-Gas Reentrancy (EIP-1153)**

- **D:** Contract uses `transfer()`/`send()` (2300-gas) as reentrancy guard + uses `TSTORE`/`TLOAD`. Post-Cancun, `TSTORE` succeeds under 2300 gas unlike `SSTORE`. Second pattern: transient reentrancy lock not cleared at call end — persists for entire tx, causing DoS via multicall/flash loan callback.
- **FP:** `nonReentrant` backed by regular storage slot (or transient mutex properly cleared). CEI followed unconditionally.

**99. Calldataload / Calldatacopy Out-of-Bounds Read**

- **D:** `calldataload(offset)` where `offset` is user-controlled or exceeds actual calldata length. Reading past `calldatasize()` returns zero-padded bytes silently (no revert), producing phantom zero values that pass downstream logic as valid inputs. Pattern: `calldataload(add(4, mul(index, 32)))` without `require(index < paramCount)`.
- **FP:** `calldatasize()` validated before assembly block (e.g., Solidity ABI decoder already checked). Static offsets into known fixed-length function signatures. Explicit `if lt(calldatasize(), minExpected) { revert(0,0) }` guard.

**100. Banned Opcode in Validation Phase (Simulation-Execution Divergence)**

- **D:** `validateUserOp`/`validatePaymasterUserOp` references `block.timestamp`, `block.number`, `block.coinbase`, `block.prevrandao`, `block.basefee`. Per ERC-7562, banned in validation — values differ between simulation and execution.
- **FP:** Banned opcodes only in execution phase (`execute`/`executeBatch`). Entity is staked under ERC-7562 reputation system.

**101. Deployer Privilege Retention Post-Deployment**

- **D:** Deployer EOA retains owner/admin/minter/pauser/upgrader after deployment script completes. Pattern: `Ownable` sets `owner = msg.sender` with no `transferOwnership()`. `AccessControl` grants `DEFAULT_ADMIN_ROLE` to deployer with no `renounceRole()`.
- **FP:** Script includes `transferOwnership(multisig)`. Admin role granted to timelock/governance, deployer renounces. `Ownable2Step` with pending owner set to multisig.

**102. Non-Atomic Multi-Contract Deployment (Partial System Bootstrap)**

- **D:** Deployment script deploys interdependent contracts across separate transactions. Midway failure leaves half-deployed state with missing references or unwired contracts. Pattern: multiple `vm.broadcast()` blocks or sequential `await deploy()` with no idempotency checks.
- **FP:** Single `vm.startBroadcast()`/`vm.stopBroadcast()` block. Factory deploys+wires all in one tx. Script is idempotent. Hardhat-deploy with resumable migrations.

**103. CREATE / CREATE2 Deployment Failure Silently Returns Zero**

- **D:** Assembly `create(v, offset, size)` or `create2(v, offset, size, salt)` returns `address(0)` on failure (insufficient balance, collision, init code revert) but the code does not check for zero. The zero address is stored or used, and subsequent calls to `address(0)` silently succeed as no-ops (no code) or interact with precompiles.
- **FP:** Immediate check: `if iszero(addr) { revert(0, 0) }` after create/create2. Address validated downstream before any state-dependent operation.

**104. ERC721 / ERC1155 Type Confusion in Dual-Standard Marketplace**

- **D:** Shared `buy`/`fill` function uses type flag for ERC721/ERC1155. `quantity` accepted for ERC721 without requiring == 1. `price * quantity` with `quantity = 0` yields zero payment. Ref: TreasureDAO (2022).
- **FP:** ERC721 branch `require(quantity == 1)`. Separate code paths for ERC721/ERC1155.

---

---

**105. Cross-Contract Reentrancy**

- **D:** Two contracts share logical state (balances in A, collateral check in B). A makes external call before syncing state B reads. A's `ReentrancyGuard` doesn't protect B.
- **FP:** State B reads is synchronized before A's external call. No re-entry path from A's callee into B.

**106. Non-Atomic Proxy Initialization (Front-Running `initialize()`)**

- **D:** Proxy deployed in one tx, `initialize()` called in separate tx. Uninitialized proxy front-runnable. Pattern: `new TransparentUpgradeableProxy(impl, admin, "")` with empty data, separate `initialize()`. Ref: Wormhole (2022).
- **FP:** Proxy constructor receives init calldata atomically: `new TransparentUpgradeableProxy(impl, admin, abi.encodeCall(...))`. OZ `deployProxy()` used.

**107. EIP-2981 Royalty Signaled But Never Enforced**

- **D:** `royaltyInfo()` implemented and `supportsInterface(0x2a55205a)` returns true, but transfer/settlement logic never calls `royaltyInfo()` or routes payment. EIP-2981 is advisory only.
- **FP:** Settlement contract reads `royaltyInfo()` and transfers royalty on-chain. Royalties intentionally zero and documented.

**108. Paymaster Gas Penalty Undercalculation**

- **D:** Paymaster prefund formula omits 10% EntryPoint penalty on unused execution gas (`postOpUnusedGasPenalty`). Large `executionGasLimit` with low usage drains paymaster deposit.
- **FP:** Prefund explicitly adds unused-gas penalty. Conservative overestimation covers worst case.

**109. ERC721 Approval Not Cleared in Custom Transfer Override**

- **D:** Custom `transferFrom` override skips `super._transfer()` or `super.transferFrom()`, missing the `delete _tokenApprovals[tokenId]` step. Previous approval persists under new owner.
- **FP:** Override calls `super.transferFrom` or `super._transfer` internally. Or explicitly deletes approval / calls `_approve(address(0), tokenId, owner)`.

**110. DoS via Push Payment to Rejecting Contract**

- **D:** ETH distribution in a single loop via `recipient.call{value:}("")`. Any reverting recipient blocks entire loop.
- **FP:** Pull-over-push pattern. Loop uses `try/catch` and continues on failure.

**111. Weak On-Chain Randomness**

- **D:** Randomness from `block.prevrandao`, `blockhash(block.number - 1)`, `block.timestamp`, `block.coinbase`, or combinations. Validator-influenceable or visible before inclusion.
- **FP:** Chainlink VRF v2+. Commit-reveal with future-block reveal and slashing for non-reveal.

**112. Delegatecall to Untrusted Callee**

- **D:** `address(target).delegatecall(data)` where `target` is user-provided or unconstrained.
- **FP:** `target` is hardcoded immutable verified library address.

**113. UUPS `_authorizeUpgrade` Missing Access Control**

- **D:** `function _authorizeUpgrade(address) internal override {}` with empty body and no access modifier. Anyone can call `upgradeTo()`. Ref: CVE-2021-41264.
- **FP:** `_authorizeUpgrade()` has `onlyOwner` or equivalent. Multisig/governance controls owner role.

**114. Insufficient Block Confirmations / Reorg Double-Spend**

- **D:** DVN relays cross-chain message before source chain reaches finality. Attacker deposits on source chain, gets minted on destination, then causes a reorg on source chain (or the chain reorgs naturally) to reverse the deposit while keeping minted tokens. Pattern: confirmation count set below chain's known reorg depth (e.g., < 32 blocks on Polygon).
- **FP:** Confirmation count matches or exceeds chain-specific finality guarantees. Chain has fast finality (e.g., Ethereum post-merge ~12 min). DVN waits for finalized blocks.

---

---

**115. Nested Mapping Inside Struct Not Cleared on `delete`**

- **D:** `delete myMapping[key]` on struct containing `mapping` or dynamic array. `delete` zeroes primitives but not nested mappings. Reused key exposes stale values.
- **FP:** Nested mapping manually cleared before `delete`. Key never reused after deletion.

**116. ERC721A Lazy Ownership — ownerOf Uninitialized in Batch Range**

- **D:** ERC721A/`ERC721Consecutive` batch mint: only first token has ownership written. `ownerOf(id)` for mid-batch IDs may return `address(0)` before any transfer. Access control checking `ownerOf == msg.sender` fails on freshly minted tokens.
- **FP:** Explicit transfer initializes packed slot before ownership check. Standard OZ `ERC721` writes `_owners[tokenId]` per mint.

**117. Cross-Chain Message Spoofing (Missing Endpoint/Peer Validation)**

- **D:** Receiver contract accepts cross-chain messages without verifying `msg.sender == endpoint` and `_origin.sender == registeredPeer[srcChainId]`. Attacker calls the receive function directly with fabricated message data, triggering unauthorized mints/unlocks.
- **FP:** `onlyPeer` modifier or equivalent checks both `msg.sender` (endpoint) and `_origin.sender` (peer). Standard `OAppReceiver._acceptNonce` validates origin. Ref: CrossCurve bridge exploit (Jan 2026) — $3M stolen via spoofed `expressExecute`.

**118. Proxy Admin Key Compromise**

- **D:** `ProxyAdmin.owner()` returns EOA, not multisig/governance; no timelock on `upgradeTo`. Ref: PAID Network (2021), Ankr (2022).
- **FP:** Multisig (threshold >= 2) + timelock (24-72h). Admin role separate from operational roles.

**119. Unauthorized Peer Initialization (Fake Peer Attack)**

- **D:** `setPeer()` / `setTrustedRemote()` sets the remote peer address that a cross-chain contract trusts. If the owner is compromised or `setPeer` lacks proper access control, an attacker registers a fraudulent peer contract on the source chain that can mint/unlock tokens on the destination without legitimate deposits. Pattern: `setPeer` callable by non-owner, or owner key compromised.
- **FP:** `setPeer` protected by multisig + timelock. Peer addresses verified against known deployment registry. `allowInitializePath()` properly implemented to reject unknown peers. Ref: GAIN token exploit (Sep 2025) — fake peer minted 5B tokens, $3M stolen.

**120. Rounding in Favor of the User**

- **D:** `shares = assets / pricePerShare` rounds down for deposit but up for redeem. Division without explicit rounding direction. First-depositor donation amplifies the error.
- **FP:** `Math.mulDiv` with explicit `Rounding.Up` where vault-favorable. OZ ERC4626 `_decimalsOffset()`. Dead shares at init.

**121. Arbitrary External Call with User-Supplied Target and Calldata**

- **D:** `target.call{value: v}(data)` where `target` or `data` (or both) are caller-supplied parameters. Attacker crafts calldata to invoke unintended functions on the target (e.g., `transferFrom` on an approved ERC20, or `safeTransferFrom` on held NFTs), stealing assets the contract holds or has approvals for.
- **FP:** Target restricted to hardcoded/whitelisted address. Calldata function selector restricted to known-safe set. No token approvals or asset holdings on the calling contract. `delegatecall` vector covered separately (V58/V105); this covers `call`.

**122. Paymaster ERC-20 Payment Deferred to postOp Without Pre-Validation**

- **D:** `validatePaymasterUserOp` doesn't transfer/lock tokens — payment deferred to `postOp` via `safeTransferFrom`. User can revoke allowance between validation and execution; paymaster loses deposit.
- **FP:** Tokens transferred/locked during `validatePaymasterUserOp`. `postOp` only refunds excess.

**123. Minimal Proxy (EIP-1167) Implementation Destruction**

- **D:** EIP-1167 clones `delegatecall` a fixed implementation. If implementation is destroyed, all clones become no-ops with locked funds. Pattern: `Clones.clone(impl)` where impl has no `selfdestruct` protection or is uninitialized.
- **FP:** No `selfdestruct` in implementation. `_disableInitializers()` in constructor. Post-Dencun: code not destroyed. Beacon proxies used for upgradeability.

---

**124. Spot Price Oracle from AMM**

- **D:** Price from AMM reserves: `reserve0 / reserve1`, `getAmountsOut()`, `getReserves()`. Flash-loan exploitable atomically.
- **FP:** TWAP >= 30 min window. Chainlink/Pyth as primary source.

---

**125. Missing Slippage Protection (Sandwich Attack)**

- **D:** Swap/deposit/withdrawal with `minAmountOut = 0`, or `minAmountOut` computed on-chain from current pool state.
- **FP:** `minAmountOut` set off-chain by user and validated on-chain.

**126. NFT Staking Records msg.sender Instead of ownerOf**

- **D:** `depositor[tokenId] = msg.sender` without checking `nft.ownerOf(tokenId)`. Approved operator (not owner) calls stake — transfer succeeds via approval, operator credited as depositor.
- **FP:** Reads `nft.ownerOf(tokenId)` before transfer and records actual owner. Or `require(nft.ownerOf(tokenId) == msg.sender)`.
