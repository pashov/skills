# Attack Vectors Reference

65 attack vectors. For each: detection pattern (what to look for in code) and false-positive signals (what makes it NOT a vulnerability even if the pattern matches).

---

**1. Missing Slippage Protection (Sandwich Attack)**

- **Detect:** Swap/deposit/withdrawal with `minAmountOut = 0`, or `minAmountOut` computed on-chain from current pool state (always passes). Pattern: `router.swap(..., 0, deadline)`.
- **FP:** `minAmountOut` set off-chain by the user and validated on-chain.

**2. Flash Loan Governance Attack**

- **Detect:** Governance voting uses `token.balanceOf(msg.sender)` or `getPastVotes(account, block.number)` (current block). Attacker borrows governance tokens, votes, repays in one tx.
- **FP:** Uses `getPastVotes(account, block.number - 1)` (prior block, un-manipulable in current tx). Timelock between snapshot and vote. Staking required before voting.

**3. ERC721/ERC1155 Callback Reentrancy**

- **Detect:** `safeTransferFrom` (ERC721) or `safeMint`/`safeTransferFrom` (ERC1155) called before state updates. These invoke `onERC721Received`/`onERC1155Received` on recipient contracts.
- **FP:** All state committed before the safe transfer. Function is `nonReentrant`.

**4. Write to Arbitrary Storage Location**

- **Detect:** (1) Assembly block with `sstore(slot, value)` where `slot` is derived from user-supplied calldata, function parameters, or arithmetic over user-controlled values without bounds validation — allows overwriting any slot including `owner`, `implementation`, or balance mappings. (2) (Solidity <0.6) Direct assignment to a storage array's `.length` field (`arr.length = userValue`) followed by an indexed write `arr[largeIndex] = x`. The storage slot for `arr[i]` is `keccak256(arraySlot) + i`; with a crafted large index, slot arithmetic wraps around and overwrites arbitrary slots. (SWC-124)
- **FP:** Assembly is read-only (`sload` only, no `sstore`). Slot value is a compile-time constant or derived exclusively from non-user-controlled data (e.g., `keccak256("protocol.slot")` pattern). Solidity ≥0.6 used throughout (compiler disallows direct array length assignment). Slot arithmetic validated against a fixed known-safe range before use.

**5. Missing chainId (Cross-Chain Replay)**

- **Detect:** Signed payload doesn't include `chainId`. Valid signature on mainnet replayable on forks or other EVM chains where the contract is deployed. Or `chainId` hardcoded at deployment rather than read via `block.chainid`.
- **FP:** EIP-712 domain separator includes `chainId: block.chainid` (dynamic) and `verifyingContract`. Domain separator re-checked or invalidated if `block.chainid` changes.

**6. Block Stuffing / Gas Griefing on Subcalls**

- **Detect:** Time-sensitive function can be blocked by filling blocks (SWC-126). For relayer gas-forwarding griefing via the 63/64 rule, see Vector 48.
- **FP:** Function is not time-sensitive or has a sufficiently long window that block stuffing is economically infeasible.

**7. Spot Price Oracle from AMM**

- **Detect:** Price computed from AMM reserves directly: `price = reserve0 / reserve1`, `getAmountsOut()`, `getReserves()`. Any lending, liquidation, or collateral logic built on spot price is flash-loan exploitable atomically.
- **FP:** TWAP oracle with a 30-minute or longer observation window. Chainlink or Pyth as primary source.

**8. abi.encodePacked Hash Collision with Dynamic Types**

- **Detect:** `keccak256(abi.encodePacked(a, b, ...))` where two or more arguments are dynamic types (`string`, `bytes`, or dynamic arrays such as `uint[]`, `address[]`). `abi.encodePacked` concatenates raw bytes without length prefixes, so `("AB","CD")`, `("A","BCD")`, and `("ABC","D")` all produce the same byte sequence `0x41424344` and thus the same hash. If the hash is used for permit/signature verification, access control key derivation, or uniqueness enforcement (mapping keys, nullifiers), an attacker crafts an alternative input that collides with a legitimate hash and gains the same privileges.
- **FP:** `abi.encode()` used instead — each argument is ABI-padded and length-prefixed, eliminating ambiguity. Only one argument is a dynamic type (no two dynamic types to collide between). All arguments are fixed-size types (`uint256`, `address`, `bytes32`).

**9. Cross-Contract Reentrancy**

- **Detect:** Two separate contracts share logical state (e.g., balances in A, collateral check in B). A makes an external call before syncing the state B reads. A's `ReentrancyGuard` does not protect B.
- **FP:** The state B reads is synchronized before A's external call. No re-entry path exists from A's external callee back into B — verified by tracing the full call graph.

**10. Unprotected Initializer / UUPS Implementation selfdestruct**

