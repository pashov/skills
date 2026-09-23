# Dedup, record and assembly — Turn 4 and Turn 5

This file holds the two turns that run **after the 12 agents return**: Turn 4
deduplicates, gates, tags and records each pass, and Turn 5 assembles and prints
the one report. `SKILL.md` keeps the name of each turn and the condition that
decides whether it runs; the procedure is here.

The orchestrator reads this file **once, in Turn 3b**, while it waits for the
agents. It stays in context for the later passes of a loop.

Both turns use `{stamp}`, `{bundle_dir}`, `{passes}`, `{resolved_path}` and
`{project-name}` exactly as `SKILL.md` set them.

---

## Turn 4

**Turn 4 — Deduplicate, validate & record.** Runs **every pass**, and it is the end of the loop body: deduplicate this pass's agent results, gate-evaluate, tag, record the pass, write the ledger. **It prints no report** — there is exactly one report per scan and Turn 5 prints it. Do NOT print an intermediate dedup list.

> **This turn used to print the report and clean up, and both moved.** The report moved to Turn 5 so that a 1-pass scan and an N-pass scan take the **same** path through this turn — the "1 pass is byte-identical to today" constraint is easier to hold with one report writer than with a last pass that doubles as one. The auto-clean moved to Turn 5 because, left here, pass 1 deletes what pass 2 needs: `source.md`, the ledger photocopy and the accumulating rows file. A later editor must not move either back.

Then, after the loop body has run `{passes}` times (or stopped early), go to Turn 5 once.

1. **Dedup.** Parse every FINDING and LEAD from the 12 agents. Group by `group_key` (Contract | function | bug-class). Exact-match first; merge synonymous bug_class within same (Contract, function). Keep best per group, number sequentially, annotate `[agents: N]`.

   **MANDATORY — Canonicalise the bug-class label (HARD GATE).** Before grouping, for every (Contract, function) whose agents used **more than one** bug-class label, choose **one** label and rewrite every one of those findings to carry it. Then group.

   Choose in this order, and stop at the first that applies:
   1. A label already listed for that same contract and function in `{bundle_dir}/known-findings.md` — the repository's own word wins, always.
   2. Otherwise the label that most agents used.
   3. Otherwise the shortest label that names the **defect**, not its consequence. `zero-abort-address` over `abort-address-zero-burns-funds`.

   Merging under one label is only correct when the labels name the **same class of bug**. Two genuinely different bugs in one function keep two labels and stay two records — function isolation is about functions, and this rule is about words.

   **Why this is a gate and not a nicety.** The per-function vocabulary that keeps a key stable only constrains what an **earlier scan** wrote. A class discovered mid-scan is constrained by nothing, and a real scan proved what follows: three agents in one pass named one bug `zero-abort-address`, `unregistered-abort-address` and `abort-address-zero-burns-funds`, and the over-approval class drew three labels across three passes. Unfixed, that is three ledger records for one bug, three lines in every future `known-findings.md`, and one bug that is never recognised again. This step is the only thing standing between the fork and the ledger. Canonicalise here and the next pass inherits the canonical label, so the fork closes after one scan.

   **MANDATORY — Wide-description (group_key).** Merged group with distinct mechanisms (different `fix:`, code-level cause, or attack path) MUST list every mechanism. No dropping. Same function can have multiple coexisting bugs at the same group_key — all MUST appear.

   **MANDATORY — Function-level second pass (after group_key dedup).** Run at (Contract, function), ignoring bug_class. Agents often label coexisting bugs with different bug_class tags but reference multiple mechanisms in the body. For every (Contract, function) with multiple final findings: scan body (description, path, proof, fix) of every constituent for distinct mechanisms across bug_class boundaries. Every mechanism in any constituent body MUST appear in ≥1 final finding.

   **MANDATORY — Function isolation (HARD).** NEVER merge across different `function:` fields. Dedup only within (Contract, function). Different function = different bug. Second pass above stays WITHIN (Contract, function), never across.

   **MANDATORY — Fix preservation (HARD GATE).** Before writing merged `fix:` on a multi-finding (Contract, function):
   1. Collect every raw `fix:` from agents flagging the tuple.
   2. Group by ADD-lines (`+` lines, or equivalent require/assignment).
   3. Distinct if ADD-lines differ in: called function/expression (e.g., `require(msg.value == amount)` vs `require(zrc20 != _ETH_ADDRESS_)`), check direction (validate/restrict/ban), or checked parameter.
   4. ≥2 distinct → present as Option A, B, … — one block per distinct fix, verbatim from agent text (no paraphrase).
   5. Label intuitively: validate / restrict / allow-and-handle / ban-path.

   **Output format when 2+ distinct fixes exist:**

   ```
   **Fix (Option A — <label>)**:

   ```diff
   <verbatim diff from raw agent N1's fix>
   ```

   **Fix (Option B — <label>)**:

   ```diff
   <verbatim diff from raw agent N2's fix>
   ```
   ```

   **Inline check before printing**: count distinct fixes from raw for this (Contract, function). ≥2 distinct but merged shows 1 → violation, add alternatives.

   **MANDATORY — Completeness (HARD GATE).** Before print: list every unique (Contract, function, bug-class) in any raw FINDING/LEAD across the 12 agents. Every unique (Contract, function) MUST have ≥1 item in final. Zero = silent drop, fix it. Multiple bug-class within same (Contract, function) MAY collapse to one item (wide-description), but the (Contract, function) MUST survive. Print inline before report: `Completeness: N unique (Contract, function) in raw, N covered in final.`

   Composite chains: if A's output feeds B's precondition AND combined impact > either alone, add `Chain: [A] + [B]` at conf = min(A, B). Most audits: 0–2.

