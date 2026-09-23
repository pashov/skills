# Fizz Suite

## What Is Here

- `Base.sol`: shared setup, deployed contract references, actors, helpers, and ghost state
- `Snapshots.sol`: before/after state capture used by properties
- `Properties.sol`: global and function-specific invariants
- `handlers/`: protocol actions exposed to the fuzzers
- `harness/`: (optional) harness contracts that inherit from target contracts to expose private/internal state needed by properties
- `symbolic/`: (optional, usually absent) `prove_*` properties run through Echidna's verification mode instead of fuzzed — see below
- `utils/`: shared helper libraries, assertions, clamping logic, math helpers, deploy helpers, logging, and mocks
- `FuzzTester.sol`: main Echidna/Medusa fuzzing entry point
- `FoundryTester.sol`: Foundry harness for quick debugging and local repros

## Inheritance Chain

```
Base (is StringUtils, Clamp, Deployer, Math)
        └─► Snapshots (is Base)
              └─► Properties (is PropertiesAsserts, Snapshots)
                    └─► <Contract>Handler (is Properties)   — one per target contract
                          └─► Handlers (is <all handlers>)  — aggregator + actor switching
                                ├─► FuzzTester (is Handlers)       — Echidna/Medusa entry point
                                └─► FoundryTester (is Test, Handlers) — Foundry quick debug/PoC entry point
```

## Related Paths Outside This Directory

- `../../fizz_data/`: extracted ABI inventory, entry-point selection, protocol-understanding notes, corpora, logs, and coverage outputs
- `../../echidna.yaml`: Echidna config
- `../../medusa.json`: Medusa config

## How To Run

From the project root:

```bash
forge build
forge test --match-contract FoundryTester
echidna . --contract FuzzTester --config echidna.yaml
medusa fuzz --config medusa.json
```

If `symbolic/` exists, those properties are *proved* rather than fuzzed (Echidna >= 2.4 and
`bitwuzla` required). They run one contract at a time and are unrelated to the campaign above:

```bash
echidna test/fizz/symbolic/ProveMath.t.sol --contract ProveMath \
        --config test/fizz/symbolic/echidna-verify.yaml --format text
```

Echidna exits non-zero under `workers: 0` — that is not a failure; read the per-method result
lines. Only `verified` means proven: `passed` means no counterexample was found but some solver
queries returned unknown. Every result is bounded by the harness assumptions (typically
`uint128` inputs) and covers a single transaction, so multi-transaction behaviour is covered only
by the fuzz campaign.

## How To Read The Suite

Recommended order:

1. `README.md`
2. `Base.sol`
3. `handlers/Handlers.sol`
4. individual handler files under `handlers/`
5. `Snapshots.sol`
6. `Properties.sol`
7. `harness/` (if present) — to understand what private/internal state is exposed and why
8. `utils/` when you need to understand helper behavior or mocks
9. `FuzzTester.sol`
10. `FoundryTester.sol`
