---
name: x-ray
description: "Generates an x-ray.md pre-audit report covering overview, enhanced threat model (protocol-type profiling, git-weighted attack surfaces, temporal risk analysis, composability dependency mapping), invariants, integrations, docs quality, test analysis, and developer/git history. Triggers on 'x-ray', 'audit readiness', 'readiness report', 'pre-audit report', 'prep this protocol', 'protocol prep', 'summarize this protocol'."
---

# X-Ray

Generate an `x-ray/` folder at the project root containing all output files. Pipeline: 3 steps, always sequential.

`$SKILL_DIR` = the directory containing this SKILL.md file. Resolve it from the path you loaded this skill from (e.g. if this file is at `/path/to/x-ray/SKILL.md`, then `$SKILL_DIR` = `/path/to/x-ray`).

## Progress tracking (MANDATORY)

Before doing anything else, call TodoWrite with these 3 todos (all `pending`):

1. `Phase 1: Enumerate & measure codebase`
2. `Phase 2: Read sources, classify entry points, synthesize invariants`
3. `Phase 3: Write x-ray report files`

Transitions (update via TodoWrite — never batch):
- Mark Phase 1 `in_progress` immediately, before running `enumerate.sh`.
- When Step 1's parallel batch returns, in ONE TodoWrite call mark Phase 1 `completed` and Phase 2 `in_progress`.
- When Step 2 (including 2b–2g) finishes, in ONE TodoWrite call mark Phase 2 `completed` and Phase 3 `in_progress`.
- After all Step 3 output files are written, mark Phase 3 `completed`.

Rule: exactly one todo is `in_progress` at any time. Status updates happen the moment a phase starts or ends.

## Step 1: Enumerate & Measure

If the user specifies a path, use it as project root. Otherwise use cwd. If no `.sol` files or `foundry.toml`/`hardhat.config.*` at root, check one level deep.

**Source directory detection**: Auto-detect from `foundry.toml` (`src = "..."`) or `hardhat.config.*`. If no config, try both `src/` and `contracts/`. Read `foundry.toml` first if present.

**Run enumeration** (single Bash call — includes output directory creation):
```bash
mkdir -p [project-root]/x-ray && bash $SKILL_DIR/scripts/enumerate.sh [project-root] [src-dir]
```

**Immediately after**, launch ALL of the following in a single message (parallel):

**0. Version check** (foreground):
- Read the local `VERSION` file from `$SKILL_DIR/VERSION`
- Bash `curl -sf https://raw.githubusercontent.com/pashov/skills/main/x-ray/VERSION`
- If the remote VERSION fetch succeeds and differs from local, print `⚠️ You are not using the latest version. Please upgrade for best security coverage. See https://github.com/pashov/skills`. If it fails, skip silently.

**1. Coverage** (`run_in_background: true`):

For Foundry:
```bash
cd [project-root] && forge coverage 2>&1 || (echo "RETRYING_WITH_IR_MINIMUM" && forge coverage --ir-minimum 2>&1)
```

For Hardhat:
```bash
cd [project-root] && npx hardhat coverage 2>&1
```

If toolchain is not installed (e.g., `forge: command not found`, `npx: command not found`, missing `node_modules/`), the coverage command will fail. This is expected — test *existence* is already captured by enumeration in the step above. Coverage failure does NOT mean tests are absent.

**2. Git security analysis + JSON read** (foreground, single Bash call):
```bash
cd [project-root] && python3 $SKILL_DIR/scripts/analyze_git_security.py --repo . --src-dir [src-dir] --json x-ray/git-security-analysis.json 2>&1 && cat x-ray/git-security-analysis.json
```

The JSON has 7 sections: `repo_shape`, `fix_candidates`, `dangerous_area_changes`, `late_changes`, `forked_deps`, `tech_debt`, `dev_patterns`.

**3. Preload reference files** (2 parallel Read calls — these must be in context before Step 2d/3a):
- `$SKILL_DIR/references/threats.md` — threat profiles, temporal threats, composability threats
- `$SKILL_DIR/references/templates.md` — output template, entry points template, architecture guide

**4. Spec/whitepaper detection** (1 Glob: `**/{whitepaper,spec,design,protocol,architecture,overview,README}*.{pdf,md}` excluding `node_modules/`, `lib/`, `x-ray/`, `test/`). Skip user-facing docs (tutorials, API refs, changelogs, contribution guides). Then apply size-aware handling:

- **Path A (≤5 docs, each ≤300 lines):** Include them as Read calls in Step 2's parallel message. Direct reads — no subagent needed.
- **Path B (>5 docs OR any doc >300 lines):** Launch a single subagent (`model: "sonnet"`) that reads ALL doc files and returns a structured extraction (max 200 lines). Subagent prompt:
  ```
  Read each doc file listed below. Extract ONLY security-relevant information into this format:
  Files: [list of doc file paths]

  Return this exact structure:
  ### Doc-Stated Global Invariants
  [Bullet list of every invariant, constraint, or guarantee the docs claim must hold globally across calls. Treated like NatSpec-stated invariants by Step 2g — routed directly to §2 / §3 / §4 of invariants.md by shape, NOT into §1 (Enforced Guards, which is per-call preconditions only).]
  ### Actor Definitions
  [Each actor/role with stated permissions and trust level]
  ### Trust Assumptions
  [What the protocol assumes about external systems, oracles, admins, users]
  ### Cross-System Flows
  [How value/data moves between contracts or external systems]
  ### Economic Properties
  [Fee structures, reward mechanisms, tokenomics, bounded parameters]
  ### Key Design Decisions
  [Explicit "we chose X over Y because Z" statements]

  Rules: Quote the source doc for each claim. Omit sections with no relevant content. Max 200 lines total.
  ```
  Include this subagent in Step 1's parallel message. Its output feeds Step 3 report writing.

For both paths, extract only: doc-stated global invariants, actor definitions, cross-system flows, trust assumptions, economic properties, key design decisions. Tag all spec-derived claims in the report with `(per spec)` so auditors know what is code-verified vs spec-stated. Doc-stated global invariants feed Step 2g's NatSpec routing step — they route to §2 / §3 / §4 of `invariants.md` by shape, NOT to §1 (Enforced Guards).

ALL calls (coverage, git analysis, reference reads, spec glob) MUST appear in the same message. Proceed to Step 2 without waiting for forge coverage.

## Step 2: Read Source Files + Entry Point Scan (SINGLE message, ALL tool calls parallel)

CRITICAL: Every tool call — Bash, Agent, Read, Grep — MUST be issued in ONE message so they run concurrently. This includes source file reads, the entry point grep scan, and any spec doc detected in Step 1 (they are all independent).

### Scope Filtering
- Skip interfaces: `interfaces/` dirs or filenames `I` + uppercase letter
- Skip vendored libs: Uniswap FullMath/TickMath, OZ copies
- When uncertain, include it but exclude from scope table

### Path A: ≤20 source files (direct reads)
One Read call per file. Do NOT read README, docs, or foundry.toml (already read in Step 1).

**Extract per file:** contract type & inheritance, roles & access control, value-holding state vars, external calls, fund flows, invariant comments, assert/require, backwards-compatibility indicators (see below), **delta writes** (per function: storage variables and the symbolic delta applied — e.g. `Δ(totalSupply) = +shares, Δ(balanceOf[msg.sender]) = +shares` — same-basic-block only, no cross-function inference; inherited helpers like OZ `_mint`/`_burn` may be resolved only when their effect on `balanceOf`/`_totalSupply` is semantically unambiguous), **guard predicates** (every `require`/`assert`/`if-revert` that references a storage variable, quoted verbatim with line number; skip guards that reference only function parameters), **enum/one-shot transitions** (every `require(state == X); ...; state = Y` pair, recorded as `X@Lx → Y@Ly` — include one-shot latches like `require(addr == address(0)); addr = concrete`).

### Path B: >20 source files (parallel subagents)

**Tier 1 — Small files (≤120 lines):** Batch into single Bash `cat` call.

**Tier 2 — Large files (>120 lines):** Group by subsystem. Launch **one subagent per subsystem** (`model: "sonnet"`, up to 5, max ~10 files each). Subagent prompt:
```
Read each file listed below and return a structured summary. Do NOT analyze — just extract facts.
Files: [list of file paths]
For EACH file, return this exact format:
### [filename]
- **Type**: contract | library | abstract
- **Inherits**: [parent contracts]
- **Imports**: [imported libraries/contracts]
- **Roles/Access**: [onlyOwner, role constants, modifiers]
- **State vars (value-holding)**: [mappings/vars that hold balances, collateral, etc.]
- **External calls**: [calls to other contracts, ERC20 transfers, etc.]
- **Fund flows**: [deposit/withdraw/mint/burn/transfer paths]
- **Invariants**: [require/assert statements, NatSpec invariant comments]
- **Delta writes**: For EACH non-view non-pure function, list storage variables that change and the symbolic delta applied. Use format `Δ(var) = +expr` or `Δ(var) = -expr`. Only report pairs where BOTH writes appear in the same function body with no intervening call to an unknown external contract. Do NOT chase writes through inherited/imported functions unless the semantic effect is unambiguous (OZ `_mint` → `balanceOf` + `_totalSupply` is fine; custom internal helpers are NOT — list those deltas only in the internal helper's own entry). Example:
  - `deposit()`: `Δ(totalSupply) = +shares`, `Δ(balanceOf[msg.sender]) = +shares`
  - `borrow()`: `Δ(totalBorrows) = +amount`, `Δ(underlyingBalance) = -amount`
- **Guard predicates**: Every `require`/`assert`/`if-revert` in the file that references a storage variable. Quote verbatim with line number. Skip guards that reference only function parameters.
  - `Vault.sol:206`: `require(_fee <= 10, "fee is capped at 0.1%")`
- **Enum/one-shot transitions**: Every pattern of `require(var == X); ...; var = Y` where `var` is a storage enum, uint, or address. Record as `X@Lx → Y@Ly`. Include one-shot latches like `require(addr == address(0)); addr = concrete`.
- **Key logic**: [1-2 sentences on what the contract does]
- **Function-level access map** (REQUIRED for contracts, skip for libraries):
  List every public/external non-view non-pure function with its access control:
  - `functionName()` — [modifier name, e.g. `onlyRole(OCT_KEEPER)`] or [NONE — permissionless]
  For functions with NO modifier, also list which external calls they make:
  - `functionName()` — NONE — calls `ContractName.method()`
```