2. **Gate.** Run each deduped finding through the four gates in `judging.md` (no skip, no reorder, no revisit after verdict).

   **Single-pass:** every relevant code path ONCE in fixed order (constructor → setters → swap → mint → burn → liquidate). One-line verdict: `BLOCKS` / `ALLOWS` / `IRRELEVANT` / `UNCERTAIN`. `UNCERTAIN = ALLOWS`. Commit, no re-examination.

3. **Lead promotion / rejection.**
   - LEAD → FINDING (conf 75) if: full exploit chain in source, OR `[agents: 2+]` demoted (not rejected) same issue.
   - `[agents: 2+]` does NOT override a code path that interrupts attack before harm — demote to LEAD if execution uncertain.
   - No deployer-intent reasoning — what code allows, not how deployer might use it.

4. **Memory tag.** **SKIP this step entirely when memory is off.** It comes before the report, not after it, because the report prints what it decides. It is a **lookup, never a judgment** — no finding is re-argued here, and no verdict from the gate is revisited.

   a. **Build the key** for every gated FINDING and every gated LEAD — the three segments of Turn 4's `group_key`, each normalised **on its own** (lower case, every run of non-alphanumeric characters to one hyphen), then joined with `|`: `vault|withdraw|reentrancy`. Normalise the segments separately, never the joined string, or the separators become hyphens too.

   **The bug-class segment is where memory succeeds or fails.** Before writing a key, read the per-function vocabulary back from `{bundle_dir}/known-findings.md` — the same file the agents were given: *if this finding is one of the bug classes already listed for this same contract and function, write that exact label. Invent a new label only when none of them is the same class of bug.* This is the only judgment in the whole memory path, and it happens when the label is **written** — never at merge time. The keys built here are the keys step 6 writes; build them once.

   b. **Tag each finding and each lead.** Look its key up in the pre-scan key list:

   ```bash
   tail -n +2 {bundle_dir}/memory-before.tsv | cut -f1,3 | sort > {bundle_dir}/known-keys.tsv
   ```

   Key present → **KNOWN**, printed as `KNOWN (n scans)` where **n is column 2 plus one**. The scan that is printing has found it again, so the count the report shows is the count the ledger will hold when step 6 has written it — report and file say the same number. Key absent → **NEW**. Nothing else decides this tag.

   The lookup is against the **pre-scan photocopy**, in every pass of a loop. `KNOWN` means "an earlier **scan** recorded this"; a finding first raised by pass 1 of this scan is still `NEW` in pass 3, and how many passes saw it is what `seen in k/N runs` says. Tagging against the live ledger would make pass 2 call this scan's own work old news.

   c. **Write this run's keys** to `{bundle_dir}/run-keys.tsv`, one per line, from step 4a.

   The "Known from earlier scans" rows are **not** built here. They are report work, and a pass that built them could not know what a later pass is about to raise. They are built once, in Turn 5.

