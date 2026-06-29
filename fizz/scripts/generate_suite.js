#!/usr/bin/env node
/**
 * generate_suite.js
 *
 * Copies the full template scaffold and fuzzer config into the target
 * project's fuzzing directory, including static utility helpers such as
 * MockERC20. The copied files are then modified by the LLM in later
 * steps with full protocol context.
 *
 * Usage:
 *   node generate_suite.js <PROJECT_ROOT> [--suite-dir <path>] [--meta-dir <path>] [--templates <path>] [--selection <path>]
 *
 * Defaults:
 *   --suite-dir    test/fizz  (relative to project root)
 *   --meta-dir     fizz_data  (relative to project root)
 *   --fuzzing-dir  deprecated alias for --suite-dir
 *   --templates    <script_dir>/../templates
 *   --selection    <meta-dir>/entry-point-selection.json
 */

const fs = require('fs');
const path = require('path');

// ――――――――――――――――――――――――― Argument parsing ―――――――――――――――――――――――――

const args = process.argv.slice(2);
if (args.length === 0 || args[0] === '--help') {
    console.log('Usage: node generate_suite.js <PROJECT_ROOT> [--suite-dir <dir>] [--meta-dir <dir>] [--templates <dir>] [--selection <path>]');
    process.exit(0);
}

const projectRoot = path.resolve(args[0]);
const scriptDir = __dirname;
let suiteRelDir = path.join('test', 'fizz');
let metaRelDir = 'fizz_data';
let templatesDir = path.join(scriptDir, '..', 'templates');
let selectionPath = '';

for (let i = 1; i < args.length; i++) {
    if (args[i] === '--suite-dir' && args[i + 1]) { suiteRelDir = args[++i]; }
    else if (args[i] === '--meta-dir' && args[i + 1]) { metaRelDir = args[++i]; }
    else if (args[i] === '--fuzzing-dir' && args[i + 1]) { suiteRelDir = args[++i]; }
    else if (args[i] === '--templates' && args[i + 1]) { templatesDir = path.resolve(args[++i]); }
    else if (args[i] === '--selection' && args[i + 1]) { selectionPath = path.resolve(args[++i]); }
}

const suiteDir = path.join(projectRoot, suiteRelDir);
const metaDir = path.join(projectRoot, metaRelDir);
if (!selectionPath) {
    selectionPath = path.join(metaDir, 'entry-point-selection.json');
}

// ――――――――――――――――――――――――― Template copying ―――――――――――――――――――――――――

/**
 * Recursively copy template files from src to dst, skipping existing files.
 * This includes static utility helpers such as utils/MockERC20.sol.
 */
function copyTemplates(src, dst, isRoot = false) {
    const copied = [];
    if (!fs.existsSync(dst)) {
        fs.mkdirSync(dst, { recursive: true });
    }

    for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
        const srcPath = path.join(src, entry.name);
        const dstPath = path.join(dst, entry.name);
        const relativeSrcPath = path.relative(templatesDir, srcPath);

        // Skip config files at root level — handled separately
        if (isRoot && (entry.name === 'echidna.yaml' || entry.name === 'medusa.json')) continue;
        if (relativeSrcPath === path.join('handlers', 'Handlers.sol')) continue;

        if (entry.isDirectory()) {
            copied.push(...copyTemplates(srcPath, dstPath));
        } else if (entry.isFile()) {
            if (fs.existsSync(dstPath)) {
                console.log(`  [exists] ${path.relative(projectRoot, dstPath)}`);
            } else {
                const needsSubstitution = metaRelDir !== 'fizz_data' && entry.name === 'README.md';
                if (needsSubstitution) {
                    const content = fs.readFileSync(srcPath, 'utf8').replaceAll('fizz_data', metaRelDir);
                    fs.writeFileSync(dstPath, content);
                } else {
                    fs.copyFileSync(srcPath, dstPath);
                }
                copied.push(dstPath);
                console.log(`  [new]    ${path.relative(projectRoot, dstPath)}`);
            }
        }
    }
    return copied;
}

// ――――――――――――――――――――― Config file placement ―――――――――――――――――――――――

function copyRootConfigs() {
    for (const filename of ['echidna.yaml', 'medusa.json']) {
        const src = path.join(templatesDir, filename);
        const dst = path.join(projectRoot, filename);
        if (!fs.existsSync(src)) continue;

        if (fs.existsSync(dst)) {
            console.log(`  [exists] ${path.relative(projectRoot, dst)}`);
        } else {
            let content = fs.readFileSync(src, 'utf8');
            if (metaRelDir !== 'fizz_data') {
                content = content.replaceAll('fizz_data', metaRelDir);
            }
            fs.writeFileSync(dst, content);
            console.log(`  [new]    ${path.relative(projectRoot, dst)}`);
        }
    }
}

