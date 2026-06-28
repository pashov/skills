#!/usr/bin/env node
/**
 * fizz_sync.js
 *
 * Deterministic drift detector for projects previously processed by the
 * Fizz skill. Compares the stored snapshot (fizz_data/last-run.json)
 * against the current source/ABI state and emits:
 *   - a human-readable report to stdout
 *   - a machine-readable JSON report for consumption by the /fizz-sync skill
 *
 * Modes:
 *   (default)          Dry-run. Prints delta + writes sync-report.json. No file edits.
 *   --init             Writes a fresh last-run.json from current state. Refuses to
 *                      overwrite an existing snapshot unless --force is passed.
 *   --refresh-snapshot Overwrites last-run.json with current state (used after
 *                      --apply to "bless" the new state). Requires an existing snapshot.
 *   --apply-handlers   Regenerates handler files for contracts whose signatures drifted.
 *                      Backs up the old handler file to <name>.pre-sync.bak before
 *                      overwriting. User edits to clamping bodies WILL be lost — intended
 *                      to be driven by the skill doc which then reseeds them via the LLM.
 *
 * Options:
 *   --only <name>      Scope diff/apply to a single contract name.
 *   --force            Allow destructive operations (--init over existing snapshot).
 *   --meta-dir <dir>   Metadata directory (default: fizz_data).
 *   --suite-dir <dir>  Suite directory    (default: test/fizz).
 *   --report <path>    Explicit JSON report path (default: <meta>/sync-report.json).
 *
 * Exit codes:
 *   0 — no drift detected (or --init/--refresh-snapshot/--apply-handlers succeeded)
 *   1 — drift detected in dry-run mode
 *   2 — precondition error (missing file, bad input)
 *   3 — unexpected error
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

// ──────────────────────────────── CLI ────────────────────────────────

const args = process.argv.slice(2);
if (args.length === 0 || args.includes('--help') || args.includes('-h')) {
    printUsage();
    process.exit(0);
}

const projectRoot = path.resolve(args[0]);
const opts = {
    init: false,
    refreshSnapshot: false,
    applyHandlers: false,
    force: false,
    only: null,
    metaRelDir: 'fizz_data',
    suiteRelDir: path.join('test', 'fizz'),
    reportPath: null,
};

for (let i = 1; i < args.length; i++) {
    const a = args[i];
    if (a === '--init') opts.init = true;
    else if (a === '--refresh-snapshot') opts.refreshSnapshot = true;
    else if (a === '--apply-handlers') opts.applyHandlers = true;
    else if (a === '--force') opts.force = true;
    else if (a === '--only' && args[i + 1]) opts.only = args[++i];
    else if (a === '--meta-dir' && args[i + 1]) opts.metaRelDir = args[++i];
    else if (a === '--suite-dir' && args[i + 1]) opts.suiteRelDir = args[++i];
    else if (a === '--report' && args[i + 1]) opts.reportPath = path.resolve(args[++i]);
    else {
        console.error(`Unknown argument: ${a}`);
        printUsage();
        process.exit(2);
    }
}

const metaDir = path.join(projectRoot, opts.metaRelDir);
const suiteDir = path.join(projectRoot, opts.suiteRelDir);
const snapshotPath = path.join(metaDir, 'last-run.json');
const contractsJsonPath = path.join(metaDir, 'contracts.json');
const selectionPath = path.join(metaDir, 'entry-point-selection.json');
const propertiesMdPath = path.join(projectRoot, 'PROPERTIES.md');
const propertiesSolPath = path.join(suiteDir, 'Properties.sol');
const handlersDir = path.join(suiteDir, 'handlers');
const reportPath = opts.reportPath || path.join(metaDir, 'sync-report.json');

function printUsage() {
    console.log(
`Usage: node fizz_sync.js <PROJECT_ROOT> [mode] [options]

Modes (choose at most one):
  (default)            Dry-run drift report.
  --init               Write last-run.json from current state.
  --refresh-snapshot   Overwrite last-run.json with current state.
  --apply-handlers     Regenerate drifted handler files (creates .pre-sync.bak).

Options:
  --only <contract>    Scope to a single contract name.
  --force              Allow destructive ops (overwrite snapshot in --init).
  --meta-dir <dir>     Metadata directory (default: fizz_data).
  --suite-dir <dir>    Suite directory    (default: test/fizz).
  --report <path>      Explicit JSON report path.`
    );
}

// ────────────────────────── Helpers ──────────────────────────

function fail(code, msg) {
    console.error(`fizz-sync: ${msg}`);
    process.exit(code);
}

function loadJson(p) {
    if (!fs.existsSync(p)) return null;
    try {
        return JSON.parse(fs.readFileSync(p, 'utf8'));
    } catch (e) {
        fail(2, `failed to parse ${p}: ${e.message}`);
    }
}

function sha256File(p) {
    if (!fs.existsSync(p)) return null;
    return 'sha256:' + crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
}

/** Canonical Solidity-style function signature used as the match key. */
function canonicalSignature(fn) {
    const parts = (fn.inputs || []).map(i => {
        // Prefer internalType when present so struct types and arrays are distinguishable.
        // Fall back to raw ABI type otherwise.
        const t = i.internalType || i.type || 'unknown';
        // Strip leading 'struct ' / 'contract ' / 'enum ' — extract_abis already does this
        // for contracts.json, but belt-and-suspenders for snapshots written from elsewhere.
        return t.replace(/^(struct|contract|enum)\s+/, '');
    });
    return `${fn.name}(${parts.join(',')})`;
}

