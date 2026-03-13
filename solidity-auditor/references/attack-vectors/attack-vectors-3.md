---

**111. Nested Mapping Inside Struct Not Cleared on `delete`**

- **D:** `delete myMapping[key]` on struct containing `mapping` or dynamic array. `delete` zeroes primitives but not nested mappings. Reused key exposes stale values.
- **FP:** Nested mapping manually cleared before `delete`. Key never reused after deletion.

**112. ERC721A Lazy Ownership — ownerOf Uninitialized in Batch Range**

- **D:** ERC721A/`ERC721Consecutive` batch mint: only first token has ownership written. `ownerOf(id)` for mid-batch IDs may return `address(0)` before any transfer. Access control checking `ownerOf == msg.sender` fails on freshly minted tokens.
- **FP:** Explicit transfer initializes packed slot before ownership check. Standard OZ `ERC721` writes `_owners[tokenId]` per mint.

**113. Cross-Chain Message Spoofing (Missing Endpoint/Peer Validation)**

- **D:** Receiver contract accepts cross-chain messages without verifying `msg.sender == endpoint` and `_origin.sender == registeredPeer[srcChainId]`. Attacker calls the receive function directly with fabricated message data, triggering unauthorized mints/unlocks.
- **FP:** `onlyPeer` modifier or equivalent checks both `msg.sender` (endpoint) and `_origin.sender` (peer). Standard `OAppReceiver._acceptNonce` validates origin. Ref: CrossCurve bridge exploit (Jan 2026) — $3M stolen via spoofed `expressExecute`.

**114. Proxy Admin Key Compromise**

- **D:** `ProxyAdmin.owner()` returns EOA, not multisig/governance; no timelock on `upgradeTo`. Ref: PAID Network (2021), Ankr (2022).
- **FP:** Multisig (threshold >= 2) + timelock (24-72h). Admin role separate from operational roles.

**115. Unauthorized Peer Initialization (Fake Peer Attack)**

- **D:** `setPeer()` / `setTrustedRemote()` sets the remote peer address that a cross-chain contract trusts. If the owner is compromised or `setPeer` lacks proper access control, an attacker registers a fraudulent peer contract on the source chain that can mint/unlock tokens on the destination without legitimate deposits. Pattern: `setPeer` callable by non-owner, or owner key compromised.
- **FP:** `setPeer` protected by multisig + timelock. Peer addresses verified against known deployment registry. `allowInitializePath()` properly implemented to reject unknown peers. Ref: GAIN token exploit (Sep 2025) — fake peer minted 5B tokens, $3M stolen.

**116. Rounding in Favor of the User**

- **D:** `shares = assets / pricePerShare` rounds down for deposit but up for redeem. Division without explicit rounding direction. First-depositor donation amplifies the error.
- **FP:** `Math.mulDiv` with explicit `Rounding.Up` where vault-favorable. OZ ERC4626 `_decimalsOffset()`. Dead shares at init.

**117. Arbitrary External Call with User-Supplied Target and Calldata**

- **D:** `target.call{value: v}(data)` where `target` or `data` (or both) are caller-supplied parameters. Attacker crafts calldata to invoke unintended functions on the target (e.g., `transferFrom` on an approved ERC20, or `safeTransferFrom` on held NFTs), stealing assets the contract holds or has approvals for.
- **FP:** Target restricted to hardcoded/whitelisted address. Calldata function selector restricted to known-safe set. No token approvals or asset holdings on the calling contract. this covers `call` only, not `delegatecall`.

**118. Paymaster ERC-20 Payment Deferred to postOp Without Pre-Validation**

- **D:** `validatePaymasterUserOp` doesn't transfer/lock tokens — payment deferred to `postOp` via `safeTransferFrom`. User can revoke allowance between validation and execution; paymaster loses deposit.
- **FP:** Tokens transferred/locked during `validatePaymasterUserOp`. `postOp` only refunds excess.

**119. Minimal Proxy (EIP-1167) Implementation Destruction**

