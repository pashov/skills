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

- **Detect:** Time-sensitive function can be blocked by filling blocks. Related: relayer pattern forwards calls without checking `gasleft()` - exploits 63/64 rule where the subcall fails silently and is marked as "sent." (SWC-126)
- **FP:** `gasleft()` checked explicitly before forwarding with a minimum gas threshold that guarantees subcall completion.

**7. Spot Price Oracle from AMM**

- **Detect:** Price computed from AMM reserves directly: `price = reserve0 / reserve1`, `getAmountsOut()`, `getReserves()`. Any lending, liquidation, or collateral logic built on spot price is flash-loan exploitable atomically.
- **FP:** TWAP oracle with a 30-minute or longer observation window. Chainlink or Pyth as primary source.

**8. abi.encodePacked Hash Collision with Dynamic Types**

- **Detect:** `keccak256(abi.encodePacked(a, b, ...))` where two or more arguments are dynamic types (`string`, `bytes`, or dynamic arrays such as `uint[]`, `address[]`). `abi.encodePacked` concatenates raw bytes without length prefixes, so `("AB","CD")`, `("A","BCD")`, and `("ABC","D")` all produce the same byte sequence `0x41424344` and thus the same hash. If the hash is used for permit/signature verification, access control key derivation, or uniqueness enforcement (mapping keys, nullifiers), an attacker crafts an alternative input that collides with a legitimate hash and gains the same privileges.
- **FP:** `abi.encode()` used instead — each argument is ABI-padded and length-prefixed, eliminating ambiguity. Only one argument is a dynamic type (no two dynamic types to collide between). All arguments are fixed-size types (`uint256`, `address`, `bytes32`).

**9. Cross-Contract Reentrancy**

- **Detect:** Two separate contracts share logical state (e.g., balances in A, collateral check in B). A makes an external call before syncing the state B reads. A's `ReentrancyGuard` does not protect B.
- **FP:** State B reads is synchronized before A's external call. No re-entry path exists from A's external callee back into B — verified by tracing the full call graph.

**10. UUPS Implementation Not Initialized / selfdestruct Risk**

- **Detect:** UUPS implementation deployed without `_disableInitializers()` in constructor. Anyone can call `initialize()` on the bare implementation, claim ownership, call `upgradeTo(maliciousImpl)` with `selfdestruct`, destroying all proxies that point to it.
- **FP:** Constructor calls `_disableInitializers()`. Implementation verifies it's being called via a proxy before executing any logic.

**11. Integer Overflow / Underflow**

- **Detect:** Arithmetic inside `unchecked {}` blocks (Solidity ≥0.8) that could over/underflow: subtraction without a prior `require(amount <= balance)`, multiplication of two large values. Any arithmetic in Solidity <0.8 without SafeMath. (SWC-101)
- **FP:** Value range is provably bounded by earlier checks that appear in the same function before the unchecked block. `unchecked` used exclusively for loop counter increments of the form `++i` where `i < arr.length`, making overflow structurally impossible.

**12. DoS via Push Payment to Rejecting Contract**

- **Detect:** ETH/token distribution in a single loop using push model (`recipient.call{value:}("")`). If any recipient reverts on receive, the entire loop reverts. Also: `transfer()`/`send()` to contracts with expensive `fallback()`. (SWC-113)
- **FP:** Pull-over-push pattern used — recipients withdraw their own funds. Loop uses `try/catch` and continues on failure.

**13. Weak On-Chain Randomness**

- **Detect:** Randomness from `block.prevrandao` (RANDAO, validator-influenceable), `blockhash(block.number - 1)` (known before inclusion), `block.timestamp`, `block.coinbase`, or combinations. (SWC-120)
- **FP:** Chainlink VRF v2+ used. Commit-reveal scheme with future-block reveal and a meaningful economic penalty (slashing or bond forfeiture) enforced in code for non-reveal.

**14. Missing or Incorrect Access Modifier**

- **Detect:** State-changing function (`setOwner`, `withdrawFunds`, `mint`, `pause`, `setOracle`, `updateFees`) has no access guard, or modifier references an uninitialized variable. `public`/`external` visibility on privileged operations with no restriction.
- **FP:** Function is genuinely permissionless by design — any caller can legitimately invoke it and the worst-case outcome is a non-critical state transition (e.g., triggering a public distribution, settling an open auction, or advancing a time-locked process that anyone can advance).