### Entry Point Grep Scan (INCLUDED in the same parallel message as source reads)

Launch these two **Bash** calls in the SAME message as the source file reads above — they are independent and can run concurrently. Commands use **only POSIX ERE + POSIX character classes** (no `-P` / PCRE, no GNU-only escapes like `\s` `\w` `\b`), so they work identically on GNU grep (Linux/WSL), BSD grep (macOS default `/usr/bin/grep`, FreeBSD), and ripgrep:

```bash
# 1. Single-line signatures: function name and visibility on same line
grep -rnE 'function[[:space:]]+[[:alnum:]_]+[[:space:]]*\([^)]*\)[[:space:]]+(external|public)' [src-dir]/ --include='*.sol' \
  | grep -v '/interfaces/' | grep -v '/mock/' \
  | grep -Ev '(^|[^[:alnum:]_])(view|pure)([^[:alnum:]_]|$)'
```

```bash
# 2. Multiline signatures: visibility keyword on the closing-paren line (covers 90%+ of multiline cases)
grep -rnE '^[[:space:]]*\)[[:space:]]+(external|public)' [src-dir]/ --include='*.sol' -B5 \
  | grep -v '/interfaces/' | grep -v '/mock/' \
  | grep -Ev '(^|[^[:alnum:]_])(view|pure)([^[:alnum:]_]|$)'
```
Combine results from both. The multiline grep is critical — Solidity functions often split parameters across lines, putting `external`/`public` on the `)` line while `function name(` is lines above. The trailing `grep -Ev '(^|[^[:alnum:]_])(view|pure)([^[:alnum:]_]|$)'` is the POSIX-portable substitute for `\b(view|pure)\b`: it drops any line where `view` or `pure` appears as a standalone identifier (surrounded by non-identifier chars or line boundaries), while preserving lines that merely contain `view_param` / `pure_x` identifier substrings.

**Portability guarantees:**
- `-E`, `-v`, `-r`, `-n`, `-B` → POSIX (2001+) / supported by macOS, FreeBSD, Linux GNU grep, busybox grep, ripgrep
- `[[:space:]]`, `[[:alnum:]_]` → POSIX character classes, supported by all above
- `--include='*.sol'` → GNU + macOS BSD grep + ripgrep. Not supported by busybox grep (niche; Alpine minimal); if the skill ever needs to run there, replace `--include='*.sol' [src]/` with `$(find [src]/ -name '*.sol')` passed as arguments.

ALL tool calls (source reads/Bash/subagents, BOTH grep scans) MUST be in ONE message.

Do NOT read test files or documentation files.

### Step 2b: Entry Point Classification

Using the grep results already returned from Step 2's parallel message, classify ALL entry points. Do NOT rely solely on subagent summaries — subagents extract facts at the contract level and can misattribute which function makes which external call or which function has which modifier.

