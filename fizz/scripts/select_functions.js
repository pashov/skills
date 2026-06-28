#!/usr/bin/env node
/**
 * select_functions.js
 *
 * Zero-dependency interactive contract/function selector.
 * Reads contracts.json from the fuzz suite metadata directory, spins up a
 * localhost HTTP server, opens a browser with a checkbox UI, and writes
 * entry-point-selection.json when the user confirms.
 *
 * Usage:
 *   node select_functions.js <PROJECT_ROOT> [--contracts <path>] [--selection <path>] [--preselect <path>] [--meta-dir <path>]
 *
 * Defaults:
 *   --contracts    <meta-dir>/contracts.json
 *   --selection    optional entry-point-selection JSON used as the default checked state and save target
 *   --preselect    deprecated alias for --selection
 *   --meta-dir     fizz_data  (relative to project root)
 *   --fuzzing-dir  deprecated alias for --meta-dir
 *
 * Output:
 *   --selection path or <meta-dir>/entry-point-selection.json
 */

const fs = require('fs');
const path = require('path');
const http = require('http');
const { execSync } = require('child_process');

// ――――――――――――――――――――――――― Argument parsing ―――――――――――――――――――――――――

const args = process.argv.slice(2);
if (args.length === 0 || args[0] === '--help') {
    console.log('Usage: node select_functions.js <PROJECT_ROOT> [--contracts <path>] [--selection <path>] [--preselect <path>] [--meta-dir <dir>] [--auto]');
    process.exit(0);
}

const projectRoot = path.resolve(args[0]);
let contractsPath = '';
let selectionPath = '';
let metaRelDir = 'fizz_data';
let autoMode = false;

for (let i = 1; i < args.length; i++) {
    if (args[i] === '--contracts' && args[i + 1]) { contractsPath = path.resolve(args[++i]); }
    else if (args[i] === '--selection' && args[i + 1]) { selectionPath = path.resolve(args[++i]); }
    else if (args[i] === '--preselect' && args[i + 1]) { selectionPath = path.resolve(args[++i]); }
    else if (args[i] === '--meta-dir' && args[i + 1]) { metaRelDir = args[++i]; }
    else if (args[i] === '--fuzzing-dir' && args[i + 1]) { metaRelDir = args[++i]; }
    else if (args[i] === '--auto') { autoMode = true; }
}

const metaDir = path.join(projectRoot, metaRelDir);
if (!contractsPath) {
    contractsPath = path.join(metaDir, 'contracts.json');
}
if (!selectionPath) {
    selectionPath = path.join(metaDir, 'entry-point-selection.json');
}

// ――――――――――――――――――――――――― Read contracts ―――――――――――――――――――――――――

if (!fs.existsSync(contractsPath)) {
    console.error(`contracts.json not found: ${contractsPath}`);
    console.error('Run extract_abis.js first.');
    process.exit(1);
}

const contracts = JSON.parse(fs.readFileSync(contractsPath, 'utf8'));

if (contracts.length === 0) {
    console.error('No contracts found in contracts.json.');
    process.exit(1);
}

function contractKey(contract) {
    return `${contract.name}::${contract.sourcePath}`;
}

function functionKey(func) {
    const inputs = (func.inputs || []).map(input => `${input.type}:${input.name || ''}`).join(',');
    return `${func.name}(${inputs})`;
}

function cloneSelection(selection) {
    return JSON.parse(JSON.stringify(selection));
}

function buildSelectedMap(selectionContracts) {
    const selectedMap = new Map();

    for (const contract of selectionContracts || []) {
        const key = contractKey(contract);
        const functionSet = new Set((contract.functions || []).map(functionKey));
        selectedMap.set(key, {
            functions: functionSet,
            hasReceive: !!contract.hasReceive,
            hasFallback: !!contract.hasFallback,
        });
    }

    return selectedMap;
}

let defaultSelection = cloneSelection(contracts);
let defaultSelectionLabel = 'all functions from contracts.json';

if (fs.existsSync(selectionPath)) {
    defaultSelection = JSON.parse(fs.readFileSync(selectionPath, 'utf8'));
    defaultSelectionLabel = `initial selection from ${selectionPath}`;
}

const preselectedMap = buildSelectedMap(defaultSelection);

// ――――――――――――――――――――――――― HTML page ―――――――――――――――――――――――――