5. **Record the pass.** Do NOT print the report.

   a. **Write the run file** to `.solidity-auditor/runs/{stamp}/run-K.md`, where `K` is the pass number. **Every pass of every scan writes one**, at any pass count, `{passes}` of 1 included. This is the only place this pass's work is recorded, and Turn 5 assembles the report out of these files — a pass that writes no run file has produced nothing the report can print.

   One directory per scan, one file per run; `ls` is history in order. The git SHA goes **inside** the file, not in the directory name, so two scans of the same commit sit side by side instead of colliding. Nothing deletes these files, and `--file-output` does not govern them — they are memory, not reports.

   **The file, exactly:**

   ````markdown
   # Run K — solidity-auditor

   <!--RUN pass=K of=N stamp={stamp} sha=abc1234 agents=11/12-->

   Pass K of N · <date> · `abc1234` · 11/12 agents returned — the access-control agent died.

   ## Findings

   <finding blocks, kind=FINDING>

   ## Leads

   <finding blocks, kind=LEAD>
   ````

   The sentence is for the human; the `<!--RUN-->` marker is what shell reads. `agents=11/12` is where the `Passes` row gets its degradation text, so a lost agent is on disk and not only in a printed line that scrolls away — and the dead agent's **name** stays here, in the sentence, and never enters the Scope table.

   **These two headings and no others, in every run.** No `## New findings` in a later run — newness is already carried by the `NEW` / `KNOWN` tag and by `seen in k/N runs`, and a heading saying it again is a second source of truth that can disagree with the first. **No "verified clean", "checked" or "sound" section, under any name.** A path a pass did not raise is not a path a pass cleared, and a real scan invented such a section unasked. Nothing ever reads it back, and it is the same overstated-coverage defect this whole design exists to kill.

   **The finding block, exactly:**

   ````markdown
   <!--F key=contract|function|bug-class conf=95 kind=FINDING agents=8-->

   [95] **<Title>**

   `ContractName.functionName` · Confidence: 95

   **Description**
   <the vulnerable pattern and why it is exploitable, 1 short sentence>

   **Fix**

   ```diff
   - vulnerable line(s)
   + fixed line(s)
   ```

   <!--/F-->
   ````

   - **The markers bound the block.** `<!--F ` opens it, `<!--/F-->` closes it, each on its own line at the start of the line. **Never `---`**: today's separator also appears inside a unified diff (`--- a/Vault.sol`), so it cannot cut a block that now carries one. The HTML comment renders invisible, so the file still reads as human memory.
   - **`key`** — exactly the key step 4a built, unchanged. Never re-derived here. The same key the ledger stores, so the run file and `memory.tsv` agree by construction.
   - **`conf`** — an integer, on `kind=FINDING` blocks only. **A `kind=LEAD` block carries no `conf` attribute at all** — a lead is not scored, and writing `0` would sort it against real numbers.
   - **`kind`** — `FINDING` or `LEAD`.
   - **`agents`** — carried from `[agents: 8]`. Informational; nothing parses it.

   **Write the markers exactly as printed.** They are the only thing standing between a finding and a silent loss: the assembler counts open markers against close markers against readable blocks, and a disagreement becomes a visible `**Run files**` row in the report saying how many findings could not be read. The report may print **less** than the scan found; it may never claim to print **more**. A fudged marker costs a visible warning, not a hidden hole — but it still costs the finding.

   **Above and below the threshold, the block shape is identical.** A block whose `conf` is below 75 simply has no `**Fix**` section. The run file does **not** mark which side of the line a finding sits on; the assembler re-derives that from `conf`. One source of truth.

   **Write the Description and the diff Fix block here, in full.** This is the expensive per-finding writing, and it is paid **now**, in the pass that found the bug, while that pass still has context to spare. Turn 5 re-words nothing — it pastes these bytes into the report. An orchestrator drafting seventy findings at the end of a long scan is the failure this ordering exists to prevent.

   **The title and the Description are written in Simplified Technical English**, per `{resolved_path}/report-language.md`, which Turn 2 read. Because Turn 5 re-words nothing, this is the **only** step where the report's sentences can be made readable — there is no later cleanup pass and there must never be one. Four pieces of text obey that file: the title, the Description, the Lead description, and the Lead's code-smell list.

   Three things it does **not** reach, and a later editor must not extend it to them: the **diff** inside the Fix block, which is pasted verbatim from the agent, the **bug-class label** in the `key` attribute, which is a memory key and is chosen by step 1 and step 4a, and the **identifiers** on the location line, which are spelled as the source spells them. Softening a label to read better writes a second ledger record for one bug.

   Where the agent handed up a sentence that already meets the rules, keep the agent's words. Where it did not — a metaphor, an `-ing` clause, forty words, `catastrophic` — rewrite the sentence and keep the claim. Rewriting is about the wording only: the mechanism, the actor and the effect the agent proved are not up for revision here, and the gate has already run.

   **Then record the agent count**, once per pass, always, `12/12` included:

   ```bash
   printf '%s\t%s\n' pass_{K}_agents "11/12" >> .solidity-auditor/runs/{stamp}/scope.tsv
   ```

   Written only when a pass ran short, a missing key would mean two different things — a whole pass and a lost pass — and the assembler could not tell them apart.

   b. **Print one summary line**, only when `{passes}` is above 1, and nothing else — the last thing the pass does, after step 6 has written the ledger. It is the only thing the runner sees for minutes at a time, so it answers two questions: how far along, and is the loop still learning?

   ```
   Pass 2/3 — 17 findings (3 new) · 6 leads (2 new) · ledger 41 records
   ```

   - The counts are post-dedup and post-gate — the numbers `run-2.md` holds, not raw agent output.
   - **new** = the key was not in the ledger before this pass. A lookup, not a judgment.
   - `ledger N records` is the row count of `.solidity-auditor/memory.tsv` after step 6 has written it, so print this line after step 6.
   - The parentheses are printed **only when the ledger was non-empty when the scan started**. On a first-ever scan every key is new and they say nothing: `Pass 1/3 — 17 findings · 6 leads · ledger 17 records`.
   - When a pass lost an agent, the line gains a clause: `Pass 2/3 — 15 findings (2 new) · 6 leads (0 new) · ledger 39 records · 11/12 agents`.
   - When **both** new-counts are zero, the line ends with `· no new ground`. That is the loop's most informative outcome — the passes have converged — and it must not have to be inferred from two zeros:

   ```
   Pass 3/3 — 17 findings (0 new) · 6 leads (0 new) · ledger 41 records · no new ground
   ```

   Elapsed time is deliberately not printed: it needs a `date` call either side of every pass, and the runner's terminal already shows wall-clock.

   > **On a 1-pass scan this whole step prints nothing.** Step 5a still writes `run-1.md` — silently. `Pass 1/1 — …` is a progress line for a loop that is not running, and the plain path prints the bytes it printed before loop mode existed. Writing a file is not printing; the freeze covers printed output.

