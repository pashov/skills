#!/usr/bin/env node
/**
 * test_generate_handlers.js
 *
 * Comprehensive test suite for generate_handlers.js.
 * Creates temp fixtures, runs the script, and asserts on the output.
 *
 * Usage:  node test_generate_handlers.js
 * Exit:   0 = all passed, 1 = failures
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const os = require('os');

const SCRIPT = path.join(__dirname, 'generate_handlers.js');
let tmpRoot = '';
let passed = 0;
let failed = 0;

// ――――――――――――――――――――――――― Helpers ―――――――――――――――――――――――――

function setup() {
    tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'gen-handlers-test-'));
}

function teardown() {
    fs.rmSync(tmpRoot, { recursive: true, force: true });
}

function makeProject(name) {
    const dir = path.join(tmpRoot, name);
    const metaDir = path.join(dir, 'fizz_data');
    const suiteDir = path.join(dir, 'test', 'fizz', 'handlers');
    fs.mkdirSync(metaDir, { recursive: true });
    fs.mkdirSync(suiteDir, { recursive: true });
    return { dir, metaDir, suiteDir };
}

function writeSelection(metaDir, selection) {
    fs.writeFileSync(path.join(metaDir, 'entry-point-selection.json'), JSON.stringify(selection, null, 2));
}

function writeStubHandler(suiteDir, contractName) {
    const content = `// SPDX-License-Identifier: MIT
pragma solidity >=0.6.2 <0.9.0;

import "../Base.sol";
import {Properties} from "../Properties.sol";

/// @notice Handles the interaction with ${contractName}
abstract contract ${contractName}Handler is Properties {

    // ――――――――――――――――――――――――― Clamped ――――――――――――――――――――――――――

    // ―――――――――――――――――――――――― Unclamped ―――――――――――――――――――――――――
}
`;
    fs.writeFileSync(path.join(suiteDir, `${contractName}Handler.sol`), content);
}

function writeEditedHandler(suiteDir, contractName) {
    const content = `// SPDX-License-Identifier: MIT
pragma solidity >=0.6.2 <0.9.0;

import "../Base.sol";
import {Properties} from "../Properties.sol";

abstract contract ${contractName}Handler is Properties {

    function ${contractName.charAt(0).toLowerCase() + contractName.slice(1)}_customFunc(uint256 x) public asActor {
        // user-written code here
    }
}
`;
    fs.writeFileSync(path.join(suiteDir, `${contractName}Handler.sol`), content);
}

function run(projectDir, extraArgs = '') {
    return execSync(`node "${SCRIPT}" "${projectDir}" ${extraArgs}`, {
        encoding: 'utf8',
        timeout: 10000,
    });
}

function readHandler(suiteDir, contractName) {
    return fs.readFileSync(path.join(suiteDir, `${contractName}Handler.sol`), 'utf8');
}

function assert(condition, message) {
    if (condition) {
        passed++;
        console.log(`  ✓ ${message}`);
    } else {
        failed++;
        console.error(`  ✗ ${message}`);
    }
}

// ――――――――――――――――――――――――― Test fixtures ―――――――――――――――――――――――――

/** A realistic contract selection with varied types */
const VAULT_CONTRACT = {
    name: 'Vault',
    sourcePath: 'src/Vault.sol',
    artifactPath: 'out/Vault.sol/Vault.json',
    constructor: { inputs: [], stateMutability: 'nonpayable' },
    functions: [
        {
            name: 'deposit',
            inputs: [
                { name: 'amount', type: 'uint256', internalType: 'uint256' },
            ],
            stateMutability: 'nonpayable',
        },
        {
            name: 'withdraw',
            inputs: [
                { name: 'shares', type: 'uint256', internalType: 'uint256' },
                { name: 'recipient', type: 'address', internalType: 'address' },
            ],
            stateMutability: 'nonpayable',
        },
        {
            name: 'depositETH',
            inputs: [],
            stateMutability: 'payable',
        },
    ],
    hasReceive: true,
    hasFallback: false,
};

