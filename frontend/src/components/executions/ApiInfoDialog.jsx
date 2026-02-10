import React from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Copy, CheckCircle2, Upload, Code } from "lucide-react";
import { toast } from "sonner";

export default function ApiInfoDialog({ open, onOpenChange }) {
  const examplePayload = {
    test_case_id: "your-test-case-id",
    result: "passed",
    execution_date: "2024-01-15",
    executed_by: "Jenkins CI",
    duration: 5.2,
    notes: "Automated execution via CI/CD",
    step_results: [
      {
        step_number: 1,
        action: "Login to application",
        expected_result: "User logged in successfully",
        result: "passed",
        actual_result: "User logged in successfully"
      },
      {
        step_number: 2,
        action: "Navigate to dashboard",
        expected_result: "Dashboard loads with widgets",
        result: "passed",
        actual_result: "Dashboard loaded in 0.8s"
      },
      {
        step_number: 3,
        action: "Click on reports section",
        expected_result: "Reports page opens",
        result: "failed",
        actual_result: "404 error - page not found"
      }
    ],
    defects_found: "Dashboard reports section returns 404 error",
    release_id: "optional-release-id"
  };

  const jsExample = `import { base44 } from '@/api/base44Client';
import axios from 'axios';

// Call from your test automation framework / CI
const response = await axios.post('http://localhost:8005/executions', ${JSON.stringify(examplePayload, null, 2)}, {
  headers: { 'Content-Type': 'application/json' },
});

console.log(response.data);`;

  const curlExample = `curl -X POST http://localhost:8005/executions \\
  -H "Content-Type: application/json" \\
  -d '${JSON.stringify(examplePayload, null, 2)}'`;

  const handleCopyPayload = () => {
    navigator.clipboard.writeText(JSON.stringify(examplePayload, null, 2));
    toast.success('Example payload copied to clipboard!');
  };

  const handleCopyJsExample = () => {
    navigator.clipboard.writeText(jsExample);
    toast.success('JavaScript example copied to clipboard!');
  };

  const handleCopyCurlExample = () => {
    navigator.clipboard.writeText(curlExample);
    toast.success('cURL example copied to clipboard!');
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl">
            <Upload className="w-6 h-6 text-blue-600" />
            Test Results Upload API
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6">
          {/* Overview */}
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <h3 className="font-semibold text-blue-900 mb-2">API Overview</h3>
            <p className="text-sm text-blue-800 mb-3">
              Use this backend function to automatically upload test automation results from your CI/CD pipeline or test framework.
            </p>
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="bg-white">Function Name</Badge>
                <code className="text-blue-900 font-mono">uploadTestResults</code>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="bg-white">Method</Badge>
                <code className="text-blue-900 font-mono">POST</code>
              </div>
            </div>
          </div>

          {/* Required Fields */}
          <div>
            <h3 className="font-semibold text-slate-900 mb-3 flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-green-600" />
              Required Fields
            </h3>
            <div className="bg-slate-50 rounded-lg p-4 space-y-2 text-sm">
              <div className="flex items-start gap-3">
                <code className="font-mono text-blue-600 mt-0.5">test_case_id</code>
                <span className="text-slate-600">- ID of the test case being executed</span>
              </div>
              <div className="flex items-start gap-3">
                <code className="font-mono text-blue-600 mt-0.5">result</code>
                <span className="text-slate-600">- Test result: "passed", "failed", "blocked", or "skipped"</span>
              </div>
              <div className="flex items-start gap-3">
                <code className="font-mono text-blue-600 mt-0.5">execution_date</code>
                <span className="text-slate-600">- Date of execution (YYYY-MM-DD format)</span>
              </div>
            </div>
          </div>

          {/* Optional Fields */}
          <div>
            <h3 className="font-semibold text-slate-900 mb-3">Optional Fields</h3>
            <div className="bg-slate-50 rounded-lg p-4 space-y-2 text-sm">
              <div className="flex items-start gap-3">
                <code className="font-mono text-purple-600 mt-0.5">executed_by</code>
                <span className="text-slate-600">- Name of executor (default: "Automation")</span>
              </div>
              <div className="flex items-start gap-3">
                <code className="font-mono text-purple-600 mt-0.5">duration</code>
                <span className="text-slate-600">- Execution duration in minutes</span>
              </div>
              <div className="flex items-start gap-3">
                <code className="font-mono text-purple-600 mt-0.5">notes</code>
                <span className="text-slate-600">- Execution notes</span>
              </div>
              <div className="flex items-start gap-3">
                <code className="font-mono text-purple-600 mt-0.5">defects_found</code>
                <span className="text-slate-600">- Description of defects or issues</span>
              </div>
              <div className="flex items-start gap-3">
                <code className="font-mono text-purple-600 mt-0.5">step_results</code>
                <span className="text-slate-600">- Array of step-by-step results</span>
              </div>
              <div className="flex items-start gap-3">
                <code className="font-mono text-purple-600 mt-0.5">release_id</code>
                <span className="text-slate-600">- Optional release ID to link execution</span>
              </div>
            </div>
          </div>

          {/* Example Payload */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-slate-900 flex items-center gap-2">
                <Code className="w-5 h-5 text-slate-600" />
                Example Payload
              </h3>
              <Button
                size="sm"
                variant="outline"
                onClick={handleCopyPayload}
                className="gap-2"
              >
                <Copy className="w-3 h-3" />
                Copy JSON
              </Button>
            </div>
            <div className="relative">
              <pre className="bg-slate-900 text-slate-100 rounded-lg p-4 overflow-x-auto text-xs">
                <code>{JSON.stringify(examplePayload, null, 2)}</code>
              </pre>
            </div>
          </div>

          {/* JavaScript Example */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-slate-900">JavaScript Example</h3>
              <Button
                size="sm"
                variant="outline"
                onClick={handleCopyJsExample}
                className="gap-2"
              >
                <Copy className="w-3 h-3" />
                Copy Code
              </Button>
            </div>
            <div className="relative">
              <pre className="bg-slate-900 text-slate-100 rounded-lg p-4 overflow-x-auto text-xs">
                <code>{jsExample}</code>
              </pre>
            </div>
          </div>

          {/* cURL Example */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-slate-900">cURL Example</h3>
              <Button
                size="sm"
                variant="outline"
                onClick={handleCopyCurlExample}
                className="gap-2"
              >
                <Copy className="w-3 h-3" />
                Copy Command
              </Button>
            </div>
            <div className="relative">
              <pre className="bg-slate-900 text-slate-100 rounded-lg p-4 overflow-x-auto text-xs">
                <code>{curlExample}</code>
              </pre>
            </div>
          </div>

          {/* Integration Tips */}
          <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
            <h3 className="font-semibold text-amber-900 mb-2">💡 Integration Tips</h3>
            <ul className="text-sm text-amber-800 space-y-1 list-disc list-inside">
              <li>Call this function at the end of each automated test run</li>
              <li>Include step_results to see which specific steps failed</li>
              <li>Use meaningful names in executed_by (e.g., "Jenkins Build #123")</li>
              <li>Link to releases using release_id for better tracking</li>
              <li>Set execution_type to "automated" is handled automatically</li>
            </ul>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}