**Exclude** from entry points: view/pure functions, interface-only declarations, library internal functions (they're downstream calls, not entry points), mock contracts.

**For each result, classify into one of three categories:**

1. **Permissionless** — no access-control modifier AND no internal caller restriction in the function body. You MUST verify the function body before classifying as permissionless. For **Path A (≤20 files)**, the bodies are already in context from Step 2 reads — classify directly without additional Read calls. For **Path B**, batch all candidate body reads into a SINGLE parallel message. Look for ANY of these patterns that restrict the caller:
   - `require(msg.sender == X)` or `if (msg.sender != X) revert ...`
   - `if (msg.sender != X || ...) revert ...` (compound conditions)
   - Calls to internal functions that check `msg.sender`
   A function without a modifier but WITH an internal `msg.sender` check is **role-gated**, not permissionless. Common examples: `acceptOwnership()`, `acceptMsig()`, `confirmX()` — these often have no modifier but restrict the caller to a specific pending address via `if (msg.sender != pendingX) revert`.
2. **Role-gated** — has a role modifier (`onlyRole(X)`, `onlyOwner`, `onlyRouter`, etc.) OR an internal `msg.sender` restriction (via `require`, `if/revert`, or delegated check). Record which role or address is required.
3. **Admin-only** — gated by `DEFAULT_ADMIN_ROLE`, `onlyOwner` pointing to the protocol admin, or similar top-level authority.

Note: `nonReentrant` alone is NOT access control. `initializer`/`reinitializer` are one-time deployment functions — track separately.

**For each entry point, record:**
- Contract name and function name
- Access level (permissionless / role name / admin)
- Caller (User, Keeper, Admin, LP, etc.)
- Parameters with trust level: `(user-controlled)`, `(user-signed)`, `(keeper-provided)`, `(protocol-derived)`
- Call chain: trace downstream calls using subagent summaries + function-level access maps. Format: `→ Contract.fn() → Contract.fn()`
- State modified: which storage vars/mappings change
- Value flow: `in` (tokens deposited), `out` (tokens withdrawn), `none`
- Reentrancy guard: yes/no

This data feeds TWO outputs:
- The **permissionless entry points** list in `x-ray.md` (Section 2) — use the permissionless subset only
- The full **entry-points.md** file (Step 3c) — uses all categories

### Step 2b-flow: Protocol Flow Path Construction

Using the entry point data already collected in Step 2b, construct flow paths for entry-points.md. This is NOT a separate analysis pass — it reorganizes data you already have.

**For each major user-facing entry point** (permissionless and role-gated functions that move value):
1. Identify its `require` statements and state variable checks
2. For each check, find which function WRITES that state variable (already known from the "State modified" field of other entry points)
3. Chain these backwards: destination ← writer of its precondition ← writer of THAT precondition ← ... ← deployment
4. Note non-function preconditions (time passage, market conditions, external state) with `◄──` annotations

**Output**: Simple arrow chains grouped by actor flow. Reference earlier flows instead of repeating. 15-30 lines total. See the Protocol Flow Paths section in the entry-points.md template for exact format.

The grep scan is a **hard gate**: the permissionless entry points section in the report must match this grep-verified list, not the subagent summaries. If there is a conflict, the grep + code reading result wins.

### Step 2c: Backwards-Compatibility Code Detection

While reading source files, watch for code that appears to be remnants of a removed mechanism kept so the remaining codebase does not break. Common signals: empty or trivial function bodies, state variables declared but never meaningfully read or written, comments containing "deprecated" / "legacy" / "backwards compat" / "no longer used", functions that implement an interface but always return a default, and storage variables preserved solely for proxy storage layout compatibility.

After reading ALL source files, cross-reference candidates against these **mandatory verification checks** before classifying anything as backwards-compatibility. **Batch ALL caller-check Grep calls for all candidates into a SINGLE parallel message** — do not verify them one-by-one:

1. **Caller check (REQUIRED)**: Use Grep to confirm the function/variable has NO active callers in the current codebase. If it IS called from active code paths, it is NOT backwards-compatibility — it is the current design, regardless of whether it returns defaults or zeros.
2. **NatSpec/comment check (REQUIRED)**: If the code has NatSpec or inline comments explaining WHY it behaves a certain way (e.g., "simplified for X mode", "by design", "intentionally zero"), this is documented intentional design, NOT backwards-compatibility code. Do not override explicit developer documentation with heuristic pattern matching.
3. **Interface obligation check**: A function that returns default values but exists because an interface requires it AND is actively called is part of the current architecture, not a remnant.

Only classify code as backwards-compatibility when ALL of: (a) no active callers exist, (b) no NatSpec/comments document the behavior as intentional, and (c) git history shows the mechanism it belonged to was removed.

Do not describe backwards-compatibility code as active features in the report. Instead, note them explicitly in Section 1 (see output template) so auditors know which parts of the codebase are retained for compatibility rather than being live functionality. If no backwards-compatibility code survives the verification checks above, omit the subsection entirely.

### Step 2d: Centralization & Pause Coverage Analysis

After reading source files and classifying entry points, perform two analyses that feed into the Actors table, Trust Boundaries, and Key Attack Surfaces (Section 2). These are NOT standalone sections — the results integrate into existing report sections.

**Centralization analysis** — For each privileged role (admin, owner, operator, keeper, service, etc.):
1. List every operational action the role can take (from the function-level access map)
2. For each action, note whether a timelock, multi-sig, or delay exists. Distinguish between role *transfer* delays (e.g., `AccessControlDefaultAdminRules` 1-day delay) and operational *action* delays — they are not the same. A role transfer delay does NOT protect against a compromised holder using instant operational functions.
3. Identify which actions can extract or redirect user funds (e.g., `emergencyWithdraw`, `setTreasury`, `transferFee`)

Integrate into: **Actors table** (Capabilities column should be specific about what's instant vs timelocked), **Trust Boundaries** (describe what each boundary actually protects vs what bypasses it), **Key Attack Surfaces** (frame as "Admin operational powers" or "[Role] compromise" — the attack surface is the role compromise, not individual functions).

**Pause coverage analysis** — For each critical state-changing function:
1. Check whether `whenNotPaused` (or equivalent) is applied
2. Note which functions are pausable vs not
3. If a function that should logically be pausable is not (e.g., a function callable by a bounded role that operates on user funds), integrate this finding into the relevant attack surface for that role. The missing pause is not itself an attack surface — it's a detail that worsens the relevant role's compromise scenario.

**Anti-pattern: Do NOT create a standalone "Centralization Risks" subsection.** Centralization details belong distributed across Actors, Trust Boundaries, Key Attack Surfaces, and Protocol-Type Concerns. A dedicated section duplicates information already present in those sections. The same applies to pause coverage — integrate into the relevant role's attack surface description.

### Step 2e: Protocol Classification

After reading source, classify the protocol following the procedures in `references/threats.md` (type detection + hybrid classification, phase detection, and external call classification — all in one file).

### Step 2f: nSLOC

Use the exact nSLOC TOTAL from the Step 1 enumerate output (no `~` prefix) in the report header and scope table.

### Step 2g: Invariant Synthesis

Using the delta writes, guard predicates, enum/one-shot transitions, and invariant comments extracted in Step 2 (from direct reads in Path A, or subagent output in Path B), systematically walk the following taxonomy to produce invariant candidates. This is a reasoning pass — no new tool calls needed (except the Grep batch in step 2 Pass B — see below).

**Terminology**: A *guard* is a per-call precondition enforced at a single callsite (e.g., `require(amount >= MIN)`). It is NOT a falsifiable invariant — the code itself guarantees it at that callsite. An *invariant* is a property that must hold globally across any sequence of calls (e.g., "every active position ≥ MIN"). Guards feed §1 of `invariants.md` (Enforced Guards reference) only. Invariants that are *lifted* from guards (see step 2 below) or stated in NatSpec feed §2 / §3 / §4.

**NatSpec routing** (run before the structural walk): For each NatSpec `@invariant` tag or inline comment asserting a global property (e.g., *"totalSupply always equals Σ balances"*, *"fee never exceeds MAX_BP"*, *"only one active epoch at a time"*), route DIRECTLY to §2 (or §3/§4 if the property spans contracts or derives from multiple primitives) by category shape (Conservation / Bound / Ratio / StateMachine / Temporal). Source tag: `NatSpec: Contract.sol:LN`. Do NOT place developer-stated global invariants in §1 — §1 is per-call guard predicates only. After routing, still run the structural scans below — they may confirm (On-chain=Yes) or contradict (On-chain=No) the NatSpec claim.

**Walk order** (each step uses the raw extraction data, not prior-step conclusions):

1. **Conservation scan**: For each function, find delta-write pairs where `Δ(A) = +expr` and `Δ(B) = -expr` (or `Δ(B) = +expr` for a mapping counterpart) in the same function body. Each matched pair is a conservation candidate: `A + B = const` or `A == Σ B[key]`.
   - For mapping writes (`mapping[key] += e` paired with `scalar += e`), infer `scalar == Σ mapping[key]`. Verify the pattern holds across ALL functions that write to either variable — if ANY function writes to one without the other, note the gap as "partial conservation" and split into Yes/No rows.
   - For transfer patterns (`mapping[from] -= e`, `mapping[to] += e` with no scalar change), confirm the mapping sum is self-conserving.
   - **Negative conservation** (important): If a function that *ought* to track a flow (e.g., flashloan pull/push, receive/forward) has zero storage Δ, record this as a Conservation-negative finding. Absence of Δ is itself an invariant observation.

2. **Guard extraction and lift** (two passes over each `require`/`assert`/`if-revert`):

   **Pass A — Extract verbatim (Enforced Guards reference)**: Every `require`/`assert`/`if-revert` becomes a `G-N` row in §1 of `invariants.md`. Quote the predicate verbatim with source location. This is a mechanical dump of per-call preconditions — not falsifiable, not fuzzed. Skip guards that only reference function parameters with no storage tie-back AND have no global implication (pure local input validation with no audit value beyond Pass B).

   **Pass B — Lift to global property, then check all write sites**: For each guard, ask: *"does this imply a property that must hold across any sequence of calls, not just at this callsite?"*
   - If **NO** (the guard only constrains a transient parameter that is consumed by the function and does not tie to persistent storage) → leave in §1 only. Do not promote.
   - If **YES** (the guard implies a persistent property — e.g., `require(amount >= MIN)` at deposit implies "every active position ≥ MIN"; `require(_fee <= 10)` at setter implies "fee ∈ [0, 10]") → rewrite the guard as a global property, then locate ALL write sites of the constrained storage variable using Grep on the variable name across scope files. Batch ALL write-site Greps for all lifted guards into a SINGLE parallel message — do not verify one at a time:
     - If **ALL write sites** enforce an equivalent guard → promote to §2 as a Bound invariant with On-chain=**Yes**. Derivation: cite the guard + confirm all write sites.
     - If **ANY write site** writes the variable without an equivalent guard → promote to §2 as a Bound invariant with On-chain=**No**, and cite the unguarded write site(s) as the gap. **This is the high-signal output** — the gap is simultaneously an invariant and a potential bug.

   Include setter-level bounds where a setter writes to a storage variable constrained by its own parameter check. Run the same all-write-site check — if multiple setters write the same variable but only some enforce the bound, the property is On-chain=No.

3. **Ratio scan**: For each storage write of form `A = B * C / D` where B, C, D are storage variables or function-scoped snapshots of storage, record the ratio. Note whether the snapshot is taken before or after other state changes in the same function (ordering matters — e.g., `totalSupply` snapshotted before `_burn` vs after).

4. **State machine / one-shot scan**: For each enum/uint/address variable in `require(var == X); ... var = Y` patterns, record the transition. Distinguish:
   - **One-shot latch**: `require(var == default); var = concrete` with no path back (e.g., `setStrategy`, `setLeverager`).
   - **Togglable flag**: `require(var == false); var = true` but another function flips it back (e.g., `freeze/unFreeze`, `toggleVaultLeverage`). NOT a state machine invariant — skip.
   - **Cyclic state**: `false → true → false` driven by timing/condition (e.g., `ongoingVestingPosition`). Record as a cycle invariant.

5. **Temporal scan**: For each `block.timestamp` or `block.number` comparison involving a storage variable (deadline, lastUpdate, lockPeriod, interval), extract the temporal constraint. Note whether the constraint is checked-then-updated (safe) or updated-then-checked (potential stale read).

6. **Cross-contract scan**: For each external call where the return value is used in arithmetic or a storage write, record what the caller assumes. Then find the callee's write sites for that state. If the callee can change it independently (via another function), the assumption is unvalidated — record as a cross-contract invariant with On-chain=No. ONLY include rows where BOTH sides (caller assumption + callee write sites) are inside the scope files. Do not speculate about out-of-scope contracts.
   - Also include: **setter-vs-invariant mismatches** — where an admin setter writes a storage value without checking that existing invariants still hold (e.g., `setReserveCapacity` without checking against current liquidity). These are cross-contract in the sense that the setter is one contract/function and the invariant is enforced elsewhere.

7. **Economic derivation**: After steps 1-6, check if any combination of single-contract + cross-contract invariants implies a higher-order property. Each economic invariant must cite the specific I-N / X-N IDs it derives from. If the derivation chain has a gap (one of the source invariants is On-chain=No), the economic invariant is also On-chain=No.

**Verification gate** (MANDATORY before including any inferred invariant):
- Conservation: confirm the Δ-pair exists at the cited lines (same function body).
- Guard (Pass A, §1 row): confirm the require/assert/if-revert is verbatim from code.
- Guard lift (Pass B, §2 row): confirm the lifted global property references persistent storage (not just a transient parameter restatement). Confirm all write sites of the constrained variable have been enumerated via Grep, and the On-chain=Yes/No verdict matches the enumeration — if any write site lacks the guard and the row says On-chain=Yes, the row is invalid.
- NatSpec: confirm the `@invariant` tag or comment exists verbatim at the cited location AND asserts a global property (not a per-call note). If it's a per-call note, drop — do not route to §2.
- Ratio: confirm the formula is exact and the snapshot ordering (before/after other writes in the same function) is noted.
- StateMachine: confirm both sides of the edge exist AND confirm no reverse path. If there IS a reverse path, it's a togglable flag — drop.
- Temporal: confirm the comparison involves a storage variable, not just block.timestamp vs parameters.
- Cross-contract: confirm both caller usage AND callee write site exist in scope.
- Economic: confirm all referenced I-N / X-N IDs are themselves verified.
- If you cannot verify → drop the row. "Could not verify" is not a valid row.

**Output**: Invariant candidates feed directly into `invariants.md` (Step 3a). x-ray.md Section 3 gets Enforced Guards (Reference) + top 3-5 inferred (prioritize On-chain=No from Conservation, Cross-Contract, and lifted-guard gaps; include one high-signal Yes row for structural coverage like a ratio or state-machine latch).

## Step 3: Write Output

### Test existence vs. coverage execution (CRITICAL)

**Test presence** is determined by Step 1 enumeration (`test_files`, `test_functions`, `stateless_fuzz`, `foundry_invariant`, `echidna`, `medusa`, `hardhat_fuzz`, `fork`, `certora`, `halmos`, `hevm` counts). These are file-scan results and are ALWAYS reliable regardless of whether the toolchain can compile or run. Multi-signal categories (`echidna`, `medusa`, `certora`, `halmos`) output as `functions:configs` — e.g., `5:1` means 5 test functions + 1 config file detected.

**Coverage metrics** (line/branch %) come from `forge coverage` or `hardhat coverage` which require installed dependencies, successful compilation, and passing tests. Coverage can fail for many reasons unrelated to test quality:
- Dependencies not installed (`npm install` / `forge install` not run)
- Compiler errors (stack-too-deep, version mismatch)
- Test execution failures (missing RPC, fork config)

**Rules:**
1. Use `test_files`/`test_functions` from Step 1 enumeration for ALL test existence claims. Never infer "no tests" from coverage tool failure.
2. If coverage fails but enumeration shows tests exist, report: `"[N] test files with [M] test functions detected; coverage metrics unavailable — [failure reason]"`.
3. In "Gaps" subsection, only flag missing test categories (stateless_fuzz=0, foundry_invariant=0, echidna=0, medusa=0, certora=0, halmos=0, hevm=0, fork=0), never flag "no tests" when enumeration shows they exist. Prioritize gaps by audit impact: missing stateful fuzz and formal verification for math-heavy/financial logic is higher priority than missing fork tests.
4. In git history "Security Observations", never claim "commits without tests" based on coverage failure. The `test_co_change_rate` from git analysis measures file co-modification in commits, not coverage — qualify it as such.
5. If coverage fails, do NOT let the failure cascade into threat model or risk assessments. Test presence (from enumeration) and coverage metrics (from tooling) are independent signals.

Check forge coverage status: include results if done, failure reason if failed, "pending" if still running. Do NOT wait.

### 3a. Write ALL output files (4 parallel Write calls in ONE message)

All output files go into the `x-ray/` directory. Write ALL FOUR files in a SINGLE message so they are created concurrently:

**1. x-ray/architecture.json** — Follow format and rules in the architecture guide section of `references/templates.md` (already loaded in Step 1).

**2. x-ray/x-ray.md** — Follow template in the output template section of `references/templates.md` (already loaded in Step 1). Under 500 lines. No fabrication. Section 3 (Invariants) is a **POINTER ONLY** to `invariants.md` — do NOT include a Guards table, do NOT list top inferred invariants. One blockquote callout with counts (guards / single-contract / cross-contract / economic) and a strong link to the invariants.md file is the entire §3. The invariant catalog lives exclusively in `invariants.md`; duplicating it in x-ray.md was old V2 behavior and is no longer correct.

**Key Attack Surfaces cross-link requirement**: When writing Section 2 Key Attack Surfaces, cross-reference each surface against the `invariants.md` blocks you just produced. If the surface's cited `file:line` falls within the `Location` / `Derivation` / `Caller side` / `Callee side` window of any G-N / I-N / X-N / E-N block, append the matching IDs as bracketed markdown links immediately after the surface title using LOWERCASE slug fragments: `- **Surface name** &nbsp;&#91;[X-4](invariants.md#x-4), [I-17](invariants.md#i-17)&#93; — ...`. Separate each surface bullet with a blank line. Surfaces that are purely access-control or upgrade-ability concerns may be left unlinked — that is a healthy signal, not a gap. Typical hit rate on non-trivial protocols: ≥70% of surfaces link to at least one invariant.

**3. x-ray/entry-points.md** — Using the full entry point data collected in Step 2b and the flow paths from Step 2b-flow, follow the entry points template section of `references/templates.md` (already loaded in Step 1). Start with the Protocol Flow Paths section (arrow chains showing prerequisite sequences for each major entry point), then the access-level detail sections. Factual only — no threat analysis (that stays in x-ray.md). If the protocol has >30 entry points, use compact tables for role-gated and admin sections instead of per-function detail blocks. Only permissionless entry points get the full detail block treatment regardless of count.

**4. x-ray/invariants.md** — Follow the invariant map template section of `references/templates.md` (already loaded in Step 1). Four sections: Enforced Guards (Reference), Inferred (Single-Contract), Inferred (Cross-Contract), Economic. **Use `#### G-N` / `#### I-N` / `#### X-N` / `#### E-N` heading blocks — NOT tables.** Heading anchors (slug `#g-1`, `#i-17`, …) are the target of cross-file markdown links from x-ray.md attack surfaces; inline `<a id>` anchors inside table cells do NOT work cross-file in VS Code. Each `G-N` block must include a `Purpose` line explaining what the guard protects (not just what it checks). Every inferred block MUST cite a concrete Δ-pair, guard-lift + write-sites, edge, temporal predicate, or NatSpec claim — drop blocks that cannot. Every cross-contract block must cite BOTH caller-side assumption AND callee-side write sites (both must be inside the scope files). Every economic block must derive from specific I-N / X-N IDs. No cap on block count. Factual only — no threat analysis.

**Writing Section 2 (Threat & Trust Model)** — Follow the structure in the output template. Use `references/threats.md` for threat profiles, temporal threats, and composability threats content (all in one file, already loaded in Step 1). For hybrids, merge: primary adversary list first, then unique secondary threats (de-duplicate overlapping ones).

**Verification rules** (apply during Section 2 writing):
- **Permissionless entry points**: Use only the grep-verified list from Step 2b. The Step 2b procedure is the source of truth — do not rely on subagent summaries.
- **Security claims**: Before writing any claim that a security check is missing, incomplete, or bypassable, you MUST trace the actual data flow by reading the relevant code. Specifically: (1) identify all write sites for the variable under question (use Grep), (2) confirm your claim holds against those write sites. Subagent summaries are not sufficient. If you cannot verify, qualify the claim with "could not confirm" rather than stating it as fact.

**Section 7 (Git History)**: Integrate `x-ray/git-security-analysis.json` into: Contributors, Review Signals, Hotspots, Security-Relevant Commits (score >= 5), Dangerous Area Evolution, Forked Dependencies, Tech Debt, Cross-Reference Synthesis (2-4 bullets connecting git signals to Sections 2-3).

### Branch scoping (CRITICAL)

The git analysis is scoped to the **current branch only** (HEAD). The `git_branch` field in the JSON meta tells you which branch was analyzed. All git signals (fix candidates, hotspots, dangerous areas, late changes) reflect ONLY commits reachable from HEAD — not other branches.

**Rules:**
1. State the analyzed branch in the report header or git history section: "Analyzed branch: `[branch]` at `[commit]`".
2. When describing fix commits or code changes from git history, always describe them as what the **current branch code** does — not what a fix "changed" if you cannot see the before/after on this branch.
3. Never describe code state from other branches. The source files you read in Step 2 are the current branch's files — git history describes how those files evolved on this branch only.
4. If the repo shape is `squashed_import` (1 commit), there is no meaningful evolution to describe — state this and skip fix/hotspot analysis.

### 3b. Generate & Validate Architecture SVG

```bash
python3 $SKILL_DIR/scripts/generate_svg.py x-ray/architecture.json x-ray/architecture.svg
```

Then follow the rendering, audit checklist, and fix loop in the architecture guide section of `references/templates.md`. Max 3 iterations. Cleanup temp files after (including `x-ray/git-security-analysis.json`).

### 3c. Terminal Verdict

After all files are written and cleanup is done, read the `## X-Ray Verdict` section from the generated `x-ray/x-ray.md` and print it verbatim to the terminal. Do NOT paraphrase, summarize, or rewrite — copy the exact tier, justification, and key observations as they appear in the file.

## Constraints

- Under 500 lines. Protect threat model, invariants, test gaps, git analysis, verdict — compress other sections if needed.
- No fabrication. Say "could not determine" when uncertain.
- Steps 1-3 fully autonomous. No user interaction required.
- Always group contracts by subsystem in scope table.
- Single pass. No partial outputs.
- Never reference audit platforms, contest rules, or bounty program framing — keep the report vendor-neutral.
- If git security analysis script fails, fall back to bash-only git stats. Never block on a missing script.

---

Before doing anything else, print this exactly:

```
██████╗  █████╗ ███████╗██╗  ██╗ ██████╗ ██╗   ██╗     ███████╗██╗  ██╗██╗██╗     ██╗     ███████╗
██╔══██╗██╔══██╗██╔════╝██║  ██║██╔═══██╗██║   ██║     ██╔════╝██║ ██╔╝██║██║     ██║     ██╔════╝
██████╔╝███████║███████╗███████║██║   ██║██║   ██║     ███████╗█████╔╝ ██║██║     ██║     ███████╗
██╔═══╝ ██╔══██║╚════██║██╔══██║██║   ██║╚██╗ ██╔╝     ╚════██║██╔═██╗ ██║██║     ██║     ╚════██║
██║     ██║  ██║███████║██║  ██║╚██████╔╝ ╚████╔╝      ███████║██║  ██╗██║███████╗███████╗███████║
╚═╝     ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝ ╚═════╝   ╚═══╝       ╚══════╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝╚══════╝
```
