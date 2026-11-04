# Symbolic Verification (Echidna Verification Mode)

Optional. Read this only if Step 10.5 is running, or if the user asks about proving properties
instead of fuzzing them.

Fuzzing samples the input space; it can find bugs but never proves their absence. Echidna's
**verification mode** runs the same Solidity through a symbolic engine (hevm) plus an SMT solver
and, when it succeeds, answers for **every** input rather than the ones a campaign happened to
try. This document explains when that is worth doing, what it actually buys, and what it costs.

Scope of this document, and hard limits of what this skill does:

- **Verification mode only.** Echidna also has an *exploration* mode that mixes symbolic execution
  into a stateful fuzzing campaign. It is out of scope here — the fuzz campaign in Step 10 is the
  stateful story.
- **Echidna >= 2.4 only.** This guide follows Echidna 2.4.0, which ships hevm's arithmetic
  abstraction (always on) and the `symExecSolverMemory` option. On older Echidna, skip this
  entirely and do not try to emulate it with older flags.
- **Never a replacement for the fuzz campaign.** Everything a proof leaves out — and that is most
  of the protocol — is still covered only by Step 10.

Everything below — the result statuses, the harness patterns, the abstraction's soundness contract,
the walls — comes from running this with Echidna 2.4.0 on real code, including a full "prove the core, fuzz the rest"
pass over an audited DeFi protocol. Echidna's own documentation, and the hevm and halmos
limitations pages, cover the tooling itself.

---

## 1. When this is worth running (and when it is not)

Verification mode is **not** the default choice. On most code a fuzzer finds counterexamples
faster and with far less setup. Reach for a proof when all of these are true:

| Condition | Why it matters |
|---|---|
| The property is **stateless / single-transaction** | Verification mode explores the constructor, then one symbolic call. Multi-transaction properties are out of reach. |
| The target is **math**, not plumbing | Conversion, preview, quote, share-price, rounding, fee-split functions. `view`/`pure` is ideal. |
| Inputs are **value types** | Echidna refuses to symbolically execute functions taking dynamic types (`bytes`, arrays, dynamic structs). |
| No unbounded loops | A `while` over a symbolic bound either explodes or needs a loop invariant the tool does not have. |
| The code is **already fuzzed clean** | A proof is an assurance upgrade on top of a clean campaign, not a way to find the first bug. |

Concretely, in a fizz run the good candidates are already collected in Step 9a as
**CONVERSION_FUNCTIONS** (`convertTo*`, `preview*`, `toAssets`, `toShares`) and the round-trip /
rounding / monotonicity properties from the Round-Trip & Rounding Analyst.

Skip it when: the protocol's risk is emergent across transactions (most lending, most AMM
sequencing bugs, most access-control mistakes), the math is trivial, or the user just wants a
working fuzz suite. Say so plainly rather than running a proof that will time out.

---

## 2. Why the generated fizz suite is the wrong target

This is the single most common mistake, and it is worth being explicit about.

The fizz suite splits work between *handlers* (which perform the call) and `property_*` functions
(which assert, and take no arguments). Verification mode reasons about **one** symbolic
transaction, so:

- a handler mutates state but usually contains no assertion → nothing to prove;
- a `property_*` function contains the assertion but has no symbolic inputs → nothing to explore.

Running verification mode against `FuzzTester` therefore produces a lot of trivially "verified"
methods and proves nothing interesting. This is a known limitation of the split-harness style that
fuzzing campaigns favour, not something to work around by loosening the suite.

**So proofs live in their own small harness** — `{SUITE_DIR}/symbolic/Prove*.t.sol` — separate from
the stateful suite, where a single function takes symbolic arguments, does the call, and asserts,
all in one transaction.

---

## 3. The harness: two patterns

Both patterns use a `prove_` prefix by convention, and the config lists those names in
`symExecTargets`. Echidna 2.4 picks up `prove*` and `check*` functions on its own when
`symExecTargets` is empty, but it then also verifies every other function that contains an
assertion, including inherited `testFuzz_*` tests without the `uint128` bound. Keep the explicit
list.

