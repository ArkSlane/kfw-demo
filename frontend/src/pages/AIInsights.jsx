import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Sparkles, TrendingUp, AlertTriangle, Lightbulb, Target, BarChart3, Bot, RefreshCw } from "lucide-react";
import { toast } from "sonner";

export default function AIInsights() {
  const [analyzing, setAnalyzing] = useState(false);
  const [insights, setInsights] = useState(null);

  const { data: testCases } = useQuery({
    queryKey: ['testCases'],
    queryFn: async () => [],
    initialData: [],
    enabled: false,
  });

  const { data: executions } = useQuery({
    queryKey: ['executions'],
    queryFn: async () => [],
    initialData: [],
    enabled: false,
  });

  const { data: automations } = useQuery({
    queryKey: ['automations'],
    queryFn: async () => [],
    initialData: [],
    enabled: false,
  });

  const { data: requirements } = useQuery({
    queryKey: ['requirements'],
    queryFn: async () => [],
    initialData: [],
    enabled: false,
  });

  const analyzeTestResults = async () => {
    setAnalyzing(true);
    try {
      // Prepare data summary for AI analysis
      const failedTests = testCases.filter(tc => tc.status === 'failed');
      const failedExecutions = executions.filter(exec => exec.result === 'failed');
      const failedAutomations = automations.filter(auto => 
        auto.last_run_result === 'failed' || auto.status === 'failing'
      );

      const testCasesWithMultipleFailures = failedExecutions.reduce((acc, exec) => {
        const tcId = exec.test_case_id;
        if (!acc[tcId]) acc[tcId] = [];
        acc[tcId].push(exec);
        return acc;
      }, {});

      const frequentlyFailingTests = Object.entries(testCasesWithMultipleFailures)
        .filter(([_, execs]) => execs.length > 1)
        .map(([tcId, execs]) => {
          const tc = testCases.find(t => t.id === tcId);
          return {
            testCase: tc?.title || 'Unknown',
            failureCount: execs.length,
            defects: execs.map(e => e.defects_found).filter(Boolean)
          };
        });

      const automationStats = {
        total: automations.length,
        passing: automations.filter(a => a.last_run_result === 'passed').length,
        failing: automations.filter(a => a.last_run_result === 'failed').length,
        notRun: automations.filter(a => !a.last_run_result).length,
      };

      const coverageStats = {
        totalRequirements: requirements.length,
        coveredRequirements: requirements.filter(req => 
          testCases.some(tc => tc.requirement_ids && tc.requirement_ids.includes(req.id))
        ).length,
        totalTestCases: testCases.length,
        executedTestCases: testCases.filter(tc => 
          executions.some(exec => exec.test_case_id === tc.id) ||
          automations.some(auto => auto.test_case_id === tc.id && auto.last_run_result)
        ).length,
      };

      const prompt = `You are a QA expert analyzing test execution results. Provide comprehensive insights based on the following data:

**Test Statistics:**
- Total Test Cases: ${testCases.length}
- Failed Test Cases: ${failedTests.length}
- Total Executions: ${executions.length}
- Failed Executions: ${failedExecutions.length}

**Automation Statistics:**
- Total Automations: ${automationStats.total}
- Passing: ${automationStats.passing}
- Failing: ${automationStats.failing}
- Not Run: ${automationStats.notRun}

**Coverage Statistics:**
- Total Requirements: ${coverageStats.totalRequirements}
- Covered Requirements: ${coverageStats.coveredRequirements}
- Coverage Rate: ${Math.round((coverageStats.coveredRequirements / coverageStats.totalRequirements) * 100)}%
- Execution Rate: ${Math.round((coverageStats.executedTestCases / coverageStats.totalTestCases) * 100)}%

**Frequently Failing Tests:**
${frequentlyFailingTests.length > 0 
  ? frequentlyFailingTests.slice(0, 5).map(t => `- "${t.testCase}": ${t.failureCount} failures`).join('\n')
  : 'None identified'}

**Recent Defects:**
${failedExecutions.slice(0, 5).filter(e => e.defects_found).map(e => `- ${e.defects_found}`).join('\n') || 'No defects logged'}

Provide:
1. **Failure Patterns** (2-3 key patterns you identify)
2. **Root Cause Analysis** (potential causes for failures)
3. **Stability Recommendations** (3-4 actionable recommendations to improve test stability)
4. **Coverage Recommendations** (3-4 actionable recommendations to improve coverage)
5. **Priority Actions** (top 3 immediate actions to take)

Be specific, actionable, and insightful.`;

      // AI LLM integration removed - Base44 SDK no longer available
      // TODO: Replace with actual LLM API call when backend is ready
      
      // Mock implementation - replace with actual API call
      const result = {
        failure_patterns: [],
        root_causes: [],
        stability_recommendations: [],
        coverage_recommendations: [],
        priority_actions: []
      };

      setInsights({
        ...result,
        stats: {
          totalTests: testCases.length,
          failedTests: failedTests.length,
          totalExecutions: executions.length,
          failedExecutions: failedExecutions.length,
          automationStats,
          coverageStats,
          frequentlyFailingTests
        },
        timestamp: new Date()
      });

      toast.success('AI analysis feature coming soon!');
    } catch (error) {
      toast.error('Failed to generate AI insights');
      console.error(error);
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="p-6 lg:p-8 space-y-6">
      <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 mb-2 flex items-center gap-3">
            <Sparkles className="w-8 h-8 text-purple-600" />
            AI Test Insights
          </h1>
          <p className="text-slate-600">AI-powered analysis of test execution results and quality metrics</p>
        </div>
        <Button 
          onClick={analyzeTestResults}
          disabled={analyzing}
          className="bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 gap-2"
        >
          {analyzing ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
              Analyzing...
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              Generate AI Insights
            </>
          )}
        </Button>
      </div>

      {!insights && !analyzing && (
        <Card className="border-none shadow-md bg-gradient-to-br from-purple-50 to-blue-50">
          <CardContent className="p-12 text-center">
            <Bot className="w-16 h-16 mx-auto mb-4 text-purple-600" />
            <h3 className="text-xl font-semibold text-slate-900 mb-2">
              Ready to Analyze Your Test Results
            </h3>
            <p className="text-slate-600 mb-6 max-w-2xl mx-auto">
              Click "Generate AI Insights" to get comprehensive analysis of your test execution data, 
              including failure patterns, root cause analysis, and actionable recommendations.
            </p>
            <Button 
              onClick={analyzeTestResults}
              className="bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700"
            >
              <Sparkles className="w-4 h-4 mr-2" />
              Get Started
            </Button>
          </CardContent>
        </Card>
      )}

      {insights && (
        <>
          {/* Stats Overview */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card className="border-none shadow-md">
              <CardContent className="p-4">
                <p className="text-sm text-slate-600 mb-1">Total Tests</p>
                <p className="text-2xl font-bold text-slate-900">{insights.stats.totalTests}</p>
                <p className="text-xs text-slate-500 mt-1">
                  {insights.stats.failedTests} failed
                </p>
              </CardContent>
            </Card>
            <Card className="border-none shadow-md">
              <CardContent className="p-4">
                <p className="text-sm text-slate-600 mb-1">Executions</p>
                <p className="text-2xl font-bold text-slate-900">{insights.stats.totalExecutions}</p>
                <p className="text-xs text-slate-500 mt-1">
                  {insights.stats.failedExecutions} failed
                </p>
              </CardContent>
            </Card>
            <Card className="border-none shadow-md">
              <CardContent className="p-4">
                <p className="text-sm text-slate-600 mb-1">Test Coverage</p>
                <p className="text-2xl font-bold text-slate-900">
                  {Math.round((insights.stats.coverageStats.coveredRequirements / insights.stats.coverageStats.totalRequirements) * 100)}%
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  {insights.stats.coverageStats.coveredRequirements}/{insights.stats.coverageStats.totalRequirements} requirements
                </p>
              </CardContent>
            </Card>
            <Card className="border-none shadow-md">
              <CardContent className="p-4">
                <p className="text-sm text-slate-600 mb-1">Automation Health</p>
                <p className="text-2xl font-bold text-slate-900">
                  {insights.stats.automationStats.total > 0 
                    ? Math.round((insights.stats.automationStats.passing / insights.stats.automationStats.total) * 100)
                    : 0}%
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  {insights.stats.automationStats.passing} passing
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Priority Actions */}
          <Card className="border-none shadow-md bg-gradient-to-br from-red-50 to-orange-50">
            <CardHeader className="border-b border-red-100">
              <CardTitle className="text-lg font-semibold flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-red-600" />
                Priority Actions
              </CardTitle>
            </CardHeader>
            <CardContent className="p-6">
              <div className="space-y-4">
                {insights.priority_actions.map((action, idx) => (
                  <div key={idx} className="flex gap-4 p-4 bg-white rounded-lg border border-red-200">
                    <div className="flex-shrink-0 w-8 h-8 bg-red-600 text-white rounded-full flex items-center justify-center font-bold">
                      {idx + 1}
                    </div>
                    <div className="flex-1">
                      <h4 className="font-semibold text-slate-900 mb-1">{action.action}</h4>
                      <p className="text-sm text-slate-600">{action.reason}</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Failure Patterns */}
          <Card className="border-none shadow-md">
            <CardHeader className="border-b border-slate-100">
              <CardTitle className="text-lg font-semibold flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-blue-600" />
                Failure Patterns Detected
              </CardTitle>
            </CardHeader>
            <CardContent className="p-6">
              <div className="space-y-4">
                {insights.failure_patterns.map((pattern, idx) => (
                  <div key={idx} className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                    <h4 className="font-semibold text-slate-900 mb-2 flex items-center gap-2">
                      <BarChart3 className="w-4 h-4 text-blue-600" />
                      {pattern.pattern}
                    </h4>
                    <p className="text-sm text-slate-700">{pattern.description}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Root Cause Analysis */}
          <Card className="border-none shadow-md">
            <CardHeader className="border-b border-slate-100">
              <CardTitle className="text-lg font-semibold flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-orange-600" />
                Potential Root Causes
              </CardTitle>
            </CardHeader>
            <CardContent className="p-6">
              <div className="space-y-4">
                {insights.root_causes.map((cause, idx) => (
                  <div key={idx} className="p-4 bg-orange-50 rounded-lg border border-orange-200">
                    <h4 className="font-semibold text-slate-900 mb-2">{cause.cause}</h4>
                    <p className="text-sm text-slate-700">{cause.explanation}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <div className="grid lg:grid-cols-2 gap-6">
            {/* Stability Recommendations */}
            <Card className="border-none shadow-md">
              <CardHeader className="border-b border-slate-100">
                <CardTitle className="text-lg font-semibold flex items-center gap-2">
                  <Target className="w-5 h-5 text-green-600" />
                  Stability Recommendations
                </CardTitle>
              </CardHeader>
              <CardContent className="p-6">
                <div className="space-y-4">
                  {insights.stability_recommendations.map((rec, idx) => (
                    <div key={idx} className="p-4 bg-green-50 rounded-lg border border-green-200">
                      <div className="flex items-start gap-3">
                        <Lightbulb className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
                        <div>
                          <h4 className="font-semibold text-slate-900 mb-1">{rec.recommendation}</h4>
                          <p className="text-sm text-slate-600">
                            <span className="font-medium">Impact:</span> {rec.impact}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Coverage Recommendations */}
            <Card className="border-none shadow-md">
              <CardHeader className="border-b border-slate-100">
                <CardTitle className="text-lg font-semibold flex items-center gap-2">
                  <Target className="w-5 h-5 text-purple-600" />
                  Coverage Recommendations
                </CardTitle>
              </CardHeader>
              <CardContent className="p-6">
                <div className="space-y-4">
                  {insights.coverage_recommendations.map((rec, idx) => (
                    <div key={idx} className="p-4 bg-purple-50 rounded-lg border border-purple-200">
                      <div className="flex items-start gap-3">
                        <Lightbulb className="w-5 h-5 text-purple-600 flex-shrink-0 mt-0.5" />
                        <div>
                          <h4 className="font-semibold text-slate-900 mb-1">{rec.recommendation}</h4>
                          <p className="text-sm text-slate-600">
                            <span className="font-medium">Impact:</span> {rec.impact}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Frequently Failing Tests */}
          {insights.stats.frequentlyFailingTests.length > 0 && (
            <Card className="border-none shadow-md bg-gradient-to-br from-yellow-50 to-orange-50">
              <CardHeader className="border-b border-yellow-100">
                <CardTitle className="text-lg font-semibold flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-yellow-600" />
                  Frequently Failing Tests
                </CardTitle>
              </CardHeader>
              <CardContent className="p-6">
                <div className="space-y-3">
                  {insights.stats.frequentlyFailingTests.slice(0, 5).map((test, idx) => (
                    <div key={idx} className="flex items-center justify-between p-3 bg-white rounded-lg border border-yellow-200">
                      <div className="flex-1">
                        <p className="font-medium text-slate-900">{test.testCase}</p>
                        {test.defects.length > 0 && (
                          <p className="text-sm text-slate-600 mt-1">{test.defects[0]}</p>
                        )}
                      </div>
                      <Badge className="bg-red-100 text-red-700 border-red-200">
                        {test.failureCount} failures
                      </Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Refresh Section */}
          <div className="flex justify-center pt-4">
            <Button
              onClick={analyzeTestResults}
              variant="outline"
              className="gap-2"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh Analysis
            </Button>
          </div>

          <p className="text-center text-xs text-slate-500">
            Analysis generated on {insights.timestamp.toLocaleString()}
          </p>
        </>
      )}
    </div>
  );
}