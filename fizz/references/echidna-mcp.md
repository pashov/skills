# Steering an Echidna Campaign Over MCP

Optional. Read this only if Step 10 is running Echidna with steering enabled (`--steer`, or the
user accepted the offer in guided mode), or if the user asks how to drive a running Echidna
campaign.

A fuzzing campaign left alone spends its whole budget on what its mutators happen to produce. When
coverage stops growing, the usual cause is a call ordering or a specific value the mutators are
unlikely to stumble into: a function that only works after two others, a key derived from state, a
handler that reverts on almost every input. Echidna >= 2.4 serves the
[Model Context Protocol](https://modelcontextprotocol.io/) from a running campaign, so an agent can
read what the campaign has and has not reached and push it towards the rest, **without stopping
it**.

Scope, and hard limits of what this does:

- **Echidna >= 2.4 only.** `--server <port>` served a one-way event stream before 2.4; it now serves
  MCP. Medusa has no equivalent.
- **It biases the fuzzer; it does not replace it.** An injected sequence is a hint the fuzzer
  explores around. Violations are still found, shrunk, and reported by the campaign itself, and
  triaged exactly as in Step 10.
- **It does not fix a broken harness.** A handler that reverts on every input needs a fix in the
  handler (Step 8), not an injected sequence.

---

## 1. Starting a campaign with the server

`run_echidna.js` passes the port through and adds `--format text` (the interactive UI would
otherwise own the terminal):

```bash
node {SKILL_PATH}/scripts/run_echidna.js {PROJECT_ROOT} --meta-dir {META_DIR} --timeout 1800 --server 8080
```

Run it as a tracked background job, as Step 10 already does. The log shows

```
[Server] MCP server listening on http://127.0.0.1:8080/mcp
```

once the campaign has compiled and deployed. Wait for that line before calling any tool. If the
port is taken, pick another; nothing else about the setup changes.

The server listens on `127.0.0.1` only and rejects any request that carries an `Origin` header, so a
web page cannot drive the campaign. Command-line clients send no `Origin` and are unaffected.

## 2. Calling the tools

`{SKILL_PATH}/scripts/echidna_mcp.js` is a dependency-free client (Node >= 18) that performs the MCP
handshake, calls one tool, and prints its answer. Use it from the shell; there is no need to
register an MCP server in the agent's own client:

```bash
node {SKILL_PATH}/scripts/echidna_mcp.js <tool> --port 8080 [--<arg> <value> ...]
node {SKILL_PATH}/scripts/echidna_mcp.js tools --port 8080      # list tools with descriptions
```

Every `--<arg> <value>` becomes a tool argument; a bare flag such as `--trace` is passed as `true`.
Exit codes: `0` answered, `1` the tool refused (its reason is printed; usually a bad sequence), `2`
no campaign is listening.

A user who wants the tools available natively can register the same endpoint in an MCP-capable
client instead (in Claude Code: `claude mcp add --transport http echidna http://127.0.0.1:8080/mcp`,
then restart the session). The script works in any agent that can run shell commands, so the skill
uses it.

### The tools

Report on the campaign:

| Tool | Arguments | Answer |
|---|---|---|
| `status` | none | JSON: `corpus_size`, `iterations`, `iteration_limit`, `coverage_points`, `tests_failed`, `tests_total`, `time_since_last_coverage_sec`, `recent_covered_functions`, `optimization_values`, `samples` |
| `target` | none | The contract under test and the functions the fuzzer calls, as canonical signatures |
| `show_coverage` | `--contract <Name>` | One contract's source, line by line: `*` executed, `r` reverted, `o` out of gas, `e` other error, blank never reached |
| `dump_lcov` | none | Writes an LCOV file of the coverage so far and returns its path |

Steer it:

| Tool | Arguments | Effect |
|---|---|---|
| `execute_sequence` | `--transactions "<calls>"` `[--trace]` | Runs a concrete sequence from the initial state and reports each call: completed, reverted, or `assertion_failed`, with gas and events. **The campaign is untouched**: no coverage, no corpus entry, no falsified test. |
| `inject_fuzz_transactions` | `--transactions "<calls>"` | Every fuzzing worker starts generating this ordering some of the time. `?` leaves an argument to the fuzzer. |
| `clear_fuzz_priorities` | none | Forgets every injected ordering. |
| `sample` | `--function <name or signature>` / `--function off` | Records how often a function is called, how often it fails, its return range, and recent revert summaries; results appear under `samples` in `status`. |
| `reload_corpus` | none | Adds sequences written to the corpus directory since the campaign started (they are mutated, not replayed). |

### The sequence syntax

Calls are written as in Solidity and separated by `;`. Only `inject_fuzz_transactions` accepts `?`:

```
handler_deposit(?); handler_lock(6007); handler_drain()
```

- **Name handlers, never `property_*` functions.** Echidna's assertion mode excludes the `prefix`
  functions from the calls it generates, and in a fizz suite properties run inside the handlers
  anyway. A sequence that names `property_x` is accepted by the parser but the fuzzer cannot place
  that call. Check names against `target`.
- **Every call goes to the contract under test** (`FuzzTester`). A function of another deployed
  contract cannot be addressed.
- Calls are checked against the ABI by name and argument count; a typo is refused with the reason.

## 3. How an injection behaves

Knowing this avoids misreading the results:

- **The ordering is pinned, not the sequence.** Up to three random calls are inserted between
  consecutive injected calls, the sequence may start from a prefix of a corpus entry (except on
  worker 0, which always starts from the initial state), and it is padded to `seqLen`. A value that
  only works in an exact state (`lock(total * 3 + 7)`) still lands, just not every time.
- **Workers use it with different probabilities**: worker 0 about 90% of the time, the others spread
  between 20% and 90%, so the campaign keeps exploring the corpus.
- **Injections accumulate.** Each one is added to the list a worker picks from. Call
  `clear_fuzz_priorities` before injecting a new round, or the budget is split across every ordering
  ever suggested.
- **Nothing is instant.** Workers read commands between sequences, and `status` reflects them on the
  next call. Poll; do not assume.

## 4. The steering loop

The default cadence is passive. Steer only when the numbers say the campaign is stuck.

1. **Watch.** Call `status` about once a minute. Note `coverage_points`, `corpus_size`,
   `tests_failed`, and `time_since_last_coverage_sec`.
2. **Detect a plateau.** Treat `time_since_last_coverage_sec` above ~120 seconds (or 5% of the
   campaign timeout, whichever is larger) as a plateau. Do nothing before that.
3. **Find what is missing.** Call `show_coverage` for each **target** contract, not the harness.
   Collect the lines that are blank (never reached) or `r` (reached, but always reverted). Line
   markers are per source line, so a one-line function whose `require` passes sometimes shows `*`;
   read the branch, not just the marker.
4. **Diagnose the gate.** For the handler that reaches the missing code, call `sample`, wait one
   poll, and read its `calls`, `reverts` and `recent_reverts`. Then `sample --function off`.
   - **Reverts on (almost) every call**, with argument values that are obviously out of range: the
     handler's clamping is wrong. Fix the handler, rebuild, and restart the campaign. Do not inject.
   - **Reverts because of state** (a stage flag, a missing approval, a cooldown): an ordering
     problem. Continue.
5. **Test the hypothesis without side effects.** Write the ordering with concrete values and run it
   with `execute_sequence`. Iterate until the target call `completed`. Add `--trace` to see why a
   call reverted.
6. **Inject.** `clear_fuzz_priorities`, then `inject_fuzz_transactions` with the working ordering.
   Replace concrete arguments with `?` wherever the exact value does not matter, so the fuzzer
   explores around it; keep the values that are the point (a derived key, a boundary amount).
7. **Check the effect** over the next two or three polls. `coverage_points` should rise and
   `time_since_last_coverage_sec` reset. If it did not, `clear_fuzz_priorities` and move on.
8. **Stop steering** after **five rounds** per campaign, or when the remaining unreached lines are
   explained (dead code, privileged paths the suite deliberately excludes). The campaign keeps
   running to its timeout either way.

### When `execute_sequence` reports `assertion_failed`

That is a lead, not a result: `execute_sequence` never marks a test as falsified. Inject the same
ordering so the campaign reproduces it, shrinks it, and saves a reproducer. Then handle it like any
Step 10 violation, including the harness-bug check. Never report a violation that only
`execute_sequence` has seen.

### Keep a steering log

Append one entry per round to `{PROJECT_ROOT}/{META_DIR}/steering-log.md`: the time, the
plateau (`coverage_points`, seconds since last coverage), the unreached lines, the diagnosis, the
sequence injected (or the handler fixed), and the coverage two polls later. The report writer reads
it.

## 5. Worked example

From a test campaign on a three-step vault (`deposit` raises `total` and unlocks stage 1 above 1000,
`lock(key)` requires `key == total * 3 + 7`, `drain()` requires stage 2; the handler for `drain`
checks the property `stage != 3`):

```
$ node echidna_mcp.js status --port 8080          # after 90 s, ~2.1M calls
{"corpus_size":5,"coverage_points":1011,...,"tests_failed":0,"time_since_last_coverage_sec":93}

$ node echidna_mcp.js sample --port 8080 --function handler_lock
$ node echidna_mcp.js status --port 8080          # 10 s later
... "function":"handler_lock(uint256)","calls":73474,"reverts":73474 ...

$ node echidna_mcp.js execute_sequence --port 8080 \
    --transactions "handler_deposit(2000); handler_lock(6007); handler_drain()"
{"failed_tx_index":3,"status":"assertion_failed", ... "handler_lock(6007)" ... "status":"completed" ...}

$ node echidna_mcp.js sample --port 8080 --function off
$ node echidna_mcp.js inject_fuzz_transactions --port 8080 \
    --transactions "handler_deposit(2000); handler_lock(6007); handler_drain()"
Fuzzing that sequence on 4 workers.
```

Within a second the campaign logged `Test handler_drain() falsified!`, and the final report
shrank it to the three calls above. `coverage_points` went from 1011 to 1280.

## 6. Reporting rules

1. A violation counts only when the **campaign** reports it (`failed!` in the log, a reproducer
   saved). Steering changes how fast it is found, not how it is triaged.
2. Say that the campaign was steered, and list the injected orderings from the steering log. A
   reviewer needs to know which states were reached by hint rather than by mutation.
3. Report coverage the campaign reached. `execute_sequence` runs do not count as coverage.