- **Detect:** Two related patterns: (1) `initialize()` is missing the `initializer` modifier — anyone can call it on the implementation contract or re-initialize a proxy; (2) UUPS implementation constructor omits `_disableInitializers()` — attacker calls `initialize()` on the bare implementation, claims ownership, calls `upgradeTo(maliciousImpl)` with `selfdestruct`, destroying every proxy pointing to it. Look for: `function initialize(...)` without `initializer`/`reinitializer` modifier; UUPS `_authorizeUpgrade` present but no `_disableInitializers()` in constructor.
- **FP:** Constructor calls `_disableInitializers()`. `initializer` modifier from OpenZeppelin `Initializable` is present and correctly gates the function. Implementation verifies it is being called through a proxy before executing any logic.

**11. Integer Overflow / Underflow**

- **Detect:** Arithmetic inside `unchecked {}` blocks (Solidity ≥0.8) that could over/underflow: subtraction without a prior `require(amount <= balance)`, multiplication of two large values. Any arithmetic in Solidity <0.8 without SafeMath. (SWC-101)
- **FP:** Value range is provably bounded by earlier checks that appear in the same function before the unchecked block. `unchecked` used exclusively for loop counter increments of the form `++i` where `i < arr.length`, making overflow structurally impossible.

**12. DoS via Push Payment to Rejecting Contract**

- **Detect:** ETH/token distribution in a single loop using push model (`recipient.call{value:}("")`). If any recipient reverts on receive, the entire loop reverts. Also: `transfer()`/`send()` to contracts with expensive `fallback()`. (SWC-113)
- **FP:** Pull-over-push pattern used — recipients withdraw their own funds. Loop uses `try/catch` and continues on failure.

**13. Weak On-Chain Randomness / Randomness Frontrunning**

- **Detect:** Randomness from `block.prevrandao` (RANDAO, validator-influenceable), `blockhash(block.number - 1)` (known before inclusion), `block.timestamp`, `block.coinbase`, or combinations. Validators can influence RANDAO; all block values are visible before tx inclusion, enabling front-running of randomness-dependent outcomes. (SWC-120)
- **FP:** Chainlink VRF v2+ used. Commit-reveal scheme with future-block reveal and a meaningful economic penalty (slashing or bond forfeiture) enforced in code for non-reveal.

**14. Missing or Incorrect Access Modifier**

- **Detect:** State-changing function (`setOwner`, `withdrawFunds`, `mint`, `pause`, `setOracle`, `updateFees`) has no access guard, or modifier references an uninitialized variable. `public`/`external` visibility on privileged operations with no restriction.
- **FP:** Function is genuinely permissionless by design — any caller can legitimately invoke it and the worst-case outcome is a non-critical state transition (e.g., triggering a public distribution, settling an open auction, or advancing a time-locked process that anyone can advance).

**15. Proxy Storage Slot Collision**

- **Detect:** Proxy stores `implementation`/`admin` at sequential slots (0, 1) and implementation contract also declares variables from slot 0. Implementation's slot 0 write overwrites the proxy's `implementation` pointer.
- **FP:** Proxy uses EIP-1967 slots (`keccak256("eip1967.proxy.implementation") - 1`). OpenZeppelin Transparent or UUPS proxy pattern used correctly.

**16. Off-By-One in Bounds or Range Checks**

- **Detect:** (1) Loop upper bound uses `<=` instead of `<` on an array index: `for (uint i = 0; i <= arr.length; i++)` — accesses `arr[arr.length]` on the final iteration, reverting or reading uninitialized memory. (2) `arr[arr.length - 1]` or `arr[index - 1]` without a preceding `require(arr.length > 0)` / `require(index > 0)` — in `unchecked` blocks the underflow silently wraps to a huge index. (3) Inclusive/exclusive boundary confusion in financial logic: `require(block.timestamp >= vestingEnd)` vs. `> vestingEnd`, or `require(amount <= MAX)` where MAX was intended as exclusive — one unit of difference causes early unlock or allows a boundary-exceeding deposit. (4) Cumulative distribution: allocating a total across N recipients using integer division, where rounding errors accumulate and the final recipient receives more or less than intended.
- **FP:** Loop uses `<` not `<=` and the upper bound is a fixed-length array or a compile-time constant — overflow into out-of-bounds is structurally impossible. Last-element access is always preceded by a `require(arr.length > 0)` or equivalent in the same scope. Financial boundary comparisons (`>=` vs `>`) are demonstrably correct for the invariant being enforced (e.g., `>= vestingEnd` for an inclusive deadline, `< MAX` for an exclusive cap).

**17. Chainlink Staleness / No Validity Checks**

- **Detect:** `latestRoundData()` called but any of these checks are missing: `answer > 0`, `updatedAt > block.timestamp - MAX_STALENESS`, `answeredInRound >= roundId`, fallback on failure.
- **FP:** All four checks present. Circuit breaker or fallback oracle used when any check fails.

**18. Single-Function Reentrancy**

- **Detect:** External call (`call{value:}`, `transfer`, `send`, `safeTransfer`, `safeTransferFrom`) happens _before_ state update (balance set to 0, flag set, counter decremented). Classic: check-external-effect instead of check-effect-external.
- **FP:** State updated before the call (CEI followed). `nonReentrant` modifier present. Callee is a hardcoded immutable address of a contract whose receive/fallback is known to not re-enter.

