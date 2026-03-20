**1. Cross-Chain Message Spoofing (Missing Endpoint/Peer Validation)**

- **D:** Receiver contract accepts cross-chain messages without verifying `msg.sender == endpoint` and `_origin.sender == registeredPeer[srcChainId]`. Attacker calls the receive function directly with fabricated message data, triggering unauthorized mints/unlocks.
- **FP:** `onlyPeer` modifier or equivalent checks both `msg.sender` (endpoint) and `_origin.sender` (peer). Standard `OAppReceiver._acceptNonce` validates origin.

**2. EIP-7702 Code Inspection Opcode Invalidation**

- **D:** `extcodesize`, `extcodehash`, `extcodecopy` on delegated EOA operate on the 23-byte `0xef0100` delegation stub, not the delegate's code. `isContract()` checks misroute delegated EOAs. `extcodehash` comparisons against known implementation hashes fail. Proxy detection and ERC-1167 clone verification return unexpected results.
- **FP:** No security-critical branching on `extcodesize`/`extcodehash`. Uses `CODESIZE`/`CODECOPY` within execution context (which follow delegation) rather than `EXT*` variants.

**3. Paymaster Gas Penalty Undercalculation**

- **D:** Paymaster prefund formula omits 10% EntryPoint penalty on unused execution gas (`postOpUnusedGasPenalty`). Large `executionGasLimit` with low usage drains paymaster deposit.
- **FP:** Prefund explicitly adds unused-gas penalty. Conservative overestimation covers worst case.

**4. Reward Rate Changed Without Settling Accumulator**

- **D:** Admin updates emission rate without calling `updateReward()` first. New rate retroactively applied to entire elapsed period, overpaying or underpaying.
- **FP:** Rate-change calls `updateReward()` before applying new rate. Modifier auto-settles on every state change.

**5. lzCompose Sender Impersonation (Composed Message Spoofing)**

- **D:** Two independent checks, BOTH required — missing either one is a finding:
  (a) `lzCompose` does not validate `msg.sender == address(endpoint)`. Attacker calls `lzCompose` directly.
  (b) `lzCompose` does not verify the sender/OApp parameter (`_from`, `_oApp`, or first address parameter) matches the expected trusted OFT/OApp address. Attacker spoofs the origin OApp via the endpoint relay or nested compose messages where sender context degrades to `address(this)`.
- **FP:** BOTH (a) and (b) are present. No nested compose message support. Standard `OAppReceiver` modifier used.

**6. Tick Crossing Fee Accounting Manipulation via JIT**

- **D:** On tick crossing, `feesPerLiquidityOutside` flips (`global - outside`). JIT provider adds at tick boundary after fees accumulate but before crossing — flip credits position with pre-existing fees it didn't earn.
- **FP:** `feesPerLiquidityInsideLast` set at creation; crossing correctly partitions pre/post fees. Same-block creation and crossing yield zero claimable.

**7. Withdrawal Queue Rate Lock-In Front-Run**

- **D:** `requestWithdraw()` locks exchange rate at request time, not claim time. Attacker front-runs pending loss event (slashing, depeg), locks pre-loss rate. Remaining depositors absorb full loss.
- **FP:** Conversion at claim time using worst of request/claim rate. Same-block deposit+request prevented. Loss realization atomic with share price update.

**8. Partial Redemption Fails to Reduce Tracked Total**

- **D:** Partial redemption fill doesn't reduce `totalQueuedShares`/`totalPendingAssets` proportionally. Inflated total skews share price.
- **FP:** Partial fill reduces tracked totals proportionally. Per-request tracking. Atomic full-or-nothing redemptions.

**9. ERC1155 safeBatchTransferFrom Unchecked Array Lengths**

- **D:** Custom `_safeBatchTransferFrom` iterates `ids`/`amounts` without `require(ids.length == amounts.length)`. Assembly-optimized paths may silently read uninitialized memory.
- **FP:** OZ ERC1155 base used unmodified. Custom override asserts equal lengths as first statement.

**10. EIP-7702 Whitelist / Allowlist Privilege Borrowing**

- **D:** Whitelisted address signs EIP-7702 delegation. Attacker includes that authorization in their tx, calls the delegated address — target contract sees `msg.sender == whitelisted_address`. One phished signature becomes a permanent gateway for unlimited actors.
- **FP:** Access control rejects delegation designator prefix (`0xef0100`). Whitelist requires per-call signature, not just address check.

**11. Deprecated Gauge Blocks Claiming Accrued Rewards**

- **D:** Killing/deprecating gauge blocks `claimReward()` for already-accrued, unclaimed rewards — users who earned before deprecation cannot retrieve.
- **FP:** Kill stops future accrual only — claim remains active for pre-kill balances. Emergency claim bypasses active check.

**12. Force-Feeding ETH via selfdestruct / Coinbase / CREATE2 Pre-Funding**

- **D:** Contract uses `address(this).balance` for accounting or gates logic on exact balance (e.g., `require(balance == totalDeposits)`). `selfdestruct(target)`, coinbase rewards, or pre-computed `CREATE2` deposits force ETH in without calling `receive()`/`fallback()`, breaking invariants.
- **FP:** Internal accounting only (`totalDeposited` state variable, never reads `address(this).balance`). Contract designed to accept arbitrary ETH (e.g., WETH wrapper).

**13. EIP-7702 Dual Signature Validation Confusion**

- **D:** Delegated EOA supports both ECDSA (private key) and ERC-1271 (`isValidSignature` from delegate). Protocol checking only one path lets attacker exploit the other. Signature replay across redelegation — message signed under Delegate A interpreted differently by Delegate B.
- **FP:** OZ `SignatureChecker.isValidSignatureNow` used. ERC-1271 checked first for accounts with code, ECDSA fallback for codeless. Signatures include delegate address in EIP-712 domain.

**14. JIT Liquidity on Deterministic TWAMM Virtual Order Execution**

- **D:** TWAMM virtual orders execute at deterministic intervals with publicly readable sale rates. Attacker adds concentrated liquidity before execution, captures fees from predictable flow, removes immediately. No mempool needed — timing fully on-chain.
- **FP:** Time-weighted fee discount for liquidity added within execution window. Execution boundary randomized. Same-block positions excluded from TWAMM fee capture.

**15. Fixed-End Auction Last-Block Sniping**

- **D:** On-chain auction with fixed `endBlock`/`endTime` and no extension. Validator places winning bid in final block, censors competitors. Pattern: `require(block.timestamp <= endTime)` without anti-snipe extension.
- **FP:** Auction extends on late bids. Candle auction (random end). Sealed-bid second-price. Batch/uniform-price clearing.

**16. Adverse Selection — Passive LP Value Extraction via Selective JIT**

- **D:** No time-weighting or lock on fee distribution. JIT providers enter only during high-fee moments and exit during adverse moves. Passive LPs bear 100% IL but share fees with JIT providers bearing zero IL.
- **FP:** Fee share time-weighted by duration. Dynamic fee increases during volatility. Withdrawal cooldown makes selective entry costly.

**17. Governance Flash-Loan Upgrade Hijack**

- **D:** Proxy upgrades via governance using current-block vote weight (`balanceOf` or `getPastVotes(block.number)`). No voting delay or timelock. Flash-borrow, vote, execute upgrade in one tx.
- **FP:** `getPastVotes(block.number - 1)`. Timelock 24-72h. High quorum thresholds. Staking lockup required.

**18. Non-Standard ERC20 Return Values (USDT-style)**

- **D:** `require(token.transfer(to, amount))` reverts on tokens returning nothing (USDT, BNB). Or return value ignored (silent failure).
- **Fix:** Always recommend OZ `SafeERC20.safeTransfer()`/`safeTransferFrom()`. Never recommend `require(token.transfer(...))` — that pattern is itself the bug for non-standard tokens.
- **FP:** OZ `SafeERC20.safeTransfer()`/`safeTransferFrom()` used throughout.

**19. TWAP Accumulator Not Updated During Sync or Skim**

- **D:** `sync()`/`skim()` updates reserves but doesn't call `_update()` to advance TWAP accumulator. Stale TWAP enables manipulation via sync-then-trade.
- **FP:** `sync()` calls `_update()` before overwriting reserves. TWAP from external oracle. Uniswap V3 `observe()` used.

**20. Cross-Chain Sandwich via Bridge Parameter Exposure**

- **D:** Bridge tx on source chain exposes destination swap params (`amountOutMin`, token, amount) in plaintext. Attacker frontruns on destination L2 to manipulate pool, backruns after bridge tx executes.
- **FP:** Encrypted/committed bridge payloads. Destination swap recalculates slippage via oracle. Intent-based bridge (solver fills off-chain).

**21. Funding Rate Derived from Single Trade Price**

- **D:** Perp funding rate uses last trade price as mark. Single self-trade at extreme price skews funding — attacker profits on opposing position.
- **FP:** Mark from TWAP or external oracle. Funding rate capped per period. VWAP used.

**22. Loan State Transition Before Interest Settlement**

- **D:** Repay sets loan to `Repaid` before interest settled. Accrual skips `Repaid` loans — accumulated interest permanently uncollectable.
- **FP:** `settleInterest()` before state transition. `require(msg.value >= principal + accruedInterest)`.

**23. Missing Slippage Protection on Vault Withdraw/Redeem**

- **D:** ERC4626 `withdraw`/`redeem` accept no slippage parameter. Exchange rate changes between submission and execution (yield, donations, losses). Users receive fewer assets or burn more shares than expected.
- **FP:** Fixed 1:1 exchange rate. Custom `withdrawWithSlippage` wrapper. Frontend simulation with revert. Loss-proof yield source.

**24. Dirty Higher-Order Bits on Sub-256-Bit Types**

- **D:** Assembly loads a value as a full 32-byte word (`calldataload`, `sload`, `mload`) but treats it as a smaller type (`address`, `uint128`, `uint8`, `bool`) without masking upper bits. Dirty bits cause incorrect comparisons, mapping key mismatches, or storage corruption. Pattern: `let addr := calldataload(4)` used directly without `and(addr, 0xffffffffffffffffffffffffffffffffffffffff)`.
- **FP:** Explicit bitmask applied: `and(value, mask)` immediately after load. Value produced by a prior Solidity expression that already cleaned it. `shr(96, calldataload(offset))` pattern that naturally zeros upper bits for addresses.

**25. Unsafe Downcast / Integer Truncation**

- **D:** `uint128(largeUint256)` without bounds check. Solidity >= 0.8 silently truncates on downcast (no revert). Dangerous in price feeds, share calculations, timestamps.
- **FP:** `require(x <= type(uint128).max)` before cast. OZ `SafeCast` used.

**26. Small-Type Arithmetic Overflow Before Upcast**

- **D:** Arithmetic on `uint8`/`uint16`/`uint32` before assigning to wider type: `uint256 result = a * b` where `a`,`b` are `uint8`. Overflow happens in narrow type before widening.
- **FP:** Operands explicitly upcast before operation: `uint256(a) * uint256(b)`. SafeCast used.

**27. Missing chainId (Cross-Chain Replay)**

- **D:** Signed payload omits `chainId`. Valid signature replayable on forks/other EVM chains. Or `chainId` hardcoded at deployment instead of `block.chainid`.
- **FP:** EIP-712 domain separator includes dynamic `chainId: block.chainid` and `verifyingContract`.

**28. Chainlink Staleness / No Validity Checks**

- **D:** `latestRoundData()` called but missing checks: `answer > 0`, `updatedAt > block.timestamp - MAX_STALENESS`, `answeredInRound >= roundId`, fallback on failure.
- **FP:** All four checks present. Circuit breaker or fallback oracle on failure.

**29. Signed Integer Mishandling (signextend / sar / slt Confusion)**

- **D:** Assembly performs arithmetic on signed integers but uses unsigned opcodes. `shr` instead of `sar` (arithmetic shift right) loses the sign bit. `lt`/`gt` instead of `slt`/`sgt` treats negative numbers as huge positives. Missing `signextend` when loading a signed value smaller than 256 bits from calldata or storage.
- **FP:** Code consistently uses `sar`/`slt`/`sgt` for signed operations and `shr`/`lt`/`gt` for unsigned. `signextend(byteWidth - 1, val)` applied after loading sub-256-bit signed values. Code only operates on unsigned integers.

**30. ERC777 tokensToSend / tokensReceived Reentrancy**

- **D:** Token `transfer()`/`transferFrom()` called before state updates on a token that may implement ERC777 (ERC1820 registry). ERC777 hooks fire on ERC20-style calls, enabling reentry from sender's `tokensToSend` or recipient's `tokensReceived`.
- **FP:** CEI — all state committed before transfer. `nonReentrant` on all entry points. Token whitelist excludes ERC777.

**31. Storage Layout Collision Between Proxy and Implementation**

- **D:** Proxy declares state variables at sequential slots (not EIP-1967). Implementation also starts at slot 0. Proxy's admin overlaps implementation's `initialized` flag.
- **FP:** EIP-1967 slots. OZ Transparent/UUPS pattern. No state variables in proxy contract.

**32. Token Decimal Mismatch in Cross-Token Arithmetic**

- **D:** Cross-token math uses hardcoded `1e18` or assumes identical decimals. Pattern: collateral/LTV/rate calculations combining token amounts without per-token `decimals()` normalization.
- **FP:** Amounts normalized to canonical precision (WAD/RAY) using each token's `decimals()`. Explicit `10 ** (18 - decimals())` scaling. Protocol only supports tokens with identical verified decimals.

**33. ERC4626 Caller-Dependent Conversion Functions**