**15. Proxy Storage Slot Collision**

- **Detect:** Proxy stores `implementation`/`admin` at sequential slots (0, 1) and implementation contract also declares variables from slot 0. Implementation's slot 0 write overwrites the proxy's `implementation` pointer.
- **FP:** Proxy uses EIP-1967 slots (`keccak256("eip1967.proxy.implementation") - 1`). OpenZeppelin Transparent or UUPS proxy pattern used correctly.

**16. Off-By-One in Bounds or Range Checks**

- **Detect:** (1) Loop upper bound uses `<=` instead of `<` on an array index: `for (uint i = 0; i <= arr.length; i++)` — accesses `arr[arr.length]` on the final iteration, reverting or reading uninitialized memory. (2) `arr[arr.length - 1]` or `arr[index - 1]` without a preceding `require(arr.length > 0)` / `require(index > 0)` — in `unchecked` blocks the underflow silently wraps to a huge index. (3) Inclusive/exclusive boundary confusion in financial logic: `require(block.timestamp >= vestingEnd)` vs. `> vestingEnd`, or `require(amount <= MAX)` where MAX was intended as exclusive — one unit of difference causes early unlock or allows a boundary-exceeding deposit. (4) Cumulative distribution: allocating a total across N recipients using integer division, where rounding errors accumulate and the final recipient receives more or less than intended.
- **FP:** Loop bounds verified correct by an explicit in-code invariant comment that explains the boundary choice. Last-element access is immediately preceded by a non-zero length check in the same block.

**17. ERC4626 Inflation Attack (First Depositor)**

- **Detect:** Vault shares math: `shares = assets * totalSupply / totalAssets`. When `totalSupply == 0`, attacker deposits 1 wei, donates large amount to vault, victim's deposit rounds to 0 shares. No virtual offset or dead shares protection.
- **FP:** OpenZeppelin ERC4626 with `_decimalsOffset()` override. Dead shares minted to `address(0)` at init.

**18. Chainlink Staleness / No Validity Checks**

- **Detect:** `latestRoundData()` called but any of these checks are missing: `answer > 0`, `updatedAt > block.timestamp - MAX_STALENESS`, `answeredInRound >= roundId`, fallback on failure.
- **FP:** All four checks present. Circuit breaker or fallback oracle used when any check fails.

**19. Single-Function Reentrancy**

- **Detect:** External call (`call{value:}`, `transfer`, `send`, `safeTransfer`, `safeTransferFrom`) happens _before_ state update (balance set to 0, flag set, counter decremented). Classic: check-external-effect instead of check-effect-external.
- **FP:** State updated before the call (CEI followed). `nonReentrant` modifier present. Callee is a hardcoded immutable address of a contract whose receive/fallback is known to not re-enter.

**20. Function Selector Clash in Proxy**

- **Detect:** Proxy and implementation share a 4-byte function selector collision. A call intended for the implementation gets routed to the proxy's own function (or vice versa), silently executing the wrong logic.
- **FP:** Transparent proxy pattern used (admin calls always hit proxy admin; user calls always delegate, eliminating the clash for the user-facing surface).

**21. Fee-on-Transfer Token Accounting**

- **Detect:** Deposit recorded as `deposits[user] += amount` then `transferFrom(..., amount)`. Fee-on-transfer tokens (SAFEMOON, STA) cause the contract to receive `amount - fee` but record `amount`. Subsequent withdrawals drain other users.
- **FP:** Balance measured before/after transfer: `uint256 before = token.balanceOf(this); token.transferFrom(...); uint256 received = token.balanceOf(this) - before;` and `received` used for accounting.

**22. Missing Nonce (Signature Replay)**

- **Detect:** Signed message has no per-user nonce, or nonce is present in the struct but never stored/incremented after use. Same valid signature can be submitted multiple times. (SWC-121)
- **FP:** Monotonic per-signer nonce included in signed payload, stored, checked for reuse, incremented atomically. `usedSignatures[hash]` mapping invalidates after first use.

**23. Rebasing / Elastic Supply Token Accounting**

- **Detect:** Contract holds rebasing tokens (stETH, AMPL, aTokens) and caches `token.balanceOf(this)` in a state variable used for future accounting. After a rebase, cached value diverges from actual balance.
- **FP:** Protocol enforces at the code level that rebasing tokens cannot be deposited (explicit revert or whitelist). Accounting always reads `balanceOf` live. Wrapper tokens (wstETH) used instead.