**19. Function Selector Clash in Proxy**

- **Detect:** Proxy and implementation share a 4-byte function selector collision. A call intended for the implementation gets routed to the proxy's own function (or vice versa), silently executing the wrong logic.
- **FP:** Transparent proxy pattern used — admin calls always route to the proxy admin and user calls always delegate, so the implementation selector space is the only relevant one for users. UUPS proxy with no custom functions in the proxy shell — all calls delegate unconditionally, making selector clashes between proxy and implementation impossible.

**20. Missing Nonce (Signature Replay)**

- **Detect:** Signed message has no per-user nonce, or nonce is present in the struct but never stored/incremented after use. Same valid signature can be submitted multiple times. (SWC-121)
- **FP:** Monotonic per-signer nonce included in signed payload, stored, checked for reuse, incremented atomically. `usedSignatures[hash]` mapping invalidates after first use.

**21. tx.origin Authentication**

- **Detect:** `require(tx.origin == owner)` or `require(tx.origin == authorized)` used for authentication. Vulnerable to phishing via malicious intermediary contract.
- **FP:** `tx.origin == msg.sender` used only to assert caller is not a contract (anti-bot pattern, not auth).

**22. L2 Sequencer Uptime Not Checked**

- **Detect:** Contract on Arbitrum/Optimism/Base/etc. uses Chainlink feeds but does not query the L2 Sequencer Uptime Feed before consuming prices. Stale data during sequencer downtime can trigger wrong liquidations.
- **FP:** Sequencer uptime feed queried explicitly (`answer == 0` = up), with a grace period enforced after restart.

**23. Precision Loss - Division Before Multiplication**

- **Detect:** Expression `(a / b) * c` in integer math. Division truncates first, then multiplication amplifies the error. Common in fee calculations: `fee = (amount / 10000) * bps`. Correct form: `(a * c) / b`.
- **FP:** `a` is provably divisible by `b` — enforced by a preceding explicit check (e.g., `require(a % b == 0)`) or by mathematical construction visible in the code.

**24. Return Bomb (Returndata Copy DoS)**

- **Detect:** `(bool success, bytes memory data) = target.call(payload)` where `target` is user-supplied or unconstrained. Malicious target returns huge returndata; copying it costs enormous gas.
- **FP:** Returndata not copied (`assembly { success := call(...) }` without copy, or gas-limited call). Callee is a hardcoded immutable trusted contract.

**25. Flash Loan-Assisted Price Manipulation**

- **Detect:** A function reads price/ratio from an on-chain source (AMM reserves, vault `totalAssets()`), and that source can be manipulated atomically in the same tx via flash loan + swap. Attacker sequence: borrow → move price → call function → restore → repay.
- **FP:** Price source is TWAP with a 30-minute or longer observation window. Multi-block cooldown enforced between price reads. Function can only be called in a separate block from any state that could be manipulated.

**26. msg.value Reuse in Loop / Multicall**

- **Detect:** `msg.value` read inside a loop body, or inside a `delegatecall`-based multicall where each sub-call is dispatched via `address(this).delegatecall(data[i])`. `msg.value` is a transaction-level constant — it does not decrease as ETH is "spent" within the call. Direct loop: `for (uint i = 0; i < n; i++) { deposit(msg.value); }` credits `n × msg.value` while only `msg.value` was sent. Delegatecall multicall: each sub-call inherits the original `msg.value`, so including the same payable function `n` times receives credit for `n × msg.value` with one payment.
- **FP:** `msg.value` captured into a local variable before the loop; that local is decremented per iteration and the contract enforces that total allocated equals the captured value. Function is non-payable. Multicall dispatches via `call` (not `delegatecall`), so each sub-call only receives ETH explicitly forwarded to it.

**27. Read-Only Reentrancy**

- **Detect:** Protocol calls a `view` function (e.g., `get_virtual_price()`, `totalAssets()`, `convertToAssets()`) on an external contract from within a callback (`receive`, `onERC721Received`, flash loan hook). The external contract has no reentrancy guard on its view functions - a mid-execution call can return a transitional/manipulated value.
- **FP:** External contract's view functions are themselves `nonReentrant`. Protocol uses Chainlink or another oracle instead of the external view. External contract's reentrancy lock is public and the protocol reads and enforces it before calling any view function.

**28. Block Number as Timestamp Approximation**

- **Detect:** Time computed as `(block.number - startBlock) * 13` assuming fixed block times. Post-Merge Ethereum has variable block times; Polygon/Arbitrum/BSC have very different averages. Causes wrong interest accrual, vesting, or reward calculations.
- **FP:** `block.timestamp` used instead of `block.number` for all time-sensitive calculations.

**29. Missing chainId / Message Uniqueness in Bridge**

- **Detect:** Bridge/messaging contract processes incoming messages but lacks: `processedMessages[messageHash]` check (replay), `destinationChainId == block.chainid` validation, or source chain ID in the message hash. A message from Chain A to Chain B can be replayed on Chain C, or submitted twice on the destination.
- **FP:** Each message has a unique nonce per sender. Hash of `(sourceChain, destinationChain, nonce, payload)` stored in `processedMessages` and checked before execution. Contract address included in message hash.

