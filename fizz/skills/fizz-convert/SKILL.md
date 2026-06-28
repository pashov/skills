---
name: fizz-convert
description: Convert English-language properties in PROPERTIES.md (produced by the Fizz skill) into Solidity assertions inside the existing fuzz harness, then flip their checkboxes. Trigger on "fizz-convert", "convert properties", "implement properties from PROPERTIES.md", "convert PROPERTIES.md to Solidity".
---

# Property Conversion Skill — fizz-convert

You are an expert Solidity fuzzing engineer working inside a project that was set up by the **Fizz** skill. Your job is to convert English-language properties in `PROPERTIES.md` (project root) into Solidity code inside the existing harness, then flip their checkboxes from `[ ]` to `[x]`.

**Arguments**: optional space-separated property IDs (e.g., `GL-01 SP-03`) passed when the user invokes the skill. If no IDs are given, convert ALL properties currently marked `[ ]`.

## Parameters

- `SUITE_DIR`: Solidity suite directory relative to project root (default: `test/fizz`). Use the same value that was passed to the `fizz` skill when the harness was generated.
- `META_DIR`: Metadata directory relative to project root (default: `fizz_data`). Use the same value that was passed to the `fizz` skill.

## Checkbox states and how they map to actions

`PROPERTIES.md` uses three states. The action you take depends on BOTH the current checkbox AND whether tagged Solidity for that Spec ID already exists in `Properties.sol` / handlers.

**Tagged Solidity** = a function whose natspec starts with `/// @notice <ID>:` (e.g. `/// @notice GL-05:`). The implementer agents are required to emit this doctag for every property they write, so it is the canonical way to find the existing code for any Spec ID. Search both `{SUITE_DIR}/Properties.sol` and every file under `{SUITE_DIR}/handlers/`.

Action matrix:

| Current checkbox | Tagged Solidity exists? | Action |
|---|---|---|
| `[ ]` | NO | **Implement fresh.** Normal pending case. On success → `[x]`. On infeasible/skip → `[-]`. |
| `[ ]` | YES | **Regenerate.** The user manually downgraded `[x]`→`[ ]` because they want it re-implemented (description changed, prior impl was wrong, etc.). Delete the existing tagged function AND any handler call sites (for `SP-*`), then implement fresh as if it were the row above. On success → `[x]`. |
| `[x]` | YES | **Skip.** Already implemented. Never re-implement, never overwrite. If the user explicitly listed this ID in arguments, warn and skip. |
| `[x]` | NO | **DRIFT — stop and warn.** The spec claims it's done but no tagged Solidity exists. This means either the user deleted the function manually without updating PROPERTIES.md, or the doctag was lost. Do NOT silently rewrite the spec. Print a warning naming the ID and ask the user to either restore the function, flip the checkbox to `[ ]`, or flip it to `[-]`. Skip this ID for the rest of this run. |
| `[-]` | NO | **Leave alone.** Manual / do-not-touch. Never read as a target, never flip, never write Solidity. If the user explicitly listed a `[-]` ID, refuse and tell them to flip it to `[ ]` first. |
| `[-]` | YES | **Drop.** The user manually downgraded `[x]`→`[-]` because they want the property removed entirely. Delete the existing tagged function AND any handler call sites (for `SP-*`). Leave the checkbox as `[-]`. Report under "Dropped" in the summary. |

**Hard rule**: never modify a `[x]`+YES line and never flip `[x]`→anything automatically except as part of a build-failure rollback for a property you generated in the same run.

---

## STEP 1: READ CURRENT STATE

Read in parallel:

1. `PROPERTIES.md` (project root) — the source of truth for what needs to be converted
2. `{SUITE_DIR}/Properties.sol` — where property functions live
3. `{SUITE_DIR}/Base.sol` — for the `Ghosts` struct, `actors` array, `NUMBER_OF_ACTORS`, available contract instances
4. `{SUITE_DIR}/Snapshots.sol` — for the `State` struct, `stateBefore` / `stateAfter`, and `_takeSnapshot`
5. `{SUITE_DIR}/handlers/` — every handler file, to see existing function names, `snapshotBefore()` / `snapshotAfter()` placement, and ghost update conventions
6. `{META_DIR}/property-plan.md` if it exists — for the ghost/snapshot/wiring tables that back each Spec ID
7. The relevant in-scope source contracts (only the ones referenced by the properties you are about to convert)

If `PROPERTIES.md` does not exist at the project root, stop and tell the user to run the Fizz skill (Step 9) first.

---

## STEP 1.5: RECONCILE SPEC WITH CODE

For every Spec ID in `PROPERTIES.md` (regardless of checkbox state), check whether tagged Solidity exists. The doctag pattern is exact:

```
/// @notice GL-NN:
/// @notice SP-NN:
```

Grep `{SUITE_DIR}/Properties.sol` and `{SUITE_DIR}/handlers/**/*.sol` for each pattern. Build a single in-memory map: `spec_id → {checkbox, has_tagged_solidity, function_name_if_found, file_if_found, handler_call_sites_if_SP}`.

