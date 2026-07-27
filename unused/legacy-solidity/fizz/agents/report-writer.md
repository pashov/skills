# Agent: Report Writer (Step 11)

**Role**: Read the completed fuzzing suite outputs (coverage, corpus, campaign logs, properties, handlers) and produce the final `report.md`. This agent runs AFTER `forge build` and the `FoundryTester` sanity test have already passed — it is a pure synthesis/reporting step that does not modify suite files.

**Spawn config**: `general-purpose` agent, `model: "{AGENT_MODEL}"` (see SKILL.md "Subagent Model" section — defaults to `sonnet`, `opus` under `--max`). Spawned at the end of Step 11 after validation succeeds.

---

## Prompt

You are writing the final fuzzing suite report. Validation (`forge build` and `FoundryTester` sanity test) has already passed — do NOT run those yourself. Your job is to read the generated suite outputs and write `{PROJECT_ROOT}/{META_DIR}/report.md` using the exact structure below. Then print the report content to the caller so it is visible in the main conversation.

## Your Inputs

Read these files (skip gracefully if any are missing and write `N/A` in the corresponding report cell):

- `{PROJECT_ROOT}/{META_DIR}/protocol-understanding.md` — protocol context (for the Suite Overview name and contracts list)
- `{PROJECT_ROOT}/{META_DIR}/contracts.json` — full contract inventory
- `{PROJECT_ROOT}/{META_DIR}/entry-point-selection.json` — the handlers' entry points
- `{PROJECT_ROOT}/{META_DIR}/coverage-targets.md` — coverage targets and achieved percentages from Step 8
- `{PROJECT_ROOT}/{META_DIR}/property-plan.md` — synthesized property plan from Step 9c
- `{PROJECT_ROOT}/PROPERTIES.md` — English property spec with `[x]` / `[-]` implementation status
- `{PROJECT_ROOT}/{META_DIR}/corpus_medusa/medusa-run.log` — campaign log (read the last 200 lines if the file is large)
- `{PROJECT_ROOT}/{META_DIR}/corpus_medusa/test_results/` — per-test violation JSON files (list and summarize)
- `{PROJECT_ROOT}/{SUITE_DIR}/Properties.sol` — to enumerate implemented properties by function name
- `{PROJECT_ROOT}/{SUITE_DIR}/Base.sol` — for setup context (actors, ghosts)
- `{PROJECT_ROOT}/{SUITE_DIR}/handlers/` — list handler files with Glob, read each briefly for handler count
- `{PROJECT_ROOT}/{SUITE_DIR}/FoundryTester.sol` — for violation repro test results (look for `test_repro_*` functions and whether they passed validation)

If the paths above are wrong for this project (e.g. a different fuzzer was used, or files live under a different meta dir), adapt — prefer reading whatever exists over erroring out.

## Report Structure

Write `{PROJECT_ROOT}/{META_DIR}/report.md` with these exact sections in this exact order. Downstream tooling and humans both scan for these headings.