**30. Cross-Function Reentrancy**

- **Detect:** Two functions share a state variable. Function A makes an external call before updating shared state; Function B reads or modifies that same state. `nonReentrant` on A but not B.
- **FP:** Both functions are guarded by the same contract-level mutex. Shared state fully updated before any external call in A.

**31. DoS via Unbounded Loop**

- **Detect:** Loop iterates over an array that grows with user interaction and is unbounded: `for (uint i = 0; i < users.length; i++) { ... }`. If anyone can push to `users`, the function will eventually hit the block gas limit. (SWC-128)
- **FP:** Array length capped at insertion time with a `require(arr.length < MAX)` check. Loop iterates a fixed small constant count.

**32. Delegatecall to Untrusted / User-Supplied Callee**

- **Detect:** `address(target).delegatecall(data)` where `target` is user-provided or unconstrained. Callee executes in the caller's storage context - can overwrite owner, balances, call `selfdestruct`. (SWC-112)
- **FP:** `target` is a hardcoded immutable verified library address that cannot be changed after deployment.

**33. Unsafe Downcast / Integer Truncation**

- **Detect:** Explicit cast to smaller type without bounds check: `uint128(largeUint256)`. Solidity ≥0.8 silently truncates on downcast (does NOT revert). Especially dangerous in price feeds, share calculations, timestamps.
- **FP:** Value validated against the target type's maximum before cast (e.g., `require(x <= type(uint128).max)`). OpenZeppelin `SafeCast` library used.

**34. Block Timestamp Dependence**

- **Detect:** `block.timestamp` used for game outcomes, randomness (`block.timestamp % N`), or auction timing where a 15-second manipulation changes the outcome. (SWC-116)
- **FP:** Timestamp used only for periods spanning hours or days, where 15-second validator manipulation has no meaningful impact on the outcome. Timestamp used only for event logging with no effect on state or logic.

**35. Missing or Expired Deadline on Swaps**

- **Detect:** `deadline = block.timestamp` (computed inside the tx, always valid), `deadline = type(uint256).max`, or no deadline at all. Transaction can be held in mempool and executed at any future price.
- **FP:** Deadline is a calldata parameter validated on-chain as `require(deadline >= block.timestamp)` and is not derived from `block.timestamp` or set to `type(uint256).max` within the function itself.

**36. Missing Storage Gap in Upgradeable Base Contract**

- **Detect:** Upgradeable base contract has no `uint256[N] private __gap;` at the end. A future version adding state variables to the base shifts the derived contract's storage layout, overwriting existing variables.
- **FP:** EIP-1967 namespaced storage slots used for all variables in the base contract. Single-contract (non-inherited) implementation where new variables can only be appended safely.

**37. Improper Flash Loan Callback Validation**

- **Detect:** `onFlashLoan` callback does not verify `msg.sender == lendingPool`, or does not verify `initiator`, or does not check `token`/`amount` match. Attacker can call the callback directly without a real flash loan.
- **FP:** Both `msg.sender == address(lendingPool)` and `initiator == address(this)` are validated. Token and amount checked against pre-stored values.

**38. Signature Malleability**

- **Detect:** Raw `ecrecover(hash, v, r, s)` used without validating `s <= 0x7FFF...20A0`. Both `(v,r,s)` and `(v',r,s')` recover the same address. If signatures are used as unique identifiers (stored to prevent replay), a malleable variant bypasses the uniqueness check. (SWC-117)
- **FP:** OpenZeppelin `ECDSA.recover()` used (validates `s` range and `v`). Full message hash used as dedup key, not the signature bytes.

**39. Transient Storage Low-Gas Reentrancy (EIP-1153)**

- **Detect:** Contract uses `transfer()` or `send()` (2300-gas stipend) as its reentrancy protection, AND either the contract or a called external contract uses `transient` variables or `TSTORE`/`TLOAD` in assembly. Post-Cancun (Solidity ≥0.8.24), `TSTORE` succeeds with fewer than 2300 gas — unlike `SSTORE`, which is blocked by EIP-2200. The 2300-gas-as-reentrancy-guard assumption is broken. Second pattern: transient reentrancy lock that is not explicitly cleared at the end of the call frame. Because transient storage persists for the entire transaction (not just the call), if the contract is invoked again in the same tx (e.g., via multicall or flash loan callback), the transient lock from the first invocation is still set, causing a permanent DoS for the remainder of the tx.
- **FP:** Reentrancy protection uses an explicit `nonReentrant` modifier backed by a regular storage slot (or a correctly implemented transient mutex cleared at call end). CEI pattern followed unconditionally regardless of gas stipend. Contract does not use transient storage at all.

**40. Force-Feeding ETH via selfdestruct or coinbase**

