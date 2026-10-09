---
name: rust-auditor
description: Security audit of Rust Solana programs (Anchor, native solana-program, Pinocchio) while you develop. Trigger on "audit this program", "audit the Solana program", "check this program", "review this Rust/Anchor code for security", "run rust auditor", "loop mode", "run the rust auditor in loop mode", "run 3 passes". Modes - default (full repo) or a specific filename. Loop mode runs several passes in one scan, each pass told what the earlier ones found, and ends in one combined report; it remembers findings between scans in a ledger.
---

# Solana Program Security Audit

You are the orchestrator of a parallelized security audit of Rust programs that run on Solana — Anchor, native `solana-program`, or Pinocchio.

## Mode Selection

**What is in scope by default:** the `.rs` files of **on-chain program crates** — a crate whose `Cargo.toml` `[dependencies]` names `anchor-lang`, `anchor-spl`, `solana-program`, `solana-program-entrypoint`, `solana-account-info`, `pinocchio*` or `steel`. Shared library crates the programs depend on (a `libs/math` crate on `solana-program`) are program code and are in scope too.

**Exclude pattern:** skip **dependency and build directories** — `target/`, `.anchor/`, `node_modules/`, `vendor/`, `test-ledger/`, `migrations/`, `.git/` — **non-production code** — `tests/`, `test/`, `benches/`, `examples/`, `fuzz/`, `trident-tests/` and files named `*_test.rs`, `*_tests.rs`, `tests.rs`, `test_*.rs`, `build.rs` — and **off-chain client code** — `client/`, `clients/`, `sdk/`, `cli/`, and any crate whose `[dependencies]` (not `[dev-dependencies]`) names `solana-client`, `solana-rpc-client*`, `anchor-client`, `clap`, `tokio` or `reqwest`. A crate with none of the on-chain dependencies above is not a program and is skipped.

**`#[cfg(test)]` modules are out of scope even inside an in-scope file.** The file is scanned because its production code is; a `mod tests` block inside it is read for context and never reported. `shared-rules.md` tells the agents the same.

**Deploy and admin scripts stay in scope.** Rust under `scripts/`, `script/`, `deploy/`, `admin/` or a crate's `src/bin/` is audited like any other code, even when it depends on RPC crates: an init or admin script picks the config values, hands over the upgrade, mint and admin authorities, and seeds state, and it carries real bugs. Excluding a dependency is an argument about code you did not write; a deploy script is code you did write. Deploy scripts written in TypeScript (`migrations/deploy.ts`, `scripts/*.ts`) are not `.rs` and a default scan does not discover them — name them on the command line to scan them.

- **Default** (no arguments): scan all in-scope `.rs` files. Use Bash `find` (not Glob), exactly this command:

  ```bash
  find . -type f -name '*.rs' \
    -not -path '*/target/*' -not -path '*/.anchor/*' -not -path '*/node_modules/*' \
    -not -path '*/test-ledger/*' -not -path '*/migrations/*' -not -path '*/.git/*' \
    -not -path '*/vendor/*' -not -path '*/tests/*' -not -path '*/test/*' \
    -not -path '*/benches/*' -not -path '*/examples/*' -not -path '*/fuzz/*' \
    -not -path '*/trident-tests/*' -not -path '*/client/*' -not -path '*/clients/*' \
    -not -path '*/sdk/*' -not -path '*/cli/*' \
    -not -name '*_test.rs' -not -name '*_tests.rs' -not -name 'tests.rs' \
    -not -name 'test_*.rs' -not -name 'build.rs' \
  | sort | while IFS= read -r f; do
    case "$f" in */scripts/*|*/script/*|*/deploy/*|*/admin/*|*/src/bin/*) echo "$f"; continue ;; esac
    d=$(dirname "$f")
    while [ ! -f "$d/Cargo.toml" ] && [ "$d" != "." ] && [ "$d" != "/" ]; do d=$(dirname "$d"); done
    [ -f "$d/Cargo.toml" ] || continue
    deps=$(awk '{ sub(/[[:space:]]*#.*/, "") } /^[[:space:]]*\[/ { s=$0 } s ~ /^[[:space:]]*\[(target\..*\.)?dependencies[].]/ && s !~ /cfg\(not\([^]]*target_(os|arch)[[:space:]]*=[[:space:]]*\\?"(solana|bpf|sbf)/' "$d/Cargo.toml")
    printf '%s\n' "$deps" | grep -qE '(^[[:space:]]*|dependencies\.)"?(anchor-lang|anchor-spl|solana-program|solana-program-entrypoint|solana-account-info|pinocchio[a-z0-9-]*|steel)"?[[:space:]]*[]=.]' || continue
    printf '%s\n' "$deps" | grep -qE '(^[[:space:]]*|dependencies\.)"?(solana-client|solana-rpc-client[a-z0-9-]*|anchor-client|clap|tokio|reqwest)"?[[:space:]]*[]=.]' && continue
    echo "$f"
  done
  ```

  Do not re-derive this command — paste it. Three parts of it are **required, not tidiness**:

  - `-type f` — `cat` on a directory breaks the source build, and a `find` without it matches any directory whose name ends in `.rs`.
  - The `[dependencies]`-only `awk` — a program crate routinely lists `solana-program-test`, `litesvm`, `tokio` or `solana-client` under `[dev-dependencies]` for its tests, or under a host-only `[target.'cfg(not(target_os = "solana"))'.dependencies]` table. Reading the whole manifest would classify every tested program as a client and scan nothing. The `awk` drops `#` comments and host-only target tables (`cfg(not(target_os = "solana"))`, also `target_arch = "bpf"`/`"sbf"`; any other `cfg(not(...))` table, such as `cfg(not(feature = "no-entrypoint"))`, is still read), and the greps match a crate name only in key position (`name =`, `name.workspace`, `[dependencies.name]`), never inside a `features = [...]` list.
  - The walk up to the nearest `Cargo.toml` — a program's instruction handlers live in `src/instructions/*.rs`, several directories below the manifest that says what the crate is.

  **If the command prints nothing**, the repository has `.rs` files but no crate that depends on a Solana program framework. Print `no crate depends on anchor-lang, solana-program or pinocchio — scanning every non-test .rs file`, and re-run the `find` **without** the `| sort | while … done` filter. Do not stop: a program can reach the runtime through a framework this list does not know.

- **`$filename ...`**: scan the specified file(s) only. **The exclude pattern does not apply here.** A file named on the command line is always scanned, wherever it lives — naming `~/.cargo/registry/src/index.crates.io-*/anchor-lang-0.30.1/src/accounts/account.rs` scans that file, and naming `migrations/deploy.ts` scans that script. The pattern chooses what a *default* scan discovers; it never overrides an explicit request.

**Flags:**

