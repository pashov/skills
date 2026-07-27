#!/usr/bin/env node
/**
 * estimate_cost.js
 *
 * Prints and writes a rough cost estimate for a Fizz run based on the
 * selected entry points and the subagent model tier. Numbers are ballpark —
 * actual cost varies with handler complexity, rerun cycles, coverage churn,
 * and orchestrator context size.
 *
 * Usage:
 *   node estimate_cost.js <PROJECT_ROOT> [--meta-dir <dir>] [--model <sonnet|opus>] [--mode <guided|automatic>] [--output <path>]
 *
 * Defaults:
 *   --meta-dir   fizz_data
 *   --model      sonnet
 *   --mode       automatic
 *   --output     <meta-dir>/cost-estimate.md
 */

const fs = require('fs');
const path = require('path');

// ――― Pricing (USD per million tokens, Anthropic list price) ―――
const PRICING = {
    sonnet: { input: 3, output: 15 },
    opus: { input: 15, output: 75 },
};

// ――― Per-stage baseline token usage (thousands, medium codebase = 1.0x) ―――
// Derived from observed Fizz runs in fizz-workspace/.
const STAGES = [
    { name: 'Protocol Analyzer (conditional)',  count: 1, in_k: 50,  out_k: 8,  note: 'skipped when x-ray output is usable' },
    { name: 'Discovery agents',                 count: 5, in_k: 80,  out_k: 12, note: 'read all sources + handlers' },
    { name: 'Synthesizer',                      count: 1, in_k: 50,  out_k: 12, note: 'merges 5 discovery outputs' },
    { name: 'Implementers',                     count: 2, in_k: 60,  out_k: 15, note: 'edit Base / Snapshots / Properties / handlers' },
    { name: 'Report Writer',                    count: 1, in_k: 30,  out_k: 8,  note: 'synthesizes final report' },
    { name: 'Orchestrator overhead',            count: 1, in_k: 250, out_k: 40, note: 'parent agent across all steps' },
];

// ――― Argument parsing ―――

const args = process.argv.slice(2);
if (args.length === 0 || args[0] === '--help') {
    console.log('Usage: node estimate_cost.js <PROJECT_ROOT> [--meta-dir <dir>] [--model <sonnet|opus>] [--mode <guided|automatic>] [--output <path>]');
    process.exit(0);
}

const projectRoot = path.resolve(args[0]);
let metaRelDir = 'fizz_data';
let model = 'sonnet';
let mode = 'automatic';
let outputPath = '';

for (let i = 1; i < args.length; i++) {
    if (args[i] === '--meta-dir' && args[i + 1]) { metaRelDir = args[++i]; }
    else if (args[i] === '--model' && args[i + 1]) { model = args[++i].toLowerCase(); }
    else if (args[i] === '--mode' && args[i + 1]) { mode = args[++i].toLowerCase(); }
    else if (args[i] === '--output' && args[i + 1]) { outputPath = path.resolve(args[++i]); }
}

if (!PRICING[model]) {
    console.error(`Unknown --model: ${model}. Expected 'sonnet' or 'opus'.`);
    process.exit(1);
}

const metaDir = path.join(projectRoot, metaRelDir);
const selectionPath = path.join(metaDir, 'entry-point-selection.json');
if (!outputPath) {
    outputPath = path.join(metaDir, 'cost-estimate.md');
}

// ――― Read selection ―――

let contractCount = 0;
let functionCount = 0;
if (fs.existsSync(selectionPath)) {
    try {
        const selection = JSON.parse(fs.readFileSync(selectionPath, 'utf8'));
        contractCount = selection.length;
        for (const c of selection) functionCount += (c.functions || []).length;
    } catch (e) {
        console.error(`Failed to parse ${selectionPath}: ${e.message}`);
        process.exit(1);
    }
} else {
    console.error(`entry-point-selection.json not found at ${selectionPath} — producing a generic estimate with no scaling.`);
}

// ――― Size bucket ―――

function sizeBucket(f) {
    if (f < 20) return { label: 'small',  scale: 0.7 };
    if (f < 50) return { label: 'medium', scale: 1.0 };
    if (f < 100) return { label: 'large', scale: 1.4 };
    return              { label: 'xl',     scale: 1.8 };
}
const bucket = sizeBucket(functionCount);
const scale = bucket.scale;

// ――― Compute per-stage and totals ―――

const price = PRICING[model];
let totalInK = 0;
let totalOutK = 0;
const rows = STAGES.map(s => {
    const inK = s.count * s.in_k * scale;
    const outK = s.count * s.out_k * scale;
    totalInK += inK;
    totalOutK += outK;
    const costUsd = (inK * price.input + outK * price.output) / 1000;
    return { ...s, inK, outK, costUsd };
});
const totalUsd = (totalInK * price.input + totalOutK * price.output) / 1000;
const lowUsd = totalUsd * 0.7;
const highUsd = totalUsd * 1.5;

// ――― Format output ―――

function fmtK(k) { return `${k.toFixed(1).replace(/\.0$/, '')}k`; }
function fmtUsd(v) { return `$${v.toFixed(2)}`; }

function pad(s, n) { return String(s).padEnd(n); }
function padL(s, n) { return String(s).padStart(n); }

const header = `| Stage                              | Count | Input    | Output  | Cost     |`;
const sep    = `|------------------------------------|-------|----------|---------|----------|`;
const bodyLines = rows.map(r => (
    `| ${pad(r.name, 34)} | ${padL(r.count, 5)} | ${padL(fmtK(r.inK), 8)} | ${padL(fmtK(r.outK), 7)} | ${padL(fmtUsd(r.costUsd), 8)} |`
));
const totalLine = `| ${pad('TOTAL', 34)} | ${padL('', 5)} | ${padL(fmtK(totalInK), 8)} | ${padL(fmtK(totalOutK), 7)} | ${padL(fmtUsd(totalUsd), 8)} |`;

const md = [
    `# Cost Estimate`,
    ``,
    `Model: **${model}** (${fmtUsd(price.input)}/M input, ${fmtUsd(price.output)}/M output)`,
    `Mode: **${mode}**`,
    `Selected contracts: **${contractCount}**`,
    `Selected functions: **${functionCount}** — scale ${scale}x (${bucket.label})`,
    ``,
    header,
    sep,
    ...bodyLines,
    totalLine,
    ``,
    `**Estimated total: ${fmtUsd(totalUsd)}** — expected range ${fmtUsd(lowUsd)} – ${fmtUsd(highUsd)}`,
    ``,
    `These numbers are Anthropic list-price estimates for the subagents and a rough orchestrator overhead share. Actual cost varies with: coverage-iteration cycles (Step 8), re-runs after compile errors, handler complexity, whether x-ray skipped the Protocol Analyzer, and prompt-cache hit rate. Treat this as a ballpark, not a commitment.`,
    ``,
].join('\n');

// ――― Write file + print ―――

fs.mkdirSync(path.dirname(outputPath), { recursive: true });
fs.writeFileSync(outputPath, md);

process.stdout.write(md);
process.stdout.write(`\nWrote: ${outputPath}\n`);