- **Detect:** Business logic relies on `address(this).balance` for invariant checks, share/deposit accounting, or as a denominator: `require(address(this).balance == trackingVar)`, `shares = msg.value * totalSupply / address(this).balance`. ETH can be force-sent without triggering `receive()`/`fallback()` via: (1) `selfdestruct(payable(target))` — even if target has no payable functions; (2) pre-deployment: computing a contract's deterministic address and sending ETH before it is deployed; (3) being set as the `coinbase` address for a mined block. Forced ETH inflates the balance above expected values, breaking any invariant or ratio built on it.
- **FP:** All accounting uses a private `uint256 _deposited` variable incremented only inside payable functions — never `address(this).balance`. `address(this).balance` appears only in informational view functions, not in guards or financial math.

**41. CREATE2 Address Reuse After selfdestruct**

- **Detect:** Protocol whitelists, approves, or trusts a contract at an address derived from CREATE2. Attacker controls the salt or factory. Pre-EIP-6780: attacker deploys a benign contract, earns trust (e.g., token approval, whitelist entry, governance power), calls `selfdestruct`, then redeploys a malicious contract to the identical address. The stored approval/whitelist entry now points to the malicious code. Pattern: `create2Factory.deploy(salt, initcode)` where `salt` is user-supplied or predictable, combined with no bytecode-hash verification at trust-grant time.
- **FP:** Post-Dencun (EIP-6780): `selfdestruct` no longer destroys code unless it occurs in the same transaction as contract creation, effectively eliminating the redeploy path on mainnet. Bytecode hash of the approved contract recorded at approval time and re-verified before each privileged call. No user-controlled CREATE2 salt accepted by the factory.

**42. extcodesize Zero / isContract Bypass in Constructor**

- **Detect:** Access control or anti-bot check uses `require(msg.sender.code.length == 0)` or assembly `extcodesize(caller())` to assert the caller is an EOA. During a contract's constructor execution, `extcodesize` of that contract's own address returns zero — no code is stored until construction finishes. An attacker deploys a contract whose constructor calls the protected function, bypassing the check. Common targets: minting limits, presale allocation caps, "no smart contracts" whitelist enforcement.
- **FP:** The check is informational only and not security-critical. The function is independently protected by a merkle-proof allowlist, signed permit, or other mechanism that cannot be satisfied inside a constructor. Protocol explicitly states and accepts on-chain contract interaction.

**43. Multi-Block TWAP Oracle Manipulation**

- **Detect:** Protocol uses a Uniswap V2 or V3 TWAP with an observation window shorter than 30 minutes (~150 blocks). Post-Merge PoS validators who are elected to propose consecutive blocks can hold an AMM pool in a manipulated state across multiple blocks with no flash-loan repayment pressure. Each held block contributes a manipulated price sample to the TWAP accumulator. With short windows (e.g., 5–10 minutes), controlling 2–3 consecutive blocks shifts the TWAP enough to trigger profitable liquidations or over-collateralized borrows. Cost: only the capital to move the pool, held for a few blocks — far cheaper than equivalent single-block manipulation.
- **FP:** TWAP window ≥ 30 minutes. Chainlink or Pyth used as the price source instead of AMM TWAP. Protocol uses max-deviation circuit breaker that rejects price updates deviating more than X% from a secondary source.

**44. Missing Input Validation on Critical Setters**

- **Detect:** Admin functions set numeric parameters with no validation: `setFee(uint256 fee)` with no `require(fee <= MAX_FEE)`; `setOracle(address o)` with no interface check. A misconfigured call — wrong argument, value exceeding 100% — silently bricks fee collection, enables 100% fee extraction, or points the oracle to a dead address.
- **FP:** Every setter has explicit `require` bounds on all parameters. Numeric parameters validated against documented protocol constants.

**45. Staking Reward Front-Run by New Depositor**

- **Detect:** Reward checkpoint (`rewardPerTokenStored`, `lastUpdateTime`) is updated lazily — only when a user action triggers it — and the update happens AFTER the new stake is recorded in `_balances` or `totalSupply`. A new staker can join immediately before `notifyRewardAmount()` is called (or immediately before a large pending reward accrues), and the checkpoint then distributes the new rewards pro-rata over a supply that includes the attacker's stake. The attacker earns rewards for a period they were not staked. Pattern: `_balances[user] += amount; totalSupply += amount;` executed before `updateReward()`.
- **FP:** `updateReward(account)` is the very first step of `stake()` — executed before any balance update — so new stakers start from the current `rewardPerTokenStored` and earn nothing retroactively. `rewardPerTokenPaid[user]` correctly tracks per-user checkpoint.

**46. ecrecover Returns address(0) on Invalid Signature**

- **Detect:** Raw `ecrecover(hash, v, r, s)` used without checking that the returned address is not `address(0)`. An invalid or malformed signature does not revert — `ecrecover` silently returns `address(0)`. If the code then checks `recovered == authorizedSigner` and `authorizedSigner` is uninitialized (defaults to `address(0)`), or if `permissions[recovered]` is read from a mapping that has a non-zero default for `address(0)` (e.g., from a prior `grantRole(ROLE, address(0))`), an attacker passes any garbage signature to gain privileges.
- **FP:** OpenZeppelin `ECDSA.recover()` used — it explicitly reverts when `ecrecover` returns `address(0)`. Explicit `require(recovered != address(0))` check present before any comparison or lookup.

