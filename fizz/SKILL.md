---
name: fizz
description: Generate Echidna/Medusa-compatible Solidity fuzz suites from Foundry or Hardhat projects. Trigger on "fizz", "generate fuzz suite", "build fuzz harness", "stateful fuzzing", "fuzzing harness", "property testing", and "invariant suite".
---

# Fizz

Generate a stateful Solidity fuzz suite under `{SUITE_DIR}` (default: `test/fizz/`), with metadata and fuzzer runtime files under `{META_DIR}` (default: `fizz_data/`).

Use `Echidna` and `Medusa` for invariant campaigns. Use `Foundry` for compilation, smoke testing, and quick debugging.

## Workflow Rules

- Follow the steps in order. Do not skip forward if a required artifact for the current step does not exist yet.
- If a step fails, stop there and report the blocker.
- If tooling is missing, say exactly what was attempted and what is missing.
- Keep the generated Solidity suite isolated under `test/fizz/` and the metadata/runtime files under `fizz_data/` unless the user explicitly asks for different paths.
- Reuse existing project setup and test logic whenever possible; do not invent a deployment flow if the repo already has one.

## Parameters

- `PROJECT_ROOT`: user-provided path, otherwise the current working directory.
- `SKILL_PATH`: the directory containing this `SKILL.md`.
- `SUITE_DIR`: `test/fizz` relative to `PROJECT_ROOT`. Pass `--suite-dir` to suite-generation steps.
- `META_DIR`: `fizz_data` relative to `PROJECT_ROOT`. Pass `--meta-dir` to metadata steps.
- Optional contract arguments narrow handler generation to specific contracts.
- `--no-invariants` skips Step 9 only.
- `--max` (or `--opus`, or "max quality") upgrades every subagent in this run from Sonnet to Opus. See "Subagent Model" below.
- `--guided` / `--automatic` selects the run mode. See "Run Mode" below.

## Run Mode

The skill runs in one of two modes, resolved once at the start of the run and reused for every checkpoint below:

- `{MODE} = "guided"` — the parent agent pauses for user input at key checkpoints: Step 3 (additional docs), Step 4 (interactive function picker UI), Step 4.5 (cost confirmation), Step 6 (setup review), Step 8 (per-cycle coverage decision), Step 9c (property review), Step 10 (fuzzer choice).
- `{MODE} = "automatic"` — the parent agent never pauses. Step 4 runs with `--auto`, Step 8 loops up to 3 coverage cycles then proceeds, Step 10 defaults to Medusa, and the cost estimate from Step 4.5 is printed but not gated on user confirmation.

### Resolving `{MODE}`

- If the user invoked with `--guided` / "guided mode" / "walk me through" / "let me review" → `{MODE} = "guided"`.
- If the user invoked with `--automatic` / `--auto` / "unguided" / "run the whole thing" / "no prompts" → `{MODE} = "automatic"`.
- Otherwise, leave `{MODE}` unresolved; Step 0 asks for it via the selection prompt **after** printing the banner.

Every subsequent instruction referencing `{MODE}` must substitute the resolved value. Do NOT switch modes mid-run.

## Subagent Model

All subagents spawned by this skill (Step 3 fallback Protocol Analyzer, the 5 Step 9b discovery agents, the Step 9c Synthesizer, the 2 Step 9d Implementers, and the Step 11 Report Writer) default to **Sonnet** for cost and latency. 

The parent agent orchestrating the pipeline is whatever model the user's Claude Code session is running (this skill does not control it). Only the delegated subagents are covered by `{AGENT_MODEL}`.

### Resolving `{AGENT_MODEL}`

Resolve once at the start of the run and reuse it for every spawn below:

- If the user invoked with `--max` / `--opus` / "max quality" / "run on opus" / similar → `{AGENT_MODEL} = "opus"`.
- If the user invoked with `--sonnet` / "use sonnet" / "default model" → `{AGENT_MODEL} = "sonnet"`.
- Otherwise, leave `{AGENT_MODEL}` unresolved; Step 0 asks for it via the selection prompt **after** printing the banner.

Every subsequent spawn instruction below references `{AGENT_MODEL}` — substitute the resolved value when making the actual tool call. Do NOT mix tiers within a single run.

## Step 0: Print Banner

At the start of every skill run, **first** print this ASCII banner once before any other output — including any selection prompt:

```text

██████╗  █████╗ ███████╗██╗  ██╗ ██████╗ ██╗   ██╗     ███████╗██╗  ██╗██╗██╗     ██╗     ███████╗
██╔══██╗██╔══██╗██╔════╝██║  ██║██╔═══██╗██║   ██║     ██╔════╝██║ ██╔╝██║██║     ██║     ██╔════╝
██████╔╝███████║███████╗███████║██║   ██║██║   ██║     ███████╗█████╔╝ ██║██║     ██║     ███████╗
██╔═══╝ ██╔══██║╚════██║██╔══██║██║   ██║╚██╗ ██╔╝     ╚════██║██╔═██╗ ██║██║     ██║     ╚════██║
██║     ██║  ██║███████║██║  ██║╚██████╔╝ ╚████╔╝      ███████║██║  ██╗██║███████╗███████╗███████║
╚═╝     ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝ ╚═════╝   ╚═══╝       ╚══════╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝╚══════╝
                                
```

After the banner, resolve `{MODE}` per the "Run Mode" section and `{AGENT_MODEL}` per the "Subagent Model" section. For any value still unresolved from invocation flags, ask the user via a single `AskUserQuestion` tool call containing only the unresolved questions (skip the call entirely if both were resolved from flags).

