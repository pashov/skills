# Shared Scan Rules

## Bundle contents

Your bundle is concatenated files: all in-scope source code (opening with a **Build context** header and the crate manifests), the SOP (HOW to think), your specialty agent (WHAT to look for), these shared rules (output format, dedup tags), the report language rules (HOW to word a finding), the Solana exploit-pattern catalogue (incidents and bug classes to hunt for), and the account map (a pre-scan list of leads — accounts, CPIs, state and auto-highlighted red flags per instruction). When memory is on, a "Known findings" section is appended last.

Read the whole bundle once at the start. The bundle contains all in-scope source. Use Read/Grep only for cross-file searches or out-of-scope context (`tests/`, client and SDK crates, the IDL, and framework sources under `~/.cargo/registry/src/`) — do not re-read in-scope files for the initial scan.

## Build context — read it first

The top of `source.md` says which framework each crate uses and whether release overflow checks are on. Both change what the code really checks:

- **Framework.** Anchor checks a lot for you — but only for the account types and constraints that are actually written. Native `solana-program` and Pinocchio check **nothing** you do not write by hand: every signer, owner, discriminator, PDA and program ID check is a line of code or it does not exist. Pinocchio also hands out unchecked borrows (`borrow_mut_data_unchecked`, or `borrow_unchecked_mut` on the newer `AccountView`; raw pointers) that skip its borrow-state flag. A repo can mix frameworks; judge each crate by its own manifest.
- **Framework version.** The manifests carry the exact `anchor-lang` / `solana-program` / `pinocchio` / `spl-token-2022` versions. What `close`, `init_if_needed`, `realloc` and duplicate-account handling do has changed across Anchor releases. When a finding depends on what the framework checks, read that version's source under `~/.cargo/registry/src/` rather than assuming. When that version is not on disk, say in `proof:` which framework behaviour you assumed and for which version, so the judge can weigh it.
- **Release overflow checks.** `not set` or `OFF` means `+ - *` wrap silently in the deployed program. `on` means they panic. `as` casts truncate and `wrapping_*` wraps either way. The setting is **per workspace**: when the line says `differs per workspace`, it names the crates under each root — use the root of the crate you are reading (a nested or `exclude`d workspace is built with its own profile, not the top-level one).
- **Hand-coded byte offsets (native / Pinocchio).** When a handler reads account data by fixed offsets (`data[1..33]`, `data[33..41]`, `*(ptr.add(9) as *const u64)`), lay the offsets against the struct the account holds. Under `#[repr(C)]` each field is aligned to its size (`u8` then `u64` puts 7 bytes of padding at 1..8); under `#[repr(packed)]` there is no padding; an Anchor or `bytemuck` account starts with its discriminator. A range that does not start and end on field boundaries reads the wrong bytes. Then ask what that does: a check built on the wrong bytes either **never passes** (the instruction fails for every caller — a correctness finding, `judging.md` Gate 4) or **compares bytes the attacker controls** (a bypass). It also decides whether a missing-signer or owner bug next to it is reachable today — an instruction that always fails cannot be exploited until the offset is fixed, so report the offset as the finding and the bypass as its own finding masked by it (see Output, "A bug that hides another bug"). The account map raises `offset-mismatch` when it can match the struct.

## Out of scope inside in-scope files

`#[cfg(test)]` modules (`mod tests { … }`) and `#[test]` functions are test code. Read them for context — they often show what the developer believed — but never report a bug in them. Code behind a feature flag (`#[cfg(feature = "…")]`) **is** in scope: note which build the bug is in, and flag any check that a feature flag removes from the production build.

## Naming — finding the same instruction under every spelling

One instruction has several names. When you match an instruction across files, check all of them:

- **Anchor:** the `#[program]` module fn `withdraw`, its `#[derive(Accounts)] pub struct Withdraw<'info>`, and its logic, often in `instructions/withdraw.rs` as `pub fn handler(ctx: Context<Withdraw>, …)`, `impl<'info> Withdraw<'info> { fn process(…) }` or `ctx.accounts.withdraw(…)`.
- **Native / Pinocchio:** the instruction enum variant `Instruction::Withdraw`, the match arm in `process_instruction`, and the handler `process_withdraw` / `withdraw::process`.

## The group key

`group_key` is `Program | function | bug_class`.

- **Program** — the Anchor `#[program]` module name (`vault`), otherwise the program crate directory name (`programs/vault/` → `vault`). For a shared library crate, its crate directory name.
- **function** — for an instruction handler **or its Accounts struct**, the **instruction name** (`withdraw` — not `handler`, not `Withdraw`). A missing constraint in `struct Withdraw` and a logic bug in the `withdraw` handler share `program | withdraw`. For a native program, the handler fn (`process_withdraw`). For any other code, the fn's own name.
- **bug_class** — a short kebab-case label that names the defect, not its consequence (`missing-signer-check`, `missing-owner-check`, `non-canonical-bump`, `stale-account-after-cpi`).

