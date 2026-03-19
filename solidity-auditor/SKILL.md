---
name: solidity-auditor
description: Security audit of Solidity code while you develop. Trigger on "audit", "check this contract", "review for security". Modes - default (full repo) or a specific filename.
---

# Smart Contract Security Audit

You are the orchestrator of a parallelized smart contract security audit.

## Mode Selection

**Exclude pattern:** skip directories `interfaces/`, `lib/`, `mocks/`, `test/` and files matching `*.t.sol`, `*Test*.sol` or `*Mock*.sol`.

- **Default** (no arguments): scan all `.sol` files using the exclude pattern. Use Bash `find` (not Glob).
- **`$filename ...`**: scan the specified file(s) only.

**Flags:**

- `--file-output` (off by default): also write the report to a markdown file (path per `{resolved_path}/report-formatting.md`). Never write a report file unless explicitly passed.
- `--log-output` (off by default): persist intermediate results to a timestamped directory. See **Logging**. Never write log files unless explicitly passed.

## Orchestration

**Turn 1 — Discover.** Print the banner, then make these parallel tool calls in one message:

a. Bash `find` for in-scope `.sol` files per mode selection
b. Glob for `**/references/attack-vectors/attack-vectors.md` — extract the `references/` directory (two levels up) as `{resolved_path}`
c. ToolSearch `select:Agent`
d. Read the local `VERSION` file from the same directory as this skill
e. Bash `curl -sf https://raw.githubusercontent.com/pashov/skills/main/solidity-auditor/VERSION`
f. Bash `mktemp -d /tmp/audit-XXXXXX` → store as `{bundle_dir}`

If the remote VERSION fetch succeeds and differs from local, print `⚠️ You are not using the latest version. Please upgrade for best security coverage. See https://github.com/pashov/skills`. If it fails, skip silently. If `--log-output`: also Bash `mkdir -p assets/audit-logs/{YYYYMMDD-HHMMSS}/` → `{log_dir}` (can parallel with above).

**Turn 2 — Prepare.** In one message, make parallel tool calls: (a) Read `{resolved_path}/report-formatting.md`, (b) Read `{resolved_path}/judging.md`.

Then **classify** each in-scope file by path/name heuristics (do NOT read files for classification):

- **Core** — entry-point contracts, main business logic, state-changing external/public functions that move value or update critical storage. Top 30–40% of files by importance.
- **Peripheral** — interfaces, abstract bases, libraries, pure helpers, access-control boilerplate, simple wrappers.

**Heuristic rules** (apply in order, first match wins):
- Filename starts with `I` + uppercase letter (e.g., `IERC20.sol`, `ISolvBTC.sol`) → Peripheral
- Path contains `interfaces/`, `access/`, `utils/`, `external/`, `governance/`, `libraries/` → Peripheral
- Filename contains `Factory`, `Deployer`, `Proxy`, `Beacon` → Peripheral
- Filename ends with `.t.sol`, `.s.sol`, or contains `Test`, `Mock`, `Script` → skip (already excluded)
- Filename contains `Oracle` → Peripheral
- Everything else → Core
- If fewer than 30% of files are Core, demote the smallest/simplest remaining Core files. If more than 40%, promote the most important Peripheral files.
- If a classification is genuinely ambiguous from the name alone, read that file (and only that file) to decide.

Write classification to `{bundle_dir}/classification.md` (two sections: `## Core`, `## Peripheral`).

Then build all bundles in a single Bash command using `cat` (not shell variables or heredocs):

1. `{bundle_dir}/core-source.md` — core `.sol` files, each with a `### path` header and fenced code block.
2. `{bundle_dir}/file-manifest.md` — peripheral file paths (one per line, `- ` prefix), header `# Peripheral Files (read on demand)`.
3. Agent bundles = `core-source.md` + `file-manifest.md` + agent-specific files:

| Bundle               | Appended files (relative to `{resolved_path}`)                                                                  |
| -------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `agent-1-bundle.md`  | `attack-vectors/attack-vectors.md` + `hacking-agents/vector-scan-agent.md` + `hacking-agents/shared-rules.md`   |
| `agent-2-bundle.md`  | `hacking-agents/math-precision-agent.md` + `hacking-agents/shared-rules.md`                                     |
| `agent-3-bundle.md`  | `hacking-agents/access-control-agent.md` + `hacking-agents/shared-rules.md`                                     |
| `agent-4-bundle.md`  | `hacking-agents/economic-security-agent.md` + `hacking-agents/shared-rules.md`                                  |
| `agent-5-bundle.md`  | `hacking-agents/execution-trace-agent.md` + `hacking-agents/shared-rules.md`                                    |
| `agent-6-bundle.md`  | `hacking-agents/invariant-agent.md` + `hacking-agents/shared-rules.md`                                          |
| `agent-7-bundle.md`  | `hacking-agents/periphery-agent.md` + `hacking-agents/shared-rules.md`                                          |
| `agent-8-bundle.md`  | `hacking-agents/first-principles-agent.md` + `hacking-agents/shared-rules.md`                                   |

