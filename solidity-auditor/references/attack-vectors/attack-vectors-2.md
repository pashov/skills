---

**56. Cross-Chain Address Ownership Variance**

- **D:** Same address has different owners on different chains (EOA private key not used on all chains, or `CREATE`-deployed contract at same nonce but different deployer). Cross-chain logic that assumes `address(X) on Chain A == address(X) on Chain B` implies same owner enables impersonation. Pattern: `lzRead` checking `ownerOf(tokenId)` cross-chain and granting rights to the same address locally.
- **FP:** `CREATE2`-deployed contracts with same factory + salt are safe. Peer mapping explicitly binds (chainId, address) pairs. Authorization uses cross-chain messaging (not address equality) to prove ownership.

**57. Read-Only Reentrancy**

- **D:** Protocol calls `view` function (`get_virtual_price()`, `totalAssets()`) on external contract from within a callback. External contract has no reentrancy guard on view functions — returns transitional/manipulated value mid-execution.
- **FP:** External view functions are `nonReentrant`. Chainlink oracle used instead. External contract's reentrancy lock checked before calling view.

**58. Bytecode Verification Mismatch**

- **D:** Verified source doesn't match deployed bytecode behavior: different compiler settings, obfuscated constructor args, or `--via-ir` vs legacy pipeline mismatch. No reproducible build (no pinned compiler in config).
- **FP:** Deterministic build with pinned compiler/optimizer in committed config. Verification in deployment script (Foundry `--verify`). Sourcify full match. Constructor args published.

**59. Scratch Space Corruption Across Assembly Blocks**

- **D:** Data written to scratch space (`0x00`–`0x3f`) in one assembly block is expected to persist and be read in a later assembly block, but intervening Solidity code (or compiler-generated code for `keccak256`, `abi.encode`, etc.) overwrites scratch space between the two blocks. Pattern: `mstore(0x00, key); mstore(0x20, slot)` in block A, then `keccak256(0x00, 0x40)` in block B with Solidity statements between them.
- **FP:** All scratch space reads occur within the same contiguous assembly block as the writes. Developer explicitly rewrites scratch space before each use. No intervening Solidity code between blocks.

**60. ERC1155 Custom Burn Without Caller Authorization**

- **D:** Public `burn(address from, uint256 id, uint256 amount)` callable by anyone without verifying `msg.sender == from` or operator approval. Any caller burns another user's tokens.
- **FP:** `require(from == msg.sender || isApprovedForAll(from, msg.sender))` before `_burn`. OZ `ERC1155Burnable` used.

**61. ERC721 Unsafe Transfer to Non-Receiver**

- **D:** `_transfer()`/`_mint()` used instead of `_safeTransfer()`/`_safeMint()`, sending NFTs to contracts without `IERC721Receiver`. Tokens permanently locked.
- **FP:** All paths use `safeTransferFrom`/`_safeMint`. Function is `nonReentrant`.

**62. ERC1155 Fungible / Non-Fungible Token ID Collision**

- **D:** ERC1155 represents both fungible and unique items with no enforcement: missing `require(totalSupply(id) == 0)` before NFT mint, or no cap preventing additional copies of supply-1 IDs.
- **FP:** `require(totalSupply(id) + amount <= maxSupply(id))` with `maxSupply=1` for NFTs. Fungible/NFT ID ranges disjoint and enforced. Role tokens non-transferable.

**63. ERC4626 Deposit/Withdraw Share-Count Asymmetry**

- **D:** `_convertToShares` uses `Rounding.Floor` for both deposit and withdraw paths. `withdraw(a)` burns fewer shares than `deposit(a)` minted, manufacturing free shares. Single rounding helper called on both paths without distinct rounding args.
- **FP:** `deposit` uses `Floor`, `withdraw` uses `Ceil` (vault-favorable both directions). OZ ERC4626 without custom conversion overrides.

**64. ERC4626 Mint/Redeem Asset-Cost Asymmetry**

