import React, { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from "@/components/ui/collapsible";
import { Checkbox } from "@/components/ui/checkbox";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { toast } from "sonner";
import {
  GitMerge, Loader2, FlaskConical, Bot, FileCode2, ChevronDown, ChevronRight,
  ClipboardCheck, ArrowRight, Plus, Check, AlertCircle, Play, FileText,
} from "lucide-react";
import gitRepoConnectionsAPI from "@/api/gitRepoConnectionsClient";
import generatorAPI from "@/api/generatorClient";
import { requirementsAPI } from "@/api/requirementsClient";
import { testcasesAPI } from "@/api/testcasesClient";
import { useQuery, useQueryClient } from "@tanstack/react-query";

const PIPELINE_STEPS = [
  { key: "fetch", label: "Fetch MR", icon: GitMerge, description: "Retrieve merge request details and diff" },
  { key: "requirements", label: "Extract Requirements", icon: FileText, description: "AI-analyze diff to extract requirements" },
  { key: "testcases", label: "Generate Test Cases", icon: ClipboardCheck, description: "Generate test cases from requirements" },
  { key: "automations", label: "Generate Automations", icon: Bot, description: "Generate Playwright scripts from test cases" },
];

export default function MergeRequestPipeline() {
  const queryClient = useQueryClient();

  // --- MR Selection ---
  const [repoId, setRepoId] = useState("");
  const [provider, setProvider] = useState("");
  const [mrNumber, setMrNumber] = useState("");

  // --- Pipeline state ---
  const [currentStep, setCurrentStep] = useState(null); // null | "fetch" | "requirements" | "testcases" | "automations"
  const [completedSteps, setCompletedSteps] = useState(new Set());
  const [running, setRunning] = useState(false);

  // --- MR data ---
  const [mrInfo, setMrInfo] = useState(null);
  const [extractedReqs, setExtractedReqs] = useState([]);
  const [generatedTests, setGeneratedTests] = useState([]);
  const [generatedAutomations, setGeneratedAutomations] = useState([]);

  // --- Options ---
  const [autoRunAll, setAutoRunAll] = useState(true);
  const [testCaseCount, setTestCaseCount] = useState("3");

  // --- Load repos ---
  const { data: repos = [] } = useQuery({
    queryKey: ["repoConnections"],
    queryFn: () => gitRepoConnectionsAPI.list(),
  });

  const repoList = useMemo(() => {
    const app = repos.filter((r) => r.repo_type === "application_repository");
    return app.length > 0 ? app : repos;
  }, [repos]);

  // ─── Pipeline execution ─────────────────────────────────────────────
  const runPipeline = async () => {
    if (!repoId || !mrNumber) {
      toast.error("Please select a repository and enter a MR/PR number");
      return;
    }

    setRunning(true);
    setCompletedSteps(new Set());
    setMrInfo(null);
    setExtractedReqs([]);
    setGeneratedTests([]);
    setGeneratedAutomations([]);

    try {
      // Step 1: Fetch MR info
      setCurrentStep("fetch");
      const mrData = await _fetchMRInfo();
      setMrInfo(mrData);
      setCompletedSteps((s) => new Set([...s, "fetch"]));

      if (!autoRunAll) { setRunning(false); return; }

      // Step 2: Extract requirements from diff
      setCurrentStep("requirements");
      const reqs = await _extractRequirements(mrData);
      setExtractedReqs(reqs);
      setCompletedSteps((s) => new Set([...s, "requirements"]));

      if (!autoRunAll) { setRunning(false); return; }

      // Step 3: Generate test cases
      setCurrentStep("testcases");
      const tests = await _generateTestCases(reqs);
      setGeneratedTests(tests);
      setCompletedSteps((s) => new Set([...s, "testcases"]));

      if (!autoRunAll) { setRunning(false); return; }

      // Step 4: Generate automations
      setCurrentStep("automations");
      const autos = await _generateAutomations(tests);
      setGeneratedAutomations(autos);
      setCompletedSteps((s) => new Set([...s, "automations"]));

      toast.success("Pipeline complete! Generated test cases and automations from MR.");
    } catch (e) {
      toast.error(`Pipeline failed at "${currentStep}": ${e.message}`);
    } finally {
      setRunning(false);
      setCurrentStep(null);
    }
  };

  const continueFromStep = async (stepKey) => {
    setRunning(true);
    try {
      const stepIndex = PIPELINE_STEPS.findIndex((s) => s.key === stepKey);
      for (let i = stepIndex; i < PIPELINE_STEPS.length; i++) {
        const step = PIPELINE_STEPS[i];
        setCurrentStep(step.key);

        if (step.key === "requirements") {
          const reqs = await _extractRequirements(mrInfo);
          setExtractedReqs(reqs);
        } else if (step.key === "testcases") {
          const tests = await _generateTestCases(extractedReqs);
          setGeneratedTests(tests);
        } else if (step.key === "automations") {
          const autos = await _generateAutomations(generatedTests.length > 0 ? generatedTests : []);
          setGeneratedAutomations(autos);
        }

        setCompletedSteps((s) => new Set([...s, step.key]));
      }
      toast.success("Pipeline steps complete!");
    } catch (e) {
      toast.error(`Step failed: ${e.message}`);
    } finally {
      setRunning(false);
      setCurrentStep(null);
    }
  };

  // ─── Placeholder step implementations ───────────────────────────────
  const _fetchMRInfo = async () => {
    // Placeholder — would call GET /merge-requests/{number}/details
    await new Promise((r) => setTimeout(r, 1200));
    return {
      number: mrNumber,
      title: `Feature: Example MR #${mrNumber}`,
      description: "This merge request adds new functionality to the application.",
      author: "developer",
      status: "open",
      files_changed: 8,
      additions: 245,
      deletions: 32,
      changed_files: [
        "src/components/Dashboard.tsx",
        "src/api/userService.ts",
        "src/hooks/useAuth.ts",
        "src/pages/Settings.tsx",
        "src/utils/validation.ts",
        "tests/auth.test.ts",
        "README.md",
        "package.json",
      ],
    };
  };

  const _extractRequirements = async (mrData) => {
    // Placeholder — would call POST /requirements/extract-from-mr
    await new Promise((r) => setTimeout(r, 2000));
    return [
      {
        id: `mr-req-1`,
        title: "User authentication settings page",
        description: "Users should be able to view and update their authentication settings including password and 2FA.",
        source: "merge-request",
        tags: ["authentication", "settings"],
      },
      {
        id: `mr-req-2`,
        title: "Input validation for user forms",
        description: "All user-facing forms should validate input before submission with appropriate error messages.",
        source: "merge-request",
        tags: ["validation", "UX"],
      },
      {
        id: `mr-req-3`,
        title: "Dashboard data refresh",
        description: "Dashboard should refresh data when navigating back to it, ensuring up-to-date information.",
        source: "merge-request",
        tags: ["dashboard", "data"],
      },
    ];
  };

  const _generateTestCases = async (reqs) => {
    // Placeholder — would create requirements first, then call generatorAPI.generateTestcases
    await new Promise((r) => setTimeout(r, 2500));
    const tests = [];
    for (const req of reqs) {
      for (let i = 1; i <= Math.min(parseInt(testCaseCount) || 3, 5); i++) {
        tests.push({
          id: `${req.id}-tc-${i}`,
          title: `TC${i}: Verify ${req.title.toLowerCase()}`,
          requirement: req.title,
          priority: i === 1 ? "high" : "medium",
          type: i <= 2 ? "positive" : "negative",
          steps: [
            { step: "Navigate to the relevant page", expected: "Page loads successfully" },
            { step: "Perform the action under test", expected: "Expected behavior is observed" },
            { step: "Verify the result", expected: "Result matches acceptance criteria" },
          ],
        });
      }
    }
    return tests;
  };

  const _generateAutomations = async (tests) => {
    // Placeholder — would call generatorAPI.generateAutomation for each test
    await new Promise((r) => setTimeout(r, 2000));
    return tests.slice(0, 3).map((tc) => ({
      id: `${tc.id}-auto`,
      testCase: tc.title,
      framework: "Playwright",
      status: "generated",
      script: `// Auto-generated Playwright test for: ${tc.title}\ntest('${tc.title}', async ({ page }) => {\n  // TODO: Implement test steps\n  await page.goto('/');\n});`,
    }));
  };

  // ─── Render ─────────────────────────────────────────────────────────
  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-gradient-to-br from-orange-500 to-red-600 rounded-xl flex items-center justify-center shadow-lg">
          <GitMerge className="w-6 h-6 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">MR Pipeline</h1>
          <p className="text-sm text-slate-500">
            Generate test cases and automations from a merge request
          </p>
        </div>
      </div>

      {/* MR Selection */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">Select Merge Request</CardTitle>
          <CardDescription>
            Choose a repository and enter the MR/PR number to start the pipeline.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label>Repository</Label>
              <Select value={repoId} onValueChange={(v) => { setRepoId(v); const r = repos.find((x) => x.id === v); if (r) setProvider(r.provider || "github"); }}>
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
              <Select value={provider} onValueChange={setProvider}>
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

          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <Checkbox
                id="auto-run"
                checked={autoRunAll}
                onCheckedChange={setAutoRunAll}
              />
              <Label htmlFor="auto-run" className="text-sm cursor-pointer">
                Run all steps automatically
              </Label>
            </div>
            <div className="flex items-center gap-2">
              <Label className="text-sm">Test cases per requirement:</Label>
              <Select value={testCaseCount} onValueChange={setTestCaseCount}>
                <SelectTrigger className="w-20">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {[1, 2, 3, 5].map((n) => (
                    <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <Button onClick={runPipeline} disabled={!repoId || !mrNumber || running} size="lg">
            {running ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Play className="w-4 h-4 mr-2" />}
            {running ? "Running Pipeline…" : "Run Pipeline"}
          </Button>
        </CardContent>
      </Card>

      {/* Pipeline Steps Visualization */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2">
        {PIPELINE_STEPS.map((step, idx) => {
          const isDone = completedSteps.has(step.key);
          const isCurrent = currentStep === step.key;
          const Icon = step.icon;
          return (
            <React.Fragment key={step.key}>
              {idx > 0 && (
                <ArrowRight className={`w-4 h-4 shrink-0 ${isDone ? "text-emerald-500" : "text-slate-300"}`} />
              )}
              <div
                className={`flex items-center gap-2 px-4 py-2 rounded-lg border text-sm whitespace-nowrap transition-colors ${
                  isCurrent
                    ? "bg-blue-50 border-blue-300 text-blue-700"
                    : isDone
                    ? "bg-emerald-50 border-emerald-200 text-emerald-700"
                    : "bg-slate-50 border-slate-200 text-slate-500"
                }`}
              >
                {isCurrent ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : isDone ? (
                  <Check className="w-4 h-4" />
                ) : (
                  <Icon className="w-4 h-4" />
                )}
                {step.label}
              </div>
            </React.Fragment>
          );
        })}
      </div>

      {/* ── Results Sections ─────────────────────────────────────────── */}

      {/* MR Info */}
      {mrInfo && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              <GitMerge className="w-5 h-5 text-orange-500" />
              MR #{mrInfo.number}: {mrInfo.title}
            </CardTitle>
            <CardDescription>
              {mrInfo.files_changed} files changed · +{mrInfo.additions} −{mrInfo.deletions}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-slate-600 mb-3">{mrInfo.description}</p>
            <div className="flex flex-wrap gap-1">
              {mrInfo.changed_files.map((f) => (
                <Badge key={f} variant="outline" className="font-mono text-xs">{f}</Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Extracted Requirements */}
      {extractedReqs.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg flex items-center gap-2">
                <FileText className="w-5 h-5 text-emerald-500" />
                Extracted Requirements
                <Badge variant="secondary">{extractedReqs.length}</Badge>
              </CardTitle>
              {!completedSteps.has("testcases") && !running && (
                <Button size="sm" variant="outline" onClick={() => continueFromStep("testcases")}>
                  Continue → Generate Tests
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {extractedReqs.map((req) => (
                <div key={req.id} className="p-3 rounded-lg border bg-emerald-50/50 border-emerald-100">
                  <p className="text-sm font-medium text-slate-800">{req.title}</p>
                  <p className="text-xs text-slate-500 mt-1">{req.description}</p>
                  <div className="flex gap-1 mt-2">
                    {req.tags?.map((t) => (
                      <Badge key={t} variant="secondary" className="text-xs">{t}</Badge>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Generated Test Cases */}
      {generatedTests.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg flex items-center gap-2">
                <ClipboardCheck className="w-5 h-5 text-blue-500" />
                Generated Test Cases
                <Badge variant="secondary">{generatedTests.length}</Badge>
              </CardTitle>
              {!completedSteps.has("automations") && !running && (
                <Button size="sm" variant="outline" onClick={() => continueFromStep("automations")}>
                  Continue → Generate Automations
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {generatedTests.map((tc) => (
                <Collapsible key={tc.id}>
                  <CollapsibleTrigger className="w-full">
                    <div className="flex items-center gap-3 p-3 rounded-lg border hover:bg-slate-50 transition-colors cursor-pointer">
                      <ChevronRight className="w-4 h-4 text-slate-400 ui-state-open:hidden" />
                      <ChevronDown className="w-4 h-4 text-slate-400 hidden ui-state-open:block" />
                      <div className="flex-1 text-left">
                        <p className="text-sm font-medium text-slate-800">{tc.title}</p>
                        <p className="text-xs text-slate-500">Requirement: {tc.requirement}</p>
                      </div>
                      <Badge className={tc.type === "positive" ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"}>
                        {tc.type}
                      </Badge>
                      <Badge variant="outline">{tc.priority}</Badge>
                    </div>
                  </CollapsibleTrigger>
                  <CollapsibleContent>
                    <div className="ml-10 pl-3 border-l-2 border-blue-100 pb-2 space-y-1">
                      {tc.steps?.map((s, i) => (
                        <div key={i} className="text-xs text-slate-600 py-1">
                          <span className="font-medium text-slate-800">Step {i + 1}:</span> {s.step}
                          <span className="text-slate-400 mx-2">→</span>
                          <span className="text-emerald-600">{s.expected}</span>
                        </div>
                      ))}
                    </div>
                  </CollapsibleContent>
                </Collapsible>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Generated Automations */}
      {generatedAutomations.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              <Bot className="w-5 h-5 text-purple-500" />
              Generated Automations
              <Badge variant="secondary">{generatedAutomations.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {generatedAutomations.map((auto) => (
                <Collapsible key={auto.id}>
                  <CollapsibleTrigger className="w-full">
                    <div className="flex items-center gap-3 p-3 rounded-lg border hover:bg-slate-50 transition-colors cursor-pointer">
                      <ChevronRight className="w-4 h-4 text-slate-400" />
                      <div className="flex-1 text-left">
                        <p className="text-sm font-medium text-slate-800">{auto.testCase}</p>
                      </div>
                      <Badge className="bg-purple-100 text-purple-700">{auto.framework}</Badge>
                      <Badge variant="outline" className="text-xs">{auto.status}</Badge>
                    </div>
                  </CollapsibleTrigger>
                  <CollapsibleContent>
                    <pre className="mt-2 text-xs bg-slate-900 text-green-400 p-4 rounded-lg overflow-x-auto max-h-64">
                      {auto.script}
                    </pre>
                  </CollapsibleContent>
                </Collapsible>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Empty state */}
      {!mrInfo && !running && (
        <Card className="border-dashed">
          <CardContent className="py-16 flex flex-col items-center gap-4 text-center">
            <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center">
              <GitMerge className="w-8 h-8 text-slate-400" />
            </div>
            <div>
              <p className="font-medium text-slate-700">No merge request selected</p>
              <p className="text-sm text-slate-500 mt-1 max-w-md">
                Select a repository and enter a merge/pull request number above, then run the pipeline
                to automatically extract requirements, generate test cases, and create automation scripts.
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
