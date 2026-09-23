# Report Formatting

## The one rule

**A report must not overstate its own coverage.** Every other rule in this file serves that
one. The report may print **less** than the scan found — a mistyped marker, a dead agent, a
pass that never ran — and when it does it says so in words. It may never claim to print
**more**. A report that shows 14 findings and reads as if it showed all of them is the defect
this whole design exists to kill.

## Who reads this file

Nothing composes a report from this template any more. There are two readers:

- **SKILL.md Turn 4 step 5a** — the pass writing its findings into `run-K.md`. It uses the
  **finding block** shape below: title line, location line, `**Description**`, diff `**Fix**`
  block. Those bytes are pasted straight through into the report, so they are written in the
  report's own shape while the pass still has context to spare.
- **`references/assemble.sh`** — the assembler. Everything below the finding block — the
  banner, the Scope table, the ordering, the Findings List, the Leads section, "Known from
  earlier scans", the disclaimer — is what the assembler emits.

**This file settles the shape. `report-language.md` settles the words.** Every sentence a
human reads in the report — the finding title, the Description, the Lead description, the
Lead's code smells — is written in Simplified Technical English, and that file holds the rules.
It is read by the same Turn 4 step 5a that writes the block, and it is in all twelve agent
bundles. It never reaches the diff in a **Fix** block, the bug-class label inside a key, or an
identifier on a location line: those three are data, and it says so.

**The template is the contract the assembler emits, not a shape a model imitates.** A later
editor must not re-teach the orchestrator to write it. The orchestrator under context pressure
is the thing that failed; the step that must not lose a finding holds no model judgment.

## Report Path

**Every scan assembles `.solidity-auditor/runs/{stamp}/full-report.md`** — the whole report,
banner line down to the disclaimer — at any pass count, with or without flags. That file is
the report. There is exactly one producer of it, and it is the assembler.

`--file-output` makes a **copy** of that file into the current working directory as
`{project-name}-pashov-ai-audit-report-{stamp}.md`, where `{project-name}` is the repo root
basename and `{stamp}` is `YYYYMMDD-HHMMSS` at scan time. A copy, not a second build —
nothing regenerates, so the flag cannot collapse the report the way the terminal once did. The
flag never causes a report to be produced; it only decides whether a copy lands where the
runner can see it.

The `run-K.md` files stay in `.solidity-auditor/runs/{stamp}/` under the same stamp, so a
report and the runs that produced it are tied together by eye. They are never copied into the
working directory — they are memory, not reports.

## Output Format

This is what the assembler emits.

````
# 🔐 Security Review — <ContractName or repo name>

---

## Scope

|  |  |
| --- | --- |
| **Mode** | ALL / default / filename                              |
| **Files reviewed** | `File1.sol` · `File2.sol`<br>`File3.sol` · `File4.sol` | <!-- every file, 3 per line -->
| **Confidence threshold (1-100)** | N                                    |
| **Passes** | 3                                                      | <!-- only when passes > 1 -->
| **Memory** | 12 records before this scan · 14 after · `a1b2c3d`     | <!-- only when memory is on -->
| **Run files** | ⚠️ 2 findings marked, 1 readable. 1 could not be read. | <!-- only when the structure check disagrees -->

---

## Findings

[95] **1. <Title>**

`ContractName.functionName` · Confidence: 95 · seen in 2/3 runs · KNOWN (4 scans) <!-- runs segment only when passes > 1; memory segment only when memory is on -->

**Description**
<The vulnerable code pattern and why it is exploitable, in 1 short sentence>

**Fix**

```diff
- vulnerable line(s)
+ fixed line(s)
```

---

[82] **2. <Title>**

`ContractName.functionName` · Confidence: 82

**Description**
<The vulnerable code pattern and why it is exploitable, in 1 short sentence>

**Fix**

```diff
- vulnerable line(s)
+ fixed line(s)
```

---

< ... all above-threshold findings >

---

[60] **3. <Title>**

`ContractName.functionName` · Confidence: 60

**Description**
<The vulnerable code pattern and why it is exploitable, in 1 short sentence>

---

< ... all below-threshold findings (description only, no Fix block) >

---

Findings List

| # | Confidence | Title |
|---|---|---|
| 1 | [95] | <title> |
| 2 | [82] | <title> |
| 3 | [75] | <title> |
| | | **Below Confidence Threshold** |
| 4 | [60] | <title> |