**24. tx.origin Authentication**

- **Detect:** `require(tx.origin == owner)` or `require(tx.origin == authorized)` used for authentication. Vulnerable to phishing via malicious intermediary contract.
- **FP:** `tx.origin == msg.sender` used only to assert caller is not a contract (anti-bot pattern, not auth).

**25. ERC721 Unsafe Transfer to Non-Receiver**

- **Detect:** `_transfer()` (unsafe) used instead of `_safeTransfer()`, or `_mint()` instead of `_safeMint()`, sending NFTs to contracts that may not implement `IERC721Receiver`. Tokens permanently locked in the recipient contract.
- **FP:** All transfer and mint paths use `safeTransferFrom` or `_safeMint`, which perform the `onERC721Received` callback check. Function is `nonReentrant` to prevent callback abuse.

**26. L2 Sequencer Uptime Not Checked**

- **Detect:** Contract on Arbitrum/Optimism/Base/etc. uses Chainlink feeds but does not query the L2 Sequencer Uptime Feed before consuming prices. Stale data during sequencer downtime can trigger wrong liquidations.
- **FP:** Sequencer uptime feed queried explicitly (`answer == 0` = up), with a grace period enforced after restart.

**27. Precision Loss - Division Before Multiplication**

- **Detect:** Expression `(a / b) * c` in integer math. Division truncates first, then multiplication amplifies the error. Common in fee calculations: `fee = (amount / 10000) * bps`. Correct form: `(a * c) / b`.
- **FP:** `a` is provably divisible by `b` — enforced by a preceding explicit check (e.g., `require(a % b == 0)`) or by mathematical construction visible in the code.

**28. Return Bomb (Returndata Copy DoS)**

- **Detect:** `(bool success, bytes memory data) = target.call(payload)` where `target` is user-supplied or unconstrained. Malicious target returns huge returndata; copying it costs enormous gas.
- **FP:** Returndata not copied (`assembly { success := call(...) }` without copy, or gas-limited call). Callee is a hardcoded immutable trusted contract.

**29. Flash Loan-Assisted Price Manipulation**

- **Detect:** A function reads price/ratio from an on-chain source (AMM reserves, vault `totalAssets()`), and that source can be manipulated atomically in the same tx via flash loan + swap. Attacker sequence: borrow → move price → call function → restore → repay.
- **FP:** Price source is TWAP with a 30-minute or longer observation window. Multi-block cooldown enforced between price reads. Function can only be called in a separate block from any state that could be manipulated.

**30. msg.value Reuse in Loop / Multicall**

- **Detect:** `msg.value` read inside a loop body, or inside a `delegatecall`-based multicall where each sub-call is dispatched via `address(this).delegatecall(data[i])`. `msg.value` is a transaction-level constant — it does not decrease as ETH is "spent" within the call. Direct loop: `for (uint i = 0; i < n; i++) { deposit(msg.value); }` credits `n × msg.value` while only `msg.value` was sent. Delegatecall multicall: each sub-call inherits the original `msg.value`, so including the same payable function `n` times receives credit for `n × msg.value` with one payment.
- **FP:** `msg.value` captured into a local variable before the loop; that local is decremented per iteration and the contract enforces that total allocated equals the captured value. Function is non-payable. Multicall dispatches via `call` (not `delegatecall`), so each sub-call only receives ETH explicitly forwarded to it.

**31. ERC-2771 + Multicall msg.sender Spoofing**

- **Detect:** Contract implements both ERC-2771 (`_msgSender()` reads last 20 bytes of calldata from trusted forwarder) and a `multicall` using `delegatecall`. Attacker crafts calldata via the trusted forwarder where subcall data's last 20 bytes are a victim address. `_msgSender()` in the subcall resolves to the victim.
- **FP:** Multicall explicitly handles ERC-2771 context suffix per subcall (OpenZeppelin patched version). Contract uses `msg.sender` directly, not `_msgSender()`. No trusted forwarder is set.

**32. Read-Only Reentrancy**