### Pattern A — promote an existing stateless test (lowest effort, highest value)

If the repo already has `testFuzz_*` unit tests over the math, a proof is a one-line wrapper: the
same test body, quantified over all inputs instead of sampled. The only addition is a uniform
bound (see §5):

```solidity
contract ProveConversions is ConversionFuzzTests {   // the repo's own test contract
    function prove_convertToShares(uint256 rate, uint256 amount) public {
        require(rate <= type(uint128).max && amount <= type(uint128).max);
        testFuzz_convertToShares(rate, amount);         // unmodified original test
    }
}
```

The property and its exact assertion stay the repo's, not a copy that can drift. On an audited
DeFi protocol this pattern turned the repo's own stateless fuzz tests into theorems, one `require`
apiece — which is why it is the first thing to try.

### Pattern B — a relational property written for the prover

When the exact closed form is out of the solver's reach, a weaker property often still rules out
the attack. These are the three shapes that pay off most:

```solidity
// monotonicity: more in never yields less out (blocks split/reorder value extraction)
function prove_shares_monotonic(uint256 a, uint256 b) public {
    require(a <= b && b <= type(uint128).max);
    assert(vault.convertToShares(a) <= vault.convertToShares(b));
}

// round-trip: value -> shares -> value never grows (blocks inflation attacks)
function prove_roundtrip_no_inflation(uint256 v) public {
    require(v <= type(uint128).max);
    assert(vault.convertToAssets(vault.convertToShares(v)) <= v);
}

// rounding bound: round-up and round-down never differ by more than one wei
function prove_rounding_tight(uint256 x) public {
    require(x <= type(uint128).max);
    assert(f_roundUp(x) - f_roundDown(x) <= 1);
}
```

Monotonicity is a genuine safety property, not a consolation prize: a non-monotonic conversion is
exactly what lets a user split or reorder amounts to extract value.

### The mapping wall, and the one sound workaround

Properties that read balances through a real `MockERC20` frequently die on setup: a
`mapping(address => uint256)` read is a keccak-indexed SMT term, and nested inside abstracted
non-linear arithmetic it puts the query past the solver. The workaround is a token whose
`balanceOf` is a **single storage slot** instead of a mapping, so each read is one clean symbolic
value, with the protocol contract left untouched.

**This is only sound when every property reads each token at exactly one holder and never moves
tokens between holders.** If the property deposits, transfers, or involves two holders of the same
token, the single-slot model is wrong and the "proof" is meaningless. In that case do not model
around it — send the property to the fuzzer and record it as out of reach.

---

## 4. Running it

Config (`{SUITE_DIR}/symbolic/echidna-verify.yaml`, copied from
`{SKILL_PATH}/templates/symbolic/echidna-verify.yaml`):

```yaml
testMode: verification        # implies symExec: true, workers: 0, seqLen: 1
symExecSMTSolver: bitwuzla    # the default; z3 is much weaker here
symExecMaxExplore: 5000       # max branches explored (default 10)
symExecMaxIters: 5000         # max revisits of one instruction (default 5)
symExecTimeout: 300           # per-SMT-query seconds; default 30 is usually too low
symExecSolverMemory: 16384    # per-solver memory limit in MB (the default); see §6
testMaxGas: 1000000000        # keep gas-heavy paths from being cut as out-of-gas
symExecTargets:               # union of every prove_* across the symbolic contracts;
  - prove_shares_monotonic    # matching is per-contract, so one list serves all files
  - prove_roundtrip_no_inflation
```

`testMode: verification` forces one symbolic worker, no fuzzing workers, and one transaction per
sequence, so `symExec`, `workers`, and `seqLen` do not need to be set. There is no
`symExecAbstractArith` key in 2.4: the abstraction is always on (§5), and Echidna warns
`unused option` if the key is present.

Run one contract at a time:

```bash
echidna {SUITE_DIR}/symbolic/ProveMath.t.sol --contract ProveMath \
        --config {SUITE_DIR}/symbolic/echidna-verify.yaml --format text
```

Operational notes:

