# Unused production material

This directory contains the original Solidity-oriented skills excised from the
Inferrex production path on 27 July 2026. The files are retained verbatim so
their history and restoration remain reviewable.

## Inventory

| Archived path | Former production path | Why it is unused for T0–T4 |
|---|---|---|
| `legacy-solidity/x-ray/` | `x-ray/` | Enumerates Solidity contracts, Foundry/Hardhat coverage, entry points and DeFi threat profiles |
| `legacy-solidity/solidity-auditor/` | `solidity-auditor/` | Uses smart-contract exploit gates, Solidity-specific agents and contract/function finding keys |
| `legacy-solidity/fizz/` | `fizz/` | Generates Foundry/Echidna/Medusa Solidity fuzz harnesses |
| `legacy-solidity/static/` | `static/` | Demonstrations for the archived skills |

These skills are not deleted and are not loaded by the Inferrex commands. They
remain useful reference material when Inferrex reaches a stage that owns
Solidity code, but they do not establish correctness of the T0 specification,
the T1 PostgreSQL kernel, the T2 economic loop, the T3 API or the T4 seller and
provider adapters.

## Walk an excision back into production

Restore only on a dedicated branch and only for a named stage or component.

1. Record the exact archived directory, stage owner and reason for restoration
   in the pull request.
2. Move the selected directory from `unused/legacy-solidity/<name>/` to a
   production path. Prefer a stage-qualified name such as
   `inferrex-t7-solidity-fuzz/` rather than reviving a generic command.
3. Replace DeFi-wide assumptions with the owning Inferrex specification
   invariants and stage evidence requirements. Do not merely rename the skill.
4. Narrow source detection, toolchain setup, threat profiles, report
   dispositions and output paths to the component actually under review.
5. Add the restored skill to the root skill table, version-bump workflow and
   contribution checklist.
6. Run the restored scripts against a representative repository, run the skill
   validator, and prove that non-Solidity T0–T4 repositories do not trigger it.
7. Update this inventory with the new production path, commit and pull request
   that performed the restoration. Keep any still-unused siblings here.

For a full rollback to the original layout, move all four archived directories
back to their former production paths and restore the corresponding root
README, contribution guidance and version workflow from Git history. That
rollback intentionally re-enables the original Pashov-oriented commands and
should not be combined with the Inferrex commands without resolving command
and scope ambiguity.
