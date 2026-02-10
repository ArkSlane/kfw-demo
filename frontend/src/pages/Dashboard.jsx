
import React, { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import { createPageUrl } from "@/utils";
import { FileText, ClipboardCheck, Bot, Plus, TrendingUp, CheckCircle2, AlertCircle, Package, Filter, X, ChevronLeft, ChevronRight, XCircle, Clock, Target } from "lucide-react";
import StatsCard from "../components/dashboard/StatsCard";
import { Badge } from "@/components/ui/badge";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Checkbox } from "@/components/ui/checkbox";


export default function Dashboard() {
  const [selectedReleases, setSelectedReleases] = useState([]);
  const [requirementsPage, setRequirementsPage] = useState(1);
  const [testCasesPage, setTestCasesPage] = useState(1);
  const itemsPerPage = 5;

  const { data: releases } = useQuery({
    queryKey: ['releases'],
    queryFn: async () => [],
    initialData: [],
    enabled: false,
  });

  const { data: requirements, isLoading: loadingReqs } = useQuery({
    queryKey: ['requirements'],
    queryFn: async () => [],
    initialData: [],
    enabled: false,
  });

  const { data: testCases, isLoading: loadingTests } = useQuery({
    queryKey: ['testCases'],
    queryFn: async () => [],
    initialData: [],
    enabled: false,
  });

  const { data: automations, isLoading: loadingAutos } = useQuery({
    queryKey: ['automations'],
    queryFn: async () => [],
    initialData: [],
    enabled: false,
  });

  // Filter data by multiple releases with hierarchical relationships
  const filteredRequirements = selectedReleases.length === 0
    ? requirements
    : requirements.filter(r => selectedReleases.includes(r.release_id));

  // Get requirement IDs for selected releases
  const releaseRequirementIds = filteredRequirements.map(r => r.id);

  // Filter test cases: either linked to selected releases OR linked to a requirement in these releases
  const filteredTestCases = selectedReleases.length === 0
    ? testCases
    : testCases.filter(tc =>
        (tc.release_ids && tc.release_ids.some(rid => selectedReleases.includes(rid))) ||
        (tc.requirement_ids && tc.requirement_ids.some(rid => releaseRequirementIds.includes(rid)))
      );

  // Get test case IDs for selected releases
  const releaseTestCaseIds = filteredTestCases.map(tc => tc.id);

  // Filter automations: linked to selected releases OR linked to a test case in these releases
  const filteredAutomations = selectedReleases.length === 0
    ? automations
    : automations.filter(a =>
        selectedReleases.includes(a.release_id) ||
        releaseTestCaseIds.includes(a.test_case_id)
      );

  // Pagination logic
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

  // Reset pagination when filter changes
  useEffect(() => {
    setRequirementsPage(1);
    setTestCasesPage(1);
  }, [selectedReleases]);

  // Calculate test execution statistics based on automation results
  const getExecutionStats = () => {
    // Get unique test cases that have automations with results
    const testCasesWithAutomations = filteredTestCases.filter(tc => 
      filteredAutomations.some(auto => auto.test_case_id === tc.id && auto.last_run_result)
    );

    let passed = 0;
    let failed = 0;
    let skipped = 0;

    testCasesWithAutomations.forEach(tc => {
      // Get all automations for this test case
      const tcAutomations = filteredAutomations.filter(auto => auto.test_case_id === tc.id && auto.last_run_result);
      
      // Get the most recent automation result
      if (tcAutomations.length > 0) {
        // Sort by last_run_date to get most recent
        const mostRecentAuto = tcAutomations.reduce((latest, current) => {
          if (!latest.last_run_date) return current;
          if (!current.last_run_date) return latest;
          return new Date(current.last_run_date) > new Date(latest.last_run_date) ? current : latest;
        });

        if (mostRecentAuto.last_run_result === 'passed') passed++;
        else if (mostRecentAuto.last_run_result === 'failed') failed++;
        else if (mostRecentAuto.last_run_result === 'skipped') skipped++;
      }
    });

    const notExecuted = filteredTestCases.length - testCasesWithAutomations.length;
    const total = filteredTestCases.length;
    const executionRate = total > 0 ? Math.round(((passed + failed + skipped) / total) * 100) : 0;

    return { passed, failed, skipped, notExecuted, total, executionRate };
  };

  // Calculate requirements coverage
  const getCoverageStats = () => {
    const covered = filteredRequirements.filter(req => 
      testCases.some(tc => tc.requirement_ids && tc.requirement_ids.includes(req.id))
    ).length;
    
    const notCovered = filteredRequirements.length - covered;
    const total = filteredRequirements.length;
    const coveragePercentage = total > 0 ? Math.round((covered / total) * 100) : 0;

    return { covered, notCovered, total, coveragePercentage };
  };

  const executionStats = getExecutionStats();
  const coverageStats = getCoverageStats();

  const passedTests = filteredTestCases.filter(tc => tc.status === 'passed').length;
  const passRate = filteredTestCases.length > 0 ? Math.round((passedTests / filteredTestCases.length) * 100) : 0;

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

  return (
    <div className="p-6 lg:p-8 space-y-8">
      <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 mb-2">Dashboard</h1>
          <p className="text-slate-600">Overview of your test management system</p>
        </div>
        <div className="flex gap-3 flex-wrap">
          <Link to={createPageUrl("Requirements")}>
            <Button variant="outline" className="gap-2">
              <Plus className="w-4 h-4" />
              New Requirement
            </Button>
          </Link>
          <Link to={createPageUrl("TestCases")}>
            <Button className="bg-blue-600 hover:bg-blue-700 gap-2">
              <Plus className="w-4 h-4" />
              New Test Case
            </Button>
          </Link>
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
          title="Requirement Coverage"
          value={`${coverageStats.coveragePercentage}%`}
          icon={Target}
          trend={`${coverageStats.covered}/${coverageStats.total} covered`}
          trendDirection="up"
          bgColor="bg-amber-500"
          iconColor="text-amber-600"
        />
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <Card className="border-none shadow-md">
          <CardHeader className="border-b border-slate-100">
            <CardTitle className="text-lg font-semibold flex items-center gap-2">
              <Bot className="w-5 h-5 text-purple-600" />
              Test Execution Status
              <Badge variant="outline" className="ml-auto">{executionStats.total} total</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-6">
            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 rounded-lg bg-green-50 border border-green-200">
                <div className="flex items-center gap-3">
                  <CheckCircle2 className="w-8 h-8 text-green-600" />
                  <div>
                    <p className="font-semibold text-slate-900">Passed</p>
                    <p className="text-sm text-slate-600">Successfully executed</p>
                  </div>
                </div>
                <span className="text-2xl font-bold text-green-600">{executionStats.passed}</span>
              </div>

              <div className="flex items-center justify-between p-4 rounded-lg bg-red-50 border border-red-200">
                <div className="flex items-center gap-3">
                  <XCircle className="w-8 h-8 text-red-600" />
                  <div>
                    <p className="font-semibold text-slate-900">Failed</p>
                    <p className="text-sm text-slate-600">Execution failed</p>
                  </div>
                </div>
                <span className="text-2xl font-bold text-red-600">{executionStats.failed}</span>
              </div>

              <div className="flex items-center justify-between p-4 rounded-lg bg-slate-50 border border-slate-200">
                <div className="flex items-center gap-3">
                  <Clock className="w-8 h-8 text-slate-600" />
                  <div>
                    <p className="font-semibold text-slate-900">Not Executed</p>
                    <p className="text-sm text-slate-600">No automation results</p>
                  </div>
                </div>
                <span className="text-2xl font-bold text-slate-600">{executionStats.notExecuted}</span>
              </div>

              <div className="pt-3 border-t border-slate-200">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-slate-700">Execution Rate</span>
                  <span className="text-sm font-bold text-slate-900">{executionStats.executionRate}%</span>
                </div>
                <div className="w-full bg-slate-200 rounded-full h-3">
                  <div 
                    className="bg-gradient-to-r from-blue-500 to-purple-500 h-3 rounded-full transition-all" 
                    style={{ width: `${executionStats.executionRate}%` }}
                  />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-none shadow-md">
          <CardHeader className="border-b border-slate-100">
            <CardTitle className="text-lg font-semibold flex items-center gap-2">
              <Target className="w-5 h-5 text-amber-600" />
              Requirements Coverage
              <Badge variant="outline" className="ml-auto">{coverageStats.total} total</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-6">
            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 rounded-lg bg-green-50 border border-green-200">
                <div className="flex items-center gap-3">
                  <CheckCircle2 className="w-8 h-8 text-green-600" />
                  <div>
                    <p className="font-semibold text-slate-900">Covered</p>
                    <p className="text-sm text-slate-600">Has test cases</p>
                  </div>
                </div>
                <span className="text-2xl font-bold text-green-600">{coverageStats.covered}</span>
              </div>

              <div className="flex items-center justify-between p-4 rounded-lg bg-orange-50 border border-orange-200">
                <div className="flex items-center gap-3">
                  <AlertCircle className="w-8 h-8 text-orange-600" />
                  <div>
                    <p className="font-semibold text-slate-900">Not Covered</p>
                    <p className="text-sm text-slate-600">No test cases assigned</p>
                  </div>
                </div>
                <span className="text-2xl font-bold text-orange-600">{coverageStats.notCovered}</span>
              </div>

              <div className="pt-3 border-t border-slate-200">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-slate-700">Coverage Rate</span>
                  <span className="text-sm font-bold text-slate-900">{coverageStats.coveragePercentage}%</span>
                </div>
                <div className="w-full bg-slate-200 rounded-full h-3">
                  <div 
                    className={`h-3 rounded-full transition-all ${
                      coverageStats.coveragePercentage >= 80 ? 'bg-green-500' :
                      coverageStats.coveragePercentage >= 50 ? 'bg-amber-500' : 'bg-orange-500'
                    }`}
                    style={{ width: `${coverageStats.coveragePercentage}%` }}
                  />
                </div>
              </div>

              {coverageStats.notCovered > 0 && (
                <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                  <p className="text-sm text-amber-800">
                    ⚠️ {coverageStats.notCovered} requirement{coverageStats.notCovered > 1 ? 's' : ''} need{coverageStats.notCovered === 1 ? 's' : ''} test case coverage
                  </p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <Card className="border-none shadow-md">
          <CardHeader className="border-b border-slate-100">
            <Link to={createPageUrl("Requirements")}>
              <CardTitle className="text-lg font-semibold flex items-center gap-2 hover:text-blue-600 transition-colors cursor-pointer">
                <FileText className="w-5 h-5 text-blue-600" />
                Requirements
                <Badge variant="outline" className="ml-auto">{filteredRequirements.length}</Badge>
              </CardTitle>
            </Link>
          </CardHeader>
          <CardContent className="p-6">
            <div className="space-y-3">
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
                        <Badge className={`${statusColors[req.status]}`}>
                          {req.status.replace(/_/g, ' ')}
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
            </div>

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
          </CardContent>
        </Card>

        <Card className="border-none shadow-md">
          <CardHeader className="border-b border-slate-100">
            <Link to={createPageUrl("TestCases")}>
              <CardTitle className="text-lg font-semibold flex items-center gap-2 hover:text-purple-600 transition-colors cursor-pointer">
                <ClipboardCheck className="w-5 h-5 text-purple-600" />
                Test Cases
                <Badge variant="outline" className="ml-auto">{filteredTestCases.length}</Badge>
              </CardTitle>
            </Link>
          </CardHeader>
          <CardContent className="p-6">
            <div className="space-y-3">
              {paginatedTestCases.map((test) => {
                const linkedAutomations = automations.filter(a => a.test_case_id === test.id);
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
                      <Badge className={`ml-2 ${statusColors[test.status]}`}>
                        {test.status === 'passed' && <CheckCircle2 className="w-3 h-3 mr-1" />}
                        {test.status === 'failed' && <AlertCircle className="w-3 h-3 mr-1" />}
                        {test.status}
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
            </div>

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
          </CardContent>
        </Card>
      </div>

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
    </div>
  );
}
