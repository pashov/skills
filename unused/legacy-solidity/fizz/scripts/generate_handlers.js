#!/usr/bin/env node
/**
 * generate_handlers.js
 *
 * Reads entry-point-selection.json and generates handler files with
 * pre-populated function signatures (clamped + unclamped) for each
 * selected contract.  Replaces the empty stubs that generate_suite.js
 * creates so the LLM only needs to fill in body logic — not discover
 * signatures, types, or naming conventions.
 *
 * Usage:
 *   node generate_handlers.js <PROJECT_ROOT> [options]
 *
 * Options:
 *   --suite-dir  <dir>   Suite directory           (default: test/fizz)
 *   --meta-dir   <dir>   Metadata directory         (default: fizz_data)
 *   --selection  <path>  Entry-point selection file
 *   --force              Overwrite handlers that already contain user edits
 */

const fs = require('fs');
const path = require('path');

// ――――――――――――――――――――――――― Argument parsing ―――――――――――――――――――――――――

const args = process.argv.slice(2);
if (args.length === 0 || args[0] === '--help') {
    console.log(
        'Usage: node generate_handlers.js <PROJECT_ROOT> ' +
        '[--suite-dir <dir>] [--meta-dir <dir>] [--selection <path>] [--force]'
    );
    process.exit(0);
}

const projectRoot = path.resolve(args[0]);
let suiteRelDir = path.join('test', 'fizz');
let metaRelDir = 'fizz_data';
let selectionPath = '';
let force = false;

for (let i = 1; i < args.length; i++) {
    if (args[i] === '--suite-dir' && args[i + 1]) { suiteRelDir = args[++i]; }
    else if (args[i] === '--meta-dir' && args[i + 1]) { metaRelDir = args[++i]; }
    else if (args[i] === '--selection' && args[i + 1]) { selectionPath = path.resolve(args[++i]); }
    else if (args[i] === '--force') { force = true; }
}

const suiteDir = path.join(projectRoot, suiteRelDir);
const metaDir = path.join(projectRoot, metaRelDir);
if (!selectionPath) {
    selectionPath = path.join(metaDir, 'entry-point-selection.json');
}

// ――――――――――――――――――――――――― Type mapping ―――――――――――――――――――――――――

/**
 * Reference-type keywords that require a `memory` data-location qualifier
 * when used as function parameters in Solidity ≥0.5.
 */
const MEMORY_TYPES = new Set(['bytes', 'string']);

/**
 * Convert a contracts.json input descriptor to a Solidity parameter string.
 *
 * contracts.json stores:
 *   type         – simplified ABI type ('array', 'contract', 'enum', or the raw type)
 *   internalType – Solidity-level type without 'struct '/'contract '/'enum ' prefix
 *   name         – parameter name (may be empty)
 */
function toSolidityParam(input, index) {
    const name = input.name || `_arg${index}`;
    const { type, internalType } = input;

    // Contracts are address at the ABI level
    if (type === 'contract') return `address ${name}`;

    // Enums encode as uint8 at the ABI level
    if (type === 'enum') return `uint8 ${name}`;

    // Arrays — internalType has the real Solidity type (e.g. "uint256[]")
    if (type === 'array') return `${internalType} memory ${name}`;

    // Tuples (structs) — internalType has the struct path (e.g. "MyLib.MyStruct")
    if (type === 'tuple') return `${internalType} memory ${name}`;

    // Reference types that need 'memory'
    if (MEMORY_TYPES.has(type)) return `${type} memory ${name}`;

    // Value types — pass through (uint256, int128, address, bool, bytes32, …)
    return `${type} ${name}`;
}

/**
 * Return just the name portion of a parameter for use in call arguments.
 */
function paramName(input, index) {
    return input.name || `_arg${index}`;
}

// ――――――――――――――――――――――――― Helper utilities ―――――――――――――――――――――――――

/** Lowercase the first character of a string. */
function lcFirst(s) {
    if (!s) return s;
    return s.charAt(0).toLowerCase() + s.slice(1);
}

// ――――――――――――――――――――――――― Stub detection ―――――――――――――――――――――――――

/**
 * Return true if the file looks like an unmodified stub from generate_suite.js:
 * it has no function definitions between the Clamped / Unclamped markers.
 */
function isStubHandler(filePath) {
    if (!fs.existsSync(filePath)) return true; // treat missing as writable
    const content = fs.readFileSync(filePath, 'utf8');
    // Strip single-line comments to avoid matching "function" inside comments
    const stripped = content.replace(/\/\/.*$/gm, '');
    // If there are no `function ` keywords the file is still a bare stub
    return !/\bfunction\s+\w+/.test(stripped);
}