- **The exit code means something.** Echidna exits 0 when every property is `verified` or
  `passed`, and 1 when any property `failed` or `could not evaluate`. A non-zero exit is a result
  to read, not a crash. In a loop over several contracts, record the code and keep going.
- **Per-property results are printed when Echidna exits.** While it runs, `--format text` shows
  only what the symbolic worker is doing (`Verifying ...`, warnings). `--format json` gives the
  same results as `verified` / `passed` / `solved` / `error` statuses.
- `--sym-exec-target <name>` (repeatable) runs selected properties without editing the config,
  the fastest way to iterate on one stubborn proof.
- **bitwuzla must be on `PATH`.** It is the default solver; verify it before running.

### Reading the result

| Result line | Meaning | What to do |
|---|---|---|
| `verified ✅` | Every path explored, every query solved, no counterexample. Holds for all inputs in the stated domain. | Record it. This is the product. |
| `passed! 🎉` | No counterexample, but not a proof: some SMT query came back `unknown` (usually a timeout), some paths were only partially explored, or hevm hit an unsupported feature (e.g. a symbolic `pow` exponent). The worker's warnings say which. | **Not a proof.** Report as "no counterexample", tune once (§6), and keep the property in the fuzz campaign. |
| `failed!💥` | hevm found a model, and Echidna replayed it concretely and the assertion failed. The call sequence is printed. | A concrete counterexample. Check it against the harness assumptions (§5), then treat it as a bug. |
| `could not evaluate ☣` | The execution environment broke, usually in the constructor or `setUp`. | Not a result. Fix or simplify the setup. |

If a property never prints `Verifying ...` and the log says `Skipped verification of method`, it
was not in `symExecTargets` or takes dynamic arguments.

Tune once, then stop. A property that resists two rounds of tuning is out of reach; that is a
normal outcome and belongs in the report as such.

---

## 5. Abstract arithmetic: the key trade, and its soundness contract

`a * b / c` over three unknown 256-bit values is the shape of essentially all DeFi accounting, and
it is the shape SMT solvers handle worst: an unknown×unknown multiply bitblasts into a 256×256
multiplier, division is worse, and bounding the *values* does not help because the terms are still
256 bits wide.

Echidna 2.4 runs hevm's arithmetic abstraction ([argotorg/hevm#1075](https://github.com/argotorg/hevm/pull/1075))
in every symbolic run. Instead of computing what `a * b` is, hevm treats the result as a sealed
value and gives the solver a list of facts true of *every* product and quotient: a product never
shrinks when an input grows, `a * b == b * a`, a quotient never grows when the divisor does,
constant factors cancel, and so on. The effect can be dramatic: properties that return `unknown`
after a two-minute native timeout can discharge in under a second.

**The soundness contract, which must be respected when reporting:**

- **A `verified` result is sound.** Every fact used holds for ordinary arithmetic, so the proof
  covers a more general contract of which the deployed one is a special case.
- **A `failed` result is concrete.** When the abstract query has a model, hevm checks it again with
  exact multiplication, and Echidna then replays the resulting transaction on the concrete EVM.
  Only a transaction that fails there is reported. What remains to check is the harness: a
  counterexample that violates an assumption the harness should have made (a missing bound, an
  unrealistic modelled token) is a harness bug, not a protocol bug.

**The abstraction is not always a win.** It exists for pure, non-mutating math over symbolic
divisors. With constant divisors (`/1e18`, `/1e27`) or on storage-mutating proofs it can add solver
work, and a property may come back `passed` where native arithmetic would prove it. Echidna 2.4
has no switch to turn it off. If a property only resists under the abstraction, record it as out
of reach; running it through hevm directly (`hevm test --no-abstract-arith`) is outside this step.

Safe to tune freely: `symExecMaxExplore`, `symExecMaxIters`, `symExecTimeout`,
`symExecSolverMemory`, and `symExecNSolvers`. They change completeness and resources, never
validity. Do **not** raise `symExecAskSMTIters`; its default of 1 is the sound setting.

### The `uint128` bound