/** camelCase instance name (matches generate_handlers.js). */
function lcFirst(s) { return s ? s.charAt(0).toLowerCase() + s.slice(1) : s; }

// ────────────────────── Snapshot build/read ──────────────────────

/**
 * Build a snapshot object from current metadata + source state.
 *
 * Scope comes from entry-point-selection.json (the user's prior choice of what to fuzz).
 * Signatures come from contracts.json (refreshed by extract_abis before sync runs).
 * Tier comes from entry-point-selection.json.
 *
 * Contracts in selection but no longer in contracts.json become "removed".
 * New functions that appear in contracts.json (for in-scope contracts) inherit tier "primary".
 */
function buildSnapshot() {
    const selection = loadJson(selectionPath);
    if (!selection) fail(2, `missing ${path.relative(projectRoot, selectionPath)} — run Step 4 of the Fizz skill first.`);

    const contractsJson = loadJson(contractsJsonPath);
    if (!contractsJson) fail(2, `missing ${path.relative(projectRoot, contractsJsonPath)} — run extract_abis.js first.`);
    const contractsJsonByName = new Map(contractsJson.map(c => [c.name, c]));

    // Tier lookup: selection[contract].function.name → tier
    const tierByContract = new Map();
    for (const sel of selection) {
        const m = new Map();
        for (const f of (sel.functions || [])) m.set(canonicalSignature(f), f.tier || 'primary');
        tierByContract.set(sel.name, m);
    }

    const contracts = [];
    for (const sel of selection) {
        const fresh = contractsJsonByName.get(sel.name);
        if (!fresh) {
            // Contract removed from source — keep the old entry shape with an empty function list
            // so diffSnapshots flags it as removed.
            contracts.push({
                name: sel.name,
                sourcePath: sel.sourcePath,
                sourceHash: null,
                constructor: sel.constructor || { inputs: [], stateMutability: 'nonpayable' },
                functions: [],
                _removedFromSource: true,
            });
            continue;
        }
        const srcAbs = path.join(projectRoot, fresh.sourcePath);
        const tierMap = tierByContract.get(sel.name) || new Map();
        contracts.push({
            name: fresh.name,
            sourcePath: fresh.sourcePath,
            sourceHash: sha256File(srcAbs),
            constructor: fresh.constructor || { inputs: [], stateMutability: 'nonpayable' },
            functions: (fresh.functions || []).map(f => {
                const sig = canonicalSignature(f);
                return {
                    name: f.name,
                    inputs: f.inputs || [],
                    stateMutability: f.stateMutability || 'nonpayable',
                    tier: tierMap.get(sig) || 'primary',
                    signature: sig,
                };
            }),
        });
    }

    // Handler file hashes (all .sol files under handlers/, excluding Handlers.sol aggregator).
    const handlerFiles = {};
    if (fs.existsSync(handlersDir)) {
        for (const entry of fs.readdirSync(handlersDir)) {
            if (!entry.endsWith('.sol')) continue;
            const full = path.join(handlersDir, entry);
            handlerFiles[entry] = sha256File(full);
        }
    }

    // Property registry from PROPERTIES.md + tagged Solidity in Properties.sol.
    const propertiesFromMd = parsePropertiesMd();
    const taggedSolidity = scanTaggedProperties();
    const properties = propertiesFromMd.map(p => ({
        id: p.id,
        checkbox: p.checkbox,
        functionName: taggedSolidity.get(p.id)?.functionName || null,
        file: taggedSolidity.get(p.id)?.file || null,
    }));

    return {
        version: 1,
        createdAt: new Date().toISOString(),
        projectRoot: path.relative(projectRoot, projectRoot) || '.',
        suiteDir: opts.suiteRelDir,
        metaDir: opts.metaRelDir,
        contracts,
        handlers: handlerFiles,
        properties,
    };
}