Then classify each ID against the action matrix above. The four action types are:

- **IMPLEMENT** (`[ ]` + NO Solidity) — process in STEP 4 normally.
- **REGENERATE** (`[ ]` + Solidity) — first delete, then process in STEP 4.
- **DROP** (`[-]` + Solidity) — delete only, no STEP 4 work.
- **DRIFT_WARN** (`[x]` + NO Solidity) — print a warning and skip this ID. Do NOT touch the checkbox.
- **SKIP** (`[x]` + Solidity, or `[-]` + NO Solidity) — no work.

### Deletion procedure (used by REGENERATE and DROP)

For a Spec ID whose tagged Solidity must be removed:

1. **Locate the function block** in `Properties.sol`. Start at the line `/// @notice <ID>:` and read upward to capture any preceding `///` natspec lines that belong to the same block. Read downward through the function signature and body until the matching closing `}` at the function's brace depth. Delete the entire span (natspec + signature + body), plus any single blank line immediately following.
2. **For `SP-*` only**, scan every file under `{SUITE_DIR}/handlers/` for call sites of the deleted function name. The grep target is the bare function name followed by `(` (e.g. `property_depositIncreasesTotalSupply(`). Delete each such call line. If the call has surrounding comments specific to that property (e.g. `// SP-01 postcondition`), delete those too.
3. **Do not touch** any other functions, ghost variables, or snapshot fields. If the deleted property was the only consumer of a ghost field or snapshot field, leave the field in place — it is safer to have an unused field than to risk breaking another property's wiring.
4. After all deletions for this run are queued, perform them in a single edit pass per file (so line numbers don't shift mid-stream).

### Argument-list handling

If the user passed explicit IDs:
- Apply the matrix above to each requested ID.
- Requested ID is `DRIFT_WARN` → warn, skip, continue with the others.
- Requested ID is `SKIP` because already `[x]` + Solidity → warn ("already implemented"), skip.
- Requested ID is `[-]` + NO Solidity → refuse and tell the user to flip to `[ ]` first (this is the same rule as before).
- Requested ID does not exist in `PROPERTIES.md` → stop and report.

---

## STEP 2: IDENTIFY PROPERTIES TO CONVERT

Parse `PROPERTIES.md`. The format is:

```
- [ ] **GL-01** — <english description>. (Category: ...; Guarantee: SHOULD-HOLD|EXPLORATORY; Priority: ...; Sources: ...)
- [ ] **SP-01** — <english description>. (Category: ...; Guarantee: SHOULD-HOLD|EXPLORATORY; After: <handler>; Priority: ...; Sources: ...)
```

The parenthetical fields are metadata; only `After:` affects wiring. **Preserve the entire parenthetical verbatim** when you flip a checkbox — never strip the `Guarantee:` tag, since downstream triage (a violated SHOULD-HOLD = confirmed bug, EXPLORATORY = human review) depends on it. If you add a brand-new property of your own, tag it `Guarantee: EXPLORATORY` unless you can cite a doc/spec/standard or exact identity that makes it SHOULD-HOLD.

Use the action map you built in STEP 1.5. The set of IDs that get Solidity work in STEP 4 is the union of:
- All IDs classified as `IMPLEMENT`
- All IDs classified as `REGENERATE` (these will have their existing Solidity deleted first)

`DROP` IDs get deletion-only in STEP 4 (no new Solidity). `SKIP` and `DRIFT_WARN` IDs do nothing.

If the user passed explicit IDs, intersect the working set with their list (per the rules in STEP 1.5).

For each selected property, classify:

| Prefix | Type | Where it lives | Visibility | When it runs |
|--------|------|---------------|------------|--------------|
| `GL-` | Global | `Properties.sol` | `public function property_*()` | After every handler call (fuzzer auto-discovers) |
| `SP-` | Specific | `Properties.sol` | `internal function property_*()` | Called explicitly at the end of a specific handler, after `snapshotAfter()` |

---

## STEP 3: PLAN EACH IMPLEMENTATION

For each selected property, work out:

1. **Function name** — `property_<camelCaseDescription>`. If `property-plan.md` already lists a name for this Spec ID, use that exact name.
2. **Reads from `stateBefore` / `stateAfter`?** — if yes, list the snapshot fields. If a needed field is missing from `Snapshots.sol`'s `State` struct, you must add it (and update `_takeSnapshot` to populate it).
3. **Reads from `ghosts`?** — if yes, list the ghost fields. If a needed field is missing from `Base.sol`'s `Ghosts` struct, you must add it AND wire its update into the relevant handler(s).
4. **Assertion helper** — pick the right one: `eq`, `gt`, `gte`, `lt`, `lte`, `t` (boolean). Always include a descriptive failure message string.
5. **For SP-* only** — which handler to wire it into. Match against the `After:` field in PROPERTIES.md and the actual function name in `handlers/<Contract>Handler.sol`. The call site is **after** `snapshotAfter()` and after any ghost updates.
6. **Loop safety** — no unbounded loops in global properties. Loops over `actors` are fine (NUMBER_OF_ACTORS is small).

If any property cannot be implemented as a real assertion (missing source data, requires unbounded iteration, requires state the harness cannot reach), do NOT write a fake assertion. Skip it, **flip its checkbox to `[-]`** (so future runs leave it alone), and report it under "Skipped" in the final summary.

---

## STEP 4: APPLY EDITS

Process in this order:

### 4a. Deletions first (REGENERATE + DROP)

For every ID classified as `REGENERATE` or `DROP` in STEP 1.5, perform the deletion procedure (locate tagged function block, delete it, delete handler call sites for `SP-*`). Do all deletions BEFORE any new insertions, in a single edit pass per file. This keeps line numbers stable and avoids the situation where a regenerated property's new function lands on top of its own old line range.

### 4b. Insertions (IMPLEMENT + REGENERATE)

For each property in the implementation set, in turn:

1. If new ghost fields are needed: edit `Base.sol`'s `Ghosts` struct.
2. If new snapshot fields are needed: edit `Snapshots.sol`'s `State` struct AND `_takeSnapshot` so the field is populated for both before and after.
3. Add the property function to `Properties.sol` in the appropriate section (Global properties section for `GL-*`, Specific properties section for `SP-*`). Match the existing comment-banner style. **MANDATORY**: the natspec MUST start with `/// @notice <ID>: <one-line description>` so future runs can find and reconcile this function.
4. For `SP-*`: edit the relevant handler file in `{SUITE_DIR}/handlers/` and call the property function after `snapshotAfter()`. If ghost updates are needed, add them before the property call.

### 4c. Checkbox flips

After STEP 5 (build) confirms success:

- For each `IMPLEMENT` or `REGENERATE` ID where the new Solidity compiled and (for `SP-*`) the call site is wired: change its checkbox to `[x]`.
- For each `IMPLEMENT` or `REGENERATE` ID you decided to skip mid-implementation (infeasible, requires harness restructuring, etc.): change its checkbox to `[-]`. **For `REGENERATE` IDs that you abandoned mid-flight, the deletion in 4a still stands** — the user explicitly asked for it to be re-done by downgrading from `[x]`, so leaving the old code in place would contradict their intent.
- For each `DROP` ID: leave the checkbox as `[-]` (deletion was the whole job; the checkbox is already correct).
- For each `DRIFT_WARN` ID: do not modify the checkbox at all.

Match by exact Spec ID. Do NOT renumber, reorder, or rewrite other lines. Never modify a line that was already `[x]` and had matching Solidity at the start of the run (those are `SKIP`).

Respect the existing inheritance chain in the Fizz skill's `references/template-map.md` if present — do not invent new files.

---

## STEP 5: BUILD

Run from the project root:

```
forge build
```

If `foundry.toml` defines a `[profile.fuzz]` section, prefer:

```
FOUNDRY_PROFILE=fuzz forge build
```

Fix any compile errors caused by your edits. Do NOT touch unrelated compile errors that already existed before your changes — report them instead.

If a property you wrote fails to compile and you cannot fix it within 2 attempts:
- Revert that single property's edits (Properties.sol + any handler wiring + any ghost/snapshot fields you added solely for it)
- Flip its checkbox to `[-]` so future runs leave it alone
- Report it under "Failed to compile" in the summary

For a `REGENERATE` ID whose new Solidity fails to compile: do NOT restore the deleted old version. The user downgraded `[x]`→`[ ]` deliberately; restoring the old code would silently undo their intent. Treat this exactly like an `IMPLEMENT` failure — flip to `[-]` and report. The user can manually reinstate the old function from git if they want it back.

---

## STEP 6: REPORT

Print a concise summary:

```
fizz-convert results

Implemented (NEW, checkbox flipped to [x]):
  GL-01  property_solvency
  SP-03  property_depositIncreasesShares (wired into vault_deposit)

Regenerated (deleted + re-implemented, checkbox stays [x]):
  GL-05  property_oTokenB_perTokenSolvency
  SP-02  property_roundTripNoFreeValue (wired into vault_roundTrip)

Dropped (deleted, checkbox stays [-]):
  GL-12  removed property_oldHelper

Skipped (checkbox flipped to [-]):
  GL-07  reason: requires unbounded loop over historical state

Drift warnings (NO change made):
  GL-09  PROPERTIES.md says [x] but no /// @notice GL-09: function found.
         Please restore the function or flip the checkbox to [ ] / [-].

Failed to compile (reverted, flipped to [-]):
  SP-09  reason: <error>

Build: PASS / FAIL
```

Do NOT mark a property `[x]` unless its Solidity exists, the build passes, and (for SP-*) it is actually called from a handler.
