# Output Template

Write `x-ray.md` using this exact structure. Every line should tell an auditor something useful — write for someone who has 5 minutes to decide where to look first.

```markdown
# X-Ray Report

> [Protocol Name] | [total in-scope nSLOC] nSLOC | [short-hash] (`[branch]`) | [framework] | [DD/MM/YY]

---

## 1. Protocol Overview

**What it does:** [One sentence — the core mechanism.]

- **Users**: [Who interacts and why]
- **Core flow**: [The main user-facing operation in one bullet]
- **Key mechanism**: [AMM type, vault model, oracle design, etc.]
- **Token model**: [What tokens exist and their roles]
- **Admin model**: [Who controls what — owner, multisig, governance]

[No paragraphs. No fluff. Keep vendor-neutral — no audit platform or bounty program framing.]

For a visual overview of the protocol's architecture, see the [architecture diagram](architecture.svg).

### Contracts in Scope

[Group by subsystem — one row per subsystem, not one row per file. List key contracts in the row.]

| Subsystem | Key Contracts | nSLOC | Role |
|-----------|--------------|------:|------|
| [Subsystem] | [Contract1, Contract2, ...] | [total] | [One-line role of this subsystem] |

[Only protocol-authored contracts and libraries. No interfaces, no vendored libs.]

### Backwards-Compatibility Code

[Include this subsection ONLY if backwards-compatibility remnants were identified in Step 2c. Omit entirely if none found.]

[Some protocols remove a mechanism but leave parts of it in the codebase so the remaining code does not break. List any such code here for clarity, so auditors know these are not active features.]

- `[contract:function/variable]` — [what it was part of, why it's retained, and that it is not active functionality]

[Keep entries short. The goal is clarity — preventing auditors from investigating dead code as if it were live.]

### How It Fits Together

[Start with "The core trick:" — one sentence explaining the protocol's fundamental mechanism.]

[Then show 3-5 key flows as annotated code-block diagrams. Each flow gets:]
[1. A ### subheading (no numbering — order is self-evident)]
[2. A code block showing the call chain with tree-style branching (├─ └─)]
[3. Italic annotations on critical steps (where state changes, where callbacks fire, where payment is verified)]
[Keep it to the 3-5 MOST IMPORTANT flows. Skip governance/admin/oracle flows — those are covered in Section 2. This section is about the core user-facing mechanics only.]

[IMPORTANT: Use concrete contract/library names in call chains, NOT interface names. Write `FuturesManager.addCollateral()`, not `ICollateralManager.addCollateral()`. Write `Vault.depositRequest()`, not `IVault.depositRequest()`. Interfaces are how the caller references the target in code, but the auditor needs to know which actual contract executes. The only exception is calls to genuinely external contracts (e.g. `IERC20.safeTransfer()` for a third-party token) where the concrete contract is outside the protocol's codebase.]

[Focus on flows that span multiple contracts — these are where integration bugs hide.]

[No inheritance lists. No import lists. Those details are in the scope table and the diagram. This section answers: "how does the system actually work, end to end?"]
[No bridge/transition sentences at end of section. No filler lines like "This is the flow an auditor traces..."]

---

## 2. Threat & Trust Model

### Protocol Threat Profile

> Protocol classified as: **[Primary type]** with **[Secondary type(s)]** characteristics

[1-2 sentences explaining why this classification, based on code signals detected. For hybrids, merge adversary lists: primary first, then unique secondary threats — de-duplicate overlapping ones.]

### Actors & Adversary Model

| Actor | Trust Level | Capabilities |
|-------|-------------|-------------|
| [Role] | [Trusted / Bounded (reason)] | [What they can do] |

[Only named roles from code. No "Anyone". Never use "Semi-trusted" — use "Bounded (reason)" instead.]

[CENTRALIZATION INTEGRATION: The Capabilities column must be specific about what is instant vs timelocked/delayed. If a role has a transfer delay (e.g., AccessControlDefaultAdminRules) but instant operational functions, state both — "1-day transfer delay, but all operational functions instant." If a role's functions are not subject to pausability, note it in the Trust Level or Capabilities column — e.g., "Bounded (can only complete CREATED swaps with constraints). Not subject to whenNotPaused — can operate during pause." This replaces any standalone "Centralization Risks" section — centralization details belong here, in Trust Boundaries, and in Key Attack Surfaces.]

**Adversary Ranking** (ordered by threat level for this protocol type, adjusted by git evidence):

1. **[Adversary type]** — [1 sentence: WHO they are and WHY they are relevant to this protocol type.]
2. **[Adversary type]** — [...]
3. [...]

[Include only adversary types relevant to this protocol. Typically 3-5. Keep each entry to ONE sentence — the adversary ranking identifies WHO threatens the protocol. The HOW and WHERE details belong in Key Attack Surfaces below. Do NOT describe attack mechanics or cite specific functions here.]

[Do NOT include a "Permissionless Entry Points" list here — that information lives in entry-points.md. Instead, reference: "See [entry-points.md](entry-points.md) for the full permissionless entry point map."]

### Trust Boundaries

[Where trust transitions happen. For each boundary: what's trusted, what damage if compromised, whether timelock/multisig exists.]
[For admin/privileged boundaries, distinguish what the delay mechanism actually protects. E.g., if AccessControlDefaultAdminRules protects role transfer but operational functions are instant, state: "1-day delay protects the admin seat itself, but all operational actions (emergencyWithdraw, setFee, etc.) execute instantly with no delay."]
[If git analysis shows trust boundary code was frequently modified or has fix-scored commits, note: "*Git signal: N modifications, M fix-scored commits — elevated risk.*"]

### Key Attack Surfaces

[This is the SINGLE authoritative location for attack surface details. Adversary Ranking above identifies WHO; this section describes WHERE and HOW. Do NOT repeat the same risk in both places.]

[Sorted by priority score (protocol-type relevance + git hotspot + fix history + late changes + dangerous area churn). NOT alphabetical.]
[These are suggestions for where to focus — brief pointers, not full attack writeups. The auditor decides severity and builds attack paths.]
[No RISK labels (HIGH/MEDIUM/LOW). No mitigation analysis. No git evidence per surface.]

- **[Surface name]** — [1-2 sentences: what makes this area interesting and which contracts/functions are involved]

[Repeat for each surface. Keep each entry to 1-3 lines max.]

[FRAMING RULE: Attack surfaces should be named after the root threat, not individual symptoms. E.g., "SERVICE_ROLE compromise" is an attack surface — missing pausability on completeSwap is a detail that makes that surface worse, not a separate surface. Similarly, "Admin operational powers without timelock" is a surface — individual functions like emergencyWithdraw and setFee are evidence within that surface. Frame surfaces as the actor/capability that is dangerous, then list the specific functions and gaps that make it dangerous within the description.]

### Upgrade Architecture Concerns

[Include if any upgradeable contracts exist (UUPS, transparent proxy, beacon). Concrete concerns tied to this codebase's upgrade patterns.]

- **[Concern]** — [1-2 sentences describing the specific risk and which contracts are affected]

[Typical concerns: uninitialized implementations, storage gap consistency, missing timelock on upgrades, blast radius of upgrading shared contracts, placeholder proxy windows.]

### Protocol-Type Concerns

[Based on the protocol classification from Section 2a. ONLY include concerns that are NOT already covered in Key Attack Surfaces above. This section adds protocol-type-specific technical details (math precision, curve invariants, share accounting, etc.) — not the same risks restated from a type perspective.]

**As a [Primary type]:**
- [Technical concern specific to this protocol-type — e.g., math precision at boundaries, curve invariant edge cases, share price rounding direction]

**As a [Secondary type]** *(if applicable)*:
- [Same format]

[2-3 bullets per type. If a concern is already an attack surface above, skip it here. No generic protocol-type advice — every bullet must cite a specific contract/function.]

### Temporal Risk Profile

[ONLY include phases that add NEW information not already in Actors, Attack Surfaces, or Upgrade Architecture. Skip any phase whose risks are already fully covered above. Typical: Deployment & Initialization adds value (empty-state, front-running init); Governance & Upgrade usually does NOT (already covered in Actors + Upgrade Architecture). 1-3 bullets per phase, each citing specific code locations.]

**Deployment & Initialization:**
- [Specific risk + code location + mitigation status]

**Market Stress** *(include only if adding new info beyond Attack Surfaces)*:
- [Specific risk + code location + mitigation status]

**Deprecation** *(include only if V2/migration evidence exists)*:
- [Specific risk + code location + mitigation status]

### Composability & Dependency Risks

**Dependency Risk Map:**

[Use blockquote format per dependency — one block each, easy to scan:]

> **[External Name]** — via `[contract:function]`
> - Assumes: [key assumptions about return value / behavior]
> - Validates: [what checks exist] or [NONE]
> - Mutability: [Immutable / Upgradeable by X / Governed by X]
> - On failure: [what happens — revert / fallback / fail-open]

[Repeat for each significant external dependency. Well-mitigated ones can be shorter.]

**Token Assumptions** *(unvalidated only)*:
- [Token type]: assumes [assumption not validated in code] — impact if violated: [consequence]

**Shared State Exposure** *(if applicable)*:
- [Which shared resources (pools, oracles), what other protocols share them, whether this protocol's actions could affect others]

[Do NOT add an "Integration Summary" table — the Dependency Risk Map blockquotes above already cover every external dependency. A summary table would duplicate them.]

---

## 3. Invariants

### Stated Invariants

[From comments, NatSpec, docs, assert/require. Quote with source location.]

### Inferred Invariants

- **[Short name]**: [Description]. Derived from `[contract:function]`. If violated: [consequence].

---

## 4. Documentation Quality

| Aspect | Status | Notes |
|--------|--------|-------|
| README | [Present/Missing] | [Filename/path if present] |
| NatSpec | [~N annotations] | [Coverage notes] |
| Spec/Whitepaper | [Present/Missing] | [Filename/path if present] |
| Inline Comments | [Sparse/Adequate/Thorough] | [Notable gaps] |

[Skip user-facing docs (tutorials, API refs, marketing). If a spec/whitepaper was ingested in Step 1, tag derived claims with `(per spec)` vs `(per code)` so auditors know what is code-verified vs spec-stated.]

---

## 5. Test Analysis

| Metric | Value | Source |
|--------|-------|--------|
| Test files | [N] | File scan (always reliable) |
| Test functions | [N] | File scan (always reliable) |
| Line coverage | [N% or "Pending" or "Unavailable — [reason]"] | Coverage tool (requires compilation) |
| Branch coverage | [N% or "Pending" or "Unavailable — [reason]"] | Coverage tool (requires compilation) |

[IMPORTANT: Test file/function counts come from file scanning and are always accurate. Coverage metrics require the toolchain to compile and run — if coverage fails (missing deps, compiler error, stack-too-deep), this does NOT mean tests are absent. State this clearly when coverage is unavailable.]

### Test Depth

| Category | Count | Contracts Covered |
|----------|-------|-------------------|
| Unit | [N] | [List or "broad"] |
| Integration | [N] | [List or "none"] |
| Fork | [N] | [List or "none"] |
| Stateless Fuzz | [N] | [List or "none"] |
| Stateful Fuzz (Foundry) | [N] | [List or "none"] |
| Stateful Fuzz (Echidna) | [N] | [List or "none"] |
| Stateful Fuzz (Medusa) | [N] | [List or "none"] |
| Formal Verification (Certora) | [N] | [List or "none"] |
| Formal Verification (Halmos) | [N] | [List or "none"] |
| Formal Verification (HEVM) | [N] | [List or "none"] |
| Scribble Annotations | [N] | [List or "none"] |

[Only include rows where the count > 0 or where the absence is notable. For categories with 0, consolidate into the Gaps section instead of showing empty rows. Always include Unit, Stateless Fuzz, Stateful Fuzz (at least one tool), and Formal Verification (at least one tool) — even if 0 — since their absence is audit-relevant. Omit Hardhat Fuzz row unless the package.json dependency was detected.]

[Enumeration output format for multi-signal categories: `echidna`, `medusa`, `certora`, `halmos`, `scribble` output as `functions:configs` (e.g., `5:1` = 5 functions + 1 config file). Report the function/spec count in the table. If configs exist but no functions, note: "[tool] config present but no test functions found".]

### Gaps

[Notable testing gaps. Only flag missing test categories — never claim "no tests" when enumeration found test files. Prioritize gaps by audit impact: missing stateful fuzz and formal verification for math-heavy/financial logic is higher priority than missing fork tests.]

---

## 6. Developer & Git History

> Repo shape: [normal_dev / squashed_import] — [one sentence: e.g., "All source arrived in 1 commit (9fb17ba); no development history visible" or "Normal development history with N source-touching commits over N months"]

### Contributors

| Author | Commits | Source Lines (+/-) | % of Source Changes |
|--------|--------:|--------------------|--------------------:|
| [Name] | [N]     | +[N] / -[N]       | [N%]                |

[Compute % from source line additions. Flag single-developer dominance (>90%), ghost contributors (1 commit), or uneven distribution.]

### Review & Process Signals

| Signal | Value | Assessment |
|--------|-------|------------|
| Unique contributors | [N] | [Single-dev / Small team / Larger team] |
| Merge commits | [N] of [total] ([%]) | [Formal review process / No merge commits — likely no peer review] |
| Repo age | [first] → [last] | [Duration] |
| Recent source activity (30d) | [N] commits | [Active / Quiet / Late burst before audit] |
| Test co-change rate | [N%] | [% of source-changing commits that also modify test files — measures co-modification, NOT coverage] |

### File Hotspots

| File | Modifications | Note |
|------|-------------:|------|
| [path] | [N] | [High churn — prioritize review] |

[Top 5-10 most-modified source files. High modification count correlates with higher defect density.]

### Security-Relevant Commits

[Include ONLY if fix_candidates from git security analysis has entries with score >= 5. For squashed-import repos, skip this subsection and note "No development history — fix detection not applicable."]

**Score** = weighted sum of fix-like signals in a commit: message keywords (fix, bug, reentrancy, overflow...), diff patterns (deletes code, changes `require`/`assert`, touches access control or accounting), and change shape (focused = higher). **10+ warrants a manual diff.**

| SHA | Date | Subject | Score | Key Signal |
|-----|------|---------|------:|------------|
| [hash] | [date] | [subject] | [N] | [top reason from scoring] |

### Dangerous Area Evolution

[Include if the repo has normal development history. Shows which security-sensitive code areas changed most.]

| Security Area | Commits | Key Files |
|--------------|--------:|-----------|
| [fund_flows / access_control / oracle_price / liquidation / signatures / state_machines] | [N] | [top 2-3 files] |

[Areas with high commit counts warrant deeper review — frequent changes to security-critical code correlate with higher defect density.]

### Forked Dependencies

[Include if forked_deps.detected_libs contains internalized libraries. Skip if all libs are standard submodules.]

| Library | Path | Upstream | Status | Notes |
|---------|------|----------|--------|-------|
| [name] | [lib/path] | [Uniswap V2 / OpenZeppelin / etc.] | [Submodule / Internalized] | [Pragma mismatch, modifications from upstream, etc.] |

[Internalized libraries with pragma or logic changes from upstream are hidden attack surface — the team may have introduced bugs while adapting code, and upstream security fixes won't auto-propagate.]

### Technical Debt Markers

[Include if tech_debt.total_count > 0. Skip otherwise.]

| File:Line | Type | Text | Author | Date |
|-----------|------|------|--------|------|
| [path:N] | [TODO/FIXME/HACK/XXX] | [comment text] | [blame author] | [date] |

[TODO/FIXME/HACK comments represent known-but-unresolved issues. These are areas where the developer acknowledged incomplete work.]

### Security Observations

[4-8 bullets — synthesize ALL git signals into audit-relevant observations:]
- [Single-developer risk if applicable]
- [Missing code review signals if no merge commits]
- [High-churn files that warrant deeper review]
- [Recent rapid changes / last-minute additions before audit]
- [Large unreviewed commits if detected]
- [Fix commits without corresponding test file changes — residual risk (note: this measures file co-modification, not coverage)]
- [Forked dependencies with divergent pragmas or logic]
- [Technical debt in security-critical paths]

### Cross-Reference Synthesis

[2-4 bullets connecting git history signals to findings from Sections 2-3. This is where git evidence amplifies or confirms threat model concerns:]
- [e.g., "ClearingHouse.sol is flagged in both Threat Model (liquidation attack surface) AND git history (highest modification count) — prioritize for deep review"]
- [e.g., "Forked UniswapV2 uses pragma 0.8.27 (upstream: 0.5.x/0.6.x) — overflow behavior differs, verify arithmetic assumptions in GTELaunchpadV2Pair"]
- [e.g., "3 fix commits touch oracle price logic without co-modified test files — residual risk in price manipulation scenarios identified in Section 2"]
- [e.g., "TODO in CollateralManager:L42 ('handle negative PnL edge case') aligns with inferred margin solvency invariant in Section 3"]

---

## X-Ray Verdict

**[TIER]** — [one sentence justification]

[Tier calculation: take the lowest level across Tests, Docs, Access Control (evidence is in Sections 4-5). If Code Hygiene has TODOs in security-critical paths (Section 6), drop one tier. Absence of TODOs does NOT raise the tier.]

[IMPORTANT: Test tier is based on test EXISTENCE from Step 1 file scan counts (test_files, test_functions, stateless_fuzz, etc.), NOT on whether tests pass or fail at runtime. If enumeration found 23 unit test functions, the Tests signal is "unit tests exist" regardless of compilation or runtime failures.]

[Tier thresholds:]
[Tests: EXPOSED=0 test functions found, FRAGILE=unit only, ADEQUATE=unit + fuzz OR invariant, HARDENED=unit + fuzz + invariant, FORTIFIED=+ formal verification]
[Docs: EXPOSED=no NatSpec + no spec, FRAGILE=sparse NatSpec, ADEQUATE=NatSpec present, HARDENED=+ spec/whitepaper, FORTIFIED=+ thorough inline comments]
[Access Control: EXPOSED=unclear roles, FRAGILE=roles exist + no timelock, ADEQUATE=roles + boundaries clear, HARDENED=+ timelock or multisig, FORTIFIED=+ emergency pause]

**Structural facts:**
1. [Verifiable structural fact — e.g., "15K nSLOC across N subsystems", "N upgradeable contracts", "2 developers wrote N% of code"]
2. [...]
3. [...]
[3-5 items. ONLY measurable, verifiable facts from Sections 1-6. No security claims, no speculation about what "could" happen, no bug hypotheses, no attack scenarios. The verdict describes the codebase's structural posture (tests, docs, access control, complexity) — NOT its security. The auditor forms their own security conclusions.]
```
# Entry Point Map Template