- `--file-output` (off by default): **copy** the assembled report into the working directory (name per `{resolved_path}/report-formatting.md`). The flag never causes a report to be produced — every scan assembles `.rust-auditor/runs/{stamp}/full-report.md` whether it is passed or not. It only decides whether a copy lands where the runner can see it.

  > **This rule does not say "never write a report file unless explicitly passed".** The rule protects the runner's **working directory**: without the flag, nothing is written outside `.rust-auditor/`. The report is assembled by shell on every scan, so the flag cannot collapse the report — nothing regenerates, it copies.

- `--memory` (off by default): remember findings between scans in a ledger at `.rust-auditor/memory.tsv` in the audited repo. Any pass count above 1 turns memory on by itself, whether or not the flag was passed.
- `--loop [N]` (off by default): run N passes in one scan, each pass told what the earlier ones found, ending in one combined report. `--loop` with no number is **3** passes. `--loop 1` is a 1-pass scan. The flag exists for runners who prefer flags; when it is passed the picker in Turn 1b does not ask, it obeys.
- `--poc` (off by default): after judging, try to verify each **High/Critical** finding by writing and running a regression test that demonstrates whether the bug is real. Confirmed bugs ship with a failing test; findings that cannot be reproduced drop to leads. It writes only under `.rust-auditor/runs/{stamp}/poc/` and builds in a scratch copy of the repo — **never** the user's source or tests. The full procedure, harness choice, budget and labels (`CONFIRMED` / `NOT REPRODUCED` / `UNVERIFIED`) are in `{resolved_path}/poc-guide.md`. A plain scan without this flag runs no builds and reaches none of this.

**Vocabulary (used throughout this file):**

- **run** — one pass of the 12 agents.
- **scan** — one invocation of this skill. A scan holds 1 or more runs.

The ledger's `scans` column counts scans. The report's `seen in k/N runs` counts runs inside one scan and is never written to the ledger. Two numbers, two names — do not mix them.

The pass count the scan runs is `{passes}` — settled in Turn 1b, 1 or more. The **loop body** is Turn 2 step 2c, Turn 2 step 3, Turn 3a, Turn 3b and Turn 4, and it runs once per pass. Everything before it runs once per scan, and Turn 5 closes the scan once, whatever `{passes}` is.

> **HARD RULE — the plain path must stay plain.** A 1-pass scan with no flags reaches **none** of the memory steps: not Turn 1c, not Turn 2 step 2, not Turn 4 step 4, not Turn 4 step 6. It reads no ledger, writes no memory file, and prints exactly the plain report. Memory is on only when `--memory` was passed or the pass count is above 1. A later editor who is tempted to make any memory step unconditional is breaking this on purpose, not tidying up.

> **A 1-pass answer reaches none of the loop or memory machinery.** No ledger is read or written. No `Passes` or `Memory` row in the Scope table. No `seen in k/N runs`. No `KNOWN` / `NEW` tag. No per-pass summary lines. **The printed report is the plain report** — the shape `report-formatting.md` calls the freeze. The only trace of the picker is the question itself.
>
> **What it does write.** Every scan writes `.rust-auditor/runs/{stamp}/` — one `run-1.md`, one `scope.tsv`, one `full-report.md` — because the report is assembled from those files at every pass count, and `name`, `mode`, `files` and `threshold` are needed by every report. A 1-pass answer **does** create a `.rust-auditor/` directory and `runs/` files; keeping disk untouched was never what the rule was protecting.
>
> **What the rule protects, stated exactly:** on the plain path the scan reads no ledger, writes no `mem_` key, and prints a Scope table of exactly **three** rows — `Mode`, `Files reviewed`, `Confidence threshold (1-100)` — and no `Passes` row, no `Memory` row. The one exception is a scan that lost coverage: it adds a loss row — `Agents` when pass 1 ran fewer than 12 agents, `Run files` when the run files do not add up (`report-formatting.md`). No flag produces it; never remove it to get back to three rows. Disk is not printed output. A later editor who makes a **memory** step unconditional is breaking this on purpose; writing the runs directory is not one of those steps.
>
> `--memory` on a 1-pass run is the single exception: memory turns on, the loop machinery stays off.

## Orchestration

**Turn 1 — Discover.** Print the banner, then make these parallel tool calls in one message:

a. Bash `find` for in-scope `.rs` files per mode selection
b. Glob for `**/references/hacking-agents/account-validation-agent.md` — extract the `references/` directory (two levels up) as `{resolved_path}`. Glob for **this** file and not `shared-rules.md`: the solidity-auditor ships a `shared-rules.md` at the same relative path, and with both skills installed a glob for it returns two directories. `account-validation-agent.md` exists only in this skill.
c. ToolSearch `select:Agent`
d. Read the local `VERSION` file from the same directory as this skill
e. Bash `curl -sf https://raw.githubusercontent.com/pashov/skills/main/rust-auditor/VERSION`
f. Bash `mktemp -d ./.audit-XXXXXX` → store as `{bundle_dir}`
g. Bash `date +%Y%m%d-%H%M%S` → store as `{stamp}`, the scan-time stamp. **One stamp per scan, computed once, here.** The runs directory, the run files and any `--file-output` copy all carry it, so a report and the runs that produced it are tied together by eye.

**Turn 1a — Open the scan directory.** After the `find` returns, in one Bash command:

```bash
mkdir -p .rust-auditor/runs/{stamp}
: > .rust-auditor/runs/{stamp}/scope.tsv
```

Then write the three scope keys this turn knows. **A scope key is written with one `printf` and never any other way:**

```bash
printf '%s\t%s\n' name  "{project-name}" >> .rust-auditor/runs/{stamp}/scope.tsv
printf '%s\t%s\n' mode  "{mode}"         >> .rust-auditor/runs/{stamp}/scope.tsv
printf '%s\t%s\n' files "{file list}"    >> .rust-auditor/runs/{stamp}/scope.tsv
```

- `{project-name}` — the repo root basename, the same one `report-formatting.md` names.
- `{mode}` — `default` or `filename`, as Mode Selection settled it.
- `{file list}` — every in-scope path the `find` returned, **space separated on one line**, in `find` order (the command sorts it). The assembler wraps them 3 per row; the order it prints is the order written here.

> **`scope.tsv` is `key<TAB>value`, append-only, last line per key wins.** An absent key gives an absent table row — that is what keeps the plain scan's Scope table at three rows with no special case (the `Agents` loss row prints only when `pass_1_agents` is not `12/12`). A tab or a newline in a value breaks the row, so values are **stripped**, not escaped: no key here has any use for either character. Six writers across four turns append to this one file, and none of them ever rewrites or deletes a line.
>
> `name` and `mode` are the **only two keys a model types**. Everything else is either shell knowledge or read by the assembler for itself: the threshold from the constant, `N` in `seen in k/N runs` from counting run files, the stamp from the directory's own name.

If the remote VERSION fetch succeeds, compare the two as **numbers** and warn **only when the local one is lower**: print `⚠️ You are not using the latest version. Please upgrade for best security coverage. See https://github.com/pashov/skills`. If it fails, skip silently.

