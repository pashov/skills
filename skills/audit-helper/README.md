# audit-helper

Bootstraps everything a security researcher needs to understand a Solidity protocol before they start finding bugs. Point it at a Foundry or Hardhat repo and it builds the project, reads the contracts, and produces five structured documents in an `audit-helper/` directory.

## What it generates

| File | Contents |
|---|---|
| `protocol-summary.md` | Plain-English overview - what the protocol does, core invariants, roles, upgrade patterns, design tradeoffs |
| `architecture.md` | Mermaid class diagram of contracts, inheritance, dependencies, and external integrations |
| `flow-of-funds.md` | Mermaid flowchart of every path ETH and tokens take - deposits, withdrawals, fees, liquidations |
| `integrations.md` | Every external dependency (oracles, DEXes, bridges) with trust assumptions and failure modes |
| `threat-model.md` | Assets, actors, trust boundaries, attack surfaces, and realistic threat scenarios derived from the actual code |

## Usage

```
/audit-helper
```

Run it from the repo root. It detects Foundry (`foundry.toml`) or Hardhat (`hardhat.config.js/ts`) automatically, builds the project, then generates all five files. If the build fails, errors are captured in `audit-helper/build-errors.md` and the rest of the workflow continues.

## Who this is for

Security researchers and auditors who want to get up to speed on an unfamiliar codebase fast. The output is designed to be dropped into an audit workspace, shared with a team, or used as context for a deeper manual review.

For ongoing security feedback during development, see [`audit`](../audit/).
