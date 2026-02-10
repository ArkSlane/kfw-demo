import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useQuery } from "@tanstack/react-query";
import { releasesAPI } from "@/api/releasesClient";

export default function RequirementDialog({ open, onOpenChange, requirement, onSubmit, isLoading }) {
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    source: 'manual',
    tags: [],
    release_id: '',
  });

  const { data: releases } = useQuery({
    queryKey: ['releases'],
    queryFn: () => releasesAPI.list(),
    initialData: [],
  });

  useEffect(() => {
    if (requirement) {
      setFormData({
        title: requirement.title || '',
        description: requirement.description || '',
        source: requirement.source || 'manual',
        tags: requirement.tags || [],
        release_id: requirement.release_id || '',
      });
    } else {
      setFormData({
        title: '',
        description: '',
        source: 'manual',
        tags: [],
        release_id: '',
      });
    }
  }, [requirement, open]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.title.trim()) {
      return;
    }
    onSubmit(formData);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{requirement ? 'Edit Requirement' : 'New Requirement'}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="title">Title *</Label>
            <Input
              id="title"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              placeholder="Enter requirement title"
              required
              minLength={3}
            />
          </div>

          <div>
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="Detailed requirement description"
              rows={4}
            />
          </div>

          <div>
            <Label htmlFor="source">Source</Label>
            <Select value={formData.source} onValueChange={(value) => setFormData({ ...formData, source: value })}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="manual">Manual</SelectItem>
                <SelectItem value="code-analysis">Code Analysis</SelectItem>
                <SelectItem value="jira">Jira</SelectItem>
                <SelectItem value="other">Other</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label htmlFor="release_id">Release (Optional)</Label>
            <Select value={formData.release_id} onValueChange={(value) => setFormData({ ...formData, release_id: value })}>
              <SelectTrigger>
                  <SelectValue placeholder="Select a release (Optional)" />
                </SelectTrigger>
              <SelectContent>

                {releases.map((rel) => (
                  <SelectItem key={rel.id} value={rel.id}>
                    {rel.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label htmlFor="tags">Tags</Label>
            <Input
              id="tags"
              value={formData.tags.join(', ')}
              onChange={(e) => setFormData({ ...formData, tags: e.target.value.split(',').map(t => t.trim()).filter(t => t) })}
              placeholder="Enter tags separated by commas"
              autoComplete="off"
              onKeyDown={(e) => {
                // Allow all keys including comma
              }}
            />
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading} className="bg-blue-600 hover:bg-blue-700">
              {isLoading ? 'Saving...' : requirement ? 'Update' : 'Create'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}