The location line in a report reads `program::function`.

## Cross-instruction patterns

When you find a bug in one instruction, **weaponize that pattern across every other instruction and program in the bundle.** Search by account name, by account type and by code pattern. A missing owner check on `config` in `deposit` means you check every instruction that takes `config`; a PDA whose seeds lack the user key in one place means you check every PDA built from the same seeds. Missing a repeat instance is an audit failure.

After scanning: escalate every finding to its worst exploitable variant (an instruction that fails may hide a fund theft, and a fake account that sets one field may set them all). Then revisit every instruction where you found something and attack the other branches and the other accounts.

## The account map is leads, not findings

The account map in your bundle (after the exploit-pattern catalogue, before any known findings) is produced by pattern matching (a script, with any `?` cells completed by the orchestrator). Its **Review leads** table points at suspicious spots — an authority written with no signer, a key compared against stored data with no `is_signer` (`key-compared-no-signer`), an `UncheckedAccount` with no `/// CHECK`, a PDA whose seeds lack a user key, a caller-chosen bump, a hand offset that misses the struct layout (`offset-mismatch`), a CPI to a non-constant program, unvalidated `remaining_accounts`. Global singletons are folded: one `singleton-init` lead where a constant-seed PDA is created (check who can call it first), one `singleton-write` when nothing in scope creates it, one `global-signer` lead per program for constant CPI signer seeds (check every listed CPI is gated). Start there, but a map line is never a finding: confirm your own exploit path in the source before you report anything, and a clean map is not a clean program.

**A confirmed map lead keeps its own key.** When you confirm a map lead, report it as its own FINDING or LEAD under its own bug class — never fold it into another item on the same function ("also, no signer"). Dedup keeps one item per program, function and bug class, so a lead folded into a missing-owner finding is a missing-signer bug nobody reports. This matters most for `no-signer`, `authority-not-signer` and `key-compared-no-signer` on native handlers, read paths included: a handler that authorizes the caller by comparing a key with stored data authenticates nobody without `is_signer`, whether or not it writes state.

## The Solana threat model — hold it for every instruction

- **The caller picks every account.** Any account list and any instruction data can be sent by anyone, in any order, as often as they like. The client, the SDK and the frontend are not guards.
- **Instructions compose.** An attacker puts any instructions — yours, other programs', their own program's — before and after yours in one transaction. Intermediate state between two of your instructions is visible to the instruction in between.
- **Anyone can send tokens or lamports to any account.** A balance read from a token account or from `lamports()` is not the program's own record. `lamports()` also includes the rent-exempt minimum. Subtract it before comparing with a tracked reserve (`invariant-agent.md`).
- **Accounts die and come back.** A close that drains lamports but leaves the owner and data in place can be re-funded in the same transaction and used again; a PDA address can be created again after any close (a later `init` / `init_if_needed` succeeds).
- **The runtime does protect some things.** A program cannot debit or write an account it does not own, a signer must really sign, only the deriving program can sign for its PDA, cross-program reentrancy (A → B → A) is rejected, and a failed instruction rolls back the whole transaction. Do not report what the runtime already prevents.

## Do not report