- **D:** `redeem(s)` returns more assets than `mint(s)` costs — cycling yields net profit. Root cause: `_convertToAssets` rounds up in `redeem` and down in `mint` (opposite of EIP-4626 spec). Pattern: `previewRedeem` uses `Rounding.Ceil`, `previewMint` uses `Rounding.Floor`.
- **FP:** `redeem` uses `Math.Rounding.Floor`, `mint` uses `Math.Rounding.Ceil`. OZ ERC4626 without custom conversion overrides.

**65. ERC1155 Batch Transfer Partial-State Callback Window**

- **D:** Custom batch mint/transfer updates `_balances` and calls `onERC1155Received` per ID in loop, instead of committing all updates first then calling `onERC1155BatchReceived` once. Callback reads stale balances for uncredited IDs.
- **FP:** All balance updates committed before any callback (OZ pattern). `nonReentrant` on all transfer/mint entry points.

**66. Chainlink Staleness / No Validity Checks**

- **D:** `latestRoundData()` called but missing checks: `answer > 0`, `updatedAt > block.timestamp - MAX_STALENESS`, `answeredInRound >= roundId`, fallback on failure.
- **FP:** All four checks present. Circuit breaker or fallback oracle on failure.

**67. Unsafe Downcast / Integer Truncation**

- **D:** `uint128(largeUint256)` without bounds check. Solidity >= 0.8 silently truncates on downcast (no revert). Dangerous in price feeds, share calculations, timestamps.
- **FP:** `require(x <= type(uint128).max)` before cast. OZ `SafeCast` used.

**68. Missing `enforcedOptions` — Insufficient Gas for lzReceive**

- **D:** OApp does not call `setEnforcedOptions()` to mandate minimum gas for destination execution. User-supplied `_options` can specify insufficient gas, causing `lzReceive` to revert on destination. Funds debited on source but not credited on destination — stuck in limbo until manual recovery via `lzComposeAlert` or `skipPayload`.
- **FP:** `enforcedOptions` configured with tested gas limits for each message type. `lzReceive` logic is simple (single mapping update) requiring minimal gas. Executor provides guaranteed minimum gas.

**69. Nonce Gap from Reverted Transactions (CREATE Address Mismatch)**

- **D:** Deployment script uses `CREATE` and pre-computes addresses from deployer nonce. Reverted/extra tx advances nonce — subsequent deployments land at wrong addresses. Pre-configured references point to empty/wrong contracts.
- **FP:** `CREATE2` used (nonce-independent). Script reads nonce from chain before computing. Addresses captured from deployment receipts, not pre-assumed.

**70. Fee-on-Transfer Token Accounting**

- **D:** Deposit records `deposits[user] += amount` then `transferFrom(..., amount)`. Fee-on-transfer tokens cause contract to receive less than recorded.
- **FP:** Balance measured before/after: `uint256 before = token.balanceOf(this); transferFrom(...); received = balanceOf(this) - before;` and `received` used for accounting.

**71. Assembly Delegatecall Missing Return/Revert Propagation**

- **D:** Proxy fallback written in assembly performs `delegatecall` but omits one or more required steps: (1) not copying full calldata via `calldatacopy`, (2) not copying return data via `returndatacopy(0, 0, returndatasize())`, (3) not branching on the result to `return(0, returndatasize())` on success or `revert(0, returndatasize())` on failure. Silent failures or swallowed reverts.
- **FP:** Complete proxy pattern: `calldatacopy(0, 0, calldatasize())` → `delegatecall(gas(), impl, 0, calldatasize(), 0, 0)` → `returndatacopy(0, 0, returndatasize())` → `switch result case 0 { revert(0, returndatasize()) } default { return(0, returndatasize()) }`. OZ Proxy.sol used.

**72. Merkle Tree Second Preimage Attack**

- **D:** `MerkleProof.verify(proof, root, leaf)` where leaf derived from user input without double-hashing or type-prefixing. 64-byte input (two sibling hashes) passes as intermediate node.
- **FP:** Leaves double-hashed or include type prefix. Input length enforced != 64 bytes. OZ MerkleProof >= v4.9.2 with sorted-pair variant.

**73. Dirty Higher-Order Bits on Sub-256-Bit Types**