Print line counts for every bundle, `core-source.md`, and `file-manifest.md`. Do NOT inline file content into agent prompts.

**Turn 3 — Spawn.** In one message, spawn all 8 agents as parallel foreground Agent calls. Prompt template (substitute real values):

```
Your bundle file is {bundle_dir}/agent-N-bundle.md (XXXX lines).
The bundle contains core source code inline and a peripheral file manifest.
Read the bundle first, then read peripheral files relevant to your specialty.
```

If `--log-output`: after all agents return, write each output to `{log_dir}/agent-{N}-output.md` (8 parallel writes).

**Turn 4 — Deduplicate.** Parse every FINDING and LEAD from all 8 agents. Group by `group_key` field (format: `Contract | function | bug-class`). Exact-match first; then merge synonymous bug_class tags sharing the same contract and function. Keep the best version per group, number sequentially, annotate `[agents: N]`.

Check for **composite chains**: if finding A's output feeds into B's precondition AND combined impact is strictly worse than either alone, add "Chain: [A] + [B]" at confidence = min(A, B). Most audits have 0–2.

Output the deduplicated list as text (not to a file):

```
## [N] Title
- **Type:** FINDING | LEAD
- **Contract:** contract name
- **Function:** function name
- **Bug class:** tag
- **Agents:** [agents: N]
- **Description:** one-paragraph summary from the best agent version
- **Key code:** the relevant code snippet or location
```

If `--log-output`: also write to `{log_dir}/dedup-decisions.md` and `{log_dir}/chain-analysis.md`.

**Turn 5 — Validate & output.** No file reads needed — all context is available from prior turns.

1. **Gate evaluation.** Run each finding through the four gates in `judging.md` (do not skip or reorder).

   **Single-pass protocol:** evaluate every relevant code path ONCE in fixed order (constructor → setters → swap functions → mint → burn → liquidate). One-line verdict per path: `BLOCKS`, `ALLOWS`, `IRRELEVANT`, or `UNCERTAIN`. Commit after all paths — do not re-examine. `UNCERTAIN` = `ALLOWS`.

2. **Lead promotion & rejection guardrails.**
   - Promote LEAD → FINDING (confidence 75) if: complete exploit chain traced in source, OR `[agents: 2+]` demoted (not rejected) the same issue.
   - `[agents: 2+]` does NOT override a concrete refutation — demote to LEAD if refutation is uncertain.
   - No deployer-intent reasoning — evaluate what the code _allows_, not how the deployer _might_ use it.

3. **Fix verification** (confidence ≥ 80 only): trace the attack with fix applied; verify no new DoS, reentrancy, or broken invariants (use `safeTransfer` not `require(token.transfer(...))`); list all locations if the pattern repeats. If no safe fix exists, omit it with a note.

4. **Format and print** per `report-formatting.md`. Exclude rejected items. If `--file-output`: also write to file. If `--log-output`: write `{log_dir}/final-report.md` and `{log_dir}/gate-results.md`, print `📂 Audit logs saved to {log_dir}`.

## Logging

When `--log-output` is set, write to `assets/audit-logs/{YYYYMMDD-HHMMSS}/`: `agent-{1-8}-output.md`, `dedup-decisions.md`, `chain-analysis.md`, `gate-results.md`, `final-report.md`.

## Banner

Before doing anything else, print this exactly:

```

██████╗  █████╗ ███████╗██╗  ██╗ ██████╗ ██╗   ██╗     ███████╗██╗  ██╗██╗██╗     ██╗     ███████╗
██╔══██╗██╔══██╗██╔════╝██║  ██║██╔═══██╗██║   ██║     ██╔════╝██║ ██╔╝██║██║     ██║     ██╔════╝
██████╔╝███████║███████╗███████║██║   ██║██║   ██║     ███████╗█████╔╝ ██║██║     ██║     ███████╗
██╔═══╝ ██╔══██║╚════██║██╔══██║██║   ██║╚██╗ ██╔╝     ╚════██║██╔═██╗ ██║██║     ██║     ╚════██║
██║     ██║  ██║███████║██║  ██║╚██████╔╝ ╚████╔╝      ███████║██║  ██╗██║███████╗███████╗███████║
╚═╝     ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝ ╚═════╝   ╚═══╝       ╚══════╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝╚══════╝

```
