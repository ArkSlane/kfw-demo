import axios from "axios";
import { getAuthToken } from "@/api/httpClient";

const viteEnv = /** @type {any} */ (import.meta).env;
const GIT_URL = viteEnv?.VITE_GIT_URL || "http://localhost:8007";

const locatorsAPI = {
  /**
   * List scannable frontend files in a repo connection.
   * @param {string} connectionId
   * @param {string|null} path - optional sub-path filter
   */
  listFiles: async (connectionId, path = null) => {
    const params = path ? { path } : {};
    const res = await axios.get(`${GIT_URL}/locators/files/${connectionId}`, { params });
    return res.data; // { connection_id, files: string[], count }
  },

  /**
   * Analyze frontend files for test-locator suggestions (streaming).
   * Uses NDJSON streaming so results arrive per-file while analysis continues.
   *
   * @param {string} connectionId
   * @param {string|null} path - optional sub-path filter
   * @param {(event: {type: string, [k:string]: any}) => void} onEvent
   *   Called for each streamed event:
   *     - {type:"metadata", connection_id, repo_url, total_files}
   *     - {type:"file_result", file, previous_locators, locators, code, message, files_scanned_so_far, total_files}
   *     - {type:"done", files_scanned, total_locators}
   * @param {AbortSignal} [signal] - optional abort signal
   * @param {string[]|null} [files] - optional list of specific file paths to analyze
   */
  analyzeStream: async (connectionId, path = null, onEvent, signal, files = null) => {
    const headers = { "Content-Type": "application/json" };
    const token = getAuthToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const body = { connection_id: connectionId, path: path || null };
    if (files && files.length > 0) body.files = files;

    const resp = await fetch(`${GIT_URL}/locators/analyze`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      signal,
    });

    if (!resp.ok) {
      // try to parse error body
      let detail = resp.statusText;
      try {
        const err = await resp.json();
        detail = err.detail || err.message || detail;
      } catch { /* ignore */ }
      throw new Error(detail);
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // Process complete lines (NDJSON — one JSON object per line)
      let newlineIdx;
      while ((newlineIdx = buffer.indexOf("\n")) !== -1) {
        const line = buffer.slice(0, newlineIdx).trim();
        buffer = buffer.slice(newlineIdx + 1);
        if (!line) continue;
        try {
          const event = JSON.parse(line);
          onEvent(event);
        } catch {
          console.warn("[locatorsClient] failed to parse NDJSON line:", line);
        }
      }
    }

    // Handle any remaining buffer content
    if (buffer.trim()) {
      try {
        onEvent(JSON.parse(buffer.trim()));
      } catch { /* ignore trailing data */ }
    }
  },
};

export default locatorsAPI;