Write `entry-points.md` using this structure. This file is a purely structural reference — no threat analysis, no invariants, no git history. It answers: "what can be called, by whom, and what does it touch."

```markdown
# Entry Point Map

> [Protocol Name] | [N] entry points | [N] permissionless | [N] role-gated | [N] admin-only

---

## Protocol Flow Paths

[Order entry points into expected execution flows — the "story" of the protocol from deployment to steady-state operation. Each major user-facing entry point gets a path showing every step that must happen before it becomes callable. This lets auditors immediately see the full prerequisite chain for any function.]

[Group flows by actor. For each flow, trace backwards from the destination function to deployment, listing every function call that must have succeeded first. Use simple arrow chains — no boxes, no diagrams. Annotate non-obvious preconditions with `◄──` comments.]

[Example format:]

### Setup (Owner)

`initReserve()` → `setLeverager()` → `initVault()` → `setLeverageParams()`

### User Flow

`[owner setup above]` → `Lender.deposit()` → `openPosition()`  ◄── liquidity must exist
                                                    ├─→ `withdraw()`
                                                    └─→ `liquidatePosition()`  ◄── position unhealthy

### Maintenance (Keeper)

`[deposit above]` → [rebalanceInterval passes] → [price in range] → `rebalance()`

[Rules for flow paths:]
[- One chain per major destination function. Branch with `├─→` and `└─→` when a function has multiple exit paths.]
[- Reference earlier flows with `[owner setup above]` or `[deposit above]` instead of repeating the chain.]
[- Add `◄──` annotations for preconditions that are NOT function calls (time passage, market conditions, position health, sufficient liquidity).]
[- Keep it factual — trace from require statements and state variable checks back to the functions that write those variables.]
[- This section should be 15-30 lines. It is an index into the detailed sections below, not a replacement.]

---

## Permissionless

[Entry points callable by any address with no effective access restriction. Sorted by value flow: tokens-in first, tokens-out second, no-token-movement last.]

### `Contract.functionName()`

| Aspect | Detail |
|--------|--------|
| Visibility | [external/public], [nonReentrant if present] |
| Caller | [Who actually calls this — User, Anyone, etc.] |
| Parameters | [paramName (user-controlled), paramName (protocol-derived)] |
| Call chain | `→ Contract.fn() → Contract.fn() → ...` |
| State modified | [storage vars/mappings that change] |
| Value flow | [Tokens: sender → Vault / Vault → recipient / None] |
| Reentrancy guard | [yes / no] |

[Repeat for each permissionless entry point]

---

## Role-Gated

[Entry points restricted by a role modifier. Group by role. Within each role, sort by value flow.]

### `OCT_KEEPER`

#### `Contract.functionName()`

| Aspect | Detail |
|--------|--------|
| Visibility | [external], [modifier name] |
| Caller | [Keeper bot / Relayer / etc.] |
| Parameters | [paramName (user-signed), paramName (keeper-provided), paramName (protocol-derived)] |
| Call chain | `→ Contract.fn() → Contract.fn() → ...` |
| State modified | [storage vars/mappings that change] |
| Value flow | [direction] |
| Reentrancy guard | [yes / no] |

[Repeat for each role and function]

---

## Admin-Only

[Entry points restricted to DEFAULT_ADMIN_ROLE or owner. These configure the protocol rather than operate it.]

[For admin functions, use a compact table instead of per-function detail blocks — auditors need to see the full admin surface at a glance:]

| Contract | Function | Parameters | State Modified |
|----------|----------|------------|----------------|
| [Contract] | `functionName()` | [params] | [what changes] |

[Repeat for each admin function]
```