- **D:** `convertToShares()`/`convertToAssets()` branches on `msg.sender`-specific state (per-user fees, whitelist, balances). EIP-4626 requires caller-independence. Downstream aggregators get wrong sizing.
- **FP:** Implementation reads only global vault state (`totalSupply`, `totalAssets`, protocol-wide fee constants).

**34. Permit Signature Frontrun Griefing**

- **D:** Contract calls `permit()` then `transferFrom()` sequentially. Attacker extracts permit from mempool, calls `permit()` first — nonce consumed, user's tx reverts.
- **FP:** `try token.permit(...) {} catch {}` — permit failure non-fatal. Permit2 with unordered nonces. Direct approval flow.

**35. Slippage Enforced at Intermediate Step, Not Final Output**

- **D:** Multi-hop swap checks `minAmountOut` on the first hop or an intermediate step, but the amount actually received by the user at the end of the pipeline has no independent slippage bound. Second/third hops can be sandwiched freely.
- **FP:** `minAmountOut` validated against the user's final received balance (delta check). Single-hop swap. User specifies per-hop minimums.

**36. False Existence Detection via Balance Check at Computed Address**

- **D:** Contract checks pool/pair existence via `balanceOf()` at computed CREATE2 address. Pre-sent tokens make `balanceOf > 0` before deployment — logic assumes pool exists, attempts swap, reverts.
- **FP:** Existence via factory: `factory.getPair(A, B) != address(0)`. `code.length > 0` checked. Pool verified by calling pool-specific function (`getReserves()`, `token0()`).

**37. Missing Cross-Chain Rate Limits / Circuit Breakers**

- **D:** Bridge or OFT contract has no per-transaction or time-window transfer caps. No pause mechanism to halt operations during an active exploit.
- **FP:** Per-tx and per-window rate limits configured (e.g., Chainlink CCIP per-lane limits). `whenNotPaused` modifier on send/receive. Anomaly detection with automated pause. Guardian/emergency multisig can freeze operations.

**38. Weak On-Chain Randomness**

- **D:** Randomness from `block.prevrandao`, `blockhash(block.number - 1)`, `block.timestamp`, `block.coinbase`, or combinations. Validator-influenceable or visible before inclusion.
- **FP:** Chainlink VRF v2+. Commit-reveal with future-block reveal and slashing for non-reveal.

**39. Spot Price Oracle from AMM**

- **D:** Price from AMM reserves: `reserve0 / reserve1`, `getAmountsOut()`, `getReserves()`. Flash-loan exploitable atomically.
- **FP:** TWAP >= 30 min window. Chainlink/Pyth as primary source.

**40. Liquidation Discount Applied Inconsistently Across Code Paths**

- **D:** One path calculates debt at face value, another applies discount. Mismatch causes underflow or leaves residual bad debt unaccounted.
- **FP:** Discount applied consistently across all liquidation paths. Single source of truth for discounted value.

**41. Beacon Proxy Single-Point-of-Failure Upgrade**

- **D:** Multiple proxies read implementation from single Beacon. Compromising Beacon owner upgrades all proxies at once. `UpgradeableBeacon.owner()` returns single EOA.
- **FP:** Beacon owner is multisig + timelock. `Upgraded` events monitored. Per-proxy upgrade authority where isolation required.

**42. Upgrade Race Condition / Front-Running**

- **D:** `upgradeTo(V2)` and post-upgrade config calls are separate txs in public mempool. Window for front-running (exploit old impl) or sandwiching between upgrade and config.
- **FP:** `upgradeToAndCall()` bundles upgrade + init. Private mempool (Flashbots Protect). V2 safe with V1 state from block 0. Timelock makes execution predictable.

**43. LST Redemption-Rate vs Market-Price Divergence**

- **D:** LST collateral valued at protocol redemption rate (`stETH.getPooledEthByShares()`) while market trades at discount. Borrower posts overvalued collateral, borrows against inflated value. During stress, redemption rate stays high while market drops — bad debt.
- **FP:** Market price feed (Chainlink stETH/ETH) used. `min(redemptionRate, marketPrice)` for valuation. LTV haircut for historical deviation. Circuit breaker on divergence.

**44. Returndatasize-as-Zero Assumption**

- **D:** Assembly uses `returndatasize()` as a gas-cheap substitute for `push 0` (saves 1 gas). If a prior `call`/`staticcall` in the same execution context returned data, `returndatasize()` is nonzero, corrupting the intended zero value. Pattern: `let ptr := returndatasize()` or `mstore(returndatasize(), value)` after an external call has been made.
- **FP:** `returndatasize()` used as zero only at the very start of execution before any external calls. Used immediately after a controlled call where the return size is known. Used as an actual size measurement (its intended purpose).

**45. ERC1155 Fungible / Non-Fungible Token ID Collision**

- **D:** ERC1155 represents both fungible and unique items with no enforcement: missing `require(totalSupply(id) == 0)` before NFT mint, or no cap preventing additional copies of supply-1 IDs.
- **FP:** `require(totalSupply(id) + amount <= maxSupply(id))` with `maxSupply=1` for NFTs. Fungible/NFT ID ranges disjoint and enforced. Role tokens non-transferable.

**46. Array `delete` Leaves Zero-Value Gap Instead of Removing Element**

- **D:** `delete array[index]` resets element to zero but does not shrink the array or shift subsequent elements. Iteration logic treats the zeroed slot as a valid entry — phantom zero-address recipients, skipped distributions, or inflated `length`.
- **FP:** Swap-and-pop pattern used (`array[index] = array[length - 1]; array.pop()`). Iteration skips zero entries explicitly. EnumerableSet or similar library used.

**47. Merkle Proof Reuse — Leaf Not Bound to Caller**

- **D:** Merkle leaf doesn't include `msg.sender`: `MerkleProof.verify(proof, root, keccak256(abi.encodePacked(amount)))`. Proof can be front-run from different address.
- **FP:** Leaf encodes `msg.sender`: `keccak256(abi.encodePacked(msg.sender, amount))`. Proof recorded as consumed after first use.

**48. Missing chainId / Message Uniqueness in Bridge**

- **D:** Three independent checks, ALL required — missing any one is a finding:
  (a) No `processedMessages[hash]` or equivalent replay check. Same message processable multiple times on the same chain.
  (b) No `destinationChainId == block.chainid` validation. Message intended for chain A processable on chain B.
  (c) Source chain ID not included in message hash. Messages from different source chains produce identical hashes, enabling cross-chain replay.
- **FP:** ALL three present: (a) unique nonce/hash stored and checked before processing, (b) destination chain validated, (c) hash includes `(sourceChain, destChain, nonce, payload)`. Contract address in hash.

**49. Quorum Computed from Live Supply, Not Snapshot**

- **D:** `quorum = totalSupply() * quorumBps / 10000` reads current supply. Attacker inflates supply after proposal creation, lowering effective quorum percentage.
- **FP:** Quorum snapshotted at proposal creation. Fixed absolute quorum. Supply changes don't affect active proposals.

**50. Integer Overflow / Underflow**

- **D:** Arithmetic in `unchecked {}` (>=0.8) without prior bounds check: subtraction without `require(amount <= balance)`, large multiplications. Any arithmetic in <0.8 without SafeMath.
- **FP:** Range provably bounded by earlier checks in same function. `unchecked` only for `++i` loop increments where `i < arr.length`.

**51. Share Redemption at Optimistic Rate**

- **D:** Shares redeemed at projected end-of-term rate rather than current realized rate. Early redeemers take more than proportional share — late redeemers find vault depleted.
- **FP:** Redemption uses current realized rate (`totalAssets() / totalSupply()`). Withdrawal queue enforces proportional access. Early redemption penalty applied.

**52. Rounding in Favor of the User**

- **D:** `shares = assets / pricePerShare` rounds down for deposit but up for redeem. Division without explicit rounding direction. First-depositor donation amplifies the error.
- **FP:** `Math.mulDiv` with explicit `Rounding.Up` where vault-favorable. OZ ERC4626 `_decimalsOffset()`. Dead shares at init.

**53. UUPS Upgrade Logic Removed in New Implementation**

- **D:** New UUPS implementation doesn't inherit `UUPSUpgradeable` or removes `upgradeTo`/`upgradeToAndCall`. Proxy permanently loses upgrade capability. Pattern: V2 missing `_authorizeUpgrade` override.
- **FP:** Every version inherits `UUPSUpgradeable`. Tests verify `upgradeTo` works after each upgrade. OZ upgrades plugin checks in CI.

**54. Uninitialized Implementation Takeover**

- **D:** Implementation behind proxy has `initialize()` but constructor lacks `_disableInitializers()`. Attacker calls `initialize()` on implementation directly, becomes owner, can upgrade to malicious contract.
- **FP:** Constructor contains `_disableInitializers()`. OZ `Initializable` correctly gates the function. Not behind a proxy (standalone).

**55. EIP-7702 EOA Reentrancy and ETH Transfer DoS**

- **D:** ETH sent to address assumed to be EOA. Delegated EOA has `receive()`/`fallback()` — enables classic reentrancy if state updated after `call{value:}`. Second pattern: `transfer()`/`send()` forwards only 2300 gas, insufficient for delegate's fallback — reverts, DoS-ing withdrawals/refunds.
- **FP:** CEI pattern followed. `nonReentrant` applied. Uses `call{value:}` not `transfer`/`send`. Pull-payment pattern.

**56. Atomic JIT Liquidity via Flash Accounting**

- **D:** Flash accounting / lock-callback allows add-liquidity + swap + remove-liquidity atomically with zero capital. No minimum hold duration or fee decay. Attacker adds concentrated liquidity at current tick, swap executes through it, liquidity removed — all in one callback.
- **FP:** Minimum hold duration enforced. Fee share weighted by time-in-pool. Withdrawal fee on short-lived positions. Flash callback restricted from `updatePosition`.

**57. Missing Nonce (Signature Replay)**

- **D:** Signed message has no per-user nonce, or nonce present but never stored/incremented after use. Same signature resubmittable.
- **FP:** Monotonic per-signer nonce in signed payload, checked and incremented atomically. Or `usedSignatures[hash]` mapping.

**58. ERC721A Lazy Ownership — ownerOf Uninitialized in Batch Range**

- **D:** ERC721A/`ERC721Consecutive` batch mint: only first token has ownership written. `ownerOf(id)` for mid-batch IDs may return `address(0)` before any transfer. Access control checking `ownerOf == msg.sender` fails on freshly minted tokens.
- **FP:** Explicit transfer initializes packed slot before ownership check. Standard OZ `ERC721` writes `_owners[tokenId]` per mint.

**59. No Buffer Between Max LTV and Liquidation Threshold**

- **D:** Max borrowable LTV equals liquidation threshold — positions at max LTV immediately liquidatable on any adverse tick. With origination fees, positions born underwater.
- **FP:** Max LTV meaningfully lower than liquidation threshold (e.g., 80% vs 85%). Origination fee deducted from borrowed amount.

**60. Return Bomb (Returndata Copy DoS)**

- **D:** `(bool success, bytes memory data) = target.call(payload)` where `target` is user-supplied. Malicious target returns huge returndata; copying costs enormous gas.
- **FP:** Returndata not copied (assembly call without copy, or gas-limited). Callee is hardcoded trusted contract.

**61. Cross-Contract Reentrancy**

- **D:** Two contracts share logical state (balances in A, collateral check in B). A makes external call before syncing state B reads. A's `ReentrancyGuard` doesn't protect B.
- **FP:** State B reads is synchronized before A's external call. No re-entry path from A's callee into B.

**62. DoS via Push Payment to Rejecting Contract**

- **D:** ETH distribution in a single loop via `recipient.call{value:}("")`. Any reverting recipient blocks entire loop.
- **FP:** Pull-over-push pattern. Loop uses `try/catch` and continues on failure.

**63. Diamond Shared-Storage Cross-Facet Corruption**

- **D:** EIP-2535 Diamond facets declare top-level state variables (plain `uint256 foo`) instead of namespaced storage structs. Multiple facets independently start at slot 0, corrupting each other.
- **FP:** All facets use single `DiamondStorage` struct at namespaced position (EIP-7201). No top-level state variables. OZ `@custom:storage-location` pattern.

**64. ERC721 / ERC1155 Type Confusion in Dual-Standard Marketplace**

- **D:** Shared `buy`/`fill` function uses type flag for ERC721/ERC1155. `quantity` accepted for ERC721 without requiring == 1. `price * quantity` with `quantity = 0` yields zero payment.
- **FP:** ERC721 branch `require(quantity == 1)`. Separate code paths for ERC721/ERC1155.

**65. Improper Flash Loan Callback Validation**

- **D:** Two independent checks, BOTH required — missing either one is a finding:
  (a) `onFlashLoan` callback doesn't verify `msg.sender == lendingPool`. Attacker calls the callback directly without a real flash loan.
  (b) `onFlashLoan` doesn't validate `initiator`, `token`, or `amount` parameters. Attacker triggers a legitimate flash loan from the pool but with crafted parameters to hijack the callback logic.
- **FP:** BOTH (a) and (b) are present: `msg.sender == address(lendingPool)` validated AND `initiator == address(this)` plus token/amount checked.

**66. ERC721 Unsafe Transfer to Non-Receiver**

- **D:** `_transfer()`/`_mint()` used instead of `_safeTransfer()`/`_safeMint()`, sending NFTs to contracts without `IERC721Receiver`. Tokens permanently locked.
- **FP:** All paths use `safeTransferFrom`/`_safeMint`. Function is `nonReentrant`.

