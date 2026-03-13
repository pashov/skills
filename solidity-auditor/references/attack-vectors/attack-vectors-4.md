---

**166. Calldata Input Malleability**

- **D:** Contract hashes raw calldata for uniqueness (`processedHashes[keccak256(msg.data)]`). Dynamic-type ABI encoding uses offset pointers — multiple distinct calldata layouts decode to identical values. Attacker bypasses dedup with semantically equivalent but bytewise-different calldata.
- **FP:** Uniqueness check hashes decoded parameters: `keccak256(abi.encode(decodedParams))`. Nonce-based replay protection. Only fixed-size types in signature (no encoding ambiguity).

**167. Reward Accrual During Zero-Depositor Period**

- **D:** Time-based reward distribution starts at vault deployment but no depositors exist yet. First depositor claims all rewards accumulated during the empty period regardless of deposit size or timing.
- **FP:** Rewards only accrue when `totalSupply > 0`. Reward start time set on first deposit. Unclaimed pre-deposit rewards sent to treasury or burned.

**168. MEV Withdrawal Before Bad Debt Socialization**

- **D:** External event (liquidation, exploit, depeg) causes vault loss. MEV actor observes pending loss-causing tx in mempool and front-runs a withdrawal at pre-loss share price, leaving remaining depositors to absorb the full loss.
- **FP:** Withdrawals require time-delayed request queue (epoch-based or cooldown). Loss realization and share price update are atomic. Private mempool used for liquidation txs.

**169. Vault Insolvency via Accumulated Rounding Dust**

- **D:** Vault tracks `totalAssets` as a storage variable separate from `token.balanceOf(vault)`. Solidity's floor rounding on each deposit/withdrawal creates tiny overages — user receives 1 wei more than burned shares represent. Over many operations `totalAssets` exceeds actual balance, causing last withdrawers to revert.
- **FP:** Rounding consistently favors the vault (round shares up on deposit, round assets down on withdrawal). OZ Math with `Rounding.Ceil`/`Rounding.Floor` applied correctly.

**170. FIFO Withdrawal Ordering Degrades Yield**

- **D:** Aggregator vault withdraws from sub-vaults in fixed FIFO order, depleting highest-APY vaults first. Remaining capital concentrates in lowest-yield positions, reducing overall returns for all depositors.
- **FP:** Withdrawal ordering sorted by APY ascending (lowest-yield first). Dynamic rebalancing after withdrawals. Single underlying vault (no ordering issue).

**171. ERC4626 convertToAssets Used Instead of previewWithdraw**

- **D:** Integration calls `convertToAssets(shares)` to estimate withdrawal proceeds. Per ERC4626 spec this excludes fees and slippage — actual redeemable amount is lower. Downstream logic (health checks, rebalancing, UI) operates on inflated values.
- **FP:** `previewWithdraw()` or `previewRedeem()` used for actual withdrawal estimates. Vault charges no withdrawal fees. Fee delta accounted separately.

**172. Unclaimed Reward Tokens from Underlying Protocol**

- **D:** Vault deposits into yield protocol (Morpho, Aave, Convex) that emits reward tokens. Vault never calls `claim()` or lacks logic to distribute claimed rewards to depositors. Rewards accumulate indefinitely in the vault or underlying protocol, inaccessible to shareholders.
- **FP:** Explicit `claimRewards()` function harvests and distributes. Reward tokens tracked dynamically (mapping, not hardcoded list). Vault sweeps unexpected token balances to treasury.

**173. Idle Asset Dilution from Sub-Vault Deposit Caps**

- **D:** Parent/aggregator vault accepts deposits without checking sub-vault capacity. When sub-vaults hit their deposit caps, excess assets sit idle in the parent — earning zero yield but diluting share price for all depositors.
- **FP:** `maxDeposit()` reflects combined sub-vault remaining capacity. Deposits revert when no productive capacity remains. Idle assets auto-routed to fallback yield source.

**174. Memory Struct Copy Not Written Back to Storage**

- **D:** `MyStruct memory s = myMapping[key]` creates a memory copy. Modifications to `s` do not persist — storage remains unchanged. Common in reward updates, position tracking, and config changes where the developer assumes memory aliases storage.
- **FP:** Uses `storage` keyword: `MyStruct storage s = myMapping[key]`. Explicitly writes back: `myMapping[key] = s` after modification.

**175. On-Chain Slippage Computed from Manipulated Pool**

- **D:** `amountOutMin` calculated on-chain by querying the same pool that will execute the swap. Attacker manipulates the pool before the tx, making both the quote and the swap reflect the manipulated state — slippage check passes despite sandwich.
- **FP:** `amountOutMin` supplied by the caller (off-chain quote). Uses a separate oracle for the floor price. TWAP-based minimum.

**176. Withdrawal Queue Bricked by Zero-Amount Entry**

- **D:** FIFO withdrawal queue processes entries sequentially. A cancelled or zeroed-out entry causes the loop to `break` or revert on zero amount instead of skipping it, permanently blocking all subsequent withdrawals behind it.
- **FP:** Queue skips zero-amount entries. Cancellation removes the entry or marks it processed. Queue uses linked list allowing removal.

**177. Lazy Epoch Advancement Skips Reward Periods**

- **D:** Epoch counter advances only on user interaction. If no one interacts during an epoch, it is never advanced — rewards for that period are miscalculated, lost, or retroactively applied to the wrong epoch when the next interaction occurs.
- **FP:** Keeper or automation advances epochs independently. Epoch catch-up loop processes all skipped epochs on next interaction. Continuous (non-epoch) reward accrual.

**178. Reward Rate Changed Without Settling Accumulator**

- **D:** Admin updates the emission rate but `updateReward()` / `updatePool()` is not called first. The new rate is retroactively applied to the entire elapsed period since the last update, overpaying or underpaying rewards for that window.
- **FP:** Rate-change function calls `updateReward()` before applying the new rate. Modifier auto-settles on every state change.

**179. Liquidated Position Continues Accruing Rewards**

- **D:** Position is liquidated (balance zeroed, collateral seized) but is not removed from the reward distribution system. `rewardDebt` and accumulated rewards are not reset — the liquidated user earns phantom rewards, or the rewards are locked permanently.
- **FP:** Liquidation calls `_withdrawRewards()` or equivalent before zeroing the position. Reward system checks `balance > 0` before accruing.

**180. Cached Reward Debt Not Reset After Claim**

- **D:** After `claimRewards()`, the cached reward amount (`pendingReward` or `rewardDebt`) is not zeroed. On the next claim cycle, the full cached amount is paid again — double (or repeated) payout.
- **FP:** `pendingReward[user] = 0` after transfer. `rewardDebt` recalculated from current balance and accumulator after claim.

**181. Emission Distribution Before Period Update**

- **D:** `distribute()` reads the contract's token balance before `updatePeriod()` mints or transfers new emissions. New rewards arrive after distribution already executed — they sit idle until the next cycle, underpaying the current period.
- **FP:** `updatePeriod()` called before `distribute()` in the same tx. Emissions pre-funded before distribution window opens.

**182. Pause Modifier Blocks Liquidations**

- **D:** `whenNotPaused` applied broadly to all external functions including `liquidate()`. During a pause, interest accrues and prices move but positions cannot be liquidated — bad debt accumulates unchecked until unpause.
- **FP:** Liquidation functions exempt from pause. Separate `pauseLiquidations` flag with independent governance. Interest accrual also paused.

**183. Liquidation Arithmetic Reverts at Extreme Price Drops**

- **D:** When collateral price drops 95%+, liquidation math overflows or underflows — e.g., `collateralNeeded = debt / price` becomes enormous, exceeding available collateral. The liquidation function reverts, making the position unliquidatable and locking bad debt.
- **FP:** Liquidation caps `collateralSeized` at position's total collateral. Graceful handling of underwater positions (full seizure, remaining bad debt socialized).

**184. Borrower Front-Runs Liquidation**

- **D:** Borrower observes pending `liquidate()` tx in mempool, front-runs with minimal repayment or collateral top-up to push health factor above threshold. Immediately re-borrows after liquidation tx fails. Repeated indefinitely to maintain risky position.
- **FP:** Liquidation uses flash-loan-resistant health check (same-block deposit doesn't count). Minimum repayment cooldown. Dutch auction liquidation (no fixed threshold to game).

**185. Liquidation Discount Applied Inconsistently Across Code Paths**

- **D:** One code path calculates debt at face value, another applies a liquidation discount. When the discounted amount is subtracted from the non-discounted amount, the result underflows or leaves residual bad debt unaccounted.
- **FP:** Discount applied consistently in all paths touching liquidation accounting. Single source of truth for discounted value.

**186. No Buffer Between Max LTV and Liquidation Threshold**

- **D:** Max borrowable LTV equals the liquidation threshold. A borrower at max LTV is immediately liquidatable on any adverse price tick. Combined with origination fees, positions can be born underwater.
- **FP:** Max LTV is meaningfully lower than liquidation threshold (e.g., 80% vs 85%). Origination fee deducted from borrowed amount, not added to debt.

**187. Same-Block Vote-Transfer-Vote**

- **D:** Governance reads voting power at current block, not a past snapshot. User votes, transfers tokens to a second wallet in the same block, and votes again — doubling their effective vote weight.
- **FP:** `getPastVotes(block.number - 1)` or proposal-creation snapshot. Voting power locked on first vote until proposal closes. ERC20Votes with checkpoint-based historical balances.

**188. Quorum Computed from Live Supply, Not Snapshot**

- **D:** `quorum = totalSupply() * quorumBps / 10000` reads current supply. After a proposal is created, an attacker mints tokens (or deposits to inflate supply), lowering the effective quorum percentage needed to pass.
- **FP:** Quorum snapshotted at proposal creation: `totalSupply(proposalSnapshot)`. Fixed absolute quorum amount. Supply changes do not affect active proposals.

**189. Checkpoint Overwrite on Same-Block Operations**

- **D:** Multiple delegate/transfer operations in the same block call `_writeCheckpoint()` with the same `block.number` key. Each overwrites the previous — binary search returns the first (incomplete) checkpoint, losing intermediate state.
- **FP:** Checkpoint appends only when `block.number > lastCheckpoint.blockNumber`. Same-block operations accumulate into the existing checkpoint. Off-chain indexer used instead of on-chain lookups.

**190. Self-Delegation Doubles Voting Power**

- **D:** Delegating to self adds votes to the delegate (self) but does not subtract the undelegated balance. Voting power is counted twice — once as held tokens, once as delegated votes.
- **FP:** Delegation logic subtracts from holder's direct balance when adding to delegate. Self-delegation is a no-op or explicitly handled. OZ Votes implementation used correctly.

**191. Nonce Not Incremented on Reverted Execution**

- **D:** Meta-transaction or permit nonce is checked before execution but only incremented on success. If the inner call reverts (after nonce check, before increment), the same signed message can be replayed until it eventually succeeds.
- **FP:** Nonce incremented before execution (check-effects-interaction). Nonce incremented in both success and failure paths. Deadline-based expiry on signed messages.

**192. Bridge Global Rate Limit Griefing**

- **D:** Bridge enforces a global throughput cap (total value per window) not segmented by user. Attacker fills the rate limit by bridging cheap tokens back and forth, blocking all legitimate users from bridging during the cooldown window.
- **FP:** Per-user rate limits. Rate limit segmented by token or route. Whitelist for high-value transfers. No global rate limit.

**193. Self-Matched Orders Enable Wash Trading**

- **D:** Order matching does not verify `maker != taker`. A user submits both sides of a trade to farm trading rewards, inflate volume metrics, bypass royalties (NFT), or extract fee rebates.
- **FP:** `require(makerOrder.signer != takerOrder.signer)`. Volume-based rewards use time-weighted averages resistant to single-block spikes. Royalty enforced regardless of counterparty.

**194. Dutch Auction Price Decay Underflow**

- **D:** `currentPrice = startPrice - (decayRate * elapsed)`. When the auction runs past the point where price should reach zero, the subtraction underflows — reverting on 0.8+ or wrapping to `type(uint256).max` on <0.8. Auction becomes unfinishable.
- **FP:** `currentPrice = elapsed >= duration ? reservePrice : startPrice - (decayRate * elapsed)`. Floor price enforced. `min()` used to cap decay.

**195. Timelock Anchored to Deployment, Not Action**

- **D:** Recovery or admin timelock measured from contract deployment or initialization, not from when the action was queued. Once the initial delay elapses, all future actions can execute instantly — the timelock is effectively permanent bypass.
- **FP:** Timelock resets on each queued action. `executeAfter = block.timestamp + delay` set at queue time. OZ TimelockController pattern.

**196. Withdrawal Rate Limit Bypassed via Share Transfer**

- **D:** Per-address withdrawal limit: `require(withdrawn[msg.sender] + amount <= limitPerPeriod)`. User transfers vault shares to a fresh address and withdraws from there — each new address gets a fresh limit.
- **FP:** Limit tracks the underlying position, not the address. Shares are non-transferable or transfer resets withdrawal allowance. KYC-bound withdrawal limits.

**197. Blacklist and Whitelist Not Mutually Exclusive**

- **D:** An address can hold both `BLACKLISTED` and `WHITELISTED` roles simultaneously. Whitelist-gated paths do not check the blacklist — a blacklisted address bypasses restrictions by also being whitelisted.
- **FP:** Adding to blacklist auto-removes from whitelist (and vice versa). Single enum role per address. Both checks applied on every restricted path.

**198. Dead Code After Return Statement**

- **D:** Critical state update or validation (`require(success)`, `emit Event`, `nonce++`) placed after a `return` statement. The code is unreachable — failures go undetected, events are never emitted, state is never updated.
- **FP:** All critical logic precedes `return`. Compiler warnings for unreachable code are addressed. Linter enforces no-unreachable-code rule.

**199. Partial Redemption Fails to Reduce Tracked Total**

- **D:** Withdrawal queue partially fills a redemption request but does not proportionally reduce `totalQueuedShares` or `totalPendingAssets`. The vault's tracked total remains inflated, skewing share price for all other depositors.
- **FP:** Partial fill reduces tracked totals proportionally. Queue uses per-request tracking, not a global aggregate. Atomic full-or-nothing redemptions.

**200. TWAP Accumulator Not Updated During Sync or Skim**

- **D:** Pool's `sync()` or `skim()` function updates reserves but does not call `_update()` to advance the TWAP cumulative price accumulator. TWAP observations return stale values, enabling price manipulation through sync-then-trade sequences.
- **FP:** `sync()` calls `_update()` before overwriting reserves. TWAP sourced from external oracle, not internal accumulator. Uniswap V3 `observe()` used (accumulator updated on every swap).

**201. Expired Oracle Version Silently Assigned Previous Price**

- **D:** In request-commit oracle patterns (Pyth, custom keepers), an expired or unfulfilled price request is assigned the last valid price instead of reverting or returning invalid. Pending orders execute at stale prices rather than being cancelled.
- **FP:** Expired versions return `price = 0` or `valid = false`, forcing order cancellation. Staleness threshold enforced per-request. Fallback oracle used for expired primaries.

**202. Funding Rate Derived from Single Trade Price**

- **D:** Perpetual swap funding rate uses the last trade price as the mark price. A single self-trade at an extreme price skews the funding rate — the attacker profits from funding payments on their opposing position.
- **FP:** Mark price derived from TWAP or external oracle index. Funding rate capped per period. Volume-weighted average price used.

**203. Open Interest Tracked with Pre-Fee Position Size**

- **D:** Open interest incremented by the full position size before fees are deducted. Actual exposure is smaller than recorded OI. Aggregate OI is permanently inflated, eventually hitting caps and blocking new positions.
- **FP:** OI incremented by post-fee position size. OI decremented on close by same amount used at open. Periodic OI reconciliation.

**204. Interest Accrual Rounds to Zero but Timestamp Advances**

- **D:** `interest = rate * timeDelta / SECONDS_PER_YEAR` rounds to zero when `timeDelta` is small (e.g., <207s at 15% APR). But `lastAccrualTime = block.timestamp` is still updated — the fractional interest is permanently lost, not deferred to the next accrual.
- **FP:** Accumulator uses sufficient precision (e.g., RAY = 1e27) to avoid zero rounding at per-block intervals. `lastAccrualTime` only advances when computed interest > 0.

**205. Permissionless accrueInterest Griefing**

- **D:** `accrueInterest()` is permissionless and updates `lastAccrualTime` on every call. Attacker calls it at very short intervals — each call computes zero interest (rounding) but advances the timestamp, systematically suppressing interest accumulation to near-zero.
- **FP:** Minimum accrual interval enforced: `require(block.timestamp - lastAccrualTime >= MIN_INTERVAL)`. Precision high enough that per-block interest > 0. Access-restricted accrual.

**206. notifyRewardAmount Overwrites Active Reward Period**

- **D:** Calling `notifyRewardAmount(newAmount)` replaces the current reward period. Remaining undistributed rewards from the old period are silently lost — not carried forward. Admin or attacker can erase pending rewards by notifying a smaller amount.
- **FP:** New notification adds to remaining: `rewardRate = (newAmount + remaining) / duration`. Only callable by designated distributor with timelock. Remaining rewards refunded before reset.

**207. Governance Proposal Executable Before Voting Period Ends**

- **D:** `execute()` checks quorum and majority but not `block.timestamp >= proposal.endTime`. Once quorum is met, the proposal can be executed immediately — cutting the voting window short, preventing opposing votes from being cast.
- **FP:** `require(block.timestamp >= proposal.endTime)` in execute. OZ Governor enforces `ProposalState.Succeeded` which requires voting period to have ended.

**208. Partial Liquidation Leaves Position in Worse State**

- **D:** Partial liquidation seizes some collateral but does not enforce a minimum post-liquidation health factor. Liquidator cherry-picks the most valuable collateral, leaving the position with worse health than before — approaching full insolvency without triggering full liquidation.
- **FP:** Post-liquidation health factor check: `require(healthFactor(position) >= MIN_HF)`. Full liquidation triggered below a floor threshold. Liquidator must bring position to target health factor.

**209. Delegation to address(0) Blocks Token Transfers**

- **D:** Delegating votes to `address(0)` causes `_beforeTokenTransfer` or `_update` hooks to revert when attempting to modify the zero-address delegate's checkpoint. All subsequent transfers and burns for that token holder permanently revert.
- **FP:** Delegation to `address(0)` treated as undelegation (no-op or clears delegation). Hook skips checkpoint update when delegate is `address(0)`. OZ Votes implementation handles this case.

**210. ERC4626 maxDeposit Returns Non-Zero When Paused**

- **D:** `maxDeposit()` returns `type(uint256).max` even when the vault is paused. Integrating protocols (aggregators, routers) read this as "deposits accepted," attempt a deposit, and revert. Per ERC4626, `maxDeposit` must return 0 when deposits would revert.
- **FP:** `maxDeposit()` returns 0 when paused. OZ ERC4626 with pausing override. Integrators use `try deposit()` with fallback.

**211. Deprecated Gauge Blocks Claiming Accrued Rewards**

- **D:** Killing or deprecating a gauge clears future distributions but also blocks the `claimReward()` path for already-accrued, unclaimed rewards. Users who earned rewards before deprecation cannot retrieve them.
- **FP:** Kill only stops future accrual — claim function remains active for pre-kill balances. Rewards swept to fallback address on deprecation. Emergency claim path bypasses active-gauge check.

**212. Liquidation Blocked by External Pool Illiquidity**

- **D:** Liquidation function swaps collateral for debt token via an external DEX. If the DEX pool is drained or lacks liquidity, the swap reverts, making liquidation impossible. Bad debt accumulates while the pool remains illiquid.
- **FP:** Liquidation accepts collateral directly without swap. Fallback liquidation path uses a different DEX or oracle price. Liquidator provides debt token and receives collateral.

**213. No-Bid Auction Fails to Clear State**

- **D:** Auction expires without any bids. The finalization function does not clear lien, auction, or escrow data — collateral remains locked in the auction contract with no path to return it to the owner or trigger a new auction.
- **FP:** No-bid finalization returns collateral to owner and clears all associated state. Re-auction mechanism triggered automatically. Timeout-based collateral release.

**214. Position Reduction Triggers Liquidation**

- **D:** User attempts to improve health by partially repaying debt or withdrawing a small amount of excess collateral. The intermediate state (after collateral removal, before debt reduction) crosses the liquidation threshold — a bot liquidates the position mid-transaction or in the same block.
- **FP:** Repay and collateral changes are atomic (single function). Health check applied only to final state, not intermediate. Liquidation grace period after position modification.

**215. Repeated Liquidation of Same Position**

- **D:** Liquidation function does not flag the position as liquidated. After partial liquidation, the position still appears undercollateralized — a second liquidator (or the same one) liquidates again, seizing collateral beyond what was intended.
- **FP:** Position marked as `liquidated` or deleted after processing. Liquidation requires `status != Liquidated`. Post-liquidation health check prevents re-triggering.

**216. Loan State Transition Before Interest Settlement**

- **D:** Repaying principal sets the loan state to `Repaid` before accrued interest is settled. Once in `Repaid` state, the interest accrual function skips the loan — all accumulated interest becomes permanently uncollectable.
- **FP:** `settleInterest()` called before state transition. Interest added to repayment amount: `require(msg.value >= principal + accruedInterest)`. State transition only after full settlement.

**217. Protocol Fee Inflates Reward Accumulator**

- **D:** Protocol fee routed to treasury is processed through the same `rewardPerToken` accumulator as staker rewards. The accumulator increments as if all distributed tokens go to stakers, but part went to treasury — stakers' `earned()` returns more than the contract holds.
- **FP:** Fee deducted before updating accumulator: `rewardPerToken += (reward - fee) / totalStaked`. Separate accounting for fees and rewards. Fee transferred directly, not through reward distribution.

**218. Profit Tracking Underflow Blocks Withdrawals**

- **D:** Vault tracks cumulative strategy profit. When a strategy reports a loss exceeding its recorded profit, `totalProfit -= loss` underflows (reverts on 0.8+). All withdrawal functions that read `totalProfit` are permanently bricked.
- **FP:** Loss capped: `totalProfit -= min(loss, totalProfit)`. Signed integer used for profit/loss tracking. Per-strategy profit tracking (one strategy's loss doesn't affect others).

**219. Share Redemption at Optimistic Rate**

- **D:** Shares redeemed at a projected end-of-term exchange rate rather than the current realized rate. Early redeemers receive more than their proportional share of actual assets — late redeemers find the vault depleted.

**220. DoS via Reverting External Call in Loop**

- **D:** Withdrawal, burn, or claim function loops over a dynamic list and makes an external call per iteration (token transfer, swap, oracle read, callback). If any single call reverts — token paused/blacklisted, pool illiquid, recipient rejects — the entire function reverts, blocking all users from the operation even for the unaffected entries. Pattern: `for (i < list.length) { externalCall(list[i]); }` in a withdrawal/burn/claim path with no alternative exit.
- **FP:** Each external call wrapped in `try/catch` (skip on failure). Separate per-item withdrawal function exists. Admin can remove problematic entries from the list and users can still access remaining assets.
