#!/usr/bin/env node
/**
 * extract_abis.js
 *
 * Walks Foundry (or Hardhat) compilation artifacts and extracts contract data
 * into a contracts.json file compatible with the Fizz skill pipeline.
 *
 * Usage:
 *   node extract_abis.js <PROJECT_ROOT> [--output <path>] [--src <contracts_dir>] [--out <artifacts_dir>] [--exclude <dir1,dir2,...>]
 *
 * Defaults:
 *   --src / --out  read from foundry.toml when available
 *   --src          src   (fallback relative to project root)
 *   --out          out   (fallback relative to project root)
 *   --output       <meta-dir>/contracts.json
 *   --meta-dir     fizz_data  (relative to project root)
 *   --fuzzing-dir  deprecated alias for --meta-dir
 */

const fs = require('fs');
const path = require('path');

function readFoundryPaths(projectRoot) {
    const foundryToml = path.join(projectRoot, 'foundry.toml');
    const defaults = { src: 'src', out: 'out' };

    if (!fs.existsSync(foundryToml)) return defaults;

    const lines = fs.readFileSync(foundryToml, 'utf-8').split(/\r?\n/);
    let section = '';
    const values = { ...defaults };

    for (const rawLine of lines) {
        const line = rawLine.trim();
        if (!line || line.startsWith('#')) continue;

        const sectionMatch = line.match(/^\[(.+)\]$/);
        if (sectionMatch) {
            section = sectionMatch[1].trim();
            continue;
        }

        const keyValueMatch = line.match(/^(src|out)\s*=\s*"([^"]+)"/);
        if (!keyValueMatch) continue;

        const [, key, value] = keyValueMatch;
        if (section === '' || section === 'profile.default') {
            values[key] = value;
        }
    }

    return values;
}

// ――――――――――――――――――――――――― Argument parsing ―――――――――――――――――――――――――

const args = process.argv.slice(2);
if (args.length === 0 || args[0] === '--help') {
    console.log('Usage: node extract_abis.js <PROJECT_ROOT> [--output <path>] [--src <dir>] [--out <dir>]');
    process.exit(0);
}

const projectRoot = path.resolve(args[0]);
const foundryPaths = readFoundryPaths(projectRoot);
let srcDir = foundryPaths.src;
let outDir = foundryPaths.out;
let metaRelDir = 'fizz_data';
let outputPath = '';
let extraExcludes = [];

for (let i = 1; i < args.length; i++) {
    if (args[i] === '--src' && args[i + 1]) { srcDir = args[++i]; }
    else if (args[i] === '--out' && args[i + 1]) { outDir = args[++i]; }
    else if (args[i] === '--output' && args[i + 1]) { outputPath = path.resolve(args[++i]); }
    else if (args[i] === '--meta-dir' && args[i + 1]) { metaRelDir = args[++i]; }
    else if (args[i] === '--fuzzing-dir' && args[i + 1]) { metaRelDir = args[++i]; }
    else if (args[i] === '--exclude' && args[i + 1]) { extraExcludes = args[++i].split(',').map(s => s.trim().toLowerCase()); }
}

if (!outputPath) {
    outputPath = path.join(projectRoot, metaRelDir, 'contracts.json');
}

const EXCLUDED_DIRS = new Set(['mock', 'mocks', 'test', 'tests', 'fizz', ...extraExcludes]);
// Also exclude the fuzzing output directory itself (by basename) to prevent circular extraction
const metaDirBasename = path.basename(metaRelDir).toLowerCase();
if (metaDirBasename && !EXCLUDED_DIRS.has(metaDirBasename)) {
    EXCLUDED_DIRS.add(metaDirBasename);
}

const contractsDir = path.join(projectRoot, srcDir);
const artifactsDir = path.join(projectRoot, outDir);

// ――――――――――――――――――――――― Source file discovery ――――――――――――――――――――――――

/**
 * Recursively find all .sol files under a directory.
 */
function findSolFiles(dir) {
    const results = [];
    if (!fs.existsSync(dir)) return results;

    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory()) {
            if (EXCLUDED_DIRS.has(entry.name.toLowerCase())) continue;
            results.push(...findSolFiles(fullPath));
        } else if (entry.isFile() && entry.name.endsWith('.sol')) {
            results.push(fullPath);
        }
    }
    return results;
}

/**
 * Extract contract names from a .sol file via regex (strips comments first).
 */