---

## Leads

_Vulnerability trails with concrete code smells where the full exploit path could not be completed in one analysis pass. These are not false positives — they are high-signal leads for manual review. Not scored._

- **<Title>** — `Contract.function` · NEW — Code smells: <missing guard, unsafe arithmetic, etc.> — <1-2 sentence description of the trail and what remains unverified> <!-- memory segment only when memory is on -->
- **<Title>** — `Contract.function` · seen in 2/3 runs · KNOWN (2 scans) — Code smells: <...> — <1-2 sentence description> <!-- runs segment only when passes > 1 -->

---

## Known from earlier scans

<!-- only when memory is on AND the ledger held at least one record — see Memory in the report -->

_Recorded by earlier scans of this repo, not raised again by this one. Not re-checked — a record here may be fixed, or may still be live and missed. `.solidity-auditor/memory.tsv`._

| Scans | Kind | Location | Title |
|---|---|---|---|
| 4 | FINDING | `Router.swap` | Swap trusts a spot price as an oracle |
| 2 | LEAD | `Vault.sweep` | Sweep lets the owner take user deposits |

---

> ⚠️ This review was performed by an AI assistant. AI analysis can never verify the complete absence of vulnerabilities and no guarantee of security is given. Team security reviews, bug bounty programs, and on-chain monitoring are strongly recommended. For a consultation regarding your projects' security, visit [https://www.pashov.com](https://www.pashov.com)

````

**Rules describing the output**, all of them held by the assembler and none of them addressed
to a model:

- Findings are sorted by confidence, highest first.
- A finding at or above the threshold carries a **Description** and a diff **Fix** block. One
  below carries the **Description** only. Nothing in the run file marks which side of the line
  a finding sits on — it is re-derived from the confidence, so there is one source of truth.
- The **Below Confidence Threshold** separator row is printed whenever at least one finding
  falls below the threshold, and left out when none does. Without it the table runs 1, 2, 3
  with nothing to mark the boundary, so a reader of the table alone cannot tell which findings
  carry no **Fix** block.
- **Empty cases say so in words, never with an empty table**: `_None — this scan raised no
  findings._` in place of the Findings List, `_None._` under Leads, `**Body missing** — pass K
  raised this finding and wrote no description.` in place of a body.
- **A `Run files` row appears only when the structure check disagrees.** The model types the
  markers that bound each finding in a run file, so it can mistype one. The assembler counts
  open markers against close markers against readable blocks, and prints the disagreement as a
  Scope row naming how many findings could not be read. Everything readable is still printed
  and the assembler never stops. That row is the one rule at the top made mechanical.
- **The Scope table's column padding is not part of the shape.** Markdown renders
  `| **Mode** | default |` and a space-padded form identically, and the padding above is for
  reading this file. Content and order are the contract; character widths are not.

**The threshold is 75**, set in `judging.md` and printed in the Scope row above. It is named
in `judging.md` and nowhere else; this file reads it from there. A finding at 75 or above gets
a description and a **Fix** block, one below 75 gets the description only. A promoted lead
lands at exactly 75, so it clears — that is why the number is 75.

## The size trigger

**More than 20 findings.** At 20 the terminal prints the assembled file word for word; at 21
it stops printing findings. Findings only — above and below the threshold together. **Leads
are excluded from the trigger count**, so a scan with 18 findings and 40 leads prints in full.

The trigger is on **size, not on flags**. A plain scan of a small contract is unchanged; a
plain scan of a big one gets the new shape.

**Above the trigger the terminal prints four things:** the banner, the Scope table unchanged,
a **Findings List holding the top 3 findings**, and the path to the full report — then the
disclaimer. About fifteen lines.

The full report is unaffected. Above the trigger, as below it, `full-report.md` holds every
finding in the shape above — only the terminal changes.

**The slice is honest because it is counted.** The table's header reads
`Findings List — top 3 of {F}`, and that `{F}` is the whole rule:

- **A report may print less than the scan found. It may never look like it printed more.**
  A bare list of three findings breaks that — a reader cannot tell a truncated list from a
  complete one. `top 3 of 52` cannot be misread.
- **The total goes in the header, not a footnote.** A reader who sees the table sees the
  total in the same glance. This is not a style choice; a footnote can be scrolled past.
- **Three rows, and nothing else is enumerated.** No Leads, no "Known from earlier scans",
  no findings past the third.

