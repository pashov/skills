/**
 * log-viewer.js
 *
 * Shared browser-based log viewer for fuzzing wrappers (Medusa, Echidna).
 * Exports functions to start an HTTP server, render ANSI-colored output, and open the viewer in a browser.
 *
 * Usage:
 *   const { startLogViewer } = require('./lib/log-viewer');
 *   const { viewerState, appendViewerText, writeStdout, writeStderr } = startLogViewer('Medusa', '#22c55e');
 *   writeStderr('[medusa] Starting...\n');
 */

const http = require('http');
const { execFile } = require('child_process');

/**
 * Start an HTTP server serving a live log viewer.
 *
 * @param {string} title - Fuzzer name for the HTML title and header (e.g., "Medusa", "Echidna")
 * @param {string} accentColor - Hex color for the header radial gradient (e.g., "#22c55e" for green, "#a855f7" for purple)
 * @param {object} [options] - Optional settings.
 * @param {boolean} [options.open=false] - When true, also open the viewer URL in the default browser. Off by default.
 * @returns {object} { viewerState, appendViewerText, writeStdout, writeStderr, viewerURL }
 */
function startLogViewer(title, accentColor, { open = false } = {}) {
    const viewerState = {
        closed: false,
        content: '',
    };

    function appendViewerText(text) {
        viewerState.content += text;
    }

    function writeStdout(text) {
        process.stdout.write(text);
        appendViewerText(text);
    }

    function writeStderr(text) {
        process.stderr.write(text);
        appendViewerText(text);
    }

    return new Promise((resolve) => {
        const server = http.createServer((req, res) => {
            const requestURL = new URL(req.url, 'http://127.0.0.1');

            if (req.method === 'GET' && requestURL.pathname === '/') {
                res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
                res.end(buildLogViewerHTML(title, accentColor));
                return;
            }

            if (req.method === 'GET' && requestURL.pathname === '/log') {
                const offset = Number.parseInt(requestURL.searchParams.get('offset') || '0', 10);
                const safeOffset = Number.isFinite(offset) && offset >= 0 ? offset : 0;
                const normalizedOffset = Math.min(safeOffset, viewerState.content.length);
                const chunk = viewerState.content.slice(normalizedOffset);

                res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8' });
                res.end(JSON.stringify({
                    chunk,
                    nextOffset: normalizedOffset + chunk.length,
                    closed: viewerState.closed,
                }));
                return;
            }

            res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
            res.end('Not found');
        });

        server.listen(0, '127.0.0.1', () => {
            const address = server.address();
            const viewerURL = `http://127.0.0.1:${address.port}`;

            resolve({
                viewerState,
                appendViewerText,
                writeStdout,
                writeStderr,
                viewerURL,
            });

            // Attempt to open in default browser (non-blocking), only when requested via --logs.
            if (open) {
                const opener = process.platform === 'darwin' ? 'open' : process.platform === 'win32' ? 'start' : 'xdg-open';
                execFile(opener, [viewerURL], (err) => {
                    if (err) {
                        process.stderr.write(`Could not open browser automatically (${opener} failed): ${err.message}\n`);
                    }
                });
            }
        });
    });
}

/**
 * Build the HTML for the log viewer.
 *
 * @param {string} title - Fuzzer name (e.g., "Medusa", "Echidna")
 * @param {string} accentColor - Hex color for radial gradient and branding
 * @returns {string} HTML document
 */
