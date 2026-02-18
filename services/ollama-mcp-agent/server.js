import express from 'express';
import { z } from 'zod';
import fs from 'node:fs/promises';
import path from 'node:path';

import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import { CallToolResultSchema, ListToolsResultSchema } from '@modelcontextprotocol/sdk/types.js';

const PORT = Number(process.env.PORT || 3000);

const OLLAMA_URL = (process.env.OLLAMA_URL || 'http://ollama:11434').replace(/\/$/, '');
const OLLAMA_MODEL = process.env.OLLAMA_MODEL || 'gpt-oss:20b';
const OLLAMA_TEMPERATURE = Number(process.env.OLLAMA_TEMPERATURE ?? 0);
const OLLAMA_TOP_P = Number(process.env.OLLAMA_TOP_P ?? 1);
const OLLAMA_MAX_TOKENS = Number(process.env.OLLAMA_MAX_TOKENS ?? 2048);
const OFFICIAL_MCP_URL = process.env.PLAYWRIGHT_MCP_OFFICIAL_URL || 'http://playwright-mcp-core:8931/mcp';
const VIDEO_DIR = process.env.VIDEO_PATH || '/videos';

const VIDEO_MIN_BYTES = Number(process.env.VIDEO_MIN_BYTES || 50 * 1024);
const VIDEO_STABLE_WAIT_MS = Number(process.env.VIDEO_STABLE_WAIT_MS || 800);
const VIDEO_FIND_TIMEOUT_MS = Number(process.env.VIDEO_FIND_TIMEOUT_MS || 10_000);

const DEFAULT_MAX_ITERATIONS = Number(process.env.MAX_ITERATIONS || 12);
const DEFAULT_MAX_TOOL_CALLS_PER_ITERATION = Number(process.env.MAX_TOOL_CALLS_PER_ITERATION || 8);

const app = express();
app.use(express.json({ limit: '2mb' }));

function buildSystemPrompt({ recordVideo, videoPath } = {}) {
  const base = [
    'You are an automation agent that can control a browser using MCP tools.',
    'You MUST accomplish the user task by calling tools. Prefer tool calls over guessing.',
    'IMPORTANT: Follow the provided steps STRICTLY. Do NOT perform extra actions not requested by the steps.',
    'You MUST complete ALL numbered steps provided by the user. Do not stop early.',
    'Track progress explicitly. Only mark a step complete after you have actually executed it via tool calls and confirmed the result via snapshots/tool output.',
    'Use browser_navigate to open pages. Use browser_snapshot to find elements and refs.',
    'When clicking, prefer providing both element (human description) and ref when available.',
    'After navigation or clicks, use browser_wait_for(time=1) briefly if needed.',
    'Avoid saving files unless explicitly asked (e.g., do not pass snapshot filenames unless required).',
    'When all steps are completed, STOP calling tools and reply with a short summary that begins with: DONE (completed_steps=X total_steps=Y)'
  ];

  if (recordVideo) {
    base.splice(
      base.length - 1,
      0,
      `Video recording is REQUIRED for this run. Ensure the browser context is created with video recording enabled and saved under: ${VIDEO_DIR}.`,
      videoPath ? `The desired final video filename is: ${String(videoPath)}.` : 'A deterministic filename will be provided separately.',
      'IMPORTANT: Close the page/context/browser at the end so the video is finalized on disk.'
    );
  }

  return base.join('\n');
}

function countNumberedSteps(stepsText) {
  if (!stepsText || typeof stepsText !== 'string') return null;
  const lines = stepsText.split(/\r?\n/);
  let count = 0;
  for (const line of lines) {
    if (/^\s*\d+\.\s+/.test(line)) count += 1;
  }
  return count > 0 ? count : null;
}

function parseCompletionFromText(text) {
  const s = typeof text === 'string' ? text : '';
  const completedMatch = s.match(/completed_steps\s*[:=]\s*(\d+)/i);
  const totalMatch = s.match(/total_steps\s*[:=]\s*(\d+)/i);
  const completedSteps = completedMatch ? Number(completedMatch[1]) : null;
  const totalSteps = totalMatch ? Number(totalMatch[1]) : null;
  const isDone = /^\s*DONE\b/i.test(s);
  return { isDone, completedSteps, totalSteps };
}

function buildActionsTakenLog(toolCallsExecuted) {
  if (!Array.isArray(toolCallsExecuted) || toolCallsExecuted.length === 0) return '';
  return toolCallsExecuted
    .map((t) => {
      const args = t?.arguments && typeof t.arguments === 'object' ? JSON.stringify(t.arguments) : String(t?.arguments ?? '');
      return `iter ${t?.iteration ?? '?'}: ${t?.name ?? '?'} ${args}`;
    })
    .join('\n');
}