Admin-only instructions doing admin things (a creator, maker or pool creator acting on funds other users already committed is not an admin — `judging.md` Gate 3, per-instance role) — **except** an honest admin call that cannot be undone or that rewrites value users already accrued (single-step authority transfer, an unbounded setter that bricks the program, a fee / rate / mint / index change with no settle first). That is an honest-admin hazard (`judging.md` Gate 3): report it, name the honest call. **Except** an outsider who makes a privileged, one-shot or time-sensitive instruction fail (pre-creating an account it creates, filling a slot, front-running an init, a lock, a migrate, a finalize or a settle). That is privileged-op griefing (`judging.md` Gate 3, **B26**): report it. The description says an attacker makes the instruction fail, and does not use the word griefing. Standard DeFi tradeoffs (MEV, rounding dust of one base unit in the protocol's favour, the first-depositor case when the program seeds or locks initial shares). A fee, interest or debt term that rounds to zero or in the caller's favour on a path any caller can repeat or split is not dust (`judging.md` Gate 4). Self-harm only when the caller chooses their own wrong account or input and loses only their own tokens. A protocol formula that over-charges or under-charges every user on a path is not self-harm. "The admin or the upgrade authority can take the funds" without a concrete mechanism. Compute-unit micro-optimisations. Bugs only in `#[cfg(test)]` code. A candidate you would drop as "intended", "by design", "expected" or "fine" is not on this list unless a doc comment, a named constant or a spec line states that intent. Those named tradeoffs stay out: they are this list, not a guess about the program. With no such statement, emit the LEAD below.

## Output

Return findings as structured blocks:

FINDINGs have concrete, unguarded, exploitable attack paths. LEADs have real code smells with partial paths — default to LEAD over dropping.

**Correctness defects are FINDINGs, not LEADs.** When the code **proves** that an instruction fails for every caller, that a constraint is always true or never true, that a hand offset misreads the struct layout, that a two-leg route accepts the same mint or account on both legs (no `from != to`), or that a settings field an update input carries is never assigned while later logic reads it (`asymmetry-agent.md`), emit a FINDING with `bug_class` naming the defect and `proof:` quoting the line and the value, type or layout that makes it wrong. No attacker is needed; `judging.md` Gate 4 scores it in the correctness lane. Do not park it as a lead because "nobody profits". A proven fee-base mismatch, a jump in a phased formula, or a `lamports()` check that skips the rent floor is the same kind of defect when it pays no one (`math-precision-agent.md`, `numerical-gap-agent.md`, `invariant-agent.md`).

**A design guess is a LEAD, not a drop.** When a correctness or economic candidate looks intended, by design, expected, like self-harm or fine, drop it only when a doc comment, a named constant or a spec line states that intent. If the proof is in the code (two fee bases, two boundary values, a reserve check that skips the rent floor, a settings field never assigned), emit the FINDING. If you will not call it a finding, and the source does not state the intent, emit a LEAD. Its `description:` states the assumption (`assumes the fee is meant to be charged on the full input even when the fill is capped`). Never emit nothing. A protocol formula that over-charges or under-charges every user on a path is not self-harm. Self-harm is only the caller choosing their own wrong account or input and losing their own tokens. The tradeoffs named under Do not report stay dropped: they are that list, not a guess about this program.

**A stub is not a defence.** A privileged instruction whose body is only `msg!(..)` / `Ok(())` behind a broken access check is still a FINDING: describe the impact its name and accounts state (`emergency_withdraw` drains the vault), and say `Stubbed: impact as named.`

**A bug that hides another bug is not a defence.** When the only thing that stops your path is a second defect you also report — a value that is never written, a constraint that can never pass, an offset that misreads the layout — emit both. Write the hidden one as its own FINDING whose `proof:` assumes the other is fixed and names it (`masked by contribute|missing-amount-write`). An empty stub body is not such a defect: the stub rule above covers it. Do not demote it because "it pays 0 today": the developer applies the first fix, and the hidden path opens (`judging.md` Gate 1).

**Hardening gaps are LEADs, not silence.** A missing defensive check with no exploit path today is still worth one line: a layout version byte that is written but never checked on read, a discriminator or type tag whose valid value equals zeroed memory (`0`), a second loader for an account type that skips the validation the main loader does, an owner check that exists only because a PDA derivation implies it, a program ID compared nowhere because only one program can own the account today. Emit each as a LEAD with `bug_class` starting `hardening-` (`hardening-version-unchecked`) and say in `description:` what a future change would make exploitable. Never a FINDING, never dropped; `judging.md` never promotes them.

**Every FINDING must have a `proof:` field** — concrete values, traces, account lists or state sequences from the actual code. No proof = LEAD, no exceptions.

**One vulnerability per item.** Same root cause = one item. Different fixes needed = separate items.

```
FINDING | program: name | function: func | bug_class: kebab-tag | group_key: Program | function | bug-class
path: attacker transaction (accounts passed, instruction data) → instruction → state change → impact
proof: concrete values/trace demonstrating the bug
description: one sentence
fix: one-sentence suggestion

LEAD | program: name | function: func | bug_class: kebab-tag | group_key: Program | function | bug-class
code_smells: what you found
description: one sentence explaining trail and what remains unverified
```

The `group_key` enables deduplication: `Program | function | bug_class`. Agents may add custom fields.

## Language — MANDATORY

**Your `description:` and your `fix:` sentence are written in Simplified Technical English.** The
rules follow these ones in your bundle, under the heading "Report language". Read them, and
obey them in every finding and every lead you emit.

Your `description:` is what the report prints. Nothing downstream rewrites it into plain
English for you — the orchestrator pastes it into the report and the report goes to the
developer who must fix the code. One sentence, twenty-five words or fewer, active voice, no
`-ing` clause, no metaphor. Name who acts and what they get.

The rule reaches the wording and never the data. Your `bug_class` label, your `group_key`, the
program, instruction, account and function names, and every line of code you quote are written
exactly as the source and the dedup rules require. `report-language.md` says which is which.

Your `path:` and `proof:` fields are working notes, not report text. Keep them concrete;
concrete is already plain.