// ――――――――――――――――――――――――― Handler generation ―――――――――――――――――――――――――

/**
 * Build a complete handler Solidity file for a single contract from the
 * entry-point-selection data.
 */
const ADDRESS_TYPES = new Set(['address', 'contract']);

/**
 * Build the dispatcher parameter list and a per-function arg-mapping for secondary functions.
 *
 * Strategy: numeric/bool/enum/other value types share a pool of uint256 slots; address/contract
 * types share a separate pool of address slots. For each function the max pool usage across all
 * secondary functions determines the total slot count. Slots are ordered: uint256 slots first,
 * then address slots (matching the handler-patterns.md example).
 *
 * Returns:
 *   { paramStr, slotCount, funcArgExprs }
 *   - paramStr    — Solidity parameter string for the dispatcher (after `uint8 selector, `)
 *   - slotCount   — total number of generic args (uint256 + address)
 *   - funcArgExprs(func) — function that returns the call-argument expression array for a given func
 */
function buildDispatcherSignature(secondaryFuncs) {
    let maxUint256 = 0;
    let maxAddress = 0;

    // Count max slots of each kind needed by any single secondary function
    for (const func of secondaryFuncs) {
        let u = 0, a = 0;
        for (const inp of func.inputs) {
            if (ADDRESS_TYPES.has(inp.type)) a++;
            else u++;
        }
        if (u > maxUint256) maxUint256 = u;
        if (a > maxAddress) maxAddress = a;
    }

    // Build param list: arg0..argN-1 are uint256, argN..argM are address
    const params = [];
    for (let i = 0; i < maxUint256; i++) params.push(`uint256 arg${i}`);
    for (let i = 0; i < maxAddress; i++) params.push(`address arg${maxUint256 + i}`);
    const paramStr = params.join(', ');

    function funcArgExprs(func) {
        let uIdx = 0, aIdx = 0;
        return func.inputs.map(inp => {
            if (ADDRESS_TYPES.has(inp.type)) {
                return `arg${maxUint256 + aIdx++}`;
            }
            const slot = `arg${uIdx++}`;
            if (inp.type === 'bool') return `${slot} > 0`;
            if (inp.type === 'enum') return `uint8(${slot})`;
            if (/^uint\d+$/.test(inp.type) && inp.type !== 'uint256') return `${inp.type}(${slot})`;
            return slot;
        });
    }

    return { paramStr, funcArgExprs };
}