const TOKEN_CONTRACT = {
    name: 'Token',
    sourcePath: 'src/Token.sol',
    artifactPath: 'out/Token.sol/Token.json',
    constructor: { inputs: [], stateMutability: 'nonpayable' },
    functions: [
        {
            name: 'transfer',
            inputs: [
                { name: 'to', type: 'address', internalType: 'address' },
                { name: 'amount', type: 'uint256', internalType: 'uint256' },
            ],
            stateMutability: 'nonpayable',
        },
        {
            name: 'approve',
            inputs: [
                { name: 'spender', type: 'address', internalType: 'address' },
                { name: 'amount', type: 'uint256', internalType: 'uint256' },
            ],
            stateMutability: 'nonpayable',
        },
    ],
    hasReceive: false,
    hasFallback: false,
};

/** Contract with complex types: arrays, bytes, string, enum, contract, tuple */
const COMPLEX_CONTRACT = {
    name: 'Router',
    sourcePath: 'src/Router.sol',
    artifactPath: 'out/Router.sol/Router.json',
    constructor: { inputs: [], stateMutability: 'nonpayable' },
    functions: [
        {
            name: 'swap',
            inputs: [
                { name: 'path', type: 'array', internalType: 'address[]' },
                { name: 'amountIn', type: 'uint256', internalType: 'uint256' },
                { name: 'deadline', type: 'uint256', internalType: 'uint256' },
            ],
            stateMutability: 'nonpayable',
        },
        {
            name: 'execute',
            inputs: [
                { name: 'data', type: 'bytes', internalType: 'bytes' },
                { name: 'label', type: 'string', internalType: 'string' },
            ],
            stateMutability: 'nonpayable',
        },
        {
            name: 'setMode',
            inputs: [
                { name: 'mode', type: 'enum', internalType: 'Router.Mode' },
            ],
            stateMutability: 'nonpayable',
        },
        {
            name: 'setTarget',
            inputs: [
                { name: 'target', type: 'contract', internalType: 'IERC20' },
            ],
            stateMutability: 'nonpayable',
        },
        {
            name: 'batchSwap',
            inputs: [
                { name: 'params', type: 'tuple', internalType: 'Router.SwapParams' },
            ],
            stateMutability: 'nonpayable',
        },
    ],
    hasReceive: false,
    hasFallback: false,
};

/** Contract with unnamed parameters */
const UNNAMED_CONTRACT = {
    name: 'Legacy',
    sourcePath: 'src/Legacy.sol',
    artifactPath: 'out/Legacy.sol/Legacy.json',
    constructor: { inputs: [], stateMutability: 'nonpayable' },
    functions: [
        {
            name: 'doSomething',
            inputs: [
                { name: '', type: 'uint256', internalType: 'uint256' },
                { name: '', type: 'address', internalType: 'address' },
            ],
            stateMutability: 'nonpayable',
        },
    ],
    hasReceive: false,
    hasFallback: false,
};

/** Contract with overloaded functions */
const OVERLOADED_CONTRACT = {
    name: 'Pool',
    sourcePath: 'src/Pool.sol',
    artifactPath: 'out/Pool.sol/Pool.json',
    constructor: { inputs: [], stateMutability: 'nonpayable' },
    functions: [
        {
            name: 'deposit',
            inputs: [
                { name: 'amount', type: 'uint256', internalType: 'uint256' },
            ],
            stateMutability: 'nonpayable',
        },
        {
            name: 'deposit',
            inputs: [
                { name: 'amount', type: 'uint256', internalType: 'uint256' },
                { name: 'recipient', type: 'address', internalType: 'address' },
            ],
            stateMutability: 'nonpayable',
        },
    ],
    hasReceive: false,
    hasFallback: false,
};

/** Contract with smaller uint types */
const SMALLUINT_CONTRACT = {
    name: 'Config',
    sourcePath: 'src/Config.sol',
    artifactPath: 'out/Config.sol/Config.json',
    constructor: { inputs: [], stateMutability: 'nonpayable' },
    functions: [
        {
            name: 'setFee',
            inputs: [
                { name: 'fee', type: 'uint8', internalType: 'uint8' },
            ],
            stateMutability: 'nonpayable',
        },
        {
            name: 'setLimit',
            inputs: [
                { name: 'limit', type: 'uint128', internalType: 'uint128' },
            ],
            stateMutability: 'nonpayable',
        },
        {
            name: 'setHash',
            inputs: [
                { name: 'hash', type: 'bytes32', internalType: 'bytes32' },
            ],
            stateMutability: 'nonpayable',
        },
        {
            name: 'toggle',
            inputs: [
                { name: 'flag', type: 'bool', internalType: 'bool' },
            ],
            stateMutability: 'nonpayable',
        },
    ],
    hasReceive: false,
    hasFallback: false,
};

