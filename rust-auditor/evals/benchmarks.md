# rust-auditor benchmarks

A scoring set of **public** Solana security codebases and audit reports with **documented** bugs,
so a future rust-auditor run can be measured: point the skill at the scope, and check the report
against the known findings below. Only bugs the source itself documents are listed — nothing here is
invented. "Expected" means "the source says this bug is here", not "the skill is guaranteed to find
it"; a run is scored by recall against these and by false positives outside them.

Each entry pins the **commit / version** it was recorded at. Re-pin before scoring, because the
upstream repos move. Loss figures and severities are the source's own. Educational repos label
severity by bug class (the vulnerable module is deliberately exploitable); audit reports use the
auditor's severity.

Targets are not vendored: clone each repo below and check out the pinned commit with `git archive` (§0).

**Two kinds of expected bug.** Rows marked **source** are documented by the target itself (its
README, comments or audit report). Rows marked **found-by-skill** were raised by a rust-auditor
benchmark run, then **re-confirmed by hand in the code at the pinned commit** — the source does not
document them. They score recall like any other row, but a scorer should know they come from the
skill, not from the target's authors. Rows the source documents but the code does **not** contain
are kept, struck as **not present**, with the reason, so nobody re-adds them.

---

## 0. How to run a benchmark — blind

**Template comments leak the answers.** `solana-security-template` marks its bugs in comments
(`// VULN: …`, `/// CHECK: VULNERABLE - …`), and other educational repos do the same. An agent that
reads them is not auditing. **Every benchmark run must strip comments from the in-scope files
first**, on a scratch copy, never on the original clone:

```bash
SKILL=/path/to/rust-auditor                               # this skill's directory
git -C /path/to/clone archive <pinned-commit> | tar -x -C /tmp/bench-target   # snapshot, no git history
cd /tmp/bench-target
python3 "$SKILL/evals/strip-comments.py" --in-place --list scope.txt   # scope.txt = the in-scope .rs files, one per line
python3 "$SKILL/evals/strip-comments.py" --check --list scope.txt      # exit 0 = no comment left
# then run the skill on /tmp/bench-target with the same file scope
```

- `strip-comments.py` is Python 3 standard library only. It removes `//`, `///`, `//!`,
  `/* */`, `/** */` and `/*! */` (nested block comments too), keeps every string, byte-string,
  raw-string (`r#"…"#`), char literal and lifetime byte for byte, and keeps every newline, so line
  numbers in findings match the original. Other modes: `FILE.rs` alone prints to stdout;
  `--out-dir DIR FILE…` writes a mirrored tree; `--keep-check` keeps Anchor `/// CHECK` notes (they
  leak too in the template — leave the default for benchmarks). `--help` prints the full usage.
- **Use `git archive`, not a clone.** A pre-fix checkout of a repo whose later commits fix the bugs
  (M0, §5) exposes the fix commit titles to `git log --all`. A snapshot with no history does not.
- **What stripping cannot remove** — tell the scorer, do not try to hide it: file names
  (`vulnerable.rs` / `secure.rs`), function and struct names (`vulnerable_withdraw`,
  `SecureTransfer`), and string literals in code (`msg!("VULNERABLE: …")` in
  `authority-transfer/src/vulnerable.rs` and `remaining-accounts/src/vulnerable.rs`). Score with
  that in mind: a finding that only restates a name is weak evidence.
- **Catalogue leakage.** See §8: some targets are cited by the skill's own exploit-pattern catalogue,
  so a run on them measures fit, not generalisation.

---

## 1. Ubuntu-Technologies/solana-security-template — `@cb48608`

<https://github.com/Ubuntu-Technologies/solana-security-template>

Anchor (+ Pinocchio) vulnerable-vs-secure modules, each with LiteSVM tests; AMM adds Trident
fuzzing. Scope for each row = `programs/<module>/src/vulnerable.rs` (+ `state.rs`, `lib.rs`); the
matching `secure.rs` is the negative control **for that module's documented bug only** — a run
should not raise the documented bug on it. Several secure variants carry **other, real** bugs
(§1b); a finding on those is a true positive, not a false one.

