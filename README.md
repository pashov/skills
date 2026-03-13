# Pashov Audit Group Skills

> Claude Code skills for Solidity security and development — built by [Pashov Audit Group](https://www.pashov.com/).

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg)](CONTRIBUTING.md)

---

## Install & Run

Works with the **Claude Code CLI**, the **VS Code Claude extension**, and **Cursor**.

**AI CLI (Claude Code / Cursor chat):**

Install the skill by pasting this prompt:

```
Install skill https://github.com/pashov/skills/
```

Run the skill by pasting this prompt:

```
run solidity auditor on the *specified files*
```

**Claude Code CLI:**

```bash
git clone https://github.com/pashov/skills.git && mkdir -p ~/.claude/commands && cp -r skills/solidity-auditor ~/.claude/commands/solidity-auditor
```

**Cursor:**

```bash
git clone https://github.com/pashov/skills.git && mkdir -p ~/.cursor/skills && cp -r skills/solidity-auditor ~/.cursor/skills/solidity-auditor
```

The skill is then invocable as `/solidity-auditor`. See the [skill README](solidity-auditor/README.md) for usage.

**Update to latest:**

AI CLI prompt:

```
update the solidity-auditor skill to latest from https://github.com/pashov/skills/
```

Or `cd` into the cloned `skills` repo and run:

```bash
git pull
# Claude Code CLI:
cp -r solidity-auditor ~/.claude/commands/solidity-auditor
# Cursor:
cp -r solidity-auditor ~/.cursor/skills/solidity-auditor
```

---

## Skills

| Skill                                 | Description                                                                     |
| ------------------------------------- | ------------------------------------------------------------------------------- |
| [solidity-auditor](solidity-auditor/) | Fast (typically <5 min) security feedback on Solidity changes while you develop |

---

## Contributing · Security · License

We welcome improvements and fixes. See [CONTRIBUTING.md](CONTRIBUTING.md) for the PR process.

Report vulnerabilities via [Security Policy](SECURITY.md). This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). [MIT](LICENSE) © contributors.

## Contact

If you are looking to explore strategies for securing your project, reach out for a chat on [Telegram @pashovkrum](https://t.me/pashovkrum).

[![Discord](https://img.shields.io/badge/Discord-5865F2?logo=discord&logoColor=white)](https://discord.com/invite/pashovauditgroup) [![X](https://img.shields.io/badge/X-000000?logo=x&logoColor=white)](https://x.com/PashovAuditGrp) [![Telegram](https://img.shields.io/badge/Telegram-26A5E4?logo=telegram&logoColor=white)](https://t.me/pashovkrum) [![Website](https://img.shields.io/badge/Website-FF5722?logo=googlechrome&logoColor=white)](https://www.pashov.com/)
