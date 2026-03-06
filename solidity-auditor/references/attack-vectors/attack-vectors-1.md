# Attack Vectors Reference (1/4)

173 total attack vectors

---

**1. Signature Malleability**

- **D:** Raw `ecrecover` without `s <= 0x7FFF...20A0` validation. Both `(v,r,s)` and `(v',r,s')` recover same address. Bypasses signature-based dedup.
- **FP:** OZ `ECDSA.recover()` used (validates `s` range). Message hash used as dedup key, not signature bytes.

**2. ERC721Consecutive Balance Corruption with Single-Token Batch**

- **D:** OZ `ERC721Consecutive` (< 4.8.2) + `_mintConsecutive(to, 1)` — size-1 batch fails to increment balance. `balanceOf` returns 0 despite ownership.
- **FP:** OZ >= 4.8.2 (patched). Batch size always >= 2. Standard `ERC721._mint` used.

**3. Same-Block Deposit-Withdraw Exploiting Snapshot-Based Benefits**

- **D:** Protocol calculates yield, rewards, voting power, or insurance coverage based on balance at a single snapshot point. No minimum lock period between deposit and withdrawal. Attacker flash-loans tokens, deposits, triggers snapshot (or waits for same-block snapshot), claims benefit, withdraws — all in one tx/block.
- **FP:** `getPastVotes(block.number - 1)` or equivalent past-block snapshot. Minimum holding period enforced (`require(block.number > depositBlock)`). Reward accrual requires multi-block time passage.

**4. Token Decimal Mismatch in Cross-Token Arithmetic**

- **D:** Cross-token math uses hardcoded `1e18` or assumes identical decimals. Pattern: collateral/LTV/rate calculations combining token amounts without per-token `decimals()` normalization.
- **FP:** Amounts normalized to canonical precision (WAD/RAY) using each token's `decimals()`. Explicit `10 ** (18 - decimals())` scaling. Protocol only supports tokens with identical verified decimals.

**5. Block Timestamp Dependence**

- **D:** `block.timestamp` used for game outcomes, randomness (`block.timestamp % N`), or auction timing where ~15s manipulation changes outcome.
- **FP:** Timestamp used only for hour/day-scale periods. Timestamp used only for event logging with no state effect.

**6. Beacon Proxy Single-Point-of-Failure Upgrade**

- **D:** Multiple proxies read implementation from single Beacon. Compromising Beacon owner upgrades all proxies at once. `UpgradeableBeacon.owner()` returns single EOA.
- **FP:** Beacon owner is multisig + timelock. `Upgraded` events monitored. Per-proxy upgrade authority where isolation required.

**7. lzCompose Sender Impersonation (Composed Message Spoofing)**

- **D:** `lzCompose` implementation does not validate `msg.sender == endpoint` or does not check the `_from` parameter against the expected OFT address. Attacker calls `lzCompose` directly or via nested compose messages where sender context degrades to `address(this)`, impersonating the OFT contract.
- **FP:** `require(msg.sender == address(endpoint))` and `require(_from == expectedOFT)` validated. No nested compose message support. Standard `OAppReceiver` modifier used. Ref: Tapioca USDO/TOFT exploit (HIGH severity).

**8. Invariant or Cap Enforced on One Code Path But Not Another**

- **D:** A constraint (pool cap, max supply, position limit, collateral ratio) is enforced during normal operation (e.g., `deposit()`) but not during settlement, reward distribution, interest accrual, or emergency paths. Constraint violated through the unguarded path.
- **FP:** Invariant check applied in a shared modifier/internal function called by all relevant paths. Post-condition assertion validates invariant after every state change. Comprehensive integration tests verify invariant across all entry points.

**9. msg.value Reuse in Loop / Multicall**

- **D:** `msg.value` read inside a loop or `delegatecall`-based multicall. Each iteration/sub-call sees the full original value — credits `n * msg.value` for one payment.
- **FP:** `msg.value` captured to local variable, decremented per iteration, total enforced. Function non-payable. Multicall uses `call` not `delegatecall`.

**10. Zero-Amount Transfer Revert**

- **D:** `token.transfer(to, amount)` where `amount` can be zero (rounded fee, unclaimed yield). Some tokens (LEND, early BNB) revert on zero-amount transfers, DoS-ing distribution loops.
- **FP:** `if (amount > 0)` guard before all transfers. Minimum claim amount enforced. Token whitelist verified to accept zero transfers.