- **D:** EIP-1167 clones `delegatecall` a fixed implementation. If implementation is destroyed, all clones become no-ops with locked funds. Pattern: `Clones.clone(impl)` where impl has no `selfdestruct` protection or is uninitialized.
- **FP:** No `selfdestruct` in implementation. `_disableInitializers()` in constructor. Post-Dencun: code not destroyed. Beacon proxies used for upgradeability.

**120. Spot Price Oracle from AMM**

- **D:** Price from AMM reserves: `reserve0 / reserve1`, `getAmountsOut()`, `getReserves()`. Flash-loan exploitable atomically.
- **FP:** TWAP >= 30 min window. Chainlink/Pyth as primary source.

**121. Missing Slippage Protection (Sandwich Attack)**

- **D:** Swap/deposit/withdrawal with `minAmountOut = 0`, or `minAmountOut` computed on-chain from current pool state.
- **FP:** `minAmountOut` set off-chain by user and validated on-chain.

**122. NFT Staking Records msg.sender Instead of ownerOf**

- **D:** `depositor[tokenId] = msg.sender` without checking `nft.ownerOf(tokenId)`. Approved operator (not owner) calls stake — transfer succeeds via approval, operator credited as depositor.
- **FP:** Reads `nft.ownerOf(tokenId)` before transfer and records actual owner. Or `require(nft.ownerOf(tokenId) == msg.sender)`.

**123. Missing chainId (Cross-Chain Replay)**

- **D:** Signed payload omits `chainId`. Valid signature replayable on forks/other EVM chains. Or `chainId` hardcoded at deployment instead of `block.chainid`.
- **FP:** EIP-712 domain separator includes dynamic `chainId: block.chainid` and `verifyingContract`.

**124. Non-Standard ERC20 Return Values (USDT-style)**

- **D:** `require(token.transfer(to, amount))` reverts on tokens returning nothing (USDT, BNB). Or return value ignored (silent failure).
- **FP:** OZ `SafeERC20.safeTransfer()`/`safeTransferFrom()` used throughout.

**125. Front-Running Zero Balance Check with Dust Transfer**

- **D:** `require(token.balanceOf(address(this)) == 0)` gates a state transition. Dust transfer makes balance non-zero, DoS-ing the function at negligible cost.
- **FP:** Threshold check (`<= DUST_THRESHOLD`) instead of `== 0`. Access-controlled function. Internal accounting ignores direct transfers.

**126. Diamond Proxy Facet Selector Collision**

- **D:** EIP-2535 Diamond where two facets register same 4-byte selector. Malicious facet via `diamondCut` hijacks calls to critical functions. Pattern: `diamondCut` adds facet with overlapping selectors, no on-chain collision check.
- **FP:** `diamondCut` validates no selector collisions. `DiamondLoupeFacet` enumerates/verifies selectors post-cut. Multisig + timelock on `diamondCut`.

**127. Flash Loan Governance Attack**

- **D:** Voting uses `token.balanceOf(msg.sender)` or `getPastVotes(account, block.number)` (current block). Borrow tokens, vote, repay in one tx.
- **FP:** `getPastVotes(account, block.number - 1)` used. Timelock between snapshot and vote.

**128. Hardcoded Network-Specific Addresses**

- **D:** Literal `address(0x...)` constants for external dependencies (oracles, routers, tokens) in deployment scripts/constructors. Wrong contracts on different chains.
- **FP:** Per-chain config file keyed by chain ID. Script asserts `block.chainid`. Addresses passed as constructor args from environment. Deterministic cross-chain addresses (e.g., Permit2).

**129. ERC4626 Round-Trip Profit Extraction**

- **D:** `redeem(deposit(a)) > a` or inverse — rounding errors in both `_convertToShares` and `_convertToAssets` favor the user, yielding net profit per round-trip.
- **FP:** Rounding per EIP-4626: deposit/mint round down (vault-favorable), withdraw/redeem round up (vault-favorable). OZ ERC4626 with `_decimalsOffset()`.