/** Contract with mixed primary and secondary tiers */
const TIERED_CONTRACT = {
    name: 'Protocol',
    sourcePath: 'src/Protocol.sol',
    artifactPath: 'out/Protocol.sol/Protocol.json',
    constructor: { inputs: [], stateMutability: 'nonpayable' },
    functions: [
        {
            name: 'deposit',
            tier: 'primary',
            inputs: [
                { name: 'amount', type: 'uint256', internalType: 'uint256' },
            ],
            stateMutability: 'nonpayable',
        },
        {
            name: 'setPaused',
            tier: 'secondary',
            inputs: [
                { name: 'paused', type: 'bool', internalType: 'bool' },
            ],
            stateMutability: 'nonpayable',
        },
        {
            name: 'setFee',
            tier: 'secondary',
            inputs: [
                { name: 'fee', type: 'uint256', internalType: 'uint256' },
            ],
            stateMutability: 'nonpayable',
        },
        {
            name: 'setAdmin',
            tier: 'secondary',
            inputs: [
                { name: 'admin', type: 'address', internalType: 'address' },
            ],
            stateMutability: 'nonpayable',
        },
    ],
    hasReceive: false,
    hasFallback: false,
};

// ――――――――――――――――――――――――― Tests ―――――――――――――――――――――――――

function testBasicGeneration() {
    console.log('\n── Test: basic generation (Vault + Token) ──');
    const { dir, metaDir, suiteDir } = makeProject('basic');
    writeSelection(metaDir, [VAULT_CONTRACT, TOKEN_CONTRACT]);
    writeStubHandler(suiteDir, 'Vault');
    writeStubHandler(suiteDir, 'Token');

    const output = run(dir);

    // Vault handler
    const vault = readHandler(suiteDir, 'Vault');
    assert(vault.includes('abstract contract VaultHandler is Properties'), 'Vault: contract declaration');
    assert(vault.includes('function vault_deposit(uint256 amount) public asActor'), 'Vault: unclamped deposit');
    assert(vault.includes('function vault_deposit_clamped(uint256 amount) public'), 'Vault: clamped deposit');
    assert(vault.includes('function vault_withdraw(uint256 shares, address recipient) public asActor'), 'Vault: unclamped withdraw with 2 params');
    assert(vault.includes('function vault_withdraw_clamped(uint256 shares, address recipient) public'), 'Vault: clamped withdraw');
    assert(vault.includes('vault_withdraw(shares, recipient);'), 'Vault: clamped forwards to unclamped');
    assert(vault.includes('function vault_depositETH() public payable asActor'), 'Vault: payable unclamped');
    assert(vault.includes('function vault_depositETH_clamped(uint256 ethAmount) public'), 'Vault: payable clamped gets ethAmount param');
    assert(vault.includes('// TODO: wire call'), 'Vault: has TODO hints');
    assert(vault.includes('vault.deposit(amount)'), 'Vault: call hint for deposit');
    assert(vault.includes('vault.depositETH{value: msg.value}()'), 'Vault: payable call hint');

    // Token handler
    const token = readHandler(suiteDir, 'Token');
    assert(token.includes('abstract contract TokenHandler is Properties'), 'Token: contract declaration');
    assert(token.includes('function token_transfer(address to, uint256 amount) public asActor'), 'Token: unclamped transfer');
    assert(token.includes('function token_approve_clamped(address spender, uint256 amount) public'), 'Token: clamped approve');
    assert(token.includes('token_transfer(to, amount);'), 'Token: clamped forwards args');

    // Script output
    assert(output.includes('[wrote]'), 'Output: shows [wrote] for generated files');
    assert(output.includes('2 handler(s) written'), 'Output: correct count');
}