/**
 * Parse PROPERTIES.md (project root). Returns [{id, checkbox}].
 * Checkbox states: " " (pending), "x" (implemented), "~" (quarantined/stale),
 * "-" (manually dropped).
 */
function parsePropertiesMd() {
    if (!fs.existsSync(propertiesMdPath)) return [];
    const content = fs.readFileSync(propertiesMdPath, 'utf8');
    const re = /^- \[([ x~\-])\]\s+\*\*(GL-\d+|SP-\d+)\*\*/gm;
    const out = [];
    let m;
    while ((m = re.exec(content)) !== null) {
        out.push({ id: m[2], checkbox: m[1] });
    }
    return out;
}

/**
 * Scan Properties.sol + handler files for `/// @notice <ID>:` tagged functions.
 * Returns Map<id, {functionName, file}>.
 */
function scanTaggedProperties() {
    const out = new Map();
    const files = [];
    if (fs.existsSync(propertiesSolPath)) files.push(propertiesSolPath);
    if (fs.existsSync(handlersDir)) {
        for (const entry of fs.readdirSync(handlersDir)) {
            if (entry.endsWith('.sol')) files.push(path.join(handlersDir, entry));
        }
    }
    const re = /\/\/\/ @notice\s+(GL-\d+|SP-\d+):[^\n]*\n(?:\s*\/\/\/[^\n]*\n)*\s*function\s+(\w+)\s*\(/g;
    for (const f of files) {
        const content = fs.readFileSync(f, 'utf8');
        let m;
        while ((m = re.exec(content)) !== null) {
            out.set(m[1], { functionName: m[2], file: path.relative(projectRoot, f) });
        }
    }
    return out;
}

// ────────────────────── Diff logic ──────────────────────

/**
 * Compute diff between stored snapshot and freshly-built snapshot.
 * Returns an object with categorised deltas + a `hasDrift` boolean.
 */
function diffSnapshots(oldSnap, newSnap) {
    const oldByName = new Map((oldSnap.contracts || []).map(c => [c.name, c]));
    const newByName = new Map((newSnap.contracts || []).map(c => [c.name, c]));

    const contractsAdded = [];
    const contractsRemoved = [];
    const contractsChanged = [];
    const sourcesChanged = [];

    for (const [name, newC] of newByName) {
        if (opts.only && name !== opts.only) continue;
        if (!oldByName.has(name)) {
            contractsAdded.push({
                name,
                sourcePath: newC.sourcePath,
                functions: newC.functions.map(f => ({ signature: f.signature, tier: f.tier })),
            });
            continue;
        }
        const oldC = oldByName.get(name);
        if (oldC.sourceHash !== newC.sourceHash) {
            sourcesChanged.push({ name, sourcePath: newC.sourcePath });
        }

        const oldFns = new Map(oldC.functions.map(f => [f.signature, f]));
        const newFns = new Map(newC.functions.map(f => [f.signature, f]));

        // Also index by bare name so we can detect signature changes
        // (same name + different inputs counts as "changed", not add+remove).
        const oldByNameOnly = new Map();
        for (const f of oldC.functions) {
            if (!oldByNameOnly.has(f.name)) oldByNameOnly.set(f.name, []);
            oldByNameOnly.get(f.name).push(f);
        }
        const newByNameOnly = new Map();
        for (const f of newC.functions) {
            if (!newByNameOnly.has(f.name)) newByNameOnly.set(f.name, []);
            newByNameOnly.get(f.name).push(f);
        }

        const fnAdded = [];
        const fnRemoved = [];
        const fnChanged = [];
        const fnTierChanged = [];

        for (const [sig, f] of newFns) {
            if (oldFns.has(sig)) {
                const oldF = oldFns.get(sig);
                if (oldF.tier !== f.tier) {
                    fnTierChanged.push({ signature: sig, oldTier: oldF.tier, newTier: f.tier });
                }
                continue;
            }
            // Not found by sig — was it a rename of a same-named function?
            if (oldByNameOnly.has(f.name) && !newByNameOnly.get(f.name).every(x => oldFns.has(x.signature))) {
                const oldMatches = oldByNameOnly.get(f.name).filter(x => !newFns.has(x.signature));
                if (oldMatches.length === 1) {
                    fnChanged.push({
                        name: f.name,
                        oldSignature: oldMatches[0].signature,
                        newSignature: sig,
                        handlerMethodName: `${lcFirst(name)}_${f.name}`,
                    });
                    continue;
                }
            }
            fnAdded.push({ signature: sig, name: f.name, tier: f.tier, handlerMethodName: `${lcFirst(name)}_${f.name}` });
        }

        for (const [sig, f] of oldFns) {
            if (newFns.has(sig)) continue;
            // Already reported as signature change?
            if (fnChanged.some(c => c.oldSignature === sig)) continue;
            fnRemoved.push({ signature: sig, name: f.name, handlerMethodName: `${lcFirst(name)}_${f.name}` });
        }

        if (fnAdded.length || fnRemoved.length || fnChanged.length || fnTierChanged.length) {
            contractsChanged.push({
                name,
                sourcePath: newC.sourcePath,
                functionsAdded: fnAdded,
                functionsRemoved: fnRemoved,
                functionsChanged: fnChanged,
                tierChanged: fnTierChanged,
            });
        }
    }

    for (const [name, oldC] of oldByName) {
        if (opts.only && name !== opts.only) continue;
        if (!newByName.has(name)) {
            contractsRemoved.push({
                name,
                sourcePath: oldC.sourcePath,
                handlerFile: `${name}Handler.sol`,
            });
        }
    }

    // Handler file drift — files that existed at snapshot-time and were user-edited since,
    // plus orphaned handlers for removed contracts.
    const handlerOrphans = [];
    const handlerModified = [];
    const handlerMissing = [];

    const oldHandlers = oldSnap.handlers || {};
    const newHandlers = newSnap.handlers || {};

    for (const [file, oldHash] of Object.entries(oldHandlers)) {
        const newHash = newHandlers[file];
        if (newHash === undefined) {
            handlerMissing.push({ file });
            continue;
        }
        if (newHash !== oldHash) {
            handlerModified.push({ file });
        }
    }
    for (const rm of contractsRemoved) {
        if (newHandlers[rm.handlerFile] !== undefined) {
            handlerOrphans.push({ file: rm.handlerFile, contract: rm.name });
        }
    }

    // Property drift: any property whose tagged handler call site references a removed/changed function.
    const propDrift = [];
    const removedHandlerMethods = new Set();
    for (const c of contractsChanged) {
        for (const f of c.functionsRemoved) removedHandlerMethods.add(f.handlerMethodName);
        for (const f of c.functionsChanged) removedHandlerMethods.add(f.handlerMethodName);
    }
    for (const c of contractsRemoved) {
        // Every handler method of a removed contract is dead — we approximate by the
        // contract instance prefix.
        removedHandlerMethods.add(`__contract_removed__:${c.name}`);
    }

    if (removedHandlerMethods.size > 0) {
        // Scan property function bodies for references to the dead handler methods.
        const scanFiles = [];
        if (fs.existsSync(propertiesSolPath)) scanFiles.push(propertiesSolPath);
        if (fs.existsSync(handlersDir)) {
            for (const entry of fs.readdirSync(handlersDir)) {
                if (entry.endsWith('.sol')) scanFiles.push(path.join(handlersDir, entry));
            }
        }
        for (const file of scanFiles) {
            const content = fs.readFileSync(file, 'utf8');
            for (const dead of removedHandlerMethods) {
                if (dead.startsWith('__contract_removed__:')) continue;
                const re = new RegExp(`\\b${dead}\\s*\\(`);
                if (re.test(content)) {
                    propDrift.push({
                        file: path.relative(projectRoot, file),
                        reference: dead,
                        reason: 'handler method signature drifted or function removed',
                    });
                }
            }
        }
    }

    const hasDrift =
        contractsAdded.length +
        contractsRemoved.length +
        contractsChanged.length +
        sourcesChanged.length +
        handlerOrphans.length +
        handlerModified.length +
        handlerMissing.length +
        propDrift.length > 0;

    return {
        generatedAt: new Date().toISOString(),
        snapshotPath: path.relative(projectRoot, snapshotPath),
        hasDrift,
        contracts: {
            added: contractsAdded,
            removed: contractsRemoved,
            changed: contractsChanged,
            sourcesChanged,
        },
        handlers: {
            orphan: handlerOrphans,
            modified: handlerModified,
            missing: handlerMissing,
        },
        properties: {
            referencingRemoved: propDrift,
            fromSnapshot: oldSnap.properties || [],
        },
    };
}

// ────────────────────── Pretty printer ──────────────────────

function printReport(report) {
    const lines = [];
    lines.push('');
    lines.push('╭────────────────── fizz-sync drift report ──────────────────╮');
    if (!report.hasDrift) {
        lines.push('│ ✓ No drift detected. Snapshot is up to date.              │');
        lines.push('╰────────────────────────────────────────────────────────────╯');
        console.log(lines.join('\n'));
        return;
    }

    const cs = report.contracts;
    if (cs.added.length) {
        lines.push('│ + Contracts added (new in selection since snapshot):       │');
        for (const c of cs.added) {
            lines.push(`│    ${c.name} (${c.functions.length} functions)`);
        }
    }
    if (cs.removed.length) {
        lines.push('│ - Contracts removed (in snapshot, gone from selection):    │');
        for (const c of cs.removed) {
            lines.push(`│    ${c.name} — handler: ${c.handlerFile}`);
        }
    }
    if (cs.changed.length) {
        lines.push('│ ~ Contracts with drift:                                    │');
        for (const c of cs.changed) {
            lines.push(`│    ${c.name}`);
            for (const f of c.functionsAdded)   lines.push(`│      + added:   ${f.signature} [${f.tier}]`);
            for (const f of c.functionsRemoved) lines.push(`│      - removed: ${f.signature}`);
            for (const f of c.functionsChanged) lines.push(`│      ~ changed: ${f.oldSignature}  →  ${f.newSignature}`);
            for (const f of c.tierChanged)      lines.push(`│      ~ tier:    ${f.signature}  ${f.oldTier} → ${f.newTier}`);
        }
    }
    if (cs.sourcesChanged.length) {
        lines.push('│ • Source hash changed (semantic review recommended):       │');
        for (const c of cs.sourcesChanged) {
            lines.push(`│    ${c.name} (${c.sourcePath})`);
        }
    }
    const hs = report.handlers;
    if (hs.orphan.length) {
        lines.push('│ ✗ Orphan handlers (contract removed):                      │');
        for (const h of hs.orphan) lines.push(`│    ${h.file}`);
    }
    if (hs.modified.length) {
        lines.push('│ • Handler files modified since snapshot (user edits):      │');
        for (const h of hs.modified) lines.push(`│    ${h.file}`);
    }
    if (hs.missing.length) {
        lines.push('│ ✗ Handler files missing (deleted since snapshot):          │');
        for (const h of hs.missing) lines.push(`│    ${h.file}`);
    }
    const pd = report.properties.referencingRemoved;
    if (pd.length) {
        lines.push('│ ✗ Property/handler files referencing removed functions:    │');
        for (const p of pd) lines.push(`│    ${p.file}  →  ${p.reference}`);
    }
    lines.push('╰────────────────────────────────────────────────────────────╯');
    console.log(lines.join('\n'));
}

// ────────────────────── Handler apply ──────────────────────

/**
 * Spawn generate_handlers.js to regenerate handlers for drifted contracts only.
 *
 * Scoped selection is built from the FRESH contracts.json (not the stale selection file),
 * so newly-added functions are included in the regenerated handler. Tier is preserved from
 * the old selection for unchanged functions and defaults to "primary" for added ones.
 *
 * Also updates entry-point-selection.json in place so future dry-runs diff against a
 * consistent scope (otherwise the newly-added functions would show up as drift forever).
 */
function applyHandlerRegen(report) {
    const { execSync } = require('child_process');

    const oldSelection = loadJson(selectionPath);
    if (!oldSelection) fail(2, 'missing entry-point-selection.json — cannot regenerate handlers.');
    const contractsJson = loadJson(contractsJsonPath);
    if (!contractsJson) fail(2, 'missing contracts.json — run extract_abis.js first.');
    const contractsJsonByName = new Map(contractsJson.map(c => [c.name, c]));

    const driftedNames = new Set([
        ...report.contracts.added.map(c => c.name),
        ...report.contracts.changed.map(c => c.name),
    ]);
    if (opts.only) {
        for (const n of [...driftedNames]) if (n !== opts.only) driftedNames.delete(n);
    }
    if (driftedNames.size === 0) {
        console.log('fizz-sync: no added/changed contracts to regenerate — nothing to do.');
        return { regenerated: [], backedUp: [] };
    }

    // Back up existing handler files first.
    const backedUp = [];
    for (const name of driftedNames) {
        const file = path.join(handlersDir, `${name}Handler.sol`);
        if (fs.existsSync(file)) {
            const bak = `${file}.pre-sync.bak`;
            fs.copyFileSync(file, bak);
            backedUp.push(path.relative(projectRoot, bak));
        }
    }

    // Build scoped selection from fresh contracts.json, preserving tiers from the old selection.
    // Unchanged functions keep their tier. Added functions default to "primary".
    // Removed functions are dropped entirely.
    const oldSelectionByName = new Map(oldSelection.map(c => [c.name, c]));
    const scopedSelection = [];
    for (const name of driftedNames) {
        const fresh = contractsJsonByName.get(name);
        if (!fresh) continue; // contract disappeared — handled as "removed" elsewhere
        const oldEntry = oldSelectionByName.get(name);
        const oldTierBySig = new Map();
        if (oldEntry) {
            for (const f of (oldEntry.functions || [])) {
                oldTierBySig.set(canonicalSignature(f), f.tier || 'primary');
            }
        }
        scopedSelection.push({
            ...fresh,
            functions: (fresh.functions || []).map(f => ({
                ...f,
                tier: oldTierBySig.get(canonicalSignature(f)) || 'primary',
            })),
        });
    }
    const scopedPath = path.join(metaDir, 'sync-scoped-selection.json');
    fs.writeFileSync(scopedPath, JSON.stringify(scopedSelection, null, 2));

    // Also update the main selection file: replace drifted entries with the fresh ones,
    // keep untouched contracts as-is. This keeps the authoritative selection in sync.
    const newSelection = oldSelection.map(c => {
        if (driftedNames.has(c.name)) {
            const fresh = scopedSelection.find(s => s.name === c.name);
            return fresh || c;
        }
        return c;
    });
    // Also append entries for contracts that were added in drift but were missing from old selection.
    for (const fresh of scopedSelection) {
        if (!oldSelectionByName.has(fresh.name)) newSelection.push(fresh);
    }
    fs.writeFileSync(selectionPath, JSON.stringify(newSelection, null, 2));

    const genScript = path.join(__dirname, 'generate_handlers.js');
    const cmd = `node "${genScript}" "${projectRoot}" --suite-dir "${opts.suiteRelDir}" --meta-dir "${opts.metaRelDir}" --selection "${scopedPath}" --force`;
    console.log(`fizz-sync: running ${cmd}`);
    execSync(cmd, { stdio: 'inherit' });
    // Clean up scoped selection artifact.
    try { fs.unlinkSync(scopedPath); } catch (_) {}

    return { regenerated: [...driftedNames], backedUp };
}

// ────────────────────── Main ──────────────────────

function main() {
    if (!fs.existsSync(projectRoot)) fail(2, `project root not found: ${projectRoot}`);
    if (!fs.existsSync(metaDir))     fail(2, `meta dir not found: ${opts.metaRelDir} — has the Fizz skill been run?`);

    // Modes that do not require a stored snapshot.
    if (opts.init) {
        if (fs.existsSync(snapshotPath) && !opts.force) {
            fail(2, `snapshot already exists at ${path.relative(projectRoot, snapshotPath)} — use --force to overwrite, or use --refresh-snapshot.`);
        }
        const snap = buildSnapshot();
        fs.writeFileSync(snapshotPath, JSON.stringify(snap, null, 2));
        console.log(`fizz-sync: wrote initial snapshot to ${path.relative(projectRoot, snapshotPath)} (${snap.contracts.length} contracts, ${snap.properties.length} properties).`);
        return;
    }

    const oldSnap = loadJson(snapshotPath);
    if (!oldSnap) fail(2, `no snapshot at ${path.relative(projectRoot, snapshotPath)} — run: node fizz_sync.js ${opts.metaRelDir === 'fizz_data' ? '.' : projectRoot} --init`);

    if (opts.refreshSnapshot) {
        const snap = buildSnapshot();
        fs.writeFileSync(snapshotPath, JSON.stringify(snap, null, 2));
        console.log(`fizz-sync: refreshed snapshot at ${path.relative(projectRoot, snapshotPath)} (${snap.contracts.length} contracts, ${snap.properties.length} properties).`);
        return;
    }

    const newSnap = buildSnapshot();
    const report = diffSnapshots(oldSnap, newSnap);

    // Always write the machine-readable report for skill consumption.
    fs.mkdirSync(path.dirname(reportPath), { recursive: true });
    fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));

    if (opts.applyHandlers) {
        const result = applyHandlerRegen(report);
        console.log(`fizz-sync: regenerated ${result.regenerated.length} handler(s); backups: ${result.backedUp.length}`);
        if (result.backedUp.length) {
            for (const b of result.backedUp) console.log(`  bak: ${b}`);
        }
        return;
    }

    printReport(report);
    console.log(`\nMachine-readable report: ${path.relative(projectRoot, reportPath)}`);
    if (report.hasDrift) process.exit(1);
}

try {
    main();
} catch (e) {
    console.error(`fizz-sync: unexpected error: ${e.stack || e.message}`);
    process.exit(3);
}