**67. Hardcoded Calldataload Offset Bypass via Non-Canonical ABI Encoding**

- **D:** Assembly reads a field at hardcoded calldata offset (`calldataload(164)`) assuming standard ABI layout. Attacker crafts non-canonical encoding — manipulated dynamic-type offset pointers or padding — so a different value sits at the expected position.
- **FP:** Field decoded via `abi.decode()` (compiler bounds-checked). No hardcoded `calldataload` offsets — parameters extracted through Solidity's typed calldata accessors. `calldatasize() >= expected` validated before reading.

**68. EIP-7702 Delegation Initialization Front-Run**

- **D:** EOA delegates to smart wallet requiring separate `initialize(owner)` call. Attacker front-runs with victim's authorization, calls `initialize()` first — takes ownership of EOA's wallet and assets.
- **FP:** Delegation and initialization bundled atomically. Owner derived from authorization signature via `ecrecover`. No permissionless `initialize()` step.

**69. Free Memory Pointer Corruption**

- **D:** Assembly block writes to memory at fixed offsets (e.g., `mstore(0x80, val)`) without reading or updating the free memory pointer at `0x40`. Subsequent Solidity code allocates memory from stale pointer, overwriting the assembly-written data — or vice versa. Second pattern: assembly sets `mstore(0x40, newPtr)` to an incorrect value, causing later Solidity allocations to overlap prior data.
- **FP:** Assembly block reads `mload(0x40)`, writes only above that offset, then updates `mstore(0x40, newFreePtr)`. Or block only uses scratch space (`0x00`–`0x3f`). Block annotated `memory-safe` and verified to comply..8.13–0.8.14 mishandled cross-block memory writes.

**70. Rebasing / Elastic Supply Token Accounting**

- **D:** Contract holds rebasing tokens (stETH, AMPL, aTokens) and caches `balanceOf(this)`. After rebase, cached value diverges from actual balance.
- **FP:** Rebasing tokens blocked at code level (revert/whitelist). Accounting reads `balanceOf` live. Wrapper tokens (wstETH) used.

**71. Nonce Not Incremented on Reverted Execution**

- **D:** Meta-tx nonce checked before execution but incremented only on success. Reverted inner call leaves nonce unchanged — same signed message replayable until it succeeds.
- **FP:** Nonce incremented before execution (CEI). Incremented in both success/failure paths. Deadline-based expiry.

**72. ERC721/ERC1155 Callback Reentrancy**

- **D:** `safeTransferFrom`/`safeMint` called before state updates. Callbacks (`onERC721Received`/`onERC1155Received`) enable reentry.
- **FP:** All state committed before safe transfer. `nonReentrant` applied.

**73. Minimum Lock Period Bypass via Position Modification**

- **D:** Lock enforced on creation/removal but not `increaseLiquidity`/`decreaseLiquidity`. Attacker maintains minimal position, increases massively before profitable swap, decreases after — bypassing lock.
- **FP:** Lock applies to any increase — `lastModifiedBlock` updated on every change. Fee accrual begins after lock for newly added liquidity.

**74. msg.value Reuse in Loop / Multicall**

- **D:** `msg.value` read inside a loop or `delegatecall`-based multicall. Each iteration/sub-call sees the full original value — credits `n * msg.value` for one payment.
- **FP:** `msg.value` captured to local variable, decremented per iteration, total enforced. Function non-payable. Multicall uses `call` not `delegatecall`.

**75. ERC4626 Missing Allowance Check in withdraw() / redeem()**

- **D:** `withdraw(assets, receiver, owner)` / `redeem(shares, receiver, owner)` where `msg.sender != owner` but no allowance check/decrement before burning shares. Any address can burn arbitrary owner's shares.
- **FP:** `_spendAllowance(owner, caller, shares)` called unconditionally when `caller != owner`. OZ ERC4626 without custom overrides.

**76. Multi-Block TWAP Oracle Manipulation**

- **D:** TWAP observation window < 30 minutes. Post-Merge validators controlling consecutive blocks can hold manipulated AMM state across blocks, shifting TWAP cheaply.
- **FP:** TWAP window >= 30 min. Chainlink/Pyth as price source. Max-deviation circuit breaker against secondary source.

**77. ERC721 onERC721Received Arbitrary Caller Spoofing**

- **D:** `onERC721Received` uses parameters (`from`, `tokenId`) to update state without verifying `msg.sender` is the expected NFT contract. Anyone calls directly with fabricated parameters.
- **FP:** `require(msg.sender == address(nft))` before state update. Function is view-only or reverts unconditionally.

**78. Governance Precondition Manipulation**

- **D:** Parameter updates have preconditions based on manipulable state (TVL, liquidity). Adversary inflates/deflates state to block updates — DoS on governance prevents critical changes (fee adjustments, security patches, oracle swaps).
- **FP:** Preconditions use time-weighted/snapshot values. No state-dependent preconditions. Admin emergency override. Absolute thresholds, not relative to manipulable state.

**79. Same-Block Deposit-Withdraw Exploiting Snapshot-Based Benefits**

- **D:** Protocol calculates yield, rewards, voting power, or insurance coverage based on balance at a single snapshot point. No minimum lock period between deposit and withdrawal. Attacker flash-loans tokens, deposits, triggers snapshot (or waits for same-block snapshot), claims benefit, withdraws — all in one tx/block.
- **FP:** `getPastVotes(block.number - 1)` or equivalent past-block snapshot. Minimum holding period enforced (`require(block.number > depositBlock)`). Reward accrual requires multi-block time passage.

**80. Idle Asset Dilution from Sub-Vault Deposit Caps**

- **D:** Aggregator vault accepts deposits without checking sub-vault capacity. Excess assets sit idle earning zero yield but dilute share price for all depositors.
- **FP:** `maxDeposit()` reflects combined sub-vault remaining capacity. Deposits revert when no capacity remains. Idle assets auto-routed to fallback yield.

**81. Liquidation Arithmetic Reverts at Extreme Price Drops**

- **D:** Collateral drops 95%+ — `collateralNeeded = debt / price` exceeds available collateral, liquidation math overflows/reverts. Position unliquidatable, bad debt locked.
- **FP:** `collateralSeized` capped at position's total. Full seizure with remaining bad debt socialized.

**82. Memory Struct Copy Not Written Back to Storage**

- **D:** `MyStruct memory s = myMapping[key]` creates a copy — mutations don't persist. Also: internal function with `memory` parameter silently copies storage on call. Pattern: `_updatePosition(Position memory pos)` called with `positions[user]`.
- **FP:** Uses `storage` keyword. Explicitly writes back: `myMapping[key] = s`. Internal function parameter declared as `storage`.

**83. Non-Standard ERC20 Permit Interface**

- **D:** `depositWithPermit` assumes ERC-2612 standard signature. DAI uses non-standard permit with `nonce` parameter. Other tokens have different interfaces or no permit. Function reverts for non-conforming tokens.
- **FP:** Multiple permit interfaces supported (ERC-2612 + DAI). `try/catch` with fallback to regular approve. Permit restricted to verified token whitelist.

**84. Front-Running Zero Balance Check with Dust Transfer**

- **D:** `require(token.balanceOf(address(this)) == 0)` gates a state transition. Dust transfer makes balance non-zero, DoS-ing the function at negligible cost.
- **FP:** Threshold check (`<= DUST_THRESHOLD`) instead of `== 0`. Access-controlled function. Internal accounting ignores direct transfers.

**85. Vault Insolvency via Accumulated Rounding Dust**

- **D:** Vault tracks `totalAssets` as a storage variable separate from `token.balanceOf(vault)`. Solidity's floor rounding on each deposit/withdrawal creates tiny overages — user receives 1 wei more than burned shares represent. Over many operations `totalAssets` exceeds actual balance, causing last withdrawers to revert.
- **FP:** Rounding consistently favors the vault (round shares up on deposit, round assets down on withdrawal). OZ Math with `Rounding.Ceil`/`Rounding.Floor` applied correctly.

**86. ERC721 Approval Not Cleared in Custom Transfer Override**

- **D:** Custom `transferFrom` override skips `super._transfer()` or `super.transferFrom()`, missing the `delete _tokenApprovals[tokenId]` step. Previous approval persists under new owner.
- **FP:** Override calls `super.transferFrom` or `super._transfer` internally. Or explicitly deletes approval / calls `_approve(address(0), tokenId, owner)`.

**87. Vault Harvest Front-Running**

- **D:** `harvest()` claims yield and increases `totalAssets()` atomically, raising share price. Attacker deposits before harvest, withdraws after — captures yield without duration exposure.
- **FP:** Yield distributed over time (drip/streaming). Deposit lock spans harvest cycle. Harvest via keeper in private mempool. Performance fee at harvest.

**88. validateUserOp Signature Not Bound to nonce or chainId**

- **D:** `validateUserOp` reconstructs digest manually (not via `entryPoint.getUserOpHash`) omitting `userOp.nonce` or `block.chainid`. Enables cross-chain or in-chain replay.
- **FP:** Digest from `entryPoint.getUserOpHash(userOp)` (includes sender, nonce, chainId). Custom digest explicitly includes both.

**89. Self-Matched Orders Enable Wash Trading**

- **D:** Order matching doesn't verify `maker != taker`. User submits both sides to farm rewards, inflate volume, bypass royalties, or extract fee rebates.
- **FP:** `require(maker != taker)`. Volume rewards use time-weighted averages. Royalty enforced regardless of counterparty.

**90. Block Stuffing / Gas Griefing on Subcalls**

- **D:** Time-sensitive function blockable by filling blocks. Separate concern: relayer gas-forwarding griefing via 63/64 rule where subcall silently fails but outer tx succeeds.
- **FP:** Function not time-sensitive or window long enough that block stuffing is economically infeasible.

**91. Banned Opcode in Validation Phase (Simulation-Execution Divergence)**

- **D:** `validateUserOp`/`validatePaymasterUserOp` references `block.timestamp`, `block.number`, `block.coinbase`, `block.prevrandao`, `block.basefee`. Per ERC-7562, banned in validation — values differ between simulation and execution.
- **FP:** Banned opcodes only in execution phase (`execute`/`executeBatch`). Entity is staked under ERC-7562 reputation system.

**92. Flash Loan-Assisted Price Manipulation**

- **D:** Function reads price from on-chain source (AMM reserves, vault `totalAssets()`) manipulable atomically via flash loan + swap in same tx.
- **FP:** TWAP with >= 30min window. Multi-block cooldown between price reads. Separate-block enforcement.

**93. Small Positions Unliquidatable Due to Insufficient Incentive (Bad Debt)**

- **D:** Positions below a certain USD value cost more gas to liquidate than the liquidation reward. During market downturns, these "dust positions" accumulate bad debt that no liquidator will process, eroding protocol solvency.
- **FP:** Minimum position size enforced at borrow time. Protocol-operated liquidation bot covers dust positions. Socialized bad debt mechanism (insurance fund, haircuts).

**94. Profit Tracking Underflow Blocks Withdrawals**

- **D:** Vault tracks cumulative profit. Strategy loss exceeding recorded profit causes `totalProfit -= loss` to underflow (revert on 0.8+), bricking all withdrawals.
- **FP:** Loss capped: `totalProfit -= min(loss, totalProfit)`. Signed integer for profit/loss. Per-strategy tracking.

**95. Missing or Incorrect Access Modifier**

- **D:** State-changing function (`setOwner`, `withdrawFunds`, `mint`, `pause`, `setOracle`) has no access guard or modifier references uninitialized variable. `public`/`external` on privileged operations with no restriction.
- **FP:** Function is intentionally permissionless with non-critical worst-case outcome (e.g., advancing a public time-locked process).

**96. NFT Staking Records msg.sender Instead of ownerOf**

- **D:** `depositor[tokenId] = msg.sender` without checking `nft.ownerOf(tokenId)`. Approved operator (not owner) calls stake — transfer succeeds via approval, operator credited as depositor.
- **FP:** Reads `nft.ownerOf(tokenId)` before transfer and records actual owner. Or `require(nft.ownerOf(tokenId) == msg.sender)`.

**97. Cross-Chain Deployment Replay**

- **D:** Deployment tx replayed on another chain. Same deployer nonce on both chains produces same CREATE address under different control. No EIP-155 chain ID protection.
- **FP:** EIP-155 signatures. `CREATE2` via deterministic factory at same address on all chains. Per-chain deployer EOAs.

**98. abi.encodePacked Hash Collision with Dynamic Types**

- **D:** `keccak256(abi.encodePacked(a, b))` where two+ args are dynamic types (`string`, `bytes`, dynamic arrays). No length prefix means different inputs produce identical hashes. Affects permits, access control keys, nullifiers.
- **FP:** `abi.encode()` used instead. Only one dynamic type arg. All args fixed-size.

**99. ERC1155 Batch Transfer Partial-State Callback Window**

- **D:** Custom batch mint/transfer updates `_balances` and calls `onERC1155Received` per ID in loop, instead of committing all updates first then calling `onERC1155BatchReceived` once. Callback reads stale balances for uncredited IDs.
- **FP:** All balance updates committed before any callback (OZ pattern). `nonReentrant` on all transfer/mint entry points.

**100. Arbitrary `delegatecall` in Implementation**

- **D:** Implementation exposes `delegatecall` to user-supplied address without restriction. Pattern: `target.delegatecall(data)` where `target` is caller-controlled.
- **FP:** Target is hardcoded immutable address. Whitelist of approved targets enforced. `call` used instead.

**101. Cross-Chain Reentrancy via Safe Transfer Callbacks**

