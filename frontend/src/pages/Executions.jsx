import React, { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Plus, PlayCircle, CheckCircle2, XCircle, AlertCircle, Clock, Filter, User, Eye, Upload } from "lucide-react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import ExecutionDialog from "../components/executions/ExecutionDialog";
import ExecutionDetailsDialog from "../components/executions/ExecutionDetailsDialog";
import ApiInfoDialog from "../components/executions/ApiInfoDialog";
import { executionsAPI } from "../api/executionsClient";
import { releasesAPI } from "../api/releasesClient";
import { testcasesAPI } from "../api/testcasesClient";
import { format } from "date-fns";
import { toast } from "sonner";

export default function Executions() {
  const location = useLocation();
  const searchParams = new URLSearchParams(location.search || "");
  const executionIdFromQuery = searchParams.get('execution_id');

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingExecution, setEditingExecution] = useState(null);
  const [detailsDialogOpen, setDetailsDialogOpen] = useState(false);
  const [viewingExecution, setViewingExecution] = useState(null);
  const [apiInfoDialogOpen, setApiInfoDialogOpen] = useState(false);
  const [filterResult, setFilterResult] = useState("all");
  const [filterRelease, setFilterRelease] = useState("all");
  const [viewMode, setViewMode] = useState("all");
  const queryClient = useQueryClient();

  const { data: executions, isLoading: loadingExecutions } = useQuery({
    queryKey: ['executions', { filterResult, filterRelease }],
    queryFn: async () => executionsAPI.list({
      result: filterResult === 'all' ? undefined : filterResult,
      release_id: filterRelease === 'all' ? undefined : filterRelease,
    }),
    initialData: [],
  });

  const { data: directExecution } = useQuery({
    queryKey: ['execution', executionIdFromQuery],
    queryFn: async () => executionsAPI.get(executionIdFromQuery),
    enabled: Boolean(executionIdFromQuery),
    initialData: null,
  });

  const { data: automations, isLoading: loadingAutomations } = useQuery({
    queryKey: ['automations'],
    queryFn: async () => [],
    initialData: [],
    enabled: false,
  });

  const { data: testCases } = useQuery({
    queryKey: ['testCases'],
    queryFn: async () => testcasesAPI.list(),
    initialData: [],
  });

  const { data: releases } = useQuery({
    queryKey: ['releases'],
    queryFn: async () => releasesAPI.list(),
    initialData: [],
  });

  const createMutation = useMutation({
    mutationFn: async (data) => executionsAPI.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['executions'] });
      setDialogOpen(false);
      setEditingExecution(null);
      toast.success('Execution created');
    },
    onError: () => toast.error('Failed to create execution'),
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, data }) => executionsAPI.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['executions'] });
      setDialogOpen(false);
      setEditingExecution(null);
      toast.success('Execution updated');
    },
    onError: () => toast.error('Failed to update execution'),
  });

  const handleSubmit = (data) => {
    if (editingExecution) {
      updateMutation.mutate({ id: editingExecution.id, data });
    } else {
      createMutation.mutate(data);
    }
  };

  const handleEdit = (execution) => {
    setEditingExecution(execution);
    setDialogOpen(true);
  };

  const handleViewDetails = (execution, testCase) => {
    setViewingExecution({ ...execution, testCase });
    setDetailsDialogOpen(true);
  };

  const filteredExecutions = (executions || []).filter(exec => {
    const resultMatch = filterResult === "all" || exec.result === filterResult;
    const releaseMatch = filterRelease === "all" || exec.release_id === filterRelease;
    return resultMatch && releaseMatch;
  });

  const automatedExecutions = automations
    .filter(auto => auto.last_run_result && auto.last_run_date)
    .filter(auto => {
      const resultMatch = filterResult === "all" || auto.last_run_result === filterResult;
      const releaseMatch = filterRelease === "all" || auto.release_id === filterRelease;
      return resultMatch && releaseMatch;
    });

  const allExecutions = [
    ...filteredExecutions.map(exec => ({
      ...exec,
      type: exec.execution_type || 'manual',
      date: exec.execution_date,
      executor: exec.executed_by,
    })),
    ...automatedExecutions.map(auto => ({
      ...auto,
      type: 'automated',
      date: auto.last_run_date,
      result: auto.last_run_result,
      duration: auto.execution_time ? Math.round(auto.execution_time / 60) : null,
    }))
  ].sort((a, b) => new Date(b.date) - new Date(a.date));

  const displayExecutions = viewMode === "all" 
    ? allExecutions 
    : allExecutions.filter(exec => exec.type === viewMode);

  const resultColors = {
    passed: 'bg-green-100 text-green-700 border-green-200',
    failed: 'bg-red-100 text-red-700 border-red-200',
    blocked: 'bg-orange-100 text-orange-700 border-orange-200',
    skipped: 'bg-slate-100 text-slate-700 border-slate-200',
  };

  const getTestCaseTitle = (testCaseId) => {
    const testCase = testCases.find(tc => tc.id === testCaseId);
    return testCase ? testCase.title : 'Unknown Test Case';
  };

  const getTestCase = (testCaseId) => {
    return testCases.find(tc => tc.id === testCaseId);
  };

  useEffect(() => {
    if (!executionIdFromQuery) return;
    if (!directExecution) return;
    if (!Array.isArray(testCases) || testCases.length === 0) return;

    const tc = getTestCase(directExecution.test_case_id);
    setViewingExecution({ ...directExecution, testCase: tc });
    setDetailsDialogOpen(true);
  }, [executionIdFromQuery, directExecution, testCases]);

  const getStats = () => {
    const passed = displayExecutions.filter(e => e.result === 'passed').length;
    const failed = displayExecutions.filter(e => e.result === 'failed').length;
    const blocked = displayExecutions.filter(e => e.result === 'blocked').length;
    const skipped = displayExecutions.filter(e => e.result === 'skipped').length;
    const total = displayExecutions.length;
    const passRate = total > 0 ? Math.round((passed / total) * 100) : 0;

    return { passed, failed, blocked, skipped, total, passRate };
  };

  const stats = getStats();

  return (
    <div className="p-6 lg:p-8 space-y-6">
      <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 mb-2">Test Executions</h1>
          <p className="text-slate-600">Track manual and automated test execution results</p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => setApiInfoDialogOpen(true)}
            className="gap-2"
          >
            <Upload className="w-4 h-4" />
            API Documentation
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Card className="border-none shadow-md">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-600 mb-1">Total</p>
                <p className="text-2xl font-bold text-slate-900">{stats.total}</p>
              </div>
              <PlayCircle className="w-8 h-8 text-blue-600" />
            </div>
          </CardContent>
        </Card>

        <Card className="border-none shadow-md">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-600 mb-1">Passed</p>
                <p className="text-2xl font-bold text-green-600">{stats.passed}</p>
              </div>
              <CheckCircle2 className="w-8 h-8 text-green-600" />
            </div>
          </CardContent>
        </Card>

        <Card className="border-none shadow-md">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-600 mb-1">Failed</p>
                <p className="text-2xl font-bold text-red-600">{stats.failed}</p>
              </div>
              <XCircle className="w-8 h-8 text-red-600" />
            </div>
          </CardContent>
        </Card>

        <Card className="border-none shadow-md">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-600 mb-1">Blocked</p>
                <p className="text-2xl font-bold text-orange-600">{stats.blocked}</p>
              </div>
              <AlertCircle className="w-8 h-8 text-orange-600" />
            </div>
          </CardContent>
        </Card>

        <Card className="border-none shadow-md bg-gradient-to-br from-blue-500 to-purple-500">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-white/80 mb-1">Pass Rate</p>
                <p className="text-2xl font-bold text-white">{stats.passRate}%</p>
              </div>
              <CheckCircle2 className="w-8 h-8 text-white/80" />
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="border-none shadow-md">
        <CardHeader className="border-b border-slate-100">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <CardTitle className="text-lg font-semibold">All Executions</CardTitle>
            <div className="flex items-center gap-3 flex-wrap">
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

              <Tabs value={viewMode} onValueChange={setViewMode}>
                <TabsList className="bg-slate-100">
                  <TabsTrigger value="all">All</TabsTrigger>
                  <TabsTrigger value="manual">Manual</TabsTrigger>
                  <TabsTrigger value="automated">Automated</TabsTrigger>
                </TabsList>
              </Tabs>

              <Tabs value={filterResult} onValueChange={setFilterResult}>
                <TabsList className="bg-slate-100">
                  <TabsTrigger value="all">All</TabsTrigger>
                  <TabsTrigger value="passed">Passed</TabsTrigger>
                  <TabsTrigger value="failed">Failed</TabsTrigger>
                  <TabsTrigger value="blocked">Blocked</TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-6">
          {loadingExecutions || loadingAutomations ? (
            <div className="text-center py-12 text-slate-500">Loading...</div>
          ) : displayExecutions.length === 0 ? (
            <div className="text-center py-12">
              <PlayCircle className="w-16 h-16 mx-auto mb-4 text-slate-300" />
              <p className="text-slate-500">No executions found</p>
            </div>
          ) : (
            <div className="space-y-3">
              {displayExecutions.map((execution, index) => {
                const testCase = getTestCase(execution.test_case_id);
                const hasStepResults = execution.step_results && execution.step_results.length > 0;
                
                return (
                  <Card 
                    key={`${execution.type}-${execution.id || index}`}
                    className="border border-slate-200 hover:shadow-lg transition-all"
                  >
                    <CardContent className="p-5">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-2">
                            <h3 className="text-base font-semibold text-slate-900 truncate">
                              {getTestCaseTitle(execution.test_case_id)}
                            </h3>
                            <Badge 
                              variant="outline" 
                              className={execution.type === 'manual' ? 'bg-blue-50 text-blue-700 border-blue-200' : 'bg-purple-50 text-purple-700 border-purple-200'}
                            >
                              {execution.type}
                            </Badge>
                            {hasStepResults && (
                              <Badge variant="outline" className="text-xs">
                                {execution.step_results.filter(s => s.result === 'passed').length}/{execution.step_results.length} steps
                              </Badge>
                            )}
                          </div>
                          
                          <div className="flex flex-wrap gap-3 text-sm text-slate-600 mb-2">
                            <div className="flex items-center gap-1">
                              <Clock className="w-4 h-4" />
                              {format(new Date(execution.date), 'MMM d, yyyy')}
                            </div>
                            {execution.executor && (
                              <div className="flex items-center gap-1">
                                <User className="w-4 h-4" />
                                {execution.executor}
                              </div>
                            )}
                            {execution.duration && (
                              <div className="flex items-center gap-1">
                                <Clock className="w-4 h-4" />
                                {execution.duration} min
                              </div>
                            )}
                            {execution.type === 'automated' && execution.framework && (
                              <Badge variant="outline" className="text-xs">
                                {execution.framework}
                              </Badge>
                            )}
                          </div>

                          {execution.notes && (
                            <p className="text-sm text-slate-600 line-clamp-2 mt-2">
                              {execution.notes}
                            </p>
                          )}

                          {execution.defects_found && (
                            <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-800">
                              ⚠️ Defects: {execution.defects_found}
                            </div>
                          )}
                        </div>

                        <div className="flex flex-col items-end gap-2">
                          <Badge className={`border ${resultColors[execution.result]}`}>
                            {execution.result === 'passed' && <CheckCircle2 className="w-3 h-3 mr-1" />}
                            {execution.result === 'failed' && <XCircle className="w-3 h-3 mr-1" />}
                            {execution.result === 'blocked' && <AlertCircle className="w-3 h-3 mr-1" />}
                            {execution.result}
                          </Badge>
                          <div className="flex gap-1">
                            {execution.type === 'manual' && hasStepResults && (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleViewDetails(execution, testCase)}
                                className="text-xs gap-1"
                              >
                                <Eye className="w-3 h-3" />
                                View Steps
                              </Button>
                            )}
                            {execution.type === 'manual' && !hasStepResults && (
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => handleEdit(execution)}
                                className="text-xs"
                              >
                                Edit
                              </Button>
                            )}
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <ExecutionDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        execution={editingExecution}
        testCases={testCases}
        releases={releases}
        onSubmit={handleSubmit}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />

      <ExecutionDetailsDialog
        open={detailsDialogOpen}
        onOpenChange={setDetailsDialogOpen}
        execution={viewingExecution}
        testCase={viewingExecution?.testCase}
      />

      <ApiInfoDialog
        open={apiInfoDialogOpen}
        onOpenChange={setApiInfoDialogOpen}
      />
    </div>
  );
}