6. **Memory write.** **SKIP this step entirely when memory is off.** It is a step of Turn 4 and not a turn of its own because it can only be built from this turn's gated findings — the rows do not exist until the gate has run.

   a. **Build this run's rows** from the keys step 4 already built. One row per gated FINDING and per gated LEAD, four tab-separated columns:

   ```
   key	sha	title	kind
   ```

   - `key` — exactly the key step 4a built and step 4b tagged. Never rebuilt here: a key that differs between the tag and the row would report `NEW` and store a duplicate.
   - `sha` — `git rev-parse --short HEAD`. Not a git repo, or a repo with no commits: write `none` and carry on. The SHA is never part of the match, so a missing one costs nothing.
   - `title` — the finding title, tabs and newlines replaced by a single space, cut to 80 characters. Bars are safe: only the key is ever split on bars.
   - `kind` — `FINDING` or `LEAD`.

   Append the rows to the accumulating file, do not overwrite it:

   ```bash
   cat >> {bundle_dir}/scan-rows.tsv
   ```

   b. **Merge.** One `awk` pass over the photocopy and this scan's accumulated rows. `sort` + `join` is not used: `join` returns only matching rows, so keeping old-only and new-only rows would need three invocations and identical sort order across locales.

   ```bash
   awk -F'\t' -v OFS='\t' '
   FILENAME==ARGV[1] {
     if (FNR==1) next
     o_st[$1]=$2; o_sc[$1]=$3; o_sha[$1]=$4; o_ti[$1]=$5; o_ki[$1]=$6
     if (!($1 in o_seen)) { o_seen[$1]=1; oord[++on]=$1 }
     next
   }
   {
     if (!($1 in n_seen)) { n_seen[$1]=1; nord[++nn]=$1 }
     n_sha[$1]=$2; n_ti[$1]=$3; n_ki[$1]=$4
   }
   END {
     print "#solidity-auditor-memory v1", "key", "status", "scans", "sha", "title", "kind"
     for (i=1; i<=on; i++) {
       k = oord[i]
       if (k in n_seen) print k, "KNOWN", o_sc[k]+1, n_sha[k], n_ti[k], n_ki[k]
       else             print k, o_st[k], o_sc[k], o_sha[k], o_ti[k], o_ki[k]
     }
     for (i=1; i<=nn; i++) {
       k = nord[i]
       if (!(k in o_seen)) print k, "NEW", 1, n_sha[k], n_ti[k], n_ki[k]
     }
   }
   ' {bundle_dir}/memory-before.tsv {bundle_dir}/scan-rows.tsv > .solidity-auditor/memory.tsv.tmp
   ```

   The three cases, all visible in one command:

   | Case | Result |
   |---|---|
   | Old row re-found | `status` `KNOWN`, `scans` + 1, `sha` / `title` / `kind` taken from **this scan's** row |
   | Old row not re-found | carried over completely unchanged |
   | No old row | `status` `NEW`, `scans` 1 |

   Two rules the merge carries, and a later editor must not simplify away:

   - **`kind` is not part of the key.** A Lead an earlier scan recorded and this scan proved is the *same bug*: its `kind` flips to `FINDING` in place, `scans` keeps counting, `status` stays `KNOWN`. Demotion is the same rule running backwards and needs no special case. Putting `kind` in the key would remember one bug twice and list it twice.
   - **The merge is idempotent.** It always reads the pre-scan photocopy plus everything this scan has found so far, so `scans` rises by exactly 1 however many times it runs inside one scan. "Have I already counted this key?" is a question that cannot arise. Where one key appears more than once in `scan-rows.tsv`, the last row wins — which is what makes a Lead proven by a later pass land as `FINDING`.

   c. **Move it into place.**

   ```bash
   mv .solidity-auditor/memory.tsv.tmp .solidity-auditor/memory.tsv
   ```

   The temporary file sits beside the real one so the move stays on one disk. **The new file is always written before the old one is replaced** — an interrupted scan leaves one whole ledger, never half of one. Never write `memory.tsv` directly.

   `mkdir -p .solidity-auditor` before the first write. The user is expected to gitignore that directory; the ledger is not shared between machines or people.

   **Then write the other two `mem_` keys**, every pass, immediately after the move:

   ```bash
   printf '%s\t%s\n' mem_after "$(( $(wc -l < .solidity-auditor/memory.tsv) - 1 ))" \
     >> .solidity-auditor/runs/{stamp}/scope.tsv
   printf '%s\t%s\n' mem_sha "$(git rev-parse --short HEAD 2>/dev/null || echo none)" \
     >> .solidity-auditor/runs/{stamp}/scope.tsv
   ```

   Both are re-written on every pass and **last wins**, so the `Memory` row ends up describing the ledger as the scan left it, with no delete step and no "have I written this already?" flag. `mem_before` is not touched here — it was written once, in Turn 2 step 2c, and the row's arithmetic depends on it staying put.

   d. **In a loop, this step runs after every pass, and it rebuilds rather than appends.** Pass K+1 learns what pass K found by reading the merged ledger, so the write cannot wait for the end. But re-running the merge N times must not raise `scans` by N, because `scans` counts scans. The command above already holds this: it always reads the **pre-scan photocopy** plus **everything this scan has accumulated so far**, so `scans` rises by exactly 1 however many passes ran. Nothing new is invented per pass, and no "have I counted this key already?" flag exists to get wrong. It also keeps the interrupt rule for the whole loop: a loop killed at pass 3 keeps what passes 1 and 2 learned, written atomically.

   Then the next pass starts at **Turn 2 step 2c**, which rebuilds `known-findings.md` from the freshly merged `.solidity-auditor/memory.tsv` — not from the photocopy, or pass K+1 would never see pass K's findings — and re-cats the twelve bundles at Turn 2 step 3.

