// @ts-nocheck
import React, { useEffect, useMemo, useState } from "react";
import { toast } from 'sonner';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

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

  useEffect(() => {
    if (!open) return;
    setScript(draft?.script_outline || "");
    setChatInput("");
  }, [open, draft]);

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
                <details className="group rounded border bg-slate-50">
                  <summary className="cursor-pointer p-3 text-sm font-medium">Test steps</summary>
                  <div className="p-3 max-h-[240px] overflow-y-auto bg-slate-50">
                    <ol className="list-decimal pl-5 space-y-2">
                      {testCase.metadata.steps.map((s, idx) => (
                        <li key={idx} className="text-xs text-slate-700">
                          <div className="font-medium">{s?.action || `Step ${idx + 1}`}</div>
                          {s?.expected_result ? (
                            <div className="text-slate-600">Expected: {s.expected_result}</div>
                          ) : null}
                        </li>
                      ))}
                    </ol>
                  </div>
                </details>
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
