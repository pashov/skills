---
name: fizz-sync
description: Reconcile an existing Fizz harness with a changed source tree. Detects added/removed/changed contract functions, quarantines stale properties, regenerates drifted handler stubs, and refreshes the snapshot. Trigger on "fizz-sync", "resync fuzzing", "sync fuzz harness", "refresh fuzzing properties", "fuzzing drift check".
---

# Fizz Sync Skill — fizz-sync

Reconcile a project previously processed by the **Fizz** skill with a changed source tree. This is the re-use entry point: after the user modifies Solidity sources, `fizz-sync` detects drift, quarantines stale properties, regenerates drifted handler stubs, and refreshes the snapshot — WITHOUT re-running the full 11-step pipeline.

## When to use

- The source contracts under `src/` changed since `fizz` last ran.
- A property in `PROPERTIES.md` fails to compile or references a function that no longer exists.
- The user added new external functions they want fuzzed.
- The user wants a "is anything stale?" health check before re-running a campaign.

## Parameters

- `SUITE_DIR`: Solidity suite directory relative to project root (default: `test/fizz`). Use the same value that was passed to the `fizz` skill when the harness was generated.
- `META_DIR`: Metadata directory relative to project root (default: `fizz_data`). Use the same value that was passed to the `fizz` skill.

## Arguments

- `--init` — one-time bootstrap: create `{META_DIR}/last-run.json` from the current state. Use this the first time fizz-sync runs on a project (or when adopting fizz-sync on a project that was fuzzed before the snapshot format existed).
- `--only <Contract>` — scope the sync to a single contract name.
- `--apply` — actually perform the automatic fixes. Without `--apply`, fizz-sync runs in dry-run mode and only reports drift.
- `--no-property-quarantine` — skip the property quarantine phase (useful if the user wants to handle stale properties manually).

The default (no flags) runs a dry-run drift report.

## Preconditions

- The project must have been processed by the `fizz` skill at least once. Look for:
  - `{PROJECT_ROOT}/{META_DIR}/contracts.json`
  - `{PROJECT_ROOT}/{META_DIR}/entry-point-selection.json`
  - `{PROJECT_ROOT}/{SUITE_DIR}/` (suite directory)
- If any of the above are missing, stop and tell the user to run `fizz` first.

---

## STEP 0: REBUILD CURRENT ABIS

The snapshot diff compares against `contracts.json` and `entry-point-selection.json`. Those files reflect the state from the last `fizz` run, NOT the current source tree. You must refresh them first.

Run sequentially:

1. `cd {PROJECT_ROOT} && forge build --skip 'test/**/*.sol'`

   The `--skip` flag is critical: if the user's source change broke downstream call sites in `test/`, a plain `forge build` will fail on the harness code — which is exactly the drift fizz-sync is supposed to fix. Skipping `test/` means we only validate that the SOURCE compiles cleanly, which is all we need to refresh the ABI.

   If the build still fails with `--skip 'test/**/*.sol'`, the source itself has a compile error. Stop and report it. Fuzz-sync cannot proceed without valid source artifacts.

2. `node {SKILL_PATH}/../../scripts/extract_abis.js {PROJECT_ROOT} --meta-dir {META_DIR}`

   This refreshes `contracts.json` from the latest artifacts. It overwrites the old file in place.

3. **Do NOT re-run `select_functions.js` automatically.** The existing `entry-point-selection.json` encodes the user's prior tier assignments and selection choices. fizz-sync treats it as the source of truth for what's "in scope" and diffs only within that scope.

   If new contracts have been added that the user probably wants to fuzz, the drift report will surface them and the user can manually add them to `entry-point-selection.json` and re-run fizz-sync.

---

## STEP 1: HANDLE --init

If the user passed `--init`:

1. Run:

   ```
   node {SKILL_PATH}/../../scripts/fizz_sync.js {PROJECT_ROOT} --init
   ```

2. If the script reports the snapshot already exists, ask the user whether they want to overwrite with `--force` (they usually do NOT — it would erase drift history).

3. Report the number of contracts and properties captured, then stop. No further steps.

---

## STEP 2: RUN THE DRIFT REPORT

Run:

```
node {SKILL_PATH}/../../scripts/fizz_sync.js {PROJECT_ROOT}
```

The script:
- Reads `{META_DIR}/last-run.json` (created by `--init` or by Step 11 of the main `fizz` skill).
- Builds a fresh snapshot from the current `entry-point-selection.json`, source file hashes, and `PROPERTIES.md`.
- Diffs them and writes `{META_DIR}/sync-report.json`.
- Prints a human-readable summary.
- Exits 0 if no drift, 1 if drift was detected.

If exit 0 and no drift, stop and tell the user the harness is already in sync.

Read the JSON report:

```
{PROJECT_ROOT}/{META_DIR}/sync-report.json
```

The JSON schema is:

```json
{
  "generatedAt": "...",
  "hasDrift": true,
  "contracts": {
    "added":          [{"name":"...", "sourcePath":"...", "functions":[{"signature":"...", "tier":"primary"}]}],
    "removed":        [{"name":"...", "handlerFile":"...Handler.sol"}],
    "changed":        [{"name":"...", "functionsAdded":[...], "functionsRemoved":[...], "functionsChanged":[{"oldSignature":"...","newSignature":"...","handlerMethodName":"..."}], "tierChanged":[...]}],
    "sourcesChanged": [{"name":"...", "sourcePath":"..."}]
  },
  "handlers": {
    "orphan":   [{"file":"...", "contract":"..."}],
    "modified": [{"file":"..."}],
    "missing":  [{"file":"..."}]
  },
  "properties": {
    "referencingRemoved": [{"file":"...", "reference":"lender_oldMethod", "reason":"..."}],
    "fromSnapshot":       [{"id":"GL-01", "checkbox":"x", "functionName":"property_..."}]
  }
}
```

Use this object as the canonical work list for the rest of the skill.

---

## STEP 3: DRY-RUN SUMMARY (ALWAYS)

Regardless of whether `--apply` was passed, print a concise summary to the user that mirrors the report:

```
fizz-sync drift report
──────────────────────
Added contracts:     N
Removed contracts:   N
Drifted contracts:   N  (M added / M removed / M changed functions)
Orphan handlers:     N
Stale properties:    N
Modified handlers:   N  (user-edited since last snapshot)
```

If fizz-sync was invoked WITHOUT `--apply`, stop here and tell the user:

> Dry-run complete. Re-run with `--apply` to regenerate handlers and quarantine stale properties, or handle items manually using the report at `{META_DIR}/sync-report.json`.

---

## STEP 4: APPLY — HANDLER REGENERATION

Only run this step if `--apply` was passed.

### 4a. Back up user-modified handlers

For every entry in `report.handlers.modified`, the user has hand-edited that handler since the last snapshot. Regenerating it would destroy their clamping logic. The script already backs up `<file>.pre-sync.bak`, but the user should be warned.

Print a warning listing every modified handler and ask the user whether to proceed. If the user says no, skip to Step 5.

### 4b. Regenerate drifted handlers

Run:

```
node {SKILL_PATH}/../../scripts/fizz_sync.js {PROJECT_ROOT} --apply-handlers
```

The script:
- Regenerates handler files for contracts listed in `report.contracts.added` and `report.contracts.changed`.
- Creates `<name>Handler.sol.pre-sync.bak` backups next to each regenerated file.
- Uses the existing `generate_handlers.js` under the hood with a scoped selection file, so tier assignments are respected.

After the script runs, for each regenerated handler:

1. Read the `.pre-sync.bak` version and the new version.
2. Port any still-valid clamping bodies and ghost wiring from the backup into the new handler. Functions whose signature did not change can usually be copied verbatim. Functions whose signature changed must be manually rewritten against the new signature.
3. Keep `/// @notice SP-NN:` doctags intact — they are how `fizz-convert` and future `fizz-sync` runs identify which Solidity corresponds to which Spec ID.
4. For functions that were REMOVED from the source contract, delete the corresponding handler method from the regenerated file AND delete any call sites elsewhere.

### 4c. Handle orphan handlers

For every entry in `report.handlers.orphan`, the contract no longer exists in the selection. Offer the user two choices:

1. **Delete** — remove the handler file entirely and remove its inheritance line from `handlers/Handlers.sol`. Also remove any `contract_handler` field wiring.
2. **Quarantine** — leave the file in place but rename it `<name>Handler.sol.orphan` so `generate_suite.js` does not re-pick it up, and comment out its inheritance line in `Handlers.sol` with a `// FUZZ-SYNC: orphan — contract removed` marker.

Default to quarantine. Only delete if the user explicitly confirms.

### 4d. Handle missing handlers

For every entry in `report.handlers.missing`, the file disappeared since the last snapshot. If the contract still exists in `contracts.changed` / unchanged, treat this as a regeneration case — re-run the generate step without `--only` scoping (or manually invoke `generate_handlers.js`) to recreate it.

---

## STEP 5: APPLY — PROPERTY QUARANTINE

Skip if `--no-property-quarantine` was passed.

This is the most delicate phase. A property can be stale for several reasons:
- Its tagged handler function was renamed or removed (detected in `report.properties.referencingRemoved`).
- A ghost variable it depends on was deleted.
- The source function it asserts against changed semantics without changing signature (`report.contracts.sourcesChanged`).
- It no longer compiles at all.

### 5a. Compile-first triage

Run the scoped build that skips non-harness test files:

```
cd {PROJECT_ROOT} && FOUNDRY_PROFILE=fuzz forge build $(find test -maxdepth 1 -name '*.sol' -exec echo --skip {} \;)
```

(fall back to plain `forge build ...` without `FOUNDRY_PROFILE=fuzz` if no `fuzz` profile is configured).

The `find ... --skip` wrapper is essential: without it, compile errors in the user's own top-level test files (e.g. `test/MyContract.t.sol`, which is outside the fuzzing harness and NOT managed by this skill) would block the build and prevent fizz-sync from running its quarantine logic. Those top-level test files are the user's responsibility to fix; this skill only owns `{SUITE_DIR}/`.

