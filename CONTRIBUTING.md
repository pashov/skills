# Contributing to Pashov Audit Group Skills

Thank you for your interest in contributing. This guide covers everything you need to add or improve a skill.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Ways to Contribute](#ways-to-contribute)
- [Before You Start](#before-you-start)
- [Skill Structure](#skill-structure)
- [Creating a New Skill](#creating-a-new-skill)
- [Improving an Existing Skill](#improving-an-existing-skill)
- [Quality Standards](#quality-standards)
- [Pull Request Process](#pull-request-process)
- [Reporting Bugs](#reporting-bugs)

---

## Code of Conduct

By participating, you agree to our [Code of Conduct](CODE_OF_CONDUCT.md). Please read it before contributing.

---

## Ways to Contribute

- **New skill** — Add a focused, self-contained skill for a new capability.
- **Improve an existing skill** — Sharpen instructions, add attack vectors, fix false positives, improve output format.
- **Expand reference material** — Add entries to a skill's `references/` files (e.g., new attack vectors to `security-scan`, new lint rules to `lint`).
- **Documentation** — Fix typos, improve usage examples, clarify instructions.
- **Bug report** — Open an issue using the bug report template.

---

## Before You Start

1. **Search existing issues and PRs** to avoid duplicating work.
2. For new skills or significant changes, open an issue first to discuss your approach.
3. Fork the repository and create a branch from `main`.

```bash
git clone https://github.com/pashov/skills.git
cd skills
git checkout -b feat/my-skill-name
```

---

## Skill Structure

Every skill lives in its own directory under `skills/`:

```
skills/
└── skill-name/
    ├── SKILL.md          # Required — YAML frontmatter + instruction body
    ├── README.md         # Required — usage examples and feature documentation
    ├── references/       # Optional — reference material loaded at runtime
    ├── assets/           # Optional — codebase-specific data (per-project, not checked in by contributors)
    └── scripts/          # Optional — executable helpers invoked by the skill
```

### `SKILL.md`

The core of every skill. Consists of a YAML frontmatter block followed by the instruction body.

**Frontmatter** (required fields):

```yaml
---
name: skill-name
description: >
  What this skill does and when to use it. This text is read by the agent to
  decide when to invoke the skill — be specific about trigger phrases and use cases.
---
```

The `name` becomes the slash command: `name: security-scan` → `/security-scan`.

**Instruction body**: everything below the frontmatter. Written in plain markdown. Describes exactly what the agent should do — workflow, modes, output format, constraints. See the existing skills for style guidance.

### `README.md`

Human-readable documentation. Must include:

- What the skill does (2-3 sentences)
- Usage examples with actual invocation commands
- Any configuration or setup the user needs to do (e.g., populating `assets/false-positives.md`)

### `references/`

Files the agent loads at runtime to inform its work. Examples:

- `security-scan/references/attack-vectors.md` — 52 attack vectors with detect patterns and false-positive signals
- `lint/references/rules.md` — detailed rules for each linting pass

Reference files should be structured and precise — the agent reads them as a checklist or specification.

### `assets/`

Per-project data that users populate themselves. **Not contributed to this repo** — these files exist in the user's own codebase.

Examples from `security-scan`:

- `assets/false-positives.md` — known non-issues for a specific codebase
- `assets/findings/` — prior audit reports used as context

Document the expected format in the skill's `README.md` so users know how to populate these files.

### `scripts/`

Executable helpers (bash, Python, etc.) invoked by the skill as part of its workflow. Must be well-documented and not require external dependencies unless absolutely necessary.

---

## Creating a New Skill

### 1. Create the directory

```bash
mkdir skills/your-skill-name
```

Do not copy from `_template/` — there is no template directory. Use an existing skill as reference instead.

### 2. Write `SKILL.md`

Start with frontmatter:

```yaml
---
name: your-skill-name
description: >
  One to three sentences. What capability does this add? When should an agent invoke it?
  Include likely trigger phrases ("when the user says X", "use when Y").
---
```

Then write the instruction body. Be explicit about:

- **Modes** — if the skill supports different invocation patterns, document each
- **Workflow** — step by step what the agent does
- **Output format** — exact structure the agent should produce
- **Constraints** — what the agent must never do

### 3. Write `README.md`

Document the skill for users. Include:

- What it does and who it is for
- Every invocation pattern with a real command example
- Any files the user needs to create in their project (`assets/`)
- Limitations and what the skill is not designed to do

### 4. Add reference material (if needed)

If your skill requires a reference file (checklist, ruleset, specification), place it in `references/` and load it explicitly in the instruction body of `SKILL.md`.

Reference content must reflect real, tested behavior — no fabricated examples.

### 5. Verify the skill works

Test your skill with at least one real invocation on an actual codebase or file. Paste a representative input/output pair in your PR.

---

## Improving an Existing Skill

The most valuable contributions are targeted improvements to existing skills:

**Adding to `references/`** — new attack vectors in `security-scan`, new lint rules in `lint`. Follow the exact format of existing entries (detect pattern + false-positive signal, or rule + rationale).

**Fixing the instruction body in `SKILL.md`** — tighten a workflow step, clarify output format, add a missing constraint, fix a false-positive in the scanning logic.

**Improving `README.md`** — add a usage example, document a mode that isn't covered, correct outdated instructions.

**Do not** change the invocation name (`name` in frontmatter) without updating all references to it across the repo.

---

## Quality Standards

- **One skill, one purpose.** A skill that does two unrelated things should be two skills.
- **No fabricated examples.** Outputs in documentation must reflect real model responses, not idealized ones.
- **No secrets or personal data.** No API keys, tokens, wallet addresses, internal hostnames, or anything sensitive.
- **Agent-agnostic.** Skills must work across Claude Code, Codex, GitHub Copilot, Cursor, and Windsurf. Avoid Claude-specific syntax in the instruction body unless the skill explicitly targets a single agent.
- **Honest about scope.** If a skill only works well for Foundry projects, say so clearly. Do not overstate capability.
- **Constraints are mandatory.** Every skill instruction body must include explicit constraints — what the agent must not do, must not report, must not fabricate.

---

## Pull Request Process

1. Ensure your branch is up to date with `main`.
2. CI runs automatically on push — make sure it passes:
   - `python scripts/validate_skills.py` — validates skill manifests
   - `markdownlint` — lints all `.md` files
3. Fill in the PR template completely. Include a real input/output example.
4. A maintainer will review within 5 business days.
5. Address feedback promptly. Once approved, a maintainer will merge.

### PR checklist

- [ ] `SKILL.md` has `name` and `description` frontmatter
- [ ] `README.md` documents usage with at least one real example
- [ ] Reference files (if any) contain only real, tested content — no fabricated outputs
- [ ] No API keys, tokens, or sensitive data anywhere in the skill
- [ ] Skill works with at least one agent listed in the repo's supported matrix
- [ ] CI passes

---

## Reporting Bugs

Use the [Bug Report](.github/ISSUE_TEMPLATE/bug_report.md) issue template and include:

- Which skill is affected and how you invoked it.
- The agent and model used (e.g., Claude Code with claude-sonnet-4-6).
- The input you gave and the output you got.
- What you expected instead.