- **D:** Assembly loads a value as a full 32-byte word (`calldataload`, `sload`, `mload`) but treats it as a smaller type (`address`, `uint128`, `uint8`, `bool`) without masking upper bits. Dirty bits cause incorrect comparisons, mapping key mismatches, or storage corruption. Pattern: `let addr := calldataload(4)` used directly without `and(addr, 0xffffffffffffffffffffffffffffffffffffffff)`.
- **FP:** Explicit bitmask applied: `and(value, mask)` immediately after load. Value produced by a prior Solidity expression that already cleaned it. `shr(96, calldataload(offset))` pattern that naturally zeros upper bits for addresses.

**74. Returndatasize-as-Zero Assumption**

- **D:** Assembly uses `returndatasize()` as a gas-cheap substitute for `push 0` (saves 1 gas). If a prior `call`/`staticcall` in the same execution context returned data, `returndatasize()` is nonzero, corrupting the intended zero value. Pattern: `let ptr := returndatasize()` or `mstore(returndatasize(), value)` after an external call has been made.
- **FP:** `returndatasize()` used as zero only at the very start of execution before any external calls. Used immediately after a controlled call where the return size is known. Used as an actual size measurement (its intended purpose).

**75. tx.origin Authentication**

- **D:** `require(tx.origin == owner)` used for auth. Phishable via intermediary contract.
- **FP:** `tx.origin == msg.sender` used only as anti-contract check, not auth.

**76. ERC20 Non-Compliant: Return Values / Events**

- **D:** Custom `transfer()`/`transferFrom()` doesn't return `bool` or always returns `true` on failure. `mint()`/`burn()` missing `Transfer` events. `approve()` missing `Approval` event.
- **FP:** OZ `ERC20.sol` base with no custom overrides of transfer/approve/event logic.

**77. ERC721Enumerable Index Corruption on Burn or Transfer**

- **D:** Override of `_beforeTokenTransfer` (OZ v4) or `_update` (OZ v5) without calling `super`. Index structures (`_ownedTokens`, `_allTokens`) become stale — `tokenOfOwnerByIndex` returns wrong IDs, `totalSupply` diverges.
- **FP:** Override always calls `super` as first statement. Contract doesn't inherit `ERC721Enumerable`.

**78. Block Stuffing / Gas Griefing on Subcalls**

- **D:** Time-sensitive function blockable by filling blocks. Separate concern: relayer gas-forwarding griefing via 63/64 rule where subcall silently fails but outer tx succeeds.
- **FP:** Function not time-sensitive or window long enough that block stuffing is economically infeasible.

**79. ERC777 tokensToSend / tokensReceived Reentrancy**

- **D:** Token `transfer()`/`transferFrom()` called before state updates on a token that may implement ERC777 (ERC1820 registry). ERC777 hooks fire on ERC20-style calls, enabling reentry from sender's `tokensToSend` or recipient's `tokensReceived`.
- **FP:** CEI — all state committed before transfer. `nonReentrant` on all entry points. Token whitelist excludes ERC777.

**80. Rebasing / Elastic Supply Token Accounting**

- **D:** Contract holds rebasing tokens (stETH, AMPL, aTokens) and caches `balanceOf(this)`. After rebase, cached value diverges from actual balance.
- **FP:** Rebasing tokens blocked at code level (revert/whitelist). Accounting reads `balanceOf` live. Wrapper tokens (wstETH) used.

**81. Assembly Arithmetic Silent Overflow and Division-by-Zero**

- **D:** Arithmetic inside `assembly {}` (Yul) does not revert on overflow/underflow (wraps like `unchecked`) and division by zero returns 0 instead of reverting. Developers accustomed to Solidity 0.8 checked math may not expect this.
- **FP:** Manual overflow checks in assembly (`if gt(result, x) { revert(...) }`). Denominator checked before `div`. Assembly block is read-only (`mload`/`sload` only, no arithmetic).

**82. Flash Loan-Assisted Price Manipulation**

- **D:** Function reads price from on-chain source (AMM reserves, vault `totalAssets()`) manipulable atomically via flash loan + swap in same tx.
- **FP:** TWAP with >= 30min window. Multi-block cooldown between price reads. Separate-block enforcement.

**83. Non-Standard Approve Behavior (Zero-First / Max-Approval Revert)**

