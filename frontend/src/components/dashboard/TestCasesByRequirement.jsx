import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronRight, Plus, CheckCircle2, XCircle, AlertCircle, User, Bot, Hash } from "lucide-react";
import { cn } from "@/lib/utils";

export default function TestCasesByRequirement({ 
  requirements, 
  testCases, 
  automations,
  executions,
  onCreateTestCase,
  onEditTestCase
}) {
  const [expandedRequirements, setExpandedRequirements] = useState(new Set());

  const toggleRequirement = (reqId) => {
    const newExpanded = new Set(expandedRequirements);
    if (newExpanded.has(reqId)) {
      newExpanded.delete(reqId);
    } else {
      newExpanded.add(reqId);
    }
    setExpandedRequirements(newExpanded);
  };

  const getTestCasesForRequirement = (reqId) => {
    return testCases.filter(tc => tc.requirement_ids && tc.requirement_ids.includes(reqId));
  };

  const getExecutionStatus = (testCaseId) => {
    const manualExecs = executions.filter(exec => exec.test_case_id === testCaseId);
    if (manualExecs.length > 0) {
      const latest = manualExecs.reduce((latest, current) => {
        return new Date(current.execution_date) > new Date(latest.execution_date) ? current : latest;
      });
      return { status: latest.result, type: 'manual', date: latest.execution_date };
    }

    const linkedAutos = automations.filter(auto => auto.test_case_id === testCaseId && auto.last_run_result);
    if (linkedAutos.length > 0) {
      const latest = linkedAutos.reduce((latest, current) => {
        if (!latest.last_run_date) return current;
        if (!current.last_run_date) return latest;
        return new Date(current.last_run_date) > new Date(latest.last_run_date) ? current : latest;
      });
      return { status: latest.last_run_result, type: 'automated', date: latest.last_run_date };
    }

    return { status: 'not_executed', type: null, date: null };
  };

  const getRequirementCoverage = (reqId) => {
    const reqTestCases = getTestCasesForRequirement(reqId);
    if (reqTestCases.length === 0) return { coverage: 0, executed: 0, total: 0 };

    const executed = reqTestCases.filter(tc => {
      const execStatus = getExecutionStatus(tc.id);
      return execStatus.status !== 'not_executed';
    }).length;

    const coverage = Math.round((executed / reqTestCases.length) * 100);
    return { coverage, executed, total: reqTestCases.length };
  };

  const statusColors = {
    passed: 'bg-green-100 text-green-700 border-green-200',
    failed: 'bg-red-100 text-red-700 border-red-200',
    blocked: 'bg-orange-100 text-orange-700 border-orange-200',
    skipped: 'bg-slate-100 text-slate-700 border-slate-200',
    not_executed: 'bg-slate-100 text-slate-500 border-slate-200',
  };

  const priorityColors = {
    critical: 'bg-red-100 text-red-700 border-red-200',
    high: 'bg-orange-100 text-orange-700 border-orange-200',
    medium: 'bg-yellow-100 text-yellow-700 border-yellow-200',
    low: 'bg-blue-100 text-blue-700 border-blue-200',
  };

  return (
    <div className="space-y-3">
      {requirements.map((req) => {
        const reqTestCases = getTestCasesForRequirement(req.id);
        const isExpanded = expandedRequirements.has(req.id);
        const coverage = getRequirementCoverage(req.id);
        const hasCoverage = reqTestCases.length > 0;

        return (
          <Card key={req.id} className="border border-slate-200">
            <CardHeader 
              className="p-4 cursor-pointer hover:bg-slate-50 transition-colors"
              onClick={() => toggleRequirement(req.id)}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3 flex-1 min-w-0">
                  <button className="mt-1">
                    {isExpanded ? (
                      <ChevronDown className="w-5 h-5 text-slate-600" />
                    ) : (
                      <ChevronRight className="w-5 h-5 text-slate-600" />
                    )}
                  </button>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h4 className="font-semibold text-slate-900 truncate">{req.title}</h4>
                      <Badge variant="outline" className="gap-1 text-xs text-slate-500 border-slate-300">
                        <Hash className="w-3 h-3" />
                        {req.id.substring(0, 8)}
                      </Badge>
                    </div>
                    <div className="flex flex-wrap gap-2 items-center">
                      <Badge variant="outline" className={`text-xs ${priorityColors[req.priority]}`}>
                        {req.priority}
                      </Badge>
                      <Badge variant="outline" className="text-xs text-slate-600">
                        {req.category}
                      </Badge>
                      <span className="text-xs text-slate-500">
                        {reqTestCases.length} test case{reqTestCases.length !== 1 ? 's' : ''}
                      </span>
                      {hasCoverage && (
                        <>
                          <span className="text-xs text-slate-400">•</span>
                          <span className={cn(
                            "text-xs font-medium",
                            coverage.coverage >= 80 ? "text-green-600" : 
                            coverage.coverage >= 50 ? "text-yellow-600" : "text-red-600"
                          )}>
                            {coverage.coverage}% executed
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  className="gap-1 shrink-0"
                  onClick={(e) => {
                    e.stopPropagation();
                    onCreateTestCase(req);
                  }}
                >
                  <Plus className="w-3 h-3" />
                  Add Test
                </Button>
              </div>
            </CardHeader>

            {isExpanded && (
              <CardContent className="p-4 pt-0 border-t border-slate-100">
                {reqTestCases.length === 0 ? (
                  <div className="text-center py-6 text-slate-500">
                    <p className="text-sm mb-2">No test cases linked to this requirement</p>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => onCreateTestCase(req)}
                    >
                      <Plus className="w-3 h-3 mr-1" />
                      Create Test Case
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {reqTestCases.map((tc) => {
                      const execStatus = getExecutionStatus(tc.id);
                      const linkedAutos = automations.filter(auto => auto.test_case_id === tc.id);
                      const hasAutomation = linkedAutos.length > 0;

                      return (
                        <div
                          key={tc.id}
                          className="p-3 rounded-lg border border-slate-200 hover:border-blue-300 hover:shadow-sm transition-all cursor-pointer"
                          onClick={() => onEditTestCase(tc)}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <h5 className="text-sm font-medium text-slate-900 truncate">
                                  {tc.title}
                                </h5>
                                <Badge variant="outline" className="gap-1 text-xs text-slate-500 border-slate-300">
                                  <Hash className="w-2.5 h-2.5" />
                                  {tc.id.substring(0, 6)}
                                </Badge>
                              </div>
                              <div className="flex flex-wrap gap-2 items-center">
                                <Badge variant="outline" className="text-xs">
                                  {tc.test_type}
                                </Badge>
                                {tc.steps && tc.steps.length > 0 && (
                                  <span className="text-xs text-slate-500">
                                    {tc.steps.length} steps
                                  </span>
                                )}
                                {hasAutomation ? (
                                  <div className="flex items-center gap-1">
                                    <Bot className="w-3 h-3 text-purple-600" />
                                    <span className="text-xs text-purple-600">Automated</span>
                                  </div>
                                ) : (
                                  <div className="flex items-center gap-1">
                                    <User className="w-3 h-3 text-blue-600" />
                                    <span className="text-xs text-blue-600">Manual</span>
                                  </div>
                                )}
                              </div>
                            </div>
                            <div className="shrink-0">
                              <Badge className={`border text-xs ${statusColors[execStatus.status]}`}>
                                {execStatus.status === 'passed' && <CheckCircle2 className="w-3 h-3 mr-1" />}
                                {execStatus.status === 'failed' && <XCircle className="w-3 h-3 mr-1" />}
                                {execStatus.status === 'blocked' && <AlertCircle className="w-3 h-3 mr-1" />}
                                {execStatus.status === 'not_executed' ? 'Not Executed' : execStatus.status}
                              </Badge>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            )}
          </Card>
        );
      })}

      {requirements.length === 0 && (
        <div className="text-center py-12 text-slate-500">
          <p>No requirements found</p>
        </div>
      )}
    </div>
  );
}