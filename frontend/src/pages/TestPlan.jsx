
import React, { useState, useEffect, useMemo } from "react";
import { requirementsAPI } from "@/api/requirementsClient";
import { testcasesAPI } from "@/api/testcasesClient";
import { releasesAPI } from "@/api/releasesClient";
import { executionsAPI } from "@/api/executionsClient";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import { createPageUrl } from "@/utils";
import { FileText, ClipboardCheck, Bot, Plus, TrendingUp, CheckCircle2, AlertCircle, Package, Filter, X, ChevronLeft, ChevronRight, XCircle, Clock, Target, Calendar, Layers } from "lucide-react";
import StatsCard from "../components/dashboard/StatsCard";
import TestCasesByRequirement from "../components/dashboard/TestCasesByRequirement";
import TestCaseDialog from "../components/testcases/TestCaseDialog";
import { Badge } from "@/components/ui/badge";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Checkbox } from "@/components/ui/checkbox";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { format, subDays, startOfDay, differenceInDays } from 'date-fns';
import { toast } from "sonner";

export default function TestPlan() {
  const [selectedReleases, setSelectedReleases] = useState([]);
  const [requirementsPage, setRequirementsPage] = useState(1);
  const [testCasesPage, setTestCasesPage] = useState(1);
  const [trendDays, setTrendDays] = useState(7);
  const [viewMode, setViewMode] = useState("list");
  const [testCaseDialogOpen, setTestCaseDialogOpen] = useState(false);
  const [editingTestCase, setEditingTestCase] = useState(null);
  const [selectedRequirement, setSelectedRequirement] = useState(null);
  const itemsPerPage = 5;
  const queryClient = useQueryClient();

  const { data: releases } = useQuery({
    queryKey: ['releases'],
    queryFn: () => releasesAPI.list(),
    initialData: [],
  });

  const { data: requirements, isLoading: loadingReqs } = useQuery({
    queryKey: ['requirements'],
    queryFn: () => requirementsAPI.list(),
    initialData: [],
  });

  const transformTestCaseFromBackend = (tc) => ({
    ...tc,
    requirement_ids: tc.metadata?.requirement_ids || (tc.requirement_id ? [tc.requirement_id] : []),
    release_ids: tc.metadata?.release_ids || [],
    priority: tc.metadata?.priority || 'medium',
    test_type: tc.metadata?.test_type || 'manual',
    preconditions: tc.metadata?.preconditions || '',
    steps: tc.metadata?.steps || [],
    description: tc.metadata?.description || tc.gherkin || '',
  });

  const transformExecutionFromBackend = (exec) => ({
    ...exec,
    execution_date: exec.execution_date || exec.created_at || exec.updated_at || new Date().toISOString(),
    execution_type: exec.execution_type || 'manual',
    result: exec.result || 'skipped',
  });

  const { data: testCases, isLoading: loadingTests } = useQuery({
    queryKey: ['testCases'],
    queryFn: async () => {
      const data = await testcasesAPI.list();
      return Array.isArray(data) ? data.map(transformTestCaseFromBackend) : [];
    },
    initialData: [],
  });

  const { data: automations, isLoading: loadingAutos } = useQuery({
    queryKey: ['automations'],
    queryFn: async () => [],
    initialData: [],
  });

  const { data: executions, isLoading: loadingExecutions } = useQuery({
    queryKey: ['executions'],
    queryFn: async () => {
      const data = await executionsAPI.list({ limit: 200 });
      return Array.isArray(data) ? data.map(transformExecutionFromBackend) : [];
    },
    initialData: [],
  });

  // Normalize test case shape so release filters work even if backend returns singular fields
  const normalizedTestCases = useMemo(() => {
    return testCases.map(tc => ({
      ...tc,
      release_ids: tc.release_ids || (tc.release_id ? [tc.release_id] : []),
      requirement_ids: tc.requirement_ids || (tc.requirement_id ? [tc.requirement_id] : []),
    }));
  }, [testCases]);

  const buildTestcasePayload = (data) => {
    let gherkin = data.description || '';
    if (data.steps && data.steps.length > 0) {
      gherkin = data.steps.map((step, i) => `Step ${i + 1}: ${step.action}\nExpected: ${step.expected_result}`).join('\n\n');
    }
    return {
      requirement_id: data.requirement_ids?.[0] || '',
      title: data.title,
      gherkin,
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
      },
    };
  };

  const createTestCaseMutation = useMutation({
    mutationFn: (data) => testcasesAPI.create(buildTestcasePayload(data)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['testCases'] });
      setTestCaseDialogOpen(false);
      setEditingTestCase(null);
      setSelectedRequirement(null);
      toast.success('Test case created successfully!');
    },
  });

  const updateTestCaseMutation = useMutation({
    mutationFn: ({ id, data }) => testcasesAPI.update(id, buildTestcasePayload(data)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['testCases'] });
      setTestCaseDialogOpen(false);
      setEditingTestCase(null);
      setSelectedRequirement(null);
      toast.success('Test case updated successfully!');
    },
  });

  const handleTestCaseSubmit = (data) => {
    if (selectedRequirement && !editingTestCase) {
      const requirementIds = data.requirement_ids || [];
      if (!requirementIds.includes(selectedRequirement.id)) {
        requirementIds.push(selectedRequirement.id);
      }
      data = { ...data, requirement_ids: requirementIds };
      
      if (selectedRequirement.release_id) {
        const releaseIds = data.release_ids || [];
        if (!releaseIds.includes(selectedRequirement.release_id)) {
          releaseIds.unshift(selectedRequirement.release_id);
        }
        data = { ...data, release_ids: releaseIds };
      }
    }

    if (editingTestCase) {
      updateTestCaseMutation.mutate({ id: editingTestCase.id, data });
    } else {
      createTestCaseMutation.mutate(data);
    }
  };

  const handleCreateTestCase = (requirement) => {
    setSelectedRequirement(requirement);
    setEditingTestCase(null);
    setTestCaseDialogOpen(true);
  };

  const handleEditTestCase = (testCase) => {
    setEditingTestCase(testCase);
    setSelectedRequirement(null);
    setTestCaseDialogOpen(true);
  };

  const filteredRequirements = selectedReleases.length === 0
    ? requirements
    : requirements.filter(r => selectedReleases.includes(r.release_id));

  const releaseRequirementIds = filteredRequirements.map(r => r.id);

  const filteredTestCases = selectedReleases.length === 0
    ? normalizedTestCases
    : normalizedTestCases.filter(tc =>
        (tc.release_ids && tc.release_ids.some(rid => selectedReleases.includes(rid))) ||
        (tc.requirement_ids && tc.requirement_ids.some(rid => releaseRequirementIds.includes(rid)))
      );

  const releaseTestCaseIds = filteredTestCases.map(tc => tc.id);

  const filteredAutomations = selectedReleases.length === 0
    ? automations
    : automations.filter(a =>
        selectedReleases.includes(a.release_id) ||
        releaseTestCaseIds.includes(a.test_case_id)
      );
  
  const filteredExecutions = selectedReleases.length === 0
    ? executions
    : executions.filter(exec =>
        selectedReleases.includes(exec.release_id) ||
        releaseTestCaseIds.includes(exec.test_case_id)
      );

  // Get last execution status for a test case (manual or automated)
  const getTestCaseExecutionStatus = (testCaseId) => {
    // Get manual executions
    const manualExecs = filteredExecutions.filter(e => e.test_case_id === testCaseId);
    // Get automated executions
    const autoExecs = filteredAutomations.filter(a => a.test_case_id === testCaseId && a.last_run_result);

    let lastExecution = null;

    // Find most recent manual execution
    if (manualExecs.length > 0) {
      const mostRecentManual = manualExecs.reduce((latest, current) => {
        return new Date(current.execution_date) > new Date(latest.execution_date) ? current : latest;
      });
      lastExecution = {
        result: mostRecentManual.result,
        date: new Date(mostRecentManual.execution_date),
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

      const autoDate = new Date(mostRecentAuto.last_run_date);
      
      // Compare with manual if it exists
      if (!lastExecution || autoDate > lastExecution.date) {
        lastExecution = {
          result: mostRecentAuto.last_run_result,
          date: autoDate,
          type: 'automated'
        };
      }
    }

    return lastExecution;
  };

  const totalRequirementsPages = Math.ceil(filteredRequirements.length / itemsPerPage);
  const totalTestCasesPages = Math.ceil(filteredTestCases.length / itemsPerPage);

  const paginatedRequirements = filteredRequirements.slice(
    (requirementsPage - 1) * itemsPerPage,
    requirementsPage * itemsPerPage
  );

  const paginatedTestCases = filteredTestCases.slice(
    (testCasesPage - 1) * itemsPerPage,
    testCasesPage * itemsPerPage
  );

  useEffect(() => {
    setRequirementsPage(1);
    setTestCasesPage(1);
  }, [selectedReleases]);

  // Calculate historical trend data based on actual executions
  const getTrendData = useMemo(() => {
    if (filteredTestCases.length === 0) {
      return [];
    }

    const today = startOfDay(new Date());
    const daysData = [];

    for (let i = trendDays - 1; i >= 0; i--) {
      const date = subDays(today, i);
      daysData.push({
        date: format(date, 'MMM dd'),
        fullDate: date,
        passed: 0,
        failed: 0,
        blocked: 0,
        notExecuted: 0,
      });
    }

    // For each day, calculate the status of each test case as of that day
    daysData.forEach((dayData) => {
      const dayEnd = new Date(dayData.fullDate);
      dayEnd.setHours(23, 59, 59, 999);

      filteredTestCases.forEach(tc => {
        // Get all executions for this test case up to this day
        const manualExecsUpToDay = filteredExecutions
          .filter(e => e.test_case_id === tc.id && new Date(e.execution_date) <= dayEnd);
        
        const autoExecsUpToDay = filteredAutomations
          .filter(a => a.test_case_id === tc.id && a.last_run_result && a.last_run_date && new Date(a.last_run_date) <= dayEnd);

        let lastExecUpToDay = null;

        // Find most recent execution up to this day
        if (manualExecsUpToDay.length > 0) {
          const mostRecentManual = manualExecsUpToDay.reduce((latest, current) => {
            return new Date(current.execution_date) > new Date(latest.execution_date) ? current : latest;
          });
          lastExecUpToDay = {
            result: mostRecentManual.result,
            date: new Date(mostRecentManual.execution_date)
          };
        }

        if (autoExecsUpToDay.length > 0) {
          const mostRecentAuto = autoExecsUpToDay.reduce((latest, current) => {
            if (!latest.last_run_date) return current;
            if (!current.last_run_date) return latest;
            return new Date(current.last_run_date) > new Date(latest.last_run_date) ? current : latest;
          });

          const autoDate = new Date(mostRecentAuto.last_run_date);
          
          if (!lastExecUpToDay || autoDate > lastExecUpToDay.date) {
            lastExecUpToDay = {
              result: mostRecentAuto.last_run_result,
              date: autoDate
            };
          }
        }

        // Count based on last execution status
        if (!lastExecUpToDay) {
          dayData.notExecuted++;
        } else if (lastExecUpToDay.result === 'passed') {
          dayData.passed++;
        } else if (lastExecUpToDay.result === 'failed') {
          dayData.failed++;
        } else if (lastExecUpToDay.result === 'blocked') {
          dayData.blocked++;
        } else {
          dayData.notExecuted++; // skipped counts as not executed
        }
      });
    });

    return daysData;
  }, [selectedReleases, filteredTestCases, filteredExecutions, filteredAutomations, trendDays]);

  // Calculate test execution statistics based on actual executions
  const getExecutionStats = () => {
    let passed = 0;
    let failed = 0;
    let blocked = 0;
    let notExecuted = 0;

    filteredTestCases.forEach(tc => {
      const lastExec = getTestCaseExecutionStatus(tc.id);
      
      if (!lastExec) {
        notExecuted++;
      } else if (lastExec.result === 'passed') {
        passed++;
      } else if (lastExec.result === 'failed') {
        failed++;
      } else if (lastExec.result === 'blocked') {
        blocked++;
      } else {
        notExecuted++; // skipped
      }
    });

    const total = filteredTestCases.length;

    return { passed, failed, blocked, notExecuted, total };
  };

  const getCoverageStats = () => {
    const covered = filteredRequirements.filter(req => 
      testCases.some(tc => tc.requirement_ids && tc.requirement_ids.includes(req.id))
    ).length;
    
    const notCovered = filteredRequirements.length - covered;
    const total = filteredRequirements.length;
    const coveragePercentage = total > 0 ? Math.round((covered / total) * 100) : 0;

    return { covered, notCovered, total, coveragePercentage };
  };

  const getOverallTestCoverage = () => {
    if (filteredRequirements.length === 0) return { percentage: 0, details: {} };

    let requirementsWithTests = 0;
    let requirementsFullyTested = 0; // Changed: now counts only fully passed requirements
    let totalTestCasesLinked = 0;
    let totalTestCasesExecuted = 0;

    filteredRequirements.forEach(req => {
      const reqTestCases = testCases.filter(tc => tc.requirement_ids && tc.requirement_ids.includes(req.id));
      
      if (reqTestCases.length > 0) {
        requirementsWithTests++;
        totalTestCasesLinked += reqTestCases.length;

        // Check execution status for all test cases
        const testCaseStatuses = reqTestCases.map(tc => {
          const lastExec = getTestCaseExecutionStatus(tc.id);
          return {
            executed: lastExec !== null,
            passed: lastExec && lastExec.result === 'passed'
          };
        });

        // Count executed test cases
        const executedCount = testCaseStatuses.filter(status => status.executed).length;
        totalTestCasesExecuted += executedCount;

        // A requirement is "fully tested" ONLY if ALL its test cases are executed AND passed
        const allTestCasesPassed = reqTestCases.length > 0 && testCaseStatuses.every(status => status.passed);
        
        if (allTestCasesPassed) {
          requirementsFullyTested++;
        }
      }
    });

    const percentage = filteredRequirements.length > 0 
      ? Math.round((requirementsFullyTested / filteredRequirements.length) * 100)
      : 0;

    return {
      percentage,
      details: {
        totalRequirements: filteredRequirements.length,
        requirementsWithTests,
        requirementsFullyTested, // Changed: now represents fully passed requirements
        totalTestCasesLinked,
        totalTestCasesExecuted,
      }
    };
  };

  const executionStats = getExecutionStats();
  const coverageStats = getCoverageStats();
  const overallCoverage = getOverallTestCoverage();

  // Calculate pass rate based on last execution status
  const passedTestsCount = filteredTestCases.filter(tc => {
    const lastExec = getTestCaseExecutionStatus(tc.id);
    return lastExec && lastExec.result === 'passed';
  }).length;
  const passRate = filteredTestCases.length > 0 ? Math.round((passedTestsCount / filteredTestCases.length) * 100) : 0;

  const passingAutomations = filteredAutomations.filter(a => a.last_run_result === 'passed').length;
  const autoPassRate = filteredAutomations.length > 0 ? Math.round((passingAutomations / filteredAutomations.length) * 100) : 0;

  const statusColors = {
    draft: 'bg-slate-100 text-slate-700',
    approved: 'bg-green-100 text-green-700',
    in_development: 'bg-blue-100 text-blue-700',
    ready_for_testing: 'bg-purple-100 text-purple-700',
    completed: 'bg-emerald-100 text-emerald-700',
    passed: 'bg-green-100 text-green-700',
    failed: 'bg-red-100 text-red-700',
    blocked: 'bg-orange-100 text-orange-700',
    passing: 'bg-green-100 text-green-700',
    failing: 'bg-red-100 text-red-700',
    ready: 'bg-blue-100 text-blue-700',
    in_progress: 'bg-purple-100 text-purple-700',
    skipped: 'bg-gray-100 text-gray-700',
  };

  const getRequirementTitle = (reqId) => {
    const req = requirements.find(r => r.id === reqId);
    return req ? req.title : null;
  };

  const getTestCaseTitle = (tcId) => {
    const tc = testCases.find(t => t.id === tcId);
    return tc ? tc.title : null;
  };

  const toggleRelease = (releaseId) => {
    setSelectedReleases(prev =>
      prev.includes(releaseId)
        ? prev.filter(id => id !== releaseId)
        : [...prev, releaseId]
    );
  };

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const total = payload.reduce((sum, entry) => sum + entry.value, 0);
      return (
        <div className="bg-white p-3 border border-slate-200 rounded-lg shadow-lg">
          <p className="font-semibold text-slate-900 mb-2">{payload[0].payload.date}</p>
          <div className="space-y-1">
            <p className="text-sm flex items-center gap-2">
              <span className="w-3 h-3 bg-green-500 rounded"></span>
              <span className="text-slate-700">Passed: {payload[0].value}</span>
            </p>
            <p className="text-sm flex items-center gap-2">
              <span className="w-3 h-3 bg-red-500 rounded"></span>
              <span className="text-slate-700">Failed: {payload[1].value}</span>
            </p>
            <p className="text-sm flex items-center gap-2">
              <span className="w-3 h-3 bg-orange-500 rounded"></span>
              <span className="text-slate-700">Blocked: {payload[2].value}</span>
            </p>
            <p className="text-sm flex items-center gap-2">
              <span className="w-3 h-3 bg-slate-300 rounded"></span>
              <span className="text-slate-700">Not Executed: {payload[3].value}</span>
            </p>
            <p className="text-sm font-semibold text-slate-900 mt-2 pt-2 border-t">
              Total: {total}
            </p>
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="p-6 lg:p-8 space-y-8">
      <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 mb-2">Test Plan</h1>
          <p className="text-slate-600">Overview of your test management system</p>
        </div>
        <div className="flex gap-3 flex-wrap">
          <Link to={createPageUrl("Requirements")}>
            <Button variant="outline" className="gap-2">
              <Plus className="w-4 h-4" />
              New Requirement
            </Button>
          </Link>
          <Button 
            onClick={() => {
              setSelectedRequirement(null);
              setEditingTestCase(null);
              setTestCaseDialogOpen(true);
            }}
            className="bg-blue-600 hover:bg-blue-700 gap-2"
          >
            <Plus className="w-4 h-4" />
            New Test Case
          </Button>
        </div>
      </div>

      <Card className="border-none shadow-md bg-gradient-to-r from-blue-50 to-purple-50">
        <CardContent className="p-6">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <Filter className="w-5 h-5 text-slate-700" />
              <span className="font-medium text-slate-900">Filter by Release:</span>
            </div>
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="outline" className="bg-white gap-2">
                  <Package className="w-4 h-4" />
                  {selectedReleases.length === 0 ? 'All Releases' : `${selectedReleases.length} Selected`}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-80 p-4">
                <div className="space-y-2">
                  <p className="text-sm font-semibold text-slate-700 mb-3">Select Releases</p>
                  {releases.map((rel) => (
                    <div key={rel.id} className="flex items-center space-x-2">
                      <Checkbox
                        id={`release-${rel.id}`}
                        checked={selectedReleases.includes(rel.id)}
                        onCheckedChange={() => toggleRelease(rel.id)}
                      />
                      <label
                        htmlFor={`release-${rel.id}`}
                        className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
                      >
                        {rel.name} {rel.version && `(v${rel.version})`}
                      </label>
                    </div>
                  ))}
                </div>
              </PopoverContent>
            </Popover>
            {selectedReleases.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelectedReleases([])}
                className="gap-2"
              >
                <X className="w-4 h-4" />
                Clear Filter
              </Button>
            )}
          </div>
          {selectedReleases.length > 0 && (
            <div className="mt-4 pt-4 border-t border-slate-200">
              <div className="flex flex-wrap gap-2">
                {selectedReleases.map(releaseId => {
                  const release = releases.find(r => r.id === releaseId);
                  return release ? (
                    <Badge key={releaseId} variant="outline" className="gap-2">
                      <Package className="w-3 h-3" />
                      {release.name} {release.version && `(v${release.version})`}
                    </Badge>
                  ) : null;
                })}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatsCard
          title="Requirements"
          value={filteredRequirements.length}
          icon={FileText}
          trend={selectedReleases.length > 0 ? "In selected releases" : "+12% this week"}
          trendDirection="up"
          bgColor="bg-blue-500"
          iconColor="text-blue-600"
        />
        <StatsCard
          title="Test Cases"
          value={filteredTestCases.length}
          icon={ClipboardCheck}
          trend={`${passRate}% passed`}
          trendDirection="up"
          bgColor="bg-purple-500"
          iconColor="text-purple-600"
        />
        <StatsCard
          title="Automations"
          value={filteredAutomations.length}
          icon={Bot}
          trend={`${autoPassRate}% passing`}
          trendDirection="up"
          bgColor="bg-green-500"
          iconColor="text-green-600"
        />
        <StatsCard
          title="Overall Test Coverage"
          value={`${overallCoverage.percentage}%`}
          icon={Target}
          trend={`${overallCoverage.details.requirementsFullyTested}/${overallCoverage.details.totalRequirements} requirements fully tested`}
          trendDirection="up"
          bgColor="bg-amber-500"
          iconColor="text-amber-600"
        />
      </div>

      <Card className="border-none shadow-md bg-gradient-to-br from-amber-50 to-orange-50">
        <CardHeader className="border-b border-amber-100">
          <CardTitle className="text-lg font-semibold flex items-center gap-2">
            <Target className="w-5 h-5 text-amber-600" />
            Test Coverage Breakdown
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          <div className="grid md:grid-cols-3 gap-6">
            <div className="text-center">
              <p className="text-sm text-slate-600 mb-2">Requirements with Test Cases</p>
              <p className="text-3xl font-bold text-slate-900 mb-1">
                {overallCoverage.details.requirementsWithTests}/{overallCoverage.details.totalRequirements}
              </p>
              <p className="text-xs text-slate-500">
                {overallCoverage.details.totalRequirements > 0 
                  ? Math.round((overallCoverage.details.requirementsWithTests / overallCoverage.details.totalRequirements) * 100)
                  : 0}% covered
              </p>
            </div>
            <div className="text-center">
              <p className="text-sm text-slate-600 mb-2">Test Cases Executed</p>
              <p className="text-3xl font-bold text-slate-900 mb-1">
                {overallCoverage.details.totalTestCasesExecuted}/{overallCoverage.details.totalTestCasesLinked}
              </p>
              <p className="text-xs text-slate-500">
                {overallCoverage.details.totalTestCasesLinked > 0
                  ? Math.round((overallCoverage.details.totalTestCasesExecuted / overallCoverage.details.totalTestCasesLinked) * 100)
                  : 0}% executed
              </p>
            </div>
            <div className="text-center">
              <p className="text-sm text-slate-600 mb-2">Requirements Fully Tested</p>
              <p className="text-3xl font-bold text-amber-600 mb-1">
                {overallCoverage.details.requirementsFullyTested}/{overallCoverage.details.totalRequirements}
              </p>
              <p className="text-xs text-slate-500">
                All test cases passed: {overallCoverage.percentage}%
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="border-none shadow-md">
        <CardHeader className="border-b border-slate-100">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <CardTitle className="text-lg font-semibold flex items-center gap-2">
              <Bot className="w-5 h-5 text-purple-600" />
              Test Execution Status
              <Badge variant="outline" className="ml-2">{executionStats.total} total</Badge>
            </CardTitle>
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-slate-600" />
              <select
                value={trendDays}
                onChange={(e) => setTrendDays(Number(e.target.value))}
                className="text-sm border border-slate-200 rounded-md px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value={7}>Last 7 days</option>
                <option value={14}>Last 14 days</option>
                <option value={30}>Last 30 days</option>
              </select>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-6">
          <div className="space-y-6">
            <div>
              <p className="text-sm font-medium text-slate-700 mb-3">Current Status</p>
              <div className="w-full h-12 flex rounded-lg overflow-hidden">
                {executionStats.passed > 0 && (
                  <div 
                    className="bg-green-500 flex items-center justify-center text-white text-sm font-semibold"
                    style={{ width: `${(executionStats.passed / executionStats.total) * 100}%` }}
                  >
                    {executionStats.passed}
                  </div>
                )}
                {executionStats.failed > 0 && (
                  <div 
                    className="bg-red-500 flex items-center justify-center text-white text-sm font-semibold"
                    style={{ width: `${(executionStats.failed / executionStats.total) * 100}%` }}
                  >
                    {executionStats.failed}
                  </div>
                )}
                {executionStats.blocked > 0 && (
                  <div 
                    className="bg-orange-500 flex items-center justify-center text-white text-sm font-semibold"
                    style={{ width: `${(executionStats.blocked / executionStats.total) * 100}%` }}
                  >
                    {executionStats.blocked}
                  </div>
                )}
                {executionStats.notExecuted > 0 && (
                  <div 
                    className="bg-slate-300 flex items-center justify-center text-slate-700 text-sm font-semibold"
                    style={{ width: `${(executionStats.notExecuted / executionStats.total) * 100}%` }}
                  >
                    {executionStats.notExecuted}
                  </div>
                )}
              </div>
            </div>

            {getTrendData.length > 0 && (
              <div>
                <p className="text-sm font-medium text-slate-700 mb-3">Execution Trend</p>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={getTrendData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis 
                      dataKey="date" 
                      tick={{ fill: '#64748b', fontSize: 12 }}
                      tickLine={{ stroke: '#e2e8f0' }}
                    />
                    <YAxis 
                      tick={{ fill: '#64748b', fontSize: 12 }}
                      tickLine={{ stroke: '#e2e8f0' }}
                    />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="passed" stackId="a" fill="#22c55e" name="Passed" radius={[0, 0, 0, 0]} />
                    <Bar dataKey="failed" stackId="a" fill="#ef4444" name="Failed" radius={[0, 0, 0, 0]} />
                    <Bar dataKey="blocked" stackId="a" fill="#f97316" name="Blocked" radius={[0, 0, 0, 0]} />
                    <Bar dataKey="notExecuted" stackId="a" fill="#cbd5e1" name="Not Executed" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            <div className="flex flex-wrap gap-4 justify-center pt-2 border-t border-slate-100">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-green-500 rounded"></div>
                <span className="text-sm text-slate-700">Passed ({executionStats.passed})</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-red-500 rounded"></div>
                <span className="text-sm text-slate-700">Failed ({executionStats.failed})</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-orange-500 rounded"></div>
                <span className="text-sm text-slate-700">Blocked ({executionStats.blocked})</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-slate-300 rounded"></div>
                <span className="text-sm text-slate-700">Not Executed ({executionStats.notExecuted})</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="border-none shadow-md">
        <CardHeader className="border-b border-slate-100">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <CardTitle className="text-lg font-semibold flex items-center gap-2">
              <Layers className="w-5 h-5 text-blue-600" />
              Test Cases by Requirement
            </CardTitle>
            <Tabs value={viewMode} onValueChange={setViewMode}>
              <TabsList className="bg-slate-100">
                <TabsTrigger value="list">List View</TabsTrigger>
                <TabsTrigger value="grouped">Grouped View</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
        </CardHeader>
        <CardContent className="p-6">
          {viewMode === "grouped" ? (
            <TestCasesByRequirement
              requirements={filteredRequirements}
              testCases={filteredTestCases}
              automations={filteredAutomations}
              executions={filteredExecutions}
              onCreateTestCase={handleCreateTestCase}
              onEditTestCase={handleEditTestCase}
            />
          ) : (
            <div className="grid lg:grid-cols-2 gap-6">
              <div className="space-y-3">
                <h3 className="font-semibold text-slate-900 mb-3">Requirements</h3>
                {paginatedRequirements.map((req) => {
                  const reqTestCases = testCases.filter(tc => tc.requirement_ids && tc.requirement_ids.includes(req.id));
                  const isCovered = reqTestCases.length > 0;
                  return (
                    <div key={req.id} className="border border-slate-200 rounded-lg p-3 hover:border-blue-300 transition-all">
                      <Link
                        to={createPageUrl("Requirements")}
                        className="flex items-start justify-between mb-2 group"
                      >
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-slate-900 truncate group-hover:text-blue-600 transition-colors">
                            {req.title}
                          </p>
                          <p className="text-sm text-slate-500 truncate">{req.category}</p>
                        </div>
                        <div className="flex items-center gap-2 ml-2">
                          <Badge className={`${statusColors[req.status] || 'bg-slate-100 text-slate-700'}`}>
                            {(req.status || 'unknown').replace(/_/g, ' ')}
                          </Badge>
                          {isCovered ? (
                            <Badge className="bg-green-100 text-green-700 border-green-200">
                              <CheckCircle2 className="w-3 h-3 mr-1" />
                              Covered
                            </Badge>
                          ) : (
                            <Badge className="bg-orange-100 text-orange-700 border-orange-200">
                              <AlertCircle className="w-3 h-3 mr-1" />
                              Not Covered
                            </Badge>
                          )}
                        </div>
                      </Link>
                      {reqTestCases.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-slate-100">
                          <p className="text-xs text-slate-500 mb-1">Linked Test Cases ({reqTestCases.length}):</p>
                          <div className="flex flex-wrap gap-1">
                            {reqTestCases.slice(0, 3).map(tc => (
                              <Badge key={tc.id} variant="outline" className="text-xs">
                                {tc.title.length > 20 ? tc.title.substring(0, 20) + '...' : tc.title}
                              </Badge>
                            ))}
                            {reqTestCases.length > 3 && (
                              <Badge variant="outline" className="text-xs">+{reqTestCases.length - 3} more</Badge>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
                {filteredRequirements.length === 0 && (
                  <div className="col-span-full text-center py-8 text-slate-500">
                    <FileText className="w-12 h-12 mx-auto mb-3 opacity-30" />
                    <p>No requirements{selectedReleases.length > 0 ? " in selected releases" : ""}</p>
                  </div>
                )}
                {totalRequirementsPages > 1 && (
                  <div className="flex items-center justify-between mt-4 pt-4 border-t border-slate-100">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setRequirementsPage(prev => Math.max(1, prev - 1))}
                      disabled={requirementsPage === 1}
                    >
                      <ChevronLeft className="w-4 h-4 mr-1" />
                      Previous
                    </Button>
                    <span className="text-sm text-slate-600">
                      Page {requirementsPage} of {totalRequirementsPages}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setRequirementsPage(prev => Math.min(totalRequirementsPages, prev + 1))}
                      disabled={requirementsPage === totalRequirementsPages}
                    >
                      Next
                      <ChevronRight className="w-4 h-4 ml-1" />
                    </Button>
                  </div>
                )}
              </div>

              <div className="space-y-3">
                <h3 className="font-semibold text-slate-900 mb-3">Test Cases</h3>
                {paginatedTestCases.map((test) => {
                  const linkedAutomations = automations.filter(a => a.test_case_id === test.id);
                  const lastExec = getTestCaseExecutionStatus(test.id);
                  const displayStatus = lastExec ? lastExec.result : 'draft'; // Default to 'draft' if no execution

                  return (
                    <div key={test.id} className="border border-slate-200 rounded-lg p-3 hover:border-purple-300 transition-all">
                      <Link
                        to={createPageUrl("TestCases")}
                        className="flex items-start justify-between mb-2 group"
                      >
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-slate-900 truncate group-hover:text-purple-600 transition-colors">
                            {test.title}
                          </p>
                          <div className="flex items-center gap-2 text-sm text-slate-500 mt-1">
                            <span>{test.test_type}</span>
                            {test.requirement_ids && test.requirement_ids.length > 0 && (
                              <>
                                <span>•</span>
                                <span className="truncate text-blue-600">
                                  {test.requirement_ids.length} requirement{test.requirement_ids.length > 1 ? 's' : ''}
                                </span>
                              </>
                            )}
                          </div>
                        </div>
                        <Badge className={`ml-2 ${statusColors[displayStatus]}`}>
                          {displayStatus === 'passed' && <CheckCircle2 className="w-3 h-3 mr-1" />}
                          {displayStatus === 'failed' && <XCircle className="w-3 h-3 mr-1" />}
                          {displayStatus === 'blocked' && <AlertCircle className="w-3 h-3 mr-1" />}
                          {displayStatus}
                        </Badge>
                      </Link>
                      {linkedAutomations.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-slate-100">
                          <p className="text-xs text-slate-500 mb-1">Linked Automations ({linkedAutomations.length}):</p>
                          <div className="flex flex-wrap gap-1">
                            {linkedAutomations.slice(0, 2).map(auto => (
                              <Badge key={auto.id} variant="outline" className="text-xs gap-1">
                                <Bot className="w-3 h-3" />
                                {auto.framework}
                              </Badge>
                            ))}
                            {linkedAutomations.length > 2 && (
                              <Badge variant="outline" className="text-xs">+{linkedAutomations.length - 2} more</Badge>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
                {filteredTestCases.length === 0 && (
                  <div className="col-span-full text-center py-8 text-slate-500">
                    <ClipboardCheck className="w-12 h-12 mx-auto mb-3 opacity-30" />
                    <p>No test cases{selectedReleases.length > 0 ? " in selected releases" : ""}</p>
                  </div>
                )}
                {totalTestCasesPages > 1 && (
                  <div className="flex items-center justify-between mt-4 pt-4 border-t border-slate-100">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setTestCasesPage(prev => Math.max(1, prev - 1))}
                      disabled={testCasesPage === 1}
                    >
                      <ChevronLeft className="w-4 h-4 mr-1" />
                      Previous
                    </Button>
                    <span className="text-sm text-slate-600">
                      Page {testCasesPage} of {totalTestCasesPages}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setTestCasesPage(prev => Math.min(totalTestCasesPages, prev + 1))}
                      disabled={testCasesPage === totalTestCasesPages}
                    >
                      Next
                      <ChevronRight className="w-4 h-4 ml-1" />
                    </Button>
                  </div>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="border-none shadow-md">
        <CardHeader className="border-b border-slate-100">
          <Link to={createPageUrl("Automations")}>
            <CardTitle className="text-lg font-semibold flex items-center gap-2 hover:text-green-600 transition-colors cursor-pointer">
              <Bot className="w-5 h-5 text-green-600" />
              Test Automations
              <Badge variant="outline" className="ml-auto">{filteredAutomations.length}</Badge>
            </CardTitle>
          </Link>
        </CardHeader>
        <CardContent className="p-6">
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredAutomations.slice(0, 6).map((auto) => (
              <Link
                key={auto.id}
                to={createPageUrl("Automations")}
                className="p-4 rounded-lg border border-slate-200 hover:border-green-300 hover:shadow-md transition-all group"
              >
                <div className="flex items-start justify-between mb-2">
                  <Bot className="w-5 h-5 text-green-600" />
                  {auto.last_run_result && (
                    <Badge className={`${statusColors[auto.last_run_result]}`}>
                      {auto.last_run_result}
                    </Badge>
                  )}
                </div>
                <p className="font-medium text-slate-900 mb-1 group-hover:text-green-600 transition-colors line-clamp-1">
                  {auto.title}
                </p>
                <p className="text-sm text-slate-500 mb-2">{auto.framework}</p>
                {auto.test_case_id && getTestCaseTitle(auto.test_case_id) && (
                  <div className="mt-2 pt-2 border-t border-slate-100">
                    <p className="text-xs text-slate-500 truncate">
                      📋 {getTestCaseTitle(auto.test_case_id)}
                    </p>
                  </div>
                )}
              </Link>
            ))}
            {filteredAutomations.length === 0 && (
              <div className="col-span-full text-center py-8 text-slate-500">
                <Bot className="w-12 h-12 mx-auto mb-3 opacity-30" />
                <p>No automations{selectedReleases.length > 0 ? " in selected releases" : ""}</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <TestCaseDialog
        open={testCaseDialogOpen}
        onOpenChange={setTestCaseDialogOpen}
        testCase={editingTestCase}
        requirements={requirements}
        onSubmit={handleTestCaseSubmit}
        isLoading={createTestCaseMutation.isPending || updateTestCaseMutation.isPending}
      />
    </div>
  );
}
