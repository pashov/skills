---
name: solidity-auditor
description: Security audit of Solidity code while you develop. Trigger on "audit", "check this contract", "review for security". Modes - default (full repo), deep (+ adversarial reasoning), or specific filename(s).
---

# Smart Contract Security Audit

You orchestrate a parallelized smart contract security audit. Discover in-scope files, run scanning agents, then merge and deduplicate findings into one report.

## Runtime Compatibility

Use whichever shell, file-read, and sub-agent tools are available in your runtime. Prefer parallel execution when available. If a capability is unavailable, run an equivalent sequential fallback without changing audit logic.

## Mode Selection

**Exclude pattern** (applies to all modes): skip directories `interfaces/`, `lib/`, `mocks/`, `test/` and files matching `*.t.sol`, `*Test*.sol` or `*Mock*.sol`.

- **Default** (no arguments): scan all `.sol` files using the exclude pattern. Use shell `find` (not glob expansion) to discover files.
- **deep**: same scope as default, but also spawns the adversarial reasoning agent (Agent 5). Use for thorough reviews. Slower and more costly.
- **`$filename ...`**: scan the specified file(s) only.

**Flags:**

- `--file-output` (off by default): also write the report to a markdown file (path per `{resolved_path}/report-formatting.md`). Without this flag, output goes to the terminal only. Never write a report file unless the user explicitly passes `--file-output`.

## Skill Path Resolution

Before version check, resolve `skill_root` by taking the first existing path:

1. `./.agents/skills/solidity-auditor`
2. `$HOME/.agents/skills/solidity-auditor`
3. `./solidity-auditor`
4. `$HOME/.claude/commands/solidity-auditor`

Set `{resolved_path}` to `${skill_root}/references`.

If none exists, stop and ask the user to install the skill using the repo README install commands.

## Version Check

After printing the banner, run local+remote checks in parallel when possible:

1. Read local `${skill_root}/VERSION`
2. Fetch remote `https://raw.githubusercontent.com/pashov/skills/main/solidity-auditor/VERSION`

If remote succeeds and versions differ, print:

> ⚠️ You are not using the latest version. Please upgrade for best security coverage. See https://github.com/pashov/skills#install--run

Then continue normally. If remote fetch fails (offline, timeout), skip silently.

## Orchestration

**Turn 1 — Discover.** Print the banner, parse mode/flags/filenames, and resolve in-scope Solidity files.

- For default/deep, discover files from current working directory using shell `find` with the exclude pattern.
- For filename mode, use only user-provided file paths.
- Normalize to unique existing `.sol` files.
- If no in-scope files remain, stop and report that nothing matched scope.

**Turn 2 — Prepare.**

- Read `{resolved_path}/agents/vector-scan-agent.md`.
- Read `{resolved_path}/report-formatting.md`.
- In one shell command, build four bundle files: `/tmp/audit-agent-1-bundle.md` ... `/tmp/audit-agent-4-bundle.md`.
- Each bundle must concatenate, in order:
  1. all in-scope `.sol` files with `### path` headers and fenced code blocks,
  2. `{resolved_path}/judging.md`,
  3. `{resolved_path}/report-formatting.md`,
  4. `{resolved_path}/attack-vectors/attack-vectors-N.md` (N = 1..4).
- Print each bundle line count.
- Do not inline source code directly into agent prompts; bundle files are the sole code input for Agents 1–4.

**Turn 3 — Spawn.**

- Spawn Agents 1–4 in parallel foreground calls (no background jobs).
- Each agent prompt must include the full text of `vector-scan-agent.md`, plus: `Your bundle file is /tmp/audit-agent-N-bundle.md (XXXX lines).`
- Do not hard-pin runtime-specific model names; use default model selection for the current runtime.
- Spawn Agent 5 only in **deep** mode:
  - Provide in-scope `.sol` file paths and `{resolved_path}`.
  - Instruct it to read `{resolved_path}/agents/adversarial-reasoning-agent.md` for full instructions.

If sub-agent spawning is unavailable, run equivalent passes sequentially yourself using the same inputs and output contract.

**Turn 4 — Report.**

- Merge all agent results.
- Deduplicate by root cause (keep higher-confidence version).
- Sort by confidence descending.
- Re-number sequentially.
- Insert the **Below Confidence Threshold** separator row.
- Print findings directly without re-drafting them.
- Use `report-formatting.md` for full output structure and scope table.
- If `--file-output` is set, write the report to file path per `report-formatting.md` and print the path.

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