function testComplexTypes() {
    console.log('\n── Test: complex types (array, bytes, string, enum, contract, tuple) ──');
    const { dir, metaDir, suiteDir } = makeProject('complex');
    writeSelection(metaDir, [COMPLEX_CONTRACT]);

    const output = run(dir);
    const router = readHandler(suiteDir, 'Router');

    // Array type → internalType + memory
    assert(router.includes('address[] memory path'), 'Router: array param has memory');
    // bytes → memory
    assert(router.includes('bytes memory data'), 'Router: bytes param has memory');
    // string → memory
    assert(router.includes('string memory label'), 'Router: string param has memory');
    // enum → uint8
    assert(router.includes('uint8 mode'), 'Router: enum maps to uint8');
    // contract → address
    assert(router.includes('address target'), 'Router: contract maps to address');
    // tuple → internalType + memory
    assert(router.includes('Router.SwapParams memory params'), 'Router: tuple uses internalType with memory');

    // Clamping hints
    assert(router.includes('clampBetween(amountIn'), 'Router: uint256 clamping hint');
}

function testUnnamedParams() {
    console.log('\n── Test: unnamed parameters ──');
    const { dir, metaDir, suiteDir } = makeProject('unnamed');
    writeSelection(metaDir, [UNNAMED_CONTRACT]);

    run(dir);
    const legacy = readHandler(suiteDir, 'Legacy');

    assert(legacy.includes('uint256 _arg0'), 'Legacy: first unnamed param gets _arg0');
    assert(legacy.includes('address _arg1'), 'Legacy: second unnamed param gets _arg1');
    assert(legacy.includes('legacy_doSomething(_arg0, _arg1)'), 'Legacy: forwards with generated names');
}

function testOverloadedFunctions() {
    console.log('\n── Test: overloaded functions ──');
    const { dir, metaDir, suiteDir } = makeProject('overloaded');
    writeSelection(metaDir, [OVERLOADED_CONTRACT]);

    run(dir);
    const pool = readHandler(suiteDir, 'Pool');

    // Both overloads should be present (Solidity handles this)
    assert(pool.includes('function pool_deposit(uint256 amount) public asActor'), 'Pool: first deposit overload');
    assert(pool.includes('function pool_deposit(uint256 amount, address recipient) public asActor'), 'Pool: second deposit overload');
    assert(pool.includes('function pool_deposit_clamped(uint256 amount) public'), 'Pool: first clamped overload');
    assert(pool.includes('function pool_deposit_clamped(uint256 amount, address recipient) public'), 'Pool: second clamped overload');
}

function testSkipsEditedHandlers() {
    console.log('\n── Test: skips handlers with user edits ──');
    const { dir, metaDir, suiteDir } = makeProject('skip-edited');
    writeSelection(metaDir, [VAULT_CONTRACT]);
    writeEditedHandler(suiteDir, 'Vault');

    const output = run(dir);
    const vault = readHandler(suiteDir, 'Vault');

    assert(vault.includes('customFunc'), 'Skip: original user code preserved');
    assert(!vault.includes('vault_deposit'), 'Skip: generated code NOT present');
    assert(output.includes('[skip]'), 'Skip: output shows [skip]');
    assert(output.includes('0 handler(s) written'), 'Skip: 0 written');
}

function testForceOverwrite() {
    console.log('\n── Test: --force overwrites edited handlers ──');
    const { dir, metaDir, suiteDir } = makeProject('force');
    writeSelection(metaDir, [VAULT_CONTRACT]);
    writeEditedHandler(suiteDir, 'Vault');

    const output = run(dir, '--force');
    const vault = readHandler(suiteDir, 'Vault');

    assert(!vault.includes('customFunc'), 'Force: user code replaced');
    assert(vault.includes('vault_deposit'), 'Force: generated code present');
    assert(output.includes('[wrote]'), 'Force: output shows [wrote]');
}

function testOverwritesStubs() {
    console.log('\n── Test: overwrites empty stubs without --force ──');
    const { dir, metaDir, suiteDir } = makeProject('stubs');
    writeSelection(metaDir, [TOKEN_CONTRACT]);
    writeStubHandler(suiteDir, 'Token');

    run(dir);
    const token = readHandler(suiteDir, 'Token');

    assert(token.includes('function token_transfer'), 'Stubs: stub replaced with populated handler');
}

function testCreatesHandlerDirIfMissing() {
    console.log('\n── Test: creates handler dir if missing ──');
    const dir = path.join(tmpRoot, 'no-dir');
    const metaDir = path.join(dir, 'fizz_data');
    fs.mkdirSync(metaDir, { recursive: true });
    writeSelection(metaDir, [TOKEN_CONTRACT]);

    run(dir);
    const handlerPath = path.join(dir, 'test', 'fizz', 'handlers', 'TokenHandler.sol');
    assert(fs.existsSync(handlerPath), 'No-dir: handler file created');
}

