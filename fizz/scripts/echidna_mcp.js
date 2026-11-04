#!/usr/bin/env node
/**
 * echidna_mcp.js
 *
 * Calls one tool on a running Echidna campaign's MCP server and prints the
 * answer. Echidna >= 2.4 serves MCP at http://127.0.0.1:<port>/mcp when it is
 * started with `--server <port>` (run_echidna.js passes it through). This script
 * lets an agent use that server from its shell, without registering an MCP
 * server in its own client.
 *
 * Usage:
 *   node echidna_mcp.js <tool> [--port <port> | --url <url>] [--<arg> <value> ...]
 *   node echidna_mcp.js tools [--port <port>]
 *
 * Examples:
 *   node echidna_mcp.js status --port 8080
 *   node echidna_mcp.js show_coverage --port 8080 --contract Vault
 *   node echidna_mcp.js inject_fuzz_transactions --port 8080 --transactions "handler_deposit(?); handler_withdraw(?, 1)"
 *   node echidna_mcp.js execute_sequence --port 8080 --transactions "handler_deposit(0, 100)" --trace
 *   node echidna_mcp.js sample --port 8080 --function handler_withdraw
 *
 * Every `--<arg> <value>` pair becomes a tool argument; a flag with no value
 * (e.g. `--trace`) is passed as true. `--port` defaults to $ECHIDNA_MCP_PORT,
 * then 8080.
 *
 * Exit codes: 0 the tool answered, 1 the tool reported an error (its message is
 * printed), 2 no campaign is listening or the server answered something that is
 * not MCP.
 *
 * Requires Node >= 18 (global fetch). No dependencies.
 */

const PROTOCOL_VERSION = '2025-06-18';

const args = process.argv.slice(2);
if (args.length === 0 || args[0] === '--help') {
    console.log('Usage: node echidna_mcp.js <tool> [--port <port> | --url <url>] [--<arg> <value> ...]');
    console.log('       node echidna_mcp.js tools [--port <port>]');
    process.exit(0);
}

const tool = args[0];
let url = null;
let port = process.env.ECHIDNA_MCP_PORT || '8080';
const toolArgs = {};

for (let i = 1; i < args.length; i++) {
    const a = args[i];
    if (!a.startsWith('--')) {
        console.error(`Unexpected argument: ${a}`);
        process.exit(2);
    }
    const key = a.slice(2);
    const next = args[i + 1];
    const hasValue = next !== undefined && !next.startsWith('--');
    if (key === 'port' && hasValue) {
        port = args[++i];
    } else if (key === 'url' && hasValue) {
        url = args[++i];
    } else if (hasValue) {
        toolArgs[key] = args[++i];
    } else {
        toolArgs[key] = true;
    }
}
if (!url) url = `http://127.0.0.1:${port}/mcp`;

// The server answers with plain JSON, but a Streamable HTTP server may also
// answer with a one-event SSE stream; accept both.
async function rpc(method, params, id) {
    const body = { jsonrpc: '2.0', method };
    if (id !== undefined) body.id = id;
    if (params !== undefined) body.params = params;
    const headers = {
        'Content-Type': 'application/json',
        Accept: 'application/json, text/event-stream',
    };
    if (method !== 'initialize') headers['MCP-Protocol-Version'] = PROTOCOL_VERSION;

    const res = await fetch(url, { method: 'POST', headers, body: JSON.stringify(body) });
    if (id === undefined) return null;
    if (!res.ok) throw new Error(`HTTP ${res.status} from ${url}`);
    const text = await res.text();
    if ((res.headers.get('content-type') || '').includes('text/event-stream')) {
        const data = text.split(/\r?\n/).filter((l) => l.startsWith('data:')).map((l) => l.slice(5).trim());
        return JSON.parse(data[data.length - 1]);
    }
    return JSON.parse(text);
}

async function main() {
    let reply;
    try {
        const init = await rpc('initialize', {
            protocolVersion: PROTOCOL_VERSION,
            capabilities: {},
            clientInfo: { name: 'fizz-echidna-mcp', version: '0' },
        }, 0);
        if (!init || !init.result) throw new Error(`unexpected initialize answer: ${JSON.stringify(init)}`);
        await rpc('notifications/initialized');

        if (tool === 'tools') {
            reply = await rpc('tools/list', {}, 1);
            for (const t of reply.result.tools) {
                console.log(`${t.name}: ${t.description}`);
            }
            process.exit(0);
        }
        reply = await rpc('tools/call', { name: tool, arguments: toolArgs }, 1);
    } catch (err) {
        const cause = err.cause && err.cause.code === 'ECONNREFUSED'
            ? `no Echidna campaign is listening at ${url} (was it started with --server?)`
            : err.message;
        console.error(`echidna_mcp: ${cause}`);
        process.exit(2);
    }

    if (reply.error) {
        console.error(`echidna_mcp: ${tool}: ${reply.error.message || JSON.stringify(reply.error)}`);
        process.exit(1);
    }
    const text = (reply.result.content || []).map((p) => p.text || '').join('');
    if (reply.result.isError) {
        console.error(`echidna_mcp: ${tool}: ${text}`);
        process.exit(1);
    }
    console.log(text);
}

main();