**Output discipline (mandatory)**: Between the banner block and the `AskUserQuestion` invocation, emit **no user-facing text whatsoever** — no "I'll ask about…", no "loading the tool…", no acknowledgement that flags were missing. If `AskUserQuestion`'s schema needs to be fetched via `ToolSearch` first, do that silently as well. The user should see banner → selection UI → resolved-values lines, with nothing in between. This overrides the default behavior of narrating intent before tool calls.

- **Question for `{MODE}`** — `header: "Run mode"`, `question: "How should I run?"`, options:
  - `label: "Automatic (Recommended)"`, `description: "Run end-to-end with no prompts."`
  - `label: "Guided"`, `description: "Pause at 7 checkpoints: extra docs, entry-point picker (browser UI), cost confirm, setup review, per-cycle coverage decision, property review, fuzzer choice."`
- **Question for `{AGENT_MODEL}`** — `header: "Subagent model"`, `question: "Which model should drive the subagents?"`, options:
  - `label: "Sonnet (Recommended)"`, `description: "Default. Faster and cheaper for the 5 discovery agents, synthesizer, and 2 implementers."`
  - `label: "Opus"`, `description: "Higher quality but ~10× the cost. Equivalent to passing --max / --opus."`

Map the user's selections back to `{MODE}` (`automatic` / `guided`) and `{AGENT_MODEL}` (`sonnet` / `opus`), then print these two lines so the resolved values are visible in transcript:

- `Mode: guided` or `Mode: automatic` — the resolved `{MODE}`.
- `Subagent model: sonnet` (default) or `Subagent model: opus (--max)` (if `--max` / `--opus` / "max quality" / "use opus" / Opus selection was requested).

## Step 1: Verify Tooling And Environment

Run sequentially:

1. Read [template-map.md](./references/template-map.md).
2. Run `forge --version`.
3. If `forge --version` fails, tell the user that Foundry is missing and suggest installing it using the official documentation:
   Foundry install guide: `https://www.getfoundry.sh/introduction/installation`
4. If `forge --version` fails, stop here. Foundry is required before proceeding with the rest of the workflow.
5. Run `bash {SKILL_PATH}/scripts/ensure_foundry.sh {PROJECT_ROOT}`.
6. If `foundry.toml` is missing, allow `ensure_foundry.sh` to create one. If it fails, stop and report the error.
7. Run `medusa --version`.
8. Run `echidna --version`.
9. If either command fails, tell the user which tool is missing and suggest installing it using the official documentation:
   Medusa install guide: `https://secure-contracts.com/program-analysis/medusa/docs/src/getting_started/installation.html`
   Echidna install guide: `https://secure-contracts.com/program-analysis/echidna/introduction/installation.html`
10. If `medusa --version` fails, stop here. Medusa is required before proceeding with the rest of the workflow.
11. If `echidna --version` fails but Foundry and Medusa are installed, you may continue, but keep the installation recommendation in the user-facing summary because Echidna is still expected for the full workflow.

## Step 2: Compile And Extract

Run sequentially:

1. Read `{PROJECT_ROOT}/foundry.toml`.
2. Run `cd {PROJECT_ROOT} && forge build`.
3. Run `node {SKILL_PATH}/scripts/extract_abis.js {PROJECT_ROOT} --meta-dir {META_DIR}`.

## Step 3: Understand The Protocol

This step exists to drive setup, handler selection, and invariant generation quality.

If `{MODE} = "guided"`, before touching any analysis source first ask the user: *"Any additional docs, links, whitepapers, spec files, or prior-audit notes I should consider? (paste paths or URLs, or reply 'none')"*. If the user provides anything, write the raw list to `{PROJECT_ROOT}/{META_DIR}/additional-context.md` (one entry per line, include URLs verbatim). Later sub-steps of this step — and Step 9a — must read that file if it exists and fold it into the protocol-understanding context.

Start by checking whether `{PROJECT_ROOT}/x-ray/` exists and contains `x-ray.md`. `x-ray.md` is REQUIRED — without it, x-ray output is considered unavailable regardless of which other files are present.

If `{PROJECT_ROOT}/x-ray/x-ray.md` exists, read it first as the primary project-understanding source. Then also read any of these supplementary files present in `{PROJECT_ROOT}/x-ray/`:

If `{PROJECT_ROOT}/x-ray/x-ray.md` does NOT exist, you MUST run the **x-ray Acquisition Protocol** below. The Protocol Analyzer fallback (Attempt 4) is FORBIDDEN until Attempts 1–3 have each been executed and their outcomes recorded in `/tmp/x-ray-attempts.md`. "I think x-ray isn't available" is NOT a valid skip — only the recorded output of an actual tool/command counts.

### x-ray Acquisition Protocol

Before Attempt 1, delete `/tmp/x-ray-attempts.md` if it exists (`rm -f /tmp/x-ray-attempts.md`) — stale entries from a previous run would falsely satisfy the Attempt 4 gate. Then create a fresh `/tmp/x-ray-attempts.md` and append one entry per attempt: timestamp, attempt name, command/tool invoked, exact output (or "no output"), outcome (`SUCCESS` / `FAILED: {reason}` / `SKIPPED: {reason}`). Attempt 4 requires the file to contain exactly 3 entries (one per Attempt 1, 2, 3) — `SKIPPED` entries count toward this total.