function buildHandler(contract) {
    const contractName = contract.name;
    const instanceName = lcFirst(contractName);
    const functions = contract.functions || [];

    const primaryFuncs = functions.filter(f => f.tier !== 'secondary');
    const secondaryFuncs = functions.filter(f => f.tier === 'secondary');

    const clampedLines = [];
    const unclampedLines = [];

    for (const func of primaryFuncs) {
        const prefix = `${instanceName}_${func.name}`;
        const isPayable = func.stateMutability === 'payable';

        // --- Build parameter strings ---
        const paramDecls = func.inputs.map((inp, i) => toSolidityParam(inp, i));
        const paramNames = func.inputs.map((inp, i) => paramName(inp, i));
        const paramStr = paramDecls.join(', ');
        const argStr = paramNames.join(', ');

        // --- Unclamped function ---
        const payableKw = isPayable ? ' payable' : '';
        const callValue = isPayable ? `{value: msg.value}` : '';
        const callHint = `${instanceName}.${func.name}${callValue}(${argStr})`;

        unclampedLines.push(
            `    function ${prefix}(${paramStr}) public${payableKw} asActor {`,
            `        // TODO: wire call — ${callHint};`,
            `    }`,
            '',
        );

        // --- Clamped function ---
        const clampedParamStr = isPayable && func.inputs.length === 0
            ? 'uint256 ethAmount'
            : paramStr;

        const forwardArgs = isPayable && func.inputs.length === 0
            ? ''
            : argStr;

        clampedLines.push(
            `    function ${prefix}_clamped(${clampedParamStr}) public {`,
        );

        // Add per-type clamping hints
        for (const inp of func.inputs) {
            const name = inp.name || `_arg${func.inputs.indexOf(inp)}`;
            if (inp.type === 'uint256' || inp.type === 'uint128' || inp.type === 'uint64' || inp.type === 'uint32' || inp.type === 'uint8') {
                clampedLines.push(`        // TODO: clamp ${name} — e.g. ${name} = clampBetween(${name}, min, max);`);
            } else if (inp.type === 'address') {
                clampedLines.push(`        // TODO: clamp ${name} — e.g. ${name} = toActor(${name});`);
            }
        }

        if (isPayable && func.inputs.length === 0) {
            clampedLines.push(
                `        // TODO: clamp ethAmount and forward with value`,
                `        ${prefix}();`,
            );
        } else {
            clampedLines.push(
                `        ${prefix}(${forwardArgs});`,
            );
        }

        clampedLines.push(`    }`, '');
    }

    // --- Secondary functions: individual unclamped stubs + dispatcher ---
    if (secondaryFuncs.length > 0) {
        const { paramStr: dispParamStr, funcArgExprs } = buildDispatcherSignature(secondaryFuncs);

        // Individual unclamped stubs for secondary functions (internal, prefixed with _)
        for (const func of secondaryFuncs) {
            const prefix = `_${instanceName}_${func.name}`;
            const isPayable = func.stateMutability === 'payable';
            const paramDecls = func.inputs.map((inp, i) => toSolidityParam(inp, i));
            const paramNames = func.inputs.map((inp, i) => paramName(inp, i));
            const funcParamStr = paramDecls.join(', ');
            const argStr = paramNames.join(', ');
            const payableKw = isPayable ? ' payable' : '';
            const callValue = isPayable ? `{value: msg.value}` : '';
            const callHint = `${instanceName}.${func.name}${callValue}(${argStr})`;

            unclampedLines.push(
                `    function ${prefix}(${funcParamStr}) internal${payableKw} {`,
                `        // TODO: wire call — ${callHint};`,
                `    }`,
                '',
            );
        }

        // Dispatcher function — last in the clamped section
        const dispatcherFullParams = dispParamStr ? `uint8 selector, ${dispParamStr}` : `uint8 selector`;
        const n = secondaryFuncs.length;

        clampedLines.push(
            `    function ${instanceName}_secondary(${dispatcherFullParams}) public {`,
            `        selector = uint8(selector % ${n});`,
        );

        secondaryFuncs.forEach((func, idx) => {
            const prefix = `_${instanceName}_${func.name}`;
            const args = funcArgExprs(func);
            const callExpr = `${prefix}(${args.join(', ')})`;
            if (idx === 0) {
                clampedLines.push(`        if (selector == 0) ${callExpr};`);
            } else if (idx === n - 1) {
                clampedLines.push(`        else ${callExpr};`);
            } else {
                clampedLines.push(`        else if (selector == ${idx}) ${callExpr};`);
            }
        });

        clampedLines.push(`    }`, '');
    }

    // Remove trailing blank line from each section
    if (clampedLines.length && clampedLines[clampedLines.length - 1] === '') clampedLines.pop();
    if (unclampedLines.length && unclampedLines[unclampedLines.length - 1] === '') unclampedLines.pop();

    return `// SPDX-License-Identifier: MIT
pragma solidity >=0.6.2 <0.9.0;

import "../Base.sol";
import {Properties} from "../Properties.sol";

/// @notice Handles the interaction with ${contractName}
abstract contract ${contractName}Handler is Properties {

    // ――――――――――――――――――――――――― Clamped ――――――――――――――――――――――――――

${clampedLines.join('\n')}

    // ―――――――――――――――――――――――― Unclamped ―――――――――――――――――――――――――

${unclampedLines.join('\n')}
}
`;
}

// ――――――――――――――――――――――――――――― Main ――――――――――――――――――――――――――――――

function main() {
    if (!fs.existsSync(selectionPath)) {
        console.error(`Selection file not found: ${selectionPath}`);
        console.error('Run select_functions.js first.');
        process.exit(1);
    }

    const selection = JSON.parse(fs.readFileSync(selectionPath, 'utf8'));
    if (!Array.isArray(selection) || selection.length === 0) {
        console.error('No contracts in selection file.');
        process.exit(1);
    }

    const handlersDir = path.join(suiteDir, 'handlers');
    fs.mkdirSync(handlersDir, { recursive: true });

    let written = 0;
    let skipped = 0;

    for (const contract of selection) {
        if (!contract || !contract.name || !Array.isArray(contract.functions) || contract.functions.length === 0) {
            continue;
        }

        const handlerPath = path.join(handlersDir, `${contract.name}Handler.sol`);
        const relPath = path.relative(projectRoot, handlerPath);

        if (!force && fs.existsSync(handlerPath) && !isStubHandler(handlerPath)) {
            console.log(`  [skip]  ${relPath}  (contains edits — use --force to overwrite)`);
            skipped++;
            continue;
        }

        const content = buildHandler(contract);
        fs.writeFileSync(handlerPath, content);
        console.log(`  [wrote] ${relPath}  (${contract.functions.length} functions)`);
        written++;
    }

    console.log(`\nDone: ${written} handler(s) written, ${skipped} skipped.`);
}

main();