If the build FAILS, parse every error. For each error whose location is inside `{SUITE_DIR}/`:

1. Identify the enclosing function (walk up from the error line until you hit a `function <name>(` header).
2. Check whether that function has a `/// @notice (GL-NN|SP-NN):` doctag — if yes, the Spec ID is the source of truth for reconciliation.
3. Quarantine the function:
   - Replace the entire function body with a single `revert("FUZZ-SYNC: quarantined");` statement.
   - Move the old body into a multi-line comment (`/* ... */`) directly above the function so the user can see the original logic and restore it manually when ready.
   - Add a single-line annotation above the comment:
     ```solidity
     // FUZZ-SYNC: quarantined — <short reason from build error>. Restore by deleting the revert body and uncommenting the block above.
     ```
   - `if (false) { ... }` is NOT a valid quarantine strategy — Solidity type-checks dead branches and the original compile error will persist.
4. If the function had a Spec ID, flip its checkbox in `PROPERTIES.md` from `[x]` to `[~]` and append ` (stale — source changed, re-opened)` to the description.
5. Rebuild. Repeat up to 3 cycles. If errors persist after 3 cycles, stop and report the remaining errors to the user — they need manual help.

**Important**: do NOT quarantine handler methods this way. If a handler method fails to compile, the fix belongs in Step 4b (handler regeneration) or 4c (orphan handling), not here.

### 5b. Semantic-drift sweep

After the compile triage passes, scan `report.properties.referencingRemoved`. For each entry:

1. Find the enclosing tagged function in the named file.
2. Read the whole function body.
3. If the dead reference is the ONLY purpose of the property (e.g., the property exists solely to check a post-condition of a now-removed handler call), quarantine it per the same procedure as 5a.
4. If the dead reference is incidental (e.g., the property also checks other state), leave it alone but add a `// FUZZ-SYNC: references removed method <name>` marker at the reference site. Rely on the compile triage to catch it on the next cycle if it actually breaks.

### 5c. Source-hash-only drift

For every entry in `report.contracts.sourcesChanged` that did NOT appear in `contracts.changed` (i.e., the source file changed but the ABI did not):

- This is a semantic refactor. Properties still compile but might assert the wrong thing.
- Do NOT auto-quarantine. Instead, list the affected contracts under a "Review recommended" section in the final report so the user can eyeball the properties tied to those contracts.

---

## STEP 6: REBUILD AND VALIDATE

Run:

```
cd {PROJECT_ROOT} && FOUNDRY_PROFILE=fuzz forge build $(find test -maxdepth 1 -name '*.sol' -exec echo --skip {} \;)
```

(fall back to `forge build ...` without the profile variable if no `fuzz` profile is configured).

If it fails, go back to Step 5a for one more cycle. If it has already been through 3 cycles, stop and report.

If it succeeds, proceed to snapshot refresh.

---

## STEP 7: REFRESH SNAPSHOT

Only after Step 6 succeeds and the user is happy with the result:

```
node {SKILL_PATH}/../../scripts/fizz_sync.js {PROJECT_ROOT} --refresh-snapshot
```

This overwrites `{META_DIR}/last-run.json` with the post-sync state. Future `fizz-sync` runs will diff against this new baseline.

---

## STEP 8: REPORT

Print a concise summary:

```
fizz-sync results
─────────────────

Handlers regenerated:
  VaultHandler.sol          (3 added, 1 removed, 1 signature changed)
  LendingPoolHandler.sol    (2 added)

Handlers ported from backup:
  VaultHandler.sol          (5/6 clamping bodies preserved)

Orphan handlers:
  OldStakingHandler.sol     quarantined (renamed .orphan)

Properties quarantined:
  SP-04  referenced removed function lender_oldDeposit
  SP-07  build error on line 128

Properties untouched (review recommended):
  GL-02  source hash changed but ABI stable — verify semantic intent
  GL-09  idem

Build: PASS
Snapshot refreshed: {META_DIR}/last-run.json
```

### Next actions

Tell the user:

- For newly added functions without handler bodies: re-run `fizz` Step 7 for just those contracts, or use the `fizz-convert` skill if the user also wants to regenerate properties for them.
- For quarantined properties: either rewrite them manually (flip `[~]` back to `[ ]` in `PROPERTIES.md` and run `/fizz-convert`), or leave them quarantined.
- For source-changed contracts without ABI drift: read the diff manually to confirm existing properties still encode the intended semantics.

---

## RULES

- Never run a full Fizz pipeline as part of a sync. Sync is surgical by design.
- Never regenerate ALL handlers — only the drifted subset.
- Never auto-delete orphan handlers without user confirmation.
- Never flip a `[ ]` or `[-]` checkbox to `[x]` in this skill. Only `[x] → [~]` for quarantining is allowed.
- Always back up files before destructive edits. The `.pre-sync.bak` files are the user's safety net.
- Always refresh the snapshot at the end of a successful `--apply` run, and NEVER refresh it mid-run before Step 6 passes — that would bake in the broken state.
