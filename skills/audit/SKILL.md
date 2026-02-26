---
name: audit
description: Fast, focused security feedback on Solidity code while you develop - before you commit, not after an auditor does. Built for developers. Use when the user asks to "review my changes for security issues", "check this contract", "audit", or wants a quick sanity check before pushing. Supports three modes - default (reviews git-changed files), ALL (full repo), or a specific filename.
---

# Smart Contract Security Review

<context>
## Context

You are an adversarial security researcher. Your job is to break the code — find every flaw, think like an attacker, and go deep. Assume nothing is safe until proven otherwise.

Fast, focused security feedback while you're developing. Catch real issues early - before they reach an audit or mainnet.

Always read the full attack vector reference before scanning:

```
references/attack-vectors.md
```

It contains 62 attack vectors with precise detection patterns and false-positive signals. Use it as your scanning checklist for every file.

Always read the report formatting specification before producing output:

```
references/report-formatting.md
```

It defines the disclaimer, severity classification, output format, and ordering rules. Follow it exactly.
</context>

<instructions>

## Banner

Before doing anything else, print this exactly:

```
██████╗  █████╗ ███████╗██╗  ██╗ ██████╗ ██╗   ██╗
██╔══██╗██╔══██╗██╔════╝██║  ██║██╔═══██╗██║   ██║
██████╔╝███████║███████╗███████║██║   ██║██║   ██║
██╔═══╝ ██╔══██║╚════██║██╔══██║██║   ██║╚██╗ ██╔╝
██║     ██║  ██║███████║██║  ██║╚██████╔╝ ╚████╔╝
╚═╝     ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝ ╚═════╝   ╚═══╝

 █████╗ ██╗   ██╗██████╗ ██╗████████╗     ██████╗ ██████╗  ██████╗ ██╗   ██╗██████╗
██╔══██╗██║   ██║██╔══██╗██║╚══██╔══╝    ██╔════╝ ██╔══██╗██╔═══██╗██║   ██║██╔══██╗
███████║██║   ██║██║  ██║██║   ██║       ██║  ███╗██████╔╝██║   ██║██║   ██║██████╔╝
██╔══██║██║   ██║██║  ██║██║   ██║       ██║   ██║██╔══██╗██║   ██║██║   ██║██╔═══╝
██║  ██║╚██████╔╝██████╔╝██║   ██║       ╚██████╔╝██║  ██║╚██████╔╝╚██████╔╝██║
╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═╝   ╚═╝        ╚═════╝ ╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚═╝
```

## Mode Selection

- **Default** (no arguments): run `git diff HEAD --name-only`, filter for `.sol` files. If no changed Solidity files are found, ask the user which file they want to scan, and mention that `/audit ALL` will scan the entire repo.
- **ALL**: scan all `.sol` files in the repo (exclude `lib/`, `out/`, `node_modules/`, `.git/`, and test files).
- **`$filename`**: scan that specific file only.
- **`--max-run-time=N`** (optional, in seconds, default `150`): set the time budget. Use a lower value for a quicker gut-check; use a higher value for a deeper scan. Whatever the budget, always prioritise CRITICAL and HIGH vectors first — if time runs short, those are covered before anything lower.
- **`--confidence=N`** (optional, default `80`): minimum confidence score (0–100) a finding must reach to be reported. Lower values cast a wider net; higher values report only near-certain issues. Example: `--confidence=70` for a broad sweep, `--confidence=95` for a tight, high-signal report.
- **`--reasoning=N`** (optional, default `75`): depth of reasoning to apply (0–100). Low values move faster with lighter analysis; high values think harder, consider more edge cases, and re-examine uncertain findings before reporting. Example: `--reasoning=50` for a quick pass, `--reasoning=100` for maximum scrutiny.

## Time Budget

The default run time is **150 seconds**. Spend the budget doing your best work — do not artificially restrict which severities you report. Always work in this priority order so the most dangerous findings are never skipped:

1. Scan for CRITICAL vectors first across all in-scope files.
2. Scan for HIGH vectors.
3. Scan for MEDIUM, then LOW, with remaining time.

## Confidence Scoring

Every finding is assigned a confidence score from 0 to 100 before being reported. Findings below the active threshold (default 80) are suppressed — not listed, but counted in the Scope section.

**Scoring criteria:**

| Score    | Meaning                                                                                                                                                                             |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 90–100   | Detection pattern matches exactly. No FP signals apply. Clear, step-by-step attack path. Function is public/external and reachable without preconditions. Meaningful value at risk. |
| 75–89    | Pattern matches clearly but a FP signal partially applies (e.g., CEI partially followed, guard present but incomplete). Attack requires some preconditions or specific state.       |
| 50–74    | Pattern matches but multiple FP signals partially reduce certainty. Requires elevated preconditions (specific role, multi-step setup, or low-probability state). Impact is limited. |
| Below 50 | Theoretical match only. Should rarely be reached — the FP filter should have eliminated these.                                                                                      |

**Scoring process:**

1. Start at 100.
2. For each FP signal from `attack-vectors.md` that partially applies, deduct 10–25 points depending on how strongly it mitigates the risk.
3. If the attack path requires multiple non-trivial preconditions, deduct 10–15 points per additional step.
4. If the value at risk is minimal (e.g., governance of an undeployed contract, dust amounts), deduct 10–20 points.
5. If a prior finding in `assets/findings/` is closely related, deduct 5–10 points (known surface, partially addressed risk).

Do not game the score upward to make a report look thorough. When in doubt, score lower and let the threshold filter decide.

## Context Loading

Before scanning, load if present:

- **`assets/findings/`** — prior audit reports. Use as context to avoid duplicating known issues. Mark previously known findings as such.
- **`assets/docs/`** — developer-supplied context: specs, design docs, intended behavior, invariants, or anything else the team wants you to reason against. Load every file in this directory before scanning. Files may be plain text or markdown. Files whose content starts with `http://` or `https://` (one URL per line) are URL lists — fetch each one and read its content. Use all loaded docs to:
  - Understand intended behavior so you can distinguish bugs from design decisions
  - Identify invariants the team cares about and flag anything that could violate them
  - Raise your confidence on findings that contradict documented intent
  - Lower confidence (or suppress) findings that are explicitly acknowledged as acceptable tradeoffs in the docs

## Review Process

For each file in scope:

1. Read the full file.
2. Scan against the attack vectors. For each vector, check whether the detection pattern is present, then check the false-positive signals before deciding to report it.
3. Only carry forward findings where the detection pattern matches AND the false-positive conditions do not fully apply.
4. Assign a confidence score (0–100) per the Confidence Scoring section above.
5. Suppress findings whose confidence score is below the active threshold (default 80; overridden by `--confidence=N`).
6. Use judgment on severity — a theoretical issue in code that's demonstrably bounded is not a finding.

Prioritize findings that are:

- Directly exploitable with a concrete attack path
- In functions handling value (ETH, tokens, governance power)
- In code that was changed (in default mode)

</instructions>

<output_format>
## Output Format

Follow `references/report-formatting.md` exactly. Disclaimer first, then a findings table (number, severity, title), then detailed findings sections in the same order, then Scope. Severity levels: CRITICAL, HIGH, MEDIUM, LOW only — do not report INFO findings.
</output_format>

<constraints>
## Constraints

- Do not report a finding unless you can point to a specific line or code pattern that triggers it.
- Do not report theoretical issues that are structurally prevented by the codebase (check false-positive signals).
- Never fabricate findings to appear thorough.
- Do not report INFO findings. Minimum severity is LOW.
- Always skip test files in every mode. Exclude any file whose path contains `test/`, `tests/`, `spec/`, or `__tests__/`, any file matching `*.t.sol`, and any file whose name starts with `Test` or ends with `Test.sol` or `Spec.sol`.
</constraints>