// ――――――――――――――――――――― Selection-driven handler generation ――――――――――――――――――

function readSelectedContracts() {
    if (!fs.existsSync(selectionPath)) {
        console.error(`Selection file not found: ${selectionPath}`);
        console.error('Run select_functions.js first.');
        process.exit(1);
    }

    const selection = JSON.parse(fs.readFileSync(selectionPath, 'utf8'));
    if (!Array.isArray(selection)) {
        console.error(`Invalid selection file: ${selectionPath}`);
        console.error('Expected a JSON array of selected contracts.');
        process.exit(1);
    }

    const uniqueContracts = [];
    const seen = new Set();

    for (const contract of selection) {
        if (!contract || typeof contract.name !== 'string' || contract.name.length === 0) continue;
        if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(contract.name)) {
            console.warn(`  [skip] Invalid Solidity identifier: "${contract.name}"`);
            continue;
        }
        if (seen.has(contract.name)) continue;
        seen.add(contract.name);
        uniqueContracts.push(contract.name);
    }

    if (uniqueContracts.length === 0) {
        console.error(`No selected contracts found in: ${selectionPath}`);
        process.exit(1);
    }

    return uniqueContracts;
}

function buildHandlerTemplate(contractName) {
    return `// SPDX-License-Identifier: MIT
pragma solidity >=0.6.2 <0.9.0;

import "../Base.sol";
import {Properties} from "../Properties.sol";

/// @notice Handles the interaction with ${contractName}
abstract contract ${contractName}Handler is Properties {

    // ――――――――――――――――――――――――― Clamped ――――――――――――――――――――――――――

    // ―――――――――――――――――――――――― Unclamped ―――――――――――――――――――――――――
}
`;
}

function buildHandlersAggregator(contractNames) {
    const imports = contractNames
        .map((contractName) => `import {${contractName}Handler} from "./${contractName}Handler.sol";`)
        .join('\n');
    const inheritance = contractNames
        .map((contractName, index) => `    ${contractName}Handler${index < contractNames.length - 1 ? ',' : ''}`)
        .join('\n');

    return `// SPDX-License-Identifier: MIT
pragma solidity >=0.6.2 <0.9.0;

import "../Base.sol";
${imports}

/// @notice Inherits from all the handlers to expose all entry points in a single contract.
///         Manages environment changes (e.g. current actor, current token, mocks setup, etc.).
abstract contract Handlers is
${inheritance}
{
    function setCurrentActor(uint256 entropy) public {
        actor = actors[entropy % actors.length];
    }
}
`;
}

function writeGeneratedHandlers(contractNames) {
    const handlersDir = path.join(suiteDir, 'handlers');
    fs.mkdirSync(handlersDir, { recursive: true });

    for (const contractName of contractNames) {
        const handlerPath = path.join(handlersDir, `${contractName}Handler.sol`);
        if (fs.existsSync(handlerPath)) {
            console.log(`  [exists] ${path.relative(projectRoot, handlerPath)}`);
            continue;
        }

        fs.writeFileSync(handlerPath, buildHandlerTemplate(contractName));
        console.log(`  [new]    ${path.relative(projectRoot, handlerPath)}`);
    }
}

function writeHandlersAggregator(contractNames) {
    const handlersPath = path.join(suiteDir, 'handlers', 'Handlers.sol');
    const generatedContent = buildHandlersAggregator(contractNames);

    if (fs.existsSync(handlersPath)) {
        console.log(`  [exists] ${path.relative(projectRoot, handlersPath)}`);
        return;
    }

    fs.writeFileSync(handlersPath, generatedContent);
    console.log(`  [new]    ${path.relative(projectRoot, handlersPath)}`);
}

// ――――――――――――――――――――――――――――― Main ――――――――――――――――――――――――――――――

function main() {
    if (!fs.existsSync(templatesDir)) {
        console.error(`Templates directory not found: ${templatesDir}`);
        process.exit(1);
    }

    const selectedContracts = readSelectedContracts();

    console.log('Copying template scaffold...');
    const copied = copyTemplates(templatesDir, suiteDir, true);

    console.log('\nCopying config files...');
    copyRootConfigs();

    console.log('\nGenerating handler stubs...');
    writeGeneratedHandlers(selectedContracts);
    writeHandlersAggregator(selectedContracts);

    console.log('\nScaffold complete.');
    console.log(`  new files: ${copied.length}`);
    console.log('\nNext: the LLM modifies the copied scaffold in later steps');
    console.log('to wire setup, generate handlers, and add invariants.');
}

main();
