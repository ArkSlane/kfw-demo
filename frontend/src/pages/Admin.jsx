// @ts-nocheck
import React, { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

import gitTokensAPI from "@/api/gitTokensClient";
import gitRepoConnectionsAPI from "@/api/gitRepoConnectionsClient";
import llmConnectionsAPI from "@/api/llmConnectionsClient";

// jsconfig.json enables checkJs; cast import.meta to any for Vite env access.
const viteEnv = /** @type {any} */ (import.meta).env;

const DEFAULT_SERVICE_URLS = {
  requirements: viteEnv?.VITE_REQUIREMENTS_URL || "http://localhost:8001",
  testcases: viteEnv?.VITE_TESTCASES_URL || "http://localhost:8002",
  generator: viteEnv?.VITE_GENERATOR_URL || "http://localhost:8003",
  releases: viteEnv?.VITE_RELEASES_URL || "http://localhost:8004",
  executions: viteEnv?.VITE_EXECUTIONS_URL || "http://localhost:8005",
  automations: viteEnv?.VITE_AUTOMATIONS_URL || "http://localhost:8006",
  git: viteEnv?.VITE_GIT_URL || "http://localhost:8007",
  toabrkia: viteEnv?.VITE_TOABRKIA_URL || "http://localhost:8008",
  testcaseMigration: viteEnv?.VITE_TESTCASE_MIGRATION_URL || "http://localhost:8009",
  ollama: viteEnv?.VITE_OLLAMA_URL || "http://localhost:11434",
};

const STORAGE_KEYS = {
  repos: "aitp.admin.repos.v1",
  users: "aitp.admin.users.v1",
  aiPrompts: "aitp.admin.aiPrompts.v1",
  testApproach: "aitp.admin.testApproach.v1",
};

function loadJson(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw);
  } catch {
    return fallback;
  }
}

function saveJson(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function uid() {
  return Math.random().toString(16).slice(2) + Date.now().toString(16);
}

function maskToken(token) {
  const t = String(token || "");
  if (!t) return "";
  if (t.length <= 8) return "********";
  return `${t.slice(0, 4)}…${t.slice(-4)}`;
}

function tokenPreview(token) {
  // Prefer server-provided masking if present.
  if (token?.token_masked) return token.token_masked;
  return maskToken(token?.token);
}

function detectProviderFromRepoUrl(repoUrl) {
  const url = (repoUrl || "").toLowerCase();
  if (url.includes("github.com")) return "github";
  if (url.includes("gitlab.com")) return "gitlab";
  if (url.includes("dev.azure.com") || url.includes("visualstudio.com")) return "azureDevOps";
  return "unknown";
}

async function fetchWithTimeout(url, opts = {}, timeoutMs = 5000) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...opts, signal: controller.signal });
    return res;
  } finally {
    clearTimeout(id);
  }
}

