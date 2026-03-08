# Attack Vectors Reference (5/5)

210 total attack vectors — Extended patterns from DeFi protocol analysis, L2 considerations, and behavioral vulnerabilities

---

**171. L2 Sequencer Grace Period Missing**

- **D:** On L2 chains, when sequencer restarts after downtime, contracts immediately liquidate positions without allowing users a grace period to adjust collateral. Users who were solvent before downtime get unfairly liquidated.
- **FP:** Explicit grace period logic after sequencer restart (e.g., `require(block.timestamp > sequencerUptimeTimestamp + GRACE_PERIOD)`). L1-only deployment. Chainlink L2 Sequencer Uptime Feed checked with grace window.

**172. Liquidation Incentive Insufficient for Trustless Actors**

- **D:** Liquidation reward (bonus %) doesn't cover gas cost for small positions. No one profitably liquidates dust positions, leading to bad debt accumulation. Protocol becomes insolvent as underwater positions compound.
- **FP:** Minimum position size enforced at borrow time. Protocol operates its own liquidation bot. Insurance fund covers unprofitable liquidations. Dynamic liquidation incentive scaled to position size.

**173. Collateral Withdrawal While Position Underwater**

- **D:** User can withdraw partial collateral even when position is underwater, as long as the specific collateral's PNL is positive. Removes liquidation incentive without improving protocol health.
- **FP:** Withdrawal blocked when overall position health factor < 1. Strict overcollateralization lock prevents any withdrawal while underwater.

**174. Dust Loan Griefing (Minimum Loan Size Bypass)**

- **D:** Attacker bypasses or exploits missing `minLoanSize` checks to create many tiny loans that are individually too small to profitably liquidate. Gas cost of liquidation exceeds recovered value, accumulating protocol bad debt.
- **FP:** `require(borrowAmount >= MIN_BORROW)` enforced on all borrow paths. Batch liquidation mechanism handles dust positions. Automatic write-off for sub-threshold bad debt.

**175. Unfair Liquidation via Cherry-Picked Collateral**

- **D:** Liquidator selects which collateral asset to seize, choosing the most liquid/stable asset while leaving volatile collateral. Borrower's position becomes unhealthier post-liquidation despite liquidator profiting.
- **FP:** Collateral seizure follows defined priority ordering. Liquidation enforces health improvement post-seizure (`healthFactorAfter > healthFactorBefore`). Single-collateral system.

**176. Interest Accrual During Emergency Pause**

- **D:** When admin pauses repayments for emergency, interest continues accruing. Users cannot repay but their debt grows, forcing liquidation of positions that were healthy before the pause.
- **FP:** Pause simultaneously halts interest accrual. Symmetric pause behavior (repay and liquidate both paused together). Grace period after unpause before liquidations resume.

**177. Repayment Paused While Liquidation Active**

- **D:** Admin pauses repayments for emergency but liquidations remain active. Borrowers cannot exit positions while protocol can still seize their collateral — asymmetric freeze benefits protocol at user expense.
- **FP:** Synchronized pause (repay and liquidate paused/unpaused together). Documented asymmetric design with economic justification. Emergency pause as intentional protocol safety feature.

**178. Liquidation Leaves Borrower Unhealthier**

- **D:** After partial liquidation, borrower's health factor is lower than before due to incorrect close factor calculation, cherry-picked collateral seizure, or liquidation bonus exceeding available surplus.
- **FP:** Post-liquidation health check (`require(healthAfter >= healthBefore || healthAfter >= 1)`). Full liquidation when partial would worsen position. Documented minimum health improvement requirement.

**179. No LTV Gap Between Borrow and Liquidation Threshold**

- **D:** Liquidation threshold equals max borrow LTV. Positions become immediately liquidatable after borrowing with zero buffer for normal price volatility. Users have no margin to avoid liquidation.
- **FP:** Explicit gap between max borrow LTV and liquidation threshold (e.g., borrow at 75%, liquidate at 80%). Documentation explains chosen parameters. Per-asset configurable thresholds.

**180. First Depositor Reward Stealing (Staking)**

- **D:** In staking/reward contracts, first depositor front-runs initial reward distribution with minimal (1-wei) deposit, capturing 100% of initial rewards intended for later legitimate stakers.
- **FP:** Minimum stake amount enforced. Admin-only initial deposit establishes baseline. Time-weighted reward calculation prevents instant claiming. Initial reward distribution delayed until minimum TVL reached.

