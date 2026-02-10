import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Plus, Trash2, X, Sparkles, Lock, AlertTriangle, ChevronUp, ChevronDown } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Checkbox } from "@/components/ui/checkbox";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

export default function TestCaseDialog({ open, onOpenChange, testCase, requirements, onSubmit, isLoading, aiGeneratedData, preLinkedRequirementId }) {
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    requirement_ids: [],
    release_ids: [],
    priority: 'medium',
    status: 'draft',
    test_type: 'manual',
    preconditions: '',
    steps: [],
  });
  const [sodWarningOpen, setSODWarningOpen] = useState(false);
  const [sodViolation, setSODViolation] = useState(null);

  const { data: releases } = useQuery({
    queryKey: ['releases'],
    queryFn: async () => [],
    initialData: [],
    enabled: false,
  });

  const { data: sodRules } = useQuery({
    queryKey: ['sodSettings'],
    queryFn: async () => [],
    initialData: [],
    enabled: false,
  });

  const { data: currentUser } = useQuery({
    queryKey: ['currentUser'],
    queryFn: async () => null,
    enabled: false,
  });

  const getInheritedReleases = () => {
    const inheritedReleaseIds = new Set();
    formData.requirement_ids.forEach(reqId => {
      const req = requirements.find(r => r.id === reqId);
      if (req && req.release_id) {
        inheritedReleaseIds.add(req.release_id);
      }
    });
    return Array.from(inheritedReleaseIds);
  };

  const inheritedReleaseIds = getInheritedReleases();

  useEffect(() => {
    const currentInheritedReleases = getInheritedReleases();

    const manuallySelectedReleases = formData.release_ids.filter(rid => !currentInheritedReleases.includes(rid));
    
    const newReleaseIds = [...new Set([...currentInheritedReleases, ...manuallySelectedReleases])];
    
    const sortedCurrent = [...formData.release_ids].sort();
    const sortedNew = [...newReleaseIds].sort();

    if (JSON.stringify(sortedCurrent) !== JSON.stringify(sortedNew)) {
      setFormData(prev => ({ ...prev, release_ids: newReleaseIds }));
    }
  }, [formData.requirement_ids, requirements, formData.release_ids]);

  useEffect(() => {
    if (testCase) {
      setFormData({
        title: testCase.title || '',
        description: testCase.description || '',
        requirement_ids: testCase.requirement_ids || [],
        release_ids: testCase.release_ids || [],
        priority: testCase.priority || 'medium',
        status: testCase.status || 'draft',
        test_type: testCase.test_type || 'manual',
        preconditions: testCase.preconditions || '',
        steps: testCase.steps || [],
      });
    } else if (aiGeneratedData) {
      setFormData({
        title: aiGeneratedData.title || '',
        description: aiGeneratedData.description || '',
        requirement_ids: preLinkedRequirementId ? [preLinkedRequirementId] : [],
        release_ids: [],
        priority: aiGeneratedData.priority || 'medium',
        status: 'draft',
        test_type: aiGeneratedData.test_type || 'manual',
        preconditions: aiGeneratedData.preconditions || '',
        steps: aiGeneratedData.steps || [],
      });
    } else {
      setFormData({
        title: '',
        description: '',
        requirement_ids: preLinkedRequirementId ? [preLinkedRequirementId] : [],
        release_ids: [],
        priority: 'medium',
        status: 'draft',
        test_type: 'manual',
        preconditions: '',
        steps: [],
      });
    }
  }, [testCase, aiGeneratedData, preLinkedRequirementId, open]);

  const checkSODViolation = async (newStatus) => {
    if (!testCase || !currentUser) return false;

    // Check if SOD rules are enabled for test case approval
    const testCaseRule = sodRules.find(rule => rule.rule_type === 'test_case_approval' && rule.enabled);
    if (!testCaseRule) return false;

    // Check if this status change is restricted
    const isRestricted = testCaseRule.restricted_status_transitions?.some(
      transition => transition.from_status === testCase.status && transition.to_status === newStatus
    );

    if (!isRestricted) return false;

    // Check if current user is the creator
    const isCreator = testCase.created_by === currentUser.email;
    
    if (isCreator) {
      return {
        rule: testCaseRule,
        fromStatus: testCase.status,
        toStatus: newStatus,
        creator: testCase.created_by
      };
    }

    return false;
  };

  const handleStatusChange = async (newStatus) => {
    if (testCase) {
      const violation = await checkSODViolation(newStatus);
      if (violation) {
        setSODViolation(violation);
        setSODWarningOpen(true);
        return;
      }
    }
    setFormData({ ...formData, status: newStatus });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (testCase) {
      const violation = await checkSODViolation(formData.status);
      if (violation) {
        setSODViolation(violation);
        setSODWarningOpen(true);
        return;
      }
    }
    
    onSubmit(formData);
  };

  const addStep = () => {
    setFormData({
      ...formData,
      steps: [...formData.steps, { step_number: formData.steps.length + 1, action: '', expected_result: '' }]
    });
  };

  const updateStep = (index, field, value) => {
    const newSteps = [...formData.steps];
    newSteps[index][field] = value;
    setFormData({ ...formData, steps: newSteps });
  };

  const removeStep = (index) => {
    const newSteps = formData.steps.filter((_, i) => i !== index);
    newSteps.forEach((step, i) => step.step_number = i + 1);
    setFormData({ ...formData, steps: newSteps });
  };

  const moveStep = (fromIndex, toIndex) => {
    if (toIndex < 0 || toIndex >= formData.steps.length) return;

    const newSteps = [...formData.steps];
    const [moved] = newSteps.splice(fromIndex, 1);
    newSteps.splice(toIndex, 0, moved);
    newSteps.forEach((step, i) => (step.step_number = i + 1));
    setFormData({ ...formData, steps: newSteps });
  };

  const toggleRequirement = (reqId) => {
    setFormData(prev => ({
      ...prev,
      requirement_ids: prev.requirement_ids.includes(reqId)
        ? prev.requirement_ids.filter(id => id !== reqId)
        : [...prev.requirement_ids, reqId]
    }));
  };

  const removeRequirement = (reqId) => {
    setFormData(prev => ({
      ...prev,
      requirement_ids: prev.requirement_ids.filter(id => id !== reqId)
    }));
  };

  const toggleRelease = (releaseId) => {
    setFormData(prev => ({
      ...prev,
      release_ids: prev.release_ids.includes(releaseId)
        ? prev.release_ids.filter(id => id !== releaseId)
        : [...prev.release_ids, releaseId]
    }));
  };

  const removeRelease = (releaseId) => {
    if (!inheritedReleaseIds.includes(releaseId)) {
      setFormData(prev => ({
        ...prev,
        release_ids: prev.release_ids.filter(id => id !== releaseId)
      }));
    }
  };

  const isReleaseInherited = (releaseId) => {
    return inheritedReleaseIds.includes(releaseId);
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {testCase ? 'Edit Test Case' : 'New Test Case'}
              {aiGeneratedData && (
                <Badge variant="outline" className="gap-1 bg-gradient-to-r from-purple-50 to-blue-50 border-purple-200">
                  <Sparkles className="w-3 h-3 text-purple-600" />
                  AI Generated
                </Badge>
              )}
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <Label htmlFor="title">Title *</Label>
              <Input
                id="title"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder="Enter test case title"
                required
              />
            </div>

            <div>
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Test case description"
                rows={3}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Linked Requirements</Label>
                <Popover>
                  <PopoverTrigger asChild>
                    <Button variant="outline" className="w-full justify-start">
                      {formData.requirement_ids.length === 0 ? 'Select requirements' : `${formData.requirement_ids.length} selected`}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-80 p-4 max-h-80 overflow-y-auto">
                    <div className="space-y-2">
                      <p className="text-sm font-semibold text-slate-700 mb-3">Select Requirements</p>
                      {requirements.map((req) => (
                        <div key={req.id} className="flex items-center space-x-2">
                          <Checkbox
                            id={`req-${req.id}`}
                            checked={formData.requirement_ids.includes(req.id)}
                            onCheckedChange={() => toggleRequirement(req.id)}
                          />
                          <label
                            htmlFor={`req-${req.id}`}
                            className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer flex-1"
                          >
                            {req.title}
                          </label>
                        </div>
                      ))}
                    </div>
                  </PopoverContent>
                </Popover>
                {formData.requirement_ids.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {formData.requirement_ids.map(reqId => {
                      const req = requirements.find(r => r.id === reqId);
                      return req ? (
                        <Badge key={reqId} variant="outline" className="gap-1">
                          {req.title.length > 20 ? `${req.title.substring(0, 20)}...` : req.title}
                          <X
                            className="w-3 h-3 cursor-pointer hover:text-red-600"
                            onClick={() => removeRequirement(reqId)}
                          />
                        </Badge>
                      ) : null;
                    })}
                  </div>
                )}
              </div>

              <div>
                <Label>Releases</Label>
                <Popover>
                  <PopoverTrigger asChild>
                    <Button variant="outline" className="w-full justify-start">
                      {formData.release_ids.length === 0 ? 'Select releases' : `${formData.release_ids.length} selected`}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-80 p-4 max-h-80 overflow-y-auto">
                    <div className="space-y-2">
                      <p className="text-sm font-semibold text-slate-700 mb-3">Select Releases</p>
                      {releases.map((rel) => {
                        const inherited = isReleaseInherited(rel.id);
                        return (
                          <div key={rel.id} className="flex items-center space-x-2">
                            <Checkbox
                              id={`rel-${rel.id}`}
                              checked={formData.release_ids.includes(rel.id)}
                              onCheckedChange={() => toggleRelease(rel.id)}
                              disabled={inherited}
                            />
                            <label
                              htmlFor={`rel-${rel.id}`}
                              className={`text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer flex-1 ${inherited ? 'text-slate-500' : ''}`}
                            >
                              {rel.name} {rel.version && `(v${rel.version})`}
                              {inherited && (
                                <span className="text-xs ml-2 text-blue-600">(from requirement)</span>
                              )}
                            </label>
                          </div>
                        );
                      })}
                    </div>
                  </PopoverContent>
                </Popover>
                {formData.release_ids.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {formData.release_ids.map(releaseId => {
                      const rel = releases.find(r => r.id === releaseId);
                      const inherited = isReleaseInherited(releaseId);
                      return rel ? (
                        <Badge 
                          key={releaseId} 
                          variant="outline" 
                          className={`gap-1 ${inherited ? 'bg-blue-50 border-blue-200' : ''}`}
                        >
                          {inherited && <Lock className="w-3 h-3 text-blue-600" />}
                          {rel.name.length > 15 ? `${rel.name.substring(0, 15)}...` : rel.name}
                          {!inherited && (
                            <X
                              className="w-3 h-3 cursor-pointer hover:text-red-600"
                              onClick={() => removeRelease(releaseId)}
                            />
                          )}
                        </Badge>
                      ) : null;
                    })}
                  </div>
                )}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="priority">Priority</Label>
                <Select value={formData.priority} onValueChange={(value) => setFormData({ ...formData, priority: value })}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="critical">Critical</SelectItem>
                    <SelectItem value="high">High</SelectItem>
                    <SelectItem value="medium">Medium</SelectItem>
                    <SelectItem value="low">Low</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label htmlFor="status">Status</Label>
                <Select value={formData.status} onValueChange={handleStatusChange}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="draft">Draft</SelectItem>
                    <SelectItem value="ready">Ready</SelectItem>
                    <SelectItem value="in_progress">In Progress</SelectItem>
                    <SelectItem value="passed">Passed</SelectItem>
                    <SelectItem value="failed">Failed</SelectItem>
                    <SelectItem value="blocked">Blocked</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div>
              <Label htmlFor="test_type">Test Type</Label>
              <Select value={formData.test_type} onValueChange={(value) => setFormData({ ...formData, test_type: value })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="manual">Manual</SelectItem>
                  <SelectItem value="automated">Automated</SelectItem>
                  <SelectItem value="both">Both</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label htmlFor="preconditions">Preconditions</Label>
              <Textarea
                id="preconditions"
                value={formData.preconditions}
                onChange={(e) => setFormData({ ...formData, preconditions: e.target.value })}
                placeholder="Any preconditions for this test"
                rows={2}
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <Label>Test Steps</Label>
                <Button type="button" size="sm" variant="outline" onClick={addStep}>
                  <Plus className="w-4 h-4 mr-1" />
                  Add Step
                </Button>
              </div>
              <div className="space-y-3">
                {formData.steps.map((step, index) => (
                  <div key={index} className="border border-slate-200 rounded-lg p-3 space-y-2">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-slate-700">Step {index + 1}</span>
                      <div className="flex items-center gap-1">
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          onClick={() => moveStep(index, index - 1)}
                          disabled={index === 0}
                          aria-label="Move step up"
                        >
                          <ChevronUp className="w-4 h-4" />
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          onClick={() => moveStep(index, index + 1)}
                          disabled={index === formData.steps.length - 1}
                          aria-label="Move step down"
                        >
                          <ChevronDown className="w-4 h-4" />
                        </Button>
                        <Button type="button" size="sm" variant="ghost" onClick={() => removeStep(index)} aria-label="Remove step">
                          <Trash2 className="w-4 h-4 text-red-600" />
                        </Button>
                      </div>
                    </div>
                    <Input
                      placeholder="Action to perform"
                      value={step.action}
                      onChange={(e) => updateStep(index, 'action', e.target.value)}
                    />
                    <Input
                      placeholder="Expected result"
                      value={step.expected_result}
                      onChange={(e) => updateStep(index, 'expected_result', e.target.value)}
                    />
                  </div>
                ))}
              </div>
            </div>

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={isLoading} className="bg-blue-600 hover:bg-blue-700">
                {isLoading ? 'Saving...' : testCase ? 'Update' : 'Create'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* SOD Violation Warning */}
      <AlertDialog open={sodWarningOpen} onOpenChange={setSODWarningOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-amber-600" />
              Segregation of Duty Violation
            </AlertDialogTitle>
            <AlertDialogDescription className="space-y-3">
              <p className="text-slate-700">
                <strong>You cannot perform this action due to SOD policy:</strong>
              </p>
              {sodViolation && (
                <>
                  <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
                    <p className="text-sm text-amber-900 mb-2">
                      <strong>Rule:</strong> {sodViolation.rule.rule_name}
                    </p>
                    <p className="text-sm text-amber-800">
                      {sodViolation.rule.description}
                    </p>
                  </div>
                  <p className="text-sm text-slate-600">
                    You created this test case as <strong>{sodViolation.creator}</strong>. To maintain quality standards and independent review, another team member or administrator must approve it by changing the status to "Ready".
                  </p>
                </>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogAction onClick={() => setSODWarningOpen(false)}>
              Understood
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}