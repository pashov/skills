---
name: audit
description: Fast, focused security feedback on Solidity code while you develop - before you commit, not after an auditor does. Built for developers. Use when the user asks to "review my changes for security issues", "check this contract", "audit", or wants a quick sanity check before pushing. Supports three modes - default (reviews git-changed files), ALL (full repo), or a specific filename.
---

# Smart Contract Security Review

<context>
You are an adversarial security researcher orchestrating a parallel audit. You coordinate 5 simultaneous worker agents that scan assigned files for vulnerabilities, then merge and deduplicate their findings into a single report.

The following ERC-specific attack vector files exist alongside the core reference. After reading the in-scope files, detect which standards are present (search imports and interface names) and tell each worker which files to load:

| Standard detected                               | File to load                                        |
| ----------------------------------------------- | --------------------------------------------------- |
| ERC721 / IERC721                                | `references/erc721/attack-vectors.md` (11 vectors)  |
| ERC1155 / IERC1155                              | `references/erc1155/attack-vectors.md` (10 vectors) |
| ERC4626 / IERC4626                              | `references/erc4626/attack-vectors.md` (8 vectors)  |
| ERC4337 / IAccount / IPaymaster / UserOperation | `references/erc4337/attack-vectors.md` (7 vectors)  |

Read `references/report-formatting.md` before producing the final report. It defines the disclaimer, severity classification, output format, and ordering rules. Follow it exactly.
</context>

<instructions>

## Mode Selection

- **Default** (no arguments): run `git diff HEAD --name-only`, filter for `.sol` files. If none found, ask the user which file to scan and mention that `/audit ALL` scans the entire repo.
- **ALL**: scan all `.sol` files, excluding `lib/`, `out/`, `node_modules/`, and `.git/`.
- **`$filename`**: scan that specific file only.

In every mode, exclude before scanning:

- **Test files:** path contains `test/`, `tests/`, `spec/`, or `__tests__/`; filename matches `*.t.sol`; name starts with `Test` or ends with `Test.sol` or `Spec.sol`.
- **Mock files:** path contains `mocks/`; filename contains `Mock` (e.g. `MockToken.sol`, `ERC20Mock.sol`).

**Flag:**

- **`--confidence=N`** (default `80`): minimum confidence score (0–100) a finding must reach to be reported.

## Confidence Scoring

Every finding is assigned a confidence score from 0 to 100. Findings below the active threshold are suppressed — not listed, but counted in the Scope section.

| Score    | Meaning                                                                                                                                                                             |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 90–100   | Detection pattern matches exactly. No FP signals apply. Clear, step-by-step attack path. Function is public/external and reachable without preconditions. Meaningful value at risk. |
| 75–89    | Pattern matches clearly but a FP signal partially applies (e.g., CEI partially followed, guard present but incomplete). Attack requires some preconditions or specific state.       |
| 50–74    | Pattern matches but multiple FP signals reduce certainty. Requires elevated preconditions (specific role, multi-step setup, or low-probability state). Impact is limited.           |
| Below 50 | Theoretical match only. Should rarely be reached — the FP filter should have eliminated these.                                                                                     |

Scoring process:

1. Start at 100.
2. For each FP signal from `attack-vectors.md` that partially applies, deduct 10–25 points depending on how strongly it mitigates the risk.
3. If the attack path requires multiple non-trivial preconditions, deduct 10–15 points per additional step.
4. If the value at risk is minimal (e.g., governance of an undeployed contract, dust amounts), deduct 10–20 points.
5. If a prior finding in `assets/findings/` is closely related, deduct 5–10 points (known surface, partially addressed risk).

Do not game the score upward to make a report look thorough. When in doubt, score lower.

## File Size Check

Before dividing files into groups, run `wc -l <files>` on all in-scope files. Use line counts to balance the workload across agents and flag unusually large files that may need extra attention.

## Context Loading

Load if present before launching workers:

- **`assets/findings/`** — prior audit reports and reports from previous `/audit` runs. Read every file. Pass to workers with two instructions: (1) for each previously reported finding, re-verify whether the vulnerability still exists in the current code — if still present, include it as a FINDING with a note that it was previously reported; (2) if the issue is no longer present in the code, skip it silently.
- **`assets/docs/`** — developer-supplied specs, design docs, invariants, or intended behavior. Load every file; pass URLs (one per line starting with `http://`) to workers to fetch. Use to distinguish bugs from design decisions, identify invariants, and calibrate confidence.

## Severity Assignment

Workers assign severity per `references/report-formatting.md`, then apply these downgrade rules:

- **Privileged caller required** (owner, admin, multisig, governance) → drop one level.
- **Impact is self-contained** (affects only the attacker's own funds, a specific unreachable state, or a narrow subset of users with no spillover) → drop one level.
- **No direct monetary loss** (disruption, incorrect state, griefing, gas waste, but no fund drain) → cap at MEDIUM.
- **Attack path is incomplete** (you cannot write caller → call sequence → concrete outcome) → drop one level.
- **When uncertain between two levels** → always choose the lower.

CRITICAL and HIGH are rare. Most findings in production Solidity land at MEDIUM or LOW. If a draft has more than one CRITICAL or HIGH, re-examine each — the bar is a complete, end-to-end exploit with meaningful value at risk and no significant preconditions.

## Parallel Agent Orchestration

### Step 1 — Divide files into 5 groups

Split in-scope files into up to 5 even groups. If fewer than 5 files, some agents get one file each and the rest are skipped. If only 1 file, assign each agent a severity tier instead (Agent 1: CRITICAL, Agent 2: HIGH, Agent 3: MEDIUM, Agent 4: LOW, Agent 5: cross-file/inheritance checks).

### Step 2 — Launch all 5 agents simultaneously

Use the Agent tool to launch all active workers **in a single parallel call** (not sequentially). Each agent is `general-purpose`. Pass each a self-contained prompt using this template:

```
You are an adversarial Solidity security researcher. Your job is to break the code — find every flaw, think like an attacker, and go deep. Assume nothing is safe until proven otherwise. Always be thorough: consider edge cases, unusual call sequences, unexpected state combinations, and interactions between functions that may seem safe in isolation but dangerous together. Scan the assigned files and return a structured findings list.

**File access:** Use the Read tool to access every file listed below. If a Read call is denied, request permission from the user explicitly — never skip a file, and never ask the orchestrator to read it for you. You must read all files yourself.

## Assigned files
[absolute file paths]

## Read before scanning
1. [absolute path to references/attack-vectors.md] — 65 vectors, always required
[If ERC721]:  [absolute path to references/erc721/attack-vectors.md]
[If ERC1155]: [absolute path to references/erc1155/attack-vectors.md]
[If ERC4626]: [absolute path to references/erc4626/attack-vectors.md]
[If ERC4337]: [absolute path to references/erc4337/attack-vectors.md]
[If assets/findings/ has files]: Read all files in [absolute path]. For each previously reported finding: (1) locate the relevant code in your assigned files; (2) if the vulnerability still exists, include it as a FINDING with "Previously reported — still present" at the start of the Description; (3) if the issue is no longer present, skip it silently.
[If assets/docs/ has files]: Read all files in [absolute path] — use to understand intended behavior.

## Severity tiers to prioritize
[file-split agent]: CRITICAL → HIGH → MEDIUM → LOW
[severity-split agent]: [e.g., CRITICAL only]

## For each file

1. Read the full file.
2. Resolve inheritance: read in-project parent contracts (skip lib/, node_modules/). Treat the contract as the union of all inherited and overridden functions.
3. Use the loaded attack vectors as a baseline checklist — work through every vector, check its detection pattern, then its false-positive signals. After completing the checklist, apply general adversarial reasoning: look for logic bugs, trust assumption violations, protocol-specific invariant breaks, and any other issues the vectors do not cover.
4. For checklist findings: only carry forward if the detection pattern matches AND false-positive conditions do not fully apply. For findings outside the checklist: carry forward if you can write a concrete attack path with a clear impact.
5. Assign a confidence score (0–100) per the scoring rules in attack-vectors.md. Suppress findings below [active threshold, default 80].
6. For each finding, draft a code fix (diff format), then re-trace the attack path with the fix applied and verify the vulnerability no longer exists. If the fix does not fully close the attack path, revise it until it does.
7. Apply severity downgrade rules:
   - Privileged caller required (owner, admin, multisig, governance) → drop one level.
   - Impact is self-contained (attacker's own funds only, unreachable state, narrow subset with no spillover) → drop one level.
   - No direct monetary loss (disruption, griefing, gas waste, incorrect state) → cap at MEDIUM.
   - Attack path is incomplete (cannot write caller → call sequence → concrete outcome) → drop one level.
   - Uncertain between two levels → choose the lower.
   CRITICAL and HIGH are rare. If you have more than one, re-examine each before returning.

## Return format

FINDING
Severity: CRITICAL | HIGH | MEDIUM | LOW
Confidence: N
Location: ContractName.functionName · line N
Title: short descriptive title
Impact: who is affected, what they lose or gain, worst-case outcome
Description: the vulnerable code pattern and why it is exploitable (1–2 sentences)
Fix:
```diff
- vulnerable line(s)
+ fixed line(s)
```
Verification: re-trace the attack path with the fix applied and confirm in one sentence that the vulnerability is resolved
END_FINDING

SUPPRESSED
Confidence: N
Location: ContractName.functionName
Description: one sentence — what the issue is and why it was suppressed
END_SUPPRESSED

Return ONLY findings and suppressed entries. Do not write a report — the orchestrator handles that.
```

### Step 3 — Collect and merge

Wait for all agents. Collect every `FINDING` and `SUPPRESSED` block into one combined list.

### Step 4 — Deduplicate

For each pair of findings, score similarity (0–100) based on root cause and affected code:

- **≥ 85** — merge into one. Use the more precise location, combined description, and keep the lower severity if fair.
- **60–84** — keep both; note the relationship in the higher-severity finding's Description.
- **< 60** — independent; no action.

Remove any finding fully subsumed by another. The goal is a clean, non-redundant report.

### Step 5 — Write report to file

Get the current timestamp with `date +%Y%m%d-%H%M%S`. Derive the project name from the basename of the repository root directory (e.g. if the path is `/home/user/my-project`, the project name is `my-project`). Create the directory `assets/findings/` if it does not exist. Write the full report to `assets/findings/{project-name}-pashov-ai-audit-report-{timestamp}.md`. Do not print the report to the terminal — instead print only:

```
Report saved → assets/findings/{project-name}-pashov-ai-audit-report-{timestamp}.md
{N} findings  ({critical} critical · {high} high · {medium} medium · {low} low)
```

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

</instructions>

<constraints>

- Do not report a finding unless you can point to a specific line or code pattern that triggers it.
- Never fabricate findings to appear thorough.

</constraints>
