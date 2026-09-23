# Solidity Auditor

A security agent with a simple mission - findings in minutes, not weeks.

Built for:

- **Solidity devs** who want a security check before every commit
- **Security researchers** looking for fast wins before a manual review
- **Just about anyone** who wants an extra pair of eyes.

Not a substitute for a formal audit - but the check you should never skip.

## Demo

_Portrayed below: finding multiple high-confidence vulnerabilities in a codebase_

![Running solidity-auditor in terminal](../static/skill_pag.gif)

## Usage

```
Install https://github.com/pashov/skills/ and run solidity auditor on the codebase
```

```
run solidity auditor on *specified files*
```

```
update skill to latest version
```

More than one run per scan is loop mode. Each run is a full audit, and every run after the first is
told what the earlier ones found, so it hunts new ground instead of the same bugs. You get one
report at the end, not one per run.

```
run solidity auditor in loop mode
```

## Tips

- **Target hot contracts.** Rather than scanning an entire repo, point the tool at the 2-5 contracts you're actively changing. Smaller scope means denser context for each agent and higher-signal findings.
- **Use loop mode.** LLM output is non-deterministic — each pass can surface different vulnerabilities. Three passes is a good default: the later ones know what the earlier ones found, and you still get a single report.
- **Read the report file.** Long scans print a short summary in the terminal; every finding and its fix is in `full-report.md`.
