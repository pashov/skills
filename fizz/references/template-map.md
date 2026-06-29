# Template Map

Maps each generated file to its role in the inheritance chain and generation phase.

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

## File Descriptions

### Core files (scaffolded, then refined)

| File | Phase | Role |
|---|---|---|
| `Actor.sol` | Step 5 + Step 6 | Actor contract representing a user. Holds ETH, has `forceSendETH`, ERC-721/1155 receivers, flash loan callback. Copied in Step 5 and then modified with protocol-specific approvals and setup needs. |
| `Base.sol` | Step 5 + Step 6 + Step 9 | Constants, state variables, ghost struct, actor management, contract instances. Copied in Step 5, wired in Step 6, and extended in Step 9. |
| `README.md` | Step 5 | Reader-facing overview of the generated suite, its key files, and the standard commands to run it. Intended for users or agents who did not build the harness originally. |
| `Snapshots.sol` | Step 5 + Step 6 + Step 9 | Before/after state tracking. Copied in Step 5, kept minimal in Step 6, and populated during invariant generation. |
| `Properties.sol` | Step 5 + Step 6 + Step 9 | Property container. Copied in Step 5, kept minimal in Step 6, and populated with checks in Step 9. |
| `handlers/Handlers.sol` | Step 5 + Step 6 + Step 7 | Aggregator copied in Step 5, then populated from the selected contracts so it imports and inherits all generated handler stubs. It can be adjusted in Step 6 if needed and refined again in Step 7. |
| `handlers/<Contract>Handler.sol` | Step 5 + Step 7 | Per-contract handler file in `{SUITE_DIR}`. Stub handler templates are generated in Step 5 from `fizz_data/entry-point-selection.json`, then replaced or rewritten in Step 7. |
| `harness/<Contract>Harness.sol` | Step 9 (conditional) | Harness contract that inherits from a target contract and exposes private/internal state needed by a property. Created only when strictly necessary. When present, `Base.sol` instantiates the harness instead of the target contract. |
| `FuzzTester.sol` | Step 5 | Echidna/Medusa entry point. Copied in Step 5 and never modified. Inherits everything through `Handlers`. |
| `FoundryTester.sol` | Step 5 | Foundry quick debug and PoC harness. Copied in Step 5 and never modified structurally, but used actively during Step 8 and Step 10 to debug coverage gaps and validate hypotheses. Inherits everything through `Handlers`. |

### Workflow metadata (generated during the workflow)

| File | Phase | Role |
|---|---|---|
| `fizz_data/contracts.json` | Step 2 | Extracted contract/function inventory used as the structural input for selection and later analysis. |
| `fizz_data/entry-point-selection.json` | Step 4 | Auto-accepted selection of contracts and functions that limits handler generation only. |
| `fizz_data/protocol-understanding.md` | Step 3 fallback | Persisted protocol understanding notes when `x-ray` is unavailable or insufficient. |

### Utility files (static, not edited)

| File | Role |
|---|---|
| `utils/Clamp.sol` | Clamping functions: `clampBetween`, `clampLt`, `clampLte`, `clampGt`, `clampGte` (uint256 + int256). |
| `utils/Hevm.sol` | Cheatcode interface (`vm.prank`, `vm.roll`, `vm.warp`, `vm.label`, etc.). |
| `utils/PropertiesAsserts.sol` | Assertion helpers for properties: `t()`, `eq()`, `neq()`, `gt()`, `gte()`, `lt()`, `lte()`. |
| `utils/Logger.sol` | Event-based logging for fuzzer trace output. |
| `utils/Math.sol` | Math helpers (`abs`, etc.). |
| `utils/StringUtils.sol` | Number-to-string conversion for log messages. |
| `utils/Deployer.sol` | Deployment helpers. |
| `utils/DecimalPrinter.sol` | Decimal formatting for uint values. |
| `utils/EnumerableSet.sol` | OpenZeppelin-style enumerable set for tracking addresses/uints. |
| `utils/MockERC20.sol` | Simple mintable ERC20 mock for external token dependencies, seeded balances, and token-donation edge cases in the generated harness. |

### Config files (project root)

| File | Role |
|---|---|
| `echidna.yaml` | Echidna fuzzer configuration. Points to `FuzzTester` as test target. |
| `medusa.json` | Medusa fuzzer configuration. Points to `FuzzTester` as test target. |

## Output Structure

```
fizz_data/
├── contracts.json               # Extracted contract/function inventory
├── entry-point-selection.json   # Auto-accepted handler-generation scope
├── protocol-understanding.md    # Fallback understanding notes when needed
├── corpus_echidna/
├── corpus_medusa/
├── crytic-export/
├── logs_medusa/
└── ...

./
├── echidna.yaml
├── medusa.json
└── ...

test/fizz/
├── README.md            # Human/agent-oriented suite overview and runbook
├── Actor.sol
├── Base.sol             # Contract declarations, setup, ghosts, helpers
├── Properties.sol       # Invariant checks
├── Snapshots.sol        # Before/after state tracking
├── FuzzTester.sol       # Echidna/Medusa entry point
├── FoundryTester.sol    # Foundry quick debug/PoC harness
├── handlers/
│   ├── Handlers.sol     # Aggregator — inherits all per-contract handlers
│   ├── VaultHandler.sol # Example: handlers for Vault contract
│   └── TokenHandler.sol # Example: handlers for Token contract
├── harness/             # Optional — only created when properties need private/internal access
│   └── VaultHarness.sol # Example: exposes internal state from Vault
└── utils/
    ├── Clamp.sol        # Clamping helpers (clampBetween, clampLt, etc.)
    ├── DecimalPrinter.sol
    ├── Deployer.sol
    ├── EnumerableSet.sol
    ├── Hevm.sol         # Cheatcode interface
    ├── Logger.sol
    ├── Math.sol
    ├── MockERC20.sol    # Mintable ERC20 mock for external token dependencies
    ├── PropertiesAsserts.sol
    └── StringUtils.sol
```

## Generation Phases Summary

1. **Template copy** — The full template scaffold and fuzzer config are copied into place.
2. **Core refinement** — `Base.sol`, `Actor.sol`, `Snapshots.sol`, `Properties.sol`, and `Handlers.sol` are modified to match the target protocol. `FuzzTester.sol` is the static fuzzer entry point — copied once and never modified. `FoundryTester.sol` is the debugging harness — also never modified structurally, but used actively in Steps 8 and 10.
3. **Handler gen** — Selected-contract handler stubs are replaced with protocol-specific handlers, and `Handlers.sol` is refined with the final imports and inheritance.
4. **Invariant gen** — `Properties.sol` gets invariant checks, `Snapshots.sol` gets tracked state, `Base.sol` gets ghosts, and handler files get ghost and snapshot wiring.