function findContracts(filePath) {
    let contents = fs.readFileSync(filePath, 'utf-8')
        .replace(/\/\/.*$/gm, '')           // single-line comments
        .replace(/\/\*[\s\S]*?\*\//g, '');  // multi-line comments

    const contractRegex = /\bcontract\s+([a-zA-Z0-9_]+)\b/g;
    const contracts = [];
    let match;
    while ((match = contractRegex.exec(contents)) !== null) {
        contracts.push(match[1]);
    }
    return contracts;
}

// ―――――――――――――――――――――――― ABI artifact reading ――――――――――――――――――――――――

/**
 * Normalize ABI input types — strip prefixes for struct/contract/enum.
 */
function mapInputs(inputs) {
    return (inputs || []).map((input) => {
        let internalType = input.internalType || input.type;
        let type = input.type.includes('[]') ? 'array' : input.type;

        if (internalType.startsWith('struct ')) {
            internalType = internalType.slice(7);
        } else if (internalType.startsWith('contract ')) {
            internalType = internalType.slice(9);
            type = 'contract';
        } else if (internalType.startsWith('enum ')) {
            internalType = internalType.slice(5);
            type = 'enum';
        }

        return { name: input.name, type, internalType };
    });
}

/**
 * Resolve artifact path — tries Foundry layout first, then Hardhat.
 * Foundry:  out/<FileName.sol>/<ContractName>.json
 * Hardhat:  artifacts/contracts/<relPath>/<ContractName>.json
 */
function resolveArtifactPath(fileRelPath, contractName) {
    // Foundry layout
    const foundryPath = path.join(artifactsDir, path.basename(fileRelPath), `${contractName}.json`);
    if (fs.existsSync(foundryPath)) return foundryPath;

    // Hardhat layout (mirrors source directory structure)
    const hardhatPath = path.join(artifactsDir, fileRelPath, `${contractName}.json`);
    if (fs.existsSync(hardhatPath)) return hardhatPath;

    // Hardhat alternate: artifacts/contracts/...
    const hardhatAltPath = path.join(projectRoot, 'artifacts', 'contracts', fileRelPath, `${contractName}.json`);
    if (fs.existsSync(hardhatAltPath)) return hardhatAltPath;

    return null;
}

/**
 * Read an artifact and extract functions, constructor, receive, fallback.
 */
function extractContractData(fileRelPath, contractName, sourcePath) {
    const artifactPath = resolveArtifactPath(fileRelPath, contractName);
    if (!artifactPath) {
        console.warn(`  [skip] No artifact found for ${contractName} (${fileRelPath})`);
        return null;
    }

    const artifact = JSON.parse(fs.readFileSync(artifactPath, 'utf-8'));
    const abi = artifact.abi;
    if (!abi || !Array.isArray(abi)) {
        console.warn(`  [skip] No ABI in artifact for ${contractName}`);
        return null;
    }

    // Check if it's an interface or abstract (no deployed bytecode)
    const bytecode = artifact.bytecode?.object || artifact.bytecode || '';
    const deployedBytecode = artifact.deployedBytecode?.object || artifact.deployedBytecode || '';
    if (typeof deployedBytecode === 'string' && (deployedBytecode === '0x' || deployedBytecode === '')) {
        // Could be interface or abstract — check if it has any non-view functions
        const hasStateful = abi.some(item =>
            item.type === 'function' && item.stateMutability !== 'view' && item.stateMutability !== 'pure'
        );
        if (!hasStateful) {
            console.warn(`  [skip] ${contractName} appears to be an interface (no state-changing functions)`);
            return null;
        }
    }

    // Extract state-changing functions (exclude view and pure)
    const functions = abi
        .filter(item => item.type === 'function' && item.stateMutability !== 'view' && item.stateMutability !== 'pure')
        .map(item => ({
            name: item.name,
            inputs: mapInputs(item.inputs),
            stateMutability: item.stateMutability,
        }));

    // Constructor
    const ctorAbi = abi.find(item => item.type === 'constructor');
    const constructor = {
        inputs: ctorAbi ? mapInputs(ctorAbi.inputs) : [],
        stateMutability: ctorAbi ? ctorAbi.stateMutability : 'nonpayable',
    };

    // Receive / Fallback
    const hasReceive = abi.some(item => item.type === 'receive');
    const hasFallback = abi.some(item => item.type === 'fallback');

    // Skip contracts that do not expose any state-changing functions.
    // receive()/fallback()-only contracts are excluded from selection output.
    if (functions.length === 0) {
        console.warn(`  [skip] ${contractName} has no state-changing functions in its ABI`);
        return null;
    }

    return {
        name: contractName,
        sourcePath,
        artifactPath: path.relative(projectRoot, artifactPath),
        constructor,
        functions,
        hasReceive,
        hasFallback,
    };
}

// ――――――――――――――――――――――――――――― Main ――――――――――――――――――――――――――――――

/**
 * Check if a directory contains at least one .json artifact file (not in build-info).
 */
function hasValidArtifacts(dir) {
    if (!fs.existsSync(dir)) return false;
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        if (entry.name === 'build-info') continue;
        const fullPath = path.join(dir, entry.name);
        if (entry.isDirectory()) {
            for (const sub of fs.readdirSync(fullPath, { withFileTypes: true })) {
                if (sub.isFile() && sub.name.endsWith('.json')) {
                    // Quick sanity: file must have non-trivial size (not empty dir artifact)
                    const stat = fs.statSync(path.join(fullPath, sub.name));
                    if (stat.size > 100) return true;
                }
            }
        }
    }
    return false;
}

function main() {
    if (!fs.existsSync(contractsDir)) {
        console.error(`Source directory not found: ${contractsDir}`);
        process.exit(1);
    }
    if (!hasValidArtifacts(artifactsDir)) {
        console.error(`No valid compilation artifacts found in: ${artifactsDir}`);
        console.error('Run `forge build` first.');
        process.exit(2);
    }

    const solFiles = findSolFiles(contractsDir);
    console.log(`Found ${solFiles.length} .sol files in ${srcDir}/`);

    const contracts = [];

    for (const filePath of solFiles) {
        const fileRelPath = path.relative(projectRoot, filePath);
        const contractNames = findContracts(filePath);

        for (const contractName of contractNames) {
            const data = extractContractData(fileRelPath, contractName, fileRelPath);
            if (data) {
                contracts.push(data);
                console.log(`  [ok] ${contractName} — ${data.functions.length} functions`);
            }
        }
    }

    fs.mkdirSync(path.dirname(outputPath), { recursive: true });
    fs.writeFileSync(outputPath, JSON.stringify(contracts, null, 2));
    console.log(`\nWrote ${contracts.length} contracts to ${path.relative(projectRoot, outputPath)}`);
}

main();