---

---

**181. Reward Dilution via Direct Token Transfer**

- **D:** Attacker transfers staking tokens directly to contract (bypassing `stake()` function), inflating `totalSupply` in balance-based calculations without earning tracked stake. Dilutes rewards for legitimate stakers.
- **FP:** Separate reward token tracking independent of raw balance. Internal `totalStaked` variable updated only via `stake()`/`unstake()`. Protocol explicitly handles direct transfer surplus.

**182. Flash Deposit/Withdraw Reward Griefing**

- **D:** Large instantaneous deposit right before reward distribution dilutes per-token reward rate. Attacker withdraws immediately after distribution, capturing disproportionate share intended for steady-state stakers.
- **FP:** Minimum stake duration requirement (cooldown). Time-weighted reward calculation. Reward snapshot at previous block. Anti-flash-loan modifier (`require(block.number > depositBlock)`).

**183. Stale Reward Index After Distribution**

- **D:** Reward distribution updates global reward pool but fails to call `updateReward()` / update `rewardPerTokenStored`. Stale index causes incorrect reward calculations for all users until next state-changing call.
- **FP:** `updateReward()` called in all reward-distributing functions via modifier. Global index updated atomically with distribution. Post-distribution assertions verify consistency.

**184. Balance Caching Issues During Reward Claims**

- **D:** Claiming rewards reads user balance, performs external token transfer, then uses the cached balance for further calculations. Reentrant callback during transfer can manipulate state between read and use.
- **FP:** `nonReentrant` on all claim functions. Balance read after transfer completes. CEI pattern followed — state updates before external calls.

**185. Liquidation Bonus Exceeds Available Collateral**

- **D:** Fixed liquidation bonus (e.g., 110% of debt in collateral) exceeds actual collateral when position is deeply underwater. Liquidation reverts because contract tries to transfer more than available, leaving bad debt permanently stuck.
- **FP:** Dynamic bonus capped at available collateral. Liquidation function handles partial recovery gracefully. Insurance fund covers shortfall. `min(bonus, availableCollateral)` pattern used.

**186. Incorrect Decimal Handling in Multi-Token Liquidations**

- **D:** Liquidation calculations assume uniform 18-decimal tokens but collateral/debt have different decimals (USDC=6, WETH=18). Order-of-magnitude errors in liquidation amounts — either liquidating too much or too little.
- **FP:** Per-token `decimals()` normalization in all cross-token math. Explicit `10 ** (18 - decimals())` scaling factors. Tested with mixed-decimal token pairs.

**187. Interest Accrual During Liquidation Auction**

- **D:** While collateral is being auctioned (Dutch auction, English auction), borrower's debt continues accruing interest. Long auctions make the position progressively worse, potentially causing auction proceeds to be insufficient.
- **FP:** Interest frozen at auction start timestamp. Auction duration bounded. Instant liquidation (no auction). Interest-inclusive reserve price.

**188. No Liquidation Slippage Protection**

- **D:** Liquidator calls `liquidate()` but received collateral amount has no minimum parameter. MEV bot sandwiches the liquidation tx, extracting value via collateral price manipulation.
- **FP:** `minCollateralReceived` parameter in liquidation function. Private mempool for liquidation txs. Protocol-operated liquidation bot with MEV protection.

**189. L2 Sequencer Downtime in Interest Accrual**

- **D:** Interest rate calculations use `block.timestamp` delta without accounting for L2 sequencer downtime periods. If sequencer is down for hours, the first post-restart block has a massive timestamp gap, compounding interest as if the protocol was operating normally.
- **FP:** Interest accrual capped per-update (`maxTimeDelta`). Sequencer uptime feed checked before accruing. Rate-limited compounding.

**190. Precision Loss in Reward-to-Token Conversion**

- **D:** Staking reward calculations use `rewardRate * timeElapsed / totalStaked` where small stakes produce zero due to integer division. Small stakers permanently receive zero rewards despite time passing.
- **FP:** Scaling factor applied (e.g., multiply by 1e18 before division). Minimum stake size enforced above precision loss threshold. Accumulator-based reward tracking.

---

---

**191. Time Unit Confusion in Interest Calculations**

- **D:** Interest accrual logic confuses time units — using `block.timestamp` (seconds) in a formula expecting days or blocks, or vice versa. Results in interest rates off by orders of magnitude (e.g., 365x too high or 86400x too low).
- **FP:** Documented time unit constants (`SECONDS_PER_YEAR = 365.25 days`). Unit tests with known interest calculations. Consistent use of `block.timestamp` (seconds) throughout.

**192. Oracle Manipulation via Self-Liquidation**

- **D:** User manipulates oracle price via flash loan (push TWAP or spot price), self-liquidates via second address at the manipulated price, extracts more collateral than debt owed. Profitable when manipulation cost < liquidation bonus.
- **FP:** TWAP with window > manipulation cost threshold. Chainlink/Pyth oracle resistant to single-tx manipulation. Self-liquidation blocked (`require(liquidator != borrower)`).

**193. On-Chain Quoter-Based Slippage Calculation**

- **D:** `minAmountOut` calculated on-chain using current spot price from an AMM quoter. Flash loan manipulates spot price before the tx, setting `minAmountOut` to near-zero, then sandwiches the actual swap.
- **FP:** `minAmountOut` supplied as calldata parameter from off-chain calculation. TWAP-based quoting. Maximum acceptable slippage hardcoded as percentage.

**194. Fixed Fee Tier Assumption in Multi-Pool DEX**

- **D:** Router hardcodes fee tier (e.g., Uniswap V3 0.3% pool) but liquidity migrates to different tier (0.05% or 1%). Swaps execute against low-liquidity pool with excessive slippage or revert.
- **FP:** Fee tier as function parameter. Router queries multiple tiers and uses optimal. Dynamic fee tier detection via factory query.

**195. Multi-Hop Swap Intermediate-Only Protection**

- **D:** Multi-hop swap (A→B→C) protects intermediate amount (B) but not final output (C). MEV extracts value on the final hop where no minimum is enforced.
- **FP:** `minFinalAmountOut` validated against user's actual received balance (balance delta check). Single-hop swap. Per-hop minimums specified by caller.

**196. block.timestamp as Swap Deadline**

- **D:** `deadline = block.timestamp` provides zero deadline protection since every block's timestamp satisfies it. Tx can be held in mempool indefinitely and executed at the worst possible time.
- **FP:** Deadline supplied as calldata from off-chain (e.g., `now + 300 seconds`). Keeper-based execution with enforced timeliness. Private mempool.

**197. Zero minAmountOut on DEX Swap**

- **D:** `swap(tokenIn, tokenOut, amountIn, 0)` — hardcoded zero minimum output. Completely unprotected from MEV/sandwich attacks. Often found in reward harvesting, fee conversion, or liquidation collateral sale paths.
- **FP:** `minAmountOut` parameter exposed to caller or computed from oracle. Internal-only swap with access control. Documented acceptance of slippage risk for small amounts.

**198. Transient Storage Reentrancy Guard in Delegatecall Context**

- **D:** Reentrancy guard uses `TSTORE`/`TLOAD` but in a delegatecall proxy context. Transient storage is per-address, not per-contract — proxy's transient storage is shared across all facets/implementations. Guard in one facet doesn't protect against reentry into different facet.
- **FP:** Shared transient storage slot used by all facets (single guard). Regular storage-based reentrancy guard. No delegatecall architecture.

**199. Uniswap V4 Hook Callback Authorization**

- **D:** Hook contract's callback functions (`beforeSwap`, `afterSwap`, etc.) don't validate `msg.sender == poolManager`. Anyone can call hook functions directly, manipulating cached state or triggering unintended side effects.
- **FP:** `require(msg.sender == address(poolManager))` in every callback. `onlyPoolManager` modifier. Hook uses `BaseHook` from Uniswap V4 periphery.

**200. Uniswap V4 Cached State Desynchronization**

- **D:** Hook caches pool state (`sqrtPriceX96`, `liquidity`, `tick`) in `beforeSwap` but state changes during the swap. `afterSwap` reads stale cached values for fee calculations or rebalancing decisions.
- **FP:** State re-read from pool in `afterSwap`. Cache explicitly invalidated between hooks. No cross-hook state dependency.

---

---

**201. Custom Access Control Without Two-Step Transfer**