> **Lower, not different.** A plain "differs" test warns the wrong person: somebody working on an unreleased version has a local `VERSION` **above** the published one, and gets told to upgrade to the version they are writing. Local equal to remote, or local above it, prints nothing.

**Turn 1b — Model and pass count.** This turn asks **two questions in one `AskUserQuestion` call**: which model the 12 agents use, and how many passes the scan runs. The runner is interrupted once, before any work starts.

> **The two questions do not fail the same way.** On a runtime without `AskUserQuestion` and an `Agent` tool that takes a `model` parameter — Codex, Gemini, Cursor's native agent — the **model** question is skipped silently, `{agent_model}` is left unset, and no prose replaces it. The **pass** question is not skipped: it falls through to the printed block in Turn 1b-ii, which stops and waits. This turn as a whole is never skipped. A later editor must not restore a blanket "SKIP this turn entirely" rule: it was true when this turn asked one question, and it is false now.

**Turn 1b-i — the `AskUserQuestion` call (Claude Code).** Ask both questions in one call. Where the `Agent` tool takes no `model` parameter, ask the pass question alone.

Question 1 — model:

1. Read your system prompt to detect your own model **family** (Opus, Sonnet, or Haiku). Ignore the version digits — the Agent tool's `model` parameter takes the family name (`"opus"` / `"sonnet"` / `"haiku"`), and the runtime resolves to the latest version in that family.
2. Put this question in the call:
   - Question: `"Which Claude model should the 12 audit agents use?"`
   - Three single-select options. Mark the orchestrator's own family as `(Recommended)` and place it first.
   - On each option, set the `description` field to `latest`.
   - On each option, set the `preview` field verbatim (preserve all whitespace exactly — the box widths must stay equal across all three):

   Opus preview:

   ```
   ┌──────────────────────────────────────────────────────────┐
   │  opus  ·  highest reasoning  ·  most expensive           │
   └──────────────────────────────────────────────────────────┘
   ```

   Sonnet preview:

   ```
   ┌──────────────────────────────────────────────────────────┐
   │  sonnet  ·  balanced reasoning  ·  mid cost              │
   └──────────────────────────────────────────────────────────┘
   ```

   Haiku preview:

   ```
   ┌──────────────────────────────────────────────────────────┐
   │  haiku  ·  lowest reasoning  ·  cheapest                 │
   └──────────────────────────────────────────────────────────┘
   ```
3. Store the runner's choice as `{agent_model}`. If no answer, default to the orchestrator's own model.

Question 2 — pass count. It goes in the **same call**, second:

4. Question: `"How many passes should this audit run? Each pass is a full 12-agent audit, and every pass after the first is told what the earlier ones found, so it hunts new ground. You get one combined report at the end."`

   Three single-select options, `3 passes` first and marked `(Recommended)`. Each carries a `preview` box in this turn's style — the boxes are **60 characters wide, equal to the model picker's**, so two questions in one prompt look like one thing. Set `preview` verbatim, whitespace preserved:

   | Label | `description` |
   | --- | --- |
   | `3 passes (Recommended)` | `~45 min` |
   | `1 pass` | `~15 min` |
   | `5 passes` | `~75 min` |

   3 passes preview:

   ```
   ┌──────────────────────────────────────────────────────────┐
   │  3 passes  ·  each pass hunts new ground  ·  ~45 min     │
   └──────────────────────────────────────────────────────────┘
   ```

   1 pass preview:

   ```
   ┌──────────────────────────────────────────────────────────┐
   │  1 pass  ·  one audit  ·  ~15 min, no ledger written     │
   └──────────────────────────────────────────────────────────┘
   ```

   5 passes preview:

   ```
   ┌──────────────────────────────────────────────────────────┐
   │  5 passes  ·  deepest sweep  ·  ~75 min                  │
   └──────────────────────────────────────────────────────────┘
   ```

   > **These numbers are a floor.** They are wall-clock estimates for 12 agents per pass on
   > Opus over a few thousand lines. Passes 2 and later run slower than pass 1, because the
   > growing `known-findings.md` is appended to all twelve bundles; Anchor programs carry more
   > lines per feature than Solidity (every instruction has an `Accounts` struct), and
   > `source.md` also carries the crate manifests. A smaller model is faster. Quote minutes
   > rather than multipliers — "~3x time" tells the runner nothing about whether to wait or
   > come back after lunch.

5. **Any other number needs no option of its own.** `AskUserQuestion` always adds an **Other** choice with a free-text box, and the runner types their number there. Do NOT add a fourth option reading "your own number" — options are fixed choices, so it could not collect the number and would dead-end.

   Parse the Other answer for the first integer. Below 1 or above 10 → ask once more. A second unusable answer → **1 pass**.

6. Store the answer as `{passes}`. No answer at all → 1 pass.

**Turn 1b-ii — the printed fallback (every runtime without `AskUserQuestion`).** Print this exactly:

```
How many passes should this audit run?

Each pass is a full 12-agent audit. Every pass after the first is told what the
earlier passes found, so it hunts new ground. You get one combined report at the end.

  1) 1 pass    — one audit, about 15 minutes. No findings ledger is written.
  2) 3 passes  — recommended. About 45 minutes.
  3) 5 passes  — deepest sweep. About 75 minutes.

Answer with 1, 2, 3, or any pass count you want.
```

> **STOP here and wait for the runner's answer.** Do NOT choose for them. Do NOT continue to Turn 2 with an assumed pass count. Do NOT start the scan and ask later.
>
> This is the one place in this skill where a question is emitted as prose. Turn 1b forbids prose questions because the model picker has a safe default — the orchestrator's own model. A pass count has no safe default: 1 and 5 differ by 5x in time and in cost, and that is the runner's money. A later editor must not "fix" this by deleting the prose block or by picking a default. If you are reading this and it looks like an inconsistency, it is deliberate.

Answers `1`, `2` and `3` are the three listed choices; any other integer is that many passes. Apply the same bounds as Turn 1b-i step 5 — below 1 or above 10, ask once more, then 1 pass.

**Turn 1b-iii — when the runner already said.** Ask nothing that has already been answered:

| What arrived | What the picker does |
| --- | --- |
| `--loop 5` | Skip the pass question, silently. 5 passes. |
| `--loop` with no number | Skip the pass question, silently. 3 passes. |
| "run 4 passes", "audit this four times" | Skip the pass question, silently. 4 passes. |
| "loop mode", "run it a few times" — a request with no number | **Ask.** They asked for the feature, not for a count. |
| Nothing | Ask. |

Skipping is silent in the first three rows — printing `using 5 passes` back at somebody who just typed `--loop 5` is noise. Skipping the pass question never skips the model question, and the reverse holds too.

**Turn 1b-iv — record the pass count.** However `{passes}` was settled — asked, typed in the prose fallback, or read off a flag — write it once, here:

```bash
printf '%s\t%s\n' passes_planned "{passes}" >> .rust-auditor/runs/{stamp}/scope.tsv
```

