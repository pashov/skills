# Pashov Audit Group Skills

> Claude skills for web3 development and security research. Built by Pashov Audit Group [www.pashov.com](https://www.pashov.com/)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg)](CONTRIBUTING.md)

Drop a skill into Claude Code and it gains a focused, reusable capability — works in VS Code and Cursor.

---

## Skills

| Skill                                | Description                                                                                      | Category           |
| ------------------------------------ | ------------------------------------------------------------------------------------------------ | ------------------ |
| [audit](skills/audit/)               | Fast security feedback on Solidity changes while you develop                                     | Secure Development |
| [audit-helper](skills/audit-helper/) | Full audit prep for security researchers - builds, architecture diagrams, threat model           | Security Research  |
| [lint](skills/lint/)                 | Lints Solidity code - unused imports, NatSpec, formatting, naming, custom errors, best practices | Secure Development |

---

## Install

Clone this repo, then copy the skill folder into Claude Code's commands directory.

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

## Contributing

We welcome new skills, improvements, and fixes. See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide — skill structure, quality standards, and PR process. One skill, one purpose.

Skills follow the [agentskills.io](https://agentskills.io/) open standard.

---

## Security · Code of Conduct · License

Report vulnerabilities via [Security Policy](SECURITY.md). This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). [MIT](LICENSE) © contributors.

For a Pashov Audit Group security engagement, reach out on [Telegram @pashovkrum](https://t.me/pashovkrum).