**47. Griefing via Dust Deposits Resetting Timelocks or Cooldowns**

- **Detect:** Time-based lock, cooldown, or delay is reset on any deposit or interaction with no minimum-amount guard: `lastActionTime[user] = block.timestamp` inside a `deposit(uint256 amount)` with no `require(amount >= MIN_AMOUNT)`. Attacker calls `deposit(1)` repeatedly, just before the victim's lock expires, resetting the cooldown indefinitely at negligible cost. Variant: vault that checks `totalSupply > 0` before first depositor can join — attacker donates 1 wei to permanently inflate the share price and trap subsequent depositors; or a contract guarded by `require(address(this).balance > threshold)` that the attacker manipulates by sending dust.
- **FP:** Minimum deposit enforced unconditionally: `require(amount >= MIN_DEPOSIT)`. Cooldown reset only for the depositing user, not system-wide. Time lock assessed independently of deposit amounts on a per-user basis.

**48. Insufficient Gas Forwarding / 63/64 Rule Exploitation**

- **Detect:** Contract forwards an external call without enforcing a minimum gas budget: `target.call(data)` (no explicit gas) or `target.call{gas: userProvidedGas}(data)`. The EVM's 63/64 rule means the callee receives at most 63/64 of the remaining gas. In meta-transaction and relayer patterns, a malicious relayer provides just enough gas for the outer function to complete but not enough for the subcall to succeed. The subcall returns `(false, "")` — which the outer function may misread as a business-logic rejection, marking the user's transaction as "processed" while the actual effect never happened. Silently censors user intent while consuming their allocated gas/fee.
- **FP:** `gasleft()` validated against a minimum threshold before the subcall: `require(gasleft() >= minGas)`. Return value and return data both checked after the call. Relayer pattern uses EIP-2771 with a verified gas parameter that the recipient contract re-validates.

**49. Chainlink Feed Deprecation / Wrong Decimal Assumption**

- **Detect:** (a) Chainlink aggregator address is hardcoded in the constructor or an immutable with no admin path to update it. When Chainlink deprecates the feed and migrates to a new aggregator contract, the protocol continues reading from the frozen old feed, which may return a stale or zeroed price indefinitely. (b) Price normalization assumes `feed.decimals() == 8` (common for USD feeds) without calling `feed.decimals()` at runtime. Some feeds (e.g., ETH/ETH) return 18 decimals — the 10^10 scaling discrepancy produces wildly wrong collateral values, enabling instant over-borrowing or mass liquidations.
- **FP:** Feed address is updatable via a governance-gated setter. `feed.decimals()` called and stored; used to normalize `latestRoundData().answer` before any arithmetic. Deviation check against a secondary oracle rejects anomalous values.

**50. Fee-on-Transfer Token Accounting**

- **Detect:** Deposit recorded as `deposits[user] += amount` then `transferFrom(..., amount)`. Fee-on-transfer tokens (SAFEMOON, STA) cause the contract to receive `amount - fee` but record `amount`. Subsequent withdrawals drain other users.
- **FP:** Balance measured before/after transfer: `uint256 before = token.balanceOf(this); token.transferFrom(...); uint256 received = token.balanceOf(this) - before;` and `received` used for accounting.

**51. Rebasing / Elastic Supply Token Accounting**

- **Detect:** Contract holds rebasing tokens (stETH, AMPL, aTokens) and caches `token.balanceOf(this)` in a state variable used for future accounting. After a rebase, cached value diverges from actual balance.
- **FP:** Protocol enforces at the code level that rebasing tokens cannot be deposited (explicit revert or whitelist). Accounting always reads `balanceOf` live. Wrapper tokens (wstETH) used instead.

**52. ERC20 Non-Compliant: Return Values / Events**

- **Detect:** Custom `transfer()`/`transferFrom()` doesn't return `bool`, or always returns `true` on failure. `mint()` missing `Transfer(address(0), to, amount)` event. `burn()` missing `Transfer(from, address(0), amount)`. `approve()` missing `Approval` event. Breaks DEX and wallet composability.
- **FP:** OpenZeppelin `ERC20.sol` used as base with no custom overrides of the transfer/approve/event logic.

**53. Non-Standard ERC20 Return Values (USDT-style)**

- **Detect:** `require(token.transfer(to, amount))` reverts on tokens that return nothing (USDT, BNB). Or return value ignored entirely (silent failure on failed transfer). (SWC-104)
- **FP:** OpenZeppelin `SafeERC20.safeTransfer()`/`safeTransferFrom()` used throughout.

**54. Blacklistable or Pausable Token in Critical Payment Path**