- **D:** (a) USDT-style: `approve()` reverts when changing from non-zero to non-zero allowance, requiring `approve(0)` first. (b) Some tokens (UNI, COMP) revert on `approve(type(uint256).max)`. Protocol calls `token.approve(spender, amount)` directly without these accommodations.
- **FP:** OZ `SafeERC20.forceApprove()` or `safeIncreaseAllowance()` used. Allowance always set from zero (fresh per-tx approval). Token whitelist excludes non-standard tokens.

**84. Missing Chain ID Validation in Deployment Configuration**

- **D:** Deploy script reads `$RPC_URL` from `.env` without `eth_chainId` assertion. Foundry script without `--chain-id` flag or `block.chainid` check. No dry-run before broadcast.
- **FP:** `require(block.chainid == expectedChainId)` at script start. CI validates chain ID before deployment.

**85. Array `delete` Leaves Zero-Value Gap Instead of Removing Element**

- **D:** `delete array[index]` resets element to zero but does not shrink the array or shift subsequent elements. Iteration logic treats the zeroed slot as a valid entry — phantom zero-address recipients, skipped distributions, or inflated `length`.
- **FP:** Swap-and-pop pattern used (`array[index] = array[length - 1]; array.pop()`). Iteration skips zero entries explicitly. EnumerableSet or similar library used.

**86. Governance Flash-Loan Upgrade Hijack**

- **D:** Proxy upgrades via governance using current-block vote weight (`balanceOf` or `getPastVotes(block.number)`). No voting delay or timelock. Flash-borrow, vote, execute upgrade in one tx.
- **FP:** `getPastVotes(block.number - 1)`. Timelock 24-72h. High quorum thresholds. Staking lockup required.

**87. Write to Arbitrary Storage Location**

- **D:** (1) `sstore(slot, value)` where `slot` derived from user input without bounds. (2) Solidity <0.6: direct `arr.length` assignment + indexed write at crafted large index wraps slot arithmetic.
- **FP:** Assembly is read-only (`sload` only). Slot is compile-time constant or non-user-controlled. Solidity >= 0.6 used.

**88. Insufficient Return Data Length Validation**

- **D:** Assembly `staticcall`/`call` writes return data into a fixed-size buffer (e.g., `staticcall(gas(), token, ptr, 4, ptr, 32)`) then reads `mload(ptr)` without checking `returndatasize() >= 32`. If the target is an EOA (no code, zero return data) or a non-compliant contract returning fewer bytes, `mload` reads stale memory at `ptr`, which may decode as a truthy value — silently treating a failed/absent call as success.
- **FP:** `if lt(returndatasize(), 32) { revert(0,0) }` checked before reading return data. `extcodesize(target)` verified > 0 before call. Safe ERC20 pattern that handles both zero-length and 32-byte returns. Ref: Consensys Diligence — 0x Exchange bug (real exploit from missing return data length check).

**89. Chainlink Feed Deprecation / Wrong Decimal Assumption**

- **D:** (a) Chainlink aggregator address hardcoded/immutable with no update path — deprecated feed returns stale/zero price. (b) Assumes `feed.decimals() == 8` without runtime check — some feeds return 18 decimals, causing 10^10 scaling error.
- **FP:** Feed address updatable via governance. `feed.decimals()` called and used for normalization. Secondary oracle deviation check.

**90. Upgrade Race Condition / Front-Running**

- **D:** `upgradeTo(V2)` and post-upgrade config calls are separate txs in public mempool. Window for front-running (exploit old impl) or sandwiching between upgrade and config.
- **FP:** `upgradeToAndCall()` bundles upgrade + init. Private mempool (Flashbots Protect). V2 safe with V1 state from block 0. Timelock makes execution predictable.

**91. Missing or Expired Deadline on Swaps**

- **D:** `deadline = block.timestamp` (always valid), `deadline = type(uint256).max`, or no deadline. Tx holdable in mempool indefinitely.
- **FP:** Deadline is calldata parameter validated as `require(deadline >= block.timestamp)`, not derived from `block.timestamp` internally.

**92. Deployment Transaction Front-Running (Ownership Hijack)**

