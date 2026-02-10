import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Hash } from "lucide-react";
import { testcasesAPI } from "@/api/testcasesClient";
import { releasesAPI } from "@/api/releasesClient";
import automationsAPI from "@/api/automationsClient";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";

export default function AutomationDialog({ open, onOpenChange, automation, testCases, onSubmit, isLoading }) {
  const [formData, setFormData] = useState({
    title: '',
    test_case_id: '',
    release_id: '',
    framework: 'selenium',
    status: 'not_started',
    script_url: '',
    last_run_date: '',
    last_run_result: '',
    execution_time: '',
    notes: '',
  });
  const { data: releases } = useQuery({
    queryKey: ['releases'],
    queryFn: async () => releasesAPI.list(null, 200, 0),
    initialData: [],
    enabled: open,
  });

  const { data: linkedTestCase } = useQuery({
    queryKey: ['testCase', formData.test_case_id],
    queryFn: () => testcasesAPI.get(formData.test_case_id),
    enabled: open && !!formData.test_case_id,
  });

  const linkedSteps = linkedTestCase?.steps || linkedTestCase?.metadata?.steps || [];

  const queryClient = useQueryClient();
  const normalizeMutation = useMutation({
    mutationFn: (id) => automationsAPI.normalizeScript(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['automations'] });
      queryClient.refetchQueries({ queryKey: ['automations'] });
      toast.success('Script normalized and saved');
    },
    onError: () => {
      toast.error('Failed to normalize script');
    },
  });

  useEffect(() => {
    if (automation) {
      setFormData({
        title: automation.title || '',
        test_case_id: automation.test_case_id || '',
        release_id: automation.release_id || '',
        framework: automation.framework || 'selenium',
        status: automation.status || 'not_started',
        script_url: automation.script_url || '',
        last_run_date: automation.last_run_date || '',
        last_run_result: automation.last_run_result || '',
        execution_time: automation.execution_time || '',
        notes: automation.notes || '',
      });
    } else {
      setFormData({
        title: '',
        test_case_id: '',
        release_id: '',
        framework: 'selenium',
        status: 'not_started',
        script_url: '',
        last_run_date: '',
        last_run_result: '',
        execution_time: '',
        notes: '',
      });
    }
  }, [automation, open]);

  const handleStatusChange = (newStatus) => {
    setFormData({ ...formData, status: newStatus });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    onSubmit(formData);
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              <div className="flex items-center gap-2">
                <span>{automation ? 'Edit Automation' : 'New Automation'}</span>
                {automation?.id && (
                  <Badge
                    variant="outline"
                    className="gap-1 text-xs text-slate-500 border-slate-300 cursor-pointer hover:bg-slate-100 hover:border-slate-400 transition-colors font-mono"
                    onClick={(e) => {
                      e.stopPropagation();
                      navigator.clipboard.writeText(automation.id);
                      toast.success('ID copied to clipboard!');
                    }}
                    title="Click to copy ID"
                  >
                    <Hash className="w-3 h-3" />
                    {automation.id}
                  </Badge>
                )}
              </div>
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <Label htmlFor="title">Title *</Label>
              <Input
                id="title"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder="Enter automation title"
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="test_case_id">Linked Test Case</Label>
                <Select value={formData.test_case_id} onValueChange={(value) => setFormData({ ...formData, test_case_id: value })}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select test case" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={null}>None</SelectItem>
                    {testCases.map((tc) => (
                      <SelectItem key={tc.id} value={tc.id}>
                        {tc.title.length > 30 ? tc.title.substring(0, 30) + '...' : tc.title}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label htmlFor="release_id">Release</Label>
                <Select value={formData.release_id} onValueChange={(value) => setFormData({ ...formData, release_id: value })}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select release" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={null}>None</SelectItem>
                    {releases.map((rel) => (
                      <SelectItem key={rel.id} value={rel.id}>
                        {rel.name} {rel.version && `(v${rel.version})`}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="framework">Framework</Label>
                <Select value={formData.framework} onValueChange={(value) => setFormData({ ...formData, framework: value })}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="selenium">Selenium</SelectItem>
                    <SelectItem value="cypress">Cypress</SelectItem>
                    <SelectItem value="playwright">Playwright</SelectItem>
                    <SelectItem value="junit">JUnit</SelectItem>
                    <SelectItem value="pytest">Pytest</SelectItem>
                    <SelectItem value="other">Other</SelectItem>
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
                    <SelectItem value="not_started">Not Started</SelectItem>
                    <SelectItem value="in_development">In Development</SelectItem>
                    <SelectItem value="ready">Ready</SelectItem>
                    <SelectItem value="passing">Passing</SelectItem>
                    <SelectItem value="failing">Failing</SelectItem>
                    <SelectItem value="maintenance">Maintenance</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div>
              <Label htmlFor="script_url">Script URL</Label>
              <Input
                id="script_url"
                value={formData.script_url}
                onChange={(e) => setFormData({ ...formData, script_url: e.target.value })}
                placeholder="Repository or script URL"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="last_run_date">Last Run Date</Label>
                <Input
                  id="last_run_date"
                  type="date"
                  value={formData.last_run_date}
                  onChange={(e) => setFormData({ ...formData, last_run_date: e.target.value })}
                />
              </div>

              <div>
                <Label htmlFor="last_run_result">Last Run Result</Label>
                <Select value={formData.last_run_result} onValueChange={(value) => setFormData({ ...formData, last_run_result: value })}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select result" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={null}>Not run yet</SelectItem>
                    <SelectItem value="passed">Passed</SelectItem>
                    <SelectItem value="failed">Failed</SelectItem>
                    <SelectItem value="skipped">Skipped</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div>
              <Label htmlFor="execution_time">Execution Time (seconds)</Label>
              <Input
                id="execution_time"
                type="number"
                value={formData.execution_time}
                onChange={(e) => setFormData({ ...formData, execution_time: e.target.value })}
                placeholder="e.g., 45"
              />
            </div>

            <div>
              <Label htmlFor="notes">Notes</Label>
              <Textarea
                id="notes"
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                placeholder="Additional notes or details"
                rows={4}
              />
            </div>

            {automation && (
              <div className="space-y-4">
                <div>
                  <div className="flex items-center justify-between gap-3">
                    <Label>Automation Code</Label>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={!automation?.id || normalizeMutation.isPending}
                      onClick={() => {
                        if (!automation?.id) return;
                        normalizeMutation.mutate(automation.id);
                      }}
                    >
                      {normalizeMutation.isPending ? 'Normalizing…' : 'Normalize Script'}
                    </Button>
                  </div>
                  <div className="mt-2">
                    <Textarea
                      value={automation.script || ''}
                      readOnly
                      placeholder="No script stored for this automation."
                      rows={10}
                      className="font-mono text-xs"
                    />
                  </div>
                </div>

                <div>
                  <Label>Test Case Steps</Label>
                  <div className="mt-2 bg-slate-50 border border-slate-200 rounded-md p-3 max-h-[35vh] overflow-auto">
                    {Array.isArray(linkedSteps) && linkedSteps.length > 0 ? (
                      <div className="space-y-3">
                        {linkedSteps.map((step, i) => (
                          <div key={i} className="text-sm text-slate-800">
                            <div className="font-medium">Step {i + 1}: {step?.action || '(no action)'} </div>
                            {step?.expected_result ? (
                              <div className="text-slate-600 whitespace-pre-wrap">Expected: {step.expected_result}</div>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-sm text-slate-600">No steps found for the linked test case.</div>
                    )}
                  </div>
                </div>
              </div>
            )}

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={isLoading} className="bg-blue-600 hover:bg-blue-700">
                {isLoading ? 'Saving...' : automation ? 'Update' : 'Create'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}