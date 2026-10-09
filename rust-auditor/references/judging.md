# Finding Validation

Every finding passes four sequential gates. Fail any gate → **rejected** or **demoted** to lead. Later gates are not evaluated for failed findings.

You are not defending the code. The job of these gates is to verify the attacker's claimed exploit actually fires end-to-end — anything that interrupts the attack between the attacker's transaction and the harm means the agent's claim does not execute, and only then does it fail to qualify as a finding.

## Gate 1 — Attack execution

Trace the agent's claimed attack path from the attacker's transaction to the harm. Read every guard that sits on that path: Anchor account types (`Account<'info, T>`, `Signer`, `Program<'info, T>`, `Interface`, `InterfaceAccount`, `Sysvar`), Anchor constraints (`has_one`, `address`, `owner`, `seeds` + `bump`, `constraint = …`, `token::mint`, `token::authority`, `associated_token::*`), `require!` / `require_keys_eq!` and explicit checks in the handler, and native checks (`is_signer`, `owner == program_id`, key comparisons). Then the runtime rules nothing in the program can turn off: an account the program does not own cannot be written or debited by it, a signer must really sign, a PDA can only be signed for by its own program, and a failed instruction rolls back the whole transaction. Confirm that none of these interrupts the attack before the exploit step fires.
- A specific guard / constraint / runtime rule on the attack path interrupts the claimed exploit step before harm occurs (quote the exact line or rule and trace it) → **REJECTED** (or **DEMOTE** if a related code smell remains)
- The supposed interruption is speculative ("the client always passes the right account", "the frontend derives the PDA", "the admin would set X", "nobody would build that transaction") → **clears**, continue. **The client is not a guard.** Any account list and any instruction data can be sent by anyone.
- The only interruption is **another defect this pass scores as a FINDING that prints a Fix** (confidence ≥ 75, not a partial-path completion) — a value that is never written (a refund pays 0 because the deposit never records the amount), a constraint that can never pass, a derived address that can never match — and that finding's own **Fix** removes it → **clears**. **A bug is not a guard:** the developer applies the Fix this report prints, and the path then fires. Gate the candidate as if that Fix were applied, deduct **-10** on top of any other deduction, and end its Description with one sentence that starts `This path works after` and names the masking defect (`This path works after contribute records the amount.`). The same holds when the blocking defect is a FINDING that prints no Fix (below 75, or a partial-path completion), only a LEAD, or the gate rates it UNCERTAIN: `UNCERTAIN = ALLOWS` lets the path through; it does not erase the blocker or its deduction. In each of those cases cap the candidate at **75**: this report prints no Fix that opens its path. A masked path that also needs a second finding's bug left in place (it enters through that finding's missing check) takes a further **-10**. One level only: a candidate masked by a finding that is itself masked stays a LEAD. A privileged instruction's stub body (only `msg!(..)`, `Ok(())` or a `// TODO`) is not a blocker under this rule: Gate 4, stubbed impact, scores it alone. A real guard — an account type, a constraint, a `require!`, a runtime rule — still rejects or demotes.

## Gate 2 — Reachability

Prove the vulnerable state exists in a live deployment.

- Structurally impossible (enforced invariant or runtime rule prevents it) → **REJECTED**
- Requires privileged actions outside normal operation → **DEMOTE**
- Achievable through normal usage, through instructions composed in one transaction, or through common mint behaviors (Token-2022 transfer fees and hooks, freeze authority, a mint closed at zero supply and re-created at the same address) → **clears**, continue

## Gate 3 — Trigger

Prove an unprivileged actor executes the attack.

- Only a trusted role can cause the harm (admin, upgrade authority, a whitelisted keeper) → **DEMOTE** (except an **honest-admin hazard**, and except **privileged-op griefing**, both below). An outsider who makes the trusted instruction fail is the trigger. The trusted caller is the victim.
- An unprivileged actor triggers profitably, or makes a privileged instruction fail, stall or behave differently → **clears**, continue

**Admin-action findings — reject unless an unprivileged amplifier is named.** This applies ONLY to harm the admin, the config authority or the upgrade authority causes, NOT to unprivileged attacker actions and NOT to harm an outsider inflicts on a privileged path. If the harm requires the admin acting maliciously or against documented intent, **REJECT** — do not even emit as a LEAD (stricter than the DEMOTE above). The finding clears only when the body names a concrete unprivileged amplifier:

- **race** — the admin sets X mid-flow; an unprivileged user exploits the window, for example in the same slot, before the update reaches every account that caches X.
- **retroactive sweep** — an admin update rewrites a pending value already credited.
- **asymmetric formula** — admin output chains into a formula an unprivileged actor profits from.
- **access gap** — a missing `Signer`, a missing owner or `has_one` check, a tautological check (`constraint = config.admin == config.admin`), an `initialize` anyone can call first, or an upgrade-authority check that reads a spoofable account (the access mechanism itself is the bug).
- **privilege passthrough** — the program forwards a user's signer, or a writable account the user owns, in a CPI to a program the **user** did not choose: a hook or plugin the admin stored in config, a program named by a mint extension or a pool, a program the caller supplies. The admin picks the program, but the defect is that the user's authority reaches it — that is an access gap, not an admin action, and it clears even when the hook is admin-set (pattern **B24**). Token-2022's own transfer-hook CPI passes every account read-only and without signer privilege; a hook that receives less than the user's signature is not this amplifier.
- **privileged-op griefing** — an actor other than the privileged caller makes a privileged, one-shot or time-sensitive instruction fail, stall or behave differently. The means are: pre-creating or pre-funding an account the instruction creates (a PDA, or an account a CPI creates in another program that does not require the owner's signature — pattern **B26**), filling a fixed slot or a capacity, front-running an init, a lock, a migrate, a finalize or a settle, or exhausting a one-shot resource. The instruction being admin-gated does not demote this. The description says an attacker makes the instruction fail, and does not use the word griefing (`report-language.md`). Gate 4 scores the impact: a migration, lock or settlement that stays blocked, so funds are stranded or the protocol stops, is material; a failure the caller can retry on the next slot, with nothing stranded, is **DEMOTE**.

No amplifier named → **REJECTED**. Amplifier named → judge it on that unprivileged path.

**A per-instance role is not an admin.** The admin rules above cover the protocol's trusted operators — the config authority, the upgrade authority, a whitelisted keeper. A creator, maker, pool creator or vault manager that **anyone becomes by creating an instance** is a party to that instance, not a trusted operator. When that role takes or locks funds other users **already committed** through a check that is missing or broken (a withdraw with no deadline or goal check, a one-time setter whose lock never engages so it can change a term again after deposits), the role is the attacker and gate 3 clears with no amplifier. A missing range check on a value the role sets once (a deadline of `u64::MAX`, a fee of 100 %) is input validation, not theft: when users commit before that value exists, it is a FINDING at the correctness lane's fixed 75 (a Low); otherwise the creation-time rule below applies. A parameter the role fixes **at creation**, which users can read before they commit (a goal of 0, a distant deadline set in `create`), is the users' informed choice: a missing bound there is a `hardening-` LEAD, never a finding and never a silent drop.

**Honest-admin hazard — the one admin case that needs no attacker.** The rule above rejects an admin who acts **against intent**. It does not cover an admin who makes **one honest call the instruction offers**, when the code turns that call into harm nobody can undo. Two shapes clear gate 3 with no amplifier:

- **irreversible** — one call that cannot be taken back: a single-step authority transfer that takes effect at once, so a typo, a PDA or a program ID as the new authority loses the role forever (pattern **B14**); a setter with no bounds that bricks the program (a fee of 100 %, a zero divisor, a pause with no unpause path); a mint, vault or oracle switch that strands the balances held under the old one.
- **retroactive** — one call that rewrites value users already accrued: a fee, rate or index change applied without first settling the accrual under the old value (no `sync` before the write); a mint or index switch that keeps the old stored index.

Score it on the honest path: deduct **-10** (it requires the admin call) and **-15** more when the harm is bounded. **Bounded here also means recoverable**: users can still leave by another path (withdraw or close still works under the bad value), or the admin can recover by creating a fresh instance or account that users move to. A config value that simply has no update instruction ("X cannot be changed after creation") is bounded in this sense unless the fixed value locks funds with no exit — and when nothing is lost and nobody is blocked, it is a `hardening-` LEAD, not a finding. This keeps an honest-admin hazard below an unprivileged theft at the same certainty. The Description names the honest call and says why it cannot be undone, or which accrued value it rewrites. **Not this lane:** a two-step transfer (propose, then accept), a bounded setter, a change that applies only forward, or harm that needs the admin to pick a bad value on purpose — those stay **REJECTED** by the rule above.

## Gate 4 — Impact

Prove material harm to an identifiable victim.

- Self-harm only — the caller chooses their own wrong account or input and loses only their own tokens → **REJECTED**. A protocol formula that over-charges or under-charges every user on a path is not this case. Do not label that formula self-harm.
- Dust-level, no compounding (a few lamports, one base unit of a token) → **DEMOTE**. **Not dust:** a fee, interest or debt term that rounds to **zero**, or rounds in the caller's favour, on a path any caller can repeat or split — the loss grows with the number of calls. Score it through the gates with **-15** (bounded).
- Material loss to an identifiable victim — tokens or lamports taken from a vault or another user, an account taken over, a mint inflated, an instruction that fails for every caller so funds stay locked, a migration, lock or settlement that stays blocked so funds are stranded or the protocol stops (Gate 3, privileged-op griefing), permanent loss of control of a privileged role (no signer can ever call the admin instructions again) → **CONFIRMED**
- Privileged-op griefing the caller can retry on the next slot, with no funds stranded → **DEMOTE**

**Stubbed impact.** A privileged instruction whose body is a stub — only `msg!(..)`, `Ok(())` or a `// TODO` — still has a name and an account list that state its impact (`emergency_withdraw` with the vault and a destination, `set_admin`, `sweep_fees`). When the **access** defect itself clears gates 1–3 (a missing `Signer`, a missing `has_one`, an `initialize` anyone can call first), judge the impact by what the name and the accounts say the instruction does: the stub is shipped code, and the next upgrade fills it in behind the same broken gate. Deduct **-15** (the harm cannot run today) and write `Stubbed: impact as named.` in the Description. A stub with no access defect is not a finding. Do not reject the access defect because "the function does nothing yet".

**Correctness lane — objectively wrong code with no attacker.** Some defects have no attacker and no victim loss, yet the code is provably wrong and the developer must fix it:

- an instruction that **fails for every caller** — a check that compares a wallet with a token account, `destination == caller` where `destination` must be a token account, a derived address that can never match;
- a constraint that is **always true or never true** (a tautology, a comparison of a value with itself, a bound no input can meet);
- a hand-coded **byte offset that misreads the struct layout** (`data[1..33]` read as the owner key when `#[repr(C)]` places the key at 16..48);
- a **two-leg route** (swap, transfer, migrate) that accepts the same mint or the same account on both legs — no `from != to` check — so a same-asset round trip runs through the accounting (pattern **B17**).

When the proof is in the code — quote the line, and the layout, value or account type that makes it always fail or always pass — it is a **FINDING at fixed confidence 75** with a **Fix** block, not a lead, and the deductions above do not apply. The title starts with `Correctness:`. Gates 2 and 3 do not apply (there is no attacker to find); gate 1 still applies — trace that the failure really happens on every call. **If the same defect also locks funds or pays an attacker, it is not in this lane:** score it through the four gates (an instruction that fails for every caller so funds stay locked is already **CONFIRMED** above, and a same-asset round trip that credits value is a normal finding).

The same split covers a proven formula or comparison defect. In this lane when nobody is paid and nothing is stranded; through the four gates when the wrong value pays a caller or strands funds:

- a fee or rate computed on amount X while the applied amount on that branch is Y ≠ X (`math-precision-agent.md`, fee-base consistency);
- a formula in phases (slot, timestamp, utilisation, supply, tier) that jumps or leaves a gap at a boundary (`numerical-gap-agent.md`, piecewise continuity);
- a `lamports()` check that compares the raw balance with a tracked reserve without subtracting the rent-exempt minimum, so it passes while the balance above rent is short (`lamports() >= tracked`, `invariant-agent.md`). Not this case: a checked debit of a tracked total that excludes the rent by construction (balance = rent + tracked) — it reaches the floor only when another defect inflates the total, that finding owns the harm, and the runtime already rejects a non-zero balance left below rent;
- a settings field that an update-input struct carries and the setter never assigns, or that the update path skips while it writes the sibling fields, while later logic reads it (`asymmetry-agent.md`, setter completeness).

Two more cases set the edges of this lane:

- **Stranded rent.** A per-user account the program creates with a user-paid `init` / `init_if_needed` (a contribution record, a position, a ticket, an order) whose role ends — amount zeroed, campaign withdrawn, order filled — while no instruction closes it and returns its rent. It stays in this lane at 75 although lamports stay locked: the loss is the payer's own rent, fixed per account. Not this case: an account that later logic relies on existing (a claim receipt, nonce, vote or "used" marker whose close allows a replay, `invariant-agent.md`), or one the source says is kept.
- **Boundary overlap.** Two instructions whose time or slot windows overlap, or leave a one-unit gap, at the same timestamp (both accept the boundary value, or both reject it — with `deadline < now` as the error check in one and `deadline > now` in the other, neither error fires at `now == deadline`, so both run) are in this lane only when an action inside that unit changes what the other instruction pays or counts, compared with the same actions one unit before and one unit after the boundary. When it does not — the same sequence off the boundary gives the same result, or the harm comes from another finding's defect — the overlap adds nothing: emit a LEAD. Multi-agent convergence does not promote it: the agents agree on the overlap, not on a harm, and the off-boundary comparison above already shows there is none.

## Design-guess demotion

Do not **REJECT** a correctness or economic candidate because it looks intended, by design, expected, like self-harm, or fine. Those words are a reason to drop it only when a doc comment, a named constant or a spec line states that intent. A proven defect stays a finding: the correctness lane, or the four gates when it pays a caller or strands funds. **Self-harm needs no source statement:** when the trace proves that only a party's own input creates the state, only that party loses, and the missing check would leave the same outcome, the candidate stays rejected (a `hardening-` LEAD if a check is missing) — never the correctness lane. When you will not score it as a finding, and the source does not state the intent, **DEMOTE** to a LEAD and put the assumption in `description:` (`assumes the fee is meant to be charged on the full input even when the fill is capped`). Never delete it. A formula that mis-charges every user on a path is not self-harm (Gate 4). Items named in **Do Not Report** below, and the standard tradeoffs named in `shared-rules.md` (MEV, rounding dust, a seeded first depositor), stay out: they are that list, not a guess about this program.

## Confidence

Start at **100**, deduct: partial attack path **-20**, bounded non-compounding impact **-15**, requires specific (but achievable) state **-10**. Confidence ≥ 75 gets description + fix. Below 75 gets description only.

**The threshold is 75, and it is set here.** `report-formatting.md` reads it from this line and states it nowhere else. It is 75 and not 80 because the lead-promotion rules below land a promoted lead at exactly 75 (all but a cross-program echo, which joins the finding it echoes and takes that finding's confidence): at a threshold of 80 every multi-agent convergence and every correctness defect would be promoted to a finding and then printed with no **Fix** block (a completed partial path is printed without one by design). The **correctness lane** (Gate 4) is fixed at 75 for the same reason: the report has no severity field — confidence is its only rank — so 75 is the lowest rank that still prints a **Fix**, which is where a Low/Info defect belongs. Moving this number means moving those rules, the lane (and the two cases set at the lane's 75: Gate 3's per-instance range check and Gate 4's stranded rent) and the Gate 1 cap on a masked candidate, or the promotions stop being worth making.

**Integer overflow depends on the Build context.** Read `Release overflow checks` at the top of `source.md`. The setting is **per workspace**: when the line says `differs per workspace`, use the root that lists the crate under review (a nested or excluded workspace is built with its own `[profile.release]`). When it is **not set** or **OFF**, `+`, `-` and `*` on integers wrap silently in the deployed program and an overflow finding is scored like any other value bug. When it is **on**, the same overflow panics and the transaction fails, so the impact is that the instruction fails for that input — score it as a denial of service, not as a wrong value, unless the panic blocks other users' funds. `as` casts truncate and `wrapping_*` wraps **in every build**, whatever the setting.

## Safe patterns (do not flag)

- `checked_add` / `checked_sub` / `checked_mul` / `checked_div` with the `None` case returned as an error (but verify a `.unwrap()` on it is not a panic an attacker can reach to block other users)
- Plain arithmetic when the Build context says release overflow checks are **on** (it panics, it does not wrap) — but `as` casts and `wrapping_*` still wrap
- `u64::try_from(x)?`, `x.try_into()?` (checked narrowing)
- Anchor `Account<'info, T>` for owner + discriminator, `Signer<'info>` for the signature, `Program<'info, T>` for the program ID, `Sysvar<'info, T>` for the sysvar address, `InterfaceAccount` / `Interface` for an owner or program in the allowed set — for exactly what each one checks and nothing more (an `Account<TokenAccount>` proves it is a token account, not **which** token account)
- `seeds` + `bump` constraints that use the canonical bump (`bump` in an `init`, or a stored `bump = state.bump` that was written from `ctx.bumps` / `find_program_address`)
- `init` (not `init_if_needed`) for accounts that must be created once
- Anchor `close = target` in a framework version that also zeroes the data and reassigns the account (verify the version in the Build context before you call a close safe)
- `transfer_checked` with the mint and its decimals; `get_price_no_older_than` with a bounded age and a checked feed ID
- `load_instruction_at_checked` / `get_instruction_relative` / `Sysvar<'info, Instructions>` for instruction introspection — when the loaded instruction's program ID and data are compared and the index cannot be shifted by a prepended instruction (these APIs prove only that the account is the real sysvar)
- Two-step authority transfer (propose, then accept by the new authority's signature)
- Constant-product and share-of-supply math done entirely in raw base units (`sqrt(a * b)`, `lp * reserve / supply`, `x * y = k`) — it is scale-invariant, so mints with different decimals do not break it. Missing decimal normalisation is a finding only where a hardcoded scale, a cross-asset value comparison or an oracle price mixes units
- A checked direct lamport debit (`sub_lamports`, or `**info.try_borrow_mut_lamports()? = info.lamports().checked_sub(x).ok_or(..)?`) from an account this program owns — it is the required way to pay SOL out of a program-owned account, because `system_program::transfer` debits only a System-owned `from` that carries no data
- Consistent protocol-favoring rounding unless compounding or zero-rounding — **but confirm the rounding really happens**: `f64` is not exact (`(x as f64 * 10f64.powi(k)).floor()` rounds to the nearest representable value once the product passes 2^53, so a "round down" can round up; `.ceil()` on an already-rounded float can land one unit low), an integer `a / b * c` floors before it scales, and a "round up" written as `(a + b - 1) / b` overflows on large `a` when overflow checks are off

## Proof-of-concept verification (`--poc` only)

**Skipped entirely without `--poc`.** When the flag is on, every finding the gate scored
**High/Critical** (confidence ≥ 90) is verified by building and running one regression test, per
`poc-guide.md`. The run attaches exactly one label, and the label feeds this file's verdict and
the report:

- **CONFIRMED** — a test demonstrated the finding's own claim (the attack fired, the harm
  occurred). Keep the finding; **confidence is unchanged** — a PoC proves reproducibility, it does
  not raise a number the gate already set, and nothing goes above 100. The test is kept as a
  regression test for the developer.
- **NOT REPRODUCED** — a faithful test built and ran and the bug did **not** occur (the guard
  held, the attack was rejected). Treat this as strong evidence of a false positive and **demote
  the finding to a LEAD**, with a one-line note of what the test did and what blocked it. Do not
  delete it silently: a NOT REPRODUCED lead tells the developer the skill checked.
- **UNVERIFIED** — no faithful test could be built or run inside the budget (missing toolchain,
  the harness could not model the state, an unrelated build failure, or the budget ran out).
  **Keep the finding at its gated confidence** — UNVERIFIED means "not checked", never "disproven".

The label never overrides a gate verdict in the other direction: a gate REJECT is already gone
before PoC runs, and PoC verifies only what survived all four gates. A Medium, a low or a lead is
never PoC-verified — the budget goes to the findings that matter most.

## Lead promotion

Before finalizing leads, promote where warranted. **`hardening-` leads are never promoted** — no rule below applies to them: they name a missing defence with no path, and convergence of several agents on one does not make a path.

- **Cross-program echo.** Same root cause confirmed as FINDING in one instruction or program → promote every instruction and program where the identical pattern appears (the same unchecked account type taken by another instruction, the same seeds used by another PDA), **folded into that finding**: its site joins the Fix and its function is named in the Description (`dedup-and-assembly.md`, Turn 4 step 3); when that finding prints no Fix block (below 75, or a partial-path completion), name the site in its Description only. One root cause is one item. **Match on the code, not the label:** the same expression — `div_floor` on a fee, an unchecked `as u64` on a quotient, the same missing constraint — in a sibling instruction is the same root cause under any `bug_class`. Echo only to an instance whose inputs can reach the same failure: a cast the math already bounds (a pro-rata payout that cannot exceed the reserve, `sqrt` of the product of two `u64`) is not the pattern.
- **Multi-agent convergence.** 2+ agents flagged the same (program, function, bug class), at least one of them filed it as a FINDING with a `proof:`, and the gate demoted it (not rejected) for a reason that is not a real guard → promote to FINDING at confidence 75. A LEAD that every agent raised only as a LEAD is not promoted by count: agreement on an unproven path is not proof. Convergence does not undo a design-guess demotion or a harmless boundary overlap (Gate 4).
- **Correctness defect parked as a lead.** A lead whose only missing piece is an attacker or a victim, while the code proves an instruction that fails for every caller, a wrong constraint, an offset that misreads the layout or a missing `from != to` → move it to the **correctness lane** (Gate 4): FINDING at confidence 75 with a **Fix** block.
- **Partial-path completion.** Only weakness is incomplete trace but path is reachable and unguarded → promote to FINDING at confidence 75, **description only — a deliberate exception to the threshold**. 75 clears the line, so this finding would otherwise carry a **Fix** block; it does not, because the trace it would fix was never completed. Multi-agent convergence takes its **Fix** block normally, and so does a correctness-lane finding; a cross-program echo adds its site to the Fix of the finding it joins, or only to its Description when that finding prints no Fix block.

## Leads

High-signal trails for manual investigation. No confidence score, no fix — title, code smells, and what remains unverified.

## Do Not Report

Clippy lints, compiler warnings, compute-unit micro-optimisations, naming, doc comments. Admin privileges by design (but an honest-admin hazard — Gate 3 — is not "by design", and privileged-op griefing is not an admin privilege). Missing `emit!` events or `msg!` logs. Centralisation without an exploit path — "the upgrade authority can replace the program" is not a finding unless the upgrade authority itself is unprotected. EVM-only classes the Solana runtime prevents: cross-program reentrancy (the runtime rejects A → B → A; only direct self-recursion is allowed). Implausible preconditions (but Token-2022 mints with transfer fees, transfer hooks, a permanent delegate or a freeze authority, mints with unusual decimals, and accounts closed and re-created at the same address ARE plausible for programs that accept any mint or any account). A guess that a formula or a check is intended, with no doc comment, named constant or spec line that says so, is not on this list: demote it and state the assumption (design-guess demotion).