This is the `P` in the Scope table's `Passes` row. The `R` — how many passes actually produced a run file — is counted by the assembler from the run files themselves, so a pass that dies before it can record anything still lowers the count. The row is printed only when `P` is above 1, so writing the key on a 1-pass scan is harmless: `passes_planned` `1` prints no row.

**Turn 1c — Memory read.** **SKIP this turn entirely when memory is off.** It is a turn of its own, and not a step of Turn 2, because two of its outcomes stop or downgrade the whole scan — they have to be reached before any expensive work starts.

1. **Shell check.** Memory is merged by `awk`. Run `command -v awk >/dev/null` once. If it fails, print `memory needs a bash shell — on Windows install Git for Windows`, turn memory **off** for this scan, scan as a plain 1-run scan, and touch no file. There is no second implementation of the merge; the rule that must never break lives in one language only.

2. **Stale temporary file.** If `.rust-auditor/memory.tsv.tmp` exists, a previous scan did not finish. Print `warning: .rust-auditor/memory.tsv.tmp left by an unfinished scan — overwriting`, then carry on. It is overwritten by this scan's merge.

3. **Read the ledger.** If `.rust-auditor/memory.tsv` does not exist, this is a first-ever scan: memory is empty, every finding is `NEW`, the file is written at the end. Otherwise read it and **validate it before using it**:
   - the first line's first tab-separated field is exactly `#rust-auditor-memory v1`
   - every later line has exactly **6** tab-separated fields

   On any failure print the path and the problem and **STOP the scan**. No agents, no report, no write. The user fixes or deletes the file. Do NOT start fresh and do NOT continue with a warning — a single bad row must never destroy real memory.

4. **Photocopy it.** `mkdir -p {bundle_dir}` is already done; copy the ledger as it was **before this scan started**:

   ```bash
   cp .rust-auditor/memory.tsv {bundle_dir}/memory-before.tsv 2>/dev/null || : > {bundle_dir}/memory-before.tsv
   ```

   Every merge this scan performs reads this photocopy, never the live file. Create it empty when no ledger exists, so the merge command below needs no special case.

5. **Create the scan's row file**, empty: `: > {bundle_dir}/scan-rows.tsv`. Each run appends its gated rows to it.

6. **Hold the key list** — column 1 of every row of the photocopy (after the prune in Turn 2, if one runs).

   The **per-function bug-class vocabulary** — for each `program|function` prefix, the bug-class labels the ledger already holds — is not held in the orchestrator's head. Turn 2 step 2c writes it to `{bundle_dir}/known-findings.md`, where the agents read it inside their bundles and Turn 4 reads it back from disk. It is a file and not a memory because the two readers are a long scan apart, and because the same labels must reach both.

   The vocabulary is what keeps exact key matching honest: a bug class is a label written in words, so the same bug re-labelled is a second record and memory fails silently. Handing the existing labels back is how the same bug keeps the same key.

**Turn 2 — Prepare.** In one message, make parallel tool calls: (a) Read `{resolved_path}/report-formatting.md`, (b) Read `{resolved_path}/judging.md`, (c) Read `{resolved_path}/agent-prompts.md`, (d) Read `{resolved_path}/report-language.md`.

> **Why `report-formatting.md` is still read, now that nothing here composes a report.** It is the shape Turn 4 step 5a writes each finding in — title line, location line, Description, diff Fix block — and the assembler pastes those bytes straight through. Read it as the contract the finding blocks meet, not as a template to imitate at the end.

> **`report-language.md` is read for the same reason, one level down.** `report-formatting.md` settles the **shape** of a finding block; `report-language.md` settles the **words inside it**. Turn 4 step 5a writes the title and the Description, the assembler pastes them through unchanged, so those bytes are the last chance to write a sentence a developer can act on. It is Simplified Technical English (ASD-STE100), and it is not optional styling: a finding the developer cannot read is a finding they do not fix. The same file is in every agent bundle, so the sentence the pass writes and the sentence the agent handed it obey one rule.

Then build `source.md`, run the memory step, and only then cat the bundles — in that order, because the bundles carry a file the memory step writes:

> **Turn 2 is split across the loop.** Step 1 runs **once per scan**: `source.md` provably cannot change between passes — one git SHA for the whole loop, no pruning between them — and it is the expensive half of the build. Step 2c and step 3 run **once per pass**, because only they carry the knowns, and re-catting twelve bundles from files already on disk is one Bash command. Steps 2a and 2b run once per scan with step 1, since both read that frozen source.
>
> **One `{bundle_dir}`, reused, everything overwritten.** `source.md` is written once and never touched again; `known-findings.md` and the twelve `agent-N-bundle.md` files are overwritten each pass. Disk stays flat whether the runner picked 1 pass or 10 — a directory per pass would hold 12 × N copies of the whole repo. This is safe because Turn 3b is a hard barrier: no pass-K agent is still reading a bundle when pass K+1 overwrites it. The cost, accepted: after the loop you cannot see what pass 2 told its agents. The durable record is the run files and the ledger.