- **Detect:** Protocol calls a `view` function (e.g., `get_virtual_price()`, `totalAssets()`, `convertToAssets()`) on an external contract from within a callback (`receive`, `onERC721Received`, flash loan hook). The external contract has no reentrancy guard on its view functions - a mid-execution call can return a transitional/manipulated value.
- **FP:** External contract's view functions are themselves `nonReentrant`. Protocol uses Chainlink or another oracle instead of the external view. External contract's reentrancy lock is public and the protocol reads and enforces it before calling any view function.

**33. Block Number as Timestamp Approximation**

- **Detect:** Time computed as `(block.number - startBlock) * 13` assuming fixed block times. Post-Merge Ethereum has variable block times; Polygon/Arbitrum/BSC have very different averages. Causes wrong interest accrual, vesting, or reward calculations.
- **FP:** `block.timestamp` used instead of `block.number` for all time-sensitive calculations.

**34. Missing chainId / Message Uniqueness in Bridge**

- **Detect:** Bridge/messaging contract processes incoming messages but lacks: `processedMessages[messageHash]` check (replay), `destinationChainId == block.chainid` validation, or source chain ID in the message hash. A message from Chain A to Chain B can be replayed on Chain C, or submitted twice on the destination.
- **FP:** Each message has a unique nonce per sender. Hash of `(sourceChain, destinationChain, nonce, payload)` stored in `processedMessages` and checked before execution. Contract address included in message hash.

**35. ERC20 Non-Compliant: Return Values / Events**

- **Detect:** Custom `transfer()`/`transferFrom()` doesn't return `bool`, or always returns `true` on failure. `mint()` missing `Transfer(address(0), to, amount)` event. `burn()` missing `Transfer(from, address(0), amount)`. `approve()` missing `Approval` event. Breaks DEX and wallet composability.
- **FP:** OpenZeppelin `ERC20.sol` used as base with no custom overrides of the transfer/approve/event logic.

**36. Rounding in Favor of the Attacker**

- **Detect:** `shares = assets / pricePerShare` rounds down for the user but up for shares redeemed. First-depositor vault manipulation: when `totalSupply == 0`, attacker donates to inflate `totalAssets`, subsequent deposits round to 0 shares. Division without explicit rounding direction.
- **FP:** `Math.mulDiv(a, b, c, Rounding.Up)` used with explicit rounding direction appropriate for the operation. Virtual offset (OpenZeppelin ERC4626 `_decimalsOffset()`) prevents first-depositor attack. Dead shares minted to `address(0)` at init.

**37. Cross-Function Reentrancy**

- **Detect:** Two functions share a state variable. Function A makes an external call before updating shared state; Function B reads or modifies that same state. `nonReentrant` on A but not B.
- **FP:** Both functions are guarded by the same contract-level mutex. Shared state fully updated before any external call in A.

**38. DoS via Unbounded Loop**

- **Detect:** Loop iterates over an array that grows with user interaction and is unbounded: `for (uint i = 0; i < users.length; i++) { ... }`. If anyone can push to `users`, the function will eventually hit the block gas limit. (SWC-128)
- **FP:** Array length capped at insertion time with a `require(arr.length < MAX)` check. Loop iterates a fixed small constant count.

**39. Delegatecall to Untrusted / User-Supplied Callee**

- **Detect:** `address(target).delegatecall(data)` where `target` is user-provided or unconstrained. Callee executes in the caller's storage context - can overwrite owner, balances, call `selfdestruct`. (SWC-112)
- **FP:** `target` is a hardcoded immutable verified library address that cannot be changed after deployment.

**40. Non-Standard ERC20 Return Values (USDT-style)**

- **Detect:** `require(token.transfer(to, amount))` reverts on tokens that return nothing (USDT, BNB). Or return value ignored entirely (silent failure on failed transfer). (SWC-104)
- **FP:** OpenZeppelin `SafeERC20.safeTransfer()`/`safeTransferFrom()` used throughout.

**41. Unsafe Downcast / Integer Truncation**

- **Detect:** Explicit cast to smaller type without bounds check: `uint128(largeUint256)`. Solidity ≥0.8 silently truncates on downcast (does NOT revert). Especially dangerous in price feeds, share calculations, timestamps.
- **FP:** Value validated against the target type's maximum before cast (e.g., `require(x <= type(uint128).max)`). OpenZeppelin `SafeCast` library used.

**42. Block Timestamp Dependence**

- **Detect:** `block.timestamp` used for game outcomes, randomness (`block.timestamp % N`), or auction timing where a 15-second manipulation changes the outcome. (SWC-116)
- **FP:** Timestamp used only for periods spanning hours or days, where 15-second validator manipulation has no meaningful impact on the outcome. Timestamp used only for event logging with no effect on state or logic.