- **D:** Cross-chain receive function (`lzReceive`, `_credit`) calls `_safeMint` or `_safeTransfer` before updating supply/ownership counters. The `onERC721Received` / `onERC1155Received` callback re-enters to initiate another cross-chain send before state is finalized, creating duplicate tokens or double-spending.
- **FP:** State updates (counters, balances) committed before any safe transfer. `nonReentrant` on receive path. `_mint` used instead of `_safeMint` (no callback).

**102. Hook Callback Reentrancy for Fee Bypass**

- **D:** User-controlled hook (beforeClaim, onReceive) fires mid-operation before fee accounting finalized. User reenters different contract via alternate path that skips fee deduction.
- **FP:** Global reentrancy lock (not per-function). Hook fires after all state changes and fees finalized. Cross-contract mutex.

**103. Signature Malleability**

- **D:** Raw `ecrecover` without `s <= 0x7FFF...20A0` validation. Both `(v,r,s)` and `(v',r,s')` recover same address. Bypasses signature-based dedup.
- **FP:** OZ `ECDSA.recover()` used (validates `s` range). Message hash used as dedup key, not signature bytes.

**104. Withdrawal Queue Bricked by Zero-Amount Entry**

- **D:** FIFO withdrawal queue hits cancelled/zeroed entry that causes `break` or revert instead of skip, permanently blocking all subsequent withdrawals.
- **FP:** Queue skips zero-amount entries. Cancellation removes or marks entry processed. Linked list allows removal.

**105. Cross-Message Token Identity Mismatch**

- **D:** Multi-hop/cross-chain flow uses user-controlled token fields per leg without cross-validation. Attacker deposits token A but encodes token B — destination withdraws contract's balance of B. Pattern: `depositedToken`, `swapFromToken`, `swapToToken`, `withdrawalToken` specified independently.
- **FP:** `require(depositedToken == message.fromToken)` at deposit. Swap output validated against withdrawal token. Stateless relay holds no funds. Fields derived from on-chain state.

**106. First-Swap Extraction on Newly Created Pools**

- **D:** New pool with minimal liquidity — first significant swap is extremely fee-rich. Attacker front-runs by adding concentrated liquidity, captures outsized fees, removes. Extreme: initializes at skewed price, profits from arb correction.
- **FP:** Minimum locked seed liquidity (Uniswap V2 `MINIMUM_LIQUIDITY`). Fee ramp-up for new pools. Anti-sniping delay on creation.

**107. ERC1155 onERC1155Received Return Value Not Validated**

- **D:** Custom ERC1155 calls `onERC1155Received` but doesn't check returned `bytes4` equals `0xf23a6e61`. Non-compliant recipient silently accepts tokens it can't handle.
- **FP:** OZ ERC1155 base validates selector. Custom impl explicitly checks return value.

**108. Self-Delegation Doubles Voting Power**

- **D:** Self-delegation adds votes to delegate (self) without subtracting undelegated balance — power counted twice: held tokens + delegated votes.
- **FP:** Delegation subtracts from holder's direct balance. Self-delegation is no-op or explicitly handled. OZ Votes used.

**109. Expired Oracle Version Silently Assigned Previous Price**

- **D:** In request-commit oracle patterns (Pyth, keepers), expired/unfulfilled request assigned last valid price instead of reverting. Pending orders execute at stale prices.
- **FP:** Expired versions return `price = 0` or `valid = false`, forcing cancellation. Staleness threshold per-request. Fallback oracle.

**110. Non-Standard Approve Behavior (Zero-First / Max-Approval Revert)**

- **D:** (a) USDT-style: `approve()` reverts when changing from non-zero to non-zero allowance, requiring `approve(0)` first. (b) Some tokens (UNI, COMP) revert on `approve(type(uint256).max)`. Protocol calls `token.approve(spender, amount)` directly without these accommodations.
- **FP:** OZ `SafeERC20.forceApprove()` or `safeIncreaseAllowance()` used. Allowance always set from zero (fresh per-tx approval). Token whitelist excludes non-standard tokens.

**111. ERC4626 Round-Trip Profit Extraction**

- **D:** `redeem(deposit(a)) > a` or inverse — rounding errors in both `_convertToShares` and `_convertToAssets` favor the user, yielding net profit per round-trip.
- **FP:** Rounding per EIP-4626: deposit/mint round down (vault-favorable), withdraw/redeem round up (vault-favorable). OZ ERC4626 with `_decimalsOffset()`.

**112. Commit-Reveal Scheme Not Bound to msg.sender**

- **D:** Commitment hash does not include `msg.sender`: `commit = keccak256(abi.encodePacked(value, salt))`. Attacker copies a victim's commitment from the chain/mempool and submits their own reveal for the same hash from a different address. Affects auctions, governance votes, randomness.
- **FP:** Commitment includes sender: `keccak256(abi.encodePacked(msg.sender, value, salt))`. Reveal validates `msg.sender` matches stored committer.

**113. ERC4626 maxDeposit Returns Non-Zero When Paused**

- **D:** `maxDeposit()` returns `type(uint256).max` when paused. Integrators read "deposits accepted," attempt deposit, revert. Per ERC4626, must return 0 when deposits would revert.
- **FP:** `maxDeposit()` returns 0 when paused. Integrators use `try deposit()`.

**114. Permissionless accrueInterest Griefing**

- **D:** Permissionless `accrueInterest()` called at short intervals — each computes zero interest (rounding) but advances timestamp, systematically suppressing accumulation.
- **FP:** Minimum accrual interval enforced. Precision ensures per-block interest > 0. Access-restricted accrual.

**115. Proxy Admin Key Compromise**

- **D:** `ProxyAdmin.owner()` returns EOA, not multisig/governance; no timelock on `upgradeTo`.
- **FP:** Multisig (threshold >= 2) + timelock (24-72h). Admin role separate from operational roles.

**116. ERC4626 convertToAssets Used Instead of previewWithdraw**

- **D:** Integration calls `convertToAssets(shares)` to estimate withdrawal proceeds — excludes fees/slippage per spec. Downstream logic (health checks, rebalancing) operates on inflated values.
- **FP:** `previewWithdraw()`/`previewRedeem()` used for estimates. No withdrawal fees. Fee delta accounted separately.

**117. MEV Withdrawal Before Bad Debt Socialization**

- **D:** External event (liquidation, exploit, depeg) causes vault loss. MEV actor observes pending loss-causing tx in mempool and front-runs a withdrawal at pre-loss share price, leaving remaining depositors to absorb the full loss.
- **FP:** Withdrawals require time-delayed request queue (epoch-based or cooldown). Loss realization and share price update are atomic. Private mempool used for liquidation txs.

**118. EIP-7702 ERC-721/ERC-1155 Callback Revert on Delegated EOA**

- **D:** `safeTransferFrom` to delegated EOA triggers `onERC721Received`/`onERC1155Received` (recipient has code). If delegate doesn't implement callback, transfer reverts — breaks distribution loops and airdrops.
- **FP:** Uses `transferFrom` (no callback). Fallback path on callback failure. Skip-and-accrue pattern.

**119. State Record Overwrite Without Existence Check**

- **D:** Mapping entry (refund, withdrawal, order) written without checking if key occupied. Overwrites legitimate user's record — blocks claim, redirects funds, or poisons state. Pattern: `records[key] = newData` without `require(records[key].amount == 0)`.
- **FP:** Existence check before write. Nonce/hash-based keys prevent collision. Append-only structure. Old entry processed before overwrite.

**120. Empty Swap Path Bypasses Token Validation**

- **D:** Empty swap data/zero-length path returns input amount without swapping — and without validating input == output token. Attacker skips swap, receives output token from contract's balance. Pattern: `if (swapData.length == 0) return amount;` without `require(fromToken == toToken)`.
- **FP:** Empty path enforces `require(fromToken == toToken)`. Swap mandatory. Reverts on empty data. Post-swap balance delta check.

**121. Missing Slippage Protection (Sandwich Attack)**

- **D:** Swap/deposit/withdrawal with `minAmountOut = 0`, or `minAmountOut` computed on-chain from current pool state.
- **FP:** `minAmountOut` set off-chain by user and validated on-chain.

**122. Nested Mapping Inside Struct Not Cleared on `delete`**

- **D:** `delete myMapping[key]` on struct containing `mapping` or dynamic array. `delete` zeroes primitives but not nested mappings. Reused key exposes stale values.
- **FP:** Nested mapping manually cleared before `delete`. Key never reused after deletion.

**123. Assembly Delegatecall Missing Return/Revert Propagation**

- **D:** Proxy fallback written in assembly performs `delegatecall` but omits one or more required steps: (1) not copying full calldata via `calldatacopy`, (2) not copying return data via `returndatacopy(0, 0, returndatasize())`, (3) not branching on the result to `return(0, returndatasize())` on success or `revert(0, returndatasize())` on failure. Silent failures or swallowed reverts.
- **FP:** Complete proxy pattern: `calldatacopy(0, 0, calldatasize())` → `delegatecall(gas(), impl, 0, calldatasize(), 0, 0)` → `returndatacopy(0, 0, returndatasize())` → `switch result case 0 { revert(0, returndatasize()) } default { return(0, returndatasize()) }`. OZ Proxy.sol used.

**124. Batch Distribution Dust Residual**

- **D:** Loop distributes funds proportionally: `share = total * weight[i] / totalWeight`. Cumulative rounding causes `sum(shares) < total`, leaving dust locked in contract. Pattern: N recipients each computed independently without remainder handling.
- **FP:** Last recipient gets `total - sumOfPrevious`. Dust swept to treasury. `mulDiv` with accumulator tracking. Protocol accepts bounded dust loss by design.

**125. Lazy Epoch Advancement Skips Reward Periods**

- **D:** Epoch advances only on user interaction. No interaction = never advanced — rewards miscalculated or lost when next interaction retroactively applies to wrong epoch.
- **FP:** Keeper advances epochs independently. Catch-up loop processes skipped epochs. Continuous (non-epoch) reward accrual.

**126. Dutch Auction Price Decay Underflow**

- **D:** `currentPrice = startPrice - (decayRate * elapsed)`. Past zero-point: underflow reverts (0.8+) or wraps to `type(uint256).max` (<0.8). Auction unfinishable.
- **FP:** Floor price via `min()` or ternary at duration boundary. Reserve price enforced.

**127. ERC721Enumerable Index Corruption on Burn or Transfer**

- **D:** Override of `_beforeTokenTransfer` (OZ v4) or `_update` (OZ v5) without calling `super`. Index structures (`_ownedTokens`, `_allTokens`) become stale — `tokenOfOwnerByIndex` returns wrong IDs, `totalSupply` diverges.
- **FP:** Override always calls `super` as first statement. Contract doesn't inherit `ERC721Enumerable`.

**128. Dead Code After Return Statement**

- **D:** Critical state update or validation placed after `return` — unreachable. Failures undetected, events never emitted, state never updated.
- **FP:** All critical logic precedes `return`. Compiler unreachable-code warnings addressed.

**129. CREATE / CREATE2 Deployment Failure Silently Returns Zero**

- **D:** Assembly `create(v, offset, size)` or `create2(v, offset, size, salt)` returns `address(0)` on failure (insufficient balance, collision, init code revert) but the code does not check for zero. The zero address is stored or used, and subsequent calls to `address(0)` silently succeed as no-ops (no code) or interact with precompiles.
- **FP:** Immediate check: `if iszero(addr) { revert(0, 0) }` after create/create2. Address validated downstream before any state-dependent operation.

**130. Proxy Storage Slot Collision**

- **D:** Proxy stores `implementation`/`admin` at sequential slots (0, 1); implementation also declares variables from slot 0. Implementation writes overwrite proxy pointers.
- **FP:** EIP-1967 randomized slots used. OZ Transparent/UUPS pattern.

**131. Algorithmic Complexity Gas DoS**

- **D:** Nested loops, combinatorial matching, or recursive computation with superlinear gas cost (O(n²), O(2ⁿ)). At production scale, execution exceeds block gas limit, bricking the function.
- **FP:** O(n) or O(n log n) algorithm. Input capped (`require(n <= MAX)` gas-tested). Computation paginated/batched. Off-chain compute with on-chain verification.

**132. Emergency Mode State Machine Incompleteness**

- **D:** Emergency mode pauses operations but accrual continues (rewards, interest, fees). On exit, accumulated state not reconciled — stuck funds. Also: emergency withdrawal omits cleanup of associated records (staking, reward debt, queue), leaving orphaned state.
- **FP:** Emergency freezes all accrual. Exit reconciles before resuming. Emergency withdrawal atomically cleans associated records. Invariants re-validated on exit.

**133. Sentinel / Placeholder Address Operations**

- **D:** Code branches on sentinel (`address(0)`, `0xEeEe...`, `type(uint256).max`) for ETH/special cases. Special branch omits validations the normal branch performs. Also: ERC20 calls on sentinel — high-level reverts (no code), low-level succeeds silently.
- **FP:** Sentinel branch has equivalent validation. No ERC20 calls on sentinels. WETH wrapping instead of dual-path. Early detection routes to independent handler.

**134. Immutable / Constructor Argument Misconfiguration**

- **D:** Constructor sets `immutable` values (admin, fee, oracle, token) that can't change post-deploy. Multiple same-type `address` params where order can be silently swapped. No post-deploy verification.
- **FP:** Deployment script reads back and asserts every configured value. Constructor validates: `require(admin != address(0))`, `require(feeBps <= 10000)`.

**135. EIP-7702 Delegation Persists on Transaction Revert**