**130. ERC1155 ID-Based Role Access Control With Publicly Mintable Role Tokens**

- **D:** Access control via `require(balanceOf(msg.sender, ROLE_ID) > 0)` where `mint` for those IDs is not separately gated. Role tokens transferable by default.
- **FP:** Minting role-token IDs gated behind separate access control. Role tokens non-transferable (`_beforeTokenTransfer` reverts for non-mint/burn). Dedicated non-token ACL used.

**131. Off-By-One in Bounds or Range Checks**

- **D:** (1) `i <= arr.length` in loop (accesses OOB index). (2) `arr[arr.length - 1]` in `unchecked` without length > 0 check. (3) `>=` vs `>` confusion in financial logic (early unlock, boundary-exceeding deposit). (4) Integer division rounding accumulation across N recipients.
- **FP:** Loop uses `<` with fixed-length array. Last-element access preceded by length check. Financial boundaries demonstrably correct for the invariant.

**132. ERC4626 Caller-Dependent Conversion Functions**

- **D:** `convertToShares()`/`convertToAssets()` branches on `msg.sender`-specific state (per-user fees, whitelist, balances). EIP-4626 requires caller-independence. Downstream aggregators get wrong sizing.
- **FP:** Implementation reads only global vault state (`totalSupply`, `totalAssets`, protocol-wide fee constants).

**133. Multi-Block TWAP Oracle Manipulation**

- **D:** TWAP observation window < 30 minutes. Post-Merge validators controlling consecutive blocks can hold manipulated AMM state across blocks, shifting TWAP cheaply.
- **FP:** TWAP window >= 30 min. Chainlink/Pyth as price source. Max-deviation circuit breaker against secondary source.

**134. Merkle Proof Reuse — Leaf Not Bound to Caller**

- **D:** Merkle leaf doesn't include `msg.sender`: `MerkleProof.verify(proof, root, keccak256(abi.encodePacked(amount)))`. Proof can be front-run from different address.
- **FP:** Leaf encodes `msg.sender`: `keccak256(abi.encodePacked(msg.sender, amount))`. Proof recorded as consumed after first use.

**135. Uninitialized Implementation Takeover**

- **D:** Implementation behind proxy has `initialize()` but constructor lacks `_disableInitializers()`. Attacker calls `initialize()` on implementation directly, becomes owner, can upgrade to malicious contract. Ref: Wormhole (2022), Parity (2017).
- **FP:** Constructor contains `_disableInitializers()`. OZ `Initializable` correctly gates the function. Not behind a proxy (standalone).

**136. Missing chainId / Message Uniqueness in Bridge**

- **D:** Bridge processes messages without `processedMessages[hash]` replay check, `destinationChainId == block.chainid` validation, or source chain ID in hash. Message replayable cross-chain or on same chain.
- **FP:** Unique nonce per sender. Hash of `(sourceChain, destChain, nonce, payload)` stored and checked. Contract address in hash.

**137. Missing Oracle Price Bounds (Flash Crash / Extreme Value)**

- **D:** Oracle returns a technically valid but extreme price (e.g., ETH at $0.01 during a flash crash). No min/max sanity bound or deviation check against historical/secondary price. Protocol executes liquidations or swaps at wildly incorrect prices.
- **FP:** Circuit breaker: `require(price >= MIN_PRICE && price <= MAX_PRICE)`. Deviation check against secondary oracle source. Heartbeat + price-change-rate limiting.

**138. DVN Collusion or Insufficient DVN Diversity**