function testMissingSelectionFile() {
    console.log('\n── Test: exits with error when selection file missing ──');
    const dir = path.join(tmpRoot, 'no-selection');
    fs.mkdirSync(dir, { recursive: true });

    let exitCode = 0;
    try {
        run(dir);
    } catch (e) {
        exitCode = e.status;
    }
    assert(exitCode !== 0, 'Missing selection: exits with non-zero');
}

function testEmptySelection() {
    console.log('\n── Test: exits with error on empty selection ──');
    const { dir, metaDir } = makeProject('empty');
    writeSelection(metaDir, []);

    let exitCode = 0;
    try {
        run(dir);
    } catch (e) {
        exitCode = e.status;
    }
    assert(exitCode !== 0, 'Empty selection: exits with non-zero');
}

function testContractWithNoFunctions() {
    console.log('\n── Test: skips contract with empty functions array ──');
    const { dir, metaDir, suiteDir } = makeProject('no-funcs');
    const emptyContract = {
        name: 'Empty',
        sourcePath: 'src/Empty.sol',
        functions: [],
        hasReceive: true,
    };
    writeSelection(metaDir, [emptyContract, TOKEN_CONTRACT]);

    run(dir);
    const emptyPath = path.join(suiteDir, 'EmptyHandler.sol');
    assert(!fs.existsSync(emptyPath), 'No-funcs: EmptyHandler.sol not created');
    assert(fs.existsSync(path.join(suiteDir, 'TokenHandler.sol')), 'No-funcs: TokenHandler.sol created');
}

function testSmallUintAndValueTypes() {
    console.log('\n── Test: small uint, bytes32, bool types ──');
    const { dir, metaDir, suiteDir } = makeProject('smalluint');
    writeSelection(metaDir, [SMALLUINT_CONTRACT]);

    run(dir);
    const config = readHandler(suiteDir, 'Config');

    assert(config.includes('uint8 fee'), 'Config: uint8 param');
    assert(config.includes('uint128 limit'), 'Config: uint128 param');
    assert(config.includes('bytes32 hash'), 'Config: bytes32 param (no memory)');
    assert(config.includes('bool flag'), 'Config: bool param');
    assert(!config.includes('bytes32 memory'), 'Config: bytes32 does NOT get memory');
    assert(config.includes('clampBetween(fee'), 'Config: uint8 gets clamping hint');
    assert(config.includes('clampBetween(limit'), 'Config: uint128 gets clamping hint');
}

function testClampingHints() {
    console.log('\n── Test: clamping hints per type ──');
    const { dir, metaDir, suiteDir } = makeProject('hints');
    writeSelection(metaDir, [VAULT_CONTRACT]);

    run(dir);
    const vault = readHandler(suiteDir, 'Vault');

    // uint256 should get clampBetween hint
    assert(vault.includes('clampBetween(amount'), 'Hints: uint256 gets clampBetween');
    // address should get toActor hint
    assert(vault.includes('toActor(recipient)'), 'Hints: address gets toActor');
}

function testSolidityStructure() {
    console.log('\n── Test: Solidity structure validity ──');
    const { dir, metaDir, suiteDir } = makeProject('structure');
    writeSelection(metaDir, [VAULT_CONTRACT]);

    run(dir);
    const vault = readHandler(suiteDir, 'Vault');

    // Check structural elements
    assert(vault.includes('// SPDX-License-Identifier: MIT'), 'Structure: SPDX header');
    assert(vault.includes('pragma solidity >=0.6.2 <0.9.0;'), 'Structure: pragma');
    assert(vault.includes('import "../Base.sol";'), 'Structure: Base import');
    assert(vault.includes('import {Properties} from "../Properties.sol";'), 'Structure: Properties import');
    assert(vault.includes('// ――――――――――――――――――――――――― Clamped ――――――――――――――――――――――――――'), 'Structure: Clamped section');
    assert(vault.includes('// ―――――――――――――――――――――――― Unclamped ―――――――――――――――――――――――――'), 'Structure: Unclamped section');

    // Clamped section comes BEFORE unclamped (matching handler-patterns.md example)
    const clampedPos = vault.indexOf('Clamped');
    const unclampedPos = vault.indexOf('Unclamped');
    assert(clampedPos < unclampedPos, 'Structure: Clamped before Unclamped');

    // Contract closes properly
    const lines = vault.trimEnd().split('\n');
    assert(lines[lines.length - 1].trim() === '}', 'Structure: file ends with closing brace');
}

