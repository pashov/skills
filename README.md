# Pashov Audit Group Skills

> Claude Code skills for Solidity security and development — built by [Pashov Audit Group](https://www.pashov.com/).

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg)](CONTRIBUTING.md)

---

## Skills

| Skill                                | Description                                                                                      | Category           |
| ------------------------------------ | ------------------------------------------------------------------------------------------------ | ------------------ |
| [audit](skills/audit/)               | Fast security feedback on Solidity changes while you develop                                     | Secure Development |
| [audit-helper](skills/audit-helper/) | Full audit prep for security researchers - builds, architecture diagrams, threat model           | Security Research  |
| [lint](skills/lint/)                 | Lints Solidity code - unused imports, NatSpec, formatting, naming, custom errors, best practices | Secure Development |

---

## Install & Run

Supports **VS Code** and **Cursor** via the Claude Code extension. Clone this repo, then copy the skill folder into Claude Code's commands directory.

**Global** — available in every project:

```bash
cp -r skills/audit ~/.claude/commands/
```

**Local** — available in the current project only:

```bash
cp -r skills/audit .claude/commands/
```

The skill is then invocable as `/audit`. Replace `audit` with any skill name from the table above.

---

## Contributing · Security · License

We welcome improvements and fixes. See [CONTRIBUTING.md](CONTRIBUTING.md) for the PR process.

Report vulnerabilities via [Security Policy](SECURITY.md). This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). [MIT](LICENSE) © contributors.

## Contact

For a Pashov Audit Group security engagement, reach out on [Telegram @pashovkrum](https://t.me/pashovkrum).
