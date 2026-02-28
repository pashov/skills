# audit

For **developers writing Solidity** who want a security gut-check as part of their normal workflow. Fast, focused security feedback while developing or before committing - not a replacement for a formal audit, but the check you should run every time you touch a contract.

## Usage

```bash
# Review only what changed (default)
/audit

# Review a specific file
/audit src/Vault.sol

# Review the entire repo
/audit ALL

# Confidence threshold - only report findings at or above N/100 (default: 75)
/audit --confidence=55    # broader sweep, includes more uncertain findings
/audit --confidence=95    # tight report, near-certain issues only

# Write report to a markdown file (terminal-only by default)
/audit ALL --file-output
```

## What it does

- **Default mode**: runs `git diff HEAD` and reviews only the `.sol` files you've changed
- **File mode**: reviews a single contract you specify
- **ALL mode**: scans the full repo (excludes `lib/`, `mocks/`, `*.t.sol`, `*Test*.sol`, `*Mock*.sol`)

Every run reads a tiered attack checklist before scanning: 65 core vectors, plus token-standard-specific vectors loaded on demand (11 ERC721, 10 ERC1155, 8 ERC4626, 7 ERC4337) — only the standards actually present in the code are loaded. Beyond the checklist, the model applies adversarial reasoning to catch project-specific logic bugs that don't map to any named vector. Findings below the confidence threshold are suppressed into a summary table. With `--file-output`, the full report is saved to `assets/findings/`.

## Performance

Most runs complete in under 5 minutes. Larger or more complex codebases (more files, more lines of code) take longer — the bulk of the time is spent in the analysis phase where each attack vector is checked against every in-scope file.
