import React, { useState, useEffect, useMemo, useRef, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from "@/components/ui/collapsible";
import { toast } from "sonner";
import { Crosshair, FolderSearch, Loader2, FileCode2, ChevronDown, ChevronRight, Copy, Check, AlertCircle, Code2, Plus, Minus } from "lucide-react";
import gitRepoConnectionsAPI from "@/api/gitRepoConnectionsClient";
import locatorsAPI from "@/api/locatorsClient";

export default function Locators() {
  // --- state ---
  const [repos, setRepos] = useState([]);
  const [selectedRepoId, setSelectedRepoId] = useState("");
  const [subPath, setSubPath] = useState("");
  const [previewFiles, setPreviewFiles] = useState(null);
  const [selectedFiles, setSelectedFiles] = useState(new Set());
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  // Streamed results: accumulated incrementally per file
  const [results, setResults] = useState([]); // [{file, previous_locators, locators, code, message}, ...]
  const [metadata, setMetadata] = useState(null);
  const [filesScanned, setFilesScanned] = useState(0);
  const [totalFiles, setTotalFiles] = useState(0);
  const [expandedFiles, setExpandedFiles] = useState(new Set());
  const [expandedCode, setExpandedCode] = useState(new Set());
  const [copiedId, setCopiedId] = useState(null);
  const abortRef = useRef(null);

  // Load connected repos on mount
  useEffect(() => {
    (async () => {
      try {
        const list = await gitRepoConnectionsAPI.list();
        setRepos(list);
      } catch {
        toast.error("Failed to load repositories");
      }
    })();
  }, []);

  const appRepos = useMemo(
    () => repos.filter((r) => r.repo_type === "application_repository"),
    [repos]
  );

  // --- preview files ---
  const handlePreviewFiles = async () => {
    if (!selectedRepoId) return;
    setLoadingFiles(true);
    setPreviewFiles(null);
    setSelectedFiles(new Set());
    try {
      const data = await locatorsAPI.listFiles(selectedRepoId, subPath || null);
      setPreviewFiles(data);
      // Auto-select all files
      setSelectedFiles(new Set(data.files));
    } catch (e) {
      const msg = e.response?.data?.detail || e.response?.data?.message || e.message;
      toast.error(msg);
    } finally {
      setLoadingFiles(false);
    }
  };

  const toggleFileSelection = (file) => {
    setSelectedFiles((prev) => {
      const next = new Set(prev);
      next.has(file) ? next.delete(file) : next.add(file);
      return next;
    });
  };

  const toggleAllFiles = () => {
    if (!previewFiles) return;
    if (selectedFiles.size === previewFiles.files.length) {
      setSelectedFiles(new Set());
    } else {
      setSelectedFiles(new Set(previewFiles.files));
    }
  };

  // --- analyze (streaming) ---
  const handleAnalyze = useCallback(async () => {
    if (!selectedRepoId) return;

    // Abort any previous in-flight analysis
    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setAnalyzing(true);
    setResults([]);
    setMetadata(null);
    setFilesScanned(0);
    setTotalFiles(0);
    setExpandedFiles(new Set());
    setExpandedCode(new Set());

    try {
      const filesToAnalyze = selectedFiles.size > 0 ? [...selectedFiles] : null;
      await locatorsAPI.analyzeStream(
        selectedRepoId,
        subPath || null,
        (event) => {
          switch (event.type) {
            case "metadata":
              setMetadata(event);
              setTotalFiles(event.total_files);
              break;
            case "file_result":
              setResults((prev) => [...prev, event]);
              setFilesScanned(event.files_scanned_so_far);
              // Auto-expand newly arriving files
              setExpandedFiles((prev) => {
                const next = new Set(prev);
                next.add(event.file);
                return next;
              });
              break;
            case "done":
              setFilesScanned(event.files_scanned);
              break;
          }
        },
        controller.signal,
        filesToAnalyze,
      );
      // Stream complete
      setResults((prev) => {
        const withLocators = prev.filter((r) => r.locators && r.locators.length > 0);
        if (withLocators.length === 0) {
          toast.info("Analysis complete — no locators added.");
        } else {
          const total = withLocators.reduce((s, r) => s + r.locators.length, 0);
          toast.success(`Done! ${total} locator(s) added across ${withLocators.length} file(s)`);
        }
        return prev;
      });
    } catch (e) {
      if (e.name === "AbortError") return;
      const msg = e.message || "Analysis failed";
      toast.error(msg);
    } finally {
      setAnalyzing(false);
      abortRef.current = null;
    }
  }, [selectedRepoId, subPath, selectedFiles]);

  const toggleFile = (file) => {
    setExpandedFiles((prev) => {
      const next = new Set(prev);
      next.has(file) ? next.delete(file) : next.add(file);
      return next;
    });
  };

  const toggleCode = (file) => {
    setExpandedCode((prev) => {
      const next = new Set(prev);
      next.has(file) ? next.delete(file) : next.add(file);
      return next;
    });
  };

  const copyToClipboard = (text, id) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  const totalLocators = results.reduce((s, r) => s + (r.locators?.length || 0), 0);
  const totalPrevious = results.reduce((s, r) => s + (r.previous_locators?.length || 0), 0);
  const newLocatorCount = totalLocators - totalPrevious;

  // --- render ---
  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-gradient-to-br from-violet-600 to-purple-700 rounded-xl flex items-center justify-center shadow-lg">
          <Crosshair className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Locator Analysis</h1>
          <p className="text-sm text-slate-500">
            AI-powered <code className="text-xs bg-slate-100 px-1 rounded">data-testid</code> insertion for your frontend
          </p>
        </div>
      </div>

      {/* Controls */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">Select Repository</CardTitle>
          <CardDescription>
            Choose an application repository to scan for frontend components.
            {appRepos.length === 0 && repos.length > 0 && (
              <span className="text-amber-600 ml-1">
                No repos tagged as "application repository" — showing all connected repos.
              </span>
            )}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-3">
            <Select value={selectedRepoId} onValueChange={(v) => { setSelectedRepoId(v); setPreviewFiles(null); setSelectedFiles(new Set()); setResults([]); setMetadata(null); setFilesScanned(0); setTotalFiles(0); }}>
              <SelectTrigger className="flex-1">
                <SelectValue placeholder="Select a repository…" />
              </SelectTrigger>
              <SelectContent>
                {(appRepos.length > 0 ? appRepos : repos).map((r) => (
                  <SelectItem key={r.id} value={r.id}>
                    {r.repo_url.split("/").slice(-2).join("/")} {r.repo_type && <span className="text-xs text-slate-400 ml-1">({r.repo_type.replace("_", " ")})</span>}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input
              className="sm:w-56"
              placeholder="Sub-path filter (e.g. src/pages)"
              value={subPath}
              onChange={(e) => setSubPath(e.target.value)}
            />
          </div>

          <div className="flex gap-2">
            <Button variant="outline" onClick={handlePreviewFiles} disabled={!selectedRepoId || loadingFiles}>
              {loadingFiles ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <FolderSearch className="w-4 h-4 mr-2" />}
              Preview Files
            </Button>
            <Button onClick={handleAnalyze} disabled={!selectedRepoId || analyzing || (previewFiles && selectedFiles.size === 0)}>
              {analyzing ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Crosshair className="w-4 h-4 mr-2" />}
              {analyzing ? "Analyzing…" : selectedFiles.size > 0 ? `Analyze ${selectedFiles.size} File(s)` : "Analyze Locators"}
            </Button>
          </div>

          {/* File preview with selection */}
          {previewFiles && (
            <div className="border rounded-lg p-3 bg-slate-50 max-h-72 overflow-auto">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium text-slate-700">
                  {previewFiles.count} frontend file(s) found
                </p>
                <button
                  onClick={toggleAllFiles}
                  className="text-xs text-violet-600 hover:text-violet-800 font-medium"
                >
                  {selectedFiles.size === previewFiles.files.length ? "Deselect All" : "Select All"}
                </button>
              </div>
              <div className="text-xs text-slate-600 space-y-0.5 font-mono">
                {previewFiles.files.map((f) => (
                  <label
                    key={f}
                    className={`flex items-center gap-2 px-2 py-1 rounded cursor-pointer transition-colors ${
                      selectedFiles.has(f) ? "bg-violet-50" : "hover:bg-slate-100"
                    }`}
                  >
                    <Checkbox
                      checked={selectedFiles.has(f)}
                      onCheckedChange={() => toggleFileSelection(f)}
                      className="h-3.5 w-3.5"
                    />
                    <FileCode2 className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    <span className={selectedFiles.has(f) ? "text-slate-800" : "text-slate-500"}>
                      {f}
                    </span>
                  </label>
                ))}
              </div>
              {selectedFiles.size > 0 && selectedFiles.size < previewFiles.files.length && (
                <p className="text-xs text-violet-600 mt-2">
                  {selectedFiles.size} of {previewFiles.count} files selected for analysis
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Analyzing indicator */}
      {analyzing && (
        <Card className="border-violet-200 bg-violet-50/50">
          <CardContent className="py-8 flex flex-col items-center gap-3">
            <Loader2 className="w-8 h-8 text-violet-600 animate-spin" />
            <p className="text-sm text-violet-700 font-medium">
              AI is analyzing your frontend code…
            </p>
            {totalFiles > 0 && (
              <div className="w-full max-w-xs">
                <div className="flex justify-between text-xs text-violet-500 mb-1">
                  <span>{filesScanned} / {totalFiles} files scanned</span>
                  <span>{Math.round((filesScanned / totalFiles) * 100)}%</span>
                </div>
                <div className="h-2 bg-violet-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-violet-600 rounded-full transition-all duration-500"
                    style={{ width: `${(filesScanned / totalFiles) * 100}%` }}
                  />
                </div>
              </div>
            )}
            <p className="text-xs text-violet-500">Results appear below as each file completes.</p>
          </CardContent>
        </Card>
      )}

      {/* Results */}
      {results.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-800">
              Results
              <Badge variant="secondary" className="ml-2">{filesScanned} files scanned</Badge>
              <Badge className="ml-2 bg-violet-100 text-violet-700">{totalLocators} locator(s)</Badge>
              {newLocatorCount > 0 && (
                <Badge className="ml-2 bg-green-100 text-green-700">+{newLocatorCount} new</Badge>
              )}
              {analyzing && <Loader2 className="inline w-4 h-4 ml-2 animate-spin text-violet-500" />}
            </h2>
          </div>

          {results.map((fileResult) => {
            const hasError = !!fileResult.error;
            const newLocs = (fileResult.locators || []).filter(
              (l) => !(fileResult.previous_locators || []).some((p) => p.locator === l.locator)
            );
            const existingLocs = (fileResult.previous_locators || []);

            return (
              <Collapsible
                key={fileResult.file}
                open={expandedFiles.has(fileResult.file)}
                onOpenChange={() => toggleFile(fileResult.file)}
              >
                <Card className={`overflow-hidden ${hasError ? "border-red-200" : ""}`}>
                  <CollapsibleTrigger className="w-full">
                    <div className="flex items-center gap-3 px-4 py-3 hover:bg-slate-50 transition-colors cursor-pointer">
                      {expandedFiles.has(fileResult.file) ? (
                        <ChevronDown className="w-4 h-4 text-slate-500" />
                      ) : (
                        <ChevronRight className="w-4 h-4 text-slate-500" />
                      )}
                      <FileCode2 className={`w-4 h-4 ${hasError ? "text-red-500" : "text-violet-500"}`} />
                      <span className="font-mono text-sm text-slate-800">{fileResult.file}</span>
                      <div className="ml-auto flex items-center gap-2">
                        {existingLocs.length > 0 && (
                          <Badge variant="secondary">{existingLocs.length} existing</Badge>
                        )}
                        {newLocs.length > 0 && (
                          <Badge className="bg-green-100 text-green-700">{newLocs.length} new</Badge>
                        )}
                        {hasError && (
                          <Badge variant="destructive">error</Badge>
                        )}
                      </div>
                    </div>
                  </CollapsibleTrigger>
                  <CollapsibleContent>
                    <div className="border-t">
                      {/* AI message */}
                      {fileResult.message && (
                        <div className={`px-4 py-2 text-xs ${hasError ? "bg-red-50 text-red-600" : "bg-blue-50 text-blue-700"}`}>
                          {fileResult.message}
                        </div>
                      )}

                      {/* New locators */}
                      {newLocs.length > 0 && (
                        <div className="px-4 py-3 space-y-2">
                          <p className="text-xs font-semibold text-green-700 flex items-center gap-1">
                            <Plus className="w-3.5 h-3.5" /> New locators added
                          </p>
                          <div className="space-y-1">
                            {newLocs.map((loc, idx) => {
                              const uid = `${fileResult.file}-new-${idx}`;
                              return (
                                <div key={uid} className="flex items-center justify-between gap-2 text-xs bg-green-50 border border-green-200 rounded px-3 py-1.5">
                                  <div className="flex items-center gap-2 min-w-0">
                                    <Badge variant="outline" className="font-mono shrink-0 border-green-300 text-green-800">
                                      data-testid="{loc.locator}"
                                    </Badge>
                                    <code className="text-slate-500 truncate">{loc.element}</code>
                                  </div>
                                  <button
                                    onClick={() => copyToClipboard(`data-testid="${loc.locator}"`, uid)}
                                    className="shrink-0 text-slate-400 hover:text-violet-600 transition-colors p-1 rounded"
                                    title="Copy data-testid attribute"
                                  >
                                    {copiedId === uid ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                                  </button>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {/* Existing locators */}
                      {existingLocs.length > 0 && (
                        <div className="px-4 py-3 space-y-2 border-t">
                          <p className="text-xs font-semibold text-slate-500 flex items-center gap-1">
                            <Minus className="w-3.5 h-3.5" /> Previously existing locators
                          </p>
                          <div className="space-y-1">
                            {existingLocs.map((loc, idx) => (
                              <div key={`${fileResult.file}-prev-${idx}`} className="flex items-center gap-2 text-xs text-slate-500 bg-slate-50 rounded px-3 py-1.5">
                                <Badge variant="outline" className="font-mono shrink-0">
                                  data-testid="{loc.locator}"
                                </Badge>
                                <code className="truncate">{loc.element}</code>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Updated code toggle */}
                      {fileResult.code && !hasError && (
                        <div className="border-t">
                          <button
                            onClick={() => toggleCode(fileResult.file)}
                            className="w-full flex items-center gap-2 px-4 py-2 text-xs text-slate-600 hover:bg-slate-50 transition-colors"
                          >
                            <Code2 className="w-3.5 h-3.5" />
                            {expandedCode.has(fileResult.file) ? "Hide" : "Show"} updated code
                          </button>
                          {expandedCode.has(fileResult.file) && (
                            <div className="relative">
                              <button
                                onClick={() => copyToClipboard(fileResult.code, `code-${fileResult.file}`)}
                                className="absolute top-2 right-2 text-slate-400 hover:text-white transition-colors p-1 rounded bg-slate-800/50"
                                title="Copy full code"
                              >
                                {copiedId === `code-${fileResult.file}` ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
                              </button>
                              <pre className="text-xs bg-slate-900 text-green-400 p-4 overflow-x-auto max-h-96 whitespace-pre-wrap">{fileResult.code}</pre>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </CollapsibleContent>
                </Card>
              </Collapsible>
            );
          })}
        </div>
      )}
    </div>
  );
}