**43. Missing or Expired Deadline on Swaps**

- **Detect:** `deadline = block.timestamp` (computed inside the tx, always valid), `deadline = type(uint256).max`, or no deadline at all. Transaction can be held in mempool and executed at any future price.
- **FP:** Deadline passed as a parameter by the caller, validated `>= block.timestamp` on-chain, and set to a meaningful near-future timestamp by the user.

**44. Missing Storage Gap in Upgradeable Base Contract**

- **Detect:** Upgradeable base contract has no `uint256[N] private __gap;` at the end. A future version adding state variables to the base shifts the derived contract's storage layout, overwriting existing variables.
- **FP:** EIP-1967 namespaced storage slots used for all variables in the base contract. Single-contract (non-inherited) implementation where new variables can only be appended safely.

**45. Improper Flash Loan Callback Validation**

- **Detect:** `onFlashLoan` callback does not verify `msg.sender == lendingPool`, or does not verify `initiator`, or does not check `token`/`amount` match. Attacker can call the callback directly without a real flash loan.
- **FP:** Both `msg.sender == address(lendingPool)` and `initiator == address(this)` are validated. Token and amount checked against pre-stored values.

**46. On-Chain Randomness Frontrunning**

- **Detect:** Randomness from `block.prevrandao`, `blockhash()`, `block.timestamp`, `block.coinbase`, or combinations. Validators can influence RANDAO; all block values are visible before tx inclusion. (SWC-120)
- **FP:** Chainlink VRF v2+ used. Commit-reveal scheme with future-block reveal and a meaningful economic penalty enforced in code for non-reveal.

**47. Unprotected Initializer (Upgradeable Contract)**

- **Detect:** `initialize()` function has no `initializer` modifier, or constructor does not call `_disableInitializers()`. Anyone can call `initialize()` on the bare implementation contract, claim ownership, and self-destruct it.
- **FP:** Constructor calls `_disableInitializers()`. `initializer` modifier from OpenZeppelin `Initializable` is present and correctly gates the function.

**48. Signature Malleability**

- **Detect:** Raw `ecrecover(hash, v, r, s)` used without validating `s <= 0x7FFF...20A0`. Both `(v,r,s)` and `(v',r,s')` recover the same address. If signatures are used as unique identifiers (stored to prevent replay), a malleable variant bypasses the uniqueness check. (SWC-117)
- **FP:** OpenZeppelin `ECDSA.recover()` used (validates `s` range and `v`). Full message hash used as dedup key, not the signature bytes.

**49. Transient Storage Low-Gas Reentrancy (EIP-1153)**

- **Detect:** Contract uses `transfer()` or `send()` (2300-gas stipend) as its reentrancy protection, AND either the contract or a called external contract uses `transient` variables or `TSTORE`/`TLOAD` in assembly. Post-Cancun (Solidity ≥0.8.24), `TSTORE` succeeds with fewer than 2300 gas — unlike `SSTORE`, which is blocked by EIP-2200. The 2300-gas-as-reentrancy-guard assumption is broken. Second pattern: transient reentrancy lock that is not explicitly cleared at the end of the call frame. Because transient storage persists for the entire transaction (not just the call), if the contract is invoked again in the same tx (e.g., via multicall or flash loan callback), the transient lock from the first invocation is still set, causing a permanent DoS for the remainder of the tx.
- **FP:** Reentrancy protection uses an explicit `nonReentrant` modifier backed by a regular storage slot (or a correctly implemented transient mutex cleared at call end). CEI pattern followed unconditionally regardless of gas stipend. Contract does not use transient storage at all.

**50. Force-Feeding ETH via selfdestruct or coinbase**

- **Detect:** Business logic relies on `address(this).balance` for invariant checks, share/deposit accounting, or as a denominator: `require(address(this).balance == trackingVar)`, `shares = msg.value * totalSupply / address(this).balance`. ETH can be force-sent without triggering `receive()`/`fallback()` via: (1) `selfdestruct(payable(target))` — even if target has no payable functions; (2) pre-deployment: computing a contract's deterministic address and sending ETH before it is deployed; (3) being set as the `coinbase` address for a mined block. Forced ETH inflates the balance above expected values, breaking any invariant or ratio built on it.
- **FP:** All accounting uses a private `uint256 _deposited` variable incremented only inside payable functions — never `address(this).balance`. `address(this).balance` appears only in informational view functions, not in guards or financial math.

