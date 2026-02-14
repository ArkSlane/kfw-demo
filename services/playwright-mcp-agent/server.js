import express from 'express';
import { promises as fs } from 'fs';
import path from 'path';

import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import { CallToolResultSchema, ListToolsResultSchema } from '@modelcontextprotocol/sdk/types.js';

const app = express();
app.use(express.json({ limit: '2mb' }));

const PORT = Number(process.env.PORT || 3000);
const VIDEO_DIR = process.env.VIDEO_PATH || '/videos';
const OFFICIAL_MCP_URL = process.env.PLAYWRIGHT_MCP_OFFICIAL_URL || 'http://playwright-mcp-core-1:8931/mcp';

// ── Playwright core pool (round-robin) ──────────────────────────────────
const MCP_POOL = (process.env.PLAYWRIGHT_MCP_POOL || OFFICIAL_MCP_URL)
  .split(',')
  .map((u) => u.trim())
  .filter(Boolean);
let _poolIndex = 0;

function nextMcpUrl() {
  const url = MCP_POOL[_poolIndex % MCP_POOL.length];
  _poolIndex = (_poolIndex + 1) % MCP_POOL.length;
  return url;
}

// Desired recorded video resolution (used to set viewport size before running scripts)
const VIDEO_WIDTH = Number(process.env.VIDEO_WIDTH || 1280);
const VIDEO_HEIGHT = Number(process.env.VIDEO_HEIGHT || 720);

const VIDEO_MIN_BYTES = Number(process.env.VIDEO_MIN_BYTES || 50 * 1024);
const VIDEO_STABLE_WAIT_MS = Number(process.env.VIDEO_STABLE_WAIT_MS || 800);
const VIDEO_FIND_TIMEOUT_MS = Number(process.env.VIDEO_FIND_TIMEOUT_MS || 10_000);

function textFromToolResult(result) {
  if (!result || !Array.isArray(result.content)) return '';
  return result.content
    .filter((c) => c && c.type === 'text' && typeof c.text === 'string')
    .map((c) => c.text)
    .join('\n');
}