function testSecondaryTierDispatcher() {
    console.log('\n── Test: secondary tier dispatcher ──');
    const { dir, metaDir, suiteDir } = makeProject('tiered');
    writeSelection(metaDir, [TIERED_CONTRACT]);

    run(dir);
    const protocol = readHandler(suiteDir, 'Protocol');

    // Primary function gets individual clamped + unclamped
    assert(protocol.includes('function protocol_deposit(uint256 amount) public asActor'), 'Tiered: primary gets unclamped');
    assert(protocol.includes('function protocol_deposit_clamped(uint256 amount) public'), 'Tiered: primary gets clamped');

    // Secondary functions get individual internal unclamped stubs (prefixed with _)
    assert(protocol.includes('function _protocol_setPaused(bool paused) internal'), 'Tiered: secondary setPaused is internal with _ prefix');
    assert(protocol.includes('function _protocol_setFee(uint256 fee) internal'), 'Tiered: secondary setFee is internal with _ prefix');
    assert(protocol.includes('function _protocol_setAdmin(address admin) internal'), 'Tiered: secondary setAdmin is internal with _ prefix');

    // Secondary stubs are NOT public/asActor
    assert(!protocol.includes('function _protocol_setPaused(bool paused) public'), 'Tiered: secondary stub not public');

    // Secondary functions do NOT get clamped counterparts
    assert(!protocol.includes('protocol_setPaused_clamped'), 'Tiered: secondary has no clamped');
    assert(!protocol.includes('protocol_setFee_clamped'), 'Tiered: secondary has no clamped');
    assert(!protocol.includes('protocol_setAdmin_clamped'), 'Tiered: secondary has no clamped');

    // Dispatcher exists with correct signature (max 1 arg per position: uint256 for fee, address for admin)
    assert(protocol.includes('function protocol_secondary(uint8 selector, uint256 arg0, address arg1) public'), 'Tiered: dispatcher signature');

    // Dispatcher modulo
    assert(protocol.includes('selector = uint8(selector % 3)'), 'Tiered: dispatcher modulo = n secondary funcs');

    // Dispatcher branches call the _ prefixed internal functions
    assert(protocol.includes('if (selector == 0) _protocol_setPaused(arg0 > 0)'), 'Tiered: bool branch calls _ internal, converts uint256');
    assert(protocol.includes('else if (selector == 1) _protocol_setFee(arg0)'), 'Tiered: uint256 branch calls _ internal');
    assert(protocol.includes('else _protocol_setAdmin(arg1)'), 'Tiered: address branch calls _ internal');

    // Dispatcher is in clamped section (before unclamped section)
    const dispatcherPos = protocol.indexOf('function protocol_secondary');
    const unclampedPos = protocol.indexOf('Unclamped');
    assert(dispatcherPos < unclampedPos, 'Tiered: dispatcher is in clamped section');

    // Dispatcher is after the primary clamped functions
    const depositClampedPos = protocol.indexOf('function protocol_deposit_clamped');
    assert(dispatcherPos > depositClampedPos, 'Tiered: dispatcher is after primary clamped functions');

    // Secondary internal stubs are in unclamped section
    const setAdminPos = protocol.indexOf('function _protocol_setAdmin');
    assert(setAdminPos > unclampedPos, 'Tiered: secondary internal stubs are in unclamped section');
}

// ――――――――――――――――――――――――― Runner ―――――――――――――――――――――――――

function main() {
    setup();

    try {
        testBasicGeneration();
        testComplexTypes();
        testUnnamedParams();
        testOverloadedFunctions();
        testSkipsEditedHandlers();
        testForceOverwrite();
        testOverwritesStubs();
        testCreatesHandlerDirIfMissing();
        testMissingSelectionFile();
        testEmptySelection();
        testContractWithNoFunctions();
        testSmallUintAndValueTypes();
        testClampingHints();
        testSolidityStructure();
        testSecondaryTierDispatcher();
    } finally {
        teardown();
    }

    console.log(`\n${'═'.repeat(50)}`);
    console.log(`  ${passed} passed, ${failed} failed`);
    console.log('═'.repeat(50));
    process.exit(failed > 0 ? 1 : 0);
}

main();
