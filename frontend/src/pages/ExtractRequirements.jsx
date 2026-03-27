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
  ChevronDown, ChevronRight, ExternalLink, Search, Download, Ticket, Upload, FileSpreadsheet, X,
  Sparkles, FolderTree, RefreshCw, Brain,
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
  const [codeProgress, setCodeProgress] = useState(null); // { stage, message, ... }
  const [codeFileExtensions, setCodeFileExtensions] = useState(""); // comma-separated: ".py,.tsx"
  const [codeAnalysisStats, setCodeAnalysisStats] = useState(null); // { files_analyzed, repo_url }

  // --- Merge request state ---
  const [mrRepoId, setMrRepoId] = useState("");
  const [mrProvider, setMrProvider] = useState("");
  const [mrNumber, setMrNumber] = useState("");
  const [mrLoading, setMrLoading] = useState(false);

  // --- File upload state ---
  const [uploadedFile, setUploadedFile] = useState(null);
  const [fileLoading, setFileLoading] = useState(false);
  const [titleColumn, setTitleColumn] = useState("");
  const [descriptionColumn, setDescriptionColumn] = useState("");
  const [detectedColumns, setDetectedColumns] = useState([]);

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
    setCodeProgress(null);
    setCodeAnalysisStats(null);
    setExtractedRequirements([]);
    setSelectedForImport(new Set());

    try {
      // Parse file extensions filter
      const extFilter = codeFileExtensions
        .split(",")
        .map((e) => e.trim())
        .filter(Boolean)
        .map((e) => (e.startsWith(".") ? e : `.${e}`));

      const response = await gitRepoConnectionsAPI.extractRequirementsStream(
        selectedRepoId,
        {
          path: codePath || null,
          file_extensions: extFilter.length > 0 ? extFilter : null,
        },
      );

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || `Server error: ${response.status}`);
      }

      // Read NDJSON stream
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const event = JSON.parse(line);
            if (event.type === "progress") {
              setCodeProgress(event);
            } else if (event.type === "requirements") {
              const reqs = (event.requirements || []).map((r, i) => ({
                id: `code-${i}`,
                title: r.title,
                description: r.description || "",
                source: "code-analysis",
                tags: r.tags || [],
                meta: {
                  source_files: r.source_files || [],
                  confidence: r.confidence || "medium",
                  repo_url: event.repo_url,
                },
              }));
              setExtractedRequirements(reqs);
              setSelectedForImport(new Set(reqs.map((r) => r.id)));
              setCodeAnalysisStats({
                files_analyzed: event.files_analyzed,
                repo_url: event.repo_url,
              });
              toast.success(`AI extracted ${reqs.length} requirement(s) from ${event.files_analyzed} files`);
            } else if (event.type === "error") {
              toast.error(event.message || "AI analysis failed");
            }
          } catch {
            // ignore malformed lines
          }
        }
      }
    } catch (e) {
      toast.error("Extraction failed: " + e.message);
    } finally {
      setCodeLoading(false);
      setCodeProgress(null);
    }
  };

  // Sync repo before extracting
  const handleSyncAndExtract = async () => {
    if (!selectedRepoId) return;
    try {
      setCodeProgress({ stage: "syncing", message: "Pulling latest changes from remote..." });
      setCodeLoading(true);
      await gitRepoConnectionsAPI.sync(selectedRepoId);
      toast.success("Repository synced");
    } catch (e) {
      toast.warning("Sync failed, analyzing existing checkout: " + (e.response?.data?.detail || e.message));
    }
    await handleExtractFromCode();
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

  // ─── File upload handlers ──────────────────────────────────────────
  const ACCEPTED_TYPES = {
    "text/csv": "csv",
    "application/vnd.ms-excel": "csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/pdf": "pdf",
    "application/msword": "doc",
  };

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const ext = file.name.split(".").pop().toLowerCase();
    const allowed = ["csv", "xlsx", "xls", "docx", "doc", "pdf"];
    if (!allowed.includes(ext)) {
      toast.error(`Unsupported file type: .${ext}. Supported: ${allowed.join(", ")}`);
      return;
    }
    setUploadedFile(file);
    setDetectedColumns([]);
    setTitleColumn("");
    setDescriptionColumn("");
    setExtractedRequirements([]);
    setSelectedForImport(new Set());

    // Auto-detect columns for CSV
    if (ext === "csv") {
      const reader = new FileReader();
      reader.onload = (ev) => {
        const text = ev.target.result;
        const firstLine = text.split(/\r?\n/)[0];
        // Try common delimiters
        const delimiter = firstLine.includes(";") ? ";" : ",";
        const cols = firstLine.split(delimiter).map((c) => c.replace(/^"|"$/g, "").trim());
        if (cols.length > 0) {
          setDetectedColumns(cols);
          // Auto-pick common column names
          const titleMatch = cols.find((c) => /^(title|name|summary|requirement|bezeichnung|anforderung)$/i.test(c));
          const descMatch = cols.find((c) => /^(description|desc|details|beschreibung|text|body)$/i.test(c));
          if (titleMatch) setTitleColumn(titleMatch);
          if (descMatch) setDescriptionColumn(descMatch);
        }
      };
      reader.readAsText(file);
    }
  };

  const handleExtractFromFile = async () => {
    if (!uploadedFile) {
      toast.error("Please select a file first");
      return;
    }
    setFileLoading(true);
    setExtractedRequirements([]);
    setSelectedForImport(new Set());

    const ext = uploadedFile.name.split(".").pop().toLowerCase();

    try {
      if (ext === "csv") {
        // Client-side CSV parsing
        const text = await uploadedFile.text();
        const lines = text.split(/\r?\n/).filter((l) => l.trim());
        if (lines.length < 2) {
          toast.error("CSV file is empty or has no data rows");
          setFileLoading(false);
          return;
        }
        const delimiter = lines[0].includes(";") ? ";" : ",";
        const headers = lines[0].split(delimiter).map((h) => h.replace(/^"|"$/g, "").trim());
        const tCol = titleColumn || headers[0];
        const dCol = descriptionColumn || (headers.length > 1 ? headers[1] : null);
        const tIdx = headers.indexOf(tCol);
        const dIdx = dCol ? headers.indexOf(dCol) : -1;

        if (tIdx === -1) {
          toast.error(`Title column "${tCol}" not found in CSV headers`);
          setFileLoading(false);
          return;
        }

        const reqs = lines.slice(1).map((line, i) => {
          const cells = line.split(delimiter).map((c) => c.replace(/^"|"$/g, "").trim());
          return {
            id: `file-${i}`,
            title: cells[tIdx] || `Row ${i + 1}`,
            description: dIdx >= 0 ? (cells[dIdx] || "") : "",
            source: "file-import",
            tags: ["csv"],
            meta: { filename: uploadedFile.name, row: i + 2 },
          };
        }).filter((r) => r.title.trim());

        setExtractedRequirements(reqs);
        setSelectedForImport(new Set(reqs.map((r) => r.id)));
        toast.success(`Parsed ${reqs.length} requirement(s) from CSV`);
      } else {
        // For xlsx, docx, pdf — send to backend
        const formData = new FormData();
        formData.append("file", uploadedFile);
        if (titleColumn) formData.append("title_column", titleColumn);
        if (descriptionColumn) formData.append("description_column", descriptionColumn);

        const response = await fetch("http://localhost:8001/requirements/extract-from-file", {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          const err = await response.json().catch(() => ({}));
          throw new Error(err.detail || `Server error: ${response.status}`);
        }

        const data = await response.json();
        const reqs = (data.requirements || []).map((r, i) => ({
          id: `file-${i}`,
          title: r.title || `Requirement ${i + 1}`,
          description: r.description || "",
          source: "file-import",
          tags: r.tags || [ext],
          meta: { filename: uploadedFile.name, ...(r.meta || {}) },
        }));

        setExtractedRequirements(reqs);
        setSelectedForImport(new Set(reqs.map((r) => r.id)));
        toast.success(`Extracted ${reqs.length} requirement(s) from ${ext.toUpperCase()} file`);
      }
    } catch (e) {
      toast.error("File extraction failed: " + e.message);
    } finally {
      setFileLoading(false);
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

  const isLoading = jiraLoading || codeLoading || mrLoading || fileLoading;

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
            Import requirements from files, Jira, code repositories, or merge requests
          </p>
        </div>
      </div>

      {/* Source tabs */}
      <Tabs defaultValue="file" className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="file" className="flex items-center gap-2">
            <Upload className="w-4 h-4" /> File Import
          </TabsTrigger>
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

        {/* ── File Upload Tab ──────────────────────────────────── */}
        <TabsContent value="file">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <FileSpreadsheet className="w-5 h-5 text-emerald-600" /> Import from File
              </CardTitle>
              <CardDescription>
                Upload a CSV, Excel (.xlsx), Word (.docx), or PDF file to extract requirements.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Drop zone / file input */}
              <div
                className="relative border-2 border-dashed rounded-xl p-8 text-center transition-colors hover:border-emerald-400 hover:bg-emerald-50/50"
                onDragOver={(e) => { e.preventDefault(); e.currentTarget.classList.add("border-emerald-400", "bg-emerald-50/50"); }}
                onDragLeave={(e) => { e.currentTarget.classList.remove("border-emerald-400", "bg-emerald-50/50"); }}
                onDrop={(e) => {
                  e.preventDefault();
                  e.currentTarget.classList.remove("border-emerald-400", "bg-emerald-50/50");
                  const file = e.dataTransfer.files?.[0];
                  if (file) handleFileSelect({ target: { files: [file] } });
                }}
              >
                <input
                  type="file"
                  accept=".csv,.xlsx,.xls,.docx,.doc,.pdf"
                  onChange={handleFileSelect}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                />
                <Upload className="w-10 h-10 text-slate-400 mx-auto mb-3" />
                <p className="text-sm font-medium text-slate-700">Drop a file here or click to browse</p>
                <p className="text-xs text-slate-400 mt-1">Supported: CSV, Excel (.xlsx), Word (.docx), PDF</p>
              </div>

              {/* Selected file info */}
              {uploadedFile && (
                <div className="flex items-center gap-3 p-3 bg-slate-50 rounded-lg border">
                  <FileSpreadsheet className="w-5 h-5 text-emerald-600 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-800 truncate">{uploadedFile.name}</p>
                    <p className="text-xs text-slate-500">{(uploadedFile.size / 1024).toFixed(1)} KB</p>
                  </div>
                  <Button variant="ghost" size="icon" onClick={() => { setUploadedFile(null); setDetectedColumns([]); setTitleColumn(""); setDescriptionColumn(""); }}>
                    <X className="w-4 h-4" />
                  </Button>
                </div>
              )}

              {/* Column mapping for CSV/Excel */}
              {uploadedFile && detectedColumns.length > 0 && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 p-4 bg-blue-50/50 rounded-lg border border-blue-100">
                  <div className="space-y-2">
                    <Label>Title Column</Label>
                    <Select value={titleColumn} onValueChange={setTitleColumn}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select title column…" />
                      </SelectTrigger>
                      <SelectContent>
                        {detectedColumns.map((col) => (
                          <SelectItem key={col} value={col}>{col}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Description Column (optional)</Label>
                    <Select value={descriptionColumn} onValueChange={setDescriptionColumn}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select description column…" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__none__">— None —</SelectItem>
                        {detectedColumns.map((col) => (
                          <SelectItem key={col} value={col}>{col}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              )}

              <Button onClick={handleExtractFromFile} disabled={!uploadedFile || fileLoading}>
                {fileLoading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Search className="w-4 h-4 mr-2" />}
                Extract Requirements
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

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
                <FileCode2 className="w-5 h-5 text-violet-600" /> Extract from Code Repository
              </CardTitle>
              <CardDescription>
                Analyze source code with AI to automatically identify testable requirements, features, and user interactions.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              {/* Repo selection & path */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Repository</Label>
                  <Select value={selectedRepoId} onValueChange={setSelectedRepoId}>
                    <SelectTrigger>
                      <SelectValue placeholder="Select a connected repository…" />
                    </SelectTrigger>
                    <SelectContent>
                      {repoList.map((r) => (
                        <SelectItem key={r.id} value={r.id}>
                          <span className="flex items-center gap-2">
                            <span>{r.repo_url.split("/").slice(-2).join("/")}</span>
                            {r.repo_type === "application_repository" && (
                              <Badge variant="secondary" className="text-[10px] px-1.5 py-0">App</Badge>
                            )}
                          </span>
                        </SelectItem>
                      ))}
                      {repoList.length === 0 && (
                        <div className="p-3 text-sm text-slate-500 text-center">
                          No repositories connected. Connect one in Settings → Git.
                        </div>
                      )}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Path filter (optional)</Label>
                  <Input
                    placeholder="e.g. src/features or src/pages"
                    value={codePath}
                    onChange={(e) => setCodePath(e.target.value)}
                  />
                  <p className="text-xs text-slate-400">Limit analysis to a subdirectory</p>
                </div>
              </div>

              {/* Advanced options */}
              <Collapsible>
                <CollapsibleTrigger className="flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700 transition-colors">
                  <ChevronRight className="w-4 h-4 ui-open:rotate-90 transition-transform" />
                  Advanced Options
                </CollapsibleTrigger>
                <CollapsibleContent className="pt-3">
                  <div className="space-y-2">
                    <Label>File extensions (optional)</Label>
                    <Input
                      placeholder="e.g. .py, .tsx, .jsx, .ts"
                      value={codeFileExtensions}
                      onChange={(e) => setCodeFileExtensions(e.target.value)}
                    />
                    <p className="text-xs text-slate-400">
                      Comma-separated list. Leave empty to scan all supported file types
                      (.py, .js, .tsx, .java, .go, .md, etc.)
                    </p>
                  </div>
                </CollapsibleContent>
              </Collapsible>

              {/* Progress indicator */}
              {codeLoading && codeProgress && (
                <div className="p-4 bg-violet-50 border border-violet-200 rounded-lg space-y-3">
                  <div className="flex items-center gap-2 text-sm font-medium text-violet-700">
                    {codeProgress.stage === "syncing" && <RefreshCw className="w-4 h-4 animate-spin" />}
                    {codeProgress.stage === "scanning" && <FolderTree className="w-4 h-4" />}
                    {codeProgress.stage === "analyzing" && <Brain className="w-4 h-4 animate-pulse" />}
                    {codeProgress.message}
                  </div>
                  {codeProgress.stage === "analyzing" && (
                    <div className="space-y-1">
                      <div className="h-1.5 w-full bg-violet-100 rounded-full overflow-hidden">
                        <div className="h-full w-1/3 bg-violet-500 rounded-full animate-[indeterminate_1.5s_ease-in-out_infinite]"
                          style={{ animation: "indeterminate 1.5s ease-in-out infinite" }}
                        />
                        <style>{`@keyframes indeterminate { 0% { transform: translateX(-100%); } 100% { transform: translateX(400%); } }`}</style>
                      </div>
                      <p className="text-xs text-violet-500">AI is reading source code and identifying requirements…</p>
                    </div>
                  )}
                </div>
              )}

              {/* Analysis stats */}
              {codeAnalysisStats && !codeLoading && extractedRequirements.length > 0 && (
                <div className="flex items-center gap-4 text-xs text-slate-500">
                  <span className="flex items-center gap-1">
                    <Sparkles className="w-3.5 h-3.5 text-violet-500" />
                    {extractedRequirements.length} requirements extracted
                  </span>
                  <span>{codeAnalysisStats.files_analyzed} files analyzed</span>
                </div>
              )}

              {/* Action buttons */}
              <div className="flex gap-2">
                <Button
                  onClick={handleSyncAndExtract}
                  disabled={!selectedRepoId || codeLoading}
                  className="bg-violet-600 hover:bg-violet-700"
                >
                  {codeLoading ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <Sparkles className="w-4 h-4 mr-2" />
                  )}
                  {codeLoading ? "Analyzing…" : "Sync & Extract Requirements"}
                </Button>
                <Button
                  variant="outline"
                  onClick={handleExtractFromCode}
                  disabled={!selectedRepoId || codeLoading}
                >
                  {codeLoading ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <Search className="w-4 h-4 mr-2" />
                  )}
                  Analyze Without Sync
                </Button>
              </div>
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
                    {/* Source files (for code-analysis) */}
                    {req.meta?.source_files?.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {req.meta.source_files.slice(0, 4).map((f) => (
                          <span key={f} className="text-[10px] text-violet-600 bg-violet-50 rounded px-1.5 py-0.5 font-mono">
                            {f}
                          </span>
                        ))}
                        {req.meta.source_files.length > 4 && (
                          <span className="text-[10px] text-slate-400">+{req.meta.source_files.length - 4} more</span>
                        )}
                      </div>
                    )}
                    <div className="flex items-center gap-2 mt-2">
                      <Badge variant="outline" className="text-xs">{req.source}</Badge>
                      {req.meta?.confidence && (
                        <Badge
                          variant="outline"
                          className={`text-xs ${
                            req.meta.confidence === "high" ? "border-green-300 text-green-700 bg-green-50" :
                            req.meta.confidence === "medium" ? "border-yellow-300 text-yellow-700 bg-yellow-50" :
                            "border-slate-300 text-slate-600"
                          }`}
                        >
                          {req.meta.confidence} confidence
                        </Badge>
                      )}
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