export default function Admin() {
  // Tokens
  const [tokens, setTokens] = useState([]);
  const [loadingTokens, setLoadingTokens] = useState(false);
  const [newTokenProvider, setNewTokenProvider] = useState("github");
  const [newTokenName, setNewTokenName] = useState("");
  const [newTokenValue, setNewTokenValue] = useState("");
  const [newAzureOrg, setNewAzureOrg] = useState("");

  // Repos
  const [repos, setRepos] = useState([]);
  const [loadingRepos, setLoadingRepos] = useState(false);
  const [repoUrl, setRepoUrl] = useState("");
  const [selectedTokenId, setSelectedTokenId] = useState(null);
  const [tokenPickerOpen, setTokenPickerOpen] = useState(false);

  // Users
  const [users, setUsers] = useState(() => loadJson(STORAGE_KEYS.users, []));
  const [newUserName, setNewUserName] = useState("");
  const [newUserRole, setNewUserRole] = useState("user");

  // Health
  const [healthRows, setHealthRows] = useState([]);
  const [loadingHealth, setLoadingHealth] = useState(false);

  // AI prompts / test approach
  const [aiPrompts, setAiPrompts] = useState(() =>
    loadJson(STORAGE_KEYS.aiPrompts, {
      testcaseAnalysisPrompt: "",
      automationChatPrompt: "",
      testcaseMigrationPrompt: "",
    })
  );
  const [testApproach, setTestApproach] = useState(() => loadJson(STORAGE_KEYS.testApproach, ""));

  // LLM connections
  const [llmConnections, setLlmConnections] = useState([]);
  const [loadingLlmConnections, setLoadingLlmConnections] = useState(false);
  const [newLlmProvider, setNewLlmProvider] = useState("openai");
  const [newLlmName, setNewLlmName] = useState("");
  const [newLlmBaseUrl, setNewLlmBaseUrl] = useState("");
  const [newLlmApiKey, setNewLlmApiKey] = useState("");
  const [newLlmDefaultModel, setNewLlmDefaultModel] = useState("");

  const refreshLlmConnections = async () => {
    setLoadingLlmConnections(true);
    try {
      const list = await llmConnectionsAPI.list();
      setLlmConnections(Array.isArray(list) ? list : []);
    } catch (e) {
      console.error("Failed to load LLM connections", e);
      toast.error("Failed to load LLM connections from git service");
    } finally {
      setLoadingLlmConnections(false);
    }
  };

  const refreshTokens = async () => {
    setLoadingTokens(true);
    try {
      const list = await gitTokensAPI.list();
      setTokens(Array.isArray(list) ? list : []);
    } catch (e) {
      console.error("Failed to load tokens", e);
      toast.error("Failed to load API tokens from git service");
    } finally {
      setLoadingTokens(false);
    }
  };

  useEffect(() => {
    refreshTokens();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    refreshLlmConnections();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const refreshRepos = async () => {
    setLoadingRepos(true);
    try {
      const list = await gitRepoConnectionsAPI.list();
      setRepos(Array.isArray(list) ? list : []);
    } catch (e) {
      console.error("Failed to load repo connections", e);
      toast.error("Failed to load repo connections from git service");
    } finally {
      setLoadingRepos(false);
    }
  };

  useEffect(() => {
    refreshRepos();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    saveJson(STORAGE_KEYS.users, users);
  }, [users]);

  useEffect(() => {
    saveJson(STORAGE_KEYS.aiPrompts, aiPrompts);
  }, [aiPrompts]);

  useEffect(() => {
    saveJson(STORAGE_KEYS.testApproach, testApproach);
  }, [testApproach]);

  const selectedToken = useMemo(() => tokens.find((t) => t.id === selectedTokenId) || null, [tokens, selectedTokenId]);
  const repoProviderHint = useMemo(() => detectProviderFromRepoUrl(repoUrl), [repoUrl]);

  const tokensByProvider = useMemo(() => {
    const map = { github: [], gitlab: [], azureDevOps: [] };
    for (const t of tokens) {
      if (map[t.provider]) map[t.provider].push(t);
    }
    return map;
  }, [tokens]);

  const createToken = async () => {
    if (!newTokenName.trim()) {
      toast.error("Token name is required");
      return;
    }
    if (!newTokenValue.trim()) {
      toast.error("Token value is required");
      return;
    }

    try {
      await gitTokensAPI.create({
        provider: newTokenProvider,
        name: newTokenName.trim(),
        token: newTokenValue,
        azure_org: newTokenProvider === "azureDevOps" ? (newAzureOrg.trim() || null) : null,
      });
      setNewTokenName("");
      setNewTokenValue("");
      setNewAzureOrg("");
      toast.success("Token stored in git service");
      await refreshTokens();
    } catch (e) {
      console.error("Failed to create token", e);
      toast.error("Failed to store token");
    }
  };

  const deleteToken = async (id) => {
    try {
      await gitTokensAPI.delete(id);
      if (selectedTokenId === id) setSelectedTokenId(null);
      toast.success("Token deleted");
      await refreshTokens();
    } catch (e) {
      console.error("Failed to delete token", e);
      toast.error("Failed to delete token");
    }
  };

  const connectRepo = async () => {
    const url = repoUrl.trim();
    if (!url) {
      toast.error("Repo URL is required");
      return;
    }
    if (!selectedTokenId) {
      toast.error("Select a token");
      return;
    }

    try {
      await gitRepoConnectionsAPI.connect({ repo_url: url, api_token_id: selectedTokenId });
      setRepoUrl("");
      setSelectedTokenId(null);
      toast.success("Repo cloned and connected");
      await refreshRepos();
    } catch (e) {
      console.error("Failed to connect repo", e);
      const msg = e?.response?.data?.detail || e?.message || "Failed to connect repo";
      toast.error(msg);
    }
  };

  const disconnectRepo = async (id) => {
    try {
      await gitRepoConnectionsAPI.disconnect(id);
      toast.success("Disconnected");
      await refreshRepos();
    } catch (e) {
      console.error("Failed to disconnect repo", e);
      toast.error("Failed to disconnect");
    }
  };

  const syncRepo = async (id) => {
    try {
      await gitRepoConnectionsAPI.sync(id);
      toast.success("Repo synced");
      await refreshRepos();
    } catch (e) {
      console.error("Failed to sync repo", e);
      const msg = e?.response?.data?.detail || e?.message || "Failed to sync repo";
      toast.error(msg);
    }
  };

  const addUser = () => {
    if (!newUserName.trim()) {
      toast.error("User name is required");
      return;
    }
    const user = {
      id: uid(),
      name: newUserName.trim(),
      role: newUserRole,
      created_at: new Date().toISOString(),
    };
    setUsers((prev) => [user, ...prev]);
    setNewUserName("");
    setNewUserRole("user");
    toast.success("User added");
  };

  const deleteUser = (id) => {
    setUsers((prev) => prev.filter((u) => u.id !== id));
    toast.success("User removed");
  };

  const refreshHealth = async () => {
    setLoadingHealth(true);
    try {
      const checks = [
        { key: "requirements", url: `${DEFAULT_SERVICE_URLS.requirements}/health` },
        { key: "testcases", url: `${DEFAULT_SERVICE_URLS.testcases}/health` },
        { key: "generator", url: `${DEFAULT_SERVICE_URLS.generator}/health` },
        { key: "releases", url: `${DEFAULT_SERVICE_URLS.releases}/health` },
        { key: "executions", url: `${DEFAULT_SERVICE_URLS.executions}/health` },
        { key: "automations", url: `${DEFAULT_SERVICE_URLS.automations}/health` },
        { key: "git", url: `${DEFAULT_SERVICE_URLS.git}/health` },
        { key: "toabrkia", url: `${DEFAULT_SERVICE_URLS.toabrkia}/health` },
        { key: "testcase-migration", url: `${DEFAULT_SERVICE_URLS.testcaseMigration}/health` },
        // Ollama doesn't expose /health; use /api/tags.
        { key: "ollama", url: `${DEFAULT_SERVICE_URLS.ollama}/api/tags` },
      ];

      const results = await Promise.all(
        checks.map(async (c) => {
          const started = performance.now();
          try {
            const res = await fetchWithTimeout(c.url, {}, 6000);
            const ms = Math.round(performance.now() - started);
            const ok = res.ok;
            return {
              service: c.key,
              url: c.url,
              status: ok ? "healthy" : `error (${res.status})`,
              response_time_ms: ms,
            };
          } catch (e) {
            const ms = Math.round(performance.now() - started);
            return {
              service: c.key,
              url: c.url,
              status: "unreachable",
              response_time_ms: ms,
            };
          }
        })
      );

      setHealthRows(results);
      toast.success("Health refreshed");
    } finally {
      setLoadingHealth(false);
    }
  };

  const tokenPickerList = useMemo(() => {
    // Prefer provider-matching tokens first.
    const provider = repoProviderHint;
    const matches = tokens.filter((t) => t.provider === provider);
    const rest = tokens.filter((t) => t.provider !== provider);
    return provider !== "unknown" ? [...matches, ...rest] : tokens;
  }, [tokens, repoProviderHint]);

  return (
    <div className="p-6 space-y-6">
      <div className="space-y-1">
        <h1 className="text-2xl font-bold text-slate-900">Admin</h1>
        <p className="text-sm text-slate-600">Administration tools and configuration.</p>
      </div>

      <Tabs defaultValue="tokens" className="w-full">
        <TabsList className="flex flex-wrap justify-start">
          <TabsTrigger value="tokens">API tokens</TabsTrigger>
          <TabsTrigger value="repos">Repo connections</TabsTrigger>
          <TabsTrigger value="users">User management</TabsTrigger>
          <TabsTrigger value="health">Service health</TabsTrigger>
          <TabsTrigger value="ai">AI inclusion</TabsTrigger>
          <TabsTrigger value="approach">Test approach</TabsTrigger>
        </TabsList>

        <TabsContent value="tokens">
          <Card className="p-6 space-y-6">
            <div className="space-y-1">
              <div className="text-sm font-medium text-slate-900">API token management</div>
              <div className="text-xs text-slate-600">Store tokens for GitHub, GitLab, and Azure DevOps.</div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <div className="space-y-2">
                <div className="text-xs text-slate-600">Provider</div>
                <Select value={newTokenProvider} onValueChange={setNewTokenProvider}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="github">GitHub</SelectItem>
                    <SelectItem value="gitlab">GitLab</SelectItem>
                    <SelectItem value="azureDevOps">Azure DevOps</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <div className="text-xs text-slate-600">Token name</div>
                <Input value={newTokenName} onChange={(e) => setNewTokenName(e.target.value)} placeholder="e.g. company-github" />
              </div>
              <div className="space-y-2">
                <div className="text-xs text-slate-600">Token</div>
                <Input
                  type="password"
                  value={newTokenValue}
                  onChange={(e) => setNewTokenValue(e.target.value)}
                  placeholder="Paste token value"
                />
                {newTokenProvider === "azureDevOps" ? (
                  <div className="space-y-2 pt-2">
                    <div className="text-xs text-slate-600">Azure DevOps org (optional)</div>
                    <Input
                      value={newAzureOrg}
                      onChange={(e) => setNewAzureOrg(e.target.value)}
                      placeholder="e.g. your-org"
                    />
                  </div>
                ) : null}
              </div>
            </div>

            <div className="flex justify-end">
              <Button onClick={createToken} disabled={loadingTokens}>Save token</Button>
            </div>

            <div className="space-y-3">
              <div className="text-sm font-medium">Saved tokens</div>
              {loadingTokens ? <div className="text-sm text-slate-600">Loading tokens…</div> : null}
              {!loadingTokens && tokens.length === 0 ? <div className="text-sm text-slate-600">No tokens saved.</div> : null}

              {tokens.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Provider</TableHead>
                      <TableHead>Name</TableHead>
                      <TableHead>Token</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {tokens.map((t) => (
                      <TableRow key={t.id}>
                        <TableCell>
                          <Badge variant="outline" className="text-slate-600 border-slate-300">
                            {t.provider}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-slate-800">{t.name}</TableCell>
                        <TableCell className="font-mono text-xs text-slate-600">{tokenPreview(t)}</TableCell>
                        <TableCell className="text-right">
                          <Button variant="outline" size="sm" onClick={() => deleteToken(t.id)}>
                            Delete
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : null}
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="repos">
          <Card className="p-6 space-y-6">
            <div className="space-y-1">
              <div className="text-sm font-medium text-slate-900">Connecting a Repo</div>
              <div className="text-xs text-slate-600">Connect a repository using a repo URL and a token selection.</div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <div className="space-y-2 lg:col-span-2">
                <div className="text-xs text-slate-600">Repo URL</div>
                <Input
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                  placeholder="https://github.com/org/repo.git"
                />
                {repoProviderHint !== "unknown" ? (
                  <div className="text-xs text-slate-500">Detected provider: {repoProviderHint}</div>
                ) : null}
              </div>

              <div className="space-y-2">
                <div className="text-xs text-slate-600">Token</div>
                <div className="flex gap-2">
                  <Button variant="outline" className="w-full justify-between" onClick={() => setTokenPickerOpen(true)}>
                    {selectedToken ? selectedToken.name : "Select token"}
                  </Button>
                </div>
                {selectedToken ? (
                  <div className="text-xs text-slate-500">
                    {selectedToken.provider} • {tokenPreview(selectedToken)}
                  </div>
                ) : null}
              </div>
            </div>

            <div className="flex justify-end">
              <Button onClick={connectRepo} disabled={!repoUrl.trim() || !selectedTokenId}>
                Connect
              </Button>
            </div>

            <div className="space-y-3">
              <div className="text-sm font-medium">Existing repo connections</div>
              {loadingRepos ? <div className="text-sm text-slate-600">Loading repo connections…</div> : null}
              {!loadingRepos && repos.length === 0 ? <div className="text-sm text-slate-600">No repo connections.</div> : null}

              {repos.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Repo</TableHead>
                      <TableHead>Provider</TableHead>
                      <TableHead>Token</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Last synced</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {repos.map((r) => {
                      const t = tokens.find((x) => x.id === r.api_token_id);
                      return (
                        <TableRow key={r.id}>
                          <TableCell className="text-slate-800">{r.repo_url}</TableCell>
                          <TableCell>
                            <Badge variant="outline" className="text-slate-600 border-slate-300">
                              {r.provider}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-xs text-slate-600">{t ? t.name : "(missing token)"}</TableCell>
                          <TableCell className="text-xs text-slate-600">{r.status}</TableCell>
                          <TableCell className="text-xs text-slate-600">{r.last_synced_at || "—"}</TableCell>
                          <TableCell className="text-right space-x-2">
                            <Button variant="outline" size="sm" onClick={() => syncRepo(r.id)}>
                              Sync
                            </Button>
                            <Button variant="outline" size="sm" onClick={() => disconnectRepo(r.id)}>
                              Disconnect
                            </Button>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              ) : null}
            </div>

            <Dialog open={tokenPickerOpen} onOpenChange={setTokenPickerOpen}>
              <DialogContent className="max-w-2xl">
                <DialogHeader>
                  <DialogTitle>Select token</DialogTitle>
                </DialogHeader>

                <div className="space-y-3">
                  {tokenPickerList.length === 0 ? (
                    <div className="text-sm text-slate-600">
                      No tokens available. Add one in the “API tokens” tab.
                    </div>
                  ) : (
                    <div className="rounded border">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Provider</TableHead>
                            <TableHead>Name</TableHead>
                            <TableHead>Token</TableHead>
                            <TableHead className="text-right">Select</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {tokenPickerList.map((t) => (
                            <TableRow key={t.id}>
                              <TableCell>
                                <Badge variant="outline" className="text-slate-600 border-slate-300">
                                  {t.provider}
                                </Badge>
                              </TableCell>
                              <TableCell>{t.name}</TableCell>
                              <TableCell className="font-mono text-xs text-slate-600">{tokenPreview(t)}</TableCell>
                              <TableCell className="text-right">
                                <Button
                                  size="sm"
                                  onClick={() => {
                                    setSelectedTokenId(t.id);
                                    setTokenPickerOpen(false);
                                  }}
                                >
                                  Use
                                </Button>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  )}
                </div>

                <DialogFooter>
                  <Button variant="outline" onClick={() => setTokenPickerOpen(false)}>
                    Close
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </Card>
        </TabsContent>

        <TabsContent value="users">
          <Card className="p-6 space-y-6">
            <div className="space-y-1">
              <div className="text-sm font-medium text-slate-900">User management</div>
              <div className="text-xs text-slate-600">No auth backend is configured; this is local-only for now.</div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <div className="space-y-2 lg:col-span-2">
                <div className="text-xs text-slate-600">Name</div>
                <Input value={newUserName} onChange={(e) => setNewUserName(e.target.value)} placeholder="User name" />
              </div>
              <div className="space-y-2">
                <div className="text-xs text-slate-600">Role</div>
                <Select value={newUserRole} onValueChange={setNewUserRole}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="user">User</SelectItem>
                    <SelectItem value="admin">Admin</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="flex justify-end">
              <Button onClick={addUser}>Add user</Button>
            </div>

            <div className="space-y-3">
              <div className="text-sm font-medium">Users</div>
              {users.length === 0 ? <div className="text-sm text-slate-600">No users.</div> : null}

              {users.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Role</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {users.map((u) => (
                      <TableRow key={u.id}>
                        <TableCell>{u.name}</TableCell>
                        <TableCell>
                          <Badge variant="outline" className="text-slate-600 border-slate-300">
                            {u.role}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button variant="outline" size="sm" onClick={() => deleteUser(u.id)}>
                            Remove
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : null}
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="health">
          <Card className="p-6 space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div className="space-y-1">
                <div className="text-sm font-medium text-slate-900">Service health</div>
                <div className="text-xs text-slate-600">Checks /health for services and /api/tags for Ollama.</div>
              </div>
              <Button onClick={refreshHealth} disabled={loadingHealth}>
                {loadingHealth ? "Refreshing..." : "Refresh"}
              </Button>
            </div>

            {healthRows.length === 0 ? (
              <div className="text-sm text-slate-600">No data yet. Click Refresh.</div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Service</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Response</TableHead>
                    <TableHead>URL</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {healthRows.map((r) => (
                    <TableRow key={r.service}>
                      <TableCell className="font-medium">{r.service}</TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={
                            r.status === "healthy"
                              ? "bg-green-50 text-green-700 border-green-200"
                              : "bg-orange-50 text-orange-700 border-orange-200"
                          }
                        >
                          {r.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-xs text-slate-600">{r.response_time_ms} ms</TableCell>
                      <TableCell className="text-xs text-slate-600">{r.url}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </Card>
        </TabsContent>

        <TabsContent value="ai">
          <Card className="p-6 space-y-6">
            <div className="space-y-1">
              <div className="text-sm font-medium text-slate-900">AI inclusion</div>
              <div className="text-xs text-slate-600">Remote LLM connections and prompt templates.</div>
            </div>

            <div className="space-y-3">
              <div className="text-sm font-medium text-slate-900">LLM connections</div>
              <div className="text-xs text-slate-600">
                Add remote LLM providers (Azure, AWS, Google, OpenAI, etc.). API keys are stored in the git service.
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
                <div className="space-y-2">
                  <div className="text-xs text-slate-600">Provider</div>
                  <Select value={newLlmProvider} onValueChange={setNewLlmProvider}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="openai">OpenAI</SelectItem>
                      <SelectItem value="azure">Azure</SelectItem>
                      <SelectItem value="aws">AWS</SelectItem>
                      <SelectItem value="google">Google</SelectItem>
                      <SelectItem value="other">Other</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <div className="text-xs text-slate-600">Name</div>
                  <Input value={newLlmName} onChange={(e) => setNewLlmName(e.target.value)} placeholder="e.g. openai-prod" />
                </div>

                <div className="space-y-2 lg:col-span-2">
                  <div className="text-xs text-slate-600">Base URL</div>
                  <Input
                    value={newLlmBaseUrl}
                    onChange={(e) => setNewLlmBaseUrl(e.target.value)}
                    placeholder="e.g. https://api.openai.com/v1"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
                <div className="space-y-2 lg:col-span-2">
                  <div className="text-xs text-slate-600">API key</div>
                  <Input
                    type="password"
                    value={newLlmApiKey}
                    onChange={(e) => setNewLlmApiKey(e.target.value)}
                    placeholder="Paste API key"
                  />
                </div>

                <div className="space-y-2 lg:col-span-2">
                  <div className="text-xs text-slate-600">Default model (optional)</div>
                  <Input
                    value={newLlmDefaultModel}
                    onChange={(e) => setNewLlmDefaultModel(e.target.value)}
                    placeholder="e.g. gpt-4o-mini"
                  />
                </div>
              </div>

              <div className="flex justify-end">
                <Button
                  onClick={async () => {
                    try {
                      await llmConnectionsAPI.create({
                        provider: newLlmProvider,
                        name: newLlmName.trim(),
                        base_url: newLlmBaseUrl.trim(),
                        api_key: newLlmApiKey,
                        default_model: newLlmDefaultModel.trim() || null,
                      });
                      setNewLlmName("");
                      setNewLlmBaseUrl("");
                      setNewLlmApiKey("");
                      setNewLlmDefaultModel("");
                      toast.success("LLM connection saved");
                      await refreshLlmConnections();
                    } catch (e) {
                      console.error("Failed to create LLM connection", e);
                      const msg = e?.response?.data?.detail || e?.message || "Failed to save LLM connection";
                      toast.error(msg);
                    }
                  }}
                >
                  Add connection
                </Button>
              </div>

              {loadingLlmConnections ? <div className="text-sm text-slate-600">Loading connections…</div> : null}
              {!loadingLlmConnections && llmConnections.length === 0 ? (
                <div className="text-sm text-slate-600">No LLM connections.</div>
              ) : null}

              {llmConnections.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Provider</TableHead>
                      <TableHead>Name</TableHead>
                      <TableHead>Base URL</TableHead>
                      <TableHead>Model</TableHead>
                      <TableHead>API key</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {llmConnections.map((c) => (
                      <TableRow key={c.id}>
                        <TableCell>
                          <Badge variant="outline" className="text-slate-600 border-slate-300">
                            {c.provider}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-slate-800">{c.name}</TableCell>
                        <TableCell className="text-xs text-slate-600">{c.base_url}</TableCell>
                        <TableCell className="text-xs text-slate-600">{c.default_model || "—"}</TableCell>
                        <TableCell className="font-mono text-xs text-slate-600">{c.api_key_masked || "—"}</TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={async () => {
                              try {
                                await llmConnectionsAPI.delete(c.id);
                                toast.success("Connection deleted");
                                await refreshLlmConnections();
                              } catch (e) {
                                console.error("Failed to delete LLM connection", e);
                                toast.error("Failed to delete connection");
                              }
                            }}
                          >
                            Delete
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : null}
            </div>

            <div className="space-y-2">
              <div className="text-xs text-slate-600">Testcase analysis prompt</div>
              <Textarea
                value={aiPrompts.testcaseAnalysisPrompt}
                onChange={(e) => setAiPrompts((p) => ({ ...p, testcaseAnalysisPrompt: e.target.value }))}
                className="min-h-[120px] text-sm"
              />
            </div>

            <div className="space-y-2">
              <div className="text-xs text-slate-600">Automation chat prompt</div>
              <Textarea
                value={aiPrompts.automationChatPrompt}
                onChange={(e) => setAiPrompts((p) => ({ ...p, automationChatPrompt: e.target.value }))}
                className="min-h-[120px] text-sm"
              />
            </div>

            <div className="space-y-2">
              <div className="text-xs text-slate-600">Testcase migration prompt</div>
              <Textarea
                value={aiPrompts.testcaseMigrationPrompt}
                onChange={(e) => setAiPrompts((p) => ({ ...p, testcaseMigrationPrompt: e.target.value }))}
                className="min-h-[120px] text-sm"
              />
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="approach">
          <Card className="p-6 space-y-4">
            <div className="space-y-1">
              <div className="text-sm font-medium text-slate-900">Test approach</div>
              <div className="text-xs text-slate-600">Local-only placeholder until a settings backend is added.</div>
            </div>
            <Textarea
              value={testApproach}
              onChange={(e) => setTestApproach(e.target.value)}
              className="min-h-[260px] text-sm"
              placeholder="Describe your test approach..."
            />
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
