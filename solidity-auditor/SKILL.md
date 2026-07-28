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
## Orchestration

**Turn 1 — Discover.** Print the banner, then make these parallel tool calls in one message:

a. Bash `find` for in-scope `.sol` files per mode selection
b. Glob for `**/references/hacking-agents/shared-rules.md` — extract the `references/` directory (two levels up) as `{resolved_path}`, and its parent (the directory holding this `SKILL.md`) as `{skill_dir}`
c. ToolSearch `select:Agent,Workflow`
d. Read the local `VERSION` file from the same directory as this skill
e. Bash `curl -sf https://raw.githubusercontent.com/pashov/skills/main/solidity-auditor/VERSION`
f. Bash `mktemp -d ./.audit-XXXXXX` → store as `{bundle_dir}`

If the remote VERSION fetch succeeds and differs from local, print `⚠️ You are not using the latest version. Please upgrade for best security coverage. See https://github.com/pashov/skills`. If it fails, skip silently.

**Turn 1b — Model selection (Claude Code only).** This turn applies ONLY when both `AskUserQuestion` and the `Agent` tool (with a `model` parameter) are available in your runtime — i.e., Claude Code. On Codex, Gemini, Cursor's native agent, or any runtime without these, SKIP this turn entirely, leave `{agent_model}` unset, and proceed to Turn 2. Do NOT emit the question as prose. Do NOT substitute any other mechanism.

On Claude Code:

1. Read your system prompt to detect your own model **family** (Opus, Sonnet, or Haiku). Ignore the version digits — the Agent tool's `model` parameter takes the family name (`"opus"` / `"sonnet"` / `"haiku"`), and the runtime resolves to the latest version in that family.
2. Call `AskUserQuestion` with:
   - Question: `"Which Claude model should the 12 audit agents use?"`
   - Three single-select options. Mark the orchestrator's own family as `(Recommended)` and place it first.
   - On each option, set the `description` field to `latest`.
   - On each option, set the `preview` field verbatim (preserve all whitespace exactly — the box widths must stay equal across all three):

   Opus preview:

   ```
   ┌──────────────────────────────────────────────────────────┐
   │  opus  ·  highest reasoning  ·  most expensive           │
   └──────────────────────────────────────────────────────────┘
   ```

   Sonnet preview:

   ```
   ┌──────────────────────────────────────────────────────────┐
   │  sonnet  ·  balanced reasoning  ·  mid cost              │
   └──────────────────────────────────────────────────────────┘
   ```

   Haiku preview:

   ```
   ┌──────────────────────────────────────────────────────────┐
   │  haiku  ·  lowest reasoning  ·  cheapest                 │
   └──────────────────────────────────────────────────────────┘
   ```
3. Store the runner's choice as `{agent_model}`. If no answer, default to the orchestrator's own model.

**Turn 1c — Resolve `{orchestration}` (Claude Code only).** No user-facing output, no question. Decide how the 12 agents will be dispatched, based on what Turn 1's ToolSearch (step c) returned:

- `{orchestration} = "workflow"` **only if** the `Workflow` tool schema actually came back — a positive schema fetch, nothing weaker. This is the Claude Code path: one deterministic fan-out with a live progress tree instead of 12 loose background tasks. Never infer availability from the model you are running, from the presence of the `Agent` tool, or from the fact that this skill mentions workflows.
- Otherwise (Codex, Gemini, Cursor's native agent, Copilot, Windsurf, or any runtime without `Workflow`) → `{orchestration} = "agents"`. Never emulate, shim, or hand-roll a workflow where the tool does not exist.

`{orchestration}` selects between Turn 3a-W and Turn 3a-A. Nothing else in this skill changes — same 12 bundles, same 12 prompts, same Turn 4.

If the Turn 3a-W `Workflow` call fails for any reason (tool not found, invalid script, rejected), do not retry it — fall back to Turn 3a-A and continue. The workflow is a dispatch optimisation, never a hard dependency.

**Turn 2 — Prepare.** In one message, make parallel tool calls: (a) Read `{resolved_path}/report-formatting.md`, (b) Read `{resolved_path}/judging.md`.

Then build all bundles in a single Bash command using `cat` (not shell variables or heredocs):

1. `{bundle_dir}/source.md` — ALL in-scope `.sol` files, each with a `### path` header and fenced code block.
2. Agent bundles = `source.md` + agent-specific files:

| Bundle                | Appended files (relative to `{resolved_path}`)                                                                                                |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `agent-1-bundle.md`   | `source.md` + `senior-auditor-sop.md` + `hacking-agents/math-precision-agent.md` + `hacking-agents/shared-rules.md`                            |
| `agent-2-bundle.md`   | `source.md` + `senior-auditor-sop.md` + `hacking-agents/access-control-agent.md` + `hacking-agents/shared-rules.md`                            |
| `agent-3-bundle.md`   | `source.md` + `senior-auditor-sop.md` + `hacking-agents/economic-security-agent.md` + `hacking-agents/shared-rules.md`                         |
| `agent-4-bundle.md`   | `source.md` + `senior-auditor-sop.md` + `hacking-agents/execution-trace-agent.md` + `hacking-agents/shared-rules.md`                           |
| `agent-5-bundle.md`   | `source.md` + `senior-auditor-sop.md` + `hacking-agents/invariant-agent.md` + `hacking-agents/shared-rules.md`                                 |
| `agent-6-bundle.md`   | `source.md` + `senior-auditor-sop.md` + `hacking-agents/periphery-agent.md` + `hacking-agents/shared-rules.md`                                 |
| `agent-7-bundle.md`   | `source.md` + `senior-auditor-sop.md` + `hacking-agents/first-principles-agent.md` + `hacking-agents/shared-rules.md`                          |
| `agent-8-bundle.md`   | `source.md` + `senior-auditor-sop.md` + `hacking-agents/asymmetry-agent.md` + `hacking-agents/shared-rules.md`                                 |
| `agent-9-bundle.md`   | `source.md` + `senior-auditor-sop.md` + `hacking-agents/boundary-agent.md` + `hacking-agents/shared-rules.md`                                  |
| `agent-10-bundle.md`  | `source.md` + `senior-auditor-sop.md` + `hacking-agents/numerical-gap-agent.md` + `hacking-agents/shared-rules.md`                             |
| `agent-11-bundle.md`  | `source.md` + `senior-auditor-sop.md` + `hacking-agents/trust-gap-agent.md` + `hacking-agents/shared-rules.md`                                 |
| `agent-12-bundle.md`  | `source.md` + `senior-auditor-sop.md` + `hacking-agents/flow-gap-agent.md` + `hacking-agents/shared-rules.md`                                  |

Each bundle = source.md + SOP + specialty + shared-rules. Agents read the bundle; no Read/Grep needed for the initial scan. Targeted Read/Grep allowed for cross-file investigation.

Print line counts for every bundle and `source.md`. Do NOT inline source code into the Agent call prompt itself.

**Turn 3a — Dispatch all 12 agents.** Exactly one of the two paths below runs, selected by `{orchestration}` from Turn 1c. Both dispatch the same 12 prompts against the same 12 bundles and produce the same raw material for Turn 4 — only the transport differs.

Agents 1–9 use the **single-specialty prompt** (Turn 3a-i). Agents 10–12 use the **gap-hunter prompt** (Turn 3a-ii).

**Turn 3a-W — Workflow path (`{orchestration} = "workflow"`).** Issue ONE `Workflow` call. This skill instructing you to call `Workflow` is the required opt-in — do not ask the user to confirm multi-agent orchestration, and do not fall back to Turn 3a-A because the tool "wasn't requested".

Pass `scriptPath` (see below) and `args` as a JSON object — an actual object, never a JSON-encoded string — with:

- `bundleDir` — `{bundle_dir}` from Turn 1
- `agentModel` — `{agent_model}` from Turn 1b, or `null` if Turn 1b was skipped
- `bundles` — 12 entries `{n, specialty, lines}`, where `specialty` is the agent's specialty file basename without extension (`math-precision`, `access-control`, `economic-security`, `execution-trace`, `invariant`, `periphery`, `first-principles`, `asymmetry`, `boundary`, `numerical-gap`, `trust-gap`, `flow-gap` for agents 1–12 in order) and `lines` is that bundle's real line count from Turn 2
- `singleSpecialtyPrompt` — the Turn 3a-i template, with `{BUNDLE_PATH}` and `{LINES}` left as literal placeholders
- `gapHunterPrompt` — the Turn 3a-ii template, same placeholders left literal

The script ships with this skill at `{skill_dir}/workflows/audit-12.js` — pass it to `Workflow` as `scriptPath`. Do NOT paste it inline as `script`; the file on disk is the single source of truth.

Notes on this script, all load-bearing. Each one exists because a real run failed without it:

- **`schema` is what makes this deterministic.** It forces each agent through a StructuredOutput tool and returns a *validated object*, so Turn 4 reads `findings[]` / `leads[]` fields directly. Never regex free text for `FINDING |` lines: an agent whose final message is truncated silently loses findings, and the loss is invisible because the surviving text still parses. A real run lost 2 FINDINGs exactly this way — the agent's return value began mid-sentence at 4,714 chars while its transcript held 12,319. A schema removes the whole failure class.
- **The `markers` field is required, not decoration.** `shared-rules.md` says the orchestrator greps agent output for `[Feynman:]` / `[Socratic:]` / `[Inversion:]` markers and verifies their counts. A schema replaces the free-text stream those markers lived in, so the counts must be carried explicitly or the protocol check silently becomes unenforceable.
- **The `typeof args === 'string'` guard is REQUIRED, not padding.** The workflows docs state `args` arrives as structured data, but a real run received it JSON-encoded. Destructuring a string does not throw — every field silently becomes `undefined` and the run dies on `bundles.map` with `undefined is not an object` before a single agent spawns. Keep the guard on every script in this skill.
- **Every agent resolves to an `{ok}` record, never a bare `null`.** `parallel` converts a thrown thunk to `null`, and `{...null}` spreads to `{}` — which would look like a successful agent that found nothing. The two-layer normalisation (`.then` for a null return, `settled` for a thrown thunk) makes a dead agent structurally distinguishable from a clean one.
- `coverage.failed` is returned so Turn 4 can name missing agents instead of silently reporting reduced coverage as a clean result.
- `parallel` is a barrier on purpose. Dedup in Turn 4 needs all 12 outputs at once, so there is nothing to pipeline.
- `agentModel` is applied per `agent()` call via `opts.model`, so Turn 1b's selection reaches every one of the 12. When it is `null` the key is omitted entirely and each agent inherits the session model — same rule as Turn 3a-A.
- Placeholder substitution uses `split`/`join`, not `String.replace`, so `$&`-style sequences inside a bundle path can't corrupt the prompt.

**Prompt suffix (workflow path only).** Append this to both templates before passing them in, so agents know where the markers go:

```
Return your result through the StructuredOutput tool matching the provided
schema. Put the literal [Feynman:] / [Socratic:] / [Inversion:] working text
in markers.transcript, and their counts in markers.feynman / .socratic /
.inversion. Every field required by shared-rules.md maps to a schema field —
findings[] for FINDINGs, leads[] for LEADs. Do not omit group_key.
```

If a schema-validated agent exhausts its retries the runtime reports `error_max_structured_output_retries`; that agent lands in `coverage.failed` and must be named in Turn 4, not treated as finding-free.

**Turn 3a-A — Agent path (`{orchestration} = "agents"`).** In one message, spawn all 12 agents as **parallel BACKGROUND Agent calls** (`run_in_background=true`). If Turn 1b set `{agent_model}`, pass `model={agent_model}` on every Agent call. If `{agent_model}` is unset (Turn 1b skipped — Codex, Gemini, others), omit the `model` parameter entirely — do NOT substitute any default. The orchestrator will receive a notification when each agent completes — do NOT poll or sleep. Single phase, no later spawns.

**Turn 3a-i — Single-specialty prompt template (agents 1–9, substitute real values):**

On the Agent path, substitute the real bundle path and line count directly. On the Workflow path, leave `{BUNDLE_PATH}` and `{LINES}` as literal placeholders — the script fills them in.

```
You are an attacker. Your specialty, mindset, source, and output rules
are in your bundle. Read it fully before producing findings.

Read first:
- {BUNDLE_PATH} ({LINES} lines) — source + SOP + specialty + shared rules.

The bundle contains all in-scope source. Do NOT re-read in-scope files
for the initial scan. Use Read/Grep only for cross-file searches or
out-of-scope context (interfaces/, lib/, mocks/, test/).

What a finding looks like:
- file, function
- root cause — the one-sentence code-level defect
- minimal fix — the smallest change that eliminates the defect
- proof — concrete numbers, a trace, or quoted code

Without concrete proof, it's a LEAD, not a finding. Leads are honest
about what you couldn't verify — they're not failures, they're
calibration. Emit them.

Don't skim. Don't trust your first read. Trust your discomfort.

Output format: see shared-rules.md inside your bundle.
```

**Turn 3a-ii — Gap-hunter prompt template (agents 10–12, substitute real values):**

Same placeholder rule as Turn 3a-i.

```
You are an attacker. Your gap-hunter specialty, mindset, source, and
output rules are in your bundle. Read it fully before producing findings.

Read first:
- {BUNDLE_PATH} ({LINES} lines) — source + SOP + gap-hunter specialty + shared rules.

The bundle contains all in-scope source. Do NOT re-read in-scope files
for the initial scan. Use Read/Grep only for cross-file searches or
out-of-scope context (interfaces/, lib/, mocks/, test/).

What a finding looks like:
- file, function
- seam — which two or three lenses combine
- root cause — the one-sentence code-level defect that lives at the seam
- minimal fix — the smallest change that eliminates the defect
- proof — concrete numbers, a trace, or quoted code showing the seam

Without concrete proof of the seam, it's a LEAD, not a finding.
Leads are honest about what you couldn't verify — they're not failures,
they're calibration. Emit them.

Don't skim. Don't trust your first read. Trust your discomfort.

Output format: see shared-rules.md inside your bundle (gap-hunter-specific
output fields are in your specialty file).
```

**Turn 3b — Wait for the 12 agents to complete.** Do NOT proceed to dedup until every agent has finished — let them run to natural completion. Do NOT poll or sleep; act only on completion notifications.

- `{orchestration} = "workflow"`: wait for the single workflow task notification. Its return value is a JSON object `{coverage, markers, findings[], leads[]}` — already validated against the schema, one flat array of findings and one of leads, each item tagged with the `agent` and `specialty` that produced it. Feed those arrays straight into Turn 4; do NOT re-parse text. Check `coverage.failed` first: any agent listed there contributed nothing and must be named in the Turn 4 completeness line. The task notification truncates long values for display — that truncation is cosmetic, the workflow's actual return value is intact, and the full per-agent record is in `journal.jsonl` in the transcript directory if you need it.
- `{orchestration} = "agents"`: wait until every one of the 12 spawned agents has notified completion.

**Turn 4 — Deduplicate, validate & output.** Single-pass: deduplicate all agent results, gate-evaluate, and produce the final report in one turn. Do NOT print an intermediate dedup list — go straight to the report.

1. **Dedup.** Collect every FINDING and LEAD from the 12 agents. On the Turn 3a-W path they arrive as the workflow's `findings[]` and `leads[]` arrays — structured, pre-tagged with `agent`/`specialty`, no parsing required. On the Turn 3a-A path, parse them out of the 12 agent notifications. If any agent produced no output at all (crashed, was skipped, or exhausted its structured-output retries), name it in the completeness line at the end of this step; a missing agent is reduced coverage, not a clean result. Group by `group_key` (Contract | function | bug-class). Exact-match first; merge synonymous bug_class within same (Contract, function). Keep best per group, number sequentially, annotate `[agents: N]`.

   **MANDATORY — Wide-description (group_key).** Merged group with distinct mechanisms (different `fix:`, code-level cause, or attack path) MUST list every mechanism. No dropping. Same function can have multiple coexisting bugs at the same group_key — all MUST appear.

   **MANDATORY — Function-level second pass (after group_key dedup).** Run at (Contract, function), ignoring bug_class. Agents often label coexisting bugs with different bug_class tags but reference multiple mechanisms in the body. For every (Contract, function) with multiple final findings: scan body (description, path, proof, fix) of every constituent for distinct mechanisms across bug_class boundaries. Every mechanism in any constituent body MUST appear in ≥1 final finding.

   **MANDATORY — Function isolation (HARD).** NEVER merge across different `function:` fields. Dedup only within (Contract, function). Different function = different bug. Second pass above stays WITHIN (Contract, function), never across.

   **MANDATORY — Fix preservation (HARD GATE).** Before writing merged `fix:` on a multi-finding (Contract, function):
   1. Collect every raw `fix:` from agents flagging the tuple.
   2. Group by ADD-lines (`+` lines, or equivalent require/assignment).
   3. Distinct if ADD-lines differ in: called function/expression (e.g., `require(msg.value == amount)` vs `require(zrc20 != _ETH_ADDRESS_)`), check direction (validate/restrict/ban), or checked parameter.
   4. ≥2 distinct → present as Option A, B, … — one block per distinct fix, verbatim from agent text (no paraphrase).
   5. Label intuitively: validate / restrict / allow-and-handle / ban-path.

   **Output format when 2+ distinct fixes exist:**

   ```
   **Fix (Option A — <label>)**:

   ```diff
   <verbatim diff from raw agent N1's fix>
   ```

   **Fix (Option B — <label>)**:

   ```diff
   <verbatim diff from raw agent N2's fix>
   ```
   ```

   **Inline check before printing**: count distinct fixes from raw for this (Contract, function). ≥2 distinct but merged shows 1 → violation, add alternatives.

   **MANDATORY — Completeness (HARD GATE).** Before print: list every unique (Contract, function, bug-class) in any raw FINDING/LEAD across the 12 agents. Every unique (Contract, function) MUST have ≥1 item in final. Zero = silent drop, fix it. Multiple bug-class within same (Contract, function) MAY collapse to one item (wide-description), but the (Contract, function) MUST survive. Print inline before report: `Completeness: N unique (Contract, function) in raw, N covered in final.`

   Composite chains: if A's output feeds B's precondition AND combined impact > either alone, add `Chain: [A] + [B]` at conf = min(A, B). Most audits: 0–2.

2. **Gate.** Run each deduped finding through the four gates in `judging.md` (no skip, no reorder, no revisit after verdict).

   **Single-pass:** every relevant code path ONCE in fixed order (constructor → setters → swap → mint → burn → liquidate). One-line verdict: `BLOCKS` / `ALLOWS` / `IRRELEVANT` / `UNCERTAIN`. `UNCERTAIN = ALLOWS`. Commit, no re-examination.

3. **Lead promotion / rejection.**
   - LEAD → FINDING (conf 75) if: full exploit chain in source, OR `[agents: 2+]` demoted (not rejected) same issue.
   - `[agents: 2+]` does NOT override a code path that interrupts attack before harm — demote to LEAD if execution uncertain.
   - No deployer-intent reasoning — what code allows, not how deployer might use it.

4. **Format/print** per `report-formatting.md`. Exclude rejected. If `--file-output`: also write to file. Do NOT re-read source to "verify the most critical claim" — agents did that, dedup filtered. Re-verification costs ~5min, rarely changes verdicts. Skip.

5. **Auto-clean.** After print (and `--file-output` write): `rm -rf {bundle_dir}`. Bundle dir = transient build state, not an artifact. Don't skip. For debugging: copy bundle elsewhere before re-running.


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