async function findNewestFile(dir, startedAfterMs, extensions) {
  const extSet = new Set((extensions || []).map((e) => e.toLowerCase()));
  try {
    const entries = await fs.readdir(dir);
    let newest = null;
    for (const name of entries) {
      const lower = name.toLowerCase();
      const ext = path.extname(lower);
      if (extSet.size > 0 && !extSet.has(ext)) continue;

      const fullPath = path.join(dir, name);
      let stat;
      try {
        stat = await fs.stat(fullPath);
      } catch {
        continue;
      }
      if (stat.mtimeMs < startedAfterMs) continue;
      if (!newest || stat.mtimeMs > newest.mtimeMs) {
        newest = { name, fullPath, mtimeMs: stat.mtimeMs, size: stat.size };
      }
    }
    return newest;
  } catch {
    return null;
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function walkFilesShallow(dirPath) {
  try {
    const entries = await fs.readdir(dirPath, { withFileTypes: true });
    return entries.filter((e) => e.isFile()).map((e) => path.join(dirPath, e.name));
  } catch {
    return [];
  }
}

async function walkFilesRecursive(dirPath, maxDepth) {
  if (maxDepth < 0) return [];
  let entries;
  try {
    entries = await fs.readdir(dirPath, { withFileTypes: true });
  } catch {
    return [];
  }

  const files = [];
  for (const ent of entries) {
    const full = path.join(dirPath, ent.name);
    if (ent.isFile()) {
      files.push(full);
    } else if (ent.isDirectory() && maxDepth > 0) {
      files.push(...(await walkFilesRecursive(full, maxDepth - 1)));
    }
  }
  return files;
}

async function listCandidateVideoFiles(dirPath, extensions) {
  const dirs = [dirPath, path.join(dirPath, 'videos')];
  const candidates = [];
  for (const d of dirs) {
    // Playwright can nest videos under per-context subfolders.
    for (const filePath of await walkFilesRecursive(d, 3)) {
      const lower = filePath.toLowerCase();
      if (!extensions.some((ext) => lower.endsWith(ext))) continue;
      candidates.push(filePath);
    }
  }
  return candidates;
}

async function statSafe(filePath) {
  try {
    return await fs.stat(filePath);
  } catch {
    return null;
  }
}

async function findNewestVideoFile(dirPath, startedAfterMs, extensions) {
  const candidates = await listCandidateVideoFiles(dirPath, extensions);
  let newest = null;
  for (const fullPath of candidates) {
    const stat = await statSafe(fullPath);
    if (!stat) continue;
    if (stat.mtimeMs < startedAfterMs) continue;
    if (!newest || stat.mtimeMs > newest.mtimeMs) {
      newest = { fullPath, name: path.basename(fullPath), mtimeMs: stat.mtimeMs, size: stat.size };
    }
  }
  return newest;
}

async function waitForStableNonTrivialFile(filePath, minBytes, stableWaitMs, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  let lastSize = -1;

  while (Date.now() < deadline) {
    const stat1 = await statSafe(filePath);
    if (!stat1) {
      await sleep(200);
      continue;
    }
    if (stat1.size < minBytes) {
      lastSize = stat1.size;
      await sleep(250);
      continue;
    }

    await sleep(stableWaitMs);
    const stat2 = await statSafe(filePath);
    if (!stat2) {
      await sleep(200);
      continue;
    }
    if (stat2.size >= minBytes && stat2.size === stat1.size) {
      return true;
    }
    lastSize = stat2.size;
  }

  return lastSize >= minBytes;
}

async function maybeRenameNewestVideo({ runStartedAt, video_path }) {
  if (!video_path) return false;

  const deadline = Date.now() + VIDEO_FIND_TIMEOUT_MS;
  while (Date.now() < deadline) {
    const newest = await findNewestVideoFile(VIDEO_DIR, runStartedAt, ['.webm', '.mp4']);
    if (!newest) {
      await sleep(250);
      continue;
    }

    // Prefer waiting for a non-trivial file, but fall back to “stable and non-zero”
    // so short runs still produce a usable video.
    let ok = await waitForStableNonTrivialFile(
      newest.fullPath,
      VIDEO_MIN_BYTES,
      VIDEO_STABLE_WAIT_MS,
      Math.max(0, deadline - Date.now())
    );
    if (!ok) {
      ok = await waitForStableNonTrivialFile(
        newest.fullPath,
        1,
        VIDEO_STABLE_WAIT_MS,
        Math.max(0, deadline - Date.now())
      );
    }
    if (!ok) {
      await sleep(250);
      continue;
    }

    const targetPath = path.join(VIDEO_DIR, String(video_path));
    await fs.mkdir(path.dirname(targetPath), { recursive: true }).catch(() => {});
    await fs.rm(targetPath, { force: true }).catch(() => {});
    await fs.rename(newest.fullPath, targetPath);
    return true;
  }

  return false;
}

async function withMcpClient(fn) {
  const mcpUrl = nextMcpUrl();
  const client = new Client({ name: 'ai-testing-v2-playwright-mcp-agent', version: '1.0.0' });
  const transport = new StreamableHTTPClientTransport(new URL(mcpUrl));
  try {
    await client.connect(transport);
    return await fn(client);
  } finally {
    try {
      await transport.close();
    } catch {
      // ignore
    }
  }
}

async function callTool(client, name, args) {
  const result = await client.request(
    {
      method: 'tools/call',
      params: {
        name,
        arguments: args || {}
      }
    },
    CallToolResultSchema
  );
  return result;
}

function parseStepsText(stepsText) {
  let text = (stepsText || '').toString();
  // Some callers accidentally send literal "\\n" instead of real newlines.
  // Normalize those so step parsing works reliably.
  text = text.replace(/\\r\\n/g, '\n').replace(/\\n/g, '\n');
  if (!text.trim()) return [];
  const lines = text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);

  const parsed = [];
  for (const line of lines) {
    const numbered = line.match(/^(\d+)\.\s+(.*)$/);
    if (numbered) {
      parsed.push({ number: Number(numbered[1]), text: numbered[2] });
      continue;
    }
    const bulleted = line.match(/^[-*]\s+(.*)$/);
    if (bulleted) {
      parsed.push({ number: parsed.length + 1, text: bulleted[1] });
      continue;
    }
  }

  if (parsed.length === 0) return [{ number: 1, text: text.trim() }];
  return parsed;
}

function extractQuotedOrLastWords(stepText) {
  const s = stepText || '';
  const quoted = s.match(/"([^"]+)"|'([^']+)'/);
  if (quoted) return (quoted[1] || quoted[2] || '').trim();

  // Heuristic: grab after keywords
  const after = s.match(/\b(?:text|named|titled|label(?:led)?|called)\b\s*[:=]?\s*(.+)$/i);
  if (after) return after[1].trim();

  // Fallback: last 4 words
  const parts = s.trim().split(/\s+/).filter(Boolean);
  return parts.slice(Math.max(0, parts.length - 4)).join(' ');
}