**51. CREATE2 Address Reuse After selfdestruct**

- **Detect:** Protocol whitelists, approves, or trusts a contract at an address derived from CREATE2. Attacker controls the salt or factory. Pre-EIP-6780: attacker deploys a benign contract, earns trust (e.g., token approval, whitelist entry, governance power), calls `selfdestruct`, then redeploys a malicious contract to the identical address. The stored approval/whitelist entry now points to the malicious code. Pattern: `create2Factory.deploy(salt, initcode)` where `salt` is user-supplied or predictable, combined with no bytecode-hash verification at trust-grant time.
- **FP:** Post-Dencun (EIP-6780): `selfdestruct` no longer destroys code unless it occurs in the same transaction as contract creation, effectively eliminating the redeploy path on mainnet. Bytecode hash of the approved contract recorded at approval time and re-verified before each privileged call. No user-controlled CREATE2 salt accepted by the factory.

**52. extcodesize Zero / isContract Bypass in Constructor**

- **Detect:** Access control or anti-bot check uses `require(msg.sender.code.length == 0)` or assembly `extcodesize(caller())` to assert the caller is an EOA. During a contract's constructor execution, `extcodesize` of that contract's own address returns zero — no code is stored until construction finishes. An attacker deploys a contract whose constructor calls the protected function, bypassing the check. Common targets: minting limits, presale allocation caps, "no smart contracts" whitelist enforcement.
- **FP:** The check is informational only and not security-critical. The function is independently protected by a merkle-proof allowlist, signed permit, or other mechanism that cannot be satisfied inside a constructor. Protocol explicitly states and accepts on-chain contract interaction.

**53. Multi-Block TWAP Oracle Manipulation**

- **Detect:** Protocol uses a Uniswap V2 or V3 TWAP with an observation window shorter than 30 minutes (~150 blocks). Post-Merge PoS validators who are elected to propose consecutive blocks can hold an AMM pool in a manipulated state across multiple blocks with no flash-loan repayment pressure. Each held block contributes a manipulated price sample to the TWAP accumulator. With short windows (e.g., 5–10 minutes), controlling 2–3 consecutive blocks shifts the TWAP enough to trigger profitable liquidations or over-collateralized borrows. Cost: only the capital to move the pool, held for a few blocks — far cheaper than equivalent single-block manipulation.
- **FP:** TWAP window ≥ 30 minutes. Chainlink or Pyth used as the price source instead of AMM TWAP. Protocol uses max-deviation circuit breaker that rejects price updates deviating more than X% from a secondary source.

**54. Blacklistable or Pausable Token in Critical Payment Path**

- **Detect:** Protocol hard-codes or accepts USDC, USDT, or another token with admin-controlled blacklisting or global pause, and routes payments through a push model: `token.transfer(recipient, amount)`. If `recipient` is blacklisted by the token issuer, or the token is globally paused, every push to that address reverts — permanently bricking withdrawals, liquidations, fee collection, or reward claims. Attacker can weaponize this by ensuring a critical address (vault, fee receiver, required counterparty) is blacklisted. Also relevant: protocol sends fee to a fixed `feeRecipient` inside a state-changing function — if `feeRecipient` is blacklisted, the entire function is permanently DOSed.
- **FP:** Pull-over-push: recipients withdraw their own funds; a blacklisted recipient only blocks themselves. Skip-on-failure logic (`try/catch`) used for fee or reward distribution. Supported token whitelist explicitly excludes blacklistable/pausable tokens.

**55. Missing Input Validation on Critical Setters**

- **Detect:** Admin functions set numeric parameters with no validation: `setFee(uint256 fee)` with no `require(fee <= MAX_FEE)`; `setOracle(address o)` with no interface check. A misconfigured call — wrong argument, value exceeding 100% — silently bricks fee collection, enables 100% fee extraction, or points the oracle to a dead address. 
- **FP:** Every setter has explicit `require` bounds on all parameters. Numeric parameters validated against documented protocol constants. 

**56. Staking Reward Front-Run by New Depositor**