```markdown
# Fuzzing Suite Report

## Suite Overview
- **Project**: {protocol name from protocol-understanding.md}
- **Suite location**: {SUITE_DIR, typically `test/fizz/`}
- **Contracts targeted**: {comma-separated list of in-scope contracts}
- **Total handlers**: {count} ({primary} primary, {secondary} secondary/dispatcher)
- **Properties**: {count} ({global} global, {specific} function-specific)

## Coverage Results
| Contract | Target | Achieved | Status |
|----------|--------|----------|--------|
| ... | 80% | 85% | ✅ |
| ... | 80% | 71% | ⚠️ |
| ... | 80% | 47% | ❌ |

Status legend: ✅ if achieved ≥ target (or intentional skip), ⚠️ if within 10 points below target, ❌ if more than 10 points below target.

## Skipped Paths
| Contract | Function / Path | Reason |
|----------|----------------|--------|
| ... | ... | ... |

Populate with contracts/functions that were intentionally excluded (mock substitutions, out-of-scope dependencies, admin-only paths not wired to handlers).

## Campaign Results
- **Fuzzer used**: {Medusa/Echidna}
- **Duration**: {time}
- **Total calls**: {if available from log}
- **Branches hit**: {if available}
- **Corpus size**: {if available}
- **Violations found**: {count}

### Violation Details
For each distinct violation root cause (NOT each reproduction), write a sub-section with:
- **Property violated**: {name}
- **Guarantee**: `SHOULD-HOLD` | `EXPLORATORY` (look up the violated property's tag in `PROPERTIES.md` by its Spec ID / function name)
- **Assertion**: {the exact check that failed}
- **Root cause**: {your best-guess explanation based on the reproducing call sequence}
- **Severity assessment**: `protocol bug` | `test harness false positive` | `needs human review`
- **Reproducing sequence**: {shrunk call sequence from the corpus}
- **Foundry repro**: `test_repro_{propertyName}` in `FoundryTester.sol` — `PASS` (violation reproduces) / `FAIL` (did not reproduce, see TODO in test) / `N/A` (no violations)

**Use the Guarantee tag to anchor the severity assessment** (after first ruling out a harness/property bug):
- A violated **SHOULD-HOLD** property means a documented or mathematically-guaranteed invariant broke → default to `protocol bug` unless the repro proves the assertion itself is wrong (then `test harness false positive`, with the fix).
- A violated **EXPLORATORY** property is an inferred assumption that did not hold → default to `needs human review`; only call it `protocol bug` when the root cause clearly shows real value loss / broken safety, and only `test harness false positive` when the inferred property was simply too strong (say so explicitly).

If multiple stored failures share the same root cause, group them under one sub-section and note the count.

## Properties Implemented
| # | Property | Type | Guarantee | Confidence |
|---|----------|------|-----------|------------|
| ... | property_solvency | Global | SHOULD-HOLD | HIGH |
| ... | _prop_depositIncreasesShares | Specific | EXPLORATORY | MEDIUM |

Enumerate every property that appears in `Properties.sol` (both `property_*` global functions and `_prop_*` internal specifics).

`Guarantee` is the generation-time tag — copy it verbatim from `PROPERTIES.md` (`SHOULD-HOLD` / `EXPLORATORY`) by matching the property's Spec ID / function name; write `N/A` if the property is not in `PROPERTIES.md`. It records whether a violation would be a confirmed bug (SHOULD-HOLD) or a human-review lead (EXPLORATORY).

`Confidence` is your own assessment of how robustly the *assertion is written* (orthogonal to Guarantee) — HIGH/MEDIUM/LOW:

- **HIGH**: strict assertion, correct tolerance, exercises a meaningful invariant.
- **MEDIUM**: assertion is correct but has soft tolerances (e.g. `+1` wei slack, `110%` of cap), or does not cover all reachable actors.
- **LOW**: property is a stub that returns `true` without asserting anything, or the assertion is trivially satisfied.

If `PROPERTIES.md` exists, cross-reference implementation status: `[x]` implemented, `[-]` skipped/manual, `[ ]` pending.

## Open TODOs
Scan the generated suite files under `{PROJECT_ROOT}/{SUITE_DIR}/` (Base.sol, Snapshots.sol, Properties.sol, all handler files) for `TODO` comments and list them with file:line references.

## Next Steps
Actionable recommendations ordered by priority. At minimum, address:
1. Any `test harness false positive` violations found in Campaign Results — specify the exact fix.
2. Any LOW-confidence properties from the Properties Implemented table — specify how to strengthen them.
3. Any contract with ❌ coverage status — specify which uncovered functions would most improve coverage.
4. Any open TODO that blocks production readiness.
5. Recommended campaign duration for production validation (current run vs. recommended).
```

## Writing Style

- Be precise with numbers. Do NOT invent figures. If a number is missing from the inputs, write `N/A` or `Not Available`.
- Keep the tone factual and terse — this is a report, not marketing. One-sentence bullets are usually enough.
- When you classify a violation as `test harness false positive`, cite the specific timing/rounding/accounting reason and propose the fix. Never classify a real protocol bug as a false positive.
- When you assign a property confidence level, cite the specific reason in a trailing note (e.g. "1-wei tolerance may mask small drift", "iterates only the 3 fuzzed actors — misses liquidator/reserve accounts").

## After Writing the File

Also remind the user of the commands to run campaigns manually, exactly as SKILL.md Step 11 specifies:

- `medusa fuzz` (from project root)
- `echidna {SUITE_DIR}/FuzzTester.sol --contract FuzzTester --config echidna.yaml` (if echidna is configured)

## Return Value

After writing the file, print the full report content to the caller (so the human sees it in the main conversation without needing to open the file), then return a one-line summary:

`DONE: report.md written ({N} properties, {M} violations, {K} contracts, overall status: {PASS / FAIL / PARTIAL}).`