1. **Once per scan.** `{bundle_dir}/source.md` — a **Build context** header, then ALL in-scope `.rs` files, each with a `### path` header and fenced code block. Build it with exactly this command, `{file list}` substituted as Turn 1a wrote it:

   ```bash
   B={bundle_dir}
   for f in {file list}; do d=$(dirname "$f"); while [ ! -f "$d/Cargo.toml" ] && [ "$d" != "." ] && [ "$d" != "/" ]; do d=$(dirname "$d"); done; [ -f "$d/Cargo.toml" ] && printf '%s\n' "$d/Cargo.toml"; done | sort -u > $B/manifests.txt
   for m in ./Cargo.toml ./Anchor.toml; do [ -f "$m" ] && ! grep -qxF "$m" $B/manifests.txt && printf '%s\n' "$m" >> $B/manifests.txt; done
   fw=$(grep 'Cargo.toml$' $B/manifests.txt | while IFS= read -r m; do
     deps=$(awk '{ sub(/[[:space:]]*#.*/, "") } /^[[:space:]]*\[/ { s=$0 } s ~ /^[[:space:]]*\[(target\..*\.)?dependencies[].]/ && s !~ /cfg\(not\([^]]*target_(os|arch)[[:space:]]*=[[:space:]]*\\?"(solana|bpf|sbf)/' "$m")
     has() { printf '%s\n' "$deps" | grep -qE "(^[[:space:]]*|dependencies\\.)\"?($1)\"?[[:space:]]*[]=.]"; }
     if has 'anchor-lang|anchor-spl'; then echo Anchor; elif has 'pinocchio[a-z0-9-]*'; then echo Pinocchio
     elif has 'steel'; then echo Steel; elif has 'solana-program|solana-program-entrypoint|solana-account-info'; then echo 'native solana-program'; fi
   done | sort -u | paste -sd '+' - | sed 's/+/ + /g')
   [ -n "$fw" ] || fw="unknown — no in-scope crate depends on anchor-lang, anchor-spl, pinocchio, steel or solana-program"
   ws_root() { c=$(dirname "$1"); d=$c
     while :; do
       if [ -f "$d/Cargo.toml" ] && grep -qE '^[[:space:]]*\[workspace\][[:space:]]*(#.*)?$' "$d/Cargo.toml"; then
         rel=${c#"$d"}; rel=${rel#/}
         ex=$(awk '/^[[:space:]]*\[/ { s=$0 } s ~ /^[[:space:]]*\[workspace\][[:space:]]*(#.*)?$/' "$d/Cargo.toml" | tr -d ' \t\r\n' | grep -oE 'exclude=\[[^]]*\]' | grep -oE '"[^"]*"' | tr -d '"')
         for x in $ex; do x=${x#./}; x=${x%/}; case "$rel/" in "$x"/*) [ -n "$rel" ] && { echo "$1"; return; } ;; esac; done
         echo "$d/Cargo.toml"; return
       fi
       { [ "$d" = "." ] || [ "$d" = "/" ]; } && break; d=$(dirname "$d")
     done; echo "$1"; }
   grep 'Cargo.toml$' $B/manifests.txt | while IFS= read -r m; do grep -q '^[[:space:]]*\[package\]' "$m" && printf '%s\t%s\n' "$(ws_root "$m")" "$(basename "$(dirname "$m")")"; done | sort -u > $B/roots.txt
   cut -f1 $B/roots.txt | sort -u | while IFS= read -r r; do grep -qxF "$r" $B/manifests.txt || printf '%s\n' "$r" >> $B/manifests.txt; done
   [ -s $B/roots.txt ] || printf '%s\t%s\n' "$(grep 'Cargo.toml$' $B/manifests.txt | head -1)" all > $B/roots.txt
   nroots=$(cut -f1 $B/roots.txt | sort -u | wc -l)
   oc=$(cut -f1 $B/roots.txt | sort -u | while IFS= read -r root; do
     v=$(awk '/^[[:space:]]*\[/ { s=$0 } s ~ /^[[:space:]]*\[profile\.release\]/ && /^[[:space:]]*overflow-checks[[:space:]]*=/ { v=$0; sub(/.*=[[:space:]]*/, "", v); sub(/[[:space:]#].*/, "", v) } END { print v }' "$root" 2>/dev/null)
     w=""; [ "$nroots" -gt 1 ] && w=" (workspace of: $(awk -F'\t' -v r="$root" '$1==r { print $2 }' $B/roots.txt | paste -sd ',' - | sed 's/,/, /g'))"
     case "$v" in true) echo "on — \`[profile.release] overflow-checks = true\` in $root$w, so integer overflow panics" ;;
       false) echo "OFF — \`[profile.release] overflow-checks = false\` in $root$w, so release builds wrap on integer overflow" ;;
       *) echo "not set in $root$w — release builds (cargo build-sbf, anchor build) wrap on integer overflow" ;; esac
   done | paste -sd ';' - | sed 's/;/; /g')
   [ "$nroots" -gt 1 ] && oc="differs per workspace — $oc"
   {
     printf '# Build context\n\n- Framework: %s\n- Release overflow checks: %s\n- Manifests: every Cargo.toml / Anchor.toml below, verbatim\n\n' "$fw" "$oc"
     while IFS= read -r m; do printf '### %s\n\n```toml\n' "$m"; cat "$m"; printf '\n```\n\n'; done < $B/manifests.txt
     printf '# In-scope source\n\n'
     for f in {file list}; do printf '### %s\n\n```rust\n' "$f"; cat "$f"; printf '\n```\n\n'; done
   } > $B/source.md
   printf 'Framework: %s\nRelease overflow checks: %s\n' "$fw" "$oc"
   ```

   **This is how the framework reaches the agents.** The **Build context** header sits at the top of `source.md`, so every one of the twelve bundles opens with it: which framework each crate uses (Anchor, native `solana-program`, Pinocchio — a repo can mix them), the exact framework versions in the manifests, and whether the release profile of **each crate's workspace root** turns overflow checks on. Cargo ignores `[profile.*]` in member crates, so the root manifest decides — but a repo can hold **more than one workspace**: a nested `[workspace]` (e.g. `programs/amm/Cargo.toml`) or a crate listed in the root's `exclude` is built under its own root, not the top-level one. `ws_root` walks up from each in-scope crate to the first `[workspace]` manifest; if that workspace's `exclude` covers the crate (or none exists), the crate's own manifest is its root. Every root is added to `manifests.txt`, and when the roots disagree the line starts `differs per workspace —` and names the crates under each root, so an agent scores a crate by **its** workspace, not the repo's top level. `cargo build-sbf` builds with the release profile, and the release default is **off** — integer overflow wraps in the deployed program. That one line changes how every arithmetic finding is scored, which is why it is computed by shell and not left for twelve agents to infer. (Member-glob coverage — a crate under a `[workspace]` directory but not matched by `members` — is not checked; Cargo refuses to build such a crate, so it is not deployed code.)

   The two `printf` lines it prints are the only output this step adds. Print them with the line counts below; they are not part of the report.

**Turn 2 step 1b — Account map (pre-scan). Runs once per scan, every mode, with step 1.** Build the account map the twelve agents read as leads:

```bash
PY=; for c in python3 python; do "$c" -c 'import sys; sys.exit(sys.version_info < (3, 6))' 2>/dev/null && { PY=$c; break; }; done
[ -n "$PY" ] && "$PY" {resolved_path}/account-map.py --out .rust-auditor/runs/{stamp}/account-map.md {file list} \
  || printf '# Account map\n\n> Account map unavailable: Python 3 was not found or the script failed. Work from the source alone.\n' > .rust-auditor/runs/{stamp}/account-map.md
```

The probe tries `python3` then `python` and runs each, because on Windows `python3` is often a Store stub that exists but does not run. If neither works, or the script fails, a one-line stub map is written, so the bundle step always finds `account-map.md`; print a one-line warning and carry on — the map is leads, and the scan does not depend on it.

The script is Python standard library only; it never installs anything and writes only the `--out` file. It lists every instruction handler with its accounts (signer / mut / owner / type / PDA seeds and bump source / init / close / constraints), its cross-program calls (the target program and how its ID is validated, plus signer seeds), the state it writes and how it is gated, and opens with an auto-highlighted **Review leads** section — authority-bearing accounts written with no signer check, keys compared against stored data with no `is_signer` (`key-compared-no-signer`), `UncheckedAccount` with no valid `/// CHECK`, PDA seeds lacking a user key, caller-chosen bumps, hand-coded byte offsets that miss the `#[repr(C)]` struct layout (`offset-mismatch`), CPI to a non-constant program ID, unvalidated `remaining_accounts`. Global singletons are folded so they do not bury the per-user leads: a constant-seed PDA is one `singleton-init` lead on the instruction that creates it (or one `singleton-write` when nothing in scope creates it), constant CPI signer seeds are one `global-signer` lead per program, and a child PDA keyed only by a validated parent, or a PDA owned by another program, raises nothing. It parses **Anchor** structurally; for **native `solana-program` and Pinocchio** it fills what it can and lists the rest under a **Needs completion** section. On native and Pinocchio code it follows the usual idioms before it raises a lead: a signer or owner check done in a helper (`verify_signer(acct)`, `acct.signer_key()`, a `Signer` wrapper type, `check_owner(acct, ..)`) counts at the call site, a typed accounts struct validated in its constructor (`impl TryFrom<&[AccountView]>`) is merged into the handler that builds it, and program names come from the crate's `Cargo.toml`.