**Build context matters here.** The root `Cargo.toml` sets `[profile.release] overflow-checks =
true` and `exclude = ["tests", "programs/amm"]`; `programs/amm/Cargo.toml` is its **own** workspace
with no `overflow-checks`, so `buggy-amm` / `secure-amm` wrap on overflow and every other module
panics. The Build context reports this per workspace.

Documented bug per module (status re-checked in code at `@cb48608`, 2026-10-06):

| Module (scope) | Documented bug | Class | Severity |
| --- | --- | --- | --- |
| `signer-authorization` | privileged action with no signer check | B1 | High |
| `owner-check` | account trusted with no owner check | B2 | High |
| `account-type-mismatch` | type cosplay — no discriminator distinguishes layouts | B3 | High |
| `insecure-init` | re-init / first-caller claims config | B4 | High |
| `remaining-accounts` | `ctx.remaining_accounts` used unvalidated | B5-adjacent | High |
| `duplicate-accounts` | two mutable accounts, no `key() !=` constraint | B6 | High |
| `pda-security` | non-canonical / predictable PDA derivation | B7 | High |
| `account-close` | ~~manual lamports-to-zero close, revival possible~~ **not present** — `vulnerable.rs` closes with Anchor `close = owner` (anchor-lang 0.32.1 from the workspace), which zeroes the data, gives the account back to the System program and shrinks it; there is no manual drain and no revival. Not expected; a revival finding here is a false positive. | ~~B8~~ | — |
| `arithmetic-overflow` | ~~unchecked arithmetic wraps (overflow-checks off)~~ **reclassified** — the arithmetic is unchecked (`amount_in * reserve_y`, `reserve_y - amount_out`), but this crate is under the root workspace with `overflow-checks = true`, so it **panics**, it does not wrap: expected impact is a failed swap for extreme inputs (DoS-level, Low), not a wrapping High. Present and expected instead: `swap_x_for_y` takes `_min_out` and never checks it (no slippage bound; the source marks it in a comment and `secure.rs` checks it). | B10 → B10 (panic) + B16 | Low (B10) / Medium (B16) |
| `account-reloading` | ~~stale account read after CPI (no `reload()`)~~ **not present** — `vulnerable.rs` makes no CPI at all; it increments `counter.count` twice in one handler and logs a warning that a CPI "would" make it stale. No stale read exists. Not expected. | ~~B11~~ | — |
| `account-griefing` | predictable `init` PDA pre-funded to DoS the victim | B13 | Medium |
| `authority-transfer` | single-step authority handover, no propose/accept | B14 | High |
| `multisig-payer` | PDA used as `init` payer — always fails (correctness, not a vuln) | — | Informational |
| `amm/buggy-amm` | weak PDA seeds + unchecked overflow (wraps — the `amm` workspace has no `overflow-checks`) + **ignored `min_out` (no slippage)** | B7+B10+B16 | High |
| `p-escrow` (`src/instructions/refund.rs`, Pinocchio) | `process_vulnerable_refund` sends the vault to any `destination`, never checked against `escrow.maker` | B15 / L2 | High |

### 1b. Found-by-skill additions — `solana-security-template @cb48608`

Raised by an earlier rust-auditor run and **re-confirmed by hand in the code** at `@cb48608`.
**Not documented by the source.** Location = file and instruction; the
evidence column names the lines that prove it.

