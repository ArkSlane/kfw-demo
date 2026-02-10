
import React, { useState } from "react";
import { testcasesAPI } from "@/api/testcasesClient";
import { requirementsAPI } from "@/api/requirementsClient";
import { releasesAPI } from "@/api/releasesClient";
import { executionsAPI } from "@/api/executionsClient";
import generatorAPI from "@/api/generatorClient";
import automationsAPI from "@/api/automationsClient";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Plus, ClipboardCheck, CheckCircle2, XCircle, AlertCircle, Sparkles, Filter, Bot, User, Calendar, Clock, Trash2, Play, Hash } from "lucide-react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import TestCaseDialog from "../components/testcases/TestCaseDialog";
import ManualExecutionDialog from "../components/testcases/ManualExecutionDialog";
import AutomationReviewDialog from "../components/testcases/AutomationReviewDialog";
import { toast } from "sonner";
import { format } from "date-fns";
import { useNavigate } from "react-router-dom";
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

export default function TestCases() {
  const navigate = useNavigate();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingTestCase, setEditingTestCase] = useState(null);
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterRequirement, setFilterRequirement] = useState("all");
  const [filterRelease, setFilterRelease] = useState("all");
  const [generatingAI, setGeneratingAI] = useState(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [testCaseToDelete, setTestCaseToDelete] = useState(null);
  const [executionDialogOpen, setExecutionDialogOpen] = useState(false);
  const [executingTestCase, setExecutingTestCase] = useState(null);

  const [automationReviewOpen, setAutomationReviewOpen] = useState(false);
  const [automationDraft, setAutomationDraft] = useState(null);
  const [automationDraftTestCase, setAutomationDraftTestCase] = useState(null);
  const [automationVideoUrl, setAutomationVideoUrl] = useState(null);
  const [automationChatMessages, setAutomationChatMessages] = useState([]);
  const [sendingAutomationChat, setSendingAutomationChat] = useState(false);
  const [savingAutomation, setSavingAutomation] = useState(false);
  const [isExecutingAutomation, setIsExecutingAutomation] = useState(false);
  const queryClient = useQueryClient();

  const transformTestCaseFromBackend = (tc) => {
    // Transform backend format back to frontend format
    return {
      ...tc,
      requirement_ids: tc.metadata?.requirement_ids || (tc.requirement_id ? [tc.requirement_id] : []),
      release_ids: tc.metadata?.release_ids || [],
      priority: tc.metadata?.priority || 'medium',
      test_type: tc.metadata?.test_type || 'manual',
      preconditions: tc.metadata?.preconditions || '',
      steps: tc.metadata?.steps || [],
      description: tc.metadata?.description || tc.gherkin || '',
    };
  };

  const { data: testCases, isLoading } = useQuery({
    queryKey: ['testCases'],
    queryFn: async () => {
      const data = await testcasesAPI.list();
      return Array.isArray(data) ? data.map(transformTestCaseFromBackend) : [];
    },
    initialData: [],
  });

  const { data: requirements } = useQuery({
    queryKey: ['requirements'],
    queryFn: () => requirementsAPI.list(),
    initialData: [],
  });

  const { data: releases } = useQuery({
    queryKey: ['releases'],
    queryFn: () => releasesAPI.list(),
    initialData: [],
  });

  const { data: automations } = useQuery({
    queryKey: ['automations'],
    queryFn: async () => [],
    initialData: [],
  });

  const { data: executions } = useQuery({
    queryKey: ['executions'],
    queryFn: async () => {
      const data = await executionsAPI.list({ limit: 200 });
      return Array.isArray(data) ? data : [];
    },
    initialData: [],
    staleTime: 0, // Always refetch on mount
    refetchOnMount: true,
    refetchOnWindowFocus: true,
  });

  const createMutation = useMutation({
    mutationFn: (data) => testcasesAPI.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['testCases'] });
      setDialogOpen(false);
      setEditingTestCase(null);
      toast.success('Test case created successfully!');
    },
    onError: (error) => {
      toast.error('Failed to create test case');
      console.error('Create error:', error);
      console.error('Error response data:', error.response?.data);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => testcasesAPI.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['testCases'] });
      setDialogOpen(false);
      setEditingTestCase(null);
      toast.success('Test case updated successfully!');
    },
    onError: (error) => {
      toast.error('Failed to update test case');
      console.error(error);
    },
  });
  const deleteMutation = useMutation({
    mutationFn: (id) => testcasesAPI.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['testCases'] });
      toast.success('Test case deleted successfully!');
      setDeleteDialogOpen(false);
      setTestCaseToDelete(null);
    },
    onError: (error) => {
      toast.error('Failed to delete test case');
      console.error(error);
    },
  });

  const createExecutionMutation = useMutation({
    mutationFn: async (data) => {
      const execDate = data.execution_date ? new Date(data.execution_date) : new Date();
      const payload = {
        test_case_id: data.test_case_id,
        release_id: data.release_id ?? executingTestCase?.release_ids?.[0] ?? null,
        execution_type: data.execution_type || 'manual',
        result: data.result || 'skipped',
        execution_date: execDate.toISOString(),
        executed_by: data.executed_by || '',
        notes: data.notes || data.execution_notes || '',
        duration_seconds: data.duration_seconds || null,
        metadata: {
          step_results: data.step_results || [],
          defects_found: data.defects_found || '',
          manual_execution: true,
        },
      };
      return executionsAPI.create(payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['executions'] });
      setExecutionDialogOpen(false);
      setExecutingTestCase(null);
      toast.success('Test execution logged successfully!');
    },
    onError: (error) => {
      toast.error('Failed to log test execution');
      console.error(error);
    },
  });

  const handleSubmit = (data) => {
    console.log('TestCase handleSubmit - received data:', data);
    
    // Build gherkin from steps if they exist, otherwise use description
    let gherkin = data.description || '';
    if (data.steps && data.steps.length > 0) {
      gherkin = data.steps.map((step, i) => `Step ${i + 1}: ${step.action}\nExpected: ${step.expected_result}`).join('\n\n');
    }

    // Transform frontend data to backend schema
    const payload = {
      requirement_id: data.requirement_ids?.[0] || '', // backend expects singular requirement_id
      title: data.title,
      gherkin: gherkin,
      status: data.status || 'draft',
      version: 1,
      metadata: {
        priority: data.priority || 'medium',
        test_type: data.test_type || 'manual',
        preconditions: data.preconditions || '',
        steps: data.steps || [],
        requirement_ids: data.requirement_ids || [],
        release_ids: data.release_ids || [],
        description: data.description || '',
      }
    };

    console.log('TestCase handleSubmit - built payload:', payload);

    if (editingTestCase) {
      updateMutation.mutate({ id: editingTestCase.id, data: payload });
    } else {
      createMutation.mutate(payload);
    }
  };

  const handleEdit = (testCase) => {
    setEditingTestCase(testCase);
    setDialogOpen(true);
  };

  const handleDeleteClick = (testCase, e) => {
    e.stopPropagation();
    setTestCaseToDelete(testCase);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = () => {
    if (testCaseToDelete) {
      deleteMutation.mutate(testCaseToDelete.id);
    }
  };

  const handleStartExecution = (testCase, e) => {
    e.stopPropagation();
    if (!testCase.steps || testCase.steps.length === 0) {
      toast.error('This test case has no steps defined. Please add steps before executing.');
      return;
    }
    setExecutingTestCase(testCase);
    setExecutionDialogOpen(true);
  };

  const handleExecutionComplete = (executionData) => {
    createExecutionMutation.mutate(executionData);
  };

  const handleGenerateAutomation = async (testCase) => {
    console.log('Starting automation generation for:', testCase);
    console.log('Setting generatingAI to:', testCase.id);
    setGeneratingAI(testCase.id);
    
    try {
      // Draft-first flow: generate a reviewable draft and only persist after user approval.
      console.log('Calling generatorAPI.generateAutomationDraft (execution-based)...');
      const draft = await generatorAPI.generateAutomationDraft({ id: testCase.id });

      setAutomationDraft(draft);
      setAutomationDraftTestCase(testCase);
      setAutomationChatMessages([]);
      setAutomationReviewOpen(true);

      toast.success('Automation draft generated. Review before saving.');
    } catch (error) {
      console.error('Automation generation error:', error);
      toast.error('Failed to generate automation');
    } finally {
      console.log('Setting generatingAI to null');
      setGeneratingAI(null);
    }
  };

  const handleSendAutomationChat = async ({ message, currentScript, setScript }) => {
    if (!automationDraftTestCase || !automationDraft) return;
    const nextMessages = [...automationChatMessages, { role: 'user', content: message }];
    setAutomationChatMessages(nextMessages);
    setSendingAutomationChat(true);

    try {
      const res = await generatorAPI.automationChat({
        test_case_id: automationDraftTestCase.id,
        message,
        history: nextMessages,
        context: {
          script_outline: currentScript,
          actions_taken: automationDraft.actions_taken,
          transcript: automationDraft.transcript,
          exec_error: automationDraft.exec_error,
          video_filename: automationDraft.video_filename,
        },
      });

      setAutomationChatMessages((prev) => [...prev, { role: 'assistant', content: res.reply }]);
      if (res.suggested_script && typeof res.suggested_script === 'string') {
        setScript(res.suggested_script);
        toast.success('Updated script from chat suggestion');
      }

      // If the generator executed the suggested script, update draft metadata and show fresh video
      if (typeof res.exec_success !== 'undefined' || res.video_filename || res.video_path) {
        setAutomationDraft((prev) => {
          if (!prev) return prev;
          const updated = {
            ...prev,
            exec_success: typeof res.exec_success !== 'undefined' ? res.exec_success : prev.exec_success,
            exec_error: res.exec_error ?? prev.exec_error,
            video_filename: res.video_filename ?? prev.video_filename,
            video_path: res.video_path ?? prev.video_path,
          };
          return updated;
        });

        // Build a cache-busted video URL so the player loads the fresh recording immediately
        const vf = res.video_filename || (automationDraft && automationDraft.video_filename);
        if (vf) {
          try {
            const raw = automationsAPI.getRawVideoUrl(vf);
            const url = `${raw}?t=${Date.now()}`;
            setAutomationVideoUrl(url);
            // Notify the user that a fresh recording is available
            toast.success('New recording available');
          } catch (e) {
            // ignore
          }
        }
      }
    } catch (error) {
      console.error('Automation chat error:', error);
      toast.error('Failed to send chat message');
    } finally {
      setSendingAutomationChat(false);
    }
  };

  const handleExecuteFromDialog = async (script) => {
    if (!automationDraftTestCase) return;
    setIsExecutingAutomation(true);
    try {
      const resp = await generatorAPI.executeScript({ test_case_id: automationDraftTestCase.id, script });

      if (resp.video_path) {
        const busted = `${resp.video_path}?t=${Date.now()}`;
        setAutomationVideoUrl(busted);
        toast.success('Execution finished — fresh recording available');
      } else if (resp.exec_error) {
        toast.error(`Execution failed: ${resp.exec_error}`);
      } else {
        toast.info('Execution completed');
      }

      if (resp.actions_taken) {
        setAutomationDraft((prev) => ({ ...(prev || {}), actions_taken: resp.actions_taken }));
      }
    } catch (e) {
      console.error('Execute script error:', e);
      toast.error('Execution request failed');
    } finally {
      setIsExecutingAutomation(false);
    }
  };

  const handleSaveAutomation = async ({ script }) => {
    if (!automationDraftTestCase || !automationDraft) return;
    setSavingAutomation(true);
    try {
      const automationPayload = {
        test_case_id: automationDraftTestCase.id,
        title: automationDraft.title || automationDraftTestCase.title,
        framework: automationDraft.framework || 'playwright',
        script,
        status: automationDraft.exec_success ? 'not_started' : 'blocked',
        notes: automationDraft.notes,
        last_actions: automationDraft.actions_taken || null,
        metadata: automationDraft.metadata || {},
        video_path: automationDraft.video_path || null,
      };

      const saved = await automationsAPI.create(automationPayload);

      // Update test case metadata only after the user explicitly saved the automation.
      const updatePayload = {
        metadata: {
          ...(automationDraftTestCase.metadata || {}),
          test_type: 'automated',
          automation_id: saved?.id,
          automation_framework: automationDraft.framework,
          automation_script_outline: script,
          automation_notes: automationDraft.notes,
        },
      };

      await testcasesAPI.update(automationDraftTestCase.id, updatePayload);
      queryClient.invalidateQueries({ queryKey: ['testCases'] });

      toast.success('Automation saved');
      setAutomationReviewOpen(false);
      setAutomationDraft(null);
      setAutomationDraftTestCase(null);
      setAutomationChatMessages([]);
      navigate('/Automations');
    } catch (error) {
      console.error('Save automation error:', error);
      toast.error('Failed to save automation');
    } finally {
      setSavingAutomation(false);
    }
  };

  const filteredTestCases = testCases.filter(tc => {
    const statusMatch = filterStatus === "all" || tc.status === filterStatus;
    const requirementMatch = filterRequirement === "all" || (tc.requirement_ids && tc.requirement_ids.includes(filterRequirement));
    
    // Release match: check if the test case's linked requirement has the selected release_id
    let releaseMatch = filterRelease === "all";
    if (!releaseMatch && tc.requirement_id) {
      const linkedRequirement = requirements.find(r => r.id === tc.requirement_id);
      releaseMatch = linkedRequirement?.release_id === filterRelease;
    }
    
    return statusMatch && requirementMatch && releaseMatch;
  });

  const statusColors = {
    draft: 'bg-slate-100 text-slate-700 border-slate-200',
    ready: 'bg-blue-100 text-blue-700 border-blue-200',
    in_progress: 'bg-purple-100 text-purple-700 border-purple-200',
    passed: 'bg-green-100 text-green-700 border-green-200',
    failed: 'bg-red-100 text-red-700 border-red-200',
    blocked: 'bg-orange-100 text-orange-700 border-orange-200',
    not_started: 'bg-slate-100 text-slate-600 border-slate-200',
    maintenance: 'bg-orange-100 text-orange-600 border-orange-200',
    passing: 'bg-green-100 text-green-700 border-green-200',
    failing: 'bg-red-100 text-red-700 border-red-200',
  };

  const priorityColors = {
    critical: 'bg-red-100 text-red-700 border-red-200',
    high: 'bg-orange-100 text-orange-700 border-orange-200',
    medium: 'bg-yellow-100 text-yellow-700 border-yellow-200',
    low: 'bg-blue-100 text-blue-700 border-blue-200',
  };

  const getRequirementTitles = (reqIds) => {
    if (!reqIds || reqIds.length === 0) return null;
    return reqIds.map(id => {
      const req = requirements.find(r => r.id === id);
      return req ? req.title : null;
    }).filter(Boolean);
  };

  const getLinkedAutomations = (testCaseId) => {
    return automations.filter(auto => auto.test_case_id === testCaseId);
  };

  const getLastExecutionStatus = (testCaseId) => {
    // Get manual executions
    const manualExecs = executions.filter(e => e.test_case_id === testCaseId);
    // Get automated executions from automations
    const autoExecs = automations.filter(a => a.test_case_id === testCaseId && a.last_run_result);

    let lastExecution = null;

    // Find most recent manual execution
    if (manualExecs.length > 0) {
      const mostRecentManual = manualExecs.reduce((latest, current) => {
        // Use created_at as tiebreaker when execution_date is the same
        const latestExecDate = new Date(latest.execution_date || latest.created_at);
        const currentExecDate = new Date(current.execution_date || current.created_at);
        
        // If execution dates are different, use execution date
        if (currentExecDate.getTime() !== latestExecDate.getTime()) {
          return currentExecDate > latestExecDate ? current : latest;
        }
        
        // If execution dates are same, use created_at as tiebreaker
        const latestCreated = new Date(latest.created_at);
        const currentCreated = new Date(current.created_at);
        return currentCreated > latestCreated ? current : latest;
      });
      lastExecution = {
        result: mostRecentManual.result,
        date: new Date(mostRecentManual.created_at), // Use created_at for more precision
        type: 'manual'
      };
    }

    // Find most recent automated execution
    if (autoExecs.length > 0) {
      const mostRecentAuto = autoExecs.reduce((latest, current) => {
        if (!latest.last_run_date) return current;
        if (!current.last_run_date) return latest;
        return new Date(current.last_run_date) > new Date(latest.last_run_date) ? current : latest;
      });
      const autoDate = mostRecentAuto.last_run_date ? new Date(mostRecentAuto.last_run_date) : null;
      
      if (autoDate && (!lastExecution || autoDate > lastExecution.date)) {
        lastExecution = {
          result: mostRecentAuto.last_run_result,
          date: autoDate,
          type: 'automated'
        };
      }
    }

    return lastExecution;
  };

  return (
    <div className="p-6 lg:p-8 space-y-6">
      <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 mb-2">Test Cases</h1>
          <p className="text-slate-600">Create and manage test cases</p>
        </div>
        <Button 
          onClick={() => {
            setEditingTestCase(null);
            setDialogOpen(true);
          }}
          className="bg-blue-600 hover:bg-blue-700 gap-2"
        >
          <Plus className="w-4 h-4" />
          New Test Case
        </Button>
      </div>

      <Card className="border-none shadow-md">
        <CardHeader className="border-b border-slate-100">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <CardTitle className="text-lg font-semibold">All Test Cases</CardTitle>
            <div className="flex items-center gap-3 flex-wrap">
              <div className="flex items-center gap-2">
                <Filter className="w-4 h-4 text-slate-600" />
                <Select value={filterRequirement} onValueChange={setFilterRequirement}>
                  <SelectTrigger className="w-[200px]">
                    <SelectValue placeholder="Filter by Requirement" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Requirements</SelectItem>
                    {requirements.map((req) => (
                      <SelectItem key={req.id} value={req.id}>
                        {req.title.length > 30 ? req.title.substring(0, 30) + '...' : req.title}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Select value={filterRelease} onValueChange={setFilterRelease}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Filter by Release" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Releases</SelectItem>
                  {releases.map((rel) => (
                    <SelectItem key={rel.id} value={rel.id}>
                      {rel.name} {rel.version && `(v${rel.version})`}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Tabs value={filterStatus} onValueChange={setFilterStatus}>
                <TabsList className="bg-slate-100">
                  <TabsTrigger value="all">All</TabsTrigger>
                  <TabsTrigger value="draft">Draft</TabsTrigger>
                  <TabsTrigger value="ready">Ready</TabsTrigger>
                  <TabsTrigger value="passed">Passed</TabsTrigger>
                  <TabsTrigger value="failed">Failed</TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-6">
          {isLoading ? (
            <div className="text-center py-12 text-slate-500">Loading...</div>
          ) : filteredTestCases.length === 0 ? (
            <div className="text-center py-12">
              <ClipboardCheck className="w-16 h-16 mx-auto mb-4 text-slate-300" />
              <p className="text-slate-500 mb-4">No test cases found</p>
              <Button onClick={() => setDialogOpen(true)} variant="outline">
                <Plus className="w-4 h-4 mr-2" />
                Create your first test case
              </Button>
            </div>
          ) : (
            <div className="grid gap-4">
              {filteredTestCases.map((test) => {
                const reqTitles = getRequirementTitles(test.requirement_ids);
                const linkedAutomations = getLinkedAutomations(test.id);
                const hasAutomation = linkedAutomations.length > 0;
                const hasFailedAutomation = linkedAutomations.some(auto => 
                  auto.last_run_result === 'failed' || auto.status === 'failing'
                );
                const isManualTest = test.test_type === 'manual' || test.test_type === 'both';
                const lastExec = getLastExecutionStatus(test.id);
                
                return (
                  <Card 
                    key={test.id}
                    className={`border transition-all ${
                      hasFailedAutomation 
                        ? 'border-red-300 bg-red-50/30 hover:shadow-lg' 
                        : 'border-slate-200 hover:shadow-lg'
                    }`}
                  >
                    <CardContent className="p-6">
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex-1 cursor-pointer" onClick={() => handleEdit(test)}>
                          <div className="flex items-center gap-2 mb-2">
                            <h3 className="text-lg font-semibold text-slate-900">{test.title}</h3>
                            {lastExec && (
                              <Badge 
                                variant="outline" 
                                className={`gap-1 text-xs ${
                                  lastExec.result === 'passed' 
                                    ? 'border-green-300 bg-green-50 text-green-700'
                                    : lastExec.result === 'failed'
                                    ? 'border-red-300 bg-red-50 text-red-700'
                                    : lastExec.result === 'blocked'
                                    ? 'border-orange-300 bg-orange-50 text-orange-700'
                                    : 'border-slate-300 bg-slate-50 text-slate-700'
                                }`}
                              >
                                {lastExec.result === 'passed' && <CheckCircle2 className="w-3 h-3" />}
                                {lastExec.result === 'failed' && <XCircle className="w-3 h-3" />}
                                {lastExec.result === 'blocked' && <AlertCircle className="w-3 h-3" />}
                                {lastExec.result === 'skipped' && <AlertCircle className="w-3 h-3" />}
                                Last: {lastExec.result}
                                <span className="text-[10px] opacity-70">({lastExec.type})</span>
                              </Badge>
                            )}
                            <Badge 
                              variant="outline" 
                              className="gap-1 text-xs text-slate-500 border-slate-300 cursor-pointer hover:bg-slate-100 hover:border-slate-400 transition-colors font-mono"
                              onClick={(e) => {
                                e.stopPropagation();
                                navigator.clipboard.writeText(test.id);
                                toast.success('ID copied to clipboard!');
                              }}
                              title="Click to copy ID"
                            >
                              <Hash className="w-3 h-3" />
                              {test.id}
                            </Badge>
                          </div>
                          <p className="text-slate-600 text-sm line-clamp-2">{test.description}</p>
                          {reqTitles && reqTitles.length > 0 && (
                            <div className="mt-2 flex flex-wrap gap-1">
                              {reqTitles.map((title, idx) => (
                                <Badge key={idx} variant="outline" className="text-xs text-blue-600">
                                  📋 {title.length > 30 ? title.substring(0, 30) + '...' : title}
                                </Badge>
                              ))}
                            </div>
                          )}
                        </div>
                        <div className="ml-4 flex items-center gap-2">
                          {isManualTest && (
                            <Button
                              size="sm"
                              variant="outline"
                              className="gap-2 bg-gradient-to-r from-green-50 to-emerald-50 border-green-200 hover:from-green-100 hover:to-emerald-100"
                              onClick={(e) => handleStartExecution(test, e)}
                            >
                              <Play className="w-3 h-3 text-green-600" />
                              Execute
                            </Button>
                          )}
                          {!hasAutomation && (
                            <Button
                              size="sm"
                              variant="outline"
                              className="gap-2 bg-gradient-to-r from-purple-50 to-blue-50 border-purple-200 hover:from-purple-100 hover:to-blue-100"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleGenerateAutomation(test);
                              }}
                              disabled={generatingAI === test.id}
                            >
                              {generatingAI === test.id ? (
                                <>
                                  <div className="animate-spin rounded-full h-3 w-3 border-2 border-purple-600 border-t-transparent" />
                                  Generating...
                                </>
                              ) : (
                                <>
                                  <Sparkles className="w-3 h-3 text-purple-600" />
                                  AI Automation
                                </>
                              )}
                            </Button>
                          )}
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={(e) => handleDeleteClick(test, e)}
                            className="text-red-600 hover:text-red-700 hover:bg-red-50"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                          {test.status === 'passed' && <CheckCircle2 className="w-6 h-6 text-green-600" />}
                          {test.status === 'failed' && <XCircle className="w-6 h-6 text-red-600" />}
                          {test.status === 'blocked' && <AlertCircle className="w-6 h-6 text-orange-600" />}
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {(() => {
                          const linkedRequirement = requirements.find(r => r.id === test.requirement_id);
                          if (linkedRequirement?.release_id) {
                            const release = releases.find(rel => rel.id === linkedRequirement.release_id);
                            return (
                              <Badge variant="outline" className="text-green-600 border-green-300 bg-green-50">
                                {release?.name || linkedRequirement.release_id}
                              </Badge>
                            );
                          }
                          return (
                            <Badge variant="outline" className="text-slate-500 border-slate-300">
                              No release assigned
                            </Badge>
                          );
                        })()}
                        <Badge className={`border ${statusColors[test.status]}`}>
                          {test.status}
                        </Badge>
                        <Badge className={`border ${priorityColors[test.priority]}`}>
                          {test.priority}
                        </Badge>
                        <Badge variant="outline" className="text-slate-600">
                          {test.test_type}
                        </Badge>
                        {test.steps && test.steps.length > 0 && (
                          <Badge variant="outline" className="text-slate-600">
                            {test.steps.length} steps
                          </Badge>
                        )}
                      </div>
                      
                      {/* Automation Status Section */}
                      <div className="mt-3 pt-3 border-t border-slate-100">
                        {hasAutomation ? (
                          <div>
                            <div className="flex items-center gap-2 mb-3">
                              <Bot className="w-4 h-4 text-purple-600" />
                              <p className="text-xs font-medium text-slate-700">
                                Linked Automations ({linkedAutomations.length}):
                              </p>
                            </div>
                            <div className="space-y-2">
                              {linkedAutomations.map(auto => {
                                const isFailed = auto.last_run_result === 'failed' || auto.status === 'failing';
                                const isPassed = auto.last_run_result === 'passed' || auto.status === 'passing';
                                
                                return (
                                  <div
                                    key={auto.id}
                                    className={`p-3 rounded-lg border transition-all ${
                                      isFailed 
                                        ? 'border-red-300 bg-red-50' 
                                        : isPassed
                                        ? 'border-green-200 bg-green-50'
                                        : 'border-slate-200 bg-slate-50'
                                    }`}
                                  >
                                    <div className="flex items-start justify-between gap-3">
                                      <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                          <Bot className={`w-3 h-3 ${isFailed ? 'text-red-600' : 'text-purple-600'}`} />
                                          <span className={`text-sm font-medium ${isFailed ? 'text-red-900' : 'text-slate-900'}`}>
                                            {auto.title}
                                          </span>
                                        </div>
                                        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
                                          <Badge variant="outline" className="text-xs">
                                            {auto.framework}
                                          </Badge>
                                          <Badge className={`border text-xs ${statusColors[auto.status]}`}>
                                            {auto.status.replace(/_/g, ' ')}
                                          </Badge>
                                          {auto.last_run_date && (
                                            <span className="flex items-center gap-1">
                                              <Calendar className="w-3 h-3" />
                                              {format(new Date(auto.last_run_date), 'MMM d, yyyy')}
                                            </span>
                                          )}
                                          {auto.execution_time && (
                                            <span className="flex items-center gap-1">
                                              <Clock className="w-3 h-3" />
                                              {auto.execution_time}s
                                            </span>
                                          )}
                                        </div>
                                      </div>
                                      {auto.last_run_result && (
                                        <div className="shrink-0">
                                          {auto.last_run_result === 'passed' && (
                                            <CheckCircle2 className="w-5 h-5 text-green-600" />
                                          )}
                                          {auto.last_run_result === 'failed' && (
                                            <XCircle className="w-5 h-5 text-red-600" />
                                          )}
                                          {auto.last_run_result === 'skipped' && (
                                            <AlertCircle className="w-5 h-5 text-slate-400" />
                                          )}
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        ) : (
                          <div className="flex items-center gap-2">
                            <User className="w-4 h-4 text-blue-600" />
                            <p className="text-xs text-slate-600">
                              <span className="font-medium text-blue-600">Manual Test Case</span> - No automation linked
                            </p>
                          </div>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <TestCaseDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        testCase={editingTestCase}
        requirements={requirements}
        onSubmit={handleSubmit}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />

      <ManualExecutionDialog
        open={executionDialogOpen}
        onOpenChange={setExecutionDialogOpen}
        testCase={executingTestCase}
        onComplete={handleExecutionComplete}
        releases={releases}
      />

      <AutomationReviewDialog
        open={automationReviewOpen}
        onOpenChange={setAutomationReviewOpen}
        testCase={automationDraftTestCase}
        draft={automationDraft}
        videoUrl={
          automationVideoUrl || (automationDraft?.video_path && automationDraft?.video_filename
            ? automationsAPI.getRawVideoUrl(automationDraft.video_filename)
            : null)
        }
        chatMessages={automationChatMessages}
        onSendChat={handleSendAutomationChat}
        onSave={handleSaveAutomation}
        isSendingChat={sendingAutomationChat}
        isSaving={savingAutomation}
        onExecute={handleExecuteFromDialog}
        isExecuting={isExecutingAutomation}
      />

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Test Case</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{testCaseToDelete?.title}"? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteConfirm}
              className="bg-red-600 hover:bg-red-700"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