function extractUrl(stepText) {
  const m = (stepText || '').match(/https?:\/\/[^\s)\]}]+/i);
  if (!m) return null;
  // If the URL contains literal escape sequences like "\\n", trim at the backslash.
  const raw = m[0];
  const cut = raw.indexOf('\\');
  return (cut >= 0 ? raw.slice(0, cut) : raw).trim();
}

function extractRefFromLine(line) {
  if (!line) return null;
  const patterns = [
    /\bref\s*=\s*"([^"]+)"/i,
    /\bref\s*=\s*'([^']+)'/i,
    /\bref\s*=\s*([^\s\]]+)/i,
    /\[ref\s*[:=]\s*([^\]]+)\]/i
  ];
  for (const re of patterns) {
    const m = line.match(re);
    if (m) return String(m[1]).trim();
  }
  return null;
}

function findRefInSnapshot(snapshotMarkdown, targetText) {
  const snap = (snapshotMarkdown || '').toString();
  const target = (targetText || '').toString().trim();
  if (!snap || !target) return null;

  const lines = snap.split(/\r?\n/);
  const targetLower = target.toLowerCase();

  // Prefer exact/substring match
  for (const line of lines) {
    if (line.toLowerCase().includes(targetLower)) {
      const ref = extractRefFromLine(line);
      if (ref) return { ref, line };
    }
  }

  // Fallback: split words and require most of them
  const words = targetLower.split(/\s+/).filter(Boolean);
  if (words.length >= 2) {
    for (const line of lines) {
      const l = line.toLowerCase();
      const hits = words.filter((w) => l.includes(w)).length;
      if (hits >= Math.ceil(words.length * 0.75)) {
        const ref = extractRefFromLine(line);
        if (ref) return { ref, line };
      }
    }
  }

  return null;
}

function normalizeLocalhostUrl(urlString) {
  try {
    const parsed = new URL(urlString);
    if (['localhost', '127.0.0.1', '0.0.0.0'].includes(parsed.hostname)) {
      parsed.hostname = 'frontend';
      parsed.port = '5173';
      return parsed.toString();
    }
  } catch {
    // ignore
  }
  return urlString;
}

app.get('/health', async (_req, res) => {
  try {
    const tools = await withMcpClient(async (client) => {
      const result = await client.request({ method: 'tools/list', params: {} }, ListToolsResultSchema);
      return result.tools.map((t) => t.name);
    });

    res.json({
      status: 'ok',
      mcp_official_url: OFFICIAL_MCP_URL,
      tools_count: tools.length,
      has_browser_snapshot: tools.includes('browser_snapshot'),
      has_browser_click: tools.includes('browser_click'),
      has_browser_run_code: tools.includes('browser_run_code')
    });
  } catch (e) {
    res.status(503).json({ status: 'degraded', mcp_official_url: OFFICIAL_MCP_URL, error: e?.message || String(e) });
  }
});

// Compatibility endpoint: execute a stored Playwright script (as used by automations service)
app.post('/execute', async (req, res) => {
  const { script, video_path, record_video } = req.body || {};
  const runStartedAt = Date.now();
  const actionLog = [];

  try {
    if (!script || typeof script !== 'string') {
      return res.status(400).json({ success: false, error: 'Missing script' });
    }

    // Wrap the script into an async function so it can be run by browser_run_code.
    // Prepend viewport sizing so the Playwright page uses the same resolution as the recorded video.
    const fnCode = `async (page) => {\n  try { await page.setViewportSize({ width: ${VIDEO_WIDTH}, height: ${VIDEO_HEIGHT} }); } catch (e) {}\n${script}\n}`;

    await withMcpClient(async (client) => {
    actionLog.push('Action: browser_run_code(script)');
    const runResult = await callTool(client, 'browser_run_code', { code: fnCode });
      const runText = textFromToolResult(runResult);
      if (runText) {
        actionLog.push('Result:');
        actionLog.push(runText);
      }

      // Give the recorder a moment to capture the final UI state.
      if (record_video) {
        try {
          await callTool(client, 'browser_wait_for', { time: 1 });
        } catch {
          // best-effort
        }
        try {
          await callTool(client, 'browser_close', {});
        } catch {
          // best-effort
        }
      }
    });

    let videoSaved = false;
    if (record_video && video_path) {
      // Guarded rename: wait for stable file (>0 bytes).
      videoSaved = await maybeRenameNewestVideo({ runStartedAt, video_path });
    }

    return res.json({
      success: true,
      message: 'Execution completed',
      actions_taken: actionLog.join('\n'),
      video_saved: videoSaved,
      video_filename: videoSaved && video_path ? String(video_path) : null
    });
  } catch (e) {
    actionLog.push(`Error: ${e?.message || String(e)}`);
    return res.status(200).json({ success: false, error: e?.message || String(e), actions_taken: actionLog.join('\n') });
  }
});

