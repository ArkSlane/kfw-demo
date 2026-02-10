import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, XCircle, AlertCircle, Clock, User, Calendar, PlayCircle, Hash } from "lucide-react";
import { format } from "date-fns";
import { cn } from "@/lib/utils";

export default function ExecutionDetailsDialog({ open, onOpenChange, execution, testCase }) {
  if (!execution) return null;

  const resultColors = {
    passed: 'bg-green-100 text-green-700 border-green-200',
    failed: 'bg-red-100 text-red-700 border-red-200',
    blocked: 'bg-orange-100 text-orange-700 border-orange-200',
    skipped: 'bg-slate-100 text-slate-700 border-slate-200',
  };

  const getStepIcon = (result) => {
    if (result === 'passed') return <CheckCircle2 className="w-5 h-5 text-green-600" />;
    if (result === 'failed') return <XCircle className="w-5 h-5 text-red-600" />;
    if (result === 'blocked') return <AlertCircle className="w-5 h-5 text-orange-600" />;
    if (result === 'skipped') return <AlertCircle className="w-5 h-5 text-slate-400" />;
    return null;
  };

  const hasStepResults = execution.step_results && execution.step_results.length > 0;
  const failedSteps = hasStepResults 
    ? execution.step_results.filter(step => step.result === 'failed')
    : [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl">
            <PlayCircle className="w-6 h-6 text-blue-600" />
            Execution Details
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h3 className="font-semibold text-slate-900">{testCase?.title || 'Test Case'}</h3>
              {testCase?.id && (
                <Badge variant="outline" className="gap-1 text-xs text-slate-500 border-slate-300">
                  <Hash className="w-3 h-3" />
                  {testCase.id.substring(0, 8)}
                </Badge>
              )}
            </div>
            {testCase?.description && (
              <p className="text-sm text-slate-600">{testCase.description}</p>
            )}
          </div>

          <div className="grid md:grid-cols-2 gap-4">
            <div className="p-4 bg-slate-50 rounded-lg border border-slate-200">
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-sm">
                  <Calendar className="w-4 h-4 text-slate-600" />
                  <span className="text-slate-600">Date:</span>
                  <span className="font-medium text-slate-900">
                    {format(new Date(execution.execution_date), 'MMM d, yyyy')}
                  </span>
                </div>
                {execution.executed_by && (
                  <div className="flex items-center gap-2 text-sm">
                    <User className="w-4 h-4 text-slate-600" />
                    <span className="text-slate-600">Executed by:</span>
                    <span className="font-medium text-slate-900">{execution.executed_by}</span>
                  </div>
                )}
                {execution.duration && (
                  <div className="flex items-center gap-2 text-sm">
                    <Clock className="w-4 h-4 text-slate-600" />
                    <span className="text-slate-600">Duration:</span>
                    <span className="font-medium text-slate-900">{execution.duration} min</span>
                  </div>
                )}
                <div className="flex items-center gap-2 text-sm">
                  <PlayCircle className="w-4 h-4 text-slate-600" />
                  <span className="text-slate-600">Type:</span>
                  <Badge variant="outline" className={execution.execution_type === 'manual' ? 'bg-blue-50 text-blue-700' : 'bg-purple-50 text-purple-700'}>
                    {execution.execution_type || 'manual'}
                  </Badge>
                </div>
              </div>
            </div>

            <div className={cn(
              "p-4 rounded-lg border-2 flex items-center justify-center",
              resultColors[execution.result]
            )}>
              <div className="text-center">
                <div className="flex items-center justify-center gap-2 mb-2">
                  {getStepIcon(execution.result)}
                  <span className="text-2xl font-bold capitalize">{execution.result}</span>
                </div>
                {hasStepResults && (
                  <p className="text-sm">
                    {execution.step_results.filter(s => s.result === 'passed').length} / {execution.step_results.length} steps passed
                  </p>
                )}
              </div>
            </div>
          </div>

          {execution.notes && (
            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <p className="text-sm font-semibold text-blue-900 mb-1">Notes:</p>
              <p className="text-sm text-blue-800 whitespace-pre-wrap">{execution.notes}</p>
            </div>
          )}

          {execution.defects_found && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm font-semibold text-red-900 mb-1">Defects Found:</p>
              <p className="text-sm text-red-800 whitespace-pre-wrap">{execution.defects_found}</p>
            </div>
          )}

          {failedSteps.length > 0 && (
            <div className="p-4 bg-red-50 border-2 border-red-300 rounded-lg">
              <div className="flex items-center gap-2 mb-3">
                <XCircle className="w-5 h-5 text-red-600" />
                <p className="font-semibold text-red-900">Failed Steps ({failedSteps.length})</p>
              </div>
              <div className="space-y-3">
                {failedSteps.map((step, idx) => (
                  <div key={idx} className="p-3 bg-white rounded border border-red-200">
                    <div className="flex items-start gap-2 mb-2">
                      <Badge className="bg-red-600 text-white">Step {step.step_number}</Badge>
                      <div className="flex-1">
                        <p className="text-sm font-medium text-slate-900 mb-1">{step.action}</p>
                        {step.actual_result && (
                          <div className="mt-2 p-2 bg-red-100 rounded">
                            <p className="text-xs font-semibold text-red-900 mb-1">Actual Result:</p>
                            <p className="text-xs text-red-800">{step.actual_result}</p>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {hasStepResults && (
            <div className="border border-slate-200 rounded-lg overflow-hidden">
              <div className="bg-slate-50 border-b border-slate-200 p-3">
                <p className="font-semibold text-slate-900">Step-by-Step Results</p>
              </div>
              <div className="divide-y divide-slate-200">
                {execution.step_results.map((step, idx) => (
                  <div
                    key={idx}
                    className={cn(
                      "p-4 transition-colors",
                      step.result === 'failed' ? 'bg-red-50/50' : 
                      step.result === 'blocked' ? 'bg-orange-50/50' : 
                      step.result === 'passed' ? 'bg-green-50/50' : 'bg-slate-50'
                    )}
                  >
                    <div className="flex items-start gap-3">
                      <Badge variant="outline" className="mt-1">
                        Step {step.step_number}
                      </Badge>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-slate-900 mb-1">{step.action}</p>
                        <p className="text-sm text-slate-600 mb-2">
                          <span className="font-medium">Expected:</span> {step.expected_result}
                        </p>
                        {step.actual_result && (
                          <p className="text-sm text-slate-600">
                            <span className="font-medium">Actual:</span> {step.actual_result}
                          </p>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        {getStepIcon(step.result)}
                        <Badge className={cn("border", resultColors[step.result])}>
                          {step.result}
                        </Badge>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}