function buildHTML(contracts, serverURL, preselectedMap) {
    const contractsJSON = JSON.stringify(contracts);
    const preselectedJSON = JSON.stringify(
        Array.from(preselectedMap.entries()).map(([key, value]) => ({
            key,
            functions: Array.from(value.functions),
            hasReceive: value.hasReceive,
            hasFallback: value.hasFallback,
        }))
    );
    return /* html */ `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fizz — Select Functions</title>
<style>
  :root {
    --bg: #0d1117; --surface: #161b22; --border: #30363d;
    --text: #e6edf3; --text-dim: #8b949e; --accent: #58a6ff;
    --green: #3fb950; --red: #f85149; --orange: #d29922;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: var(--bg); color: var(--text);
    max-width: 720px; margin: 0 auto; padding: 24px 16px;
  }
  header { margin-bottom: 24px; }
  header h1 { font-size: 22px; font-weight: 600; margin-bottom: 4px; }
  header p { color: var(--text-dim); font-size: 14px; }

  .toolbar {
    display: flex; gap: 8px; align-items: center;
    margin-bottom: 16px; flex-wrap: wrap;
  }
  .toolbar input[type="text"] {
    flex: 1; min-width: 200px; padding: 6px 10px;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 6px; color: var(--text); font-size: 14px;
    outline: none;
  }
  .toolbar input[type="text"]:focus { border-color: var(--accent); }
  .toolbar button {
    padding: 6px 12px; border-radius: 6px; border: 1px solid var(--border);
    background: var(--surface); color: var(--text-dim); cursor: pointer;
    font-size: 13px;
  }
  .toolbar button:hover { color: var(--text); border-color: var(--accent); }

  .contract-group {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; margin-bottom: 12px; overflow: hidden;
  }
  .contract-header {
    display: flex; align-items: center; gap: 8px;
    padding: 10px 14px; cursor: pointer; user-select: none;
    border-bottom: 1px solid var(--border);
  }
  .contract-header:hover { background: rgba(88,166,255,0.04); }
  .contract-cb {
    accent-color: var(--accent); width: 16px; height: 16px; cursor: pointer;
    flex-shrink: 0;
  }
  .contract-header .arrow {
    color: var(--text-dim); font-size: 12px; transition: transform 0.15s;
    width: 16px; text-align: center;
  }
  .contract-header .arrow.collapsed { transform: rotate(-90deg); }
  .contract-header .name { font-weight: 600; font-size: 15px; }
  .contract-header .path { color: var(--text-dim); font-size: 12px; margin-left: auto; }
  .contract-header .count {
    font-size: 12px; padding: 2px 8px; border-radius: 10px;
    background: rgba(88,166,255,0.12); color: var(--accent);
  }

  .function-list { padding: 4px 0; }
  .function-list.hidden { display: none; }
  .function-item {
    display: flex; align-items: center; gap: 8px;
    padding: 6px 14px 6px 38px; cursor: pointer; font-size: 14px;
  }
  .function-item:hover { background: rgba(88,166,255,0.04); }
  .function-item.hidden-search { display: none; }
  .function-item input[type="checkbox"] {
    accent-color: var(--accent); width: 16px; height: 16px; cursor: pointer;
  }
  .function-item .sig { font-family: 'SFMono-Regular', Consolas, monospace; font-size: 13px; }
  .function-item .badge {
    font-size: 11px; padding: 1px 6px; border-radius: 4px; margin-left: auto;
  }
  .badge.payable { background: rgba(210,153,34,0.15); color: var(--orange); }
  .badge.receive { background: rgba(63,185,80,0.15); color: var(--green); }
  .badge.fallback { background: rgba(248,81,73,0.15); color: var(--red); }

  .confirm-bar {
    position: sticky; bottom: 0; padding: 16px 0;
    background: var(--bg); border-top: 1px solid var(--border);
    display: flex; align-items: center; gap: 12px; margin-top: 8px;
  }
  .confirm-bar .summary { color: var(--text-dim); font-size: 14px; }
  .confirm-bar button {
    margin-left: auto; padding: 8px 24px; border-radius: 6px;
    border: none; background: var(--accent); color: #fff;
    font-size: 14px; font-weight: 600; cursor: pointer;
  }
  .confirm-bar button:hover { background: #4c9aed; }
  .confirm-bar button:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
</head>
<body>

<header>
  <h1>Fizz — Select Functions</h1>
  <p>Choose which contracts and functions to include in the fuzzing harness.</p>
</header>

<div class="toolbar">
  <input type="text" id="search" placeholder="Filter functions..." autocomplete="off">
  <button onclick="selectAll()">Select All</button>
  <button onclick="deselectAll()">Deselect All</button>
</div>

<div id="contracts"></div>

<div class="confirm-bar">
  <span class="summary" id="summary"></span>
  <button id="confirmBtn" onclick="confirm()">Confirm Selection</button>
</div>

<script>
const contracts = ${contractsJSON};
const preselectedEntries = ${preselectedJSON};
const SERVER_URL = '${serverURL}';
const preselectedMap = new Map(preselectedEntries.map(entry => [entry.key, {
  functions: new Set(entry.functions),
  hasReceive: entry.hasReceive,
  hasFallback: entry.hasFallback,
}]));

function formatSig(func) {
  const params = func.inputs.map(i => i.type + ' ' + i.name).join(', ');
  return func.name + '(' + params + ')';
}

function contractKey(contract) {
  return contract.name + '::' + contract.sourcePath;
}

function functionKey(func) {
  const params = func.inputs.map(i => i.type + ':' + (i.name || '')).join(',');
  return func.name + '(' + params + ')';
}

function isContractSelected(contract) {
  return preselectedMap.has(contractKey(contract));
}

function isFunctionSelected(contract, func) {
  const selected = preselectedMap.get(contractKey(contract));
  return selected ? selected.functions.has(functionKey(func)) : false;
}

function isSpecialSelected(contract, kind) {
  const selected = preselectedMap.get(contractKey(contract));
  if (!selected) return false;
  if (kind === 'receive') return selected.hasReceive;
  if (kind === 'fallback') return selected.hasFallback;
  return false;
}

function buildFilteredSelection() {
  const filtered = [];
  contracts.forEach((contract, ci) => {
    const copy = Object.assign({}, contract);

    copy.functions = contract.functions.filter((_, fi) => {
      const cb = document.querySelector('input[data-ci="' + ci + '"][data-fi="' + fi + '"]');
      return cb && cb.checked;
    });

    const receiveCb = document.querySelector('input[data-ci="' + ci + '"][data-kind="receive"]');
    if (receiveCb && !receiveCb.checked) copy.hasReceive = false;

    const fallbackCb = document.querySelector('input[data-ci="' + ci + '"][data-kind="fallback"]');
    if (fallbackCb && !fallbackCb.checked) copy.hasFallback = false;

    if (copy.functions.length > 0 || copy.hasReceive || copy.hasFallback) {
      filtered.push(copy);
    }
  });

  return filtered;
}

function buildSelectionFingerprint(selection) {
  return JSON.stringify(selection.map(contract => ({
    name: contract.name,
    sourcePath: contract.sourcePath,
    functions: contract.functions.map(functionKey).sort(),
    hasReceive: !!contract.hasReceive,
    hasFallback: !!contract.hasFallback,
  })));
}

const defaultFingerprint = buildSelectionFingerprint(${JSON.stringify(defaultSelection)});

function render() {
  const container = document.getElementById('contracts');
  container.innerHTML = '';

  contracts.forEach((contract, ci) => {
    const group = document.createElement('div');
    group.className = 'contract-group';

    // Header
    const header = document.createElement('div');
    header.className = 'contract-header';

    const arrow = document.createElement('span');
    arrow.className = 'arrow';
    arrow.textContent = '▼';

    const name = document.createElement('span');
    name.className = 'name';
    name.textContent = contract.name;

    const pathSpan = document.createElement('span');
    pathSpan.className = 'path';
    pathSpan.textContent = contract.sourcePath;

    const contractCb = document.createElement('input');
    contractCb.type = 'checkbox';
    contractCb.checked = isContractSelected(contract);
    contractCb.className = 'contract-cb';
    contractCb.dataset.ci = ci;
    contractCb.addEventListener('change', () => {
      const cbs = group.querySelectorAll('.function-item input[type="checkbox"]');
      cbs.forEach(cb => { cb.checked = contractCb.checked; });
      updateSummary();
    });

    const count = document.createElement('span');
    count.className = 'count';
    count.dataset.ci = ci;

    header.append(contractCb, arrow, name, pathSpan, count);
    header.addEventListener('click', (e) => {
      if (e.target.tagName === 'INPUT') return;
      const list = group.querySelector('.function-list');
      list.classList.toggle('hidden');
      arrow.classList.toggle('collapsed');
    });
    group.appendChild(header);

    // Function list
    const list = document.createElement('div');
    list.className = 'function-list';

    contract.functions.forEach((func, fi) => {
      const item = document.createElement('div');
      item.className = 'function-item';
      item.dataset.search = (contract.name + '.' + func.name).toLowerCase();

      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = isFunctionSelected(contract, func);
      cb.dataset.ci = ci;
      cb.dataset.fi = fi;
      cb.dataset.kind = 'function';
      cb.addEventListener('change', updateSummary);

      const sig = document.createElement('span');
      sig.className = 'sig';
      sig.textContent = formatSig(func);

      item.append(cb, sig);

      if (func.stateMutability === 'payable') {
        const badge = document.createElement('span');
        badge.className = 'badge payable';
        badge.textContent = 'payable';
        item.appendChild(badge);
      }

      list.appendChild(item);
    });

    // receive / fallback
    if (contract.hasReceive) {
      const item = document.createElement('div');
      item.className = 'function-item';
      item.dataset.search = (contract.name + '.receive').toLowerCase();
      const cb = document.createElement('input');
      cb.type = 'checkbox'; cb.checked = isSpecialSelected(contract, 'receive');
      cb.dataset.ci = ci; cb.dataset.kind = 'receive';
      cb.addEventListener('change', updateSummary);
      const sig = document.createElement('span');
      sig.className = 'sig'; sig.textContent = 'receive()';
      const badge = document.createElement('span');
      badge.className = 'badge receive'; badge.textContent = 'receive';
      item.append(cb, sig, badge);
      list.appendChild(item);
    }

    if (contract.hasFallback) {
      const item = document.createElement('div');
      item.className = 'function-item';
      item.dataset.search = (contract.name + '.fallback').toLowerCase();
      const cb = document.createElement('input');
      cb.type = 'checkbox'; cb.checked = isSpecialSelected(contract, 'fallback');
      cb.dataset.ci = ci; cb.dataset.kind = 'fallback';
      cb.addEventListener('change', updateSummary);
      const sig = document.createElement('span');
      sig.className = 'sig'; sig.textContent = 'fallback()';
      const badge = document.createElement('span');
      badge.className = 'badge fallback'; badge.textContent = 'fallback';
      item.append(cb, sig, badge);
      list.appendChild(item);
    }

    group.appendChild(list);
    container.appendChild(group);
  });

  updateSummary();
}

function updateSummary() {
  const checkboxes = document.querySelectorAll('.function-item input[type="checkbox"]');
  let total = 0, checked = 0;
  const perContract = {};

  checkboxes.forEach(cb => {
    total++;
    if (cb.checked) {
      checked++;
      perContract[cb.dataset.ci] = (perContract[cb.dataset.ci] || 0) + 1;
    }
  });

  // Update per-contract counts and header checkbox state
  document.querySelectorAll('.count').forEach(el => {
    const ci = el.dataset.ci;
    const contractTotal = document.querySelectorAll('.function-item input[data-ci="' + ci + '"]').length;
    const contractChecked = perContract[ci] || 0;
    el.textContent = contractChecked + '/' + contractTotal;

    const contractCb = document.querySelector('.contract-cb[data-ci="' + ci + '"]');
    if (contractCb) {
      contractCb.checked = contractChecked === contractTotal;
      contractCb.indeterminate = contractChecked > 0 && contractChecked < contractTotal;
    }
  });

  document.getElementById('summary').textContent = checked + ' of ' + total + ' functions selected';
  document.getElementById('confirmBtn').disabled = checked === 0;
}

function selectAll() {
  document.querySelectorAll('.function-item input[type="checkbox"]').forEach(cb => { cb.checked = true; });
  updateSummary();
}

function deselectAll() {
  document.querySelectorAll('.function-item input[type="checkbox"]').forEach(cb => { cb.checked = false; });
  updateSummary();
}

document.getElementById('search').addEventListener('input', (e) => {
  const q = e.target.value.toLowerCase();
  document.querySelectorAll('.function-item').forEach(item => {
    item.classList.toggle('hidden-search', q && !item.dataset.search.includes(q));
  });
});

async function confirm() {
  const btn = document.getElementById('confirmBtn');
  btn.disabled = true;
  btn.textContent = 'Saving...';

  const filtered = buildFilteredSelection();
  const changedFromDefault = buildSelectionFingerprint(filtered) !== defaultFingerprint;

  try {
    const res = await fetch(SERVER_URL + '/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ selection: filtered, changedFromDefault }),
    });
    if (res.ok) {
      btn.textContent = 'Saved! You can close this tab.';
      btn.style.background = '#3fb950';
    } else {
      throw new Error(await res.text());
    }
  } catch (err) {
    btn.textContent = 'Error: ' + err.message;
    btn.style.background = '#f85149';
    setTimeout(() => {
      btn.textContent = 'Confirm Selection';
      btn.style.background = '';
      btn.disabled = false;
    }, 3000);
  }
}

render();
</script>
</body>
</html>`;
}

