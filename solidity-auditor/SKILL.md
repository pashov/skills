---
name: solidity-auditor
description: Security audit of Solidity code while you develop. Trigger on "audit", "check this contract", "review for security". Modes - default (full repo) or a specific filename.
---

# Smart Contract Security Audit

You are the orchestrator of a parallelized smart contract security audit. Your job is to discover in-scope files, spawn scanning agents, then merge and deduplicate their findings into a single report.

## Mode Selection

**Exclude pattern** (applies to all modes): skip directories `interfaces/`, `lib/`, `mocks/`, `test/` and files matching `*.t.sol`, `*Test*.sol` or `*Mock*.sol`.

- **Default** (no arguments): scan all `.sol` files using the exclude pattern. Use Bash `find` (not Glob) to discover files.
- **`$filename ...`**: scan the specified file(s) only.

**Flags:**

- `--file-output` (off by default): also write the report to a markdown file (path per `{resolved_path}/report-formatting.md`). Without this flag, output goes to the terminal only. Never write a report file unless the user explicitly passes `--file-output`.

## Version Check

After printing the banner, run two parallel tool calls: (a) Read the local `VERSION` file from the same directory as this skill, (b) Bash `curl -sf https://raw.githubusercontent.com/pashov/skills/main/solidity-auditor/VERSION`. If the remote fetch succeeds and the versions differ, print:

> ⚠️ You are not using the latest version. Please upgrade for best security coverage. See https://github.com/pashov/skills#install--run

Then continue normally. If the fetch fails (offline, timeout), skip silently.

## Orchestration

**Turn 1 — Discover.** Print the banner, then in the same message make parallel tool calls: (a) Bash `find` for in-scope `.sol` files per mode selection, (b) Glob for `**/references/attack-vectors/attack-vectors-1.md` and extract the `references/` directory path (two levels up), (c) ToolSearch `select:Agent` to pre-load the Agent tool for Turn 3. Use this resolved path as `{resolved_path}` for all subsequent references.

**Turn 2 — Prepare.** In a single message, make parallel tool calls: (a) Read `{resolved_path}/report-formatting.md`, (b) Bash: create per-agent bundle files in a **single command**. Always create `/tmp/audit-agent-{1,2,3,4}-bundle.md` — each concatenates **all** in-scope `.sol` files (with `### path` headers and fenced code blocks), then `{resolved_path}/attack-vectors/attack-vectors-N.md`, then `{resolved_path}/hacking-agents/vector-scan-agent.md`. Also create `/tmp/audit-agent-5-bundle.md` — concatenates all in-scope `.sol` files (same format), then `{resolved_path}/hacking-agents/adversarial-reasoning-agent.md`. Also create `/tmp/audit-fp-gate-bundle.md` — concatenates all in-scope `.sol` files (same format), then `{resolved_path}/judging.md`, then `{resolved_path}/report-formatting.md`, then `{resolved_path}/operations-agents/fp-gate-agent.md`. Print line counts for every bundle created. Every agent receives the full codebase — only the trailing reference file differs. Do NOT read or inline any file content into agent prompts — the bundle files replace that entirely.

**Turn 3 — Spawn.** In a single message, spawn all 5 agents as parallel foreground Agent tool calls (do NOT use `run_in_background`).

- **Agents 1–4** (vector scanning) — Do NOT paste agent instructions into the prompt — they are already inside each bundle. Prompt: `Your bundle file is /tmp/audit-agent-N-bundle.md (XXXX lines).` (substitute the real agent number and line count).
- **Agent 5** (adversarial reasoning) — Do NOT paste agent instructions into the prompt — they are already inside the bundle. Prompt: `Your bundle file is /tmp/audit-agent-5-bundle.md (XXXX lines).` (substitute the real line count).

**Turn 4 — Report.** Process agent findings in this strict order:

1. **Pre-filter.** Scan all raw findings and immediately drop any that are informational-only (error messages, naming, gas, NatSpec, admin-only parameter setting, missing events, centralization without concrete exploit path). One word per drop — no analysis.
2. **Deduplicate.** Group surviving findings by root cause (same contract + same function + same bug class). Keep only the most detailed version of each group, drop the rest. List groups: `"Chainlink staleness: Agent 2, Agent 3, Agent 4 → keep Agent 3"`.
3. **Validate.** Spawn a single foreground Agent. Do NOT paste agent instructions into the prompt — they are already inside the bundle. Paste all deduplicated findings and leads verbatim into the prompt, then add: `Validation bundle: /tmp/audit-fp-gate-bundle.md (XXXX lines). Files reviewed: <file list>.` Substitute the real line count and file list.
4. **Output.** Print the validation agent's formatted report verbatim. If `--file-output` is set, also write it to a file (path per report-formatting.md) and print the path.

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