- **D:** Deployment tx sent to public mempool without private relay. Attacker extracts bytecode and deploys first (or front-runs initialization). Pattern: `eth_sendRawTransaction` via public RPC, constructor sets `owner = msg.sender`.
- **FP:** Private relay used (Flashbots Protect, MEV Blocker). Owner passed as constructor arg, not `msg.sender`. Chain without public mempool. CREATE2 salt tied to deployer.

**93. Duplicate Items in User-Supplied Array**

- **D:** Function accepts array parameter (e.g., `claimRewards(uint256[] calldata tokenIds)`) without checking for duplicates. User passes same ID multiple times, claiming rewards/voting/withdrawing repeatedly in one call.
- **FP:** Duplicate check via mapping (`require(!seen[id]); seen[id] = true`). Sorted-unique input enforced (`require(ids[i] > ids[i-1])`). State zeroed on first claim (second iteration reverts naturally).

**94. Transient Storage Low-Gas Reentrancy (EIP-1153)**

- **D:** Contract uses `transfer()`/`send()` (2300-gas) as reentrancy guard + uses `TSTORE`/`TLOAD`. Post-Cancun, `TSTORE` succeeds under 2300 gas unlike `SSTORE`. Second pattern: transient reentrancy lock not cleared at call end — persists for entire tx, causing DoS via multicall/flash loan callback.
- **FP:** `nonReentrant` backed by regular storage slot (or transient mutex properly cleared). CEI followed unconditionally.

**95. Calldataload / Calldatacopy Out-of-Bounds Read**

- **D:** `calldataload(offset)` where `offset` is user-controlled or exceeds actual calldata length. Reading past `calldatasize()` returns zero-padded bytes silently (no revert), producing phantom zero values that pass downstream logic as valid inputs. Pattern: `calldataload(add(4, mul(index, 32)))` without `require(index < paramCount)`.
- **FP:** `calldatasize()` validated before assembly block (e.g., Solidity ABI decoder already checked). Static offsets into known fixed-length function signatures. Explicit `if lt(calldatasize(), minExpected) { revert(0,0) }` guard.

**96. Banned Opcode in Validation Phase (Simulation-Execution Divergence)**

- **D:** `validateUserOp`/`validatePaymasterUserOp` references `block.timestamp`, `block.number`, `block.coinbase`, `block.prevrandao`, `block.basefee`. Per ERC-7562, banned in validation — values differ between simulation and execution.
- **FP:** Banned opcodes only in execution phase (`execute`/`executeBatch`). Entity is staked under ERC-7562 reputation system.

**97. Deployer Privilege Retention Post-Deployment**

- **D:** Deployer EOA retains owner/admin/minter/pauser/upgrader after deployment script completes. Pattern: `Ownable` sets `owner = msg.sender` with no `transferOwnership()`. `AccessControl` grants `DEFAULT_ADMIN_ROLE` to deployer with no `renounceRole()`.
- **FP:** Script includes `transferOwnership(multisig)`. Admin role granted to timelock/governance, deployer renounces. `Ownable2Step` with pending owner set to multisig.

**98. Non-Atomic Multi-Contract Deployment (Partial System Bootstrap)**

- **D:** Deployment script deploys interdependent contracts across separate transactions. Midway failure leaves half-deployed state with missing references or unwired contracts. Pattern: multiple `vm.broadcast()` blocks or sequential `await deploy()` with no idempotency checks.
- **FP:** Single `vm.startBroadcast()`/`vm.stopBroadcast()` block. Factory deploys+wires all in one tx. Script is idempotent. Hardhat-deploy with resumable migrations.

**99. CREATE / CREATE2 Deployment Failure Silently Returns Zero**

- **D:** Assembly `create(v, offset, size)` or `create2(v, offset, size, salt)` returns `address(0)` on failure (insufficient balance, collision, init code revert) but the code does not check for zero. The zero address is stored or used, and subsequent calls to `address(0)` silently succeed as no-ops (no code) or interact with precompiles.
- **FP:** Immediate check: `if iszero(addr) { revert(0, 0) }` after create/create2. Address validated downstream before any state-dependent operation.

**100. ERC721 / ERC1155 Type Confusion in Dual-Standard Marketplace**