- **Detect:** Reward checkpoint (`rewardPerTokenStored`, `lastUpdateTime`) is updated lazily — only when a user action triggers it — and the update happens AFTER the new stake is recorded in `_balances` or `totalSupply`. A new staker can join immediately before `notifyRewardAmount()` is called (or immediately before a large pending reward accrues), and the checkpoint then distributes the new rewards pro-rata over a supply that includes the attacker's stake. The attacker earns rewards for a period they were not staked. Pattern: `_balances[user] += amount; totalSupply += amount;` executed before `updateReward()`.
- **FP:** `updateReward(account)` is the very first step of `stake()` — executed before any balance update — so new stakers start from the current `rewardPerTokenStored` and earn nothing retroactively. `rewardPerTokenPaid[user]` correctly tracks per-user checkpoint.

**57. EIP-2612 Permit Front-Run Causing DoS**

- **Detect:** Contract calls `token.permit(owner, spender, value, deadline, v, r, s)` inline as part of a combined permit-and-action function, with no `try/catch` around the permit call. The same permit signature can be submitted by anyone — if an attacker (or MEV bot) front-runs by submitting the permit signature first, the nonce is incremented; the subsequent victim transaction's inline `permit()` call then reverts (wrong nonce), causing the entire action to fail. Because the user only has the one signature, they may be permanently blocked from that code path.
- **FP:** Permit wrapped in `try { token.permit(...); } catch {}` — falls through and relies on pre-existing allowance if permit already consumed. Permit is a standalone user call; the main action function only calls `transferFrom` (not combined).

**58. ecrecover Returns address(0) on Invalid Signature**

- **Detect:** Raw `ecrecover(hash, v, r, s)` used without checking that the returned address is not `address(0)`. An invalid or malformed signature does not revert — `ecrecover` silently returns `address(0)`. If the code then checks `recovered == authorizedSigner` and `authorizedSigner` is uninitialized (defaults to `address(0)`), or if `permissions[recovered]` is read from a mapping that has a non-zero default for `address(0)` (e.g., from a prior `grantRole(ROLE, address(0))`), an attacker passes any garbage signature to gain privileges.
- **FP:** OpenZeppelin `ECDSA.recover()` used — it explicitly reverts when `ecrecover` returns `address(0)`. Explicit `require(recovered != address(0))` check present before any comparison or lookup.

**59. Griefing via Dust Deposits Resetting Timelocks or Cooldowns**

- **Detect:** Time-based lock, cooldown, or delay is reset on any deposit or interaction with no minimum-amount guard: `lastActionTime[user] = block.timestamp` inside a `deposit(uint256 amount)` with no `require(amount >= MIN_AMOUNT)`. Attacker calls `deposit(1)` repeatedly, just before the victim's lock expires, resetting the cooldown indefinitely at negligible cost. Variant: vault that checks `totalSupply > 0` before first depositor can join — attacker donates 1 wei to permanently inflate the share price and trap subsequent depositors; or a contract guarded by `require(address(this).balance > threshold)` that the attacker manipulates by sending dust.
- **FP:** Minimum deposit enforced unconditionally: `require(amount >= MIN_DEPOSIT)`. Cooldown reset only for the depositing user, not system-wide. Time lock assessed independently of deposit amounts on a per-user basis.

**60. Insufficient Gas Forwarding / 63/64 Rule Exploitation**

- **Detect:** Contract forwards an external call without enforcing a minimum gas budget: `target.call(data)` (no explicit gas) or `target.call{gas: userProvidedGas}(data)`. The EVM's 63/64 rule means the callee receives at most 63/64 of the remaining gas. In meta-transaction and relayer patterns, a malicious relayer provides just enough gas for the outer function to complete but not enough for the subcall to succeed. The subcall returns `(false, "")` — which the outer function may misread as a business-logic rejection, marking the user's transaction as "processed" while the actual effect never happened. Silently censors user intent while consuming their allocated gas/fee.
- **FP:** `gasleft()` validated against a minimum threshold before the subcall: `require(gasleft() >= minGas)`. Return value and return data both checked after the call. Relayer pattern uses EIP-2771 with a verified gas parameter that the recipient contract re-validates.

**61. Chainlink Feed Deprecation / Wrong Decimal Assumption**

