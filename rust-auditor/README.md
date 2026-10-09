# Rust Auditor

A security agent for Solana programs written in Rust - findings in minutes, not weeks.

Covers Anchor, native `solana-program` and Pinocchio programs. It runs the same engine as the
[solidity-auditor](../solidity-auditor/) - 12 parallel attacker agents, dedup, a four-gate judge,
loop mode and a findings memory - with every agent rewritten for the Solana account model.

Two things are specific to Solana:

- **Account map.** Before the agents run, a script maps every instruction - its accounts and their
  signer / owner / PDA constraints, its cross-program calls and the state it writes - and highlights
  review leads such as an authority written with no signer check or a CPI to a program ID that is
  not pinned. On native and Pinocchio code it follows checks made in helpers and in typed account
  constructors, so they do not raise false leads.
- **Exploit patterns.** Every agent carries a catalogue of real Solana incidents (Wormhole, Cashio,
  Crema, Mango, Loopscale and more), published bug classes and lessons from public audit reports,
  each with its source, mapped to the agent that hunts it.

Built for:

- **Solana devs** who want a security check before every commit
- **Security researchers** looking for fast wins before a manual review
- **Just about anyone** who wants an extra pair of eyes.

Not a substitute for a formal audit - but the check you should never skip.

## Usage

```
Install https://github.com/pashov/skills/ and run rust auditor on the codebase
```

```
run rust auditor on *specified files*
```

```
update skill to latest version
```

More than one run per scan is loop mode. Each run is a full audit, and every run after the first is
told what the earlier ones found, so it hunts new ground instead of the same bugs. You get one
report at the end, not one per run.

```
run rust auditor in loop mode
```

## Verify the real bugs (`--poc`)

Pass `--poc` and, after judging, the skill tries to **prove** each High/Critical finding by writing
and running a regression test in a scratch copy of your project. A bug that reproduces ships with a
failing test you can keep (`PoC: CONFIRMED`); a finding that can't be reproduced drops to a lead
(`PoC: NOT REPRODUCED`), so false positives fall out of the findings list. If the build toolchain
isn't installed it says so rather than guessing (`PoC: UNVERIFIED`). It writes only under
`.rust-auditor/runs/{stamp}/poc/` and **never touches your source or tests**. A plain scan runs no
builds and is unaffected.

```
run rust auditor with --poc
```

## What it scans

By default, the `.rs` files of every on-chain program crate - a crate whose `[dependencies]`
name `anchor-lang`, `solana-program`, `pinocchio` or a related framework crate - plus Rust
deploy and admin scripts under `scripts/`, `script/`, `deploy/`, `admin/` and `src/bin/`. It
skips `target/`, `.anchor/`, `node_modules/`, `vendor/`, `test-ledger/`, `migrations/`, tests,
benches, examples, fuzz harnesses, `client/` / `sdk/` / `cli/` directories and off-chain client
crates (RPC crates under `[dev-dependencies]` or a host-only `cfg(not(target_os = "solana"))`
table do not make a program a client). Name any file on the command line to scan it anyway,
including TypeScript deploy scripts.

The account map needs Python 3 (standard library only). Without it the scan still runs, with no
map.

Every agent also sees a **Build context** header: which framework each crate uses, the exact
framework versions, and whether release builds have `overflow-checks` on (Cargo's release
default is off, so integer overflow wraps in the deployed program). The setting is resolved
**per workspace**: a nested or `exclude`d workspace is reported with its own value.

## The 12 agents

| # | Agent | Focus |
| - | ----- | ----- |
| 1 | math-precision | Wrapping arithmetic without `overflow-checks`, `as` truncation, rounding direction, decimals, share inflation |
| 2 | access-control | Missing signers, init front-running, PDA authorities that sign for anyone, signer forwarding through CPI |
| 3 | economic-security | Pyth / Switchboard staleness and spoofing, Token-2022 extensions, flash loans, address squatting, compute exhaustion |
| 4 | execution-trace | Stale accounts after CPI, write-back clobbering, duplicate accounts, instruction composition and introspection |
| 5 | invariant | Conservation laws, donation, closed-account revival and re-creation, rent and `realloc` |
| 6 | periphery | Validation helpers, layouts and deserialisation, `unsafe`, feature-flagged checks, hardcoded IDs |
| 7 | first-principles | Assumptions with no name - identity, ordering, freshness, existence |
| 8 | asymmetry | Paired instructions, Accounts-struct constraint diffs, Token vs Token-2022 and SOL vs SPL branches, settings fields a setter never writes |
| 9 | account-validation | Every account of every instruction against eleven questions, every CPI, `remaining_accounts`, instruction data |
| 10 | numerical-gap | Seams between precision, invariants and edges, including a fee base that changes on a capped fill |
| 11 | trust-gap | Seams between access, economics and asymmetry |
| 12 | flow-gap | Seams between execution, external programs and program intent |

## Tips

- **Target hot programs.** Rather than scanning an entire repo, point the tool at the instruction files you're actively changing - plus `state.rs` and the `lib.rs` that dispatches them. Smaller scope means denser context for each agent and higher-signal findings.
- **Use loop mode.** LLM output is non-deterministic — each pass can surface different vulnerabilities. Three passes is a good default: the later ones know what the earlier ones found, and you still get a single report.
- **Read the report file.** Long scans print a short summary in the terminal; every finding and its fix is in `full-report.md`.
- **Benchmarks.** `evals/` lists public Solana codebases and audit reports with documented bugs, so a run can be scored for recall and false positives. Strip comments from a benchmark copy first - educational repos name the bug in a comment (`evals/benchmarks.md`, section 0).
- **Ignore `.rust-auditor/` in git.** Every scan writes its run files there, and `--memory` keeps a findings ledger there.