---

---

**11. ERC1155 safeBatchTransferFrom Unchecked Array Lengths**

- **D:** Custom `_safeBatchTransferFrom` iterates `ids`/`amounts` without `require(ids.length == amounts.length)`. Assembly-optimized paths may silently read uninitialized memory.
- **FP:** OZ ERC1155 base used unmodified. Custom override asserts equal lengths as first statement.

**12. ERC721/ERC1155 Callback Reentrancy**

- **D:** `safeTransferFrom`/`safeMint` called before state updates. Callbacks (`onERC721Received`/`onERC1155Received`) enable reentry.
- **FP:** All state committed before safe transfer. `nonReentrant` applied.

**13. Depeg of Pegged or Wrapped Asset Breaking Protocol Assumptions**

- **D:** Protocol assumes 1:1 peg between assets (stETH:ETH, WBTC:BTC, USDC:USD) in pricing, collateral valuation, or swap routing. No depeg tolerance or independent oracle for the derivative. During depeg, collateral is overvalued, enabling undercollateralized borrows or incorrect swaps.
- **FP:** Independent price feed per asset (not assumed 1:1). Configurable depeg threshold triggering protective measures (pause, adjusted LTV). Protocol documentation explicitly acknowledges and accepts depeg risk.

**14. Missing onERC1155BatchReceived Causes Token Lock**

- **D:** Contract implements `onERC1155Received` but not `onERC1155BatchReceived` (or returns wrong selector). `safeBatchTransferFrom` reverts, blocking batch settlement/distribution.
- **FP:** Both callbacks implemented correctly, or inherits OZ `ERC1155Holder`. Protocol exclusively uses single-item `safeTransferFrom`.

**15. Missing or Incorrect Access Modifier**

- **D:** State-changing function (`setOwner`, `withdrawFunds`, `mint`, `pause`, `setOracle`) has no access guard or modifier references uninitialized variable. `public`/`external` on privileged operations with no restriction.
- **FP:** Function is intentionally permissionless with non-critical worst-case outcome (e.g., advancing a public time-locked process).

**16. extcodesize Zero in Constructor**

- **D:** `require(msg.sender.code.length == 0)` as EOA check. Contract constructors have `extcodesize == 0` during execution, bypassing the check.
- **FP:** Check is non-security-critical. Function protected by merkle proof, signed permit, or other mechanism unsatisfiable from constructor.

**17. Solmate SafeTransferLib Missing Contract Existence Check**

- **D:** Protocol uses Solmate's `SafeTransferLib` for ERC20 transfers. Unlike OZ `SafeERC20`, Solmate does not verify target address contains code — `transfer`/`transferFrom` to an EOA or not-yet-deployed `CREATE2` address returns success silently, crediting a phantom deposit.
- **FP:** OZ `SafeERC20` used instead. Manual `require(token.code.length > 0)` check. Token addresses verified at construction/initialization.

**18. Re-initialization Attack**

- **D:** V2 uses `initializer` instead of `reinitializer(2)`. Or upgrade resets initialized counter / storage-collides bool to false. Ref: AllianceBlock (2024).
- **FP:** `reinitializer(version)` with correctly incrementing versions for V2+. Tests verify `initialize()` reverts after first call.

**19. ERC1155 uri() Missing {id} Substitution**

- **D:** `uri(uint256 id)` returns fully resolved URL instead of template with literal `{id}` placeholder per EIP-1155. Clients expect to substitute zero-padded hex ID client-side. Static/empty return collapses all token metadata.
- **FP:** Returns string containing literal `{id}`. Or per-ID on-chain URI with documented deviation from substitution spec.

**20. Immutable Variable Context Mismatch**

- **D:** Implementation uses `immutable` variables (embedded in bytecode, not storage). Proxy `delegatecall` gets implementation's hardcoded values regardless of per-proxy needs. E.g., `immutable WETH` — every proxy gets same address.
- **FP:** Immutable values intentionally identical across all proxies. Per-proxy config uses storage via `initialize()`.

---

---

**21. validateUserOp Signature Not Bound to nonce or chainId**

- **D:** `validateUserOp` reconstructs digest manually (not via `entryPoint.getUserOpHash`) omitting `userOp.nonce` or `block.chainid`. Enables cross-chain or in-chain replay.
- **FP:** Digest from `entryPoint.getUserOpHash(userOp)` (includes sender, nonce, chainId). Custom digest explicitly includes both.

**22. Blacklistable or Pausable Token in Critical Payment Path**

- **D:** Push-model transfer `token.transfer(recipient, amount)` with USDC/USDT or other blacklistable token. Blacklisted recipient reverts entire function, DOSing withdrawals/liquidations/fees.
- **FP:** Pull-over-push pattern (recipients withdraw own funds). Skip-on-failure `try/catch` on fee distribution. Token whitelist excludes blacklistable tokens.

**23. Improper Flash Loan Callback Validation**

- **D:** `onFlashLoan` callback doesn't verify `msg.sender == lendingPool`, or doesn't check `initiator`/`token`/`amount`. Callable directly without real flash loan.
- **FP:** Both `msg.sender == address(lendingPool)` and `initiator == address(this)` validated. Token/amount checked.

**24. Cross-Chain Deployment Replay**

- **D:** Deployment tx replayed on another chain. Same deployer nonce on both chains produces same CREATE address under different control. No EIP-155 chain ID protection. Ref: Wintermute.
- **FP:** EIP-155 signatures. `CREATE2` via deterministic factory at same address on all chains. Per-chain deployer EOAs.

**25. DoS via Unbounded Loop**

- **D:** Loop over user-growable unbounded array: `for (uint i = 0; i < users.length; i++)`. Eventually hits block gas limit.
- **FP:** Array length capped at insertion: `require(arr.length < MAX)`. Loop iterates fixed small constant.

**26. Precision Loss - Division Before Multiplication**

- **D:** `(a / b) * c` — truncation before multiplication amplifies error. E.g., `fee = (amount / 10000) * bps`. Correct: `(a * c) / b`.
- **FP:** `a` provably divisible by `b` (enforced by `require(a % b == 0)` or mathematical construction).

**27. ecrecover Returns address(0) on Invalid Signature**

- **D:** Raw `ecrecover` without `require(recovered != address(0))`. If `authorizedSigner` is uninitialized or `permissions[address(0)]` is non-zero, garbage signature gains privileges.
- **FP:** OZ `ECDSA.recover()` used (reverts on address(0)). Explicit zero-address check present.

**28. Function Selector Clash in Proxy**

- **D:** Proxy and implementation share a 4-byte selector collision. Call intended for implementation routes to proxy's function (or vice versa).
- **FP:** Transparent proxy pattern (admin/user call routing separates namespaces). UUPS with no custom proxy functions — all calls delegate unconditionally.

**29. CREATE2 Address Squatting (Counterfactual Front-Running)**

- **D:** CREATE2 salt not bound to `msg.sender`. Attacker precomputes address and deploys first. For AA wallets: attacker deploys wallet to user's counterfactual address with attacker as owner.
- **FP:** Salt incorporates `msg.sender`: `keccak256(abi.encodePacked(msg.sender, userSalt))`. Factory restricts deployer. Different owner in constructor produces different address.

**30. Return Bomb (Returndata Copy DoS)**

- **D:** `(bool success, bytes memory data) = target.call(payload)` where `target` is user-supplied. Malicious target returns huge returndata; copying costs enormous gas.
- **FP:** Returndata not copied (assembly call without copy, or gas-limited). Callee is hardcoded trusted contract.

---

---

**31. Immutable / Constructor Argument Misconfiguration**

- **D:** Constructor sets `immutable` values (admin, fee, oracle, token) that can't change post-deploy. Multiple same-type `address` params where order can be silently swapped. No post-deploy verification.
- **FP:** Deployment script reads back and asserts every configured value. Constructor validates: `require(admin != address(0))`, `require(feeBps <= 10000)`.

**32. Small-Type Arithmetic Overflow Before Upcast**

- **D:** Arithmetic on `uint8`/`uint16`/`uint32` before assigning to wider type: `uint256 result = a * b` where `a`,`b` are `uint8`. Overflow happens in narrow type before widening. Solidity 0.8 overflow check is still on the narrow type.
- **FP:** Operands explicitly upcast before operation: `uint256(a) * uint256(b)`. SafeCast used.

**33. ERC4626 Missing Allowance Check in withdraw() / redeem()**

- **D:** `withdraw(assets, receiver, owner)` / `redeem(shares, receiver, owner)` where `msg.sender != owner` but no allowance check/decrement before burning shares. Any address can burn arbitrary owner's shares.
- **FP:** `_spendAllowance(owner, caller, shares)` called unconditionally when `caller != owner`. OZ ERC4626 without custom overrides.

