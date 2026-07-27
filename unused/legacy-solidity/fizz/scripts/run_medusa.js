#!/usr/bin/env node
/**
 * run_medusa.js
 *
 *  * Runs `medusa fuzz` against the generated FuzzTester harness, mirroring output to
 * stdout/stderr, a log file, and a temporary local browser log viewer. Medusa
 * runs until it reaches its configured `testLimit`, hits a failure condition
 * configured in `medusa.json`, reaches the wrapper timeout, or is interrupted
 * by the user. When `--coverage-mode` is enabled, it also stops once the `branches hit`
 * metric has plateaued for a configurable number of consecutive status lines, and prints
 * the coverage report path when the run finishes (pass `--logs` to also open it in the browser).
 *
 * Usage:
 *   node run_medusa.js <PROJECT_ROOT> [--meta-dir <path>] [--min-seconds <n>] [--max-stagnant-lines <n>] [--grace-seconds <n>] [--timeout <n>] [--log-file <path>] [--coverage-mode] [--logs]
 *
 * Defaults:
 *   --meta-dir            fizz_data
 *   --min-seconds         60
 *   --max-stagnant-lines  5
 *   --grace-seconds       5
 *   --timeout             300
 *   --coverage-mode       false (plateau detection disabled; coverage report path printed but never auto-opened)
 *   --logs                false (live log viewer + coverage report print their URLs, but the browser is not auto-opened)
 *   --log-file            <PROJECT_ROOT>/<meta-dir>/corpus_medusa/medusa-run.log
 */

const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { startLogViewer } = require('./lib/log-viewer');

const args = process.argv.slice(2);
if (args.length === 0 || args[0] === '--help') {
    console.log('Usage: node run_medusa.js <PROJECT_ROOT> [--meta-dir <dir>] [--min-seconds <n>] [--max-stagnant-lines <n>] [--grace-seconds <n>] [--timeout <n>] [--log-file <path>] [--coverage-mode] [--logs]');
    process.exit(0);
}

const projectRoot = path.resolve(args[0]);
let metaRelDir = 'fizz_data';
let minSeconds = 60;
let maxStagnantLines = 5;
let graceSeconds = 5;
let timeoutSeconds = 300;
let logFilePath = null;
let coverageMode = false;
let openLogs = false;

for (let i = 1; i < args.length; i++) {
    if (args[i] === '--meta-dir' && args[i + 1]) {
        metaRelDir = args[++i];
    } else if (args[i] === '--min-seconds' && args[i + 1]) {
        minSeconds = Number(args[++i]);
    } else if (args[i] === '--max-stagnant-lines' && args[i + 1]) {
        maxStagnantLines = Number(args[++i]);
    } else if (args[i] === '--grace-seconds' && args[i + 1]) {
        graceSeconds = Number(args[++i]);
    } else if (args[i] === '--timeout' && args[i + 1]) {
        timeoutSeconds = Number(args[++i]);
    } else if (args[i] === '--log-file' && args[i + 1]) {
        logFilePath = args[++i];
    } else if (args[i] === '--coverage-mode') {
        coverageMode = true;
    } else if (args[i] === '--logs') {
        openLogs = true;
    }
}

if (!logFilePath) {
    logFilePath = path.join(projectRoot, metaRelDir, 'corpus_medusa', 'medusa-run.log');
}

const logDir = path.dirname(logFilePath);
fs.mkdirSync(logDir, { recursive: true });
const logStream = fs.createWriteStream(logFilePath, { flags: 'w' });

const TAG = coverageMode ? '[plateau]' : '[medusa]';

if (!Number.isFinite(minSeconds) || minSeconds < 0) {
    console.error(`Invalid --min-seconds value: ${minSeconds}`);
    process.exit(1);
}
if (!Number.isInteger(maxStagnantLines) || maxStagnantLines < 1) {
    console.error(`Invalid --max-stagnant-lines value: ${maxStagnantLines}`);
    process.exit(1);
}
if (!Number.isFinite(graceSeconds) || graceSeconds < 0) {
    console.error(`Invalid --grace-seconds value: ${graceSeconds}`);
    process.exit(1);
}
if (!Number.isFinite(timeoutSeconds) || timeoutSeconds < 1) {
    console.error(`Invalid --timeout value: ${timeoutSeconds}`);
    process.exit(1);
}