- **Detect:** (a) Chainlink aggregator address is hardcoded in the constructor or an immutable with no admin path to update it. When Chainlink deprecates the feed and migrates to a new aggregator contract, the protocol continues reading from the frozen old feed, which may return a stale or zeroed price indefinitely. (b) Price normalization assumes `feed.decimals() == 8` (common for USD feeds) without calling `feed.decimals()` at runtime. Some feeds (e.g., ETH/ETH) return 18 decimals — the 10^10 scaling discrepancy produces wildly wrong collateral values, enabling instant over-borrowing or mass liquidations.
- **FP:** Feed address is updatable via a governance-gated setter. `feed.decimals()` called and stored; used to normalize `latestRoundData().answer` before any arithmetic. Deviation check against a secondary oracle rejects anomalous values.

**62. ERC4626 Preview Rounding Direction Violation**

- **Detect:** `previewDeposit(a)` returns more shares than `deposit(a)` actually mints; `previewRedeem(s)` returns more assets than `redeem(s)` actually transfers; `previewMint(s)` returns fewer assets than `mint(s)` actually charges; `previewWithdraw(a)` returns fewer shares than `withdraw(a)` actually burns. EIP-4626 mandates that preview functions round in the vault's favor — they must never overstate what the user receives or understate what the user pays. Custom `_convertToShares`/`_convertToAssets` implementations that apply the wrong `Math.mulDiv` rounding direction (e.g., `Rounding.Ceil` when `Rounding.Floor` is required) violate this. Integrators that use preview return values for slippage checks will pass with an incorrect expectation and receive less than they planned for.
- **FP:** OpenZeppelin ERC4626 base used without overriding `_convertToShares`/`_convertToAssets`. Custom implementation explicitly passes `Math.Rounding.Floor` for share issuance (deposit/previewDeposit) and `Math.Rounding.Ceil` for share burning (withdraw/previewWithdraw).

**63. ERC4626 Round-Trip Profit Extraction**

- **Detect:** A full operation cycle yields strictly more than the starting amount: `redeem(deposit(a)) > a`, `deposit(redeem(s)) > s`, `mint(withdraw(a)) > a`, or `withdraw(mint(s)) > s`. Possible when rounding errors in `_convertToShares` and `_convertToAssets` both truncate in the user's favor, so no value is lost in either direction and a net gain emerges with large inputs or a manipulated share price. Combined with the first-depositor inflation attack (Vector 17), the share price can be engineered so that round-trip profit scales with the amount — enabling systematic value extraction.
- **FP:** Rounding directions satisfy EIP-4626: shares issued on deposit/mint round down (vault-favorable), shares burned on withdraw/redeem round up (vault-favorable). OpenZeppelin ERC4626 with `_decimalsOffset()` used.

**64. ERC4626 Caller-Dependent Conversion Functions**

- **Detect:** `convertToShares()` or `convertToAssets()` branches on `msg.sender`-specific state — per-user fee tiers, whitelist status, individual balances, or allowances — causing identical inputs to return different outputs for different callers. EIP-4626 requires these functions to be caller-independent. Downstream aggregators, routers, and on-chain interfaces call these functions to size positions before routing; a caller-dependent result silently produces wrong sizing for some users.
- **FP:** Implementation reads only global vault state (`totalSupply()`, `totalAssets()`, protocol-wide fee constants) with no `msg.sender`-dependent branching.

**65. ERC4626 Missing Allowance Check in withdraw() / redeem()**

- **Detect:** `withdraw(assets, receiver, owner)` or `redeem(shares, receiver, owner)` where `msg.sender != owner` but no allowance validation or decrement is performed before burning shares. EIP-4626 requires that if `caller != owner`, the caller must hold sufficient share approval; the allowance must be consumed atomically. Missing this check lets any address burn shares from an arbitrary owner and redirect the assets to any receiver — equivalent to an unchecked `transferFrom`.
- **FP:** `_spendAllowance(owner, caller, shares)` called unconditionally before the share burn when `caller != owner`. OpenZeppelin ERC4626 used without custom overrides of `withdraw`/`redeem`.

---

## Severity Guide

| Severity     | Criteria                                                                     |
| ------------ | ---------------------------------------------------------------------------- |
| **CRITICAL** | Direct theft of funds, permanent loss of user assets, protocol takeover      |
| **HIGH**     | Significant loss possible with moderate preconditions, broken core invariant |
| **MEDIUM**   | Limited loss or requires specific conditions; DoS without permanent damage   |
| **LOW**      | Best practice violation, minor accounting issue, limited impact              |