> **The map is leads, never findings.** Every line is a place to look produced by pattern matching; an agent confirms each one in the source and reports nothing on the map's word alone. The script cannot see logic bugs, so an empty Review-leads section is not a clean bill.

**When the script prints a "Needs completion" list** (native/Pinocchio handlers whose accounts it could not fully resolve, or accounts read by index), read those handlers and complete the `?` cells — append a short `> model-completed:` note per handler to `account-map.md` so the agents get a full map. This is the only model work this step does, and only for native/Pinocchio gaps; an all-Anchor repo needs none. Do **not** expand this into a second review pass — filling the named cells is the whole of it.

This step writes one file under `.rust-auditor/runs/{stamp}/`, like the run files — the plain-path rule protects the working directory and printed output, not the runs directory, so a 1-pass scan writes the map too. Print the script's one stderr summary line (`account map: N instruction(s), M review lead(s), K need completion`); it is not part of the report.
2. **Turn 2 step 2 — Name map, prune and known findings** (below). SKIPPED whole when memory is off. Parts a and b run once per scan; part c runs **every pass**, because the ledger it reads grows as the loop learns.
3. **Every pass.** Agent bundles, in a single Bash command using `cat` (not shell variables or heredocs) = `source.md` + agent-specific files:

| Bundle                | Appended files (relative to `{resolved_path}`)                                                                                                |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `agent-1-bundle.md`   | `source.md` + `senior-auditor-sop.md` + `hacking-agents/math-precision-agent.md` + `hacking-agents/shared-rules.md`                            |
| `agent-2-bundle.md`   | `source.md` + `senior-auditor-sop.md` + `hacking-agents/access-control-agent.md` + `hacking-agents/shared-rules.md`                            |
| `agent-3-bundle.md`   | `source.md` + `senior-auditor-sop.md` + `hacking-agents/economic-security-agent.md` + `hacking-agents/shared-rules.md`                         |
| `agent-4-bundle.md`   | `source.md` + `senior-auditor-sop.md` + `hacking-agents/execution-trace-agent.md` + `hacking-agents/shared-rules.md`                           |
| `agent-5-bundle.md`   | `source.md` + `senior-auditor-sop.md` + `hacking-agents/invariant-agent.md` + `hacking-agents/shared-rules.md`                                 |
| `agent-6-bundle.md`   | `source.md` + `senior-auditor-sop.md` + `hacking-agents/periphery-agent.md` + `hacking-agents/shared-rules.md`                                 |
| `agent-7-bundle.md`   | `source.md` + `senior-auditor-sop.md` + `hacking-agents/first-principles-agent.md` + `hacking-agents/shared-rules.md`                          |
| `agent-8-bundle.md`   | `source.md` + `senior-auditor-sop.md` + `hacking-agents/asymmetry-agent.md` + `hacking-agents/shared-rules.md`                                 |
| `agent-9-bundle.md`   | `source.md` + `senior-auditor-sop.md` + `hacking-agents/account-validation-agent.md` + `hacking-agents/shared-rules.md`                        |
| `agent-10-bundle.md`  | `source.md` + `senior-auditor-sop.md` + `hacking-agents/numerical-gap-agent.md` + `hacking-agents/shared-rules.md`                             |
| `agent-11-bundle.md`  | `source.md` + `senior-auditor-sop.md` + `hacking-agents/trust-gap-agent.md` + `hacking-agents/shared-rules.md`                                 |
| `agent-12-bundle.md`  | `source.md` + `senior-auditor-sop.md` + `hacking-agents/flow-gap-agent.md` + `hacking-agents/shared-rules.md`                                  |
| **every one of the 12** | **+ `report-language.md`, appended after `shared-rules.md`** — unconditional, every mode, every pass. The agent's `description:` is the seed of the report's Description, so the language rule has to reach the writer and not only the editor. |
| **every one of the 12** | **+ `solana-exploit-patterns.md`, appended after `report-language.md`** — unconditional, every mode, every pass. Each agent file names, under **Exploit patterns**, the incidents and bug classes it owns; the catalogue has to be in the bundle for the agent to read those sections. |
| **every one of the 12** | **+ `.rust-auditor/runs/{stamp}/account-map.md`, appended after the exploit patterns** — unconditional, every mode, every pass. It is the pre-scan leads map from step 1b; every agent gets the same map. |
| **every one of the 12** | **+ `{bundle_dir}/known-findings.md`, appended last** — only when memory is on **and** step 2 wrote that file. Never appended on a plain scan, and never appended when the ledger holds no record. |

Each bundle = source.md (Build context + source) + SOP + specialty + shared-rules + report-language + solana-exploit-patterns + account-map (+ known findings, when there are any). Agents read the bundle; no Read/Grep needed for the initial scan. Targeted Read/Grep allowed for cross-file investigation.

**Turn 2 step 2 — Name map, prune and known findings.** **SKIP this step entirely when memory is off.** It lives in Turn 2 and not in a turn of its own because all three parts read `source.md`, which Turn 2 has just built — a separate turn would only carry that file across a boundary. It is numbered **2**, ahead of the bundle cat, because part c writes a file every bundle carries; a pruned record must never reach an agent.

a. **Build the name map, always** — once per scan, with step 1 (both the prune and the report need it, and the source it reads is frozen for the whole scan):

```bash
{
  grep -ohE '(mod|struct|enum|trait|union)[[:space:]]+[A-Za-z0-9_]+|impl(<[^>]*>)?[[:space:]]+[A-Za-z0-9_]+|for[[:space:]]+[A-Z][A-Za-z0-9_]*|fn[[:space:]]+[A-Za-z0-9_]+' {bundle_dir}/source.md
  grep -E '^### .*\.rs$' {bundle_dir}/source.md | sed 's/^### //' \
    | awk -F/ '{ s=$NF; sub(/\.rs$/, "", s); print "file " s; for (i=1; i<NF; i++) if ($(i+1)=="src" && $i!="" && $i!=".") print "crate " $i }'
} | awk '{ n=$NF; k=tolower(n); gsub(/[^a-z0-9]+/, "-", k); print k "\t" n }' \
  | sort -u > {bundle_dir}/source-names.tsv
```

Column 1 is the identifier normalised the same way a key segment is (lower case, every run of non-alphanumeric characters to one hyphen); column 2 is how it is spelled in the source. Normalising **both sides the same way** is what makes the comparison exact — a key segment can never be matched against raw source text, because `withdraw_all` is stored as `withdraw-all` and `WithdrawAll` as `withdrawall`.