- **D:** Delegation designator is set BEFORE transaction execution. If tx body reverts, delegation is NOT rolled back — EOA permanently has new code despite reverted state changes.
- **FP:** Delegation requires EOA holder's explicit signature. Wallet UI shows active delegation status.

**136. Fee Accumulation Rounding Extraction via Large JIT Position**

- **D:** `feesPerLiquidity += (feeAmount << 128) / totalLiquidity`. Large JIT position inflates `totalLiquidity` — per-unit increment rounds to zero for existing LPs while JIT provider captures truncated amount.
- **FP:** Sufficient precision (Q128+) ensures rounding loss < 1 wei at realistic ratios. Protocol minimum fee increment.

**137. Flash Loan Governance Attack**

- **D:** Voting uses `token.balanceOf(msg.sender)` or `getPastVotes(account, block.number)` (current block). Borrow tokens, vote, repay in one tx.
- **FP:** `getPastVotes(account, block.number - 1)` used. Timelock between snapshot and vote.

**138. Off-By-One in Bounds or Range Checks**

- **D:** (1) `i <= arr.length` in loop (accesses OOB index). (2) `arr[arr.length - 1]` in `unchecked` without length > 0 check. (3) `>=` vs `>` confusion in financial logic (early unlock, boundary-exceeding deposit). (4) Integer division rounding accumulation across N recipients.
- **FP:** Loop uses `<` with fixed-length array. Last-element access preceded by length check. Financial boundaries demonstrably correct for the invariant.

**139. Open Interest Tracked with Pre-Fee Position Size**

- **D:** OI incremented by full position size before fee deduction. Actual exposure < recorded OI. Permanently inflated OI hits caps, blocking new positions.
- **FP:** OI incremented by post-fee size. OI decremented on close by same amount used at open.

**140. Admin Parameter Change During Active Multi-Step Operation**

- **D:** Multi-step operation (auction, epoch, bridge transfer, pending callback) spans multiple blocks. Admin setter takes effect mid-operation — later steps use new value, or dependency swap makes pending callback unfulfillable. Pattern: `setOracle(new)` while old oracle's callback pending.
- **FP:** Setter blocked while operation active. Operation snapshots config at start. Pending callbacks resolved before dependency swap. Changes queued for next boundary.

**141. Interest Accrual Rounds to Zero but Timestamp Advances**

- **D:** `interest = rate * timeDelta / SECONDS_PER_YEAR` rounds to zero for small `timeDelta`, but `lastAccrualTime` still advances — fractional interest permanently lost.
- **FP:** Accumulator uses sufficient precision (RAY = 1e27). `lastAccrualTime` only advances when interest > 0.

**142. Oracle Price Update Front-Running**

- **D:** On-chain oracle update tx visible in mempool. Attacker front-runs a favorable price update by opening a position at the stale price, then profits when the update lands. Pattern: Pyth/Chainlink push-model where update tx is submitted to public mempool.
- **FP:** Protocol uses pull-based oracle (user submits price update atomically with their action). Private mempool (Flashbots Protect) for oracle updates. Price-update-and-action in single tx.

**143. Insufficient Block Confirmations / Reorg Double-Spend**

- **D:** DVN relays cross-chain message before source chain reaches finality. Attacker deposits on source, gets minted on destination, then reorg on source reverses the deposit while keeping minted tokens. Pattern: confirmation count below chain's known reorg depth (e.g., < 32 blocks on Polygon).
- **FP:** Confirmation count matches or exceeds chain-specific finality guarantees. Chain has fast finality (e.g., Ethereum post-merge ~12 min). DVN waits for finalized blocks.

**144. Cross-Function Reentrancy**

- **D:** Two functions share state variable. Function A makes external call before updating shared state; Function B reads that state. `nonReentrant` on A but not B.
- **FP:** Both functions share same contract-level mutex. Shared state updated before any external call.

**145. Liquidation Blocked by External Pool Illiquidity**

- **D:** Liquidation swaps collateral for debt token via external DEX. Drained pool reverts swap, making liquidation impossible. Bad debt accumulates.
- **FP:** Liquidation accepts collateral directly. Fallback path uses different DEX. Liquidator provides debt token.

**146. Oracle Extractable Value (OEV) Liquidation Leakage**

- **D:** Liquidation callable by anyone with full `liquidationBonus` going to `msg.sender`. Oracle price update → MEV race to liquidate → value leaks from protocol to searchers with no recapture.
- **FP:** OEV-aware oracle (API3 OEV Network, Chainlink SVR). Liquidation bonus auctioned with proceeds to protocol. Dutch auction liquidation. Keeper priority window.

**147. ERC4626 Mint/Redeem Asset-Cost Asymmetry**

- **D:** `redeem(s)` returns more assets than `mint(s)` costs — cycling yields net profit. Root cause: `_convertToAssets` rounds up in `redeem` and down in `mint` (opposite of EIP-4626 spec). Pattern: `previewRedeem` uses `Rounding.Ceil`, `previewMint` uses `Rounding.Floor`.
- **FP:** `redeem` uses `Math.Rounding.Floor`, `mint` uses `Math.Rounding.Ceil`. OZ ERC4626 without custom conversion overrides.

**148. Delegate Privilege Escalation**

- **D:** `setDelegate()` appoints an address that can manage OApp configurations including DVNs, Executors, message libraries, and can skip/clear payloads. If delegate is set to an insecure address (EOA, unrelated contract) or differs from owner without governance controls, the delegate can silently reconfigure the OApp's entire security stack.
- **FP:** Delegate == owner. Delegate is a governance timelock or multisig. `setDelegate` protected by the same access controls as `setPeer`.

**149. DoS via Reverting External Call in Loop**

- **D:** Distribution/claim loops over dynamic list with external call per iteration. Any single revert (paused token, blacklisted recipient, illiquid pool) blocks entire function for all users.
- **FP:** `try/catch` per iteration (skip on failure). Separate per-item withdrawal. Admin can remove problematic entries.

**150. Cross-Chain Supply Accounting Invariant Violation**

- **D:** The fundamental invariant `total_locked_source >= total_minted_destination` is violated. Can occur through: decimal conversion errors between chains, `_credit` callable without corresponding `_debit`, race conditions in multi-chain deployments, or any bug that allows minting without locking. Minted tokens become partially or fully unbacked.
- **FP:** Invariant verified via monitoring/alerting. `_credit` only callable from verified `lzReceive` path. Decimal conversion tested across all supported chains. Rate limits cap maximum exposure per time window.

**151. No-Bid Auction Fails to Clear State**

- **D:** Auction expires with no bids but finalization doesn't clear lien/escrow data — collateral locked with no return path or re-auction mechanism.
- **FP:** No-bid finalization returns collateral and clears state. Auto re-auction. Timeout-based release.

**152. Non-Atomic Proxy Initialization (Front-Running `initialize()`)**

- **D:** Proxy deployed in one tx, `initialize()` called in separate tx. Uninitialized proxy front-runnable. Pattern: `new TransparentUpgradeableProxy(impl, admin, "")` with empty data, separate `initialize()`.
- **FP:** Proxy constructor receives init calldata atomically: `new TransparentUpgradeableProxy(impl, admin, abi.encodeCall(...))`. OZ `deployProxy()` used.

**153. Hardcoded Network-Specific Addresses**

- **D:** Literal `address(0x...)` constants for external dependencies (oracles, routers, tokens) in deployment scripts/constructors. Wrong contracts on different chains.
- **FP:** Per-chain config file keyed by chain ID. Script asserts `block.chainid`. Addresses passed as constructor args from environment. Deterministic cross-chain addresses (e.g., Permit2).

**154. ERC-1271 isValidSignature Delegated to Untrusted Module**

- **D:** `isValidSignature(hash, sig)` delegated to externally-supplied contract without whitelist check. Malicious module always returns `0x1626ba7e`, passing all signature checks.
- **FP:** Delegation only to owner-controlled whitelist. Module registry has timelock/guardian approval.

**155. notifyRewardAmount Overwrites Active Reward Period**

- **D:** `notifyRewardAmount(newAmount)` replaces current period — undistributed rewards silently lost, not carried forward.
- **FP:** New notification adds remaining: `rewardRate = (newAmount + remaining) / duration`. Only callable by designated distributor with timelock.

**156. validateUserOp Missing EntryPoint Caller Restriction**

- **D:** `validateUserOp` is `public`/`external` without `require(msg.sender == entryPoint)`. Also check `execute`/`executeBatch` for same restriction.
- **FP:** `require(msg.sender == address(_entryPoint))` or `onlyEntryPoint` modifier present. Internal visibility used.

**157. Transparent Proxy Admin Routing Confusion**

- **D:** Admin address also used for regular protocol interactions. Calls from admin route to proxy admin functions instead of delegating — silently failing or executing unintended logic.
- **FP:** Dedicated `ProxyAdmin` contract used exclusively for admin calls. OZ `TransparentUpgradeableProxy` enforces separate admin.

**158. Intent Solver Collusion / Suboptimal Execution**

- **D:** Intent-based protocol with no on-chain execution quality enforcement. Colluding solvers provide suboptimal fills and split extracted value. Pattern: `fillOrder(order, solverParams)` with no price benchmark.
- **FP:** On-chain oracle comparison with max deviation. User `minOutput` enforced on-chain. Solver bond slashed for suboptimal execution.

**159. Pause Modifier Blocks Liquidations**

- **D:** `whenNotPaused` applied to all external functions including `liquidate()`. During pause, interest accrues and prices move but positions can't be liquidated — bad debt accumulates.
- **FP:** Liquidation exempt from pause. Separate `pauseLiquidations` flag. Interest accrual also paused.

**160. EIP-2981 Royalty Signaled But Never Enforced**

- **D:** `royaltyInfo()` implemented and `supportsInterface(0x2a55205a)` returns true, but transfer/settlement logic never calls `royaltyInfo()` or routes payment. EIP-2981 is advisory only.
- **FP:** Settlement contract reads `royaltyInfo()` and transfers royalty on-chain. Royalties intentionally zero and documented.

**161. Assembly Arithmetic Silent Overflow and Division-by-Zero**

- **D:** Arithmetic inside `assembly {}` (Yul) does not revert on overflow/underflow (wraps like `unchecked`) and division by zero returns 0 instead of reverting. Developers accustomed to Solidity 0.8 checked math may not expect this.
- **FP:** Manual overflow checks in assembly (`if gt(result, x) { revert(...) }`). Denominator checked before `div`. Assembly block is read-only (`mload`/`sload` only, no arithmetic).

**162. Zero-Amount Transfer Revert**

- **D:** `token.transfer(to, amount)` where `amount` can be zero (rounded fee, unclaimed yield). Some tokens (LEND, early BNB) revert on zero-amount transfers, DoS-ing distribution loops.
- **FP:** `if (amount > 0)` guard before all transfers. Minimum claim amount enforced. Token whitelist verified to accept zero transfers.

**163. Blacklist and Whitelist Not Mutually Exclusive**

- **D:** Address holds both `BLACKLISTED` and `WHITELISTED` roles. Whitelist-gated paths don't check blacklist — blacklisted address bypasses restrictions via whitelist.
- **FP:** Adding to one auto-removes from other. Single enum role per address. Both checks applied on every restricted path.

**164. extcodesize Zero in Constructor / Non-Zero on Delegated EOA**

- **D:** `require(msg.sender.code.length == 0)` as EOA check. Two bypasses: (1) contract constructor has `extcodesize == 0`, passing the check; (2) post-Pectra, EIP-7702 delegated EOA has 23-byte `0xef0100` stub, failing the check — blocks legitimate delegated EOAs or routes them to wrong code path.
- **FP:** Check is non-security-critical. Function protected by merkle proof, signed permit, or other mechanism independent of account type.

**165. Missing Chain ID Validation in Deployment Configuration**

- **D:** Deploy script reads `$RPC_URL` from `.env` without `eth_chainId` assertion. Foundry script without `--chain-id` flag or `block.chainid` check. No dry-run before broadcast.
- **FP:** `require(block.chainid == expectedChainId)` at script start. CI validates chain ID before deployment.

**166. Capacity Competition Between Accounting Variables**

- **D:** Multiple accounting variables (user shares, fee shares, rewards) share a common cap. One can fill the cap, making another permanently unfulfillable. Pattern: `maxDeposit = supplyCap - totalSupply` ignores pending fee shares — deposits fill cap, fees can never mint.
- **FP:** `maxDeposit` accounts for all future obligations. Fee shares minted eagerly. Separate caps for user/protocol shares.

**167. Accrued Interest Omitted from Health Factor or LTV Calculation**

- **D:** Health factor or LTV computed from principal debt without adding accrued interest: `health = collateral / principal` instead of `collateral / (principal + accruedInterest)`. Understates actual debt, delays necessary liquidations.
- **FP:** `getDebt()` includes accrued interest. Interest accrual function called before health check. Interest compounded on every state-changing interaction.

**168. Storage Layout Shift on Upgrade**

- **D:** V2 inserts new state variable in middle of contract instead of appending. Subsequent variables shift slots, corrupting state. Also: changing variable type between versions shifts slot boundaries.
- **FP:** New variables only appended. OZ storage layout validation in CI. Variable types unchanged between versions.

**169. Fee-on-Transfer Token Accounting**

- **D:** Deposit records `deposits[user] += amount` then `transferFrom(..., amount)`. Fee-on-transfer tokens cause contract to receive less than recorded.
- **FP:** Balance measured before/after: `uint256 before = token.balanceOf(this); transferFrom(...); received = balanceOf(this) - before;` and `received` used for accounting.