| ID | Location (variant) | Issue | Evidence | Class | Severity (suggested) |
| --- | --- | --- | --- | --- | --- |
| T1 | `amm/buggy-amm` **and** `amm/secure-amm` `deposit` | LP minted is the caller's `amount`, independent of the `x` / `y` actually paid: `max_x = max_y = 0` pays nothing and mints `amount` LP, then `withdraw` takes a share of the vaults | `mint_to(.., amount)` after transfers of `x`, `y` from `max_x`, `max_y`; no relation between them | value / logic | Critical |
| T2 | `amm/secure-amm` `deposit` | integer ratio `vault_x.amount / vault_y.amount` is 0 whenever `vault_x < vault_y`, so `max_x.checked_div(0)` returns `MathError`: every later deposit fails | `checked_div(vault_y.amount)` then `checked_div(ratio)` | DoS (B10-adjacent) | Medium |
| T3 | `duplicate-accounts` `transfer` (**vulnerable and secure**) | `authority: Signer` is never bound to `from_account.owner` (seeds use the stored `from_account.owner`), so any signer moves any user's balance; the secure fix adds only `from != to` | `seeds = [b"balance", from_account.owner.as_ref()]`, no `has_one` / constraint on `authority` | B1 | High |
| T4 | `owner-check` `initialize_config` (`lib.rs`) | no signer and no is-initialized check: anyone overwrites the admin of any program-owned config account, then passes `read_config` as admin | owner check only; raw `copy_nonoverlapping` of `Config { admin }` | B4 + B1 | High |
| T5 | `owner-check` `process_read_config` (**vulnerable and secure**) | the caller's key is compared with the stored admin but `is_signer` is never checked — anyone passes the admin's key | `caller.address().as_ref() != stored_admin`, no `is_signer()` | B1 | High (in the module's own threat model) |
| T6 | `account-type-mismatch` `init_user` / `init_admin` (`lib.rs`) | no signer and no discriminator / is-initialized check: any program-owned account (a live `User` or `Admin`) is re-written by anyone | owner check only, then raw write of a fresh struct | B4 | High |
| T7 | `account-type-mismatch` `process_action` (**vulnerable and secure**) | hand offsets misread the `#[repr(C)]` layout: the key is read at `data[1..33]` and the balance at `33..41`, but `User` is `discriminator@0, _padding@1..8, balance@8..16, pubkey@16..48`. The key check compares padding + balance bytes, so it never passes for a real user — the instruction fails for every caller, and the module's missing-signer bug is **masked** by it (`references/judging.md` Gate 1 now reports a masked bug as its own finding; this row has not been re-scored under that rule) | `&data[1..33]`, `data[33..41]` vs `state.rs` | correctness (offset) | Low (correctness lane) |
| T8 | `multisig-payer` `vote` | any signer votes any number of times; no voter record, no membership check | `yes_votes += 1` with only `voter: Signer` | B1 / logic | Medium |
| T9 | `p-escrow` `process_secure_refund` | requires `destination == caller` (the maker's wallet) and then token-transfers to it; a wallet is not a token account, so the "secure" refund fails for every caller and the escrowed tokens cannot be refunded | `destination.key() != caller.key()` → `Err`; `Transfer { to: destination }` | locked funds (always-failing refund) | Medium |

Scoring note: with these rows, "no finding on `secure.rs`" is **wrong** for `duplicate-accounts`,
`owner-check`, `account-type-mismatch`, `p-escrow` and `amm/secure-amm`. The negative control holds
only for each module's documented bug.

## 2. Abdullateef1x/solana-security-patterns — `@4646ebe`

<https://github.com/Abdullateef1x/solana-security-patterns>

Five patterns, **each in Anchor and Pinocchio** (scope = `programs/<pattern>/{anchor,pinocchio}/src/vulnerable.rs`).
Note: the repo warns these may not `anchor build` (dependency/IDL drift) — they score the account-map
+ agent review, not the `--poc` build path.

| Pattern | Documented bug | Class | Severity |
| --- | --- | --- | --- |
| `missing-signer-check` | no `is_signer` / no `Signer` | B1 | High |
| `missing-has-one` | account link not enforced (`has_one` missing) | B1/B7 | High |
| `unsafe-arithmetic` | unchecked add/sub on balances | B10 | High |
| `insecure-pda` | PDA accepted without re-derivation / seeds | B7 | High |
| `cpi-authority-misuse` | user-controlled account passed as CPI transfer authority | B5 | High |

## 3. Xzavior34/solana-security-secrets — `@a1963e7`

<https://github.com/Xzavior34/solana-security-secrets>

Educational site + one Anchor program (`anchor/programs/security_secrets/src/lib.rs`) demonstrating
five classes: signer authorization (B1), type cosplay (B3), PDA verification (B7), owner check (B2),
integer overflow (B10). Scope = that `lib.rs`. Severity: High by class. Contributes the CEI
mental model and the Anchor-vs-Pinocchio comparison, not new bug classes.

## 4. HalbornSecurity/CTFs — HalbornCTF_Rust_Solana — `@684f1af`

<https://github.com/HalbornSecurity/CTFs>

A **native** (non-Anchor) Solana program: `HalbornCTF_Rust_Solana/ctf_game/ctf/src/{processor,instructions,state,lib}.rs`.
A good native/manual-validation target. **Expected bugs: not published** — it is a CTF requiring a
PoC, so no itemized findings are listed here (not fabricated). Use it to check the account-map and
the native/Pinocchio review do not crash and produce sane leads on hand-rolled account handling.

## 5. Adevar Labs audit reports (external repos; findings documented in the report)

<https://github.com/AdevarLabs/audit-reports>

Scope = the audited repo at the commit the report pins; known findings = the report's finding IDs,
severities and file locations. Summarize, do not copy. From `AdevarLabs/audit-reports @d51d21e`:

- **GLAM** — `reports/2025-11-07_GLAM_audit_report.pdf` (audited `glamsystems/glam @bafcfeab…`).
  Documented: 2 High, 2 Medium, 10 Low. Generalizable, locatable findings:
  E06 vault can transfer SOL to any allowed address; **E07 Kamino/Drift deposit/withdraw skip the
  markets allow-list**; **E20 destination account not validated on `ext_drift/.../withdraw.rs`
  (deposit checks it, withdraw doesn't)**; L04 timelock bypass; L10/E14 fee crystallization ordering;
  M01 admin can't burn/force-transfer from non-ATA.
- **Indentura Private Credit Vault** — `reports/2026-02-17_Indentura_Private_Credit_Vault_audit_report.pdf`.
  Documented: 2 High, 2 Medium, 5 Low. **H01/H02 silent u64 overflow in admin/user withdrawal math
  → fund loss**; M01 missing slippage protection in `ACTION_WITHDRAW`; M02 deposit DoS; L04 missing
  `state_vault` check allows reinitialization; L05 broken clock check.
- **M0 MExtensions** — `reports/2025-07-02_M0_MExtensions_audit_report.pdf`.
  **Scope = `m0-foundation/solana-extensions` at the pre-fix commit `25e29e1`** ("Merge pull request
  #11 … feat-flag-v1"; the report's code links pin `AdevarLabs/solana-extensions@25e29e1c4564b12cb811e9461b44b5305a824ac9`).
  The fixes landed later — `fc4d934` ("Merge pull request #35 … audit-remediations") is a descendant
  of `25e29e1` — so **auditing HEAD finds the fixed code and scores nothing**. Check out `25e29e1`
  with `git archive` (§0), so the fix commits are not in reach of `git log`. In-scope files: the
  `programs/ext_swap/src/**` and `programs/m_ext/src/**` sources (25 files at `25e29e1`).
  Documented: 1 Critical, 3 Medium, 2 Low. **#1 (Critical) missing admin access control on `ext_swap`
  whitelist ops**; #2 retroactive fee application; #3 imprecise multiplier → insolvency; #4 swap
  doesn't forbid same-token swap; #5 `m_ext` init front-running; #6 misaligned Anchor constraint on
  the swap source token account.
  **Found-by-skill additions** (an earlier rust-auditor run, re-confirmed by hand at `25e29e1`; not
  report findings — each is corroborated by a change in `fc4d934`):
  - **M0-A1** `m_ext` `wrap` / `unwrap` / `sync` require the vault's `Earner` account
    (`seeds = [EARNER_SEED, vault_m_token_account.key()]`, `seeds::program = EARN_PROGRAM`) to read
    the index; if the Earn program removes the vault as an earner, every wrap, unwrap and sync
    fails and wrapped funds are stuck (DoS, Medium). `fc4d934` reads `m_earn_global_account` instead.
  - **M0-A2** `m_ext` `set_m_mint` swaps `global_account.m_mint` and keeps `yield_config.last_m_index`
    / `last_ext_index` from the old mint, so the next sync computes from a stale index (honest-admin,
    retroactive; Low–Medium). Overlaps the report's Enhancements, not its numbered findings.
    `fc4d934` removes `set_m_mint`.
  - **M0-A3** `ext_swap` `initialize_global`: any signer becomes `admin` of the `[GLOBAL_SEED]`
    singleton — first caller wins (init front-running, the `ext_swap` twin of #5; Medium).

## 6. anza-xyz/security-audits — core-component reports — `@4d5d71e`

<https://github.com/anza-xyz/security-audits>

Scope = the component at the audited version; these are **negative/robustness controls** (core code,
mostly clean):

- **Neodyme P-Token (Pinocchio)** — `spl/NeodymePTokenPinocchioAudit-2025-06-12.pdf`: **0 findings**
  (clean). Use as a false-positive control for a Pinocchio token program, and mine its "Select
  Common Vulnerabilities" list (freeze-authority checks, rent-exemption assertion, account-creation
  DoS, CPI recursion, redeployment cross-instance confusion, log truncation).
- **Certora P-Token formal verification** — `spl/CertoraPTokenFV-2026-05-11.pdf`.
- Zellic/Neodyme stake-program and Token-2022 reports are present for Token-2022 extension review
  context (B12).

## 7. 0xMacro/awesome-solana-security — competitive-audit targets — `@24f792c`

<https://github.com/0xMacro/awesome-solana-security>

Linked First Flights with documented results (itemized findings on the linked report pages; only the
verified aggregate counts are recorded here, not fabricated specifics):

- **RustFund** First Flight — codehawks.cyfrin.io/c/2025-03-rustfund (170 nSLOC): **4 High, 3 Medium,
  4 Low** (verified on the results page).
- **SSSwap** First Flight — codehawks.cyfrin.io/c/2025-05-ssswap: **5 High, 4 Medium, 1 Low**
  (verified on the results page).

Both are now scored in full: RustFund in §11 and SSSwap in §12.

## 8. Leakage hygiene — targets the skill has already seen

A benchmark measures generalisation only on code the skill was not developed against. Every target
the skill's own references cite, or that was used to develop it, is recorded here; score those
targets as **fit, not generalisation**, and do not add a reference entry that cites a held-out
target.

- **§1 (`solana-security-template`)** — `references/solana-exploit-patterns.md` **B13**
  (account-creation griefing) and **B14** (single-step authority transfer) cite its programs by
  name, and `references/poc-guide.md` points at it as a harness example.
- **§2 (`solana-security-patterns`)** and **§3 (`solana-security-secrets`)** — the Pinocchio
  sections of `account-validation-agent.md` and `periphery-agent.md` cite both.
- **§5 (Adevar Labs reports)** — Part C of `solana-exploit-patterns.md` cites **GLAM** (**L1**–**L4**,
  and **B15**), **Indentura** (**L5**–**L7**, and **B13**, **B16**) and the **M0 MExtensions** report
  (**L8** = #1, **L4** = #2, **L9** = #3, **L7** = #5, **L10** = #6; #4, the same-token swap, is
  not cited, but **B17**, the same-asset round trip, generalises it).
- **§6** — Part C cites the **Neodyme P-Token** report.
- The correctness lane, the hand-offset check (`offset-mismatch`), `key-compared-no-signer`, the
  honest-admin rule, singleton folding and per-workspace overflow detection were developed while
  grading §1 and §5.
- **§9 (`solana-program/escrow`)** shaped the fix-aware dedup rule, **B23**–**B25**, the
  privilege-passthrough access gap, the hardening LEAD checklist, the honest-admin recoverability
  rule and the account map's native / Pinocchio idioms.
- **§10 (`code-423n4/2025-01-pump-science`)** shaped design-guess demotion, privileged-op griefing
  (**B26**), fee-base consistency, piecewise continuity, the rent-floor subtraction and setter
  completeness.
- **§11 (RustFund)** and **§12 (SSSwap)** were scored blind first (their baselines are recorded in
  each section) and then shaped: a bug masked by another finding is gated as a finding (Gate 1), a
  per-instance role is not an admin (Gate 3), a fee that rounds to zero on a splittable path is not
  dust, code-based cross-instruction echo, convergence that needs a FINDING behind it, stranded
  rent and boundary overlap in the correctness lane, the rent-floor exception (RustFund), the
  blocker cap in Gate 1 (SSSwap), the raw-unit and lamport-debit safe patterns, the auditor framing
  of the agent prompts, and dead-agent accounting.
- **§13 (Garden)** was scored blind once and then shaped the self-harm clause of the design-guess
  rule.
- **Held-out candidates:** §4 (HalbornCTF) is not cited anywhere in the skill.
- Strip comments before every run (§0). Template comments name the bug class in the line that
  holds it.

## 9. solana-program/escrow — Accretion audit A26SFR3 — `@b27a635`

<https://github.com/solana-program/escrow> · report:
<https://github.com/accretion-xyz/audit-reports/blob/main/2026-accretion-solana-foundation-escrow-audit-A26SFR3.pdf>

**Used to develop the skill — not blind** (§8). Score runs on it as **fit**, not generalisation.

Scope = `program/src/**` at the audited commit `b27a63562bf861470ed1012211251b4320738c29` (Pinocchio,
SPL Token and Token-2022, a TLV extension block per escrow). The fix-review commit is `36187ad`;
check out `b27a635` with `git archive` (§0) so the fixes are not in reach. Documented: 1 Critical,
3 High, 4 Medium, 5 Low, 2 Informational. Summarized from the report:

- **C1** withdraw does not check the passed mint against the receipt's mint — a depositor withdraws
  a different token from the escrow's vaults.
- **H1** the extension-update helper rewrites a TLV entry in place and leaves stale bytes when the
  new entry is shorter. At `b27a635` no caller shrinks an entry (the report's link points at a later
  commit), so score it as a latent helper defect.
- **H2** the hook CPI forwards the user's signer and writable flags to the configured hook program.
- **H3** an allow-listed Token-2022 mint with a mint close authority can be closed and re-created
  with blocked extensions after the allow-time check.
- **M1** timelock / hook / arbiter changes apply to deposits made before the change.
- **M2** the blocked-extension list is checked when a mint is allowed, not at deposit.
- **M3** a transfer-fee mint makes the recorded deposit larger than the amount received.
- **M4** a System `create_account` at a predictable PDA fails once someone pre-funds the address
  (lamport-transfer DoS).
- **L1** the post-withdraw hook does not receive the receipt. **L2** one loader of the allowed-mint
  account skips its self-validation. **L3** the layout version byte is not checked on read.
  **L4** timelock, arbiter and hook cannot be updated or removed. **L5** discriminator `0` equals
  zeroed data.
- **I1** deposit and withdraw do not check the mint's owner explicitly. **I2** the extensions
  account's owner is implied by its PDA, not checked.

## 10. code-423n4/2025-01-pump-science — Code4rena, January 2025 — `@768ef58`

<https://github.com/code-423n4/2025-01-pump-science> · report:
<https://code4rena.com/reports/2025-01-pump-science>

**Used to develop the skill — not blind** (§8). Score runs on it as **fit**, not generalisation.

Scope is the in-scope Anchor program at
`768ef58478724bf6b464c9f0952e3e5a3b2a2613`. The report lists 5 unique findings: 2 High, 3 Medium,
plus 12 Low / Non-Critical. Summarized from the report:

- **H-01** `lock_pool` can be stopped by pre-creating the `lock_escrow` account.
- **H-02** `update_settings` never writes `migration_token_allocation`, although the input struct
  carries the field.
- **M-01** the buy that completes the curve charges the fee on the full input and applies less.
- **M-02** the curve's SOL-balance check counts the rent-exempt lamports as reserves.
- **M-03** the fee formula jumps at slot 250 (the linear phase does not land on the next phase).

## 11. CodeHawks-Contests/2025-03-rustfund — CodeHawks First Flight #36 — `@b5dd7b0`

<https://github.com/CodeHawks-Contests/2025-03-rustfund> · judged results:
<https://codehawks.cyfrin.io/c/2025-03-rustfund/results?t=report>

**Used to develop the skill — blind only for the baseline below** (§8). Score every later run on it as **fit**, not generalisation.

Scope = `programs/rustfund/src/lib.rs` (one Anchor program, anchor-lang 0.30.1, release
`overflow-checks = true`): a crowdfunding program with `fund_create`, `contribute`,
`set_deadline`, `refund` and `withdraw`. The judged report lists 4 High, 3 Medium and 4 Low.
Summarized from the result titles, each re-checked in the code by two independent reviewers:

| ID | Documented bug | Status in the code |
| --- | --- | --- |
| H-01 | `withdraw` does not check that the deadline has passed | valid |
| H-02 | `withdraw` does not check that the goal was met | valid |
| H-03 | `contribute` never adds the amount to `contribution.amount`, so every refund pays 0 | valid |
| H-04 | `refund` does not check the goal, so contributors of a successful campaign can refund | valid — masked by H-03 in the code as written |
| M-01 | `withdraw` does not reset `amount_raised`, so a later withdraw fails | valid |
| M-02 | `set_deadline` never sets `dealine_set`, so the creator can move the deadline at any time | valid |
| M-03 | `refund` does not lower `amount_raised`, so the creator's withdraw then fails | valid — masked by H-03 |
| L-01 | `refund` skips the time check while the deadline is 0 | valid — masked by H-03 |
| L-02 | no validation of the goal | **questionable** — a creation parameter contributors can read; `goal` is read nowhere today |
| L-03 | direct lamport manipulation in `refund` / `withdraw` | **invalid** — a checked debit from a program-owned data account is the required pattern |
| L-04 | no instruction closes a Fund or Contribution account, so rent stays locked | valid |

Found-by-skill (re-confirmed in the code): `fund_create` uses the whole `name` as a PDA seed, and
a seed holds at most 32 bytes, so every name longer than 32 bytes fails although `Fund` reserves
200 (Low / correctness).

**Blind baseline**, scored before the judging changes this target shaped (§8): all 9 valid items
were raised — 5 as Findings (H-01, H-02, H-03, M-01, M-02) and 4 as Leads (H-04, M-03, L-01,
L-04) — with 6 Findings, none a false positive (one debatable: `contribute` and `refund` both pass
when the clock equals the deadline). The 4 Leads were all lost in judging, not in discovery.

**After the changes** (one re-run of the 12 agents per §0; the judging rules were then revised
against that run's output, and the same output was re-judged — fit, not generalisation). As first
judged: 13 Findings — all 9 valid items as Findings (L-04's Fund half stays a Lead on purpose),
1 false positive (`withdraw` / `refund` ignore the rent floor), 2 debatable, 1 duplicate split.
Re-judged: 11 Findings at or above the threshold, all 9 valid items as Findings, no false
positive, one debatable — the deadline-second overlap, promoted at 75. The boundary-overlap
wording in `references/judging.md` was tightened after that re-judge to keep it a Lead; that last
change has not been re-scored.

## 12. CodeHawks-Contests/2025-05-ssswap — CodeHawks First Flight #41 — `@27a2ef8`

<https://github.com/CodeHawks-Contests/2025-05-ssswap> · judged results:
<https://codehawks.cyfrin.io/c/2025-05-ssswap/results?t=report>

**Used to develop the skill — blind only for the baseline below** (§8). Score every later run on it as **fit**, not generalisation.

Scope = `programs/amm/src/**` (one Anchor constant-product AMM, anchor-lang / anchor-spl 0.31.1,
release `overflow-checks = true`). The judged report lists 5 High, 4 Medium and 1 Low. Summarized
from the result titles, each re-checked in the code by two independent reviewers:

| ID | Documented bug | Status in the code |
| --- | --- | --- |
| H-01 | `provide_liquidity` computes the LP amount with the wrong formula | valid |
| H-02 | `provide_liquidity` takes no slippage bound | valid |
| H-03 | no validation of mint decimals at pool creation | **invalid** — every formula works in raw base units and is scale-invariant |
| H-04 | `provide_liquidity` mints from stale vault state | **invalid as stated** — the vaults are reloaded before they are read; the real defect is H-01's formula |
| H-05 | no minimum liquidity lock | **questionable** — the mechanism is real (a fully drained pool cannot take liquidity again), the permanent-DoS impact is overstated |
| M-01 | an attacker blocks pool creation for a pair through a PDA collision | valid |
| M-02 | unchecked `u128 as u64` casts | valid — in `swap_exact_out` the truncated input lets a caller take almost the whole output reserve |
| M-03 | `lp_mint` is initialised before `liquidity_pool` and fails | **invalid** — Anchor binds every account before any `init` block runs, and the `lp_mint` init needs only the pool's key |
| M-04 | the swap fee rounds down to zero on small swaps | valid |
| L-01 | non-standard token behaviour (transfer fee) is not handled | **disputed** — the root cause is real, but no Token-2022 pool can be created today (next paragraph) |

Found-by-skill (re-confirmed in the code): the creator's and the provider's ATAs use
`associated_token::*` without `associated_token::token_program`, so Anchor derives them with the
SPL Token program, and `initialize_pool_with_liquidity`, `provide_liquidity` and `remove_liquidity`
fail for every Token-2022 mint although the README lists Token-2022 as supported (Medium / Low,
correctness).

**Blind baseline**, scored before the judging changes this target shaped (§8): all 5 valid items
were raised — 4 as Findings (H-01, H-02, M-01, M-02; the M-02 cast reported as a High reserve
drain) and M-04 as a Lead — with 7 Findings, all valid. **4 of the 12 agents returned no FINDING or LEAD block:**
each read its bundle and then reported that a safety classifier withheld its reply. That run
prompted the auditor framing in the agent prompts and the `Agents` row for a 1-pass scan that loses
an agent.

**After the changes** (one re-run per §0; 12/12 agents returned results; the judging rules were
then revised against that output and the same output re-judged — fit, not generalisation). As
first judged: 11 Findings — all 5 valid items as Findings, no false positive, 4 duplicate splits
(the transfer-fee path, L-01, appeared as 3 Findings at 90). Re-judged: 7 Findings, all 5 valid
items as Findings, no false positive and no duplicate split; the one debatable item is the
transfer-fee path (L-01), which the missing ATA token program blocks today, at 80. The blocker
cap in `references/judging.md` Gate 1 was added after that re-judge to hold it at 75; it has not
been re-scored. The found-by-skill Token-2022 ATA defect above was a Finding in the baseline but
only one agent's Lead in the re-run.

## 13. code-423n4/2025-11-garden — Code4rena, November 2025 — `@933f545`

<https://github.com/code-423n4/2025-11-garden> · report:
<https://code4rena.com/reports/2025-11-garden>

**Used to develop the skill — blind only for the first run below** (§8). Score every later run on it as **fit**, not generalisation.

A **false-positive control.** Scope = `solana/solana-native/programs/solana-native-swaps/src/lib.rs`
and `solana/solana-spl-swaps/programs/solana-spl-swaps/src/lib.rs` — two Anchor HTLC swap programs,
each its own workspace with release `overflow-checks = true`. The report has **no High or Medium in
the Solana programs** (its only Medium is in the EVM code). Its top QA report lists one Solana Low:
`initiate` does not require `redeemer != refundee`, so one party can create an order with itself and
refund it at once (`[01]`). `known-issues.md` lists further accepted Solana behaviour (duplicate
orders after a close, redeem after expiry, no zero-value or timelock checks).

**Blind snapshot:** take `solana/`, `README.md`, `known-issues.md`, `scope.txt` and
`out_of_scope.txt` only. Leave out `2025-11-garden-V12-findings.md`, `4naly3er-report.md` and
`discord-export/` — they discuss candidate findings.

Expected: **no Finding at or above the threshold** that two independent reviewers accept as a real
defect. The QA Low is an acceptable `hardening-` Lead.

**Scored blind** with the changes from the first §11 / §12 runs in place: 3 correctness Findings, all false positives —
the same account accepted on both legs of `redeem`, `refund` and `instant_refund` when the funder
names the program's identity PDA as a party, a state only the funder's own input creates and only
the funder loses by. That run added the self-harm clause to the design-guess rule
(`references/judging.md`, mirrored in `references/dedup-and-assembly.md` Turn 4); re-judged under
it, the same agent output gives **0 Findings and 31 Leads**. The QA Low was not raised.
