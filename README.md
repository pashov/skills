# Pashov Audit Group Skills

> AI skills for Solidity security and development — built by [Pashov Audit Group](https://www.pashov.com/).

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg)](CONTRIBUTING.md)

---

## Install & Run

### Claude Code (CLI, VS Code extension, Cursor)

```bash
git clone https://github.com/pashov/skills.git && mkdir -p ~/.claude/commands && cp -r skills/solidity-auditor ~/.claude/commands/solidity-auditor
```

Invoke with `/solidity-auditor`. See the [skill README](solidity-auditor/README.md) for usage.

### Codex

```bash
git clone https://github.com/pashov/skills.git && mkdir -p ~/.agents/skills/solidity-auditor && cp -r skills/solidity-auditor/. ~/.agents/skills/solidity-auditor/
```

Restart Codex after install. Invoke with `$solidity-auditor` (or select it via `/skills`).

### Update to latest

`cd` into the cloned `skills` repo and run:

```bash
git pull
cp -r solidity-auditor ~/.claude/commands/solidity-auditor
mkdir -p ~/.agents/skills/solidity-auditor && cp -r solidity-auditor/. ~/.agents/skills/solidity-auditor/
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
