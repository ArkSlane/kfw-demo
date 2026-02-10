// @ts-nocheck
import React, { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";

import testcaseMigrationAPI from "@/api/testcaseMigrationClient";
import generatorAPI from "@/api/generatorClient";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";

// jsconfig.json enables checkJs; cast import.meta to any for Vite env access.
const viteEnv = /** @type {any} */ (import.meta).env;
const GENERATOR_URL = viteEnv?.VITE_GENERATOR_URL || "http://localhost:8003";

const steps = [
  { id: 1, title: "Paste code" },
  { id: 2, title: "Testcase draft" },
  { id: 3, title: "Automation draft" },
  { id: 4, title: "Summary & save" },
];

function StepHeader({ currentStep }) {
  return (
    <div className="flex flex-wrap gap-2">
      {steps.map((s) => {
        const active = s.id === currentStep;
        const done = s.id < currentStep;
        return (
          <Badge
            key={s.id}
            variant="outline"
            className={
              active
                ? "bg-blue-50 text-blue-700 border-blue-200"
                : done
                  ? "bg-slate-50 text-slate-700 border-slate-200"
                  : "text-slate-600 border-slate-200"
            }
          >
            {s.id}. {s.title}
          </Badge>
        );
      })}
    </div>
  );
}

export default function TestcaseMigration() {
  const [currentStep, setCurrentStep] = useState(1);

  // Step 1
  const [code, setCode] = useState("");

  // Step 2
  const [analysis, setAnalysis] = useState(null); // { testcase, mapping, model, generated_at }
  const [draftTestcase, setDraftTestcase] = useState(null);
  const [draftMapping, setDraftMapping] = useState([]);

  // Step 3
  const [generated, setGenerated] = useState(null); // { testcase_id, testcase, draft }
  const [script, setScript] = useState("");
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [sendingChat, setSendingChat] = useState(false);

  // Step 4
  const [saved, setSaved] = useState(null); // { testcase_id, automation_id }

  const analyzeMutation = useMutation({
    mutationFn: async () => {
      const trimmed = code.trim();
      if (!trimmed) throw new Error("Please paste legacy code first.");
      return testcaseMigrationAPI.analyze({ code: trimmed });
    },
    onSuccess: (res) => {
      setAnalysis(res);
      setDraftTestcase(res?.testcase || null);
      setDraftMapping(Array.isArray(res?.mapping) ? res.mapping : []);
      setGenerated(null);
      setScript("");
      setChatMessages([]);
      setSaved(null);
      setCurrentStep(2);
      toast.success("Analysis complete. Review testcase draft.");
    },
    onError: (err) => {
      toast.error(err?.response?.data?.message || err?.message || "Failed to analyze code");
    },
  });

  const generateMutation = useMutation({
    mutationFn: async () => {
      if (!draftTestcase) throw new Error("Run analysis first.");
      return testcaseMigrationAPI.generateAutomationDraft({
        code: code.trim() || null,
        testcase: draftTestcase,
        mapping: draftMapping || [],
      });
    },
    onSuccess: (res) => {
      setGenerated(res);
      setScript(res?.draft?.script_outline || "");
      setChatMessages([]);
      setSaved(null);
      setCurrentStep(3);
      toast.success("Automation draft generated. Review and refine.");
    },
    onError: (err) => {
      toast.error(err?.response?.data?.message || err?.message || "Failed to generate automation draft");
    },
  });

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!generated?.testcase_id) throw new Error("Generate an automation draft first.");
      if (!draftTestcase) throw new Error("Missing testcase draft.");
      if (!script.trim()) throw new Error("Script is empty.");

      return testcaseMigrationAPI.save({
        testcase_id: generated.testcase_id,
        testcase: draftTestcase,
        mapping: draftMapping || [],
        script: script.trim(),
        framework: generated?.draft?.framework || null,
        notes: generated?.draft?.notes || null,
      });
    },
    onSuccess: (res) => {
      setSaved(res);
      toast.success("Migration saved.");
    },
    onError: (err) => {
      toast.error(err?.response?.data?.message || err?.message || "Failed to save migration");
    },
  });

  const videoUrl = useMemo(() => {
    const videoPath = generated?.draft?.video_path;
    if (!videoPath) return null;
    // generator service hosts the /videos route
    return `${GENERATOR_URL}${videoPath}`;
  }, [generated]);

  const canGoBack = currentStep > 1 && !analyzeMutation.isPending && !generateMutation.isPending && !saveMutation.isPending;

  const handleBack = () => {
    if (currentStep === 2) setCurrentStep(1);
    if (currentStep === 3) setCurrentStep(2);
    if (currentStep === 4) setCurrentStep(3);
  };

  const handleContinueToSummary = () => {
    setCurrentStep(4);
  };

  const handleSendChat = async () => {
    const msg = chatInput.trim();
    if (!msg) return;
    if (!generated?.testcase_id || !generated?.draft) return;

    const nextMessages = [...chatMessages, { role: "user", content: msg }];
    setChatMessages(nextMessages);
    setChatInput("");
    setSendingChat(true);

    try {
      const res = await generatorAPI.automationChat({
        test_case_id: generated.testcase_id,
        message: msg,
        history: nextMessages,
        context: {
          script_outline: script,
          actions_taken: generated.draft.actions_taken,
          transcript: generated.draft.transcript,
          exec_error: generated.draft.exec_error,
          video_filename: generated.draft.video_filename,
        },
      });

      setChatMessages((prev) => [...prev, { role: "assistant", content: res.reply }]);
      if (res.suggested_script && typeof res.suggested_script === "string") {
        setScript(res.suggested_script);
        toast.success("Updated script from chat suggestion");
      }
    } catch (err) {
      toast.error(err?.response?.data?.message || err?.message || "Failed to send chat message");
    } finally {
      setSendingChat(false);
    }
  };

  const resetAll = () => {
    setCurrentStep(1);
    setCode("");
    setAnalysis(null);
    setDraftTestcase(null);
    setDraftMapping([]);
    setGenerated(null);
    setScript("");
    setChatMessages([]);
    setChatInput("");
    setSaved(null);
  };

  const updateDraftField = (field, value) => {
    setDraftTestcase((prev) => {
      if (!prev) return prev;
      return { ...prev, [field]: value };
    });
  };

  const updateStepField = (idx, field, value) => {
    setDraftTestcase((prev) => {
      if (!prev) return prev;
      const currentSteps = Array.isArray(prev.steps) ? prev.steps : [];
      const nextSteps = currentSteps.map((s, i) => (i === idx ? { ...(s || {}), [field]: value } : s));
      return { ...prev, steps: nextSteps };
    });
  };

  const addStep = () => {
    setDraftTestcase((prev) => {
      if (!prev) return prev;
      const currentSteps = Array.isArray(prev.steps) ? prev.steps : [];
      return { ...prev, steps: [...currentSteps, { action: "", expected_result: "" }] };
    });
  };

  const removeStep = (idx) => {
    setDraftTestcase((prev) => {
      if (!prev) return prev;
      const currentSteps = Array.isArray(prev.steps) ? prev.steps : [];
      return { ...prev, steps: currentSteps.filter((_, i) => i !== idx) };
    });
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <h1 className="text-2xl font-bold text-slate-900">Testcase Migration</h1>
          <p className="text-sm text-slate-600">
            Paste legacy automation code, generate a testcase draft, then generate a new AI automation and save.
          </p>
          <StepHeader currentStep={currentStep} />
        </div>
        <div className="flex gap-2">
          {canGoBack ? (
            <Button variant="outline" onClick={handleBack}>
              Back
            </Button>
          ) : null}
          <Button variant="outline" onClick={resetAll}>
            Start over
          </Button>
        </div>
      </div>

      {currentStep === 1 ? (
        <Card className="p-6 space-y-4">
          <div className="space-y-1">
            <div className="text-sm font-medium text-slate-900">Step 1: Paste legacy automation code</div>
            <div className="text-xs text-slate-600">Paste the script you want to migrate.</div>
          </div>
          <Textarea
            value={code}
            onChange={(e) => setCode(e.target.value)}
            className="min-h-[320px] font-mono text-xs"
            placeholder="Paste your legacy automation code here..."
            disabled={analyzeMutation.isPending}
          />
          <div className="flex justify-end">
            <Button onClick={() => analyzeMutation.mutate()} disabled={analyzeMutation.isPending || !code.trim()}>
              {analyzeMutation.isPending ? "Analyzing..." : "Analyze"}
            </Button>
          </div>
        </Card>
      ) : null}

      {currentStep === 2 ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card className="p-6 space-y-4">
            <div className="space-y-1">
              <div className="text-sm font-medium text-slate-900">Step 2: Testcase draft (not saved yet)</div>
              <div className="text-xs text-slate-600">Review the generated testcase before generating automation.</div>
            </div>

            <div className="space-y-2">
              <div className="text-sm font-medium">Title</div>
              <Input
                value={draftTestcase?.title || ""}
                onChange={(e) => updateDraftField("title", e.target.value)}
                placeholder="Testcase title"
              />
            </div>

            <div className="space-y-2">
              <div className="text-sm font-medium">Description</div>
              <Textarea
                value={draftTestcase?.description || ""}
                onChange={(e) => updateDraftField("description", e.target.value)}
                placeholder="Optional description"
                className="min-h-[90px] text-sm"
              />
            </div>

            <div className="space-y-2">
              <div className="text-sm font-medium">Preconditions</div>
              <Textarea
                value={draftTestcase?.preconditions || ""}
                onChange={(e) => updateDraftField("preconditions", e.target.value)}
                placeholder="Optional preconditions"
                className="min-h-[70px] text-sm"
              />
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between gap-2">
                <div className="text-sm font-medium">Steps</div>
                <Button variant="outline" size="sm" onClick={addStep}>
                  Add step
                </Button>
              </div>
              <div className="rounded border bg-slate-50 p-3 max-h-[520px] overflow-y-auto space-y-3">
                {(draftTestcase?.steps || []).length === 0 ? (
                  <div className="text-xs text-slate-500">No steps yet.</div>
                ) : null}
                {(draftTestcase?.steps || []).map((s, idx) => (
                  <div key={idx} className="rounded border bg-white p-3 space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-xs font-medium text-slate-700">Step {idx + 1}</div>
                      <Button variant="outline" size="sm" onClick={() => removeStep(idx)}>
                        Remove
                      </Button>
                    </div>
                    <div className="space-y-1">
                      <div className="text-xs text-slate-600">Action</div>
                      <Input
                        value={s?.action || ""}
                        onChange={(e) => updateStepField(idx, "action", e.target.value)}
                        placeholder="What to do"
                      />
                    </div>
                    <div className="space-y-1">
                      <div className="text-xs text-slate-600">Expected result</div>
                      <Input
                        value={s?.expected_result || ""}
                        onChange={(e) => updateStepField(idx, "expected_result", e.target.value)}
                        placeholder="What should happen"
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="text-xs text-slate-500">
              Note: The mapping on the right is based on the original analysis and isn’t automatically regenerated.
            </div>

            <div className="flex justify-end">
              <Button
                onClick={() => generateMutation.mutate()}
                disabled={generateMutation.isPending || !draftTestcase?.title?.trim() || (draftTestcase?.steps || []).length === 0}
              >
                {generateMutation.isPending ? "Generating..." : "Generate automation draft"}
              </Button>
            </div>
          </Card>

          <Card className="p-6 space-y-4">
            <div className="space-y-1">
              <div className="text-sm font-medium text-slate-900">Code ↔ steps mapping</div>
              <div className="text-xs text-slate-600">Shows which code lines map to which testcase steps.</div>
            </div>

            <div className="rounded border bg-white p-3 max-h-[520px] overflow-y-auto space-y-3">
              {(draftMapping || []).length === 0 ? (
                <div className="text-xs text-slate-500">No mapping available.</div>
              ) : null}
              {(draftMapping || []).map((m, idx) => (
                <div key={idx} className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="text-slate-600 border-slate-300">
                      Step {m.step_number}
                    </Badge>
                    {m.notes ? <div className="text-xs text-slate-600">{m.notes}</div> : null}
                  </div>
                  <pre className="text-xs bg-slate-50 border rounded p-2 whitespace-pre-wrap">{m.code_snippet}</pre>
                </div>
              ))}
            </div>
          </Card>
        </div>
      ) : null}

      {currentStep === 3 ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card className="p-6 space-y-4">
            <div className="flex items-center justify-between gap-2">
              <div className="space-y-1">
                <div className="text-sm font-medium text-slate-900">Step 3: Review automation draft</div>
                <div className="text-xs text-slate-600">Edit the script and optionally use chat to refine it.</div>
              </div>
              <div className="flex items-center gap-2">
                {generated?.draft?.framework ? (
                  <Badge variant="outline" className="text-slate-600 border-slate-300">
                    {generated.draft.framework}
                  </Badge>
                ) : null}
                {generated?.draft ? (
                  <Badge
                    variant="outline"
                    className={
                      generated.draft.exec_success
                        ? "bg-green-50 text-green-700 border-green-200"
                        : "bg-orange-50 text-orange-700 border-orange-200"
                    }
                  >
                    {generated.draft.exec_success ? "Execution succeeded" : "Execution failed (fallback)"}
                  </Badge>
                ) : null}
              </div>
            </div>

            <Textarea
              value={script}
              onChange={(e) => setScript(e.target.value)}
              className="min-h-[420px] font-mono text-xs"
              placeholder="Generated Playwright script appears here..."
              disabled={saveMutation.isPending || sendingChat}
            />

            {generated?.draft?.notes ? (
              <div className="text-xs text-slate-500 whitespace-pre-wrap">{generated.draft.notes}</div>
            ) : null}

            <div className="flex justify-end">
              <Button onClick={handleContinueToSummary} disabled={!script.trim()}>
                Continue
              </Button>
            </div>
          </Card>

          <Card className="p-6 space-y-4">
            <div className="space-y-1">
              <div className="text-sm font-medium text-slate-900">Transcript & chat</div>
              <div className="text-xs text-slate-600">Use chat to adjust selectors, waits, and assertions.</div>
            </div>

            {videoUrl ? (
              <div className="space-y-2">
                <div className="text-sm font-medium">Recording</div>
                <video className="w-full rounded border" controls src={videoUrl} />
              </div>
            ) : null}

            <div className="space-y-2">
              <div className="text-sm font-medium">Actions / transcript</div>
              <div className="rounded border bg-slate-50 p-3 max-h-[220px] overflow-y-auto">
                <pre className="text-xs whitespace-pre-wrap">
                  {(generated?.draft?.actions_taken || generated?.draft?.transcript || "No execution details available.").trim()}
                </pre>
              </div>
              {generated?.draft?.exec_error ? (
                <div className="text-xs text-orange-700 whitespace-pre-wrap">Error: {generated.draft.exec_error}</div>
              ) : null}
            </div>

            <div className="space-y-2">
              <div className="text-sm font-medium">Chat</div>
              <div className="rounded border bg-white p-3 max-h-[220px] overflow-y-auto space-y-2">
                {chatMessages.length === 0 ? (
                  <div className="text-xs text-slate-500">Ask the AI to adjust the automation.</div>
                ) : null}
                {chatMessages.map((m, idx) => (
                  <div key={idx} className="text-xs">
                    <div className="font-medium text-slate-700">{m.role === "assistant" ? "AI" : "You"}</div>
                    <div className="text-slate-600 whitespace-pre-wrap">{m.content}</div>
                  </div>
                ))}
              </div>

              <div className="flex gap-2">
                <Input
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder="Ask to adjust the automation..."
                  disabled={sendingChat || saveMutation.isPending}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleSendChat();
                    }
                  }}
                />
                <Button onClick={handleSendChat} disabled={sendingChat || saveMutation.isPending || !chatInput.trim()}>
                  {sendingChat ? "Sending..." : "Send"}
                </Button>
              </div>
            </div>
          </Card>
        </div>
      ) : null}

      {currentStep === 4 ? (
        <Card className="p-6 space-y-4">
          <div className="space-y-1">
            <div className="text-sm font-medium text-slate-900">Step 4: Summary & save</div>
            <div className="text-xs text-slate-600">Saves the testcase + automation.</div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="space-y-2">
              <div className="text-sm font-medium">Testcase</div>
              <div className="text-sm text-slate-700">{draftTestcase?.title || "—"}</div>
              <div className="text-xs text-slate-600">Steps: {(draftTestcase?.steps || []).length}</div>
              <div className="text-xs text-slate-600">Mappings: {(draftMapping || []).length}</div>
            </div>

            <div className="space-y-2">
              <div className="text-sm font-medium">Automation</div>
              <div className="text-xs text-slate-600">Framework: {generated?.draft?.framework || "—"}</div>
              <div className="text-xs text-slate-600">Draft testcase id: {generated?.testcase_id || "—"}</div>
            </div>

            <div className="space-y-2">
              <div className="text-sm font-medium">Script</div>
              <div className="text-xs text-slate-600">Characters: {script?.length || 0}</div>
            </div>
          </div>

          {saved ? (
            <div className="rounded border bg-green-50 border-green-200 p-3 text-sm text-green-800">
              Saved. Testcase ID: <span className="font-mono">{saved.testcase_id}</span> — Automation ID:{" "}
              <span className="font-mono">{saved.automation_id}</span>
            </div>
          ) : null}

          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={() => setCurrentStep(3)}
              disabled={saveMutation.isPending || sendingChat}
            >
              Back to review
            </Button>
            <Button
              onClick={() => saveMutation.mutate()}
              disabled={saveMutation.isPending || sendingChat || !script.trim() || !!saved}
            >
              {saveMutation.isPending ? "Saving..." : "Save"}
            </Button>
          </div>
        </Card>
      ) : null}
    </div>
  );
}