- **Attempt 1 — invoke the skill.** Call the `x-ray` skill via the `Skill` tool with `args="{PROJECT_ROOT}"`. Do NOT pre-judge availability — invoke it. Only a runtime error of the form "skill not found" / "unknown skill" counts as unavailable. If it runs, wait for completion, then verify `{PROJECT_ROOT}/x-ray/x-ray.md` was written. If yes → SUCCESS, exit Protocol.
- **Attempt 2 — install from the official source and re-invoke.** Run:
  ```bash
  git clone --depth 1 https://github.com/pashov/skills.git /tmp/pashov-skills-xray-install \
    && mkdir -p ~/.claude/skills \
    && cp -r /tmp/pashov-skills-xray-install/x-ray ~/.claude/skills/x-ray
  ```
  Then re-invoke `Skill('x-ray', args="{PROJECT_ROOT}")`. If `{PROJECT_ROOT}/x-ray/x-ray.md` is produced → SUCCESS, exit Protocol. If the re-invocation still returns "skill not found" / "unknown skill" (auto-discovery did not pick up the freshly installed skill mid-session), do NOT mark this attempt failed yet — instead read `~/.claude/skills/x-ray/SKILL.md` (or `/tmp/pashov-skills-xray-install/x-ray/SKILL.md`) and execute its instructions inline against `{PROJECT_ROOT}`. If that produces `{PROJECT_ROOT}/x-ray/x-ray.md` → SUCCESS, exit Protocol. Only if ALL of (Skill re-invocation, inline execution) fail does this attempt count as FAILED.
- **Attempt 3 — guided-mode user gate (guided only).** If `{MODE} = "guided"` AND Attempts 1–2 both failed, ASK the user: *"Could not obtain x-ray automatically (logs in `/tmp/x-ray-attempts.md`). Options: (a) paste an x-ray.md path, (b) authorize Protocol Analyzer fallback, (c) abort. Choose a/b/c."* Record their answer. If (a) and the file exists → copy to `{PROJECT_ROOT}/x-ray/x-ray.md`, SUCCESS. If (c) → halt the skill. Only (b) — explicit user authorization — permits Attempt 4. In `{MODE} = "automatic"`, skip this attempt and record `SKIPPED: automatic mode`.
- **Attempt 4 — Protocol Analyzer fallback.** Permitted ONLY after Attempts 1–3 are recorded in `/tmp/x-ray-attempts.md` (with status FAILED, SKIPPED, or — for Attempt 3 only — `(b) authorized`). Before spawning, confirm the file exists and contains 3 entries; if not, GO BACK to the missing attempt — do not proceed.

    Fallback: Read `{SKILL_PATH}/agents/protocol-analyzer.md`, replace `{SKILL_PATH}` with the actual `{SKILL_PATH}`, `{PROJECT_ROOT}` with the actual `{PROJECT_ROOT}`, and `{META_DIR}` with the actual `{META_DIR}`, then spawn as a `general-purpose` agent with `model: "{AGENT_MODEL}"`. The agent reads the source files, then writes the analysis to `{PROJECT_ROOT}/{META_DIR}/protocol-understanding.md` so that later steps can read it back instead of relying on conversation context.

From the `x-ray` documentation or `protocol-understanding.md` infer and summarize:

- deployment order
- constructor parameter meaning
- required post-deploy initialization
- actor roles and permissioned actions
- approvals, liquidity, or other state needed before handlers will be useful
- which external functions are real fuzzing entry points versus protocol-internal plumbing
- candidate invariants to carry forward into Step 9

If something is still ambiguous after those reads, keep going with a conservative assumption and leave a targeted TODO later instead of guessing broadly.

Do not plan full ghost-variable layouts, snapshot structs, or final implementation details here. Do record the likely invariants clearly so Step 9 can reuse them from `{PROJECT_ROOT}/x-ray/` or `{PROJECT_ROOT}/{META_DIR}/protocol-understanding.md` as its starting point.

## Step 4: Select Entry Points

Read [selection-policy.md](./references/selection-policy.md).

Create `{PROJECT_ROOT}/{META_DIR}/entry-point-selection.json` as a filtered copy of `{PROJECT_ROOT}/{META_DIR}/contracts.json` that keeps the functions most likely to produce useful state transitions.

Build the preselection from the protocol understanding gathered in Step 3 — primarily the x-ray entry-point map (if available) and source-level access control observations. If Step 3 produced an entry-point map with caller or access annotations, use that as the primary filter: exclude functions marked as internal-caller-only or contract-to-contract plumbing. Use `{PROJECT_ROOT}/{META_DIR}/contracts.json` only as the structural template for the output JSON format, not to decide which functions to include.

Then run:

- If `{MODE} = "automatic"`:
  `node {SKILL_PATH}/scripts/select_functions.js {PROJECT_ROOT} --contracts {PROJECT_ROOT}/{META_DIR}/contracts.json --selection {PROJECT_ROOT}/{META_DIR}/entry-point-selection.json --meta-dir {META_DIR} --auto`
- If `{MODE} = "guided"`:
  `node {SKILL_PATH}/scripts/select_functions.js {PROJECT_ROOT} --contracts {PROJECT_ROOT}/{META_DIR}/contracts.json --selection {PROJECT_ROOT}/{META_DIR}/entry-point-selection.json --meta-dir {META_DIR}`

The `--auto` flag accepts the inferred selection and exits immediately. Without it, the script opens a browser UI with the inferred selection pre-checked so the user can adjust and confirm. Both paths write `entry-point-selection.json`.

After the script completes, read `{PROJECT_ROOT}/{META_DIR}/entry-point-selection.json`.

If the script exits before writing `entry-point-selection.json`, stop and report that failure.

Print a short summary:

- selected contracts
- selected functions by contract
- notable excluded functions

### Dispatcher for Low-Frequency Functions

After reading the selection, classify the selected functions into two tiers:

- **Primary**: core user flows that should be called frequently by the fuzzer (deposit, withdraw, mint, redeem, borrow, repay, swap, stake, unstake, claim, liquidate, etc.)
- **Secondary**: less common functions that are still useful but should be called less often (admin setters, configuration changes, pause/unpause, role grants, parameter tuning, etc.)