**170. Bridge Global Rate Limit Griefing**

- **D:** Bridge enforces global throughput cap not segmented by user. Attacker fills limit bridging cheap tokens back and forth, blocking all legitimate users during cooldown.
- **FP:** Per-user rate limits. Segmented by token/route. Whitelist for high-value transfers.

**171. Minimal Proxy (EIP-1167) Implementation Destruction**

- **D:** EIP-1167 clones `delegatecall` a fixed implementation. If implementation is destroyed, all clones become no-ops with locked funds. Pattern: `Clones.clone(impl)` where impl has no `selfdestruct` protection or is uninitialized.
- **FP:** No `selfdestruct` in implementation. `_disableInitializers()` in constructor. Post-Dencun: code not destroyed. Beacon proxies used for upgradeability.

**172. Position Reduction Triggers Liquidation**

- **D:** Partial repay/withdrawal creates intermediate state below liquidation threshold — bot liquidates before atomic completion. Health check applied to intermediate, not final state.
- **FP:** Repay and collateral changes atomic. Health check on final state only. Grace period after modification.

**173. ERC4626 Deposit/Withdraw Share-Count Asymmetry**

- **D:** `_convertToShares` uses `Rounding.Floor` for both deposit and withdraw paths. `withdraw(a)` burns fewer shares than `deposit(a)` minted, manufacturing free shares. Single rounding helper called on both paths without distinct rounding args.
- **FP:** `deposit` uses `Floor`, `withdraw` uses `Ceil` (vault-favorable both directions). OZ ERC4626 without custom conversion overrides.

**174. Missing Oracle Price Bounds (Flash Crash / Extreme Value)**

- **D:** Oracle returns a technically valid but extreme price (e.g., ETH at $0.01 during a flash crash). No min/max sanity bound or deviation check against historical/secondary price. Protocol executes liquidations or swaps at wildly incorrect prices.
- **FP:** Circuit breaker: `require(price >= MIN_PRICE && price <= MAX_PRICE)`. Deviation check against secondary oracle source. Heartbeat + price-change-rate limiting.

**175. Function Selector Clashing (Proxy Backdoor)**

- **D:** Proxy contains a function whose 4-byte selector collides with an implementation function. User calls route to proxy logic instead of delegating.
- **FP:** Transparent proxy pattern separates admin/user routing. UUPS proxy has no custom functions — all calls delegate.

**176. Checkpoint Overwrite on Same-Block Operations**

- **D:** Multiple delegate/transfer operations in same block overwrite `_writeCheckpoint()` at same key — binary search returns incomplete checkpoint, losing intermediate state.
- **FP:** Same-block operations accumulate into existing checkpoint. Off-chain indexer used.

**177. Default Message Library Hijack (Configuration Drag-Along)**

- **D:** OApp does not explicitly pin its send/receive library version via `setSendVersion()` / `setReceiveVersion()` (or V2 `setSendLibrary()` / `setReceiveLibrary()`). It relies on the endpoint's mutable default. A malicious or compromised default library update silently applies to all unpinned OApps, bypassing DVN/Oracle validation.
- **FP:** OApp explicitly sets library versions in constructor or initialization. Configuration is immutable or governance-controlled with timelock. LayerZero V2 EndpointV2 is non-upgradeable (but library defaults are still mutable).

**178. Immutable Variable Context Mismatch**

- **D:** Implementation uses `immutable` variables (embedded in bytecode, not storage). Proxy `delegatecall` gets implementation's hardcoded values regardless of per-proxy needs. E.g., `immutable WETH` — every proxy gets same address.
- **FP:** Immutable values intentionally identical across all proxies. Per-proxy config uses storage via `initialize()`.

**179. Calldata Input Malleability**

- **D:** Contract hashes raw calldata for uniqueness (`processedHashes[keccak256(msg.data)]`). Dynamic-type ABI encoding uses offset pointers — multiple distinct calldata layouts decode to identical values. Attacker bypasses dedup with semantically equivalent but bytewise-different calldata.
- **FP:** Uniqueness check hashes decoded parameters: `keccak256(abi.encode(decodedParams))`. Nonce-based replay protection. Only fixed-size types in signature (no encoding ambiguity).

**180. On-Chain Slippage Computed from Manipulated Pool**

- **D:** `amountOutMin` calculated on-chain from the same pool executing the swap. Attacker manipulates pool first — quote and swap both reflect manipulated state, slippage check passes despite sandwich.
- **FP:** `amountOutMin` supplied by caller (off-chain quote). Separate oracle for floor price. TWAP-based minimum.

**181. Hardcoded Zero Slippage in Internal Swaps**

- **D:** Internal swap calls (auto-compound, liquidation, fee conversion) set `amountOutMinimum = 0` or omit slippage. Freely sandwichable. Pattern: `exactInputSingle(params)` where `params.amountOutMinimum = 0`.
- **FP:** `amountOutMin` from oracle with bounded tolerance. User-supplied slippage propagated. Private mempool for protocol swaps.

**182. Nonce Gap from Reverted Transactions (CREATE Address Mismatch)**

- **D:** Deployment script uses `CREATE` and pre-computes addresses from deployer nonce. Reverted/extra tx advances nonce — subsequent deployments land at wrong addresses. Pre-configured references point to empty/wrong contracts.
- **FP:** `CREATE2` used (nonce-independent). Script reads nonce from chain before computing. Addresses captured from deployment receipts, not pre-assumed.

**183. Unclaimed Reward Tokens from Underlying Protocol**

- **D:** Vault deposits into yield protocol (Morpho, Aave, Convex) that emits reward tokens but never calls `claim()`. Rewards accumulate inaccessibly in vault or underlying.
- **FP:** Explicit `claimRewards()` harvests and distributes. Reward tokens tracked dynamically. Vault sweeps unexpected balances to treasury.

**184. ERC4626 Preview Rounding Direction Violation**

- **D:** `previewDeposit` returns more shares than `deposit` mints, or `previewMint` charges fewer assets than `mint`. Custom `_convertToShares`/`_convertToAssets` with wrong `Math.mulDiv` rounding direction.
- **FP:** OZ ERC4626 base without overriding conversion functions. Custom impl explicitly uses `Floor` for share issuance, `Ceil` for share burning.

**185. Missing or Expired Deadline on Swaps**

- **D:** `deadline = block.timestamp` (always valid), `deadline = type(uint256).max`, or no deadline. Tx holdable in mempool indefinitely.
- **FP:** Deadline is calldata parameter validated as `require(deadline >= block.timestamp)`, not derived from `block.timestamp` internally.

**186. Calldataload / Calldatacopy Out-of-Bounds Read**

- **D:** `calldataload(offset)` where `offset` is user-controlled or exceeds actual calldata length. Reading past `calldatasize()` returns zero-padded bytes silently (no revert), producing phantom zero values that pass downstream logic as valid inputs. Pattern: `calldataload(add(4, mul(index, 32)))` without `require(index < paramCount)`.
- **FP:** `calldatasize()` validated before assembly block (e.g., Solidity ABI decoder already checked). Static offsets into known fixed-length function signatures. Explicit `if lt(calldatasize(), minExpected) { revert(0,0) }` guard.

**187. State-Time Lag Exploitation (lzRead Stale State)**

- **D:** `lzRead` queries state on a remote chain, but there is a latency window between query and delivery of the result via `lzReceive`. During this window, the queried state may change (token transferred, position closed, price moved). Protocol makes irreversible decisions based on the stale read result.
- **FP:** Read targets immutable or slowly-changing state (contract code, historical data). Read result treated as a hint with on-chain re-validation. Time-sensitive operations require fresh on-chain state, not cross-chain reads.

**188. Transient Storage Low-Gas Reentrancy (EIP-1153)**

- **D:** Contract uses `transfer()`/`send()` (2300-gas) as reentrancy guard + uses `TSTORE`/`TLOAD`. Post-Cancun, `TSTORE` succeeds under 2300 gas unlike `SSTORE`. Second pattern: transient reentrancy lock not cleared at call end — persists for entire tx, causing DoS via multicall/flash loan callback.
- **FP:** `nonReentrant` backed by regular storage slot (or transient mutex properly cleared). CEI followed unconditionally.

**189. ERC4626 Inflation Attack (First Depositor)**

- **D:** `shares = assets * totalSupply / totalAssets`. When `totalSupply == 0`, deposit 1 wei + donate inflates share price, victim's deposit rounds to 0 shares. No virtual offset.
- **FP:** OZ ERC4626 with `_decimalsOffset()`. Dead shares minted to `address(0)` at init.

**190. Arbitrary External Call with User-Supplied Target and Calldata**

- **D:** `target.call{value: v}(data)` where `target` or `data` (or both) are caller-supplied parameters. Attacker crafts calldata to invoke unintended functions on the target (e.g., `transferFrom` on an approved ERC20, or `safeTransferFrom` on held NFTs), stealing assets the contract holds or has approvals for.
- **FP:** Target restricted to hardcoded/whitelisted address. Calldata function selector restricted to known-safe set. No token approvals or asset holdings on the calling contract. this covers `call` only, not `delegatecall`.

**191. msg.value vs Computed Amount Mismatch**

- **D:** Payable function computes `netAmount` after fees but forwards full `msg.value` downstream. Or trusts user-supplied `amount` without `require(msg.value == amount)`.
- **FP:** `require(msg.value == expectedAmount)` at entry. Fee-adjusted amount used consistently. Excess refunded.

**192. ERC4626 maxDeposit vs Actual Deposit Method Mismatch**

- **D:** Vault queries `maxDeposit()` but deposits via `mint()` (or vice versa). Per ERC4626, `maxDeposit` governs `deposit()` and `maxMint` governs `mint()` — limits may differ. Same for withdrawal: `convertToAssets(maxRedeem(...))` instead of `maxWithdraw(...)` overstates amount (excludes fees/slippage).
- **FP:** Method-matched queries (`maxMint` for `mint`, `maxDeposit` for `deposit`). `previewWithdraw`/`previewRedeem` for estimates. Underlying `max*` verified consistent.

**193. Function Selector Clash in Proxy**

- **D:** Proxy and implementation share a 4-byte selector collision. Call intended for implementation routes to proxy's function (or vice versa).
- **FP:** Transparent proxy pattern (admin/user call routing separates namespaces). UUPS with no custom proxy functions — all calls delegate unconditionally.

**194. Loss-Versus-Rebalancing (LVR) in Constant-Function AMMs**

- **D:** AMM with constant-function pricing and static fees. Searchers continuously arbitrage stale pool price against external markets, extracting from LPs on every price movement. Concentrated liquidity amplifies extraction.
- **FP:** Dynamic fee adjusting for volatility (Uniswap V4 hooks). MEV-aware design (batch auctions, CoW AMM). Fee tier covers expected LVR for pair volatility.

**195. Delegation to address(0) Blocks Token Transfers**

- **D:** Delegating to `address(0)` causes `_update` hooks to revert modifying zero-address checkpoint. All transfers/burns for that holder permanently revert.
- **FP:** Delegation to `address(0)` treated as undelegation. Hook skips checkpoint when delegate is zero. OZ Votes handles this.

**196. tx.origin Authentication**

- **D:** `require(tx.origin == owner)` used for auth. Phishable via intermediary contract.
- **FP:** `tx.origin == msg.sender` used only as anti-contract check, not auth.

**197. Scratch Space Corruption Across Assembly Blocks**

- **D:** Data written to scratch space (`0x00`–`0x3f`) in one assembly block is expected to persist and be read in a later assembly block, but intervening Solidity code (or compiler-generated code for `keccak256`, `abi.encode`, etc.) overwrites scratch space between the two blocks. Pattern: `mstore(0x00, key); mstore(0x20, slot)` in block A, then `keccak256(0x00, 0x40)` in block B with Solidity statements between them.
- **FP:** All scratch space reads occur within the same contiguous assembly block as the writes. Developer explicitly rewrites scratch space before each use. No intervening Solidity code between blocks.

**198. FIFO Withdrawal Ordering Degrades Yield**

- **D:** Aggregator vault withdraws from sub-vaults in fixed FIFO order, depleting highest-APY vaults first. Remaining capital concentrates in lowest-yield positions, reducing overall returns for all depositors.
- **FP:** Withdrawal ordering sorted by APY ascending (lowest-yield first). Dynamic rebalancing after withdrawals. Single underlying vault (no ordering issue).

**199. Repeated Liquidation of Same Position**

- **D:** Liquidation doesn't flag position as processed. After partial liquidation, position still appears undercollateralized — second liquidator seizes collateral beyond intent.
- **FP:** Position marked `liquidated` or deleted. `require(status != Liquidated)`. Post-liquidation health check.

**200. ERC1155 uri() Missing {id} Substitution**

- **D:** `uri(uint256 id)` returns fully resolved URL instead of template with literal `{id}` placeholder per EIP-1155. Clients expect to substitute zero-padded hex ID client-side. Static/empty return collapses all token metadata.
- **FP:** Returns string containing literal `{id}`. Or per-ID on-chain URI with documented deviation from substitution spec.

**201. Emission Distribution Before Period Update**

- **D:** `distribute()` reads token balance before `updatePeriod()` mints new emissions. Rewards arrive after distribution — idle until next cycle, underpaying current period.
- **FP:** `updatePeriod()` called before `distribute()`. Emissions pre-funded before distribution window.

**202. Single-Function Reentrancy**

- **D:** External call (`call{value:}`, `safeTransfer`, etc.) before state update — check-external-effect instead of check-effect-external (CEI).
- **FP:** State updated before call (CEI followed). `nonReentrant` modifier. Callee is hardcoded immutable with known-safe receive/fallback.