function buildLogViewerHTML(title, accentColor) {
    // Convert hex to rgba for gradient (e.g., "#22c55e" -> "rgba(34, 197, 94, 0.14)")
    const hexToRgba = (hex, alpha = 0.14) => {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    };

    const gradientRgba = hexToRgba(accentColor);

    return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${title} Log Viewer</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #111827;
      --panel: #0b1220;
      --text: #e5e7eb;
      --muted: #94a3b8;
      --border: #1f2937;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background:
        radial-gradient(circle at top left, ${gradientRgba}, transparent 28rem),
        linear-gradient(180deg, #0f172a 0%, var(--bg) 45%, #020617 100%);
      color: var(--text);
      font: 14px/1.45 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
    }
    header {
      position: sticky;
      top: 0;
      padding: 14px 18px;
      border-bottom: 1px solid var(--border);
      background: rgba(11, 18, 32, 0.88);
      backdrop-filter: blur(10px);
    }
    h1 {
      margin: 0 0 4px;
      font-size: 14px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .status {
      color: var(--muted);
      font-size: 12px;
    }
    main { padding: 18px; }
    #log {
      margin: 0;
      min-height: calc(100vh - 84px);
      padding: 18px;
      white-space: pre-wrap;
      word-break: break-word;
      background: rgba(2, 6, 23, 0.78);
      border: 1px solid rgba(148, 163, 184, 0.16);
      border-radius: 14px;
      box-shadow: 0 24px 60px rgba(15, 23, 42, 0.45);
    }
  </style>
</head>
<body>
  <header>
    <h1>${title} Log Viewer</h1>
    <div id="status" class="status">Connecting...</div>
  </header>
  <main>
    <pre id="log" aria-live="polite"></pre>
  </main>
  <script>
    const logEl = document.getElementById('log');
    const statusEl = document.getElementById('status');
    let offset = 0;
    let closed = false;
    let pollTimer = null;
    const styleState = { bold: false, fg: null, bg: null };

    function cssColor(value) {
      if (value == null) return '';
      const base = {
        30: '#111827', 31: '#ef4444', 32: '#22c55e', 33: '#eab308',
        34: '#60a5fa', 35: '#f472b6', 36: '#22d3ee', 37: '#f8fafc',
        90: '#6b7280', 91: '#f87171', 92: '#4ade80', 93: '#fde047',
        94: '#93c5fd', 95: '#f9a8d4', 96: '#67e8f9', 97: '#ffffff'
      };
      if (typeof value === 'number') return base[value] || '';
      if (Array.isArray(value) && value[0] === 'rgb') {
        return 'rgb(' + value[1] + ', ' + value[2] + ', ' + value[3] + ')';
      }
      if (Array.isArray(value) && value[0] === 'idx') {
        const idx = value[1];
        if (idx < 16) {
          const map = [30,31,32,33,34,35,36,37,90,91,92,93,94,95,96,97];
          return base[map[idx]] || '';
        }
        if (idx >= 16 && idx <= 231) {
          const n = idx - 16;
          const r = Math.floor(n / 36);
          const g = Math.floor((n % 36) / 6);
          const b = n % 6;
          const conv = [0, 95, 135, 175, 215, 255];
          return 'rgb(' + conv[r] + ', ' + conv[g] + ', ' + conv[b] + ')';
        }
        if (idx >= 232 && idx <= 255) {
          const shade = 8 + (idx - 232) * 10;
          return 'rgb(' + shade + ', ' + shade + ', ' + shade + ')';
        }
      }
      return '';
    }

    function currentStyle() {
      const styles = [];
      if (styleState.bold) styles.push('font-weight: 700');
      const fg = cssColor(styleState.fg);
      const bg = cssColor(styleState.bg);
      if (fg) styles.push('color: ' + fg);
      if (bg) styles.push('background-color: ' + bg);
      return styles.join('; ');
    }

    function applySgr(params) {
      if (params.length === 0) params = [0];
      for (let i = 0; i < params.length; i++) {
        const code = params[i];
        if (code === 0) {
          styleState.bold = false;
          styleState.fg = null;
          styleState.bg = null;
        } else if (code === 1) {
          styleState.bold = true;
        } else if (code === 22) {
          styleState.bold = false;
        } else if ((code >= 30 && code <= 37) || (code >= 90 && code <= 97)) {
          styleState.fg = code;
        } else if (code === 39) {
          styleState.fg = null;
        } else if ((code >= 40 && code <= 47) || (code >= 100 && code <= 107)) {
          styleState.bg = code >= 100 ? code - 10 : code - 10;
        } else if (code === 49) {
          styleState.bg = null;
        } else if ((code === 38 || code === 48) && params[i + 1] === 5 && Number.isInteger(params[i + 2])) {
          if (code === 38) styleState.fg = ['idx', params[i + 2]];
          else styleState.bg = ['idx', params[i + 2]];
          i += 2;
        } else if ((code === 38 || code === 48) && params[i + 1] === 2 &&
          Number.isInteger(params[i + 2]) && Number.isInteger(params[i + 3]) && Number.isInteger(params[i + 4])) {
          const rgb = ['rgb', params[i + 2], params[i + 3], params[i + 4]];
          if (code === 38) styleState.fg = rgb;
          else styleState.bg = rgb;
          i += 4;
        }
      }
    }

    function appendAnsiText(text) {
      const stickToBottom = window.innerHeight + window.scrollY >= document.body.scrollHeight - 120;
      const fragment = document.createDocumentFragment();
      const pattern = /\\u001b\\[([0-9;]*)m/g;
      let lastIndex = 0;
      let match;

      while ((match = pattern.exec(text)) !== null) {
        if (match.index > lastIndex) {
          const span = document.createElement('span');
          span.textContent = text.slice(lastIndex, match.index);
          const style = currentStyle();
          if (style) span.style.cssText = style;
          fragment.appendChild(span);
        }

        const params = match[1]
          .split(';')
          .filter(Boolean)
          .map(value => Number.parseInt(value, 10))
          .filter(Number.isFinite);
        applySgr(params);
        lastIndex = pattern.lastIndex;
      }

      if (lastIndex < text.length) {
        const span = document.createElement('span');
        span.textContent = text.slice(lastIndex);
        const style = currentStyle();
        if (style) span.style.cssText = style;
        fragment.appendChild(span);
      }

      logEl.appendChild(fragment);
      if (stickToBottom) {
        window.scrollTo({ top: document.body.scrollHeight, behavior: 'auto' });
      }
    }

    async function poll() {
      try {
        const response = await fetch('/log?offset=' + offset, { cache: 'no-store' });
        const payload = await response.json();
        if (payload.chunk) appendAnsiText(payload.chunk);
        offset = payload.nextOffset;
        closed = payload.closed;
        statusEl.textContent = closed ? 'Run finished. Viewer page keeps the captured output.' : 'Streaming live output...';
      } catch (error) {
        statusEl.textContent = closed ? 'Run finished.' : 'Viewer disconnected: ' + error.message;
        if (!closed) pollTimer = window.setTimeout(poll, 1500);
        return;
      }

      if (!closed) pollTimer = window.setTimeout(poll, 700);
    }

    poll();
    window.addEventListener('beforeunload', () => {
      if (pollTimer) window.clearTimeout(pollTimer);
    });
  </script>
</body>
</html>`;
}

module.exports = { startLogViewer, buildLogViewerHTML };
