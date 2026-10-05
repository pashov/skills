# Shared Scan Rules

## Bundle contents

Your bundle is five concatenated files: all in-scope source code, the SOP (HOW to think), your specialty agent (WHAT to look for), these shared rules (output format, dedup tags), and the report language rules (HOW to word a finding).

Read the whole bundle once at the start. The bundle contains all in-scope source. Use Read/Grep only for cross-file searches or out-of-scope context (interfaces/, lib/, mocks/, test/) — do not re-read in-scope files for the initial scan.

When matching function names, check both `functionName` and `_functionName` (Solidity convention).

## Mental tool protocol — MANDATORY

The three tools in `senior-auditor-sop.md` are NOT optional. Each tool has a specific trigger. **When the trigger fires, you MUST record the corresponding marker in the Worklog section of your checkpoint file BEFORE continuing.** No skipping. The markers live in the Worklog — they do NOT go into the FINDING/LEAD blocks.

### Triggers → required markers

| Trigger (the condition) | Marker (required immediately, literal `[Tool: ...]` syntax) | Content |
|---|---|---|
| You open a new function or contract to read | `[Feynman: <name>]` | Explain what it does in plain English — no Solidity jargon, no `mload`/`assembly`/`mstore`/`safeTransfer`/etc. Use as many sentences as you need until the explanation is solid. If your wording slips back to jargon, you're papering over an assumption — keep going. Wherever your plain-English explanation gets fuzzy or you have to reach for a Solidity term to keep it accurate, mark that spot — that is where bugs hide. |
| You stop on a line whose purpose isn't immediately clear | `[Socratic: <file:line> — why?]` | A one-line question that drills past "because that's how it's written." If your first answer is a restatement of the code, ask again. Stop when the answer exposes the implicit belief the code rests on — don't pad with extra steps just to hit a quota. |
| A code path reads as clean / a check looks sufficient / a guard looks correct | `[Inversion: <function>]` | Three concrete attacker moves that attempt to defeat the path. Specific addresses/values/states, not abstractions. |

### Rules

1. **Triggers are not optional.** If the condition fires, the marker follows. Always. No skipping.
2. **Use the literal `[Tool: ...]` syntax.** The orchestrator greps your checkpoint file for these tags after the run.
3. **You may emit a marker without a trigger.** Extra Feynman / Inversion markers are fine. You may NOT skip a marker after its trigger fired.
4. **The protocol applies to reasoning depth, not output volume.** Heavy use of these tools is what produces the audit work. Skipping them = surface-level scanning, which is the failure mode of every junior auditor.

The orchestrator verifies marker counts after every run. Skipped markers downgrade the value of your findings and are recorded as workflow violations.


## Cross-contract patterns

When you find a bug in one contract, **weaponize that pattern across every other contract in the bundle.** Search by function name AND by code pattern. Finding native/ERC20 confusion in `ContractA.onRevert` means you check every other contract's `onRevert` — missing a repeat instance is an audit failure.

After scanning: escalate every finding to its worst exploitable variant (DoS may hide fund theft). Then revisit every function where you found something and attack the other branches.

## Do not report

Admin-only functions doing admin things. Standard DeFi tradeoffs (MEV, rounding dust, first-depositor with MINIMUM_LIQUIDITY). Self-harm-only bugs. "Admin can rug" without a concrete mechanism.

## Output — the checkpoint file is the deliverable

Your findings live in your **checkpoint file** — the orchestrator names the path in its prompt. Your final message is a short summary only: the checkpoint path, the count of FINDINGs, the count of LEADs, one line on coverage. The orchestrator collects findings from the file, never from the message — a message that dies with its stream loses nothing, because the file already holds everything you reached.

**File layout** — two sections, in this order:

```
## Worklog

[Feynman: Vault] it takes the user's payment, keeps the protocol's cut, moves the rest on
[Socratic: Vault.sol:41 — why is the fee taken before the amount is checked?]
scanned: Vault.sol
scanned: Gateway.sol

## Findings

FINDING | ... and LEAD | ... blocks, newest last
```

Read the checkpoint once before your first rewrite — the runtime refuses to overwrite a file it has not watched you read, and on a respawn the file already holds your predecessor's work.

**Rewrite the whole file with each Write, and rewrite it often.**

- After every source file, contract, or seam you finish reviewing — even one that produced nothing — rewrite the file with the Worklog grown by its markers and one `scanned: <path>` line.
- The moment you reach a FINDING or a LEAD, it enters the file on the next rewrite. Nothing is held for the end.
- The late passes of your sweep — escalating every finding to its worst exploitable variant, revisiting every function you flagged — revise earlier blocks in place. Rewriting the whole file is what makes that possible; appending cannot revise, so never append.

The cadence is also your heartbeat. The orchestrator watches this file's growth to tell a working agent from a dead one — a file silent for over an hour reads as death, whether you are deep in thought or gone. Long silent thinking is not deep work; write as you go.

Findings are structured blocks:

FINDINGs have concrete, unguarded, exploitable attack paths. LEADs have real code smells with partial paths — default to LEAD over dropping.

**Every FINDING must have a `proof:` field** — concrete values, traces, or state sequences from the actual code. No proof = LEAD, no exceptions.

**One vulnerability per item.** Same root cause = one item. Different fixes needed = separate items.

```
FINDING | contract: Name | function: func | bug_class: kebab-tag | group_key: Contract | function | bug-class
path: caller → function → state change → impact
proof: concrete values/trace demonstrating the bug
description: one sentence
fix: one-sentence suggestion

LEAD | contract: Name | function: func | bug_class: kebab-tag | group_key: Contract | function | bug-class
code_smells: what you found
description: one sentence explaining trail and what remains unverified
```

The `group_key` enables deduplication: `ContractName | functionName | bug_class`. Agents may add custom fields.

## Language — MANDATORY

**Your `description:` and your `fix:` sentence are written in Simplified Technical English.** The
rules follow these ones in your bundle, under the heading "Report language". Read them, and
obey them in every finding and every lead you emit.

Your `description:` is what the report prints. Nothing downstream rewrites it into plain
English for you — the orchestrator pastes it into the report and the report goes to the
developer who must fix the code. One sentence, twenty-five words or fewer, active voice, no
`-ing` clause, no metaphor. Name who acts and what they get.

The rule reaches the wording and never the data. Your `bug_class` label, your `group_key`, the
contract and function names, and every line of code you quote are written exactly as the
source and the dedup rules require. `report-language.md` says which is which.

Your `path:` and `proof:` fields are working notes, not report text. Keep them concrete;
concrete is already plain.
