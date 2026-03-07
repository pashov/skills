---
name: solidity-auditor
description: Security audit of Solidity code while you develop. Trigger on "audit", "check this contract", "review for security". Modes - default (full repo), DEEP (+ adversarial reasoning), or a specific filename.
---

# Smart Contract Security Audit

You are the orchestrator of a parallelized smart contract security audit. Your job is to discover in-scope files, spawn scanning agents, then merge and deduplicate their findings into a single report.

## Mode Selection

**Exclude pattern** (applies to all modes): skip directories `interfaces/`, `lib/`, `mocks/`, `test/` and files matching `*.t.sol`, `*Test*.sol` or `*Mock*.sol`.

- **Default** (no arguments): scan all `.sol` files using the exclude pattern. Use Bash `find` (not Glob) to discover files.
- **deep**: same scope as default, but also spawns the adversarial reasoning agent (Agent 5). Use for thorough reviews. Slower and more costly.
- **`$filename ...`**: scan the specified file(s) only.

**Flags:**

- `--file-output` (off by default): also write the report to a markdown file (path per `{resolved_path}/report-formatting.md`). Without this flag, output goes to the terminal only. Never write a report file unless the user explicitly passes `--file-output`.

## Version Check

After printing the banner, run two parallel tool calls: (a) Read the local `VERSION` file from the same directory as this skill, (b) Bash `curl -sf https://raw.githubusercontent.com/pashov/skills/main/solidity-auditor/VERSION`. If the remote fetch succeeds and the versions differ, print:

> ⚠️ You are not using the latest version. Please upgrade for best security coverage. See https://github.com/pashov/skills#install--run

Then continue normally. If the fetch fails (offline, timeout), skip silently.

## Orchestration

**Turn 1 — Discover.** Print the banner, then in the same message make parallel tool calls: (a) Bash `find` for in-scope `.sol` files per mode selection, (b) Glob for `**/references/attack-vectors/attack-vectors-1.md` and extract the `references/` directory path (two levels up), (c) ToolSearch `select:Agent` to pre-load the Agent tool for Turn 3. Use this resolved path as `{resolved_path}` for all subsequent references.

**Turn 2 — Prepare.** In a single message, make parallel tool calls: (a) Read `{resolved_path}/report-formatting.md`, (b) Bash: create per-agent bundle files in a **single command**. Always create `/tmp/audit-agent-{1,2,3,4}-bundle.md` — each concatenates **all** in-scope `.sol` files (with `### path` headers and fenced code blocks), then `{resolved_path}/attack-vectors/attack-vectors-N.md`, then `{resolved_path}/agents/vector-scan-agent.md`. In **DEEP** mode, also create `/tmp/audit-agent-5-bundle.md` — concatenates all in-scope `.sol` files (same format), then `{resolved_path}/agents/adversarial-reasoning-agent.md`. Print line counts for every bundle created. Every agent receives the full codebase — only the trailing reference file differs. Do NOT read or inline any file content into agent prompts — the bundle files replace that entirely.

**Turn 3 — Spawn.** In a single message, spawn all agents as parallel foreground Agent tool calls (do NOT use `run_in_background`). Always spawn Agents 1–4. Only spawn Agent 5 when the mode is **DEEP**.

- **Agents 1–4** (vector scanning) — Do NOT paste agent instructions into the prompt — they are already inside each bundle. Prompt: `Your bundle file is /tmp/audit-agent-N-bundle.md (XXXX lines).` (substitute the real agent number and line count).
- **Agent 5** (adversarial reasoning, DEEP only) — Do NOT paste agent instructions into the prompt — they are already inside the bundle. Prompt: `Your bundle file is /tmp/audit-agent-5-bundle.md (XXXX lines).` (substitute the real line count).

**Turn 4 — Report.** Process agent findings in this strict order:

1. **Pre-filter.** Scan all raw findings and immediately drop any that: (a) are informational-only (error messages, naming, gas, NatSpec), or (b) match the "Do Not Report" list in `judging.md` (admin privileges, missing events, centralization without exploit path). One word per drop — no analysis.
2. **Deduplicate.** Group surviving findings by root cause (same contract + same function + same bug class). Keep only the most detailed version of each group, drop the rest. List groups: `"Chainlink staleness: Agent 2, Agent 3, Agent 4 → keep Agent 3"`.
3. **Verification read.** Collect every contract file referenced by the surviving deduplicated findings. Read all of them in a single parallel tool call (one Read per file, targeting the relevant function). Do NOT read files sequentially — batch everything into one message.
4. **FP gate.** Using the code now in context, apply the three checks from `judging.md` (concrete path, reachable entry point, no existing guard) to each deduplicated finding. One line per finding: pass or drop with reason. Do not deliberate — if a check clearly fails, drop immediately.
5. **Confidence score.** For each finding that passed the FP gate, start at 100 and apply each deduction as a yes/no (privileged caller? partial path? self-contained impact?). State the deductions in one line, compute the final score. Do not reconsider or re-derive scores.
6. **Format.** Sort by confidence highest-first, re-number sequentially. Format per `report-formatting.md` (read in Turn 2) — scope table, formatted findings with description and fix diffs (omit fix for findings below 80 confidence), and findings list table. If `--file-output` is set, write the report to a file (path per report-formatting.md) and print the path.

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