## Turn 5

**Turn 5 — Assemble, print, clean.** Runs **once per scan**, at any pass count, including a 1-pass scan and including a loop that stopped early. There is no path where a scan ends without this turn.

> **This turn no longer composes a report, and must never be re-taught to.** It used to combine the runs, dedup them, build the "Known from earlier scans" rows and format the whole thing — all of it model work, all of it at the moment of least remaining context. On a real 3-pass scan that produced 71 findings, it printed 14 of them in full, collapsed the rest into two lines, and **claimed a coverage it did not have**. Nothing was lost from disk; the report lied about what it was showing. A prose instruction cannot fix that, because the orchestrator under context pressure is the thing that failed.
>
> So the step that must not lose a finding holds **no model judgment**. The dedup, the `seen in k/N runs` counts, the strongest-kind rule, the "Known from earlier scans" rows and the whole report body are `assemble.sh`'s work now, and it is shell. This turn copies two files, runs it, counts, and prints. If you are reading this turn and it looks too thin to be a reporting step — that is the point.

1. **Copy the memory inputs in.** **SKIP when memory is off.** The assembler reads one directory, so anything it needs that lives in `{bundle_dir}` has to be in the runs directory before it runs:

   ```bash
   cp {bundle_dir}/memory-before.tsv {bundle_dir}/source-names.tsv .solidity-auditor/runs/{stamp}/
   ```

   `memory-before.tsv` is the **pruned** photocopy — the "Known from earlier scans" section is built from it, so a record the prune dropped must not reappear here. `source-names.tsv` turns a normalised key back into the spelling the source uses, so no reader is ever shown `gatewaytransfernative.withdrawtonativechain`.

   Only these two. `run-keys.tsv` and `scan-rows.tsv` are **not** copied: the keys this scan raised come from the assembler's own index of the run files, which is the same data with no copy step.