// Compatibility endpoint: step-driven execution (used by generator execution-based generation)
app.post('/execute-test', async (req, res) => {
  const { test_description, steps, video_path } = req.body || {};
  const actionLog = [];
  const parsedSteps = parseStepsText(steps);
  const runStartedAt = Date.now();

  try {
    await withMcpClient(async (client) => {
      // Ensure viewport size is set for step-driven runs as well so recordings match expected resolution
      try {
        const prelude = `async (page) => { try { await page.setViewportSize({ width: ${VIDEO_WIDTH}, height: ${VIDEO_HEIGHT} }); } catch(e){} }`;
        await callTool(client, 'browser_run_code', { code: prelude });
      } catch (e) {
        // continue if tool not available
      }
      // Navigate can be inferred from any step containing a URL
      for (const step of parsedSteps) {
        const text = step.text || '';
        const url = extractUrl(text);
        if (url) {
          const normalized = normalizeLocalhostUrl(url);
          actionLog.push(`Action: navigate(${normalized})`);
          await callTool(client, 'browser_navigate', { url: normalized });
          // Give the SPA a moment to settle
          await callTool(client, 'browser_wait_for', { time: 1 });
          break;
        }
      }

      let completedSteps = 0;

      for (const step of parsedSteps) {
        const text = step.text || '';
        const lower = text.toLowerCase();

        // Skip navigate step (handled above)
        if (extractUrl(text)) {
          completedSteps++;
          continue;
        }

        if (lower.includes('wait')) {
          actionLog.push('Action: wait(1s)');
          await callTool(client, 'browser_wait_for', { time: 1 });
          completedSteps++;
          continue;
        }

        // For clicks/ticks/checks: use snapshot + ref lookup
        if (/(click|press|tap|open|select|tick|check)/i.test(lower)) {
          const target = extractQuotedOrLastWords(text);
          const snapResult = await callTool(client, 'browser_snapshot', {});
          const snapshot = textFromToolResult(snapResult);

          const found = findRefInSnapshot(snapshot, target);
          if (!found) {
            actionLog.push(`ActionError: could not find ref for "${target}"`);
            break;
          }

          actionLog.push(`Action: click(ref=${found.ref}, target=${target})`);
          await callTool(client, 'browser_click', { element: target, ref: found.ref });
          await callTool(client, 'browser_wait_for', { time: 1 });
          completedSteps++;
          continue;
        }

        // Observe/assertion-ish steps: do a snapshot and continue
        if (/(observe|verify|assert|expect)/i.test(lower)) {
          actionLog.push('Action: snapshot()');
          await callTool(client, 'browser_snapshot', {});
          completedSteps++;
          continue;
        }

        // Default: just snapshot so we have context
        actionLog.push('Action: snapshot()');
        await callTool(client, 'browser_snapshot', {});
        completedSteps++;
      }

      actionLog.push(`Completed ${completedSteps}/${parsedSteps.length} steps`);

      if (video_path) {
        try {
          await callTool(client, 'browser_close', {});
        } catch {
          // best-effort
        }
      }
    });

    if (video_path) {
      await maybeRenameNewestVideo({ runStartedAt, video_path });
    }

    return res.json({
      success: true,
      actions_taken: actionLog.join('\n')
    });
  } catch (e) {
    return res.status(200).json({ success: false, error: e?.message || String(e), actions_taken: actionLog.join('\n') });
  }
});

app.listen(PORT, () => {
  console.log(`Playwright MCP agent listening on ${PORT}`);
  console.log(`Official MCP URL: ${OFFICIAL_MCP_URL}`);
  console.log(`Video dir: ${VIDEO_DIR}`);
});