Write this classification to `{PROJECT_ROOT}/{META_DIR}/entry-point-selection.json` by adding a `"tier": "primary"` or `"tier": "secondary"` field to each function entry.

In Step 7, secondary-tier functions will be wrapped in a dispatcher handler that groups them behind a single entry point with an enum selector. This reduces call frequency naturally without excluding them entirely — the fuzzer picks a random selector value, so secondary functions get exercised occasionally but don't dominate the call sequence.

If the user already excluded a function during selection, it stays excluded. The dispatcher is only for functions the user chose to keep but that should be deprioritized.

`{PROJECT_ROOT}/{META_DIR}/entry-point-selection.json` limits handler generation only. It does not limit the setup dependency graph.

## Step 4.5: Cost Estimate

Run:

`node {SKILL_PATH}/scripts/estimate_cost.js {PROJECT_ROOT} --meta-dir {META_DIR} --model {AGENT_MODEL} --mode {MODE}`

The script reads `entry-point-selection.json`, applies a size bucket based on selected-function count, and writes `{PROJECT_ROOT}/{META_DIR}/cost-estimate.md` with a per-stage breakdown plus a total and an expected range. The numbers are Anthropic list-price ballparks; actual cost varies with coverage cycles, re-runs, and prompt-cache hit rate.

Print the cost estimate table to the user. Then:

- If `{MODE} = "automatic"`: continue to Step 5 without pausing.
- If `{MODE} = "guided"`: ask the user *"Proceed with this estimate, or abort?"* and wait for confirmation before continuing. If the user aborts, stop the run and report where the artifacts so far were written.

## Step 5: Generate Scaffold

Run:

`node {SKILL_PATH}/scripts/generate_suite.js {PROJECT_ROOT} --suite-dir {SUITE_DIR} --meta-dir {META_DIR}`

This copies the full template scaffold into `{PROJECT_ROOT}/{SUITE_DIR}/`, including core harness files and utility files such as `utils/MockERC20.sol`. It also writes the fuzzer config files (`echidna.yaml`, `medusa.json`) into `{PROJECT_ROOT}/`.

It also reads `{PROJECT_ROOT}/{META_DIR}/entry-point-selection.json` and generates one stub handler file per selected contract under `{PROJECT_ROOT}/{SUITE_DIR}/handlers/`. Those stubs include the clamped and unclamped section headers but no sample handler functions. `Handlers.sol` is scaffolded to import and inherit from all generated handler stubs.

Treat the copied files as the starting point only. The next steps must modify them to fit the target protocol.

## Step 6: Modify Core Files And Wire Setup

Read [setup-playbook.md](./references/setup-playbook.md) and [template-map.md](./references/template-map.md).

Modify the scaffolded core files under `{PROJECT_ROOT}/{SUITE_DIR}/`. Use [template-map.md](./references/template-map.md) as the source of truth for the inheritance chain, file roles, and which scaffolded files are expected to be refined in this step versus later steps.

Use [setup-playbook.md](./references/setup-playbook.md) as the source of truth for:

- proxy and upgradeability detection
- setup requirements and good defaults
- mock-versus-real dependency choices
- signature-dependent setup guidance
- `Base.sol` integration points and TODO/FIXME policy

When the target protocol depends on simple external ERC20s that are not part of the in-scope deployment graph, prefer the scaffolded `utils/MockERC20.sol` helper unless the project already includes a more faithful token mock.

The key output of this step is a **compiling** scaffold with a realistic `Base.sol::setup()` function and the rest of the core scaffold adjusted to match it.

If `{MODE} = "guided"`, after the edits to `Base.sol` are complete and before running `forge build`, print a **Setup Review** block summarising what was wired:

- Contracts deployed in `setup()` (name + address variable + constructor args source)
- Proxies detected and which implementation each wraps
- Mocks vs real dependencies used, with the reason for each mock
- Actors configured (addresses + role), and which ones the fuzzer will impersonate via handler caller selection
- Seeded balances (token, recipient, amount)
- Roles / access-control grants (role, grantee)
- Approvals (token, owner, spender, amount)

Then ask the user: *"Setup looks right? Reply 'proceed' to build, or tell me what to adjust."* If the user requests adjustments, apply them and re-print the review block; loop until they approve. In `{MODE} = "automatic"`, skip the review block and continue directly.

Run `cd {PROJECT_ROOT} && forge build` before moving on.

## Step 7: Generate Handlers

Read [handler-patterns.md](./references/handler-patterns.md).

First, run the handler generation script to produce pre-populated stubs with correct function signatures and type mappings:

`node {SKILL_PATH}/scripts/generate_handlers.js {PROJECT_ROOT} --suite-dir {SUITE_DIR} --meta-dir {META_DIR}`

Then read these in parallel:

- `{PROJECT_ROOT}/{SUITE_DIR}/handlers/Handlers.sol`
- each generated `{PROJECT_ROOT}/{SUITE_DIR}/handlers/<Contract>Handler.sol`
- each selected contract source file

Then refine the generated `{PROJECT_ROOT}/{SUITE_DIR}/handlers/<Contract>Handler.sol` for the selected contracts. The stubs already contain correct signatures and clamping hints — focus on wiring the actual protocol calls, adding semantic clamping, and implementing boundary-value stress variants.

Use [handler-patterns.md](./references/handler-patterns.md) as the source of truth for:

- clamped versus unclamped handler structure
- handler shaping and semantic action selection
- caller context
- clamping strategy
- edge-case and signature-dependent handler guidance

Update `Handlers.sol` to import and inherit from all generated handlers.

Run `cd {PROJECT_ROOT} && forge build` and fix compile issues before moving on.

## Step 8: Reach Coverage With Medusa

Before generating invariants, ensure the generated harness can drive enough protocol coverage under Medusa.

### Via-IR Coverage Deflation Handling

When `via_ir = true` is set in `foundry.toml`, the Yul IR optimizer aggressively merges and eliminates branches. This deflates Medusa's coverage numbers — you may be at 85% source coverage but Medusa reports 65%. This must be handled before the first Medusa run.

**Step 8.0: Detect and configure fuzz profile.**

1. Read `{PROJECT_ROOT}/foundry.toml` and check whether `via_ir = true` is set under `[profile.default]` or at the top level.
2. If `via_ir` is not enabled, skip this subsection — no fuzz profile is needed.
3. If `via_ir` is enabled, run:

```
bash {SKILL_PATH}/scripts/setup_fuzz_profile.sh {PROJECT_ROOT}
```

This script:
- Appends a `[profile.fuzz]` section to `foundry.toml` with `via_ir = false`
- Runs `FOUNDRY_PROFILE=fuzz forge build`
- If compilation succeeds: exits 0, prints `FUZZ_PROFILE=no-ir`
- If "stack too deep" error: retries with `via_ir = true` and `optimizer_runs = 0`, exits 0, prints `FUZZ_PROFILE=ir-no-opt`
- If both fail: exits 1 (use default profile, accept deflated coverage)

4. Read the script output to determine the fuzz profile mode:
   - `FUZZ_PROFILE=no-ir` → accurate coverage, use standard targets
   - `FUZZ_PROFILE=ir-no-opt` → reduced deflation but still some; lower coverage targets by ~10%
   - Script failed → fall back to default profile; lower coverage targets by ~15-20%

5. Record the profile mode in `{PROJECT_ROOT}/{META_DIR}/coverage-targets.md` at the top:
   - `no-ir`: "Fuzz profile: via_ir disabled — coverage numbers are accurate"
   - `ir-no-opt`: "Fuzz profile: via_ir required (stack too deep), optimizer_runs=0 — coverage deflated ~10%, targets adjusted"
   - default fallback: "Fuzz profile: via_ir required with optimizer — coverage deflated ~15-20%, targets adjusted"

6. For all subsequent `forge build` commands in Steps 8–11, use:
   - `cd {PROJECT_ROOT} && FOUNDRY_PROFILE=fuzz forge build` (if fuzz profile was created)
   - `cd {PROJECT_ROOT} && forge build` (if no fuzz profile needed)

Store the build command in a variable `{FUZZ_BUILD_CMD}` for reuse in later steps.

### Medusa Runs

Every Medusa run in this step must use `run_medusa.js`, including reruns after harness changes. Do not switch to raw `medusa fuzz` for later cycles in this step.

Before launching Medusa, rebuild with the fuzz profile if one was configured:

```
{FUZZ_BUILD_CMD}
```

Run the Medusa script asynchronously using the agent's command-execution tool. This is critical — do NOT use shell backgrounding (`&`), do NOT use `sleep` + `tail` to poll, and do NOT wait synchronously in a single blocking command. Start the process in a way the agent runtime can track and notify on completion.

```
node {SKILL_PATH}/scripts/run_medusa.js {PROJECT_ROOT} --meta-dir {META_DIR} --coverage-mode
```

The wrapper starts a temporary local browser log viewer and prints its URL, but does not open the browser by default. Read the viewer URL from the wrapper output and provide it to the user. Add `--logs` to the command only if the user asks for the viewer to open in their browser automatically.

When the background command completes and you are notified, inspect the resulting coverage with focus on the core protocol contracts, not peripheral mocks or helper libraries.

### Dynamic Coverage Targets

Not all contracts require the same coverage. Assign per-contract targets based on the contract's role:

| Contract Role | Target (no-ir) | Target (ir-no-opt) | Target (ir fallback) |
|---|---|---|---|
| Core protocol logic (vault, pool, lending core, staking engine) | 80%+ | 70%+ | 65%+ |
| Access control / role management | 60%+ | 50%+ | 45%+ |
| Peripheral helpers (routers, views, adapters) | 50%+ | 40%+ | 35%+ |
| Libraries and math utilities | Coverage inherited from callers | Same | Same |

Use the column matching the fuzz profile mode determined in Step 8.0.

After the first Medusa run, review the per-contract coverage report and classify each contract. If a contract has legitimately unreachable paths in the harness context (e.g., fork-only branches, multi-block MEV paths, oracle-failure paths), note them and adjust that contract's target downward rather than wasting cycles on unreachable code.

Write the per-contract targets and any skip justifications to `{PROJECT_ROOT}/{META_DIR}/coverage-targets.md` so the user can review them.

### Coverage Iteration Loop

- with `--coverage-mode`, the wrapper runs `medusa fuzz --timeout 300`, allows at least 60 seconds of fuzzing, then stops earlier if 5 consecutive progress lines show no increase in `branches hit`, and prints the coverage report path when finished (add `--logs` to also open it in the browser)
- if coverage is below target, improve handler shapes, clamping, setup, approvals, seed balances, caller roles, and any missing lifecycle actions
- when debugging why a specific handler or call sequence is not reaching the expected code paths, or when validating a hypothesis, use `FoundryTester.sol` to quickly PoC it
- rerun `{FUZZ_BUILD_CMD}` before each new Medusa run
- treat one cycle as: run `node {SKILL_PATH}/scripts/run_medusa.js {PROJECT_ROOT} --meta-dir {META_DIR} --coverage-mode`, inspect coverage, adjust the harness, then rebuild

After each cycle, build and print a per-contract coverage summary table from the Medusa coverage report:

| Contract | Role | Target | Hit | Status |
|---|---|---|---|---|

`Status` is `✅` if Hit ≥ Target, else `❌`. Append the same table to `{PROJECT_ROOT}/{META_DIR}/coverage-targets.md` under a timestamped `## Cycle N` heading so the history is preserved.

Then branch on `{MODE}`:

- `{MODE} = "automatic"`: if all contracts meet target, give a brief summary and proceed. Otherwise loop; cap at 3 cycles total, then log remaining gaps in `coverage-targets.md` and proceed to the next step with the current harness.
- `{MODE} = "guided"`: after every cycle (including cycle 1), ask the user *"iterate / adjust targets / proceed"*. `iterate` = run another cycle with the current harness adjustments. `adjust targets` = let the user edit per-contract targets in `coverage-targets.md` before the next cycle. `proceed` = exit the loop regardless of gaps. Honour the user's choice; there is no hard cap in guided mode.

After exiting the loop, provide the coverage report path for optional review: `{PROJECT_ROOT}/{META_DIR}/corpus_medusa/coverage/coverage_report.html`.

### Acceptable Skip Reasons

It is acceptable to skip coverage for specific functions or paths when:

- the function requires external state that cannot be simulated (e.g., specific oracle prices from a live feed)
- the path is a revert-only guard that is intentionally unreachable in the harness (e.g., `require(msg.sender == bridgeContract)`)
- the function is behind a time-lock or multi-sig that the harness doesn't simulate
- the function interacts with an external protocol that is not mocked

Document each skip in `{PROJECT_ROOT}/{META_DIR}/coverage-targets.md` with the reason.

Do not move to invariant generation while Medusa coverage is still clearly too low for the selected flows, unless the user explicitly tells you to proceed anyway.

## Step 9: Generate Invariants (5 Parallel Discovery Agents + Synthesizer + 2 Implementers)

Skip this step only when the user passed `--no-invariants`.

This is the make-or-break step. It uses **5 specialized discovery agents in parallel**, each applying a different invariant discovery approach drawn from 50+ real DeFi bugs caught by fuzzers.

### Step 9a: Build Invariant Context

Read [property-generation.md](./references/property-generation.md), then build `INVARIANT_CONTEXT` by reading:

- the invariant notes captured in Step 3 from `{PROJECT_ROOT}/x-ray/x-ray.md` when available, otherwise `{PROJECT_ROOT}/{META_DIR}/protocol-understanding.md`
- `{PROJECT_ROOT}/{META_DIR}/additional-context.md` if it exists (guided-mode supplementary docs/links from Step 3)
- all in-scope source files
- `Base.sol`, `Snapshots.sol`, `Properties.sol`
- all generated handler files

Extract from the codebase:
- **AGGREGATE_VARIABLES**: grep for variables named `total*`, `sum*`, `accumulated*`, or any variable that multiple functions write to
- **PAIRED_OPERATIONS**: match function pairs (deposit/withdraw, mint/burn, add/remove, lock/unlock, open/close, stake/unstake, borrow/repay, create/destroy, join/exit)
- **CONVERSION_FUNCTIONS**: grep for `convertTo*`, `preview*`, `toAssets`, `toShares`, or any function mapping between two unit systems
- **ACCESS_CONTROL**: grep for `onlyOwner`, `onlyAdmin`, `onlyRole`, `require(msg.sender`, custom role modifiers

### Step 9b: Spawn 5 Discovery Agents in Parallel

**CRITICAL**: All 5 agents MUST be spawned in a SINGLE message (one tool call per agent, all in the same response).

| Agent | File | Discovery Approach |
|-------|------|-------------------|
| 1. Conservation Auditor | `{SKILL_PATH}/agents/invariant-discovery/conservation-auditor.md` | Sum-of-parts = tracked-whole for every aggregate variable |
| 2. Round-Trip & Rounding Analyst | `{SKILL_PATH}/agents/invariant-discovery/roundtrip-rounding-analyst.md` | Forward+inverse operations, directional rounding |
| 3. State Transition Mapper | `{SKILL_PATH}/agents/invariant-discovery/state-transition-mapper.md` | Postconditions, monotonicity, entity counts, state machine |
| 4. Adversarial Profit Maximizer | `{SKILL_PATH}/agents/invariant-discovery/adversarial-profit-maximizer.md` | Attacker thinking — DoS, value extraction, edge states |
| 5. Protocol-Type Specialist | `{SKILL_PATH}/agents/invariant-discovery/protocol-type-specialist.md` | Auto-detect type, apply domain templates (vault/lending/AMM/etc.) |

Read each agent file, replace `{INVARIANT_CONTEXT}` and `{FILE_PATHS}` with actual values, spawn as `general-purpose` agent with `model: "{AGENT_MODEL}"`.

### Step 9c: Synthesize Property Plan

After all 5 agents return, read the Synthesizer agent file:

| Agent | File |
|-------|------|
| 6. Synthesizer | `{SKILL_PATH}/agents/invariant-discovery/synthesizer.md` |

Replace `{AGENT_OUTPUTS}` with the outputs from agents 1-5, `{META_DIR}` with the actual `{META_DIR}` path, `{PROJECT_ROOT}` with the actual `{PROJECT_ROOT}` path, and `{SUITE_DIR}` with the actual `{SUITE_DIR}` path, then spawn as `general-purpose` agent with `model: "{AGENT_MODEL}"`.
The Synthesizer merges, deduplicates, prioritizes, and writes BOTH:
- `{PROJECT_ROOT}/{META_DIR}/property-plan.md` — implementation tables with stable Spec IDs (`GL-NN`, `SP-NN`)
- `{PROJECT_ROOT}/PROPERTIES.md` — English-language spec with `[ ]` checkboxes, one entry per property, identified by the same Spec IDs. This is the artifact that the `/fizz-convert` command and the implementers in Step 9d operate on.

Each property carries a **Guarantee** tag set at generation time — `SHOULD-HOLD` (explicitly guaranteed by docs/spec/standard or an exact identity, with evidence cited) or `EXPLORATORY` (inferred). This tag is what lets Step 10 triage a violation without post-campaign severity guessing: a violated SHOULD-HOLD property is a confirmed bug, a violated EXPLORATORY property is a lead for human review.

Print a summary: "Generated X properties (N HIGH, N MEDIUM, N LOW; P SHOULD-HOLD, Q EXPLORATORY)" with a brief list of the top properties by priority.

If `{MODE} = "guided"`, pause here: tell the user the file path (`{PROJECT_ROOT}/PROPERTIES.md`), summarise what the Synthesizer produced, and ask *"Review `PROPERTIES.md` and edit freely — rename, add, remove, or reword properties. Keep the Spec IDs (`GL-NN` / `SP-NN`) on entries you want implemented, and leave `[ ]` checkboxes unchanged. Reply 'proceed' when done, or 'regenerate' to re-run the Synthesizer with additional guidance."* If they reply `regenerate`, ask what to change, then re-spawn the Synthesizer (Step 9c) with the extra guidance appended to its input. If they reply `proceed`, continue to Step 9d. In `{MODE} = "automatic"`, skip the pause and proceed directly.

### Step 9d: Implement Properties (2 Parallel Agents)

Read each agent file:

| Agent | File | Scope |
|-------|------|-------|
| 7A. Global Property Implementer | `{SKILL_PATH}/agents/implementers/global-property-implementer.md` | Ghosts in Base.sol, State in Snapshots.sol, global properties in Properties.sol, harness contracts if needed |
| 7B. Specific Property Implementer | `{SKILL_PATH}/agents/implementers/specific-property-implementer.md` | Specific properties in Properties.sol, handler wiring (ghost updates + snapshot calls + property assertions) |

Replace `{META_DIR}` with the actual `{META_DIR}` path, `{SKILL_PATH}` with the actual `{SKILL_PATH}` path, `{PROJECT_ROOT}` with the actual `{PROJECT_ROOT}` path, and `{SUITE_DIR}` with the actual `{SUITE_DIR}` path, then spawn both as `general-purpose` agents with `model: "{AGENT_MODEL}"` in parallel.

Both implementers MUST flip `[ ]` → `[x]` in `{PROJECT_ROOT}/PROPERTIES.md` for each property they actually implement (matching by Spec ID `GL-NN` / `SP-NN`). Properties left as TODO stubs stay `[ ]` so `/fizz-convert` can pick them up later.

### Step 9e: Validate

Run `{FUZZ_BUILD_CMD}` after the edits. Fix any compilation errors.

If a property is low-confidence after implementation, prefer a commented TODO over a brittle assertion.

## Step 10: Run Campaigns

After invariant generation and validation, run a full fuzzing campaign to find property violations.

### Fuzzer Selection

- `{MODE} = "automatic"`: default to **Medusa** — faster with multi-worker parallelism and better suited for initial runs.
- `{MODE} = "guided"`: ask the user *"Which fuzzer for this campaign — Medusa (default, parallel workers) or Echidna?"* and use their answer. If they express no preference, default to Medusa.

Do not run both fuzzers simultaneously — this consumes excessive resources and can cause system instability or crashes. Campaign Iteration (below) is where a complementary run on the other fuzzer is offered.

### Running the Campaign

Run the wrapper for the chosen fuzzer, either **Medusa** or **Echidna** (ONLY ONE), asynchronously using the agent's command-execution tool, then wait for that tracked background job to finish — the wrapper exits when the fuzzer's own stop condition triggers or the `--timeout` is reached. Both wrappers start a temporary local browser log viewer and print its URL, but do not open the browser by default; read the viewer URL from the wrapper output and provide it to the user. Add `--logs` to the command only if the user asks for the viewer to open in their browser automatically.

For **Medusa**, run this command:

```
node {SKILL_PATH}/scripts/run_medusa.js {PROJECT_ROOT} --meta-dir {META_DIR} --timeout 600
```

For **Echidna**, run this command:

```
node {SKILL_PATH}/scripts/run_echidna.js {PROJECT_ROOT} --meta-dir {META_DIR} --timeout 600
```

If Echidna fails with `unlinked libraries detected in bytecode`, link the libraries in `echidna.yaml`:

```yaml
deployContracts: [["0xf1", "Lib1"], ["0xf2", "Lib2"]]
cryticArgs: ["--compile-libraries=(Lib1,0xf1), (Lib2,0xf2)"]
```

Replace `Lib1`, `Lib2` with the actual library names and `0xf1`, `0xf2` with the desired deployment addresses.

### Interpreting Results

After the campaign completes:

- check for property violations (failed assertions)
- for each violation, extract the call sequence that triggered it
- verify the violation is a real bug, not a harness issue — if the property or handler has a bug, fix it and rerun
- **triage by the violated property's Guarantee tag** (from `PROPERTIES.md`): a violated **SHOULD-HOLD** property is a confirmed bug — the protocol broke a documented/mathematical guarantee, so report it as such; a violated **EXPLORATORY** property is flagged for human review — it may be a real bug or an over-strong inferred assumption, so present the call sequence and let a human judge rather than asserting a bug. Always rule out a harness/property bug first regardless of tag.
- if no violations were found, report that the campaign completed cleanly with the coverage achieved
- if violations were found, document each one with the failing property name, its Guarantee tag, the call sequence, and the contract state at failure

### Campaign Iteration

If the user wants to explore further after the first campaign:

- offer to run the other fuzzer (Echidna if Medusa was used, or vice versa) for a complementary pass
- offer to increase the timeout or test limit
- offer to adjust handler shapes based on coverage gaps observed during the campaign

## Step 11: Validate And Report

Run:

1. `{FUZZ_BUILD_CMD}`
2. If `FoundryTester.sol` exists, `cd {PROJECT_ROOT} && FOUNDRY_PROFILE=fuzz forge test --match-contract FoundryTester` (or without `FOUNDRY_PROFILE` if no fuzz profile was created)

If validation fails:

- fix the specific broken files
- do not regenerate the whole suite unless the user asks
- limit repair retries to 3 cycles, then report the remaining issues cleanly

### Generate Violation Repros

If the campaign in Step 10 found property violations, generate a Foundry reproduction test for each distinct violation in `FoundryTester.sol`. This turns fuzzer output into deterministic, one-command proof that the violation is real.

**When to run**: only when `{PROJECT_ROOT}/{META_DIR}/corpus_medusa/test_results/` contains violation JSON files (Medusa) or the Echidna log contains `failed!` lines with call sequences. If the campaign found no violations, skip this sub-step entirely.

**How to generate repros**:

1. Read each violation file (Medusa: one JSON per violation in `test_results/`; Echidna: parse call sequences from the log after each `failed!` line).
2. For each distinct violated property (group multiple reproductions of the same property — use only the shortest call sequence):
   - Create a `test_repro_<propertyName>()` function in `FoundryTester.sol`.
   - Replay the shrunk call sequence by calling the handler functions from the JSON `methodSignature` and `inputValues` fields directly.
   - Between calls, use `vm.roll()` and `vm.warp()` to advance block number and timestamp by the `blockNumberDelay` and `blockTimestampDelay` from each call entry.
   - The fuzzer's `from` addresses map to actors by index: `0x10000` → `actors[0]`, `0x20000` → `actors[1]`, `0x30000` → `actors[2]`. The clamped handlers accept an actor seed parameter that runs through `toActor()`, so pass the raw fuzzer input values — the seed modulus selects the right actor.
   - **Two violation patterns require different test structures**:
     - **Global property violations** (`property_*` functions that return `bool`): replay the full call sequence, then assert the property returns `false`: `assertFalse(property_xxx(), "property should be violated");`. The test **passes** when the property is violated.
     - **Inline assertion violations** (`_prop_*` / `_check*` assertions inside handlers that revert via `assert()` / `t()`): the violating handler call will revert with `panic(0x01)` before any post-call assertion can run. Wrap the violating call in `try this._repro_helperN() { revert("assertion should have fired"); } catch {}`, where `_repro_helperN()` is an `external` helper function that calls the handler. The `try/catch` proves the assertion fired. The test **passes** when the catch triggers.
3. Run `{FUZZ_BUILD_CMD}` and then `cd {PROJECT_ROOT} && FOUNDRY_PROFILE=fuzz forge test --match-contract FoundryTester -vvv` to confirm all repro tests pass.
4. If a repro test fails to compile or does not reproduce the violation, fix it (max 2 attempts per test). If it still fails, comment out the test body with a `// TODO: manual repro needed — fuzzer sequence did not reproduce under Foundry` note and move on.

**Repro naming convention**: `test_repro_<propertyName>` (e.g., `test_repro_property_solvency`, `test_repro_prop_depositIncreasesShares`). If the same property was violated by multiple distinct root causes (different call sequences hitting different code paths), suffix with `_1`, `_2`.

### Final Report

After validation succeeds, spawn the Report Writer subagent to synthesize the final report. Read `{SKILL_PATH}/agents/report-writer.md`, replace `{SKILL_PATH}` with the actual `{SKILL_PATH}`, `{PROJECT_ROOT}` with the actual `{PROJECT_ROOT}`, `{META_DIR}` with the actual `{META_DIR}`, and `{SUITE_DIR}` with the actual `{SUITE_DIR}`, then spawn as a `general-purpose` agent with `model: "{AGENT_MODEL}"`.

The agent reads the campaign outputs (coverage, corpus, `medusa-run.log`, `PROPERTIES.md`, `Properties.sol`, handler files, open TODOs) and writes `{PROJECT_ROOT}/{META_DIR}/report.md`.

The report-writer agent will also print the report content to the conversation (so the user sees it inline) and remind the user of the commands to run campaigns manually:

- `medusa fuzz` (from project root)
- `echidna . --contract FuzzTester --config echidna.yaml`

### Snapshot For Future Re-Use

After the final report is written, capture a sync snapshot so the `/fizz-sync` skill can detect drift on subsequent source changes without re-running the full pipeline:

```
node {SKILL_PATH}/scripts/fizz_sync.js {PROJECT_ROOT} --init --meta-dir {META_DIR} --suite-dir {SUITE_DIR}
```

If the snapshot already exists (because a prior run already initialised it), re-run with `--refresh-snapshot` instead so the new baseline reflects the current state:

```
node {SKILL_PATH}/scripts/fizz_sync.js {PROJECT_ROOT} --refresh-snapshot --meta-dir {META_DIR} --suite-dir {SUITE_DIR}
```

This writes `{PROJECT_ROOT}/{META_DIR}/last-run.json` — a hash+signature snapshot of the in-scope contracts, handlers, and `PROPERTIES.md` entries. Later, when the user modifies sources and invokes `/fizz-sync`, that skill diffs against this file to detect added/removed/changed functions, quarantine stale properties, and regenerate only the drifted handler stubs.