The map holds every name a key's first two segments can carry: `mod` names (an Anchor `#[program] pub mod vault`), types (`struct`, `enum`, `trait`, and the type an `impl` block is for), every `fn`, every file stem (`processor`, `withdraw`) and every crate directory above a `src/` (`programs/vault/src/…` gives `vault`). The `program` segment of a key is one of the last three, so a record survives as long as its program crate, module or file is still in scope.

b. **Prune — once per scan, and only after a whole-repo scan.** Run it **only** in default mode. Never on a named-file scan (a file that was not scanned proves nothing about the records it holds), and never a second time inside one scan — the loop's later passes read the same frozen source, so there is nothing new for a second prune to learn.

The prune edits the **photocopy**, not the live ledger. The live file inherits the prune when the first merge writes it. Pruning the live file instead would be undone by the next rebuild.

```bash
awk -F'\t' -v OFS='\t' '
FILENAME==ARGV[1] { names[$1]=1; next }
FNR==1 { print; next }
{
  split($1, p, "|")
  keep = (p[1] in names) && (p[2] in names)
  if (p[2]=="entrypoint") keep = (p[1] in names)
  if (keep) print; else print "pruned: " $6 "\t" $1 "\t" $5 > "/dev/stderr"
}
' {bundle_dir}/source-names.tsv {bundle_dir}/memory-before.tsv > {bundle_dir}/memory-before.tsv.tmp \
  && mv {bundle_dir}/memory-before.tsv.tmp {bundle_dir}/memory-before.tsv
```

A record is dropped when its program or its function can no longer be found in the assembled source. `entrypoint` is declared by the `entrypoint!` macro and is never written as `fn entrypoint`, so a record on it is kept whenever its program survives.

**The prune deletes Leads as well as findings.** A Lead is a full ledger record, so the same rule reaches it — and a pruned Lead leaves no trace anywhere else in the output. That is why the command prints every dropped row to the runner: `kind`, key and title, one line each. Print them under `Pruned N records (program or function no longer in scope):`. Never drop a record silently.

After the prune, re-read the photocopy for the key list of Turn 1c step 6. A pruned record must not reach the agents, the merge, or the "Known from earlier scans" section.


c. **Write `mem_before`, then build `{bundle_dir}/known-findings.md`.**

**`mem_before` first** — the row count of the photocopy **as the merge will read it**, which is the count *after* the prune. It is written here and nowhere else, and it is written in every mode memory is on, whether or not part b's prune ran (it does not run on a named-file scan):

```bash
n=$(( $(wc -l < {bundle_dir}/memory-before.tsv) - 1 )); [ "$n" -lt 0 ] && n=0
printf '%s\t%s\n' mem_before "$n" >> .rust-auditor/runs/{stamp}/scope.tsv
```

The `- 1` drops the header line. An empty photocopy has no header and would give `-1`, so the command clamps it to `0`. The **pre**-prune number would make the `Memory` row's own arithmetic wrong — `12 records before this scan · 14 after` has to describe the same set the merge worked on.

**This key is the memory flag the assembler reads.** Its presence is what makes the `Memory` row appear and the "Known from earlier scans" section exist — the presence of `memory-before.tsv` is not. Nothing writes a `mem_` key when memory is off, and this whole step is skipped when it is, so the flag cannot get out of step with the scan.

It is written before the early exit below, so an empty ledger still gets a `Memory` row reading `0 records before this scan`.

**Then `{bundle_dir}/known-findings.md`** — the ledger as the agents and Turn 4 read it. It is built from the **pruned** photocopy and from `source-names.tsv`, so it never names a record the prune has just dropped and never prints a normalised key at a human.

```bash
awk -F'\t' '
FILENAME==ARGV[1] { nm[$1]=$2; next }
FNR==1 { next }
{
  split($1, p, "|")
  c = (p[1] in nm) ? nm[p[1]] : p[1]
  f = (p[2] in nm) ? nm[p[2]] : p[2]
  h = c "::" f
  if (!(h in seen)) { seen[h]=1; ord[++n]=h }
  body[h] = body[h] "- `" p[3] "` — " $6 ", seen in " $3 ($3==1 ? " scan" : " scans") " — " $5 "\n"
}
END { for (i=1; i<=n; i++) printf "## %s\n\n%s\n", ord[i], body[ord[i]] }
' {bundle_dir}/source-names.tsv {bundle_dir}/memory-before.tsv > {bundle_dir}/known-findings.body.md
```

**If that file is empty, stop here** — delete it, write no `known-findings.md`, and append nothing to the bundles. An empty ledger (a first-ever scan, or a scan whose every record the prune removed) must not hand twelve agents an empty heading.

Otherwise write `{bundle_dir}/known-findings.md` as this exact prose followed by the body, unchanged:

````markdown
# Known findings — ground already walked

Earlier scans of this repository recorded the findings below, grouped by the program and
function they sit in. Each line is `bug class` — kind, scans, title.

**They are not false positives, and they are not off limits.** Put your **effort** into new
ground: functions, flows and mechanisms this list does not name. That is a rule about where
your reading time goes. It is **not** a rule about what you report.

**Report every bug you find in full, listed or not.** A listed bug you reach again is a bug
that is still there, and the report has to say so. Write it up exactly as you would write up
anything new — the same path, proof and fix — whether you reached it by the mechanism it is
listed with or by a different one. Silence is read as "nobody found this": a finding no agent
raises drops out of the report into a table of records nobody re-checked, so a repository
scanned twice would show fewer bugs than the same repository scanned once.

**Reuse the bug-class label.** The backticked label on each line is the word this repository
already uses for that class of bug in that function. When you report a finding or a lead
whose bug class is one of the classes listed for that same program and function, write
**that exact label**. Invent a new label only when none of them is the same class of bug.
Memory matches these labels as plain text, so the same bug under a new word is remembered
twice and recognised never.

<body — one `## program::function` section per function, as generated above>
````

The label-reuse rule is written here, once, for **both** readers of this file: the 12 agents,
who write the bug class in a finding, and Turn 4 step 4, which writes it into a key.

**The builder takes any 6-column ledger file.** On a single-run scan that file is the pruned
photocopy, as above. A multi-pass scan rebuilds `known-findings.md` from the freshly merged
`.rust-auditor/memory.tsv` after every pass, before it re-cats the bundles, so the agents
of pass K+1 read what pass K found as ground already walked. That is the whole point of
passing memory down a loop; the command does not change, only the file it is pointed at.

Print line counts for every bundle and `source.md`. Do NOT inline source code into the Agent call prompt itself.

**Turn 3a — Spawn all 12 agents.** Runs **every pass**. In one message, spawn all 12 agents as **parallel BACKGROUND Agent calls** (`run_in_background=true`). If Turn 1b set `{agent_model}`, pass `model={agent_model}` on every Agent call. If `{agent_model}` is unset (Turn 1b skipped — Codex, Gemini, others), omit the `model` parameter entirely — do NOT substitute any default. The orchestrator will receive a notification when each agent completes — do NOT poll or sleep. Single phase, no later spawns. Proceed to Turn 3b only after all 12 have notified completion.

