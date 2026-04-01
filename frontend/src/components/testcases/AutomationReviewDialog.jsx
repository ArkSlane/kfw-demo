// @ts-nocheck
import React, { useEffect, useMemo, useState } from "react";
import { toast } from 'sonner';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { CheckCircle2, XCircle, Circle, AlertTriangle, ChevronDown, ChevronRight, Coins } from "lucide-react";

export default function AutomationReviewDialog({
  open,
  onOpenChange,
  testCase,
  draft,
  videoUrl,
  chatMessages,
  onSendChat,
  onSave,
  isSendingChat,
  isSaving,
  onExecute,
  isExecuting,
}) {
  const [script, setScript] = useState("");
  const [chatInput, setChatInput] = useState("");
  const [expandedStep, setExpandedStep] = useState(null);

  useEffect(() => {
    if (!open) return;
    setScript(draft?.script || draft?.script_outline || "");
    setChatInput("");
    setExpandedStep(null);
  }, [open, draft]);

  // Derive step execution statuses from transcript/actions_taken
  const stepStatuses = useMemo(() => {
    const steps = testCase?.metadata?.steps;
    if (!steps || !Array.isArray(steps) || steps.length === 0) return [];

    const execSuccess = !!draft?.exec_success;
    const transcript = draft?.actions_taken || draft?.transcript || "";
    const execError = draft?.exec_error || "";
    const hasTranscript = transcript.trim().length > 0;

    // If no execution happened yet, all steps are pending
    if (!hasTranscript && !execError && !execSuccess) {
      return steps.map(() => ({ status: "pending", detail: null }));
    }

    // If execution fully succeeded, mark all steps as passed
    if (execSuccess) {
      return steps.map(() => ({ status: "passed", detail: null }));
    }

    // Execution failed — try to determine which step(s) failed.
    // Heuristic: look for error patterns; if we find TimeoutError or similar,
    // try to match against step keywords. Otherwise, assume all steps up to
    // the last one passed and the last one failed.
    const errorPatterns = [
      /TimeoutError/i, /Error/i, /FAIL/i, /crash/i
    ];
    const hasError = errorPatterns.some(p => p.test(execError) || p.test(transcript));

    if (!hasError && hasTranscript) {
      // Transcript exists but no clear error — treat as all passed (soft success)
      return steps.map(() => ({ status: "passed", detail: null }));
    }

    // Try to identify which step failed by matching step action text to the error
    let failedIdx = steps.length - 1; // default: last step failed
    for (let i = 0; i < steps.length; i++) {
      const action = (steps[i]?.action || "").toLowerCase();
      const keywords = action.split(/\s+/).filter(w => w.length > 3);
      // Check if any keyword from this step's action appears in the error
      const errorLower = (execError + " " + transcript).toLowerCase();
      for (const kw of keywords) {
        if (errorLower.includes(kw) && kw.length > 4) {
          failedIdx = i;
          break;
        }
      }
    }

    return steps.map((_, idx) => {
      if (idx < failedIdx) return { status: "passed", detail: null };
      if (idx === failedIdx) return { status: "failed", detail: execError || "Execution failed" };
      return { status: "pending", detail: null };
    });
  }, [testCase, draft]);

  const execBadge = useMemo(() => {
    if (!draft) return null;
    const ok = !!draft.exec_success;
    return (
      <Badge
        variant="outline"
        className={
          ok
            ? "bg-green-50 text-green-700 border-green-200"
            : "bg-orange-50 text-orange-700 border-orange-200"
        }
      >
        {ok ? "Execution succeeded" : "Execution failed (fallback)"}
      </Badge>
    );
  }, [draft]);

  const handleSend = async () => {
    const msg = chatInput.trim();
    if (!msg) return;
    setChatInput("");
    await onSendChat({
      message: msg,
      currentScript: script,
      setScript,
    });
  };

  const handleSave = async () => {
    await onSave({ script });
  };

  const [localExecuting, setLocalExecuting] = useState(false);

  const executing = Boolean(isExecuting || localExecuting);

  const handleExecuteClick = async () => {
    if (!onExecute) {
      toast.error('Execute handler not available');
      return;
    }
    if (!script || !script.trim()) {
      toast.error('Script is empty');
      return;
    }
    try {
      setLocalExecuting(true);
      toast('Starting execution...');
      await onExecute(script);
      toast.success('Execution request sent');
    } catch (err) {
      console.error('Execute error:', err);
      toast.error(`Execution error: ${err?.message || String(err)}`);
    } finally {
      setLocalExecuting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <span>Review automation before saving</span>
            {draft?.framework ? (
              <Badge variant="outline" className="text-slate-600 border-slate-300">
                {draft.framework}
              </Badge>
            ) : null}
            {execBadge}
            {draft?.total_tokens > 0 && (
              <TooltipProvider delayDuration={200}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span>
                      <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200 flex items-center gap-1">
                        <Coins className="h-3 w-3" />
                        {draft.total_tokens.toLocaleString()} tokens
                      </Badge>
                    </span>
                  </TooltipTrigger>
                  <TooltipContent side="bottom" className="text-xs">
                    <div>Prompt: {(draft.prompt_tokens || 0).toLocaleString()}</div>
                    <div>Completion: {(draft.completion_tokens || 0).toLocaleString()}</div>
                    <div className="font-medium border-t mt-1 pt-1">Total: {draft.total_tokens.toLocaleString()}</div>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="text-sm text-slate-600">
            {testCase?.title ? <span>Test case: {testCase.title}</span> : null}
          </div>

          {videoUrl ? (
            <div className="space-y-2">
              <div className="text-sm font-medium">Recording</div>
              <div className="w-full rounded border overflow-hidden">
                <video className="w-full h-[56vh] md:h-[48vh] object-cover" controls src={videoUrl} />
              </div>
            </div>
          ) : null}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div>
              <details className="group rounded border bg-white">
                <summary className="cursor-pointer flex items-center justify-between p-3">
                  <div className="text-sm font-medium">Generated script</div>
                  <div className="text-xs text-slate-500">Edit before saving</div>
                </summary>
                <div className="p-3">
                  <Textarea
                    value={script}
                    onChange={(e) => setScript(e.target.value)}
                    className="min-h-[320px] font-mono text-xs"
                    placeholder="Generated Playwright script appears here..."
                  />
                  {draft?.notes ? (
                    <div className="text-xs text-slate-500 whitespace-pre-wrap mt-2">{draft.notes}</div>
                  ) : null}
                </div>
              </details>
            </div>

            <div>
              {testCase?.metadata?.steps && Array.isArray(testCase.metadata.steps) && testCase.metadata.steps.length > 0 ? (
                <div className="rounded border bg-white p-3">
                  <div className="flex items-center justify-between mb-3">
                    <div className="text-sm font-medium">Automated Steps</div>
                    {draft?.exec_success != null && (
                      <div className="flex items-center gap-1.5 text-xs">
                        {(() => {
                          const passed = stepStatuses.filter(s => s.status === "passed").length;
                          const total = stepStatuses.length;
                          return (
                            <>
                              <span className={passed === total ? "text-green-600 font-medium" : "text-slate-500"}>
                                {passed}/{total} passed
                              </span>
                              <div className="flex gap-0.5 ml-1">
                                {stepStatuses.map((s, i) => (
                                  <div
                                    key={i}
                                    className={`h-1.5 w-3 rounded-full ${
                                      s.status === "passed" ? "bg-green-500" :
                                      s.status === "failed" ? "bg-red-500" :
                                      "bg-slate-200"
                                    }`}
                                  />
                                ))}
                              </div>
                            </>
                          );
                        })()}
                      </div>
                    )}
                  </div>
                  <TooltipProvider delayDuration={200}>
                    <div className="space-y-0">
                      {testCase.metadata.steps.map((s, idx) => {
                        const stepStatus = stepStatuses[idx] || { status: "pending", detail: null };
                        const isLast = idx === testCase.metadata.steps.length - 1;
                        const isExpanded = expandedStep === idx;

                        return (
                          <div key={idx} className="flex gap-3">
                            {/* Vertical timeline connector */}
                            <div className="flex flex-col items-center">
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <div className="flex-shrink-0 mt-0.5">
                                    {stepStatus.status === "passed" && (
                                      <CheckCircle2 className="h-5 w-5 text-green-500" />
                                    )}
                                    {stepStatus.status === "failed" && (
                                      <XCircle className="h-5 w-5 text-red-500" />
                                    )}
                                    {stepStatus.status === "pending" && (
                                      <Circle className="h-5 w-5 text-slate-300" />
                                    )}
                                  </div>
                                </TooltipTrigger>
                                <TooltipContent side="left" className="text-xs max-w-[200px]">
                                  {stepStatus.status === "passed" && "Step executed successfully"}
                                  {stepStatus.status === "failed" && (stepStatus.detail || "Step failed during execution")}
                                  {stepStatus.status === "pending" && "Not yet executed"}
                                </TooltipContent>
                              </Tooltip>
                              {!isLast && (
                                <div className={`w-px flex-1 min-h-[16px] ${
                                  stepStatus.status === "passed" ? "bg-green-300" :
                                  stepStatus.status === "failed" ? "bg-red-300" :
                                  "bg-slate-200"
                                }`} />
                              )}
                            </div>

                            {/* Step content */}
                            <div className={`flex-1 pb-3 ${isLast ? "pb-0" : ""}`}>
                              <button
                                type="button"
                                onClick={() => setExpandedStep(isExpanded ? null : idx)}
                                className={`w-full text-left rounded-md px-2.5 py-1.5 transition-colors ${
                                  stepStatus.status === "failed"
                                    ? "bg-red-50 hover:bg-red-100 border border-red-200"
                                    : stepStatus.status === "passed"
                                    ? "bg-green-50/50 hover:bg-green-50 border border-green-100"
                                    : "bg-slate-50 hover:bg-slate-100 border border-slate-100"
                                }`}
                              >
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center gap-2">
                                    <span className={`text-[10px] font-mono rounded px-1 py-0.5 ${
                                      stepStatus.status === "passed" ? "bg-green-100 text-green-700" :
                                      stepStatus.status === "failed" ? "bg-red-100 text-red-700" :
                                      "bg-slate-200 text-slate-500"
                                    }`}>
                                      {idx + 1}
                                    </span>
                                    <span className={`text-xs font-medium ${
                                      stepStatus.status === "failed" ? "text-red-800" :
                                      stepStatus.status === "passed" ? "text-slate-700" :
                                      "text-slate-500"
                                    }`}>
                                      {s?.action || `Step ${idx + 1}`}
                                    </span>
                                  </div>
                                  {(s?.expected_result || stepStatus.detail) && (
                                    isExpanded
                                      ? <ChevronDown className="h-3.5 w-3.5 text-slate-400 flex-shrink-0" />
                                      : <ChevronRight className="h-3.5 w-3.5 text-slate-400 flex-shrink-0" />
                                  )}
                                </div>
                              </button>
                              {isExpanded && (
                                <div className="mt-1 ml-2 pl-2 border-l-2 border-slate-200 space-y-1">
                                  {s?.expected_result && (
                                    <div className="text-[11px] text-slate-600">
                                      <span className="font-medium text-slate-500">Expected: </span>
                                      {s.expected_result}
                                    </div>
                                  )}
                                  {stepStatus.status === "failed" && stepStatus.detail && (
                                    <div className="text-[11px] text-red-600 flex items-start gap-1">
                                      <AlertTriangle className="h-3 w-3 mt-0.5 flex-shrink-0" />
                                      <span className="break-all">{stepStatus.detail.slice(0, 200)}</span>
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </TooltipProvider>
                </div>
              ) : null}
            </div>
          </div>
        </div>
          {/* Chat - full width, last item */}
          <div className="space-y-2">
            <div className="text-sm font-medium">Chat</div>
            <div className="rounded border bg-white p-3 max-h-[220px] overflow-y-auto space-y-2">
              {(chatMessages || []).length === 0 ? (
                <div className="text-xs text-slate-500">Ask the AI to adjust selectors, waits, or assertions.</div>
              ) : null}
              {(chatMessages || []).map((m, idx) => (
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
                disabled={isSendingChat || isSaving}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleSend();
                  }
                }}
              />
              <Button onClick={handleSend} disabled={isSendingChat || isSaving || !chatInput.trim()}>
                {isSendingChat ? "Sending..." : "Send"}
              </Button>
            </div>
          </div>

          {/* Actions / Transcript - moved under chat, full-width and collapsible */}
          <div className="space-y-2">
            <details className="group rounded border bg-slate-50">
              <summary className="cursor-pointer p-3 text-sm font-medium">Actions / transcript</summary>
              <div className="p-3">
                <pre className="text-xs whitespace-pre-wrap">
                  {(draft?.actions_taken || draft?.transcript || "No execution details available.").trim()}
                </pre>
                {draft?.exec_error ? (
                  <div className="mt-2 text-xs text-orange-700 whitespace-pre-wrap">Error: {draft.exec_error}</div>
                ) : null}
              </div>
            </details>
          </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSaving || isSendingChat}>
            Cancel
          </Button>
          <Button
            onClick={handleExecuteClick}
            disabled={isSaving || isSendingChat || executing || !script.trim()}
            variant="secondary"
          >
            {executing ? 'Executing...' : 'Execute'}
          </Button>
          <Button onClick={handleSave} disabled={isSaving || isSendingChat || !script.trim()}>
            {isSaving ? "Saving..." : "Save automation"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