- **D:** Shared `buy`/`fill` function uses type flag for ERC721/ERC1155. `quantity` accepted for ERC721 without requiring == 1. `price * quantity` with `quantity = 0` yields zero payment. Ref: TreasureDAO (2022).
- **FP:** ERC721 branch `require(quantity == 1)`. Separate code paths for ERC721/ERC1155.

**101. Cross-Contract Reentrancy**

- **D:** Two contracts share logical state (balances in A, collateral check in B). A makes external call before syncing state B reads. A's `ReentrancyGuard` doesn't protect B.
- **FP:** State B reads is synchronized before A's external call. No re-entry path from A's callee into B.

**102. Non-Atomic Proxy Initialization (Front-Running `initialize()`)**

- **D:** Proxy deployed in one tx, `initialize()` called in separate tx. Uninitialized proxy front-runnable. Pattern: `new TransparentUpgradeableProxy(impl, admin, "")` with empty data, separate `initialize()`. Ref: Wormhole (2022).
- **FP:** Proxy constructor receives init calldata atomically: `new TransparentUpgradeableProxy(impl, admin, abi.encodeCall(...))`. OZ `deployProxy()` used.

**103. EIP-2981 Royalty Signaled But Never Enforced**

- **D:** `royaltyInfo()` implemented and `supportsInterface(0x2a55205a)` returns true, but transfer/settlement logic never calls `royaltyInfo()` or routes payment. EIP-2981 is advisory only.
- **FP:** Settlement contract reads `royaltyInfo()` and transfers royalty on-chain. Royalties intentionally zero and documented.

**104. Paymaster Gas Penalty Undercalculation**

- **D:** Paymaster prefund formula omits 10% EntryPoint penalty on unused execution gas (`postOpUnusedGasPenalty`). Large `executionGasLimit` with low usage drains paymaster deposit.
- **FP:** Prefund explicitly adds unused-gas penalty. Conservative overestimation covers worst case.

**105. ERC721 Approval Not Cleared in Custom Transfer Override**

- **D:** Custom `transferFrom` override skips `super._transfer()` or `super.transferFrom()`, missing the `delete _tokenApprovals[tokenId]` step. Previous approval persists under new owner.
- **FP:** Override calls `super.transferFrom` or `super._transfer` internally. Or explicitly deletes approval / calls `_approve(address(0), tokenId, owner)`.

**106. DoS via Push Payment to Rejecting Contract**

- **D:** ETH distribution in a single loop via `recipient.call{value:}("")`. Any reverting recipient blocks entire loop.
- **FP:** Pull-over-push pattern. Loop uses `try/catch` and continues on failure.

**107. Weak On-Chain Randomness**

- **D:** Randomness from `block.prevrandao`, `blockhash(block.number - 1)`, `block.timestamp`, `block.coinbase`, or combinations. Validator-influenceable or visible before inclusion.
- **FP:** Chainlink VRF v2+. Commit-reveal with future-block reveal and slashing for non-reveal.

**108. Delegatecall to Untrusted Callee**

- **D:** `address(target).delegatecall(data)` where `target` is user-provided or unconstrained.
- **FP:** `target` is hardcoded immutable verified library address.

**109. UUPS `_authorizeUpgrade` Missing Access Control**

- **D:** `function _authorizeUpgrade(address) internal override {}` with empty body and no access modifier. Anyone can call `upgradeTo()`. Ref: CVE-2021-41264.
- **FP:** `_authorizeUpgrade()` has `onlyOwner` or equivalent. Multisig/governance controls owner role.

**110. Insufficient Block Confirmations / Reorg Double-Spend**

- **D:** DVN relays cross-chain message before source chain reaches finality. Attacker deposits on source chain, gets minted on destination, then causes a reorg on source chain (or the chain reorgs naturally) to reverse the deposit while keeping minted tokens. Pattern: confirmation count set below chain's known reorg depth (e.g., < 32 blocks on Polygon).
- **FP:** Confirmation count matches or exceeds chain-specific finality guarantees. Chain has fast finality (e.g., Ethereum post-merge ~12 min). DVN waits for finalized blocks.
