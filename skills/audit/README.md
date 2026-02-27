# audit

Fast, simple, stupid but effective security feedback while developing or before committing to version control.

Built for **developers** who want to catch issues early - not a replacement for a formal audit, but the check you should run every time you touch a contract.

## Usage

```bash
# Review only what changed (default)
/audit

# Review a specific file
/audit src/Vault.sol

# Review the entire repo
/audit ALL

# Default run is 150 seconds - use --max-run-time to make it shorter or longer
/audit --max-run-time=60   # quicker gut-check
/audit --max-run-time=300  # deep scan

# Confidence threshold - only report findings at or above N/100 (default: 80)
/audit --confidence=65    # broader sweep, includes more uncertain findings
/audit --confidence=95    # tight report, near-certain issues only

```

## What it does

- **Default mode**: runs `git diff HEAD` and reviews only the `.sol` files you've changed
- **File mode**: reviews a single contract you specify
- **ALL mode**: scans the full repo at its current state

Every run reads the full 62-vector attack checklist before scanning. Beyond the checklist, the model applies its own security analysis to catch project-specific logic bugs and unusual vulnerability combinations that don't map to any named vector. Findings below the confidence threshold are suppressed — the report stays signal, not noise.

## Giving it project context

Drop any docs into `assets/docs/` — specs, design documents, invariants, or a plain-English description of what the protocol is supposed to do. The reviewer reads all of it before scanning and uses it to distinguish bugs from intentional design, sharpen findings that contradict documented intent, and suppress anything the team has already acknowledged as an acceptable tradeoff.

Files can be plain text or markdown. To point it at online docs, create a file whose lines are URLs (one per line) — they will be fetched and read automatically.

## Carrying over previous findings

Drop prior audit report `.md` files into `assets/findings/`. The reviewer will use them as context - avoiding duplicate findings and focusing on new attack surface.

## Who this is for

Developers writing Solidity who want a security gut-check as part of their normal workflow.