2. **Assemble the report.**

   ```bash
   bash {resolved_path}/assemble.sh --dir .solidity-auditor/runs/{stamp}
   ```

   It writes `.solidity-auditor/runs/{stamp}/full-report.md` — the whole report, banner line down to the disclaimer, ready to print word for word. It writes to a `.part` file and moves it into place, so a half-report never exists.

   **This is the only producer of a report in this skill.** Do not re-word its output, do not re-order it, do not add to it and do not summarise it in your own words. Do not re-read source to "verify the most critical claim" either — the agents did that and the gate filtered it; re-verification costs about five minutes and rarely changes a verdict.

   If it exits non-zero, print its stderr and stop. It has told you it could not read its own inputs, and there is nothing for a model to salvage by hand.

3. **Count the findings, then branch.** One `awk` over the assembled file, no model arithmetic anywhere:

   ```bash
   awk '
   /^## Leads$/  { sec="leads"; next }
   /^## /        { sec="";      next }
   /^\[[0-9]+\]/ { F++; next }
   sec=="leads" && /^- \*\*/ { L++ }
   /Confidence: [0-9]+/ && /^`/ {
     match($0, /Confidence: [0-9]+/)
     c = substr($0, RSTART+12, RLENGTH-12) + 0
     if (c >= 90) A++; else if (c >= 75) B++; else C++
   }
   END { printf "%d %d %d %d %d\n", F, L, A, B, C }
   ' .solidity-auditor/runs/{stamp}/full-report.md
   ```

   `F` is findings, `L` leads, and `A` / `B` / `C` the confidence buckets `100-90`, `89-75` and `below 75`.

   **Only `F` is printed** — it is the trigger and it is the total in `top 3 of {F}`. `L`, `A`, `B` and `C` are computed anyway and kept as a **self-check**, not as output.

   > **`A + B + C` must equal `F`.** The buckets are the whole set, in every mode. If they do not sum, the assembled file is malformed — a finding block the counter could not read is a finding block a reader may not get either. Say so and print the full report rather than a three-row slice of a file you cannot stand behind.

   **The trigger is more than 20 findings** — `F` alone. Leads are excluded, so a scan with 18 findings and 40 leads still prints in full.

   a. **`F` is 20 or fewer — print `full-report.md` word for word.** Every byte, nothing added, nothing cut, no preface. This is the path a plain scan of a small contract takes, and its printed bytes are exactly what this skill printed before any of this existed.

   b. **`F` is above 20 — print this instead**, and nothing else:

   ````markdown
   # 🔐 Security Review — {project-name}

   ---

   ## Scope

   {the Scope table from full-report.md, copied unchanged}

   ---

   Findings List — top 3 of {F}

   | # | Confidence | Title | Location | Seen |
   |---|---|---|---|---|
   {the three rows the extractor below printed}

   **→ Full findings list, every description and every fix:** {path}

   ---

   > ⚠️ {the disclaimer line from full-report.md, copied unchanged}
   ````

   - **`{path}`** — `.solidity-auditor/runs/{stamp}/full-report.md`, or, when `--file-output` was passed, the **copy** and only the copy: `{project-name}-pashov-ai-audit-report-{stamp}.md`. Never both. Two paths to identical bytes answers a question the runner did not ask at the moment they want one filename. This line is the only part of the block a flag changes.
   - **The Scope table's `Files reviewed` row is copied unchanged**, full paths and all. It is the one row that proves *which* `SafeMath.sol` was read, and a terminal that shortens it can no longer be diffed against the file it claims to summarise.
   - **No counts summary.** The `{F} findings, {L} leads` line and the `100-90 / 89-75 / below 75` split are **not** printed. `top 3 of {F}` already carries the only total a reader needs at this moment, and the bucket split answered a question nobody asked while standing between them and the path.

   > **The `{F}` in `top 3 of {F}` is what makes the slice safe, and it is not optional.** The rule this block obeys is that a report may print **less** than the scan found and may never look like it printed **more**. A bare list of three findings breaks that rule — a reader cannot tell a truncated list from a complete one. `top 3 of 52` cannot be misread, and it sits in the header rather than in a footnote for exactly that reason. An editor who drops the total, or moves it below the table, has re-created the failure this sentence exists to prevent.
   >
   > **This replaces the older "nothing is enumerated above the trigger" rule.** That rule was right about bare truncation and wrong to conclude that no slice can ever be honest; a counted slice is. Still enumerated **nowhere**: the Leads section, the "Known from earlier scans" section, and findings 4 and beyond. Three rows, and the header says three.

   **The three rows are extracted by shell, never typed from memory.** The orchestrator has by this point read dozens of findings and is the least reliable thing in the room; one `awk` over the assembled file cannot mis-rank, mis-quote a function name or invent a confidence. Pass `-v withseen=1` when the `Passes` row is printed — that is, when `{passes}` is above 1 — and `0` otherwise, because a plain scan's location line carries no `seen in k/N runs` and an empty column would print as a stub:

   ```bash
   awk -v withseen={1 or 0} '
   /^\[[0-9]+\] \*\*/ {
     if (n >= 3) exit
     line = $0
     match(line, /^\[[0-9]+\]/); conf = substr(line, RSTART+1, RLENGTH-2)
     sub(/^\[[0-9]+\] \*\*[0-9]+\. /, "", line); sub(/\*\*[ \t]*$/, "", line)
     title = line; want = 1; next
   }
   want && /^`/ {
     loc = $0
     match(loc, /^`[^`]*`/); fn = substr(loc, RSTART+1, RLENGTH-2)
     n++
     if (withseen) {
       seen = ""
       if (match(loc, /seen in [0-9]+\/[0-9]+ runs/)) seen = substr(loc, RSTART+8, RLENGTH-13)
       printf "| %d | [%s] | %s | `%s` | %s |\n", n, conf, title, fn, seen
     } else printf "| %d | [%s] | %s | `%s` |\n", n, conf, title, fn
     want = 0
   }
   ' .solidity-auditor/runs/{stamp}/full-report.md
   ```

   With `withseen=0` the awk prints four columns, so **drop `Seen` from the header row and from the separator row too** — a five-column header over four-column rows renders as a broken table in every terminal that draws one.

   The assembled file is already sorted highest-confidence first, so "top 3" is the first three finding blocks and no sort happens here. `exit` after the third block means the extractor does not read the rest of the file.

   **Fewer than 3 findings cannot reach this branch** — `F` is above 20 or this block is not printed — so the extractor needs no short-list case.

4. **`--file-output` — copy the assembled file.** Only when the flag was passed:

   ```bash
   cp .solidity-auditor/runs/{stamp}/full-report.md "{project-name}-pashov-ai-audit-report-{stamp}.md"
   ```

   A copy, not a second build. **Nothing regenerates**, so the flag cannot collapse the report the way the terminal once did — the file and the terminal are the same bytes by construction, whatever the finding count. The run files stay in `.solidity-auditor/runs/` and are never copied into the working directory.

5. **Auto-clean.** `rm -rf {bundle_dir}`. Bundle dir = transient build state, not an artifact. Don't skip. It runs once per scan, at any pass count, and it runs when the loop stopped early too. For debugging a loop: copy the bundle elsewhere before re-running.

   > **It runs last, and the order is load-bearing.** Step 1 copies two files **out of** `{bundle_dir}`, and step 2 reads them. Deleting the bundle before either has run destroys the "Known from earlier scans" section and the name map that keeps it readable — silently, because the assembler treats a missing input as an absent section and carries on. Steps 1 → 2 → 5 is not a style preference; moving this step earlier breaks a report that will still look finished.

   Do **not** add a per-pass partial clean — reclaiming disk between passes would mean rebuilding `source.md`, the one thing built once. Do **not** add a startup sweep of stale `.audit-*` directories: a crashed scan leaks one, as it does today, and a sweep would delete the working directory of a second scan running at the same time on the same repo.