- **D:** OApp configured with a single DVN (`1/1/1` security stack) or multiple DVNs controlled by the same entity / using the same underlying verification method. Compromising one entity approves fraudulent cross-chain messages. Pattern: `setConfig` with `requiredDVNCount = 1` and no optional DVNs.
- **FP:** Diverse DVN set (e.g., Google Cloud DVN + Axelar Adapter + protocol's own DVN) with `2/3+` threshold. DVNs use independent verification methods (light client, oracle, ZKP). Protocol runs its own required DVN.

**139. Missing Cross-Chain Rate Limits / Circuit Breakers**

- **D:** Bridge or OFT contract has no per-transaction or time-window transfer caps. A single exploit transaction can drain the entire locked asset pool before detection. No pause mechanism to halt operations during an active exploit.
- **FP:** Per-tx and per-window rate limits configured (e.g., Chainlink CCIP per-lane limits). `whenNotPaused` modifier on send/receive. Anomaly detection with automated pause. Guardian/emergency multisig can freeze operations. Ref: Ronin hack went 6 days undetected — rate limits would have capped losses.

**140. Staking Reward Front-Run by New Depositor**

- **D:** Reward checkpoint (`rewardPerTokenStored`) updated AFTER new stake recorded: `_balances[user] += amount` before `updateReward()`. New staker earns rewards for unstaked period.
- **FP:** `updateReward(account)` executes before any balance update. `rewardPerTokenPaid[user]` tracks per-user checkpoint.

**141. L2 Sequencer Uptime Not Checked**

- **D:** Contract on L2 (Arbitrum/Optimism/Base) uses Chainlink feeds without querying L2 Sequencer Uptime Feed. Stale data during downtime triggers wrong liquidations.
- **FP:** Sequencer uptime feed queried (`answer == 0` = up), with grace period after restart.

**142. Insufficient Gas Forwarding / 63/64 Rule**

- **D:** External call without minimum gas budget: `target.call(data)` with no gas check. 63/64 rule leaves subcall with insufficient gas. In relayer patterns, subcall silently fails but outer tx marks request as "processed."
- **FP:** `require(gasleft() >= minGas)` before subcall. Return value + returndata both checked. EIP-2771 with verified gas parameter.

**143. Accrued Interest Omitted from Health Factor or LTV Calculation**

- **D:** Health factor or LTV computed from principal debt without adding accrued interest: `health = collateral / principal` instead of `collateral / (principal + accruedInterest)`. Understates actual debt, delays necessary liquidations.
- **FP:** `getDebt()` includes accrued interest. Interest accrual function called before health check. Interest compounded on every state-changing interaction.

**144. ERC1155 setApprovalForAll Grants All-Token-All-ID Access**

- **D:** Protocol requires `setApprovalForAll(protocol, true)` for deposits/staking. No per-ID or per-amount granularity -- operator can transfer any ID at full balance.
- **FP:** Protocol uses direct `safeTransferFrom` with user as `msg.sender`. Operator is immutable contract with escrow-only transfer logic.

**145. Storage Layout Collision Between Proxy and Implementation**

- **D:** Proxy declares state variables at sequential slots (not EIP-1967). Implementation also starts at slot 0. Proxy's admin overlaps implementation's `initialized` flag. Ref: Audius (2022).
- **FP:** EIP-1967 slots. OZ Transparent/UUPS pattern. No state variables in proxy contract.

**146. validateUserOp Missing EntryPoint Caller Restriction**

- **D:** `validateUserOp` is `public`/`external` without `require(msg.sender == entryPoint)`. Also check `execute`/`executeBatch` for same restriction.
- **FP:** `require(msg.sender == address(_entryPoint))` or `onlyEntryPoint` modifier present. Internal visibility used.

**147. Diamond Shared-Storage Cross-Facet Corruption**

- **D:** EIP-2535 Diamond facets declare top-level state variables (plain `uint256 foo`) instead of namespaced storage structs. Multiple facets independently start at slot 0, corrupting each other.
- **FP:** All facets use single `DiamondStorage` struct at namespaced position (EIP-7201). No top-level state variables. OZ `@custom:storage-location` pattern.

**148. Stale Cached ERC20 Balance from Direct Token Transfers**

- **D:** Contract tracks holdings in state variable (`totalDeposited`, `_reserves`) updated only through protocol functions. Direct `token.transfer(contract)` inflates real balance beyond cached value. Attacker exploits gap for share pricing/collateral manipulation.
- **FP:** Accounting reads `balanceOf(this)` live. Cached value reconciled at start of every state-changing function. Direct transfers treated as revenue.

**149. Cross-Function Reentrancy**

- **D:** Two functions share state variable. Function A makes external call before updating shared state; Function B reads that state. `nonReentrant` on A but not B.
- **FP:** Both functions share same contract-level mutex. Shared state updated before any external call.

**150. Slippage Enforced at Intermediate Step, Not Final Output**

- **D:** Multi-hop swap checks `minAmountOut` on the first hop or an intermediate step, but the amount actually received by the user at the end of the pipeline has no independent slippage bound. Second/third hops can be sandwiched freely.
- **FP:** `minAmountOut` validated against the user's final received balance (delta check). Single-hop swap. User specifies per-hop minimums.

**151. Non-Atomic Proxy Deployment Enabling CPIMP Takeover**

- **D:** Proxy deployed in one tx, `initialize()` in a separate tx. Attacker front-runs init and inserts a malicious middleman implementation (CPIMP) that persists across upgrades by restoring itself in ERC-1967 slot.
- **FP:** Atomic init calldata in constructor. `_disableInitializers()` in implementation constructor.

**152. Cross-Chain Reentrancy via Safe Transfer Callbacks**

- **D:** Cross-chain receive function (`lzReceive`, `_credit`) calls `_safeMint` or `_safeTransfer` before updating supply/ownership counters. The `onERC721Received` / `onERC1155Received` callback re-enters to initiate another cross-chain send before state is finalized, creating duplicate tokens or double-spending.
- **FP:** State updates (counters, balances) committed before any safe transfer. `nonReentrant` on receive path. `_mint` used instead of `_safeMint` (no callback). Ref: Ackee Blockchain cross-chain reentrancy PoC.

**153. abi.encodePacked Hash Collision with Dynamic Types**

- **D:** `keccak256(abi.encodePacked(a, b))` where two+ args are dynamic types (`string`, `bytes`, dynamic arrays). No length prefix means different inputs produce identical hashes. Affects permits, access control keys, nullifiers.
- **FP:** `abi.encode()` used instead. Only one dynamic type arg. All args fixed-size.

**154. Signed Integer Mishandling (signextend / sar / slt Confusion)**

- **D:** Assembly performs arithmetic on signed integers but uses unsigned opcodes. `shr` instead of `sar` (arithmetic shift right) loses the sign bit. `lt`/`gt` instead of `slt`/`sgt` treats negative numbers as huge positives. Missing `signextend` when loading a signed value smaller than 256 bits from calldata or storage.
- **FP:** Code consistently uses `sar`/`slt`/`sgt` for signed operations and `shr`/`lt`/`gt` for unsigned. `signextend(byteWidth - 1, val)` applied after loading sub-256-bit signed values. Code only operates on unsigned integers.

**155. Missing `_debit` / `_debitFrom` Authorization in OFT**

- **D:** Custom OFT override of `_debit` or `_debitFrom` omits `require(msg.sender == _from || allowance[_from][msg.sender] >= amount)`. Anyone can bridge tokens from any holder's balance. Pattern: `_debit` that calls `_burn(_from, amount)` without verifying caller is authorized.
- **FP:** Standard LayerZero OFT implementation used without override. Custom `_debit` includes proper authorization. `_debit` only callable via `send()` which uses `msg.sender` as `_from`.

**156. Default Message Library Hijack (Configuration Drag-Along)**

- **D:** OApp does not explicitly pin its send/receive library version via `setSendVersion()` / `setReceiveVersion()` (or V2 `setSendLibrary()` / `setReceiveLibrary()`). It relies on the endpoint's mutable default. A malicious or compromised default library update silently applies to all unpinned OApps, bypassing DVN/Oracle validation.
- **FP:** OApp explicitly sets library versions in constructor or initialization. Configuration is immutable or governance-controlled with timelock. LayerZero V2 EndpointV2 is non-upgradeable (but library defaults are still mutable).

**157. ERC-1271 isValidSignature Delegated to Untrusted Module**

- **D:** `isValidSignature(hash, sig)` delegated to externally-supplied contract without whitelist check. Malicious module always returns `0x1626ba7e`, passing all signature checks.
- **FP:** Delegation only to owner-controlled whitelist. Module registry has timelock/guardian approval.

**158. Proxy Storage Slot Collision**

- **D:** Proxy stores `implementation`/`admin` at sequential slots (0, 1); implementation also declares variables from slot 0. Implementation writes overwrite proxy pointers.
- **FP:** EIP-1967 randomized slots used. OZ Transparent/UUPS pattern.

**159. Counterfactual Wallet Initialization Parameters Not Bound to Deployed Address**

- **D:** Factory `createAccount` uses CREATE2 but salt doesn't incorporate all init params (especially owner). Attacker calls `createAccount` with different owner, deploying wallet they control to same counterfactual address.
- **FP:** Salt derived from all init params: `salt = keccak256(abi.encodePacked(owner, ...))`. Factory reverts if account exists. Initializer called atomically with deployment.

**160. Oracle Price Update Front-Running**

- **D:** On-chain oracle update tx visible in mempool. Attacker front-runs a favorable price update by opening a position at the stale price, then profits when the update lands. Pattern: Pyth/Chainlink push-model where update tx is submitted to public mempool.
- **FP:** Protocol uses pull-based oracle (user submits price update atomically with their action). Private mempool (Flashbots Protect) for oracle updates. Price-update-and-action in single tx.

**161. Metamorphic Contract via CREATE2 + SELFDESTRUCT**

- **D:** `CREATE2` deployment where deployer can `selfdestruct` and redeploy different bytecode at same address. Governance-approved code swapped before execution. Ref: Tornado Cash Governance (2023). Post-Dencun (EIP-6780): largely mitigated except same-tx create-destroy-recreate.
- **FP:** Post-Dencun: `selfdestruct` no longer destroys code unless same tx as creation. `EXTCODEHASH` verified at execution time. Not deployed via `CREATE2` from mutable deployer.

**162. Free Memory Pointer Corruption**

- **D:** Assembly block writes to memory at fixed offsets (e.g., `mstore(0x80, val)`) without reading or updating the free memory pointer at `0x40`. Subsequent Solidity code allocates memory from stale pointer, overwriting the assembly-written data — or vice versa. Second pattern: assembly sets `mstore(0x40, newPtr)` to an incorrect value, causing later Solidity allocations to overlap prior data.
- **FP:** Assembly block reads `mload(0x40)`, writes only above that offset, then updates `mstore(0x40, newFreePtr)`. Or block only uses scratch space (`0x00`–`0x3f`). Block annotated `memory-safe` and verified to comply. Ref: Solidity optimizer bug in 0.8.13–0.8.14 mishandled cross-block memory writes.

**163. ERC4626 Inflation Attack (First Depositor)**

- **D:** `shares = assets * totalSupply / totalAssets`. When `totalSupply == 0`, deposit 1 wei + donate inflates share price, victim's deposit rounds to 0 shares. No virtual offset.
- **FP:** OZ ERC4626 with `_decimalsOffset()`. Dead shares minted to `address(0)` at init.

**164. Storage Layout Shift on Upgrade**

- **D:** V2 inserts new state variable in middle of contract instead of appending. Subsequent variables shift slots, corrupting state. Also: changing variable type between versions shifts slot boundaries.
- **FP:** New variables only appended. OZ storage layout validation in CI. Variable types unchanged between versions.

**165. Hardcoded Calldataload Offset Bypass via Non-Canonical ABI Encoding**

- **D:** Assembly reads a field at hardcoded calldata offset (`calldataload(164)`) assuming standard ABI layout. Attacker crafts non-canonical encoding — manipulated dynamic-type offset pointers or padding — so a different value sits at the expected position.
- **FP:** Field decoded via `abi.decode()` (compiler bounds-checked). No hardcoded `calldataload` offsets — parameters extracted through Solidity's typed calldata accessors. `calldatasize() >= expected` validated before reading.