// Start log viewer and initialize
startLogViewer('Medusa', '#22c55e', { open: openLogs }).then(({ viewerState, appendViewerText, writeStdout, writeStderr, viewerURL }) => {
    writeStderr(`${TAG} Medusa logs: ${logFilePath}\n`);
    writeStderr(`${TAG} Live log viewer: ${viewerURL}${openLogs ? ' (opening in browser)' : ' (pass --logs to open it in the browser)'}\n`);
    if (!coverageMode) {
        writeStderr(`${TAG} Plateau detection disabled - running until timeout (${timeoutSeconds}s) or testLimit.\n`);
    }
    writeStderr('\n');

    function printCoverageSummary(lcovPath, rootDir) {
        const data = fs.readFileSync(lcovPath, 'utf8');
        const parts = data.split('end_of_record');
        const results = [];

        for (const part of parts) {
            const lines = part.trim().split('\n');
            const sfLine = lines.find(l => l.startsWith('SF:'));
            if (!sfLine) continue;

            const fname = sfLine.slice(3).trim();
            const rel = path.relative(rootDir, fname);
            if (!rel.startsWith('src' + path.sep) || rel.includes('node_modules')) continue;

            const daLines = lines.filter(l => l.startsWith('DA:'));
            if (daLines.length === 0) continue;

            const lf = daLines.length;
            const lh = daLines.filter(l => parseInt(l.split(',')[1], 10) > 0).length;
            const pct = Math.floor(lh * 100 / lf);
            results.push({ name: path.basename(fname), pct, lh, lf });
        }

        if (results.length === 0) return;

        results.sort((a, b) => a.pct - b.pct);
        const maxName = Math.max(...results.map(r => r.name.length));

        let target = 80;
        const coverageTargetsPath = path.join(rootDir, metaRelDir, 'coverage-targets.md');
        if (fs.existsSync(coverageTargetsPath)) {
            const ctContent = fs.readFileSync(coverageTargetsPath, 'utf8');
            if (ctContent.includes('ir-no-opt') || ctContent.includes('optimizer_runs=0')) {
                target = 70;
            } else if (ctContent.includes('deflated ~15-20%') || ctContent.includes('FUZZ_PROFILE=default')) {
                target = 65;
            }
        }

        writeStderr(`\n${TAG} Coverage summary (src/ contracts):\n`);
        for (const { name, pct, lh, lf } of results) {
            const flag = pct < target ? ' !' : '  ';
            writeStderr(`${TAG}${flag} ${String(pct).padStart(3)}%  ${name.padEnd(maxName)}  (${lh}/${lf} lines)\n`);
        }

        const mainContracts = results.filter(r => !r.name.includes('Lib') && !r.name.includes('Mock'));
        const allMet = mainContracts.every(r => r.pct >= target);
        if (allMet) {
            writeStderr(`${TAG} Target met: all main contracts >= ${target}%\n\n`);
        } else {
            const failing = mainContracts.filter(r => r.pct < target).map(r => `${r.name} (${r.pct}%)`).join(', ');
            writeStderr(`${TAG} Target NOT met (<${target}%): ${failing}\n\n`);
        }
    }

    let bestBranchesHit = -1;
    let stagnantLines = 0;
    let sawBranchesMetric = false;
    let stopRequestedByPlateau = false;
    let stopRequestedByUser = false;
    let graceTimer = null;
    let stdoutBuffer = '';
    let stderrBuffer = '';
    let childExited = false;

    function parseStatusLine(line) {
        if (!coverageMode) return;

        const elapsedMatch = line.match(/elapsed:\s*([\d,]+)s/i);
        const branchesMatch = line.match(/branches hit:\s*([\d,]+)/i);

        if (!elapsedMatch || !branchesMatch) return;

        sawBranchesMetric = true;

        const elapsedSeconds = Number(elapsedMatch[1].replace(/,/g, ''));
        const branchesHit = Number(branchesMatch[1].replace(/,/g, ''));
        if (!Number.isFinite(elapsedSeconds) || !Number.isFinite(branchesHit)) return;

        if (branchesHit > bestBranchesHit) {
            bestBranchesHit = branchesHit;
            stagnantLines = 0;
            return;
        }

        if (elapsedSeconds < minSeconds) return;

        stagnantLines += 1;
        if (stagnantLines < maxStagnantLines) return;

        requestPlateauStop(elapsedSeconds, branchesHit);
    }

    function flushBuffer(buffer, chunk, writer) {
        const text = buffer + chunk.toString();
        const lines = text.split(/\r?\n|\r/);
        const trailing = lines.pop() || '';

        for (const line of lines) {
            writer.write(`${line}\n`);
            logStream.write(`${line}\n`);
            appendViewerText(`${line}\n`);
            parseStatusLine(line);
        }

        return trailing;
    }

    function requestPlateauStop(elapsedSeconds, branchesHit) {
        if (stopRequestedByPlateau || stopRequestedByUser) return;

        stopRequestedByPlateau = true;
        writeStderr(
            `\n${TAG} No branch-hit increase for ${maxStagnantLines} consecutive status lines after ${elapsedSeconds}s. ` +
            `Stopping Medusa at branches hit = ${branchesHit}.\n`
        );

        child.kill('SIGINT');
        graceTimer = setTimeout(() => {
            if (!childExited) {
                writeStderr(`${TAG} Medusa did not exit within ${graceSeconds}s, sending SIGKILL.\n`);
                child.kill('SIGKILL');
            }
        }, graceSeconds * 1000);
    }

    const childEnv = { ...process.env };
    if (!childEnv.FOUNDRY_PROFILE) {
        const foundryToml = path.join(projectRoot, 'foundry.toml');
        if (fs.existsSync(foundryToml)) {
            const tomlContent = fs.readFileSync(foundryToml, 'utf8');
            if (/^\[profile\.fuzz\]/m.test(tomlContent)) {
                childEnv.FOUNDRY_PROFILE = 'fuzz';
                writeStderr('[plateau] Using FOUNDRY_PROFILE=fuzz (via-ir handling)\n');
            }
        }
    }

    const child = spawn('medusa', ['fuzz', '--timeout', String(timeoutSeconds)], {
        cwd: projectRoot,
        env: childEnv,
        stdio: ['ignore', 'pipe', 'pipe'],
    });

    child.stdout.on('data', (chunk) => {
        stdoutBuffer = flushBuffer(stdoutBuffer, chunk, process.stdout);
    });

    child.stderr.on('data', (chunk) => {
        stderrBuffer = flushBuffer(stderrBuffer, chunk, process.stderr);
    });

    child.on('error', (err) => {
        if (err.code === 'ENOENT') {
            console.error('Failed to start `medusa fuzz`: medusa was not found in PATH.');
        } else {
            console.error(`Failed to start \`medusa fuzz\`: ${err.message}`);
        }
        process.exit(1);
    });

    function handleSignal(signal) {
        stopRequestedByUser = true;
        child.kill(signal);
    }

    process.on('SIGINT', () => handleSignal('SIGINT'));
    process.on('SIGTERM', () => handleSignal('SIGTERM'));

    child.on('close', (code, signal) => {
        childExited = true;

        if (stdoutBuffer.length > 0) {
            writeStdout(stdoutBuffer);
            logStream.write(stdoutBuffer);
            parseStatusLine(stdoutBuffer);
        }
        if (stderrBuffer.length > 0) {
            writeStderr(stderrBuffer);
            logStream.write(stderrBuffer);
            parseStatusLine(stderrBuffer);
        }

        logStream.end();

        if (graceTimer) {
            clearTimeout(graceTimer);
        }

        if (coverageMode && !sawBranchesMetric) {
            writeStderr(`${TAG} No \`branches hit\` progress lines were observed; Medusa was not auto-stopped by plateau detection.\n`);
        }

        const lcovPath = path.join(projectRoot, metaRelDir, 'corpus_medusa', 'coverage', 'lcov.info');
        if (fs.existsSync(lcovPath)) {
            printCoverageSummary(lcovPath, projectRoot);
        }

        const coverageReport = path.join(projectRoot, metaRelDir, 'corpus_medusa', 'coverage', 'coverage_report.html');
        if (fs.existsSync(coverageReport)) {
            writeStderr(`${TAG} Coverage report: file://${coverageReport}\n`);
            if (coverageMode && openLogs) {
                const { execFile } = require('child_process');
                const opener = process.platform === 'darwin' ? 'open' : process.platform === 'win32' ? 'start' : 'xdg-open';
                execFile(opener, [coverageReport], (err) => {
                    if (err) {
                        writeStderr(`${TAG} Could not open browser automatically (${opener} failed): ${err.message}\n`);
                    }
                });
            }
        }

        viewerState.closed = true;

        if (stopRequestedByPlateau) {
            process.exit(0);
        }

        if (signal) {
            const signalNumbers = { SIGINT: 2, SIGTERM: 15, SIGKILL: 9 };
            process.exit(128 + (signalNumbers[signal] || 1));
        }

        process.exit(code || 0);
    });
});
