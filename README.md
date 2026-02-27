# Pashov Audit Group Skills

> Modular, agent-agnostic skills for web3 development and security research. Built by Pashov Audit Group [www.pashov.com](https://www.pashov.com/)

[![Agent Skills](https://img.shields.io/badge/Agent_Skills-agentskills.io-5B8DEF)](https://agentskills.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg)](CONTRIBUTING.md)

Drop a skill into your AI environment and it gains a focused, reusable capability - like a plugin, but for AI agents.

|                | Supported                                         |
| -------------- | ------------------------------------------------- |
| **Models**     | Claude · ChatGPT · Gemini                         |
| **Agents**     | Claude Code · Codex · OpenCode · GitHub Copilot   |
| **IDEs**       | VS Code · Cursor · Windsurf                       |
| **Extensions** | Claude Code · GitHub Copilot · Gemini Code Assist |

---

## Skills

| Skill                            | Description                                                                                      | Category           |
| -------------------------------- | ------------------------------------------------------------------------------------------------ | ------------------ |
| [audit](skills/audit/)           | Fast security feedback on Solidity changes while you develop                                     | Secure Development |
| [audit-helper](skills/audit-helper/) | Full audit prep for security researchers - builds, architecture diagrams, threat model           | Security Research  |
| [lint](skills/lint/)             | Lints Solidity code - unused imports, NatSpec, formatting, naming, custom errors, best practices | Secure Development |

---

## Install

**1. Clone**

```bash
git clone https://github.com/pashov/skills
```

**2. Copy a skill to your agent**

| Agent                   | Command                                                |
| ----------------------- | ------------------------------------------------------ |
| Claude Code (global)    | `cp -r skills/audit ~/.claude/skills/audit`            |
| GitHub Copilot (global) | `cp -r skills/audit ~/.copilot/skills/audit`           |
| Cursor (global)         | `cp skills/audit/SKILL.md ~/.cursor/commands/audit.md` |

**3. Invoke**

```
/audit path/to/Contract.sol
```

Each skill has its own README with all modes, flags, and usage examples — see [skills/audit/README.md](skills/audit/README.md).

---

## Contributing

We welcome new skills, improvements, and fixes. See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide — skill structure, quality standards, and PR process. One skill, one purpose.

Skills follow the [agentskills.io](https://agentskills.io/) open standard.

---

## Security · Code of Conduct · License

Report vulnerabilities via [Security Policy](SECURITY.md). This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). [MIT](LICENSE) © contributors.

For a Pashov Audit Group security engagement, reach out on [Telegram @pashovkrum](https://t.me/pashovkrum).