> **This replaces the older "nothing is enumerated above the trigger" rule**, which forbade
> every top-N slice. That rule was right that bare truncation lies and wrong to conclude no
> slice can be honest; a counted one is. A later editor must not restore the blanket ban by
> citing the half of the argument that survived.

**The rows are extracted by shell, never typed.** One `awk` over the assembled file — which is
already sorted highest-confidence first, so no sort happens in the terminal step. The
orchestrator has read dozens of findings by then and is the least reliable thing in the room;
the extractor cannot mis-rank, mis-quote a function name or invent a confidence. The command
is in `dedup-and-assembly.md` Turn 5 step 3b.

**The `Seen` column appears only when the `Passes` row does** — that is, when the pass count is
above 1. A plain scan's location line carries no `seen in k/N runs`, so the column is dropped
from the header, the separator and the rows together. A five-column header over four-column
rows draws as a broken table.

**There is no counts summary.** The `{F} findings, {L} leads` line and the
`100-90 / 89-75 / below 75` split are not printed. `top 3 of {F}` carries the only total the
moment needs, and the bucket split stood between the reader and the path. The buckets are still
**computed** as a self-check — `A + B + C` must equal `F`, in every mode, or the assembled file
is malformed and the scan says so instead of printing a slice of it.

The path line names `.solidity-auditor/runs/{stamp}/full-report.md`, or — when `--file-output`
was passed — the **copy** and only the copy. Never both: two paths to identical bytes answer a
question the runner did not ask at the moment they want one filename. That line is the only
part of the block a flag changes.

The exact wording, spacing and order of the block are in `dedup-and-assembly.md` Turn 5 step
3b, which is where the terminal is printed.

## The freeze

**A small scan with no flags prints what it printed before any of this existed.** Below the
trigger the terminal prints `full-report.md` word for word — every byte, nothing added,
nothing cut, no preface — so the freeze is a property of the assembled file.

The freeze is a **diff against `golden/plain-full-report.md`**, the frozen plain-path report,
and it covers the report's **content and order, not its column padding** and not what lands on
disk. Byte-identity against "today" was tried and is unmeetable: no captured report exists
anywhere, and today's bytes were composed by a model from a template that contradicted itself.
The golden file is what replaced it.

What the freeze does **not** cover: writing files. Every scan now writes a runs directory and
assembles a report there, at any pass count. Writing a file is not printing, and the freeze is
on printed output.

## Memory in the report

Everything in this section is printed **only when memory is on** (`--memory`, or a pass count
above 1). With memory off the assembled file carries no extra rows, no extra segments, no
extra sections and no dangling `·`, and below the trigger it still diffs clean against the
golden file.

**Segment order on the meta line.** One dot-separated chain, in a fixed order:

```
`ContractName.functionName` · Confidence: 95 · seen in 2/3 runs · KNOWN (4 scans)
```

location · confidence · runs · memory. **A segment appears only when it carries information** —
`seen in k/N runs` needs more than one run, `KNOWN (n scans)` / `NEW` needs memory on. So:

| Scan | Meta line |
|---|---|
| 1 pass, no flags | `` `Vault.withdraw` · Confidence: 95 `` |
| 1 pass, `--memory` | `` … · Confidence: 95 · KNOWN (4 scans) `` |
| 3 passes | `` … · Confidence: 95 · seen in 2/3 runs · KNOWN (4 scans) `` |

`KNOWN (4 scans)` and `NEW` are the ledger's own two words, so the report and the file say the
same thing. **`n` counts this scan.** The tag is derived by the assembler from
`memory-before.tsv` — the pre-scan photocopy — and `n` is that row's `scans` **plus one**: the
scan that is printing has just found it again, and the ledger already holds that same number.
Printing the stored count instead would show a report one behind its own ledger. `NEW` carries
no count. The tag is **not** carried in the run-file marker: one source, so the report and the
ledger cannot disagree.

The `Scans` column of "Known from earlier scans" is the opposite case and is printed **as
stored**: this scan did not raise those records, so nothing about them counts up. The
**Findings List** table is unchanged — it stays `# | Confidence | Title`.

Leads carry the same segments as findings, on their own line, because a Lead is a full ledger
record.

**The `Memory` row in Scope.** `<records in the ledger before this scan> records before this
scan · <records after the merge> after · `<sha>``. The SHA is the one every row of this scan
wrote; `none` when the repo has no commits. The row states the whole ledger state in one line,
so the two counts show at a glance what the scan added.

