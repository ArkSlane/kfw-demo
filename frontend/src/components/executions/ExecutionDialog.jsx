import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export default function ExecutionDialog({ open, onOpenChange, execution, testCases, releases, onSubmit, isLoading }) {
  const [formData, setFormData] = useState({
    test_case_id: '',
    release_id: '',
    execution_date: new Date().toISOString().split('T')[0],
    result: 'passed',
    executed_by: '',
    duration: '',
    notes: '',
    defects_found: '',
  });

  useEffect(() => {
    if (execution) {
      setFormData({
        test_case_id: execution.test_case_id || '',
        release_id: execution.release_id || '',
        execution_date: execution.execution_date || new Date().toISOString().split('T')[0],
        result: execution.result || 'passed',
        executed_by: execution.executed_by || '',
        duration: execution.duration || '',
        notes: execution.notes || '',
        defects_found: execution.defects_found || '',
      });
    } else {
      setFormData({
        test_case_id: '',
        release_id: '',
        execution_date: new Date().toISOString().split('T')[0],
        result: 'passed',
        executed_by: '',
        duration: '',
        notes: '',
        defects_found: '',
      });
    }
  }, [execution, open]);

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(formData);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{execution ? 'Edit Test Execution' : 'Log Manual Test Execution'}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="test_case_id">Test Case *</Label>
            <Select 
              value={formData.test_case_id} 
              onValueChange={(value) => setFormData({ ...formData, test_case_id: value })}
              required
            >
              <SelectTrigger>
                <SelectValue placeholder="Select test case" />
              </SelectTrigger>
              <SelectContent>
                {testCases.map((tc) => (
                  <SelectItem key={tc.id} value={tc.id}>
                    {tc.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="execution_date">Execution Date *</Label>
              <Input
                id="execution_date"
                type="date"
                value={formData.execution_date}
                onChange={(e) => setFormData({ ...formData, execution_date: e.target.value })}
                required
              />
            </div>

            <div>
              <Label htmlFor="result">Result *</Label>
              <Select 
                value={formData.result} 
                onValueChange={(value) => setFormData({ ...formData, result: value })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="passed">Passed</SelectItem>
                  <SelectItem value="failed">Failed</SelectItem>
                  <SelectItem value="blocked">Blocked</SelectItem>
                  <SelectItem value="skipped">Skipped</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="executed_by">Executed By</Label>
              <Input
                id="executed_by"
                value={formData.executed_by}
                onChange={(e) => setFormData({ ...formData, executed_by: e.target.value })}
                placeholder="Tester name"
              />
            </div>

            <div>
              <Label htmlFor="duration">Duration (minutes)</Label>
              <Input
                id="duration"
                type="number"
                value={formData.duration}
                onChange={(e) => setFormData({ ...formData, duration: e.target.value })}
                placeholder="e.g., 15"
              />
            </div>
          </div>

          <div>
            <Label htmlFor="release_id">Release</Label>
            <Select 
              value={formData.release_id} 
              onValueChange={(value) => setFormData({ ...formData, release_id: value })}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select release (optional)" />
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

          <div>
            <Label htmlFor="notes">Execution Notes</Label>
            <Textarea
              id="notes"
              value={formData.notes}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              placeholder="Add notes about the execution"
              rows={3}
            />
          </div>

          <div>
            <Label htmlFor="defects_found">Defects Found</Label>
            <Textarea
              id="defects_found"
              value={formData.defects_found}
              onChange={(e) => setFormData({ ...formData, defects_found: e.target.value })}
              placeholder="List any defects or issues found"
              rows={3}
            />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading} className="bg-blue-600 hover:bg-blue-700">
              {isLoading ? 'Saving...' : execution ? 'Update' : 'Log Execution'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}