- **Detect:** Protocol hard-codes or accepts USDC, USDT, or another token with admin-controlled blacklisting or global pause, and routes payments through a push model: `token.transfer(recipient, amount)`. If `recipient` is blacklisted by the token issuer, or the token is globally paused, every push to that address reverts — permanently bricking withdrawals, liquidations, fee collection, or reward claims. Attacker can weaponize this by ensuring a critical address (vault, fee receiver, required counterparty) is blacklisted. Also relevant: protocol sends fee to a fixed `feeRecipient` inside a state-changing function — if `feeRecipient` is blacklisted, the entire function is permanently DOSed.
- **FP:** Pull-over-push: recipients withdraw their own funds; a blacklisted recipient only blocks themselves. Skip-on-failure logic (`try/catch`) used for fee or reward distribution. Supported token whitelist explicitly excludes blacklistable/pausable tokens.

**55. EIP-2612 Permit Front-Run Causing DoS**

- **Detect:** Contract calls `token.permit(owner, spender, value, deadline, v, r, s)` inline as part of a combined permit-and-action function, with no `try/catch` around the permit call. The same permit signature can be submitted by anyone — if an attacker (or MEV bot) front-runs by submitting the permit signature first, the nonce is incremented; the subsequent victim transaction's inline `permit()` call then reverts (wrong nonce), causing the entire action to fail. Because the user only has the one signature, they may be permanently blocked from that code path.
- **FP:** Permit wrapped in `try { token.permit(...); } catch {}` — falls through and relies on pre-existing allowance if permit already consumed. Permit is a standalone user call; the main action function only calls `transferFrom` (not combined).

**56. ERC777 tokensToSend / tokensReceived Reentrancy**

- **Detect:** Contract calls `transfer()` or `transferFrom()` on a token that may implement ERC777 (registered via ERC1820 registry) before completing state updates. ERC777 fires a `tokensToSend` hook on the sender's registered hook contract and a `tokensReceived` hook on the recipient's — these callbacks trigger on plain ERC20-style `transfer()` calls, not just ETH. A recipient's `tokensReceived` or sender's `tokensToSend` can re-enter the calling contract before balances are updated. Pattern: `token.transferFrom(msg.sender, address(this), amount)` followed by state updates, or `token.transfer(user, amount)` before clearing user balance, with no `nonReentrant` guard and no ERC777 exclusion.
- **FP:** Strict CEI — all state committed before any token transfer. `nonReentrant` applied to all public entry points. Protocol enforces a token whitelist that explicitly excludes ERC777-compatible tokens.

**57. Token Decimal Mismatch in Cross-Token Arithmetic**

- **Detect:** Protocol multiplies or divides token amounts using a hardcoded `1e18` denominator or assumes all tokens share the same decimals. USDC has 6 decimals, WETH has 18 — a formula like `price = usdcAmount * 1e18 / wethAmount` is off by 1e12. Pattern: collateral ratio, LTV, interest rate, or exchange rate calculations that combine two tokens' amounts with no per-token decimal normalization. `token.decimals()` is never called, or is called but its result is not used in scaling factors.
- **FP:** All amounts normalized to a canonical precision (WAD/RAY) immediately after transfer, using each token's actual `decimals()`. Explicit normalization factor `10 ** (18 - token.decimals())` applied per token before any cross-token arithmetic. Protocol only supports tokens with identical, verified decimals.

**58. Zero-Amount Transfer Revert Breaking Distribution Logic**

- **Detect:** Contract calls `token.transfer(recipient, amount)` or `token.transferFrom(from, to, amount)` where `amount` can be zero — e.g., when fees round to 0, a user claims before any yield accrues, or a distribution loop pays out a zero share. Some non-standard ERC20 tokens (LEND, early BNB, certain stablecoins) include `require(amount > 0)` in their transfer logic and revert on zero-amount calls. Any fee distribution loop, reward claim, or conditional-payout path that omits a `if (amount > 0)` guard will permanently DoS on these tokens.
- **FP:** All transfer calls are preceded by `if (amount > 0)` or `require(amount > 0)`. Protocol enforces a minimum claim/distribution amount upstream. Supported token whitelist only includes tokens verified to accept zero-amount transfers (OZ ERC20 base allows them).

**59. Stale Cached ERC20 Balance from Direct Token Transfers**

- **Detect:** Contract tracks token holdings in a state variable (`totalDeposited`, `_reserves`, `cachedBalance`) that is only updated through the protocol's own deposit/receive functions. The actual `token.balanceOf(address(this))` can exceed the cached value via direct `token.transfer(contractAddress, amount)` calls made outside the protocol's accounting flow. When protocol logic uses the cached variable — not `balanceOf` live — for share pricing, collateral ratios, or withdrawal limits, an attacker donates tokens directly to inflate actual holdings, then exploits the gap between cached and real state (inflated share price, under-collateralized accounting). Distinct from ERC4626 first-depositor inflation attack (see erc4626/attack-vectors.md): applies to any contract with split accounting, not just vaults.
- **FP:** All accounting reads `token.balanceOf(address(this))` live — no cached balance variable used in financial math. Cached value is reconciled against `balanceOf` at the start of every state-changing function. Direct token transfers are explicitly considered in the accounting model (e.g., treated as protocol revenue, not phantom deposits).

**60. Merkle Tree Second Preimage Attack**

- **Detect:** `MerkleProof.verify(proof, root, leaf)` where the leaf is derived from variable-length or 32-byte user-supplied input without double-hashing or type-prefixing. An attacker can pass a 64-byte value (concatenation of two sibling hashes at an intermediate node) as if it were a leaf — the standard hash tree produces the same root, so verification passes with a shorter proof. Pattern: `leaf = keccak256(abi.encodePacked(account, amount))` without an outer hash or prefix; no length restriction enforced on leaf inputs.
- **FP:** Leaves are double-hashed (`keccak256(keccak256(data))`). Leaf includes a type prefix or domain tag that intermediate nodes cannot satisfy. Input length enforced to be ≠ 64 bytes. OpenZeppelin MerkleProof ≥ v4.9.2 with `processProofCalldata` or sorted-pair variant used correctly.

**61. Merkle Proof Reuse — Leaf Not Bound to Caller**

- **Detect:** Merkle proof accepted without tying the leaf to `msg.sender`. Pattern: `require(MerkleProof.verify(proof, root, keccak256(abi.encodePacked(amount))))` or leaf contains only an address that is not checked against `msg.sender`. Anyone who observes the proof in the mempool can front-run and claim the same entitlement by submitting it from a different address.
- **FP:** Leaf explicitly encodes the caller: `keccak256(abi.encodePacked(msg.sender, amount))`. Function validates that the leaf's embedded address equals `msg.sender` before acting. Proof is single-use and recorded as consumed after the first successful call.

**62. Diamond Proxy Cross-Facet Storage Collision**

- **Detect:** EIP-2535 Diamond proxy where two or more facets declare storage variables without EIP-7201 namespaced storage structs — each facet using plain `uint256 foo` or `mapping(...)` declarations that Solidity places at sequential storage slots 0, 1, 2, …. Different facets independently start at slot 0, so both write to the same slot. Also flag: facet uses a library that writes to storage without EIP-7201 namespacing.
- **FP:** All facets store state exclusively in a single `DiamondStorage` struct retrieved via `assembly { ds.slot := DIAMOND_STORAGE_POSITION }` using a namespaced position (EIP-7201 formula). No facet declares top-level state variables. OpenZeppelin's ERC-7201 `@custom:storage-location` pattern used correctly.

**63. Nested Mapping Inside Struct Not Cleared on `delete`**

- **Detect:** `delete myMapping[key]` or `delete myArray[i]` where the deleted item is a struct containing a `mapping` or a dynamic array. Solidity's `delete` zeroes primitive fields but does not recursively clear mappings — the nested mapping's entries persist in storage. If the same key is later reused (e.g., a re-deposited user, re-created proposal), old mapping values are unexpectedly visible. Pattern: struct with `mapping(address => uint256)` or `uint256[]` field; `delete` called on the struct without manually iterating and clearing the nested mapping.
- **FP:** Nested mapping manually cleared before `delete` (iterate and zero every entry). Struct key is never reused after deletion. Codebase explicitly accounts for residual mapping values in subsequent reads (always initialises before use).

**64. Small-Type Arithmetic Overflow Before Upcast**

- **Detect:** Arithmetic expression operates on `uint8`, `uint16`, `uint32`, `int8`, or other sub-256-bit types before the result is assigned to a wider type. Pattern: `uint256 result = a * b` where `a` and `b` are `uint8` — multiplication executes in `uint8` and overflows silently (wraps mod 256) before widening. Also: ternary returning a small literal `(condition ? 1 : 0)` inferred as `uint8`; addition `uint16(x) + uint16(y)` assigned to `uint32`. Underflow possible for signed sub-types.
- **FP:** Each operand is explicitly upcast before the operation: `uint256(a) * uint256(b)`. SafeCast used. Solidity 0.8+ overflow protection applies only within the type of the expression — if both operands are `uint8`, the check is still on `uint8` range, not `uint256`.

**65. Front-Running Exact-Zero Balance Check with Dust Transfer**

- **Detect:** An `external` or `public` function contains `require(token.balanceOf(address(this)) == 0)`, `require(address(this).balance == 0)`, or any strict equality check against a zero balance that gates a state transition (e.g., starting an auction, initializing a pool, opening a deposit round). An attacker front-runs the legitimate caller's transaction by sending a dust amount of the token or ETH to the contract, making the balance non-zero and causing the victim's transaction to revert. The attack is repeatable at negligible cost, creating a permanent DoS on the guarded function. Distinct from Vector 40 (force-feeding ETH to break invariants) — this targets the zero-check gate itself as a griefing/DoS vector rather than inflating a balance used in financial math.
- **FP:** Check uses `<=` threshold instead of `== 0` (e.g., `require(balance <= DUST_THRESHOLD)`). Function is access-controlled so only a trusted caller can trigger it. Balance is tracked via an internal accounting variable that ignores direct transfers, not via `balanceOf` or `address(this).balance`.