Agents 1–9 use the **single-specialty prompt** (Turn 3a-i). Agents 10–12 use the **gap-hunter prompt** (Turn 3a-ii).

**Turn 3a-i — Single-specialty prompt (agents 1–9).** Use the template under "Single-specialty prompt" in `{resolved_path}/agent-prompts.md`, substituting `{bundle_dir}`, the agent number and the bundle line count.

**Turn 3a-ii — Gap-hunter prompt (agents 10–12).** Use the template under "Gap-hunter prompt" in the same file.

Two rules that file carries, repeated here because they are conditions and not text:

- The **"Known findings"** paragraph is included **only when memory is on and `known-findings.md` was appended**. On a plain scan the paragraph is omitted — a paragraph about a section that is not there would send agents hunting for it.
- The **READ-ONLY** paragraph is **unconditional** — every agent, every mode, every pass. An agent that builds proof-of-concept test files inside the audited repository is wrong even if it deletes them afterwards and leaves the tree clean. In a Rust repo the same rule also forbids `anchor build`, `cargo build-sbf`, `anchor test` and `cargo test` inside the repository — each one writes `target/`, `.anchor/` or `test-ledger/` into the tree it is measuring. A later editor must not make it conditional, and must not soften it into a preference.

**Turn 3b — Wait for all 12 agents to complete.** Runs **every pass**. Once every one of the 12 spawned agents has notified completion, proceed to Turn 4. Do NOT proceed to dedup until every agent has finished — let them run to natural completion. Do NOT poll or sleep; act only on completion notifications.

**While you wait, on the first pass only, Read `{resolved_path}/dedup-and-assembly.md`.** It holds the whole of Turn 4 and Turn 5. This turn is the one point in the scan where the orchestrator has nothing else to do, so the read costs no wall-clock; and having it in hand before Turn 4 starts is what keeps Turn 4 from improvising. Later passes already hold it.

**When `--poc` was passed, Read `{resolved_path}/poc-guide.md` here too** (first pass only). The verification step runs after judging, so having the guide in hand before Turn 4 ends avoids a separate read. Without `--poc`, do not read it — there is no verification step to run.

**When an agent dies.** Continue the pass with the eleven that came back. **Never respawn it, in any mode.** A retry costs an unbounded wait for one twelfth of the coverage, and a loop covers it for free — the next pass runs the same twelve specialties again, knowing what this one found. Record the loss, or it is a silent coverage loss: in the `run-K.md` header (`agents=N/12`), in the `pass_{K}_agents` key of `scope.tsv` (Turn 4 step 5a) — the only place the report's `Passes` row (on a 1-pass scan, its `Agents` row) reads the count from — and, when `{passes}` is above 1, in the pass summary line (Turn 4 step 5b). **An agent that returns but says it stopped is dead too:** a reply with no FINDING or LEAD block that reports a refusal, a safety stop or an abort is a lost specialty, not a clean result — count it out of `agents=N/12` and out of `pass_{K}_agents`. A reply with no blocks that says it reviewed its scope and found nothing is a clean result.

**When a whole pass produces nothing** — the bundle build failed, or all twelve died:

**Record the failure before doing either.** A pass that produces nothing writes no run file, so nothing else on disk knows it was ever planned:

```bash
printf '%s\t%s\n' pass_{K}_failed 1 >> .rust-auditor/runs/{stamp}/scope.tsv
```

- **Pass 1 produces nothing:** this is not a loop failure, it is today's failure. No ledger write. Go to Turn 5, which assembles a report with no findings in it — `_None — this scan raised no findings._` — rather than printing nothing at all. The `Passes` row is suppressed on a 1-pass scan, so the assembler says it in a **Run files** row instead — `⚠️ No pass produced a run file. This scan reviewed nothing.` The runs directory stays; it holds the `scope.tsv` that says what was attempted.
- **A later pass produces nothing:** stop the loop and go straight to Turn 5. The report is assembled from the passes that finished and its `Passes` row says which one failed. Nothing is lost — the ledger was rebuilt after every pass. Grinding on to the next pass after the machinery has broken burns the runner's money.

**Turn 4 — Deduplicate, validate & record.** Runs **every pass**, and it is the end of the loop body: deduplicate this pass's agent results, gate-evaluate, tag, record the pass, write the ledger. **It prints no report** — there is exactly one report per scan and Turn 5 prints it. Do NOT print an intermediate dedup list.

**Steps 4 and 6 are SKIPPED entirely when memory is off.** Every other step runs at any pass count.

**The PoC verification step (`dedup-and-assembly.md` Turn 4 step 3b) is SKIPPED entirely unless `--poc` was passed.** A plain scan runs no builds and labels no finding. When `--poc` is on, it runs once per scan, on the final pass — after that pass has gated and before its memory tag and run file are written — per `{resolved_path}/poc-guide.md`.

Follow `{resolved_path}/dedup-and-assembly.md`, section **"Turn 4"**, step by step.

Then, after the loop body has run `{passes}` times (or stopped early), go to Turn 5 once.

**Turn 5 — Assemble, print, clean.** Runs **once per scan**, at any pass count, including a 1-pass scan and including a loop that stopped early. There is no path where a scan ends without this turn.

**This turn holds no model judgment.** It copies two files, runs `assemble.sh`, counts with `awk`, and prints. `assemble.sh` is the only producer of a report in this skill: do not re-word its output, do not re-order it, do not add to it and do not summarise it in your own words. If this turn looks too thin to be a reporting step — that is the point, and `dedup-and-assembly.md` records why.

Follow `{resolved_path}/dedup-and-assembly.md`, section **"Turn 5"**, step by step. Its step 1 is SKIPPED when memory is off; its step 4 runs only when `--file-output` was passed.

## Banner

Before doing anything else, print this exactly:

```

██████╗  █████╗ ███████╗██╗  ██╗ ██████╗ ██╗   ██╗     ███████╗██╗  ██╗██╗██╗     ██╗     ███████╗
██╔══██╗██╔══██╗██╔════╝██║  ██║██╔═══██╗██║   ██║     ██╔════╝██║ ██╔╝██║██║     ██║     ██╔════╝
██████╔╝███████║███████╗███████║██║   ██║██║   ██║     ███████╗█████╔╝ ██║██║     ██║     ███████╗
██╔═══╝ ██╔══██║╚════██║██╔══██║██║   ██║╚██╗ ██╔╝     ╚════██║██╔═██╗ ██║██║     ██║     ╚════██║
██║     ██║  ██║███████║██║  ██║╚██████╔╝ ╚████╔╝      ███████║██║  ██╗██║███████╗███████╗███████║
╚═╝     ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝ ╚═════╝   ╚═══╝       ╚══════╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝╚══════╝
                                   rust-auditor · Solana programs

```