// ――――――――――――――――――――――――― Auto mode (no UI) ―――――――――――――――――――――――――

if (autoMode) {
    fs.mkdirSync(path.dirname(selectionPath), { recursive: true });
    fs.writeFileSync(selectionPath, JSON.stringify(defaultSelection, null, 2) + '\n');

    const funcCount = defaultSelection.reduce((s, c) =>
        s + c.functions.length + (c.hasReceive ? 1 : 0) + (c.hasFallback ? 1 : 0), 0);

    console.log(`\n[auto] Accepted ${defaultSelectionLabel}`);
    console.log(`[auto] ${defaultSelection.length} contract(s), ${funcCount} function(s)`);
    console.log(`  → ${selectionPath}`);
    process.exit(0);
}

// ――――――――――――――――――――――――― HTTP server ―――――――――――――――――――――――――

const outputPath = selectionPath;

const server = http.createServer((req, res) => {
    // CORS headers — needed when browser opens page on a different loopback variant
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') {
        res.writeHead(204);
        res.end();
        return;
    }

    console.log(`  ${req.method} ${req.url}`);

    if (req.method === 'GET' && (req.url === '/' || req.url === '/index.html')) {
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
        res.end(buildHTML(contracts, serverURL, preselectedMap));
        return;
    }

    if (req.method === 'POST' && req.url === '/save') {
        let body = '';
        req.on('data', chunk => { body += chunk; });
        req.on('end', () => {
            try {
                const payload = JSON.parse(body);
                const selection = Array.isArray(payload) ? payload : payload.selection;
                const changedFromDefault = !Array.isArray(payload) && !!payload.changedFromDefault;
                if (!Array.isArray(selection)) {
                    throw new Error('Expected `selection` to be an array');
                }
                fs.mkdirSync(path.dirname(outputPath), { recursive: true });
                fs.writeFileSync(outputPath, JSON.stringify(selection, null, 2) + '\n');

                const funcCount = selection.reduce((s, c) =>
                    s + c.functions.length + (c.hasReceive ? 1 : 0) + (c.hasFallback ? 1 : 0), 0);

                res.writeHead(200, { 'Content-Type': 'text/plain' });
                res.end('OK', () => {
                    // Shut down after the response is fully flushed
                    console.log(`\nSelection saved: ${selection.length} contract(s), ${funcCount} function(s)`);
                    console.log(`Selection changed from default: ${changedFromDefault ? 'yes' : 'no'}`);
                    console.log(`  → ${outputPath}`);
                    setTimeout(() => {
                        server.close();
                        process.exit(0);
                    }, 200);
                });
            } catch (err) {
                res.writeHead(400, { 'Content-Type': 'text/plain' });
                res.end('Invalid JSON: ' + err.message);
            }
        });
        return;
    }

    res.writeHead(404);
    res.end('Not found');
});

// Track the server URL so buildHTML can embed it
let serverURL = '';

// Listen on all interfaces (IPv4 + IPv6) to avoid loopback mismatch
server.listen(0, () => {
    const port = server.address().port;
    serverURL = `http://127.0.0.1:${port}`;
    console.log(`\nFunction selector running at ${serverURL}`);
    console.log(`Waiting for selection... (Ctrl+C to use ${defaultSelectionLabel})\n`);

    // Open browser
    const platform = process.platform;
    try {
        if (platform === 'darwin') execSync(`open "${serverURL}"`);
        else if (platform === 'win32') execSync(`start "" "${serverURL}"`);
        else execSync(`xdg-open "${serverURL}"`);
    } catch {
        console.log(`Could not open browser automatically. Open this URL: ${serverURL}`);
    }
});

// Graceful shutdown on Ctrl+C
process.on('SIGINT', () => {
    fs.mkdirSync(path.dirname(outputPath), { recursive: true });
    fs.writeFileSync(outputPath, JSON.stringify(defaultSelection, null, 2) + '\n');
    console.log(`\nSelection skipped — using ${defaultSelectionLabel}.`);
    console.log(`  → ${outputPath}`);
    server.close();
    process.exit(0);
});