async function findNewestFile(dirPath, startedAtMs, extensions) {
  let entries;
  try {
    entries = await fs.readdir(dirPath, { withFileTypes: true });
  } catch {
    return null;
  }

  let newest = null;

  for (const ent of entries) {
    if (!ent.isFile()) continue;
    const lower = ent.name.toLowerCase();
    if (!extensions.some((ext) => lower.endsWith(ext))) continue;

    const fullPath = path.join(dirPath, ent.name);
    let stat;
    try {
      stat = await fs.stat(fullPath);
    } catch {
      continue;
    }

    // Ignore files that pre-date this run (best-effort).
    if (stat.mtimeMs < startedAtMs - 500) continue;

    if (!newest || stat.mtimeMs > newest.mtimeMs) {
      newest = { fullPath, name: ent.name, mtimeMs: stat.mtimeMs };
    }
  }

  return newest;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function walkFilesShallow(dirPath) {
  let entries;
  try {
    entries = await fs.readdir(dirPath, { withFileTypes: true });
  } catch {
    return [];
  }

  const files = [];
  for (const ent of entries) {
    if (!ent.isFile()) continue;
    files.push(path.join(dirPath, ent.name));
  }
  return files;
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

async function findNewestVideoFile(dirPath, startedAtMs, extensions) {
  const candidates = await listCandidateVideoFiles(dirPath, extensions);

  let newest = null;
  for (const fullPath of candidates) {
    const stat = await statSafe(fullPath);
    if (!stat) continue;
    if (stat.mtimeMs < startedAtMs - 500) continue;
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

    // Still growing; keep waiting.
    lastSize = stat2.size;
  }

  // Timed out.
  return lastSize >= minBytes;
}

async function withMcpClient(fn) {
  const client = new Client({ name: 'ai-testing-v2-ollama-mcp-agent', version: '1.0.0' });
  const transport = new StreamableHTTPClientTransport(new URL(OFFICIAL_MCP_URL));
  await client.connect(transport);
  try {
    return await fn(client);
  } finally {
    await client.close().catch(() => {});
  }
}

async function listMcpTools(client) {
  const result = await client.request({ method: 'tools/list', params: {} }, ListToolsResultSchema);
  return result.tools || [];
}

function toOpenAiTool(tool) {
  const name = tool?.name;
  if (!name) return null;

  const parameters = tool?.inputSchema && typeof tool.inputSchema === 'object' ? tool.inputSchema : { type: 'object', properties: {} };
  if (!parameters.type) parameters.type = 'object';

  return {
    type: 'function',
    function: {
      name,
      description: tool?.description || '',
      parameters
    }
  };
}

function extractTextFromMcpToolResult(result) {
  const content = result?.content;
  if (!Array.isArray(content)) return '';
  const texts = [];
  for (const part of content) {
    if (part?.type === 'text' && typeof part.text === 'string') texts.push(part.text);
    else texts.push(JSON.stringify(part));
  }
  return texts.join('\n');
}

async function callMcpTool(client, name, args) {
  return await client.request(
    {
      method: 'tools/call',
      params: {
        name,
        arguments: args || {}
      }
    },
    CallToolResultSchema
  );
}

async function callOllamaChat({ messages, tools }) {
  const payload = {
    model: OLLAMA_MODEL,
    messages,
    tools,
    stream: false,
    options: {
      temperature: OLLAMA_TEMPERATURE,
      top_p: OLLAMA_TOP_P,
      max_tokens: OLLAMA_MAX_TOKENS
    }
  };

  const resp = await fetch(`${OLLAMA_URL}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`Ollama /api/chat failed: HTTP ${resp.status} ${resp.statusText} ${text}`);
  }

  return await resp.json();
}

function toToolResponseMessage(toolCall, toolName, toolResultText) {
  const msg = {
    role: 'tool',
    content: toolResultText,
    name: toolName
  };

  // Some tool-call formats include an id; include it if present.
  if (toolCall && typeof toolCall === 'object') {
    const id = toolCall.id || toolCall.tool_call_id || toolCall?.function?.id;
    if (id) msg.tool_call_id = id;
  }

  return msg;
}

const RunRequestSchema = z
  .object({
    prompt: z.string().optional(),
    test_description: z.string().optional(),
    steps: z.union([z.string(), z.array(z.any())]).optional(),
    max_iterations: z.number().int().positive().max(50).optional(),
    record_video: z.boolean().optional(),
    video_path: z.string().optional()
  })
  .passthrough();

app.get('/health', async (_req, res) => {
  try {
    // Quick Ollama check
    const ollamaResp = await fetch(`${OLLAMA_URL}/api/tags`, { method: 'GET' });
    const ollamaOk = ollamaResp.ok;

    const mcp = await withMcpClient(async (client) => {
      const tools = await listMcpTools(client);
      const names = tools.map((t) => t.name);
      return {
        tools_count: names.length,
        has_browser_snapshot: names.includes('browser_snapshot'),
        has_browser_click: names.includes('browser_click'),
        has_browser_navigate: names.includes('browser_navigate')
      };
    });

    res.json({
      status: 'ok',
      ollama_url: OLLAMA_URL,
      ollama_model: OLLAMA_MODEL,
      ollama_ok: ollamaOk,
      mcp_official_url: OFFICIAL_MCP_URL,
      ...mcp
    });
  } catch (e) {
    res.status(503).json({ status: 'degraded', error: e?.message || String(e) });
  }
});

app.post('/run', async (req, res) => {
  const parsed = RunRequestSchema.safeParse(req.body || {});
  if (!parsed.success) {
    return res.status(400).json({ success: false, error: parsed.error.message });
  }

  const { prompt, test_description, steps, max_iterations, record_video, video_path } = parsed.data;
  const runStartedAt = Date.now();

  const parts = [];
  if (prompt && typeof prompt === 'string' && prompt.trim()) {
    parts.push(prompt.trim());
  }
  if (test_description && typeof test_description === 'string' && test_description.trim()) {
    parts.push(`Test description: ${test_description.trim()}`);
  }
  if (typeof steps === 'string' && steps.trim()) {
    parts.push(`Steps:\n${steps.trim()}`);
  } else if (Array.isArray(steps) && steps.length > 0) {
    parts.push(`Steps (JSON):\n${JSON.stringify(steps, null, 2)}`);
  }

  const userPrompt = parts.join('\n\n') || 'Open the app and perform the described steps.';

  const transcript = [];
  const toolCallsExecuted = [];
  let videoSaved = false;
  let finalVideoPath = null;
  const stepsTextForCount = typeof steps === 'string' ? steps : null;
  const totalStepsFromInput = stepsTextForCount ? countNumberedSteps(stepsTextForCount) : Array.isArray(steps) ? steps.length : null;
  let completedStepsFinal = null;
  let totalStepsFinal = totalStepsFromInput;
  let completionMarkerAttempts = 0;

  try {
    const result = await withMcpClient(async (client) => {
      const mcpTools = await listMcpTools(client);
      const ollamaTools = mcpTools.map(toOpenAiTool).filter(Boolean);

      const messages = [
        { role: 'system', content: buildSystemPrompt({ recordVideo: !!record_video, videoPath: video_path }) },
        { role: 'user', content: userPrompt }
      ];

      const maxIterations = max_iterations ?? DEFAULT_MAX_ITERATIONS;

      for (let iteration = 1; iteration <= maxIterations; iteration++) {
        const ollamaData = await callOllamaChat({ messages, tools: ollamaTools });
        const assistantMessage = ollamaData?.message || {};

        const assistantContent = typeof assistantMessage.content === 'string' ? assistantMessage.content : '';
        const toolCalls = Array.isArray(assistantMessage.tool_calls) ? assistantMessage.tool_calls : [];

        transcript.push({ iteration, role: 'assistant', content: assistantContent, tool_calls: toolCalls });

        // Always append the assistant message to the conversation so Ollama can continue coherently.
        messages.push({
          role: 'assistant',
          content: assistantContent,
          ...(toolCalls.length > 0 ? { tool_calls: toolCalls } : {})
        });

        if (toolCalls.length === 0) {
          const completion = parseCompletionFromText(assistantContent);
          const completedSteps = completion.completedSteps;
          const totalSteps = completion.totalSteps ?? totalStepsFromInput;

          if (typeof totalSteps === 'number' && totalSteps > 0) {
            // Enforce finishing all steps; if the model stops early, push it to continue.
            if (typeof completedSteps !== 'number' || Number.isNaN(completedSteps)) {
              completionMarkerAttempts += 1;
              if (completionMarkerAttempts <= 2) {
                const msg = `You must include progress markers. Reply with: DONE (completed_steps=X total_steps=${totalSteps}). If not done, continue executing remaining steps.`;
                messages.push({ role: 'user', content: msg });
                transcript.push({ iteration, role: 'user', content: msg });
                continue;
              }
            } else if (completedSteps < totalSteps) {
              const nextStep = Math.min(totalSteps, Math.max(1, completedSteps + 1));
              const msg = `You reported only ${completedSteps}/${totalSteps} steps completed. Continue executing from step ${nextStep} until you reach DONE (completed_steps=${totalSteps} total_steps=${totalSteps}).`;
              messages.push({ role: 'user', content: msg });
              transcript.push({ iteration, role: 'user', content: msg });
              continue;
            }

            completedStepsFinal = typeof completedSteps === 'number' ? completedSteps : completedStepsFinal;
            totalStepsFinal = totalSteps;
          }

          if (record_video) {
            try {
              await callMcpTool(client, 'browser_close', {});
            } catch {
              // best-effort
            }
          }
          return { final: assistantContent, iterations: iteration };
        }

        // Execute tool calls via MCP.
        const cappedToolCalls = toolCalls.slice(0, DEFAULT_MAX_TOOL_CALLS_PER_ITERATION);

        for (const tc of cappedToolCalls) {
          const fn = tc?.function;
          const toolName = fn?.name;
          const args = fn?.arguments && typeof fn.arguments === 'object' ? fn.arguments : {};

          if (!toolName || typeof toolName !== 'string') {
            const errText = 'Invalid tool call from model (missing function.name).';
            messages.push({ role: 'tool', content: errText, name: 'invalid_tool_call' });
            transcript.push({ iteration, role: 'tool', name: 'invalid_tool_call', content: errText });
            continue;
          }

          toolCallsExecuted.push({ iteration, name: toolName, arguments: args });

          let toolResultText = '';
          try {
            const toolResult = await callMcpTool(client, toolName, args);
            toolResultText = extractTextFromMcpToolResult(toolResult);
          } catch (e) {
            toolResultText = `Tool execution failed for ${toolName}: ${e?.message || String(e)}`;
          }

          const toolMsg = toToolResponseMessage(tc, toolName, toolResultText);
          messages.push(toolMsg);
          transcript.push({ iteration, role: 'tool', name: toolName, content: toolResultText });
        }
      }

      if (record_video) {
        try {
          await callMcpTool(client, 'browser_close', {});
        } catch {
          // best-effort
        }
      }

      return { final: 'Stopped: max_iterations reached.', iterations: maxIterations };
    });

    if (record_video && video_path) {
      const deadline = Date.now() + VIDEO_FIND_TIMEOUT_MS;
      let newest = null;
      while (Date.now() < deadline) {
        newest = await findNewestVideoFile(VIDEO_DIR, runStartedAt, ['.webm', '.mp4']);
        if (!newest) {
          await sleep(250);
          continue;
        }

        // Prefer a non-trivial file, but fall back to “stable and non-zero” for short runs.
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
          newest = null;
          continue;
        }

        const targetPath = path.join(VIDEO_DIR, String(video_path));
        await fs.mkdir(path.dirname(targetPath), { recursive: true }).catch(() => {});
        await fs.rm(targetPath, { force: true }).catch(() => {});
        await fs.rename(newest.fullPath, targetPath);
        videoSaved = true;
        finalVideoPath = targetPath;
        break;
      }
    }

    const actionsTaken = buildActionsTakenLog(toolCallsExecuted);
    const stepCoverage =
      typeof totalStepsFinal === 'number' && totalStepsFinal > 0 && typeof completedStepsFinal === 'number'
        ? { completed_steps: completedStepsFinal, total_steps: totalStepsFinal, ratio: completedStepsFinal / totalStepsFinal }
        : null;

    return res.json({
      success: true,
      final_answer: result.final,
      iterations: result.iterations,
      actions_taken: actionsTaken,
      tool_calls_executed: toolCallsExecuted,
      transcript,
      completed_steps: completedStepsFinal,
      total_steps: totalStepsFinal,
      step_coverage: stepCoverage,
      video_saved: videoSaved,
      video_path: finalVideoPath,
      video_filename: video_path || null
    });
  } catch (e) {
    const actionsTaken = buildActionsTakenLog(toolCallsExecuted);
    const stepCoverage =
      typeof totalStepsFinal === 'number' && totalStepsFinal > 0 && typeof completedStepsFinal === 'number'
        ? { completed_steps: completedStepsFinal, total_steps: totalStepsFinal, ratio: completedStepsFinal / totalStepsFinal }
        : null;
    return res.status(200).json({
      success: false,
      error: e?.message || String(e),
      actions_taken: actionsTaken,
      tool_calls_executed: toolCallsExecuted,
      transcript,
      completed_steps: completedStepsFinal,
      total_steps: totalStepsFinal,
      step_coverage: stepCoverage,
      video_saved: videoSaved,
      video_path: finalVideoPath,
      video_filename: video_path || null
    });
  }
});

app.listen(PORT, () => {
  console.log(`Ollama MCP agent listening on ${PORT}`);
  console.log(`Ollama: ${OLLAMA_URL} (model: ${OLLAMA_MODEL})`);
  console.log(`Official MCP: ${OFFICIAL_MCP_URL}`);
  console.log(`Video dir: ${VIDEO_DIR}`);
});