**The "before" count is the count after the prune** — the row count of `memory-before.tsv` as
the merge reads it, not the row count of the file the scan opened. On a scan where the prune
drops records the two differ, and using the pre-prune number makes the row's own arithmetic
wrong: a scan that opened 4 records, pruned 1 and added 12 would read `4 records before this
scan · 15 after`, and a reader counting 4 + 12 gets 16. The prune is already reported on its
own line (`Pruned N records …`), so the Scope row does not restate it and must not contradict
it.

**Building "Known from earlier scans".** These are the records the ledger already held that
this scan did **not** raise again. It is **not** a filter on the `status` column — `status`
stays `KNOWN` once set and never marks the not-found-again case.

**The `comm` block that used to sit here is now in `assemble.sh`**, under
`# Known from earlier scans`. It reads two inputs Turn 5 copies into the runs directory:
`memory-before.tsv`, the pruned photocopy, and `source-names.tsv`. The keys this scan raised
come from the assembler's own index of the run files, so no `run-keys.tsv` or `scan-rows.tsv`
is carried in — the run files are the record. It is computed once per scan, scoped to the
whole scan and not to the last run, so a bug found in run 1 but not in run 3 does not appear
here.

Each key `comm` returns is one row: `Scans`, `Kind` and `Title` come straight from its row in
`memory-before.tsv`. `Location` is rebuilt from the key's first two segments, which are stored
normalised (lower case, hyphenated) and cannot be printed as they are — each segment is looked
up in `source-names.tsv` and printed as the source spells it, or printed as stored when it is
not in the map, which happens on a named-file scan where the contract was never assembled into
`source.md`.

Three states, and no fourth:

- The ledger held records this scan did not raise → the table above.
- The ledger held records and this scan raised **every one** → `_None — every record in the
  ledger was raised again by this scan._`
- Memory is off, or the ledger is empty (first-ever scan) → **no section at all.** A plain
  scan grows no empty headings.

The italic line under the heading is load-bearing and is printed verbatim: these records are
**not re-checked**. A reader must not take the section as "still open", and must not take it
as "fixed".

## Loop mode in the report

Everything in this section is printed **only when the pass count is above 1**. One pass prints
none of it.

**One report per scan.** However many passes ran, the runner sees one combined list. The
per-pass output is one summary line each (SKILL.md Turn 4 step 5b) and one `run-K.md` in
`.solidity-auditor/runs/{stamp}/` — neither is a report.

**`seen in k/N runs`.** `k` is how many of this scan's runs raised that group key; `N` is how
many passes produced a run file. A pass that collapsed produced none, so it is not in `N` — a
report must not claim a run that never happened. The segment sits between confidence and the
memory tag, and it is printed on Leads exactly as it is on findings, because a Lead is a full
ledger record.

**`seen in k/N runs` and `KNOWN (n scans)` count different things and must never be mixed.**
`k/N` counts runs inside **this** scan and is never written to the ledger. `n` counts scans and
comes from the ledger. A finding first raised by pass 1 of this scan is `NEW` in pass 3 — it is
this scan's work, however many of its runs saw it.

**Which write-up survives the merge.** One winner per key: strongest kind, then highest
confidence, then the later pass — a later pass read the ledger every earlier pass wrote, so it
is the better-informed write-up. **Confidence is untouched by the merge.** A finding three runs
saw keeps the number the runs gave it; repetition is reported on the line, never scored, and
`seen in 3/3 runs` is there for the reader to weigh.

**The `Passes` row in Scope** is composed by the assembler from recorded facts, never written
as prose. It carries degradation text whenever the scan did not run whole — a report claiming
3 passes when one of them ran three-quarters of its agents overstates its own coverage:

```
| **Passes** | 3                                                    |
| **Passes** | 3 (pass 2 ran 11/12 agents)                          |
| **Passes** | 2 of 3 (pass 3 failed)                               |
| **Passes** | 2 of 3 (pass 1 ran 11/12 agents, pass 3 failed)      |
```

The `R of P` prefix comes from counting run files. The dead agent's **name** never appears
here — it stays in the run file, in the sentence under the `<!--RUN-->` marker.

On a 1-pass scan this row is suppressed, so a pass 1 that produced nothing is reported by the
`Run files` row instead: `⚠️ No pass produced a run file. This scan reviewed nothing.`