**203. Stale Cached ERC20 Balance from Direct Token Transfers**

- **D:** Contract tracks holdings in state variable (`totalDeposited`, `_reserves`) updated only through protocol functions. Direct `token.transfer(contract)` inflates real balance beyond cached value. Attacker exploits gap for share pricing/collateral manipulation.
- **FP:** Accounting reads `balanceOf(this)` live. Cached value reconciled at start of every state-changing function. Direct transfers treated as revenue.

**204. Duplicate Items in User-Supplied Array**

- **D:** Function accepts array parameter (e.g., `claimRewards(uint256[] calldata tokenIds)`) without checking for duplicates. User passes same ID multiple times, claiming rewards/voting/withdrawing repeatedly in one call.
- **FP:** Duplicate check via mapping (`require(!seen[id]); seen[id] = true`). Sorted-unique input enforced (`require(ids[i] > ids[i-1])`). State zeroed on first claim (second iteration reverts naturally).

**205. Counterfactual Wallet Initialization Parameters Not Bound to Deployed Address**

- **D:** Factory `createAccount` uses CREATE2 but salt doesn't incorporate all init params (especially owner). Attacker calls `createAccount` with different owner, deploying wallet they control to same counterfactual address.
- **FP:** Salt derived from all init params: `salt = keccak256(abi.encodePacked(owner, ...))`. Factory reverts if account exists. Initializer called atomically with deployment.

**206. Metamorphic Contract via CREATE2 + SELFDESTRUCT**

- **D:** `CREATE2` deployment where deployer can `selfdestruct` and redeploy different bytecode at same address. Governance-approved code swapped before execution.. Post-Dencun (EIP-6780): largely mitigated except same-tx create-destroy-recreate.
- **FP:** Post-Dencun: `selfdestruct` no longer destroys code unless same tx as creation. `EXTCODEHASH` verified at execution time. Not deployed via `CREATE2` from mutable deployer.

**207. ERC20 Non-Compliant: Return Values / Events**

- **D:** Custom `transfer()`/`transferFrom()` doesn't return `bool` or always returns `true` on failure. `mint()`/`burn()` missing `Transfer` events. `approve()` missing `Approval` event.
- **FP:** OZ `ERC20.sol` base with no custom overrides of transfer/approve/event logic.

**208. Insufficient Gas Forwarding / 63/64 Rule**

- **D:** External call without minimum gas budget: `target.call(data)` with no gas check. 63/64 rule leaves subcall with insufficient gas. In relayer patterns, subcall silently fails but outer tx marks request as "processed."
- **FP:** `require(gasleft() >= minGas)` before subcall. Return value + returndata both checked. EIP-2771 with verified gas parameter.

**209. Blacklistable or Pausable Token in Critical Payment Path**

- **D:** Push-model transfer `token.transfer(recipient, amount)` with USDC/USDT or other blacklistable token. Blacklisted recipient reverts entire function, DOSing withdrawals/liquidations/fees.
- **FP:** Pull-over-push pattern (recipients withdraw own funds). Skip-on-failure `try/catch` on fee distribution. Token whitelist excludes blacklistable tokens.

**210. Deployer Privilege Retention Post-Deployment**

- **D:** Deployer EOA retains owner/admin/minter/pauser/upgrader after deployment script completes. Pattern: `Ownable` sets `owner = msg.sender` with no `transferOwnership()`. `AccessControl` grants `DEFAULT_ADMIN_ROLE` to deployer with no `renounceRole()`.
- **FP:** Script includes `transferOwnership(multisig)`. Admin role granted to timelock/governance, deployer renounces. `Ownable2Step` with pending owner set to multisig.

**211. mstore8 Partial Write Leaving Dirty Bytes**

- **D:** `mstore8` writes a single byte at a memory offset, but subsequent `mload` reads the full 32-byte word containing that byte. The remaining 31 bytes retain prior memory contents (potentially uninitialized or stale data). Pattern: building a byte array with `mstore8` in a loop, then hashing or returning the full memory region — dirty bytes corrupt the result.
- **FP:** Full word zeroed with `mstore(ptr, 0)` before byte-level writes. `mload` result masked to extract only the written bytes. `mstore` used instead of `mstore8` with proper shifting.

**212. DVN Collusion or Insufficient DVN Diversity**

