#!/usr/bin/env node
/**
 * run_echidna.js
 *
 * Runs `echidna` against the generated FuzzTester harness, mirroring output to
 * stdout/stderr, a log file, and a temporary local browser log viewer. Echidna
 * runs until it reaches its configured `testLimit`, hits a failure condition
 * configured in `echidna.yaml`, reaches the wrapper timeout, or is interrupted
 * by the user.
 *
 * Usage:
 *   node run_echidna.js <PROJECT_ROOT> [--meta-dir <path>] [--config <path>] [--contract <name>] [--log-file <path>] [--timeout <seconds>] [--logs]
 *
 * Defaults:
 *   --meta-dir   fizz_data
 *   --config     <PROJECT_ROOT>/echidna.yaml
 *   --contract   FuzzTester
 *   --log-file   <PROJECT_ROOT>/<meta-dir>/corpus_echidna/echidna-run.log
 *   --timeout    600
 *   --logs       false (live log viewer runs and prints its URL, but the browser is not auto-opened)
 */

const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { startLogViewer } = require('./lib/log-viewer');

const args = process.argv.slice(2);
if (args.length === 0 || args[0] === '--help') {
    console.log('Usage: node run_echidna.js <PROJECT_ROOT> [--meta-dir <path>] [--config <path>] [--contract <name>] [--log-file <path>] [--timeout <seconds>] [--logs]');
    process.exit(0);
}

const projectRoot = path.resolve(args[0]);
let metaRelDir = 'fizz_data';
let configPath = null;
let contractName = 'FuzzTester';
let logFilePath = null;
let timeoutSeconds = 600;
let openLogs = false;

for (let i = 1; i < args.length; i++) {
    if (args[i] === '--meta-dir' && args[i + 1]) {
        metaRelDir = args[++i];
    } else if (args[i] === '--config' && args[i + 1]) {
        configPath = args[++i];
    } else if (args[i] === '--contract' && args[i + 1]) {
        contractName = args[++i];
    } else if (args[i] === '--log-file' && args[i + 1]) {
        logFilePath = args[++i];
    } else if (args[i] === '--timeout' && args[i + 1]) {
        timeoutSeconds = Number(args[++i]);
    } else if (args[i] === '--logs') {
        openLogs = true;
    }
}

if (!configPath) {
    configPath = path.join(projectRoot, 'echidna.yaml');
} else {
    configPath = path.resolve(configPath);
}

if (!logFilePath) {
    logFilePath = path.join(projectRoot, metaRelDir, 'corpus_echidna', 'echidna-run.log');
}

if (!fs.existsSync(configPath)) {
    console.error(`Echidna config not found: ${configPath}`);
    process.exit(1);
}
if (timeoutSeconds !== null && (!Number.isFinite(timeoutSeconds) || timeoutSeconds < 1)) {
    console.error(`Invalid --timeout value: ${timeoutSeconds}`);
    process.exit(1);
}

const logDir = path.dirname(logFilePath);
fs.mkdirSync(logDir, { recursive: true });
const logStream = fs.createWriteStream(logFilePath, { flags: 'w' });

const TAG = '[echidna]';

// Start log viewer and initialize
startLogViewer('Echidna', '#a855f7', { open: openLogs }).then(({ viewerState, appendViewerText, writeStdout, writeStderr, viewerURL }) => {
    writeStderr(`${TAG} Echidna logs: ${logFilePath}\n`);
    writeStderr(`${TAG} Live log viewer: ${viewerURL}${openLogs ? ' (opening in browser)' : ' (pass --logs to open it in the browser)'}\n`);
    writeStderr(`${TAG} Running until Echidna exits on its own (for example after testLimit or a configured stop condition).\n`);
    if (timeoutSeconds !== null) {
        writeStderr(`${TAG} Wrapper timeout enabled: ${timeoutSeconds}s\n`);
    }
    writeStderr('\n');

    // Inherit FOUNDRY_PROFILE=fuzz when the project has a dedicated fuzz profile.
    const childEnv = { ...process.env };
    if (!childEnv.FOUNDRY_PROFILE) {
        const foundryToml = path.join(projectRoot, 'foundry.toml');
        if (fs.existsSync(foundryToml)) {
            const tomlContent = fs.readFileSync(foundryToml, 'utf8');
            if (/^\[profile\.fuzz\]/m.test(tomlContent)) {
                childEnv.FOUNDRY_PROFILE = 'fuzz';
                writeStderr(`${TAG} Using FOUNDRY_PROFILE=fuzz (via-ir handling)\n`);
            }
        }
    }

    let stdoutBuffer = '';
    let stderrBuffer = '';
    let timeoutHandle = null;
    let timedOut = false;

    function flushBuffer(buffer, chunk, writer) {
        const text = buffer + chunk.toString();
        const lines = text.split(/\r?\n|\r/);
        const trailing = lines.pop() || '';

        for (const line of lines) {
            writer.write(`${line}\n`);
            logStream.write(`${line}\n`);
            appendViewerText(`${line}\n`);
        }

        return trailing;
    }

    const child = spawn('echidna', ['.', '--contract', contractName, '--config', configPath], {
        cwd: projectRoot,
        env: childEnv,
        stdio: ['ignore', 'pipe', 'pipe'],
    });

    if (timeoutSeconds !== null) {
        timeoutHandle = setTimeout(() => {
            timedOut = true;
            writeStderr(`\n${TAG} Reached wrapper timeout after ${timeoutSeconds}s, stopping Echidna.\n`);
            child.kill('SIGINT');
        }, timeoutSeconds * 1000);
    }

    child.stdout.on('data', (chunk) => {
        stdoutBuffer = flushBuffer(stdoutBuffer, chunk, process.stdout);
    });

    child.stderr.on('data', (chunk) => {
        stderrBuffer = flushBuffer(stderrBuffer, chunk, process.stderr);
    });

    child.on('error', (err) => {
        if (err.code === 'ENOENT') {
            console.error('Failed to start `echidna`: echidna was not found in PATH.');
        } else {
            console.error(`Failed to start \`echidna\`: ${err.message}`);
        }
        process.exit(1);
    });

    function forwardSignal(signal) {
        child.kill(signal);
    }

    process.on('SIGINT', () => forwardSignal('SIGINT'));
    process.on('SIGTERM', () => forwardSignal('SIGTERM'));

    child.on('close', (code, signal) => {
        if (timeoutHandle) {
            clearTimeout(timeoutHandle);
        }

        if (stdoutBuffer.length > 0) {
            writeStdout(stdoutBuffer);
            logStream.write(stdoutBuffer);
        }
        if (stderrBuffer.length > 0) {
            writeStderr(stderrBuffer);
            logStream.write(stderrBuffer);
        }

        logStream.end();

        viewerState.closed = true;

        if (timedOut) {
            process.exit(0);
        }

        if (signal) {
            const signalNumbers = { SIGINT: 2, SIGTERM: 15, SIGKILL: 9 };
            process.exit(128 + (signalNumbers[signal] || 1));
        }

        process.exit(code || 0);
    });
});
