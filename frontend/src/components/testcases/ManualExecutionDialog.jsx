import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { CheckCircle2, XCircle, AlertCircle, ChevronRight, ChevronLeft, PlayCircle, Flag } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

export default function ManualExecutionDialog({ open, onOpenChange, testCase, onComplete, releases = [] }) {
  const [currentStep, setCurrentStep] = useState(0);
  const [stepResults, setStepResults] = useState({});
  const [stepActualResults, setStepActualResults] = useState({});
  const [executionNotes, setExecutionNotes] = useState('');
  const [defectsFound, setDefectsFound] = useState('');
  const [executedBy, setExecutedBy] = useState('');
  const [durationMinutes, setDurationMinutes] = useState('');
  const [releaseId, setReleaseId] = useState('none');
  const [isCompleting, setIsCompleting] = useState(false);

  useEffect(() => {
    if (open) {
      // Reset state when dialog opens
      setCurrentStep(0);
      setStepResults({});
      setStepActualResults({});
      setExecutionNotes('');
      setDefectsFound('');
      setExecutedBy('');
      setDurationMinutes('');
      setReleaseId(testCase?.release_ids?.[0] || 'none');
      setIsCompleting(false);
    }
  }, [open]);

  if (!testCase) return null;

  const steps = testCase.steps || [];
  const totalSteps = steps.length;
  const progress = totalSteps > 0 ? ((currentStep + 1) / totalSteps) * 100 : 0;
  const completedSteps = Object.keys(stepResults).length;
  const allStepsCompleted = completedSteps === totalSteps;

  const handleStepResult = (stepIndex, result) => {
    setStepResults(prev => ({
      ...prev,
      [stepIndex]: result
    }));
    
    // Auto-advance to next step if not the last one
    if (stepIndex < totalSteps - 1) {
      setTimeout(() => setCurrentStep(stepIndex + 1), 300);
    }
  };

  const handleComplete = () => {
    setIsCompleting(true);
    
    // Determine overall result based on step results
    const failedSteps = Object.values(stepResults).filter(r => r === 'failed').length;
    const blockedSteps = Object.values(stepResults).filter(r => r === 'blocked').length;
    
    let overallResult = 'passed';
    if (failedSteps > 0) {
      overallResult = 'failed';
    } else if (blockedSteps > 0) {
      overallResult = 'blocked';
    }

    // Build step results array
    const stepResultsArray = steps.map((step, idx) => ({
      step_number: step.step_number || idx + 1,
      action: step.action,
      expected_result: step.expected_result,
      result: stepResults[idx] || 'skipped',
      actual_result: stepActualResults[idx] || ''
    }));

    const normalizedReleaseId = releaseId === 'none' ? '' : releaseId;

    const executionData = {
      test_case_id: testCase.id,
      execution_date: new Date().toISOString().split('T')[0],
      result: overallResult,
      executed_by: executedBy,
      notes: executionNotes || `Executed ${totalSteps} steps. ${completedSteps} completed.`,
      defects_found: defectsFound,
      duration_seconds: durationMinutes ? Math.round(Number(durationMinutes) * 60) : null,
      step_results: stepResultsArray,
      execution_type: 'manual',
      release_id: normalizedReleaseId || null,
    };

    onComplete(executionData);
  };

  const getStepIcon = (stepIndex) => {
    const result = stepResults[stepIndex];
    if (!result) return null;
    
    if (result === 'passed') return <CheckCircle2 className="w-5 h-5 text-green-600" />;
    if (result === 'failed') return <XCircle className="w-5 h-5 text-red-600" />;
    if (result === 'blocked') return <AlertCircle className="w-5 h-5 text-orange-600" />;
    return null;
  };

  const getOverallStatus = () => {
    const failedSteps = Object.values(stepResults).filter(r => r === 'failed').length;
    const blockedSteps = Object.values(stepResults).filter(r => r === 'blocked').length;
    
    if (failedSteps > 0) return { text: 'Failed', color: 'text-red-600', bg: 'bg-red-50' };
    if (blockedSteps > 0) return { text: 'Blocked', color: 'text-orange-600', bg: 'bg-orange-50' };
    return { text: 'Passed', color: 'text-green-600', bg: 'bg-green-50' };
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl">
            <PlayCircle className="w-6 h-6 text-blue-600" />
            Manual Test Execution
          </DialogTitle>
          <div className="mt-2">
            <h3 className="font-semibold text-slate-900 mb-1">{testCase.title}</h3>
            {testCase.description && (
              <p className="text-sm text-slate-600">{testCase.description}</p>
            )}
          </div>
        </DialogHeader>

        {/* Progress Bar */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-slate-600">Progress</span>
            <span className="font-medium text-slate-900">
              {completedSteps} / {totalSteps} steps completed
            </span>
          </div>
          <Progress value={progress} className="h-2" />
        </div>

        {/* Preconditions */}
        {testCase.preconditions && (
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <p className="text-sm font-semibold text-blue-900 mb-1">Preconditions:</p>
            <p className="text-sm text-blue-800">{testCase.preconditions}</p>
          </div>
        )}

        {/* Step Navigation */}
        <div className="flex items-center justify-between gap-4 py-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentStep(prev => Math.max(0, prev - 1))}
            disabled={currentStep === 0}
          >
            <ChevronLeft className="w-4 h-4 mr-1" />
            Previous
          </Button>
          <span className="text-sm font-medium text-slate-600">
            Step {currentStep + 1} of {totalSteps}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentStep(prev => Math.min(totalSteps - 1, prev + 1))}
            disabled={currentStep === totalSteps - 1}
          >
            Next
            <ChevronRight className="w-4 h-4 ml-1" />
          </Button>
        </div>

        {/* Current Step Display */}
        {steps.length > 0 && (
          <div className="border border-slate-200 rounded-lg p-6 bg-white">
            <div className="flex items-start justify-between mb-4">
              <Badge className="bg-blue-100 text-blue-700 border-blue-200">
                Step {steps[currentStep]?.step_number || currentStep + 1}
              </Badge>
              {stepResults[currentStep] && (
                <div className="flex items-center gap-2">
                  {getStepIcon(currentStep)}
                  <span className="text-sm font-medium text-slate-600 capitalize">
                    {stepResults[currentStep]}
                  </span>
                </div>
              )}
            </div>

            <div className="space-y-4">
              <div>
                <Label className="text-sm font-semibold text-slate-700 mb-2 block">
                  Action:
                </Label>
                <p className="text-slate-900 bg-slate-50 p-3 rounded border border-slate-200">
                  {steps[currentStep]?.action || 'No action defined'}
                </p>
              </div>

              <div>
                <Label className="text-sm font-semibold text-slate-700 mb-2 block">
                  Expected Result:
                </Label>
                <p className="text-slate-900 bg-slate-50 p-3 rounded border border-slate-200">
                  {steps[currentStep]?.expected_result || 'No expected result defined'}
                </p>
              </div>

              {/* Actual Result Input (for failed/blocked steps) */}
              {stepResults[currentStep] && stepResults[currentStep] !== 'passed' && (
                <div>
                  <Label className="text-sm font-semibold text-slate-700 mb-2 block">
                    Actual Result:
                  </Label>
                  <Textarea
                    value={stepActualResults[currentStep] || ''}
                    onChange={(e) => setStepActualResults(prev => ({ ...prev, [currentStep]: e.target.value }))}
                    placeholder="Describe what actually happened..."
                    rows={2}
                  />
                </div>
              )}

              <div>
                <Label className="text-sm font-semibold text-slate-700 mb-3 block">
                  Mark this step as:
                </Label>
                <div className="flex gap-3">
                  <Button
                    onClick={() => handleStepResult(currentStep, 'passed')}
                    className={cn(
                      "flex-1 gap-2",
                      stepResults[currentStep] === 'passed'
                        ? "bg-green-600 hover:bg-green-700"
                        : "bg-green-50 text-green-700 border-green-200 hover:bg-green-100"
                    )}
                    variant={stepResults[currentStep] === 'passed' ? 'default' : 'outline'}
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    Passed
                  </Button>
                  <Button
                    onClick={() => handleStepResult(currentStep, 'failed')}
                    className={cn(
                      "flex-1 gap-2",
                      stepResults[currentStep] === 'failed'
                        ? "bg-red-600 hover:bg-red-700"
                        : "bg-red-50 text-red-700 border-red-200 hover:bg-red-100"
                    )}
                    variant={stepResults[currentStep] === 'failed' ? 'default' : 'outline'}
                  >
                    <XCircle className="w-4 h-4" />
                    Failed
                  </Button>
                  <Button
                    onClick={() => handleStepResult(currentStep, 'blocked')}
                    className={cn(
                      "flex-1 gap-2",
                      stepResults[currentStep] === 'blocked'
                        ? "bg-orange-600 hover:bg-orange-700"
                        : "bg-orange-50 text-orange-700 border-orange-200 hover:bg-orange-100"
                    )}
                    variant={stepResults[currentStep] === 'blocked' ? 'default' : 'outline'}
                  >
                    <AlertCircle className="w-4 h-4" />
                    Blocked
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Steps Overview */}
        <div className="border border-slate-200 rounded-lg p-4 bg-slate-50">
          <p className="text-sm font-semibold text-slate-700 mb-3">Steps Overview:</p>
          <div className="grid grid-cols-8 gap-2">
            {steps.map((_, idx) => (
              <button
                key={idx}
                onClick={() => setCurrentStep(idx)}
                className={cn(
                  "h-10 rounded-lg border-2 flex items-center justify-center text-sm font-medium transition-all",
                  currentStep === idx
                    ? "border-blue-600 bg-blue-100 text-blue-900"
                    : stepResults[idx] === 'passed'
                    ? "border-green-300 bg-green-100 text-green-900"
                    : stepResults[idx] === 'failed'
                    ? "border-red-300 bg-red-100 text-red-900"
                    : stepResults[idx] === 'blocked'
                    ? "border-orange-300 bg-orange-100 text-orange-900"
                    : "border-slate-300 bg-white text-slate-600 hover:border-slate-400"
                )}
              >
                {idx + 1}
              </button>
            ))}
          </div>
        </div>

        {/* Execution Summary */}
        {allStepsCompleted && (
          <div className={cn("p-4 rounded-lg border-2", getOverallStatus().bg)}>
            <div className="flex items-center justify-between mb-3">
              <p className="font-semibold text-slate-900">Execution Summary</p>
              <Badge className={cn("text-lg px-3 py-1", getOverallStatus().color)}>
                {getOverallStatus().text}
              </Badge>
            </div>

            <div className="space-y-3">
              <div className="grid md:grid-cols-3 gap-3">
                <div>
                  <Label className="text-sm font-medium text-slate-700">Release (optional)</Label>
                  <Select
                    value={releaseId || 'none'}
                    onValueChange={(v) => setReleaseId(v)}
                  >
                    <SelectTrigger className="mt-1">
                      <SelectValue placeholder="Select release" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">No release</SelectItem>
                      {releases.map((rel) => (
                        <SelectItem key={rel.id} value={rel.id}>
                          {rel.name} {rel.version && `(v${rel.version})`}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-sm font-medium text-slate-700">Executed By</Label>
                  <Input
                    className="mt-1"
                    placeholder="Name or email"
                    value={executedBy}
                    onChange={(e) => setExecutedBy(e.target.value)}
                  />
                </div>
                <div>
                  <Label className="text-sm font-medium text-slate-700">Duration (minutes)</Label>
                  <Input
                    className="mt-1"
                    type="number"
                    min="0"
                    inputMode="decimal"
                    placeholder="e.g. 5"
                    value={durationMinutes}
                    onChange={(e) => setDurationMinutes(e.target.value)}
                  />
                </div>
              </div>

              <div>
                <Label htmlFor="executionNotes" className="text-sm font-medium text-slate-700">
                  Execution Notes
                </Label>
                <Textarea
                  id="executionNotes"
                  value={executionNotes}
                  onChange={(e) => setExecutionNotes(e.target.value)}
                  placeholder="Add any observations or notes about the execution..."
                  rows={3}
                  className="mt-1"
                />
              </div>

              <div>
                <Label htmlFor="defectsFound" className="text-sm font-medium text-slate-700">
                  Defects Found
                </Label>
                <Textarea
                  id="defectsFound"
                  value={defectsFound}
                  onChange={(e) => setDefectsFound(e.target.value)}
                  placeholder="Describe any defects or issues found during execution..."
                  rows={3}
                  className="mt-1"
                />
              </div>
            </div>
          </div>
        )}

        <DialogFooter className="gap-2">
          <Button 
            variant="outline" 
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          {allStepsCompleted && (
            <Button
              onClick={handleComplete}
              disabled={isCompleting}
              className="bg-blue-600 hover:bg-blue-700 gap-2"
            >
              <Flag className="w-4 h-4" />
              {isCompleting ? 'Logging Execution...' : 'Complete & Log Execution'}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}