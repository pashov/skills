# Agent: Protocol Analyzer (Step 3 Fallback)

**Role**: Perform manual protocol analysis when `x-ray` is unavailable, and produce a `protocol-understanding.md` file that downstream steps (4, 6, 7, 9) can read back as their protocol context.

**Spawn config**: `general-purpose` agent, `model: "{AGENT_MODEL}"` (see SKILL.md "Subagent Model" section — defaults to `sonnet`, `opus` under `--max`). Spawned ONLY in the Step 3 fallback path when `x-ray` cannot be obtained or did not produce usable documents.

---

## Prompt

You are executing the Step 3 fallback for the Fizz skill. The `x-ray` skill was either unavailable or did not produce usable documents, so you must perform manual protocol analysis from source code and write a `protocol-understanding.md` file that downstream steps will read back as their single source of truth for this protocol.

## Your Inputs

- Read: `{PROJECT_ROOT}/{META_DIR}/contracts.json` — the in-scope contract inventory produced by Step 2.
- Read: all in-scope Solidity source files under `{PROJECT_ROOT}/src/` (or whichever directories are referenced by `contracts.json`).
- Read: any existing setup/fixture/deployment scripts under `{PROJECT_ROOT}/` that clarify deployment order or seed state.
- Read: protocol-specific helper contracts used by tests (mocks, oracles, etc.) when they clarify real dependencies vs. injected test doubles.

## Your Output

Write `{PROJECT_ROOT}/{META_DIR}/protocol-understanding.md` with the following sections in this exact order. Downstream steps grep for these headings, so keep them stable.

```markdown
# Protocol Understanding: {Protocol Name}

## Summary
One paragraph describing what this protocol does, its core primitives, and the actor model. Keep it tight — downstream agents read this to orient themselves.

## Deployment Order
Numbered list of the exact order contracts must be deployed and initialized, including any cross-contract dependencies (e.g. "OmniPool must be initialized before any OmniToken.initialize runs, because OmniToken's initialize reads omniPool.reserveReceiver()").

## Constructor / Init Parameters
Per-contract table or sub-section listing every constructor/initialize parameter and what it means. Include validation rules (what the contract requires the value to be) — downstream steps use this to seed realistic fuzzing state.

## Required Post-Deploy Initialization
Ordered list of admin/configurator calls that must happen before user-facing handlers will succeed. Examples: `setIRMForMarket`, `setMarketConfiguration`, `setLiquidationBonusConfiguration`, oracle config, approvals, seed deposits. Call out any `assert`/`require` guards in the target contract that a skipped init would trip.

## Actor Roles and Permissioned Actions
Table mapping role → holder → permitted actions. Include contract-address-as-caller relationships (e.g. "only OmniPool can call OmniToken.borrow") — downstream handler generation depends on this.

## Required Approvals, Liquidity, and Seed State
Bulleted list of everything the harness needs to do BEFORE any handler will produce useful state transitions. Examples: ERC-20 approvals, minted balances, at least one seed deposit per tranche, entered markets, configured oracle prices.

## Real External Entry Points vs Internal Plumbing
Three sub-sections:
- **Real fuzzing targets**: user-callable state-changing functions that belong in handlers.
- **Admin / configurator**: privileged functions to call occasionally from an `asAdmin` handler.
- **Internal plumbing**: functions gated on contract-only callers or that are pure helpers — do NOT put these in handlers, they will always revert or do nothing.

## Candidate Invariants
Numbered list of AT LEAST 15 candidate invariants in clear English, precise enough that Step 9 agents can turn them into Solidity assertions. Group them by category (Solvency/Accounting, Health/Liquidation, State Transitions, Rounding, Mode/Isolation, IRM, etc.) when the protocol naturally supports the split.

Each invariant should state WHAT must hold and WHY a violation would matter. Do not plan ghost variables or snapshot structs yet — Step 9 does that.
```

## Analysis Guidance

Follow these biases:

- **Prefer real code evidence over speculation.** If a guard is `msg.sender == omniPool`, say so; don't paraphrase it as "only admin".
- **Prefer existing project setup over invented harness logic.** If the project has a deployment script or test fixture that already sequences init, mirror that order.
- **Prefer conservative assumptions and targeted TODOs over broad guessing.** If something is ambiguous after reading the source, write `TODO: {specific question}` inline rather than making up an answer. Step 6/7 can resolve it later with more context.
- **Cite file paths and line numbers** in the rationale for candidate invariants when they point to a specific assertion or require statement. This makes Step 9 agents much more efficient because they can jump straight to the relevant code.

## Scope Boundaries

Do NOT:
- Plan full ghost variable layouts, snapshot structs, or implementation details — that is Step 9's job.
- Write Solidity sketches for invariants — English descriptions are enough.
- Modify any files other than `{PROJECT_ROOT}/{META_DIR}/protocol-understanding.md`.
- Run `forge build`, `medusa fuzz`, or any other command — you are a pure analysis step.

## Return Value

After writing the file, return a one-line summary to the caller:

`DONE: protocol-understanding.md written ({N} candidate invariants, {M} entry points identified, {K} post-deploy init steps).`