- **D:** Hand-rolled `setOwner(newOwner)` with single-step transfer. Typo in `newOwner` address permanently locks out admin access with no recovery mechanism.
- **FP:** OZ `Ownable2Step` used. Multisig as owner (typo requires multiple signers). Timelock with cancel capability. Recovery mechanism via governance.

**202. Inconsistent Pausable Coverage**

- **D:** Contract imports `Pausable` but applies `whenNotPaused` modifier inconsistently. Some fund-moving operations (withdraw, transfer, liquidate) lack pause protection, allowing drain during emergency pause intended to freeze all operations.
- **FP:** All state-changing functions have `whenNotPaused`. Intentionally unpaused functions documented (e.g., emergency withdraw). Pause coverage verified in tests.

**203. OpenZeppelin Version Confusion (v4 vs v5)**

- **D:** Contract overrides `_beforeTokenTransfer` (OZ v4 hook) while importing OZ v5, where the hook was replaced with `_update`. Override silently never executes — access control, transfer restrictions, or enumerable tracking bypassed.
- **FP:** Confirmed OZ version consistency. Contract uses `_update` override for v5. No OZ token base inherited.

**204. Approval to Arbitrary User-Supplied Address (Aggregator/Router Pattern)**

- **D:** Router/aggregator calls `token.approve(userSuppliedPool, MAX_UINT)` where pool address comes from user calldata without allowlist validation. Attacker supplies malicious "pool" that calls `transferFrom` to drain all approved tokens.
- **FP:** Pool addresses validated against factory or hardcoded allowlist. Approval limited to exact amount per operation (`approve(pool, amountIn)` followed by `approve(pool, 0)`). No persistent approvals.

**205. External Call Failure DoS in Batch Operations**

- **D:** Batch operation (reward distribution, multi-user withdrawal, liquidation queue) reverts entirely if any single external call fails. One blacklisted address or reverting contract blocks all users in the batch.
- **FP:** Per-item `try/catch` with skip-on-failure. Pull-over-push pattern. Failed items queued for retry. Event emitted for failed transfers.

**206. Storage Bloat Attack (Unbounded Mapping/Array Growth)**

- **D:** Attacker fills user-controlled mappings/arrays without economic limits (e.g., `userTokens[user].push(attacker_token)` for each of thousands of fake tokens). Functions iterating over this array hit block gas limit.
- **FP:** Array size bounded (`require(arr.length < MAX)`). Economic deterrent (cost per entry). Pagination for iteration. EnumerableSet with bounded operations.

**207. Timestamp Griefing (Lock Period Reset by Third Party)**

- **D:** Any address can trigger a timestamp reset on another user's lock. Pattern: `deposit(address user, uint256 amount)` where `amount` can be 1 wei and resets `lockExpiry[user] = block.timestamp + LOCK_DURATION`. Attacker calls `deposit(victim, 1)` perpetually extending victim's lock.
- **FP:** Lock timestamp only updatable by the locked user themselves. Minimum deposit enforced. Lock extension only possible, never reset (uses `max(existing, new)`).

**208. Self-Destruct Force-Feed Breaking Strict Balance Equality**

- **D:** Contract uses `require(address(this).balance == expectedBalance)` with strict equality. Attacker force-feeds ETH via `selfdestruct(target)`, permanently breaking the equality check and DoS-ing the function.
- **FP:** Internal balance tracking (never reads `address(this).balance` for logic). Uses `>=` or `<=` comparisons. Contract designed to accept arbitrary ETH.

**209. Inconsistent Guard Coverage Across Semantically Equivalent Functions**

- **D:** Contract has multiple functions that perform the same logical operation (e.g., `transfer` and `transferFrom`, or `deposit` and `depositFor`) but security guards (pause, reentrancy, access control) are only applied to one. Attacker uses the unguarded variant.
- **FP:** Shared internal function with guards called by all public variants. Modifier applied uniformly. Single entry point for each operation.

**210. Missing Initialization of Inherited State in Upgradeable Contracts**

- **D:** Upgradeable contract calls `__Ownable_init()` but forgets to call `__ReentrancyGuard_init()`, `__Pausable_init()`, or other inherited initializers. Reentrancy guard status is 0 (uninitialized), which may not provide protection. Pausable state is unpredictable.
- **FP:** All inherited `__*_init()` functions called in `initialize()`. OZ Upgradeable contracts used with complete initialization chain. Tests verify all state correctly initialized post-deployment.