The no-overflow facts hold while products fit in 256 bits, so proofs carry a uniform
`require(x <= type(uint128).max)` on each symbolic input (and on derived sums such as
`totalAssets()`). That is ~3×10^20 tokens at 18 decimals — far past any real supply, but it **is** a
real assumption and must be stated whenever the result is reported. Do not quietly drop it.

---

## 6. Tuning, by warning

Read the symbolic worker's output and react only to what it actually says. In verification mode
the warnings name the method:

| Warning | Fix |
|---|---|
| `Partial explored path(s) during symbolic verification of method ...: Branches too deep ...` | Raise `symExecMaxExplore`. This is the most important knob; it is a branch budget, so raise it in steps rather than to a huge value. |
| `Partial explored path(s) ... : Max iterations reached ...` | Raise `symExecMaxIters`: a loop, a repeatedly-called function, or optimizer-deduplicated code. |
| `Error(s) solving constraints produced by method ...: "Result unknown by SMT solver"` | Raise `symExecTimeout` (30 → 120 → 300). If it persists, the query is out of the solver's reach under the abstraction (§5). |
| The solver dies with `std::bad_alloc` or an out-of-memory error | Each solver process is capped by `symExecSolverMemory` (MB, default 16384). hevm enforces the cap only on Linux. Keep `symExecSolverMemory × symExecNSolvers` below the machine's free RAM; lower `symExecNSolvers` before lowering the cap. |
| `could not evaluate ☣`, or the constructor/`setUp` path never completes | The setup is the wall, not the property. Simplify the setup (see the single-slot token in §3) or drop the property. |

---

## 7. Costs, stated plainly

Before proposing this to a user, be honest about all of it:

- **Human time.** The harness is hand-written and the mapping/setup walls are hit by trial. On a
  real protocol this is hours to days of work, not minutes — and it is the part no tool automates.
- **Machine time.** Per-property runtimes range from under a second to hours; some never finish.
  On an audited DeFi protocol with Echidna 2.4.0, 56 of 60 properties verified in about half an
  hour in total, most in about a second, and the four that ended `passed` took another five hours
  of solver time between them. Reaching a settled suite took far longer than running it does.
- **It expires on every code change.** A proof is about specific bytecode. Any edit to the proven
  functions invalidates every result and the whole set must be re-run.
- **Assumptions are part of the result.** The `uint128` bound, any modelled token, any `require`
  in the harness — all of it narrows what was proven. A proof of the wrong model is worse than no
  proof, because it reads like assurance.
- **Coverage is narrow by construction.** One transaction, from the constructor, calling only
  contracts your harness deployed. No reentrancy from unknown external addresses. Infinite gas is
  assumed. Multi-transaction and emergent behaviour are entirely the fuzzer's job.
- **Partial results are the norm.** Expect a meaningful fraction of properties to land on `passed`
  or `could not evaluate`. That is not a failed run; it is the shape of the technique today.

The benefits, equally plainly:

- A `verified` property holds for **every** input in the stated domain, against the real compiled
  bytecode — a strictly stronger statement than any campaign length can produce.
- It requires **no new cheatcodes and no rewritten tests**: existing stateless tests are promoted
  by a wrapper.
- For a reviewer, a verified property is code that no longer needs to be re-read by hand, which
  concentrates attention on the properties that stayed out of reach.
- The fuzzer independently cross-checks the proofs: if a modelling assumption were unsound, the
  prover would still say `verified`, but a campaign on the same unmodified code would not stay
  quiet. Running both is what makes either trustworthy.

---

## 8. Reporting rules

When writing up results (Step 11 report, or a message to the user):

1. Report **only `verified`** as proven. `passed` is "no counterexample found, but not proven" —
   say that, in those words, with the reason from the worker's warnings.
2. Always state the domain: the `uint128` bound, and any harness assumption or modelled contract.
3. Name what was **not** proven, explicitly — the out-of-reach properties and, more importantly,
   the whole stateful surface the proofs do not touch. Verified conversion math says nothing about
   whether an executed swap honours its quote.
4. Report a `failed` result as a finding only after checking the counterexample against the
   harness assumptions (§5). Echidna has already replayed it concretely.
5. Never write "formally verified" about the protocol. The verified unit is a property, in a
   domain, against one build.
