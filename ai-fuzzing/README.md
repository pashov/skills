# ai-fuzzing

A full fuzz testing suite for your smart contracts in minutes, not weeks — works with any Foundry or Hardhat project, on both Echidna and Medusa.

Built for:

- **Solidity devs** who know they should fuzz but don't have weeks to set it up
- **Security researchers** who want a full suite generated in minutes, not days

Not a replacement for a hand-written suite — just the fastest way to go from nothing to real test coverage.

## What You Get

One command produces:

| Output | What's Inside |
|--------|--------------|
| `test/ai_fuzzing/` | Full harness — setup, handlers, and invariants in plain, editable Solidity |
| `PROPERTIES.md` | Every invariant in plain English, each with a stable ID and status |
| Repro tests | A deterministic Foundry test for each distinct violation found |
| `report.md` | Campaign summary — coverage reached and violations surfaced |

## Requirements

- [Foundry](https://getfoundry.sh) and [Medusa](https://secure-contracts.com/program-analysis/medusa/docs/src/getting_started/installation.html) — required
- [Echidna](https://secure-contracts.com/program-analysis/echidna/introduction/installation.html) — optional, recommended

## Install

```bash
git clone https://github.com/PashovAuditGroup/ai-fuzzing.git
cd ai-fuzzing
mkdir -p ~/.claude/skills
ln -s "$PWD"                     ~/.claude/skills/ai-fuzzing
ln -s "$PWD/skills/fuzz-convert" ~/.claude/skills/fuzz-convert
ln -s "$PWD/skills/fuzz-sync"    ~/.claude/skills/fuzz-sync
```

Restart Claude Code. You'll have `/ai-fuzzing`, `/fuzz-convert`, and `/fuzz-sync`.

## Usage

```
/ai-fuzzing
```

Or describe the focus:

```
Generate a fuzz suite for this lending protocol. Focus on solvency and liquidation invariants.
```

- **Automatic** (default) — runs end-to-end, no prompts.
- **Guided** (`--guided`) — pauses to review entry points, setup, properties, and fuzzer choice.

## Tips

- **Run guided on first use.** Reviewing entry points and properties once shows exactly what the suite covers — then switch to automatic.
- **Keep it in sync.** After changing contracts, run `/fuzz-sync` to update the suite instead of regenerating it.
- **Write properties in English.** Drop plain-English invariants into `PROPERTIES.md` and `/fuzz-convert` turns them into Solidity.