**34. mstore8 Partial Write Leaving Dirty Bytes**

- **D:** `mstore8` writes a single byte at a memory offset, but subsequent `mload` reads the full 32-byte word containing that byte. The remaining 31 bytes retain prior memory contents (potentially uninitialized or stale data). Pattern: building a byte array with `mstore8` in a loop, then hashing or returning the full memory region — dirty bytes corrupt the result.
- **FP:** Full word zeroed with `mstore(ptr, 0)` before byte-level writes. `mload` result masked to extract only the written bytes. `mstore` used instead of `mstore8` with proper shifting.

**35. Batch Distribution Dust Residual**

- **D:** Loop distributes funds proportionally: `share = total * weight[i] / totalWeight`. Cumulative rounding causes `sum(shares) < total`, leaving dust locked in contract. Pattern: N recipients each computed independently without remainder handling.
- **FP:** Last recipient gets `total - sumOfPrevious`. Dust swept to treasury. `mulDiv` with accumulator tracking. Protocol accepts bounded dust loss by design.

**36. Arbitrary `delegatecall` in Implementation**

- **D:** Implementation exposes `delegatecall` to user-supplied address without restriction. Pattern: `target.delegatecall(data)` where `target` is caller-controlled. Ref: Furucombo (2021).
- **FP:** Target is hardcoded immutable address. Whitelist of approved targets enforced. `call` used instead.

**37. Commit-Reveal Scheme Not Bound to msg.sender**

- **D:** Commitment hash does not include `msg.sender`: `commit = keccak256(abi.encodePacked(value, salt))`. Attacker copies a victim's commitment from the chain/mempool and submits their own reveal for the same hash from a different address. Affects auctions, governance votes, randomness.
- **FP:** Commitment includes sender: `keccak256(abi.encodePacked(msg.sender, value, salt))`. Reveal validates `msg.sender` matches stored committer.

**38. Delegate Privilege Escalation**

- **D:** `setDelegate()` appoints an address that can manage OApp configurations including DVNs, Executors, message libraries, and can skip/clear payloads. If delegate is set to an insecure address (EOA, unrelated contract) or differs from owner without governance controls, the delegate can silently reconfigure the OApp's entire security stack.
- **FP:** Delegate == owner. Delegate is a governance timelock or multisig. `setDelegate` protected by the same access controls as `setPeer`.

**39. Cross-Chain Supply Accounting Invariant Violation**

- **D:** The fundamental invariant `total_locked_source >= total_minted_destination` is violated. Can occur through: decimal conversion errors between chains, `_credit` callable without corresponding `_debit`, race conditions in multi-chain deployments, or any bug that allows minting without locking. Minted tokens become partially or fully unbacked.
- **FP:** Invariant verified via monitoring/alerting. `_credit` only callable from verified `lzReceive` path. Decimal conversion tested across all supported chains. Rate limits cap maximum exposure per time window.

---

**40. ERC1155 onERC1155Received Return Value Not Validated**

- **D:** Custom ERC1155 calls `onERC1155Received` but doesn't check returned `bytes4` equals `0xf23a6e61`. Non-compliant recipient silently accepts tokens it can't handle.
- **FP:** OZ ERC1155 base validates selector. Custom impl explicitly checks return value.

---

**41. Small Positions Unliquidatable Due to Insufficient Incentive (Bad Debt)**

- **D:** Positions below a certain USD value cost more gas to liquidate than the liquidation reward. During market downturns, these "dust positions" accumulate bad debt that no liquidator will process, eroding protocol solvency.
- **FP:** Minimum position size enforced at borrow time. Protocol-operated liquidation bot covers dust positions. Socialized bad debt mechanism (insurance fund, haircuts).

**42. Ordered Message Channel Blocking (Nonce DoS)**

- **D:** OApp uses ordered nonce execution. If one message permanently reverts on destination (e.g., recipient contract reverts, invalid state), ALL subsequent messages from that source are blocked. Attacker intentionally sends a poison message to freeze the entire channel.
- **FP:** Unordered nonce mode used (LayerZero V2 default). `_lzReceive` wrapped in try/catch with fallback logic. `NonblockingLzApp` pattern (V1). Admin can `skipPayload` / `clearPayload` to unblock. Ref: Code4rena Maia DAO finding #883.
