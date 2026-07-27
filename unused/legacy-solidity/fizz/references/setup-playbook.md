# Setup Playbook

Use this guide during Step 6 when wiring `Base.sol` and `Actor.sol`.

## Base.sol FIXMEs

The scaffolded `Base.sol` contract contains `FIXME` comments that indicate where protocol-specific setup logic should be implemented.

Treat those `FIXME`s as required integration points.

## Source Priority

Look for existing project setup logic before inventing new deployment code.

Read in this order when available:

1. integration tests
2. base test fixtures
3. deployment scripts
4. helper contracts used by tests

If none of the above exist, scan for initialize() signatures and constructor arguments directly in source files.

## Extract From Existing Setup

- deployment order
- constructor argument meaning
- role grants and ownership transfers
- initialization or upgrade calls
- seed state such as approvals, liquidity, balances, oracle values, and reward funding

## Good Defaults

- reuse real in-protocol dependencies when the protocol already contains them
- use mocks only for genuinely external systems or missing infrastructure
- use mock contracts when appropriate for dependencies that are external to the protocol or unnecessarily complex for the harness
- good mock candidates include external tokens, external oracles, and complex third-party contracts that are not the main subject of the fuzz campaign
- when the missing dependency is a simple external ERC20 token, prefer the scaffolded `utils/MockERC20.sol` helper unless the project already contains a more faithful token mock
- grant actors enough balances and approvals to reach meaningful state transitions
- prefer deterministic constants over random setup branches

## Upgradeable Contracts

Before writing setup logic, check whether the target contracts use upgradeable proxies.

Strong signals:

- `_disableInitializers()` in a constructor
- an `initialize()` function protected by `initializer`
- versioned initialization functions protected by `reinitializer`

If the contract is upgradeable:

- use the project's proxy pattern such as `TransparentUpgradeableProxy` or `ERC1967Proxy`
- deploy the implementation first, then the proxy with initialization calldata
- use a dedicated proxy admin address that never calls implementation functions directly

If the contract is not upgradeable, plain `new Contract(args)` deployment is fine.

## Setup Checklist

At minimum, wire:

- deployment order
- constructor arguments
- proxy deployment and initialization when needed
- registry or service-locator wiring
- role grants and ownership transfers, including scoped roles when applicable
- token approvals and seed balances
- any required initialization calls
- market, pool, or strategy configuration needed for handlers to reach meaningful states

Deploy all in-protocol dependencies needed by the selected entry points, even if those dependencies do not get handlers.

## Signature-Dependent Setup

If selected entry points require cryptographic signatures such as signed prices, signed orders, or permit signatures:

- store a known private key constant in `Base.sol` for the signer or publisher role
- register the corresponding address as an approved signer during setup
- expect handlers in Step 7 to use `vm.sign(privateKey, digest)` to construct valid payloads
- if router-layer signature construction is too complex for the harness, consider targeting the underlying manager functions directly and document that tradeoff

## TODO Rule

Leave `// TODO` only when:

- the dependency is truly external and the correct mock or fork source is project-specific
- the constructor needs a business value that cannot be inferred safely
- the protocol needs a privileged operational decision that should come from the user

Every TODO should say what is missing and why it blocks a safe default.
