import React, { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from "@/components/ui/collapsible";
import { toast } from "sonner";
import {
  FileText, FileCode2, GitMerge, Loader2, Plus, Check, AlertCircle,
  ChevronDown, ChevronRight, ExternalLink, Search, Download, Ticket,
} from "lucide-react";
import gitRepoConnectionsAPI from "@/api/gitRepoConnectionsClient";
import { requirementsAPI } from "@/api/requirementsClient";
import { useQuery, useQueryClient } from "@tanstack/react-query";

export default function ExtractRequirements() {
  const queryClient = useQueryClient();

  // --- Shared ---
  const [extractedRequirements, setExtractedRequirements] = useState([]);
  const [selectedForImport, setSelectedForImport] = useState(new Set());
  const [importing, setImporting] = useState(false);

  // --- Jira state ---
  const [jiraUrl, setJiraUrl] = useState("");
  const [jiraEmail, setJiraEmail] = useState("");
  const [jiraToken, setJiraToken] = useState("");
  const [jiraProject, setJiraProject] = useState("");
  const [jiraJQL, setJiraJQL] = useState("");
  const [jiraTesting, setJiraTesting] = useState(false);
  const [jiraConnected, setJiraConnected] = useState(false);
  const [jiraLoading, setJiraLoading] = useState(false);

  // --- Code repo state ---
  const [selectedRepoId, setSelectedRepoId] = useState("");
  const [codePath, setCodePath] = useState("");
  const [codeLoading, setCodeLoading] = useState(false);

  // --- Merge request state ---
  const [mrRepoId, setMrRepoId] = useState("");
  const [mrProvider, setMrProvider] = useState("");
  const [mrNumber, setMrNumber] = useState("");
  const [mrLoading, setMrLoading] = useState(false);

  // --- Load repos ---
  const { data: repos = [] } = useQuery({
    queryKey: ["repoConnections"],
    queryFn: () => gitRepoConnectionsAPI.list(),
  });

  const appRepos = useMemo(
    () => repos.filter((r) => r.repo_type === "application_repository"),
    [repos],
  );
  const repoList = appRepos.length > 0 ? appRepos : repos;

  // ─── Jira handlers ──────────────────────────────────────────────────
  const handleTestJira = async () => {
    if (!jiraUrl || !jiraEmail || !jiraToken) {
      toast.error("Please fill in all Jira connection fields");
      return;
    }
    setJiraTesting(true);
    try {
      const { default: testJiraConnection } = await import("../../functions/testJiraConnection");
      const result = await testJiraConnection({ jira_url: jiraUrl, email: jiraEmail, api_token: jiraToken });
      if (result.success) {
        setJiraConnected(true);
        toast.success(result.message);
      } else {
        toast.error(result.message);
      }
    } catch (e) {
      toast.error("Failed to test Jira connection: " + e.message);
    } finally {
      setJiraTesting(false);
    }
  };

  const handleExtractFromJira = async () => {
    if (!jiraConnected) {
      toast.error("Please test and connect to Jira first");
      return;
    }
    setJiraLoading(true);
    setExtractedRequirements([]);
    setSelectedForImport(new Set());
    try {
      // Build JQL or use default
      const jql = jiraJQL || (jiraProject ? `project = "${jiraProject}" ORDER BY created DESC` : "ORDER BY created DESC");
      const baseUrl = jiraUrl.endsWith("/") ? jiraUrl.slice(0, -1) : jiraUrl;
      const authToken = btoa(`${jiraEmail}:${jiraToken}`);

      const response = await fetch(
        `${baseUrl}/rest/api/3/search?jql=${encodeURIComponent(jql)}&maxResults=50&fields=summary,description,issuetype,status,priority`,
        {
          headers: {
            Authorization: `Basic ${authToken}`,
            Accept: "application/json",
          },
        },
      );
      if (!response.ok) throw new Error(`Jira API error: ${response.status}`);
      const data = await response.json();

      const reqs = (data.issues || []).map((issue) => ({
        id: issue.key,
        title: `[${issue.key}] ${issue.fields.summary}`,
        description: _extractJiraDescription(issue.fields.description),
        source: "jira",
        tags: [issue.fields.issuetype?.name, issue.fields.priority?.name].filter(Boolean),
        meta: { jira_key: issue.key, status: issue.fields.status?.name },
      }));

      setExtractedRequirements(reqs);
      setSelectedForImport(new Set(reqs.map((r) => r.id)));
      toast.success(`Found ${reqs.length} issue(s) from Jira`);
    } catch (e) {
      toast.error("Failed to fetch from Jira: " + e.message);
    } finally {
      setJiraLoading(false);
    }
  };

  // ─── Code repo handlers ─────────────────────────────────────────────
  const handleExtractFromCode = async () => {
    if (!selectedRepoId) {
      toast.error("Please select a repository");
      return;
    }
    setCodeLoading(true);
    setExtractedRequirements([]);
    setSelectedForImport(new Set());
    try {
      // Placeholder — backend endpoint not yet implemented
      // Would call: POST /requirements/extract-from-code { connection_id, path }
      await new Promise((r) => setTimeout(r, 1500));
      toast.info("Code-based requirement extraction is coming soon. The backend endpoint is not yet available.");
      setExtractedRequirements([
        {
          id: "code-placeholder-1",
          title: "Example: User authentication flow",
          description: "Extracted from code analysis — login/logout functionality detected in the application repository.",
          source: "code-analysis",
          tags: ["auto-extracted", "authentication"],
          meta: { files: ["src/auth/login.tsx", "src/auth/logout.tsx"] },
        },
      ]);
      setSelectedForImport(new Set(["code-placeholder-1"]));
    } catch (e) {
      toast.error("Extraction failed: " + e.message);
    } finally {
      setCodeLoading(false);
    }
  };

  // ─── Merge request handlers ─────────────────────────────────────────
  const handleExtractFromMR = async () => {
    if (!mrRepoId || !mrNumber) {
      toast.error("Please select a repo and enter a merge/pull request number");
      return;
    }
    setMrLoading(true);
    setExtractedRequirements([]);
    setSelectedForImport(new Set());
    try {
      // Placeholder — backend endpoint not yet implemented
      // Would call: POST /requirements/extract-from-mr { connection_id, mr_number, provider }
      await new Promise((r) => setTimeout(r, 1500));
      toast.info("MR-based requirement extraction is coming soon. The backend endpoint is not yet available.");
      setExtractedRequirements([
        {
          id: "mr-placeholder-1",
          title: `Example: Changes from MR #${mrNumber}`,
          description: `Extracted from merge request #${mrNumber} — code diff analysis would identify testable changes.`,
          source: "merge-request",
          tags: ["auto-extracted", "merge-request"],
          meta: { mr_number: mrNumber },
        },
      ]);
      setSelectedForImport(new Set(["mr-placeholder-1"]));
    } catch (e) {
      toast.error("Extraction failed: " + e.message);
    } finally {
      setMrLoading(false);
    }
  };

  // ─── Import selected requirements ──────────────────────────────────
  const handleImportSelected = async () => {
    const toImport = extractedRequirements.filter((r) => selectedForImport.has(r.id));
    if (toImport.length === 0) {
      toast.error("No requirements selected for import");
      return;
    }
    setImporting(true);
    let succeeded = 0;
    try {
      for (const req of toImport) {
        await requirementsAPI.create({
          title: req.title,
          description: req.description || "",
          source: req.source,
          tags: req.tags || [],
        });
        succeeded++;
      }
      toast.success(`Imported ${succeeded} requirement(s) successfully`);
      queryClient.invalidateQueries({ queryKey: ["requirements"] });
      setExtractedRequirements([]);
      setSelectedForImport(new Set());
    } catch (e) {
      toast.error(`Imported ${succeeded}/${toImport.length} — error: ${e.message}`);
    } finally {
      setImporting(false);
    }
  };

  const toggleSelect = (id) => {
    setSelectedForImport((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedForImport.size === extractedRequirements.length) {
      setSelectedForImport(new Set());
    } else {
      setSelectedForImport(new Set(extractedRequirements.map((r) => r.id)));
    }
  };

  const isLoading = jiraLoading || codeLoading || mrLoading;

  // ─── Render ────────────────────────────────────────────────────────
  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-gradient-to-br from-emerald-600 to-teal-700 rounded-xl flex items-center justify-center shadow-lg">
          <Download className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Extract Requirements</h1>
          <p className="text-sm text-slate-500">
            Import requirements from Jira, code repositories, or merge requests
          </p>
        </div>
      </div>

      {/* Source tabs */}
      <Tabs defaultValue="jira" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="jira" className="flex items-center gap-2">
            <Ticket className="w-4 h-4" /> Jira
          </TabsTrigger>
          <TabsTrigger value="code" className="flex items-center gap-2">
            <FileCode2 className="w-4 h-4" /> Code Repository
          </TabsTrigger>
          <TabsTrigger value="merge-request" className="flex items-center gap-2">
            <GitMerge className="w-4 h-4" /> Merge Request
          </TabsTrigger>
        </TabsList>

        {/* ── Jira Tab ───────────────────────────────────────────── */}
        <TabsContent value="jira">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Ticket className="w-5 h-5 text-blue-600" /> Import from Jira
              </CardTitle>
              <CardDescription>
                Connect to your Jira instance and import issues as requirements.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Jira URL</Label>
                  <Input
                    placeholder="https://your-org.atlassian.net"
                    value={jiraUrl}
                    onChange={(e) => setJiraUrl(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Email</Label>
                  <Input
                    placeholder="user@example.com"
                    value={jiraEmail}
                    onChange={(e) => setJiraEmail(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>API Token</Label>
                  <Input
                    type="password"
                    placeholder="Jira API token"
                    value={jiraToken}
                    onChange={(e) => setJiraToken(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Project Key (optional)</Label>
                  <Input
                    placeholder="e.g. PROJ"
                    value={jiraProject}
                    onChange={(e) => setJiraProject(e.target.value)}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label>Custom JQL (optional)</Label>
                <Input
                  placeholder='e.g. project = "PROJ" AND type = Story AND status != Done'
                  value={jiraJQL}
                  onChange={(e) => setJiraJQL(e.target.value)}
                />
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={handleTestJira} disabled={jiraTesting}>
                  {jiraTesting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <ExternalLink className="w-4 h-4 mr-2" />}
                  {jiraConnected ? "Connected ✓" : "Test Connection"}
                </Button>
                <Button onClick={handleExtractFromJira} disabled={!jiraConnected || jiraLoading}>
                  {jiraLoading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Search className="w-4 h-4 mr-2" />}
                  Fetch Issues
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Code Repository Tab ────────────────────────────────── */}
        <TabsContent value="code">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <FileCode2 className="w-5 h-5 text-violet-600" /> Extract from Code
              </CardTitle>
              <CardDescription>
                Analyze source code to automatically identify testable requirements and features.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Repository</Label>
                  <Select value={selectedRepoId} onValueChange={setSelectedRepoId}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select a repository…" />
                    </SelectTrigger>
                    <SelectContent>
                      {repoList.map((r) => (
                        <SelectItem key={r.id} value={r.id}>
                          {r.repo_url.split("/").slice(-2).join("/")}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Path filter (optional)</Label>
                  <Input
                    placeholder="e.g. src/features"
                    value={codePath}
                    onChange={(e) => setCodePath(e.target.value)}
                  />
                </div>
              </div>
              <Button onClick={handleExtractFromCode} disabled={!selectedRepoId || codeLoading}>
                {codeLoading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Search className="w-4 h-4 mr-2" />}
                Analyze Code
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Merge Request Tab ──────────────────────────────────── */}
        <TabsContent value="merge-request">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <GitMerge className="w-5 h-5 text-orange-600" /> Extract from Merge Request
              </CardTitle>
              <CardDescription>
                Analyze a merge/pull request diff to extract testable changes as requirements.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label>Repository</Label>
                  <Select value={mrRepoId} onValueChange={(v) => { setMrRepoId(v); const r = repos.find((x) => x.id === v); if (r) setMrProvider(r.provider || ""); }}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select a repository…" />
                    </SelectTrigger>
                    <SelectContent>
                      {repoList.map((r) => (
                        <SelectItem key={r.id} value={r.id}>
                          {r.repo_url.split("/").slice(-2).join("/")}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Provider</Label>
                  <Select value={mrProvider} onValueChange={setMrProvider}>
                    <SelectTrigger>
                      <SelectValue placeholder="Provider" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="github">GitHub</SelectItem>
                      <SelectItem value="gitlab">GitLab</SelectItem>
                      <SelectItem value="azure">Azure DevOps</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>MR / PR Number</Label>
                  <Input
                    type="number"
                    placeholder="e.g. 42"
                    value={mrNumber}
                    onChange={(e) => setMrNumber(e.target.value)}
                  />
                </div>
              </div>
              <Button onClick={handleExtractFromMR} disabled={!mrRepoId || !mrNumber || mrLoading}>
                {mrLoading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Search className="w-4 h-4 mr-2" />}
                Extract from MR
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* ── Extracted Requirements Results ──────────────────────────── */}
      {extractedRequirements.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-lg">Extracted Requirements</CardTitle>
                <CardDescription>
                  {selectedForImport.size} of {extractedRequirements.length} selected for import
                </CardDescription>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={toggleSelectAll}>
                  {selectedForImport.size === extractedRequirements.length ? "Deselect All" : "Select All"}
                </Button>
                <Button size="sm" onClick={handleImportSelected} disabled={selectedForImport.size === 0 || importing}>
                  {importing ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Plus className="w-4 h-4 mr-2" />}
                  Import Selected ({selectedForImport.size})
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {extractedRequirements.map((req) => (
                <div
                  key={req.id}
                  className={`flex items-start gap-3 p-3 rounded-lg border transition-colors cursor-pointer ${
                    selectedForImport.has(req.id) ? "bg-emerald-50 border-emerald-200" : "hover:bg-slate-50"
                  }`}
                  onClick={() => toggleSelect(req.id)}
                >
                  <Checkbox
                    checked={selectedForImport.has(req.id)}
                    onCheckedChange={() => toggleSelect(req.id)}
                    className="mt-0.5"
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-800">{req.title}</p>
                    {req.description && (
                      <p className="text-xs text-slate-500 mt-1 line-clamp-2">{req.description}</p>
                    )}
                    <div className="flex items-center gap-2 mt-2">
                      <Badge variant="outline" className="text-xs">{req.source}</Badge>
                      {req.tags?.map((t) => (
                        <Badge key={t} variant="secondary" className="text-xs">{t}</Badge>
                      ))}
                      {req.meta?.jira_key && (
                        <Badge className="bg-blue-100 text-blue-700 text-xs">{req.meta.jira_key}</Badge>
                      )}
                      {req.meta?.status && (
                        <Badge variant="outline" className="text-xs">{req.meta.status}</Badge>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Empty state when loading */}
      {isLoading && extractedRequirements.length === 0 && (
        <Card className="border-dashed">
          <CardContent className="py-12 flex flex-col items-center gap-3">
            <Loader2 className="w-8 h-8 text-emerald-600 animate-spin" />
            <p className="text-sm text-slate-500">Extracting requirements…</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────
function _extractJiraDescription(adf) {
  // ADF (Atlassian Document Format) → plain text
  if (!adf) return "";
  if (typeof adf === "string") return adf;
  try {
    const texts = [];
    const walk = (node) => {
      if (node.text) texts.push(node.text);
      if (node.content) node.content.forEach(walk);
    };
    walk(adf);
    return texts.join(" ").slice(0, 500);
  } catch {
    return JSON.stringify(adf).slice(0, 300);
  }
}