## Rules

- **No overlap with x-ray.md**: Do not include threat analysis, adversary model, invariants, attack surfaces, git history, test analysis, or documentation quality. Those belong in the readiness report.
- **Factual only**: Extract facts from code. Do not speculate about risks or suggest mitigations.
- **Call chains**: Trace the full downstream path from entry point to leaf (token transfer, storage write, or external call). Use `→` notation. Stop at the first external protocol call or token transfer. Use concrete contract/library names, NOT interface names (e.g. `FuturesManager.addCollateral()`, not `ICollateralManager.addCollateral()`). Interfaces describe how the caller references the target in code, but auditors need to know which contract actually executes.
- **Parameter trust**: Mark each parameter as `(user-controlled)`, `(user-signed)`, `(keeper-provided)`, or `(protocol-derived)`. User-controlled = the caller chooses the value freely. User-signed = value comes from a user's off-chain signature. Keeper-provided = the keeper selects the value (e.g., indexPrice from price feed). Protocol-derived = read from on-chain state.
- **Exclude**: view/pure functions, interface-only functions, library internal functions (they're downstream calls, not entry points), mock contracts.
- **Include initializers separately**: If the protocol uses proxy patterns, list `initialize()` functions in a brief "Initialization" section at the end — these are one-time entry points but still attackable during deployment.
# Architecture Diagram Guide

## architecture.json Format

```json
{
  "title": "[Protocol] Architecture",
  "nodes": [
    {"id": "unique_id", "label": "DisplayName", "subtitle": "One-word role", "type": "actor|protocol|external", "row": 0}
  ],
  "edges": [
    {"from": "source_id", "to": "target_id", "label": "action description"}
  ],
  "groups": [
    {"label": "Group Name", "nodes": ["id1", "id2"]}
  ]
}
```

### Node types
- `actor`: users/roles — pill shape
- `protocol`: in-scope contracts — blue accent stripe
- `external`: out-of-scope — amber accent stripe

### subtitle
Optional short role description as second line (e.g. "Coordinator", "Price Feed"). For composite nodes, list individual contracts (e.g. "Aave / Ethena / Lido / Lista").

### row
Assign rows to **minimize edge distance**, not by node type. Place each node on the row adjacent to its primary caller. Actors typically land at the top, leaf dependencies at the bottom, but an external node called only from row 1 belongs on row 2 — NOT on a distant "externals" row.

### groups
Optional. Groups related nodes under a labeled enclosure (e.g. "Vault Layer").

**Group containment rule (CRITICAL):** Every node must be either (a) inside exactly one group, or (b) on a row that has NO group box. The SVG generator draws group boxes around all rows that contain grouped nodes. If an ungrouped node sits on the same row as a group, it will visually escape or overlap the group boundary. To fix: either add the node to the appropriate group, or move it to a different row. When deciding which group a node belongs to, classify by **primary caller** — e.g., an ACL contract called by the coordinator belongs in the coordinator's group, not in a downstream infrastructure group.

---

## Budgets & Layout Rules

### Node & edge budgets

Scale budget based on in-scope contract count (excluding interfaces):

| In-scope contracts | Max nodes | Max edges | Max per row |
|--------------------:|----------:|----------:|------------:|
| ≤10                | 12        | 14        | 4           |
| 11–20              | 16        | 18        | 4           |
| 21–35              | 20        | 22        | 5           |
| 36+                | 24        | 26        | 5           |

**Prioritize completeness over compression.** Every contract that holds funds, gates access, or sits on a critical call path should be visible — either as its own node or clearly named in a composite node's subtitle.

### Compositing rules (when to combine contracts into one node)

Apply in order — use the first tier that fits within the node budget:
- **Tier 1 — Always composite**: Contracts in the same subsystem with identical caller AND callee. Use subsystem name as label, list contracts in subtitle.
- **Tier 2 — When budget requires**: Contracts with same primary caller OR callee. Helper/satellite contracts composite into their parent node.
- **Tier 3 — Last resort**: Same-subsystem contracts with same trust level but different callers/callees.
- **Never composite across trust levels** — combining permissionless and admin-only hides trust boundaries.

### Actor and external node rules

- **Combine actors** only when they share the same trust level AND capabilities. Keep actors separate when trust levels differ.
- **External dependencies** that are sole data sources for critical logic (oracles, price feeds) should be their own node. Others can be composited by type when budget is tight.

### Same-row arc rules
- **≤2 same-row arcs per node**. If 3+ needed, move one target to adjacent row.
- **Balance directions**: 2 same-row arcs from one node → one LEFT, one RIGHT.
- **Automatic below-routing**: The SVG generator detects when a same-row arc would cross intermediate boxes and routes it below the row instead of above. Multiple below-arcs are staggered at different depths to avoid overlapping.

### Hub node layout
When a node has 3+ same-row connections (a "hub"), position it **centrally** among its same-row targets in the JSON `nodes` ordering. This minimizes arc distances and lets the generator route short connections above and long ones below. Example: if `PutManager` connects to `ftACL`, `Oracle`, and `pFT`, place `ftACL` left, `PutManager` center, `Oracle` and `pFT` right — so each arc fans out cleanly.

### Edge rules
- **Every edge label must be unique**. Never repeat the same label on multiple edges.
- **Labels: 2-3 words max**.
- **No row-skipping edges**. Every edge connects adjacent rows or same row. If an edge would span 2+ rows, move the target to an adjacent row.
- Show primary interaction flows only — not every internal call.

---

## SVG Generation & Validation

### Generate
```bash
python3 $SKILL_DIR/scripts/generate_svg.py x-ray/architecture.json x-ray/architecture.svg
```

### Render to PNG for inspection
Try in order (use first that works):
```bash
convert -density 300 x-ray/architecture.svg /tmp/architecture-preview.png
rsvg-convert x-ray/architecture.svg -o /tmp/architecture-preview.png
python3 -c "import cairosvg; cairosvg.svg2png(url='x-ray/architecture.svg', write_to='/tmp/architecture-preview.png', scale=3)"
```
Then `Read` the PNG. If no renderer is available, skip the validation loop.

### Audit checklist (max 3 iterations)

1. **Structure**: Top-to-bottom flow? Actors top, externals bottom, core middle?
2. **Edge labels**: Readable font (≥4.5), dark fill (#1E293B), sitting on their arrows (not pushed away).
3. **Edge routing**: No row-skipping edges, no arrows through boxes. Same-row arcs balanced (one LEFT, one RIGHT). Long same-row arcs that would cross intermediate boxes should route below (the generator does this automatically — verify visually).
4. **No overlapping labels**: Stagger y by ≥8 units if bounding boxes overlap.
5. **Groups**: All group rects aligned (same x-edge/width). No ungrouped node on a row that has a group box.
6. **Centering**: Nodes roughly centered on canvas, balanced across rows.

### Fix types
- **JSON-level** (regenerate): row assignments, node ordering, edges, groups → edit JSON, re-run `generate_svg.py`, re-render.
- **SVG-level** (post-process): label font/color/position → edit SVG directly, re-render.

### Cleanup
```bash
rm -f x-ray/architecture.json x-ray/git-security-analysis.json /tmp/architecture-preview.png
```

