# Fizz Suite

## What Is Here

- `Base.sol`: shared setup, deployed contract references, actors, helpers, and ghost state
- `Snapshots.sol`: before/after state capture used by properties
- `Properties.sol`: global and function-specific invariants
- `handlers/`: protocol actions exposed to the fuzzers
- `harness/`: (optional) harness contracts that inherit from target contracts to expose private/internal state needed by properties
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