- **D:** OApp configured with a single DVN (`1/1/1` security stack) or multiple DVNs controlled by the same entity / using the same underlying verification method. Compromising one entity approves fraudulent cross-chain messages. Pattern: `setConfig` with `requiredDVNCount = 1` and no optional DVNs.
- **FP:** Diverse DVN set (e.g., Google Cloud DVN + Axelar Adapter + protocol's own DVN) with `2/3+` threshold. DVNs use independent verification methods (light client, oracle, ZKP). Protocol runs its own required DVN.

**213. Paymaster ERC-20 Payment Deferred to postOp Without Pre-Validation**

- **D:** `validatePaymasterUserOp` doesn't transfer/lock tokens — payment deferred to `postOp` via `safeTransferFrom`. User can revoke allowance between validation and execution; paymaster loses deposit.
- **FP:** Tokens transferred/locked during `validatePaymasterUserOp`. `postOp` only refunds excess.

**214. Same-Block Vote-Transfer-Vote**

- **D:** Governance reads voting power at current block. User votes, transfers tokens to second wallet, votes again — doubling effective weight in same block.
- **FP:** `getPastVotes(block.number - 1)` or proposal-creation snapshot. Voting power locked on first vote. ERC20Votes with checkpoints.

**215. Depeg of Pegged or Wrapped Asset Breaking Protocol Assumptions**

- **D:** Protocol assumes 1:1 peg between assets (stETH:ETH, WBTC:BTC, USDC:USD) in pricing, collateral valuation, or swap routing. No depeg tolerance or independent oracle for the derivative. During depeg, collateral is overvalued, enabling undercollateralized borrows or incorrect swaps.
- **FP:** Independent price feed per asset (not assumed 1:1). Configurable depeg threshold triggering protective measures (pause, adjusted LTV). Protocol documentation explicitly acknowledges and accepts depeg risk.

**216. Pending Async Callback with Dependency Swap**

- **D:** Contract requests async operation (randomness, oracle, cross-chain message) fulfilled via callback. Dependency swapped before callback arrives — new provider can't fulfill old request, old rejected as unregistered. Request stuck permanently. Pattern: `setProvider(new)` while `pendingRequestId != 0`.
- **FP:** Swap blocked while requests pending. Callback validates request ID, not sender. Transition fulfills/cancels pending before registering new provider. Timeout for stuck requests.

**217. Missing `enforcedOptions` — Insufficient Gas for lzReceive**

- **D:** OApp does not call `setEnforcedOptions()` to mandate minimum gas for destination execution. User-supplied `_options` can specify insufficient gas, causing `lzReceive` to revert on destination. Funds debited on source but not credited on destination — stuck in limbo until manual recovery via `lzComposeAlert` or `skipPayload`.
- **FP:** `enforcedOptions` configured with tested gas limits for each message type. `lzReceive` logic is simple (single mapping update) requiring minimal gas. Executor provides guaranteed minimum gas.

**218. Uniswap V4 Hook Access Control and State Manipulation**

- **D:** Hook callback (`beforeSwap`, `afterSwap`) missing `require(msg.sender == address(poolManager))`. Attacker calls hook directly. Second pattern: hook uses `balanceOf(address(this))` — donatable.
- **FP:** All hooks restricted to PoolManager caller. Internal accounting (not `balanceOf`). No custom token accounting in hooks.

**219. Chainlink Feed Deprecation / Wrong Decimal Assumption**

- **D:** (a) Chainlink aggregator address hardcoded/immutable with no update path — deprecated feed returns stale/zero price. (b) Assumes `feed.decimals() == 8` without runtime check — some feeds return 18 decimals, causing 10^10 scaling error.
- **FP:** Feed address updatable via governance. `feed.decimals()` called and used for normalization. Secondary oracle deviation check.

**220. EIP-7702 tx.origin == msg.sender Bypass**

- **D:** `require(tx.origin == msg.sender)` as EOA gate or reentrancy guard. Delegated EOA passes check while executing arbitrary contract logic — enables flash loans, atomic governance manipulation, and reentrancy through "EOA-only" functions.
- **FP:** Additional `require(msg.sender.code.length == 0)` check (delegated EOAs have 23-byte `0xef0100` stub). Function protected by time-lock, multi-sig, or past-block snapshot.

**221. Deployment Transaction Front-Running (Ownership Hijack)**

- **D:** Deployment tx sent to public mempool without private relay. Attacker extracts bytecode and deploys first (or front-runs initialization). Pattern: `eth_sendRawTransaction` via public RPC, constructor sets `owner = msg.sender`.
- **FP:** Private relay used (Flashbots Protect, MEV Blocker). Owner passed as constructor arg, not `msg.sender`. Chain without public mempool. CREATE2 salt tied to deployer.

**222. ecrecover Returns address(0) on Invalid Signature**

- **D:** Raw `ecrecover` without `require(recovered != address(0))`. If `authorizedSigner` is uninitialized or `permissions[address(0)]` is non-zero, garbage signature gains privileges.
- **FP:** OZ `ECDSA.recover()` used (reverts on address(0)). Explicit zero-address check present.

**223. Non-Atomic Multi-Contract Deployment (Partial System Bootstrap)**

- **D:** Deployment script deploys interdependent contracts across separate transactions. Midway failure leaves half-deployed state with missing references or unwired contracts. Pattern: multiple `vm.broadcast()` blocks or sequential `await deploy()` with no idempotency checks.
- **FP:** Single `vm.startBroadcast()`/`vm.stopBroadcast()` block. Factory deploys+wires all in one tx. Script is idempotent. Hardhat-deploy with resumable migrations.

**224. Precision Loss - Division Before Multiplication**

- **D:** `(a / b) * c` — truncation before multiplication amplifies error. E.g., `fee = (amount / 10000) * bps`. Correct: `(a * c) / b`.
- **FP:** `a` provably divisible by `b` (enforced by `require(a % b == 0)` or mathematical construction).

**225. CREATE2 Address Squatting (Counterfactual Front-Running)**

- **D:** CREATE2 salt not bound to `msg.sender`. Attacker precomputes address and deploys first. For AA wallets: attacker deploys wallet to user's counterfactual address with attacker as owner.
- **FP:** Salt incorporates `msg.sender`: `keccak256(abi.encodePacked(msg.sender, userSalt))`. Factory restricts deployer. Different owner in constructor produces different address.

**226. Write to Arbitrary Storage Location**

- **D:** (1) `sstore(slot, value)` where `slot` derived from user input without bounds. (2) Solidity <0.6: direct `arr.length` assignment + indexed write at crafted large index wraps slot arithmetic.
- **FP:** Assembly is read-only (`sload` only). Slot is compile-time constant or non-user-controlled. Solidity >= 0.6 used.

**227. Withdrawal Rate Limit Bypassed via Share Transfer**

- **D:** Per-address withdrawal limit bypassed by transferring shares to fresh addresses — each gets a fresh limit.
- **FP:** Limit tracks underlying position, not address. Shares non-transferable or transfer resets allowance.

**228. Generalized Frontrunner on Permissionless Value Functions**

- **D:** Value-extracting function (liquidation, reward claim) pays `msg.sender` with no access control, auction, or commit-reveal. Searcher always captures by frontrunning. Pattern: `token.transfer(msg.sender, bonus)` in permissionless external function.
- **FP:** Keeper priority window. Dutch auction. Commit-reveal with caller binding. Value returned to protocol/affected user.

**229. Ordered Message Channel Blocking (Nonce DoS)**

- **D:** OApp uses ordered nonce execution. If one message permanently reverts on destination (e.g., recipient contract reverts, invalid state), ALL subsequent messages from that source are blocked.
- **FP:** Unordered nonce mode used (LayerZero V2 default). `_lzReceive` wrapped in try/catch with fallback logic. `NonblockingLzApp` pattern (V1). Admin can `skipPayload` / `clearPayload` to unblock.

**230. require(token.transfer()) Reverts on Void-Return Tokens**

- **D:** `require(IERC20(token).transfer(to, amount))` expects `bool` return. USDT returns void — ABI decoder reverts even on successful transfer. Pattern: `require(token.transfer(...))` instead of `token.safeTransfer(...)`.
- **FP:** SafeERC20 `safeTransfer`/`safeTransferFrom` used throughout. Only bool-returning tokens accepted.

**231. Insufficient Return Data Length Validation**

- **D:** Assembly `staticcall`/`call` writes return data into a fixed-size buffer (e.g., `staticcall(gas(), token, ptr, 4, ptr, 32)`) then reads `mload(ptr)` without checking `returndatasize() >= 32`. If the target is an EOA (no code, zero return data) or a non-compliant contract returning fewer bytes, `mload` reads stale memory at `ptr`, which may decode as a truthy value — silently treating a failed/absent call as success.
- **FP:** `if lt(returndatasize(), 32) { revert(0,0) }` checked before reading return data. `extcodesize(target)` verified > 0 before call. Safe ERC20 pattern that handles both zero-length and 32-byte returns.

**232. UUPS `_authorizeUpgrade` Missing Access Control**

- **D:** `function _authorizeUpgrade(address) internal override {}` with empty body and no access modifier. Anyone can call `upgradeTo()`.
- **FP:** `_authorizeUpgrade()` has `onlyOwner` or equivalent. Multisig/governance controls owner role.

**233. Liquidated Position Continues Accruing Rewards**

- **D:** Position liquidated (balance zeroed) but not removed from reward distribution. `rewardDebt` not reset — phantom rewards accrue or are locked permanently.
- **FP:** Liquidation calls `_withdrawRewards()` before zeroing. Reward system checks `balance > 0` before accruing.

**234. Self-Liquidation Profit Extraction**

- **D:** Borrower liquidates their own undercollateralized position from a second address, collecting the liquidation bonus/discount on their own collateral. Profitable whenever liquidation incentive exceeds the cost of being slightly undercollateralized.
- **FP:** `require(msg.sender != borrower)` on liquidation. Liquidation penalty exceeds any collateral bonus. Liquidation incentive is small enough that self-liquidation is net-negative after gas.

**235. Governance Proposal Executable Before Voting Period Ends**

- **D:** `execute()` checks quorum/majority but not `block.timestamp >= proposal.endTime`. Once quorum met, proposal executable immediately — cuts voting window short.
- **FP:** `require(block.timestamp >= proposal.endTime)`. OZ Governor enforces `ProposalState.Succeeded`.

**236. Timelock Anchored to Deployment, Not Action**

- **D:** Timelock measured from deployment, not action queue time. Once initial delay elapses, all future actions execute instantly — permanent bypass.
- **FP:** `executeAfter = block.timestamp + delay` set at queue time. OZ TimelockController.

**237. ERC721Consecutive Balance Corruption with Single-Token Batch**

- **D:** OZ `ERC721Consecutive` (< 4.8.2) + `_mintConsecutive(to, 1)` — size-1 batch fails to increment balance. `balanceOf` returns 0 despite ownership.
- **FP:** OZ >= 4.8.2 (patched). Batch size always >= 2. Standard `ERC721._mint` used.

**238. Reward Snapshot JIT (Same-Block Deposit-Withdraw for LP Rewards)**

- **D:** LP rewards accrue based on instantaneous liquidity share, not time-weighted contribution. Attacker adds massive liquidity before accrual, captures disproportionate share, removes after.
- **FP:** Time-weighted liquidity (`rewardPerLiquiditySecond` accumulator). Minimum staking duration. Previous-block snapshots.

**239. Partial Liquidation Leaves Position in Worse State**

- **D:** Partial liquidation seizes collateral without enforcing minimum post-liquidation health. Liquidator cherry-picks most valuable collateral, leaving position worse off.
- **FP:** Post-liquidation health check enforced. Full liquidation below floor threshold. Liquidator must achieve target health factor.

**240. EIP-7702 Cross-Chain Authorization Replay**

- **D:** Authorization tuple with `chain_id = 0` valid on ALL EVM chains supporting EIP-7702. Each chain has independent nonce — same signature replayed across L1, rollups, testnets to delegate victim's EOA everywhere.
- **FP:** Authorization signed with explicit `chain_id != 0`. Delegate contract checks `block.chainid`.

**241. Non-Atomic Proxy Deployment Enabling CPIMP Takeover**

- **D:** Proxy deployed in one tx, `initialize()` in a separate tx. Attacker front-runs init and inserts a malicious middleman implementation (CPIMP) that persists across upgrades by restoring itself in ERC-1967 slot.
- **FP:** Atomic init calldata in constructor. `_disableInitializers()` in implementation constructor.

**242. EIP-7702 Storage Collision on Redelegation**

- **D:** EOA redelegates from Contract A to Contract B. Storage persists and is reinterpreted under B's layout — corruption, privilege escalation, or fund loss.
- **FP:** ERC-7201 namespaced storage used. ERC-7779 redelegation process followed. Delegate has no persistent storage dependency.

**243. Read-Only Reentrancy**

- **D:** Protocol calls `view` function (`get_virtual_price()`, `totalAssets()`) on external contract from within a callback. External contract has no reentrancy guard on view functions — returns transitional/manipulated value mid-execution.
- **FP:** External view functions are `nonReentrant`. Chainlink oracle used instead. External contract's reentrancy lock checked before calling view.

**244. Delegatecall to Untrusted Callee**

- **D:** `address(target).delegatecall(data)` where `target` is user-provided or unconstrained.
- **FP:** `target` is hardcoded immutable verified library address.

**245. Staking Reward Front-Run by New Depositor**

- **D:** Reward checkpoint (`rewardPerTokenStored`) updated AFTER new stake recorded: `_balances[user] += amount` before `updateReward()`. New staker earns rewards for unstaked period.
- **FP:** `updateReward(account)` executes before any balance update. `rewardPerTokenPaid[user]` tracks per-user checkpoint.

**246. Cached Reward Debt Not Reset After Claim**

- **D:** After `claimRewards()`, `pendingReward`/`rewardDebt` not zeroed. Next claim pays full cached amount again — double payout.
- **FP:** `pendingReward[user] = 0` after transfer. `rewardDebt` recalculated from current balance and accumulator.

**247. Reward Accrual During Zero-Depositor Period**

- **D:** Time-based reward distribution starts at vault deployment but no depositors exist yet. First depositor claims all rewards accumulated during the empty period regardless of deposit size or timing.
- **FP:** Rewards only accrue when `totalSupply > 0`. Reward start time set on first deposit. Unclaimed pre-deposit rewards sent to treasury or burned.

**248. Borrower Front-Runs Liquidation**

- **D:** Borrower front-runs `liquidate()` with minimal repayment/top-up to push health above threshold, then re-borrows after liquidation fails. Repeatable indefinitely.
- **FP:** Flash-loan-resistant health check (same-block deposit excluded). Minimum repayment cooldown. Dutch auction liquidation.

**249. Diamond Proxy Cross-Facet Storage Collision**

- **D:** EIP-2535 Diamond facets declare storage variables without EIP-7201 namespaced storage. Multiple facets independently start at slot 0, writing to same slots.
- **FP:** All facets use single `DiamondStorage` struct at namespaced position (EIP-7201). No top-level state variables in facets.

**250. ERC1155 setApprovalForAll Grants All-Token-All-ID Access**

- **D:** Protocol requires `setApprovalForAll(protocol, true)` for deposits/staking. No per-ID or per-amount granularity -- operator can transfer any ID at full balance.
- **FP:** Protocol uses direct `safeTransferFrom` with user as `msg.sender`. Operator is immutable contract with escrow-only transfer logic.

**251. Invariant or Cap Enforced on One Code Path But Not Another**

- **D:** A constraint (pool cap, max supply, position limit, collateral ratio) is enforced during normal operation (e.g., `deposit()`) but not during settlement, reward distribution, interest accrual, or emergency paths. Constraint violated through the unguarded path.
- **FP:** Invariant check applied in a shared modifier/internal function called by all relevant paths. Post-condition assertion validates invariant after every state change. Comprehensive integration tests verify invariant across all entry points.

**252. Missing `_debit` / `_debitFrom` Authorization in OFT**

- **D:** Custom OFT override of `_debit` or `_debitFrom` omits `require(msg.sender == _from || allowance[_from][msg.sender] >= amount)`. Anyone can bridge tokens from any holder's balance. Pattern: `_debit` that calls `_burn(_from, amount)` without verifying caller is authorized.
- **FP:** Standard LayerZero OFT implementation used without override. Custom `_debit` includes proper authorization. `_debit` only callable via `send()` which uses `msg.sender` as `_from`.

**253. ERC1155 ID-Based Role Access Control With Publicly Mintable Role Tokens**

- **D:** Access control via `require(balanceOf(msg.sender, ROLE_ID) > 0)` where `mint` for those IDs is not separately gated. Role tokens transferable by default.
- **FP:** Minting role-token IDs gated behind separate access control. Role tokens non-transferable (`_beforeTokenTransfer` reverts for non-mint/burn). Dedicated non-token ACL used.

**254. ERC1155 Custom Burn Without Caller Authorization**

- **D:** Public `burn(address from, uint256 id, uint256 amount)` callable by anyone without verifying `msg.sender == from` or operator approval. Any caller burns another user's tokens.
- **FP:** `require(from == msg.sender || isApprovedForAll(from, msg.sender))` before `_burn`. OZ `ERC1155Burnable` used.

**255. Cross-Chain Address Ownership Variance**

- **D:** Same address has different owners on different chains (EOA private key not used on all chains, or `CREATE`-deployed contract at same nonce but different deployer). Cross-chain logic that assumes `address(X) on Chain A == address(X) on Chain B` implies same owner enables impersonation. Pattern: `lzRead` checking `ownerOf(tokenId)` cross-chain and granting rights to the same address locally.
- **FP:** `CREATE2`-deployed contracts with same factory + salt are safe. Peer mapping explicitly binds (chainId, address) pairs. Authorization uses cross-chain messaging (not address equality) to prove ownership.

**256. ERC1155 totalSupply Inflation via Reentrancy Before Supply Update**

- **D:** `totalSupply[id]` incremented AFTER `_mint` callback. During `onERC1155Received`, `totalSupply` is stale-low, inflating caller's share in any supply-dependent formula.
- **FP:** OZ >= 4.3.2 (patched ordering). `nonReentrant` on all mint functions. No supply-dependent logic callable from mint callback.

**257. Solmate SafeTransferLib Missing Contract Existence Check**

- **D:** Protocol uses Solmate's `SafeTransferLib` for ERC20 transfers. Unlike OZ `SafeERC20`, Solmate does not verify target address contains code — `transfer`/`transferFrom` to an EOA or not-yet-deployed `CREATE2` address returns success silently, crediting a phantom deposit.
- **FP:** OZ `SafeERC20` used instead. Manual `require(token.code.length > 0)` check. Token addresses verified at construction/initialization.

**258. Re-initialization Attack**

- **D:** V2 uses `initializer` instead of `reinitializer(2)`. Or upgrade resets initialized counter / storage-collides bool to false.
- **FP:** `reinitializer(version)` with correctly incrementing versions for V2+. Tests verify `initialize()` reverts after first call.

**259. Protocol Fee Inflates Reward Accumulator**

- **D:** Treasury fee processed through same `rewardPerToken` accumulator as staker rewards. Accumulator increments as if all goes to stakers — `earned()` exceeds contract balance.
- **FP:** Fee deducted before accumulator: `rewardPerToken += (reward - fee) / totalStaked`. Separate fee accounting.

**260. OFT Shared Decimals Truncation (uint64 Overflow)**

- **D:** OFT converts between local decimals and shared decimals (typically 6). `_toSD()` casts to `uint64`. If `sharedDecimals >= localDecimals` (both 18), no decimal conversion occurs but the `uint64` cast silently truncates amounts exceeding ~18.4e18. Also: custom fee logic applied BEFORE `_removeDust()` produces incorrect fee calculations.
- **FP:** Standard OFT with `sharedDecimals = 6` and `localDecimals = 18` (default). Fee logic applied after dust removal. Transfer amounts validated against `uint64.max` before conversion.

**261. Wrong Price Feed for Derivative or Wrapped Asset**

- **D:** Protocol uses ETH/USD feed to price stETH collateral, or BTC/USD feed for WBTC. During normal conditions the error is small, but during depeg events the mispricing enables undercollateralized borrows or incorrect liquidations.
- **FP:** Dedicated feed for the actual derivative asset (e.g., stETH/USD, WBTC/BTC). Deviation check against secondary oracle. Protocol documentation explicitly accepts depeg risk.

**262. Merkle Tree Second Preimage Attack**

- **D:** `MerkleProof.verify(proof, root, leaf)` where leaf derived from user input without double-hashing or type-prefixing. 64-byte input (two sibling hashes) passes as intermediate node.
- **FP:** Leaves double-hashed or include type prefix. Input length enforced != 64 bytes. OZ MerkleProof >= v4.9.2 with sorted-pair variant.

**263. Unauthorized Peer Initialization (Fake Peer Attack)**

- **D:** `setPeer()` / `setTrustedRemote()` sets the remote peer address that a cross-chain contract trusts. If the owner is compromised or `setPeer` lacks proper access control, an attacker registers a fraudulent peer contract on the source chain that can mint/unlock tokens on the destination without legitimate deposits. Pattern: `setPeer` callable by non-owner, or owner key compromised.
- **FP:** `setPeer` protected by multisig + timelock. Peer addresses verified against known deployment registry. `allowInitializePath()` properly implemented to reject unknown peers.

**264. Diamond Proxy Facet Selector Collision**

- **D:** EIP-2535 Diamond where two facets register same 4-byte selector. Malicious facet via `diamondCut` hijacks calls to critical functions. Pattern: `diamondCut` adds facet with overlapping selectors, no on-chain collision check.
- **FP:** `diamondCut` validates no selector collisions. `DiamondLoupeFacet` enumerates/verifies selectors post-cut. Multisig + timelock on `diamondCut`.

**265. Bytecode Verification Mismatch**

- **D:** Verified source doesn't match deployed bytecode behavior: different compiler settings, obfuscated constructor args, or `--via-ir` vs legacy pipeline mismatch. No reproducible build (no pinned compiler in config).
- **FP:** Deterministic build with pinned compiler/optimizer in committed config. Verification in deployment script (Foundry `--verify`). Sourcify full match. Constructor args published.

**266. Missing onERC1155BatchReceived Causes Token Lock**

- **D:** Contract implements `onERC1155Received` but not `onERC1155BatchReceived` (or returns wrong selector). `safeBatchTransferFrom` reverts, blocking batch settlement/distribution.
- **FP:** Both callbacks implemented correctly, or inherits OZ `ERC1155Holder`. Protocol exclusively uses single-item `safeTransferFrom`.
