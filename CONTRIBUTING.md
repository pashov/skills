# Contributing to Pashov Audit Group Skills

## Pull Request Process

1. Fork the repo and create a branch from `main`.
2. Make your changes — attack vectors, agent prompts, report formatting, or documentation.
3. Ensure your branch is up to date with `main` before opening a PR.
4. If your change affects what a skill does, bump that skill's `VERSION` in the same PR (e.g. `2.1` → `2.2`). Installed copies compare their `VERSION` with the one on `main` to show the upgrade notice, so a fix without a bump never reaches existing users. Documentation-only changes need no bump.
5. Fill in the PR template. A maintainer will review within 5 business days.

### PR checklist

- [ ] No API keys, tokens, or sensitive data
- [ ] No fabricated examples — outputs must reflect real model responses
- [ ] Skill works with Claude Code CLI, VS Code, and Cursor
- [ ] Bumped the affected skill's `VERSION` (not needed for documentation-only changes)

## What to Contribute

- **Attack vectors** — add new vectors to `solidity-auditor/references/attack-vectors/attack-vectors.md` following the existing `**D:**` / `**FP:**` format.
- **Agent prompts** — improve triage accuracy, reduce false positives, tighten output format.
- **Report formatting** — improve the output structure or fix template issues.
- **Bug fixes** — if the skill produces incorrect output, open an issue or PR with a fix.

## Reporting Bugs

Use the [Bug Report](.github/ISSUE_TEMPLATE/bug_report.md) issue template and include:

- Which skill is affected and how you invoked it.
- The Claude model used (e.g., claude-sonnet-4-6).
- The input you gave and the output you got.
- What you expected instead.
