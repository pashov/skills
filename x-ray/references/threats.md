# Protocol-Type Threat Profiles

This reference provides per-protocol-type threat intelligence. The skill auto-classifies the protocol from code signals in Step 2, then uses the matching profile(s) to weight adversaries, attack patterns, and surfaces in the threat model.

## Protocol Classification Signals

Detect protocol type from function signatures, state variables, and architectural patterns found during source file reading in Step 2. A protocol may match **multiple types** (hybrid). Rank by signal density — the type with the most matches is primary.

| Type | Detection Signals in Code |
|------|--------------------------|
| **Lending/Borrowing** | `borrow()`, `repay()`, `liquidate()`, `liquidationBonus`, `healthFactor`, `collateralFactor`, `LTV`, `debtToken`, `interestRate`, collateral ratio math, health factor calculations, borrow/supply balance tracking |
| **DEX/AMM** | `swap()`, `addLiquidity()`, `removeLiquidity()`, constant-product math (`x * y = k`), stable-swap invariant, `sqrtPriceX96`, `tick`, LP token mint/burn, fee tier, `getAmountOut()`, reserves tracking |
| **Yield Aggregator** | ERC4626 vault pattern (`deposit`/`withdraw`/`convertToShares`/`convertToAssets`), strategy pattern (deposit into external protocol + `harvest()`), yield routing, `totalAssets()`, `strategyDebt`, auto-compound |
| **Stablecoin** | Peg mechanism (mint/burn against collateral), `collateralRatio`, stability fee, `debtCeiling`, redemption mechanism, PSM (peg stability module), `anchor`/`peg`/`target` price references |
| **Derivatives/Perps** | `openPosition()`, `closePosition()`, `increaseSize()`, `decreaseSize()`, `fundingRate`, `margin`, `leverage`, PnL calculation, `markPrice`, `indexPrice`, position struct with size/collateral/entryPrice |
| **Liquid Staking** | `stake()` + derivative token mint, `unstake()`/`requestWithdrawal()`, exchange rate calculation, validator set management, withdrawal queue, rebasing token or share-based token |
| **Bridge** | Cross-chain message passing, `lock()`/`unlock()` or `burn()`/`mint()` pattern, relayer/validator set, message nonce, chain ID checks, merkle proof verification |
| **Governance** | `propose()`, `vote()`, `execute()`, `queue()`, quorum calculation, voting power snapshots, timelock, delegation, `proposalThreshold` |

### Hybrid Classification

Many protocols combine types. When multiple types match:
1. Rank by signal count — more matches = higher weight in threat model
2. The **primary type** determines adversary ranking order
3. **Secondary types** add their unique threats to the model (de-duplicating overlapping ones)
4. In the output, state: "Protocol classified as: **[Primary]** with **[Secondary]** characteristics"

Example: A protocol with `swap()`, `addLiquidity()`, `borrow()`, `liquidate()` → Primary: DEX/AMM, Secondary: Lending/Borrowing.

---

## Threat Profiles by Protocol Type

### Lending / Borrowing

**Primary adversaries** (ranked by historical exploit frequency):
1. **Flash loan attacker** — Borrows unlimited capital in a single transaction to manipulate oracle prices, inflate collateral values, and drain borrow capacity. Flash loans reduce the cost of oracle manipulation to near-zero.
2. **Oracle manipulator** — Manipulates price feeds (spot or TWAP) to make collateral appear more valuable or debt appear less valuable. The oracle is the single source of truth for solvency — if it lies, everything downstream breaks.
3. **Liquidation MEV searcher** — Extracts value from liquidation events through front-running, back-running, or sandwich attacks. If MEV extraction makes liquidation unprofitable for honest liquidators, bad debt accumulates.
4. **Malicious first depositor** — In protocols with share-based accounting (supply tokens, debt tokens), the first depositor can manipulate the share price to steal from subsequent depositors. Classic vault inflation attack applied to lending pools.
5. **Compromised admin** — Can change collateral factors, oracle addresses, interest rate models, or pause liquidations. Any of these can instantly make the protocol insolvent or prevent it from recovering.

**Dominant attack patterns:**
- Oracle manipulation → inflated collateral value → max borrow → drain lending pool
- Flash loan borrow → manipulate spot price → liquidate victim at wrong price → profit from liquidation bonus
- Bad debt accumulation through positions that become unliquidatable (oracle lag, gas price spikes, illiquid collateral)
- Interest rate manipulation via large deposit/withdraw cycles (move utilization to manipulate rates)
- Collateral factor misconfiguration allowing undercollateralized borrowing
- Recursive borrowing: deposit collateral → borrow → deposit borrowed asset as collateral → borrow again → amplified exposure that collapses under price movement

**Critical invariants:**
- `totalBorrows <= totalCollateral * LTV` — always, for every market and every account
- Every position must be liquidatable before it can cause bad debt (health factor trigger > underwater threshold)
- Liquidation must be profitable for liquidators (otherwise bad debt accrues silently)
- Oracle price reflects fair market value within acceptable deviation and freshness bounds
- Interest accrual is monotonic and cannot be manipulated to extract value

**What to look for first:**
1. The complete price calculation path: oracle read → price normalization → collateral value → health factor. Every step is a manipulation point.
2. Can a single transaction borrow, manipulate price, and liquidate? If yes, flash loan attack is viable.
3. Liquidation math: is the bonus sufficient to cover gas + slippage? What happens when collateral is illiquid?
4. Share price calculation for supply/debt tokens: what happens when totalSupply == 0?
5. What can admin change instantly vs. through timelock? Can admin change oracle address?

---

### DEX / AMM

**Primary adversaries** (ranked):
1. **MEV searcher / sandwich attacker** — The dominant threat to DEX users. Monitors mempool for pending swaps, inserts transactions before and after to extract value. Every swap without adequate slippage protection is a guaranteed extraction opportunity.
2. **Flash loan price manipulator** — Uses flash-loaned capital to move pool prices within a single transaction.
3. **Malicious first LP / empty pool attacker** — Manipulates pool initialization or empty-state transitions. In concentrated liquidity: can set initial tick to a manipulated price. In constant-product: can inflate LP share price through donation before the first real deposit.
4. **Liquidity manipulation attacker** — Adds and removes liquidity strategically to extract value from other LPs.
5. **Compromised admin** — Can change fee structures, pause trading, modify routing, or whitelist malicious pools.

**Dominant attack patterns:**
- Sandwich attacks: front-run swap to move price → victim swaps at worse price → back-run to capture difference
- LP share inflation on empty/new pools (donate assets to inflate share price before real deposits)
- Reentrancy through token callbacks (ERC-777, ERC-1155 hooks) during swap execution when pool state is inconsistent
- Price oracle exploitation: other protocols read AMM spot price, attacker manipulates pool in same tx, other protocol uses wrong price
- Concentrated liquidity tick manipulation: force price through tick boundaries to trigger stop-loss-like behavior in other positions
- Fee-on-transfer token accounting errors: pool receives fewer tokens than expected, invariant breaks

**Critical invariants:**
- Pool invariant holds before and after every operation (k = x * y, or curve-specific)
- LP share value is monotonically non-decreasing from fees (absent impermanent loss)
- No tokens can be extracted without proportional LP burn or valid swap math
- Swap output amount matches the invariant-derived calculation exactly (no rounding exploitation)
- Reserves tracked in contract state match actual token balances (no donation attack surface)

**What to look for first:**
1. Swap math: is the invariant correctly maintained? Are there rounding errors that consistently favor one direction?
2. LP mint/burn math: what happens at totalSupply == 0? Is there minimum liquidity enforcement?
3. Does the pool expose `getPrice()`, `observe()`, or similar that other contracts call? If yes, it's an oracle and manipulation has external blast radius.
4. Slippage protection: is it enforced at the router level? Can it be bypassed? What's the default?
5. Reentrancy guards: does the swap update state before making external calls (token transfers)?

---

### Yield Aggregator / Vault

**Primary adversaries** (ranked):
1. **Share inflation attacker (first depositor)** — The canonical vault attack. Deposit 1 wei, donate a large amount directly to the vault (inflating `totalAssets` without minting shares), then when the next user deposits, they receive 0 shares due to rounding and the attacker redeems for the donated + deposited amount.
2. **Malicious/compromised strategy** — Strategies hold the actual funds. A malicious strategy can report fake losses, retain approvals after migration, or transfer funds out.
3. **Reentrancy through external protocol callbacks** — Vault deposits into Aave/Compound/Yearn, which may trigger callbacks during deposit/withdraw. If vault state is inconsistent during the callback window, reentrancy can manipulate share prices.
4. **Donation/direct-transfer attacker** — Sends tokens directly to the vault contract (not through deposit()) to manipulate `totalAssets()` and therefore share price. If `totalAssets` reads `balanceOf(address(this))`, any donation changes the share price.
5. **Compromised admin** — Can add malicious strategies, change allocation weights, set harvester address, or migrate funds to attacker-controlled strategy.

**Dominant attack patterns:**
- ERC4626 share inflation: deposit(1) → donate(large amount) → next depositor gets 0 shares → redeem(all)
- Strategy reports fake gain → inflated share price → attacker deposits at inflated price → strategy reports real value → attacker loses nothing, previous depositors diluted
- Strategy retains token approval after migration to new strategy — old strategy can still pull funds
- Harvest sandwich: front-run harvest() with deposit (get shares cheap), harvest increases totalAssets, back-run with withdraw (redeem at higher share price)
- Vault accounting desync: strategy's real balance differs from vault's recorded allocation due to external protocol behavior (rebasing, slashing, reward accrual)

**Critical invariants:**
- `totalAssets()` accurately reflects real underlying value at all times
- `convertToShares(convertToAssets(shares)) <= shares` — round-trip must not create value
- `convertToAssets(convertToShares(assets)) <= assets` — same in reverse
- Strategy cannot extract more than it was allocated
- Share price can only increase from yield, never from manipulation

**What to look for first:**
1. Share price calculation: `convertToAssets` / `convertToShares`. Is there a virtual offset or minimum deposit to prevent inflation attacks?
2. Strategy interface: what can a strategy do? Can it report arbitrary gain/loss? Who can add/remove strategies?
3. Does `totalAssets()` use `balanceOf(this)` or internal accounting? If balanceOf, donation attacks are possible.
4. Deposit/withdraw: is there reentrancy protection? Are state changes before external calls?
5. Strategy migration: does the old strategy lose all approvals? Is there a cooldown?

---

### Stablecoin

**Primary adversaries** (ranked):
1. **Oracle manipulator** — If collateral price is manipulated upward, attacker can mint stablecoins against less real collateral. If manipulated downward, legitimate positions get liquidated at unfair prices. In algorithmic stablecoins, oracle manipulation can trigger or amplify depegs.
2. **Economic/governance attacker** — Acquires governance power to change collateral parameters (lower ratios, add risky collateral, change stability fees) to extract value or destabilize the peg. Can also manipulate stability mechanisms.
3. **Bank run attacker** — Triggers mass redemption by creating panic or exploiting information asymmetry. If the stablecoin's redemption mechanism has capacity limits, a strategic redemption can drain the best collateral, leaving remaining holders with worse backing.
4. **Flash loan minter** — Flash loans capital to mint stablecoins, manipulates collateral price, and profits from the discrepancy. Especially dangerous if minting has no cooldown or rate limit.
5. **Compromised admin** — Can change collateral types, oracle addresses, debt ceilings, stability fees, or pause redemptions. Any of these can break the peg or trap user funds.

**Dominant attack patterns:**
- Collateral price manipulation → mint at inflated collateral value → sell stablecoins → collateral price returns to normal → protocol is undercollateralized
- Algorithmic death spiral: sell pressure → depeg → collateral value drops → more liquidations → more sell pressure → repeat (LUNA/UST)
- Redemption mechanism DOS: spam redemptions to drain liquid collateral, leaving illiquid collateral backing remaining supply
- Governance attack: change collateral ratio to allow undercollateralized minting
- Oracle staleness exploitation: mint when oracle reports stale (higher) price, redeem when oracle updates to real (lower) price

**Critical invariants:**
- Every stablecoin unit is backed by >= 1:1 collateral value (or >= configured ratio)
- Mint and redeem are inverse operations: round-trip preserves value (no profitable loops)
- Peg mechanism is convergent, not divergent, under sell pressure
- Liquidation can always restore individual position collateralization
- Total supply <= total debt ceiling across all collateral types

**What to look for first:**
1. Minting path: what collateral is accepted → how is it valued (oracle) → what's the ratio → can the ratio be changed?
2. Redemption path: can all stablecoins be redeemed simultaneously? Is there a priority queue? What happens under stress?
3. Liquidation mechanism: is it profitable? What happens if collateral price drops faster than liquidations can execute?
4. What can governance change? How quickly? Is there a peg-break emergency mechanism?
5. Death spiral analysis: if the stablecoin depegs 10%, does the mechanism push it back or amplify the depeg?

---

### Derivatives / Perps

**Primary adversaries** (ranked):
1. **Oracle manipulator** — In derivatives, oracle errors are amplified by leverage. A 1% oracle manipulation on a 50x leveraged position creates a 50% PnL swing.
2. **Liquidation MEV searcher** — Extracts value from liquidation events. In perps, positions can be large and leverage amplifies the liquidation bonus. May also manipulate price to trigger liquidations, then capture the liquidated collateral.
3. **Funding rate manipulator** — Skews open interest to force favorable funding rate payments. With enough capital, can make the funding rate so extreme that opposing positions are forced to close, then reverse to capture the funding.
4. **Position size attacker** — Opens positions larger than the protocol can pay out, or opens positions across multiple accounts to circumvent limits. If the protocol's liquidity pool cannot cover max payout, insolvency results.
5. **Compromised admin** — Can change max leverage, funding rate parameters, liquidation thresholds, or oracle addresses. Can also pause liquidations (creating bad debt) or enable instant position changes that bypass risk checks.

**Dominant attack patterns:**
- Oracle manipulation → cascade liquidation → profit from liquidated positions
- Funding rate manipulation through concentrated one-sided open interest
- Position size exceeding protocol's payout capacity (adversary opens at max leverage, market moves in their favor, protocol can't pay)
- Delayed/stale oracle → risk-free directional bet (see current price off-chain, trade at stale on-chain price)
- Cross-margin exploitation: loss in one position affecting collateral of another, creating liquidation cascades within a single account
- ADL (auto-deleveraging) manipulation: force ADL on profitable opposing positions by creating insolvency conditions

**Critical invariants:**
- Sum of all PnL = 0 (zero-sum between longs and shorts, minus fees)
- Available liquidity >= maximum payout of all open positions under worst-case price movement
- Liquidation triggers before any position can cause bad debt to the system
- Funding rate converges open interest imbalance over time (doesn't diverge)
- Mark price cannot deviate from index price beyond safety bounds

**What to look for first:**
1. PnL calculation: is it correct under all conditions (positive, negative, at leverage limits)?
2. Liquidation threshold vs. actual execution: is there enough margin between liquidation trigger and insolvency?
3. Oracle: mark price vs. index price. How is mark price calculated? Can it be manipulated within a block?
4. Max open interest / position size limits: are they enforced? What happens if total payouts exceed pool?
5. Funding rate: can it be manipulated? What's the maximum rate? Can it drain margin faster than expected?

---

### Liquid Staking

**Primary adversaries** (ranked):
1. **Exchange rate manipulator** — The derivative token's value depends on an exchange rate (stETH/ETH, rETH/ETH). If this rate can be manipulated (through rewards reporting, slashing events, or direct donation), attackers can buy/sell the derivative at wrong prices against protocols that use it as collateral.
2. **Validator set attacker** — Compromises or controls validators that the protocol delegates to. Can trigger slashing events, withhold rewards, or censor transactions. The trust model around validator selection is critical.
3. **Withdrawal queue attacker** — Exploits timing or ordering in the unstaking queue. May front-run large unstake requests to exit first, or manipulate queue mechanics to delay others' withdrawals.
4. **Oracle/rate arbitrageur** — Exploits lag between the on-chain exchange rate and real underlying value. When a slashing event occurs, the on-chain rate may not update immediately — attacker sells derivative at stale (higher) rate before the slash is reflected.
5. **Compromised admin** — Can change validator set, fee parameters, oracle addresses, or withdrawal mechanisms. Can also pause withdrawals, trapping user funds.

**Dominant attack patterns:**
- Rewards/slashing reporting manipulation: report fake rewards to inflate exchange rate, or delay slashing report to exit at stale rate
- Withdrawal queue griefing: spam small unstake requests to delay large withdrawals
- Rebasing token integration bugs: protocols that integrate the liquid staking derivative may not handle rebasing correctly
- Validator collusion: validators withhold blocks or MEV to reduce rewards below expected rate
- Share price manipulation through direct ETH/token transfer to the contract

**Critical invariants:**
- Exchange rate reflects true underlying value (staked assets + rewards - slashing)
- Total derivative supply * exchange rate <= total underlying staked
- Withdrawal queue processes in fair order (no priority manipulation)
- Validator performance doesn't systematically disadvantage stakers
- Slashing events are reflected in exchange rate before any user can exit at stale rate

**What to look for first:**
1. Exchange rate calculation: who reports rewards/slashing? How often? Can it be manipulated?
2. Withdrawal mechanism: is there a queue? What's the delay? Can it be griefed?
3. Validator selection: who chooses validators? Can a malicious validator be added?
4. Does the derivative token rebase or use shares? How do integrating protocols handle this?
5. What happens if a massive slashing event occurs? Is the loss socialized fairly?

---

### Bridge

**Primary adversaries** (ranked):
1. **Validator/relayer set attacker** — Compromises the threshold of validators/relayers needed to approve cross-chain messages. This is the #1 bridge exploit vector by total value lost.
2. **Message replay attacker** — Replays a valid cross-chain message on a different chain or replays the same message multiple times to mint/unlock tokens repeatedly.
3. **Race condition exploiter** — Exploits timing gaps between source and destination chain finality. Initiates action on source chain, front-runs the relay on destination chain, or exploits reorgs to reverse source chain action after destination chain has already processed it.
4. **Fake message crafter** — Crafts a cross-chain message that passes validation but contains malicious data. Exploits weaknesses in message encoding, proof verification, or chain ID validation.
5. **Compromised admin** — Can change validator set, pause bridge (trapping funds), or upgrade contracts to drain locked funds. Bridge admin keys are the highest-value targets in DeFi.

**Dominant attack patterns:**
- Validator key compromise → forge cross-chain messages → mint unbacked tokens on destination
- Message replay: same message processed twice (missing nonce check or nonce overflow)
- Proof verification bypass: merkle proof or signature check has edge case that passes invalid proofs
- Chain ID confusion: message valid on chain A gets processed on chain B
- Reorg exploitation: deposit confirmed on source chain → relayed to destination → source chain reorgs → deposit reversed but destination tokens already minted

**Critical invariants:**
- Locked tokens on source chain = minted tokens on destination chain (1:1 backing)
- Every cross-chain message is processed exactly once (no replay)
- Message cannot be forged without validator threshold consensus
- Bridge accounting is consistent across chains (no cross-chain double-spend)

**What to look for first:**
1. Validator/relayer trust model: how many validators? What's the threshold? Can they be changed?
2. Message replay protection: is there a nonce? Is it checked correctly? Can it overflow?
3. Proof verification: merkle proof, signature scheme. Are there edge cases?
4. Finality assumptions: does the bridge wait for finality on source chain?
5. What can the admin do? Can they drain locked funds? Change validators instantly?

---

### Governance

**Primary adversaries** (ranked):
1. **Flash loan governance attacker** — Borrows governance tokens via flash loan, votes on a proposal, and returns tokens in the same transaction. Only possible if voting power is measured at current block rather than a snapshot.
2. **Governance capture attacker** — Gradually accumulates voting power (buying tokens, borrowing from lending protocols, receiving delegations) to pass malicious proposals. Patient, multi-block attack with potentially massive payoff.
3. **Proposal spam / griefing attacker** — Submits many proposals to exhaust voter attention, or submits proposals that appear benign but have hidden malicious effects (e.g., "update parameter to X" where X causes insolvency).
4. **Timelock exploitation attacker** — Monitors queued proposals and positions to exploit parameter changes the instant they execute.
5. **Compromised admin/guardian** — Can cancel proposals, pause governance, or execute emergency actions that bypass normal governance flow.

**Dominant attack patterns:**
- Flash loan → vote → return: instant governance control if no snapshot
- Bribe attacks: pay token holders to delegate or vote for malicious proposals (via platforms like Votium)
- Proposal obfuscation: malicious calldata hidden in a seemingly-benign proposal
- Timelock front-running: position before queued proposal executes to profit from parameter changes
- Guardian abuse: emergency powers used to bypass governance for non-emergency purposes

**Critical invariants:**
- Voting power is snapshotted at proposal creation (not measured at vote time)
- Quorum requirements prevent minority capture
- Timelock provides sufficient delay for users to exit before parameter changes take effect
- No single role can bypass governance unilaterally for non-emergency actions
- Proposal calldata matches its description (can be verified on-chain)

**What to look for first:**
1. Voting power: snapshot or current balance? If current, flash loan attack is trivial.
2. Quorum and threshold: are they high enough to prevent capture? What's the token distribution?
3. Timelock: is the delay nonzero? Is it long enough for users to react?
4. What can governance control? List every parameter/action that goes through governance.
5. Emergency powers: who has them? What can they do? Can they drain funds?
# Temporal Threat Dimension

DeFi protocols have a lifecycle, and different threats dominate at different phases. This reference provides per-phase threat intelligence. The skill auto-detects which phases are relevant from code signals and includes the applicable phases in the threat model.

## Phase Detection

Detect which phases are relevant from code patterns found during Step 2 source reading:

| Phase | Include When |
|-------|-------------|
| **Deployment & Initialization** | Always include — every protocol has this phase |
| **Steady State** | Always include — this is the baseline |
| **Market Stress** | Oracle integration exists, OR liquidation logic exists, OR collateral/debt tracking exists, OR any price-dependent calculation |
| **Governance & Upgrade Windows** | Timelock exists, OR governance contract exists, OR proxy pattern (UUPS/transparent/beacon) exists, OR `propose()`/`vote()`/`execute()` functions exist |
| **Deprecation & Wind-down** | V2/migration in contract names or comments, OR `migrate()` function exists, OR deprecated contract references, OR multi-version architecture |

---

## Phase 1: Deployment & Initialization

The most dangerous 24-48 hours. The protocol transitions from code to live system with real money. Attackers actively monitor deployment transactions.

### Threats

**Initialization front-running:**
Attacker watches the mempool for `initialize()` calls and front-runs with malicious parameters. Critical for UUPS proxies where `initialize()` sets the owner. Also applies to pool creation, market listing, and oracle setup.

What to look for: `initialize()` / `init()` functions without access control or without `initializer` modifier. Proxy deployment where `initialize` is called in a separate transaction from deployment. Pool/market creation that can be called by anyone.

**Parameter misconfiguration:**
Protocol deployed with testing parameters still active. DELAY=0 in timelocks, test oracle addresses, overly permissive access control, dev-mode fee settings. The code is correct but the configuration creates the vulnerability.

What to look for: Hardcoded constants that look like test values (0 delays, max uint fees, known test addresses like 0xdead). Constructor/initializer parameters without validation. Default values that are insecure.

**Ownership not transferred:**
Contract deployed with deployer EOA as owner, intended to transfer to multisig, but transfer hasn't happened yet. Creates a window where a single key controls everything.

What to look for: `Ownable` without `transferOwnership()` in deployment scripts. Two-step ownership transfer that hasn't been accepted. Role-based access where roles haven't been granted to the intended addresses.

**Empty-state exploitation:**
Protocols behave differently when empty. First depositor can manipulate share prices (vault inflation), set initial pool prices, or establish initial state that disadvantages subsequent users.

What to look for: `if (totalSupply == 0)` branches. Pool creation with attacker-chosen initial prices/ratios. Vault deposit when totalAssets == 0. Missing minimum initial deposit requirements.

**Deployment ordering bugs:**
Contracts deployed in wrong order, missing approvals between contracts, circular dependencies not resolved, proxy pointing at wrong implementation.

What to look for: Deployment scripts with multiple transactions. Contracts that reference each other (circular setup). Approval chains (token approvals, role grants) that must happen in specific order.


---

## Phase 2: Steady State

Normal operation. This is where the existing adversary types (flash loan, MEV, external user, compromised admin) operate. The standard threat model covers this phase — no additional temporal-specific content needed. The protocol-type threat profiles provide the detailed guidance for this phase.

---

## Phase 3: Market Stress

Protocols that work perfectly in calm markets can break catastrophically during volatility. This phase accounts for some of the largest DeFi losses (LUNA/UST, cascading liquidations during Black Thursday).

### Threats

**Oracle latency under volatility:**
Oracle heartbeat periods (1h for some Chainlink pairs) mean prices can be stale during rapid market moves. Every calculation using that price is wrong for the duration. Borrowers can be liquidated at unfair prices, or worse, cannot be liquidated at all (stale price shows healthy position while real value is underwater).

What to look for: Chainlink `latestRoundData()` calls — what staleness threshold is used? Is it appropriate for the asset's volatility? Is the heartbeat period documented/configured or hardcoded? Is there a deviation threshold check? What happens if `updatedAt` is 0 or in the future?

**Liquidation cascade:**
Position A is liquidated → liquidation dumps collateral on market → price drops further → Position B is liquidated → cycle repeats. The protocol's own liquidation mechanism amplifies the crash. Can cause systemic insolvency.

What to look for: Liquidation mechanism — does it sell collateral on-market (creating price impact)? Is there a circuit breaker? Is liquidation throttled? Can the protocol handle 30%+ collateral price drops in a single block?

**Liquidity evaporation:**
During stress, LPs withdraw liquidity. Swaps have worse slippage. Liquidation bots can't efficiently swap collateral. Bad debt accumulates because liquidations become unprofitable at the gas + slippage cost.

What to look for: Liquidation profitability assumptions — are they valid when liquidity is thin? Does the protocol assume swap paths exist with sufficient depth? Is there a minimum liquidity requirement?

**Correlated asset depeg:**
Protocol assumes USDC = $1, stETH = ETH, wBTC = BTC. During stress, these correlations break. A lending protocol that treats stETH as equivalent to ETH suddenly has undercollateralized positions.

What to look for: Hardcoded price equivalences (1:1 assumptions). Missing oracle for derivative assets (using underlying asset's oracle instead). Collateral factors that don't account for depeg risk.

**Gas price spikes:**
Critical operations (liquidations, rebalancing, oracle updates) become prohibitively expensive. Time-sensitive operations fail to execute. Keepers and bots stop operating because gas cost exceeds profit.

What to look for: Gas-sensitive operations (keeper-dependent flows). Liquidation incentive vs. gas cost assumptions. Operations that must execute within a time window. Are there fallback mechanisms for keeper failure?

**Withdrawal stampede:**
Many users try to withdraw simultaneously. If the protocol has limited liquid reserves (funds deployed in strategies, locked in positions), early withdrawers drain liquidity and late withdrawers are stuck.

What to look for: Withdrawal queues, rate limits. What percentage of TVL is liquid vs. deployed? Can strategies be unwound quickly? Is there a withdrawal fee that increases under stress (to discourage runs)?


---

## Phase 4: Governance & Upgrade Windows

Every governance action or upgrade creates a transient vulnerability window. The transition period between "old state" and "new state" is when exploits happen.

### Threats

**Timelock exploitation window:**
A governance proposal is queued with a known timelock delay. Everyone can see what parameters will change. Attackers position before execution to exploit new parameters immediately. Example: if collateral factor increases, max borrow the instant the timelock executes.

What to look for: Timelock durations — are they long enough for users to react? Can users exit positions before parameter changes take effect? Are there parameters that could be exploited if their pending value is publicly known?

**Upgrade storage collision:**
Proxy upgrade changes storage layout, corrupting existing state. Balances become wrong, ownership changes unexpectedly, access control breaks. The new implementation reads old storage through a different layout.

What to look for: UUPS `_authorizeUpgrade`, transparent proxy patterns. Is there storage gap usage? Are upgrades tested with the actual storage layout? Is there an upgrade validation step?

**Flash loan governance:**
Attacker borrows governance tokens via flash loan, votes, and returns tokens in same transaction. Trivial if voting power is measured at current block. Some protocols are immune (snapshot-based voting), others are not.

What to look for: Voting power source — `balanceOf(msg.sender)` (vulnerable) vs. snapshot at proposal creation block (immune). Can governance tokens be borrowed from lending protocols?

**Governance capture (slow):**
Attacker accumulates voting power over time — buying tokens, receiving delegations, borrowing from Aave. Once threshold is reached, passes malicious proposals. The timelock is the last defense.

What to look for: Token distribution — is voting power concentrated? What's the quorum? Can a well-funded attacker buy enough tokens to pass proposals? Is there a guardian that can veto?

**Migration window:**
Protocol migrates from V1 to V2. During migration, funds are in transit. Approval chains exist between old and new contracts. Users who don't migrate lose access or face degraded conditions. The V1→V2 bridge is an attack target.

What to look for: Migration functions, V1→V2 transfer mechanisms. Do V1 contracts retain fund access? Is there a deadline? Can migration be front-run?


---

## Phase 5: Deprecation & Wind-down

Protocols don't live forever. When maintenance stops, a new class of threats emerges. Include this phase only when there's evidence of version transitions, deprecation markers, or multi-version architecture.

### Threats

**Residual funds in deprecated contracts:**
Old contracts still hold tokens but monitoring/maintenance has stopped. Keepers no longer run. Oracles go stale permanently. Any exploitable path in the old contract becomes a free-money opportunity with zero monitoring.

What to look for: Multi-version architecture. Are old versions still accessible? Do they still hold funds? Is there a forced migration mechanism?

**Abandoned approval chains:**
Users who interacted with V1 still have active token approvals to V1 contracts. If V1 has any exploitable path, those user approvals are a liability — attacker can drain user wallets through the deprecated contract.

What to look for: Does the protocol use `approve()` (unlimited) or `permit()`? Is there a mechanism to revoke approvals during migration? Are users notified?

**Dependent protocol breakage:**
Other protocols that integrate with the deprecated protocol don't know it's deprecated. They continue calling functions that return stale data, empty results, or revert unexpectedly.

What to look for: Does this protocol serve as an oracle or data source for others? Is there a deprecation flag or kill switch that integrators can check?

**Frozen state exploitation:**
When governance stops or admin keys are lost, the protocol is frozen in its last configuration. Market conditions change but parameters can't be updated. Interest rates, collateral factors, oracle parameters all become increasingly stale.

What to look for: What happens if no governance proposal passes for 6 months? Are there parameters that must be periodically updated? Is there an automated fallback?

---

## Writing the Temporal Risk Profile

In the output, include a "Temporal Risk Profile" subsection within Section 2. For each applicable phase:

1. **Name the phase** and state why it's relevant to this protocol
2. **List the specific threats** that apply (not all threats from every phase — only those where the code has the relevant patterns)
3. **Cite the code location** where the temporal risk exists
4. **Assess mitigation**: is the risk mitigated, partially mitigated, or unmitigated?

Keep it concise — 2-4 bullets per applicable phase. Phase 2 (Steady State) is covered by the main threat model, so skip it in the temporal section to avoid duplication.
# Cross-Protocol Composability Threats

DeFi's unique property is composability — protocols interact with other protocols, creating emergent risks that don't exist in isolated analysis. This reference provides a systematic framework for identifying and documenting composability threats.

## External Call Classification

During Step 2 source reading, every external call is already extracted. This enhancement **classifies** each call into the composability threat taxonomy. For each external call found, determine:

1. **Target type**: Oracle, DEX/AMM, Lending pool, Yield protocol, Token, Governance, Bridge, Other
2. **Assumptions about return value**: What does this protocol assume the external call returns? (correct price, exact token amount, success, specific format)
3. **Validation present**: Does the code validate the return? (bounds check, staleness check, zero check, success check)
4. **Mutability of external behavior**: Can the external contract's behavior change without this protocol's consent? (upgradeable proxy? governed parameters?)
5. **Fallback on failure**: What happens if the external call fails? (revert, silent failure, fallback value, try/catch with fail-open?)

---

## Layer 1: Direct Dependency Risks

The protocol directly calls external contracts. These are visible in the code — every `interface` import and external call is a direct dependency.

### Oracle Dependency Chain

The protocol reads prices from an oracle. But that oracle aggregates from sources that can be manipulated.

**Threat**: Protocol → Oracle → underlying source(s). If any source in the chain is manipulable within the protocol's trust assumptions, the oracle is effectively manipulable.

**What to look for:**
- What oracle is used? (Chainlink, Uniswap TWAP, Pyth, custom)
- What's the oracle's aggregation method? (median of N sources, TWAP, VWAP)
- Staleness check: is `updatedAt` validated? What threshold? Is the threshold appropriate for the asset?
- Deviation check: is the returned price bounded against a reference? (e.g., within 5% of previous price)
- Zero/negative check: what happens if oracle returns 0?
- Sequencer uptime check: on L2s, is the sequencer uptime feed checked?
- Fallback oracle: if primary fails, is there a fallback? Is the fallback also validated?
- Can admin change the oracle address? Instantly or through timelock?

### Yield Strategy Dependency

Protocol deposits funds into external yield protocols (Aave, Compound, Yearn, Convex, etc.).

**Threat**: The external protocol holds the actual funds. If it gets exploited, paused, or changes behavior, this protocol's funds are at risk. The strategy is the bridge between "our code" and "their code."

**What to look for:**
- What protocols do strategies deposit into? List each one.
- Is the external protocol upgradeable? By whom? Through what process?
- Can the external protocol pause withdrawals? Under what conditions?
- Does the strategy have emergency withdrawal capability?
- What happens if the strategy reports a loss? How is it socialized?
- Can new strategies be added? By whom? Instantly or through timelock?
- Does the old strategy retain approvals after migration?
- Are there reentrancy risks through the external protocol's callbacks?


### Token Behavior Assumptions

Every `token.transfer()`, `token.transferFrom()`, `token.balanceOf()` call carries implicit assumptions about token behavior.

**Threat**: The code assumes standard ERC20 behavior. Non-standard tokens break these assumptions silently — no revert, just wrong accounting.

**Assumption matrix** (check each for every token the protocol handles):

| Assumption | Standard Tokens | Violating Tokens | Impact if Violated |
|-----------|----------------|-----------------|-------------------|
| Transfer sends exact amount | ERC20 | Fee-on-transfer (USDT with fee, PAXG) | Internal accounting > real balance, protocol becomes insolvent |
| Balance doesn't change without transfer | ERC20 | Rebasing (stETH, AMPL, aTokens) | Accounting drift, share price manipulation |
| Transfer always succeeds (or reverts) | ERC20 | USDT (returns false, no revert) | Silent transfer failure, lost funds |
| No callback on transfer | ERC20 | ERC-777, ERC-1155 | Reentrancy through transfer callback |
| 18 decimals | Most tokens | USDC (6), WBTC (8), GUSD (2) | Math errors, massive over/under-valuation |
| Token can't block specific addresses | Most tokens | USDC, USDT (blacklist), cUSDC | Withdrawal blocked, funds trapped |
| Token can't be paused | Most tokens | USDC, USDT | All protocol operations blocked |
| Token is immutable | Most tokens | Upgradeable tokens (USDC proxy) | Behavior changes post-deployment without consent |
| No max supply cap affecting mint | Most tokens | Some algorithmic tokens | Deposit credited but tokens never arrive |

**What to look for:**
- Does the code use `balanceOf(before) - balanceOf(after)` pattern? (handles fee-on-transfer)
- Does the code use SafeERC20? (handles non-reverting tokens)
- Are token decimals dynamic or hardcoded?
- Does the code handle rebasing token balance changes?
- Is there a token whitelist, or can arbitrary tokens be used?

### Callback Reentrancy

External calls can trigger callbacks that re-enter the protocol before state is finalized.

**Threat**: Even with reentrancy guards on direct calls, callbacks through external protocols can bypass them. Token transfer → external protocol callback → re-enter through a different function.

**What to look for:**
- State changes after external calls (violating checks-effects-interactions)
- Reentrancy guards: are they per-function or global? Per-function guards don't protect cross-function reentrancy
- ERC-777 tokens: `tokensReceived` hook fires on transfer
- ERC-1155 tokens: `onERC1155Received` fires on transfer
- Aave/Compound flash loan callbacks
- Uniswap swap callbacks
- Vault deposit/withdraw that triggers strategy interaction which triggers external callback

---

## Layer 2: Shared State Risks

Two or more protocols interact with the same underlying state, creating indirect dependencies that are invisible in isolated code review.

### Liquidity Coupling

**Threat**: Protocol A and Protocol B both use the same Uniswap pool for swaps or pricing. A large action in Protocol A moves the pool price, affecting Protocol B's calculations within the same block.

**What to look for:**
- Does the protocol swap through public pools? Which ones?
- Do those pools have significant TVL relative to the protocol's swap sizes?
- Could a large liquidation in this protocol move a pool price enough to affect other protocols?
- Is the protocol itself a significant LP in pools that other protocols use?

**Example**: Protocol uses Uniswap ETH/USDC pool for liquidation swaps. Large liquidation dumps ETH into the pool, cratering the pool price. Another lending protocol uses the same pool's spot price as an oracle. Cascade.

### Oracle Sharing

**Threat**: Multiple protocols use the same oracle feed. A market event triggers liquidations across all of them simultaneously, creating correlated selling pressure and oracle feedback loops.

**What to look for:**
- Which oracle feeds does this protocol use?
- Are these the same feeds used by major lending/derivatives protocols?
- Could liquidations in this protocol create sell pressure that affects the oracle price?
- Could liquidations triggered by the oracle price in *other* protocols create sell pressure that triggers liquidations *here*?

### Approval Chain Exposure

**Threat**: Users grant token approvals to protocol contracts. If any approved contract has an exploitable path, user funds are at risk even if users never interact with the vulnerable function.

**What to look for:**
- Does the protocol request unlimited approvals? (`type(uint256).max`)
- Are approvals scoped to specific functions or broad?
- If the protocol is upgradeable, an upgrade could add a function that drains approved tokens
- Are there deprecated contracts that still hold user approvals?

---

## Layer 3: Temporal Composability Risks

External protocols change over time. This protocol's assumptions about them can silently become invalid.

### Governance-Induced Behavior Change

**Threat**: An external protocol's governance changes a parameter that this protocol's logic depends on. No contract interaction changed, but economic assumptions broke.

**What to look for:**
- Does this protocol assume specific parameter values from external protocols? (interest rates, collateral factors, fee tiers)
- Are external protocol parameters read dynamically or hardcoded?
- Would an external parameter change require this protocol to update its own parameters?

**Example**: Aave governance changes ETH collateral factor from 80% to 75%. A vault strategy that assumes 80% leverage ratio is now over-leveraged and at liquidation risk.

### Upgrade-Induced Interface Change

**Threat**: External protocol upgrades its implementation. Function signatures are the same, but behavior changes (gas cost, revert conditions, return values, side effects).

**What to look for:**
- Are external dependencies behind upgradeable proxies?
- Does this protocol's error handling account for behavior changes? (try/catch that assumes specific revert reasons)
- Are gas estimates hardcoded that could break if external protocol's gas usage changes?

### Deprecation Without Notification

**Threat**: External protocol deprecates an oracle feed, a pool, or an endpoint. The call doesn't revert — it returns stale/wrong data silently. Or it starts reverting, and this protocol's try/catch falls through to an unsafe default.

**What to look for:**
- Are there freshness checks on all external data sources?
- What's the try/catch fallback behavior? Does it fail-open (use stale data) or fail-closed (revert)?
- Is there monitoring for external dependency health?

### Dependency-of-Dependency Upgrade

**Threat**: This protocol uses Protocol A, which uses Protocol B. Protocol B upgrades. Protocol A's behavior changes. This protocol's behavior changes. No visibility into the root cause.

**What to look for:**
- Map the full dependency chain (2-3 levels deep). For each level:
  - Is it upgradeable?
  - Is it governed?
  - Can its behavior change without this protocol's knowledge?
- The deeper the chain, the less control this protocol has. Flag chains deeper than 2 levels.

---

