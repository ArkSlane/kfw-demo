import React, { useState } from "react";
import { Link } from "react-router-dom";
import { createPageUrl } from "@/utils";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Plus, Bot, CheckCircle2, XCircle, Filter, Trash2, Play, Video, List } from "lucide-react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import AutomationDialog from "../components/automations/AutomationDialog";
import { format } from "date-fns";
import { toast } from "sonner";
import automationsAPI from "@/api/automationsClient";
import { testcasesAPI } from "@/api/testcasesClient";
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

export default function Automations() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingAutomation, setEditingAutomation] = useState(null);
  const [filterStatus, setFilterStatus] = useState("all");
  const [filterTestCase, setFilterTestCase] = useState("all");
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [automationToDelete, setAutomationToDelete] = useState(null);
  const [videoDialogOpen, setVideoDialogOpen] = useState(false);
  const [selectedVideoAutomationId, setSelectedVideoAutomationId] = useState(null);
  const [actionsDialogOpen, setActionsDialogOpen] = useState(false);
  const [selectedActions, setSelectedActions] = useState("");
  const [newlyCreatedId, setNewlyCreatedId] = useState(null);
  const queryClient = useQueryClient();

  const { data: automations = [], isLoading } = useQuery({
    queryKey: ['automations'],
    queryFn: () => automationsAPI.list(),
  });

  const { data: testCases = [] } = useQuery({
    queryKey: ['testCases'],
    queryFn: () => testcasesAPI.list(),
  });

  const createMutation = useMutation({
    mutationFn: (data) => automationsAPI.create(data),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['automations'] });
      setNewlyCreatedId(response?.id);
      setDialogOpen(false);
      setEditingAutomation(null);
      toast.success('Automation created successfully! 🎉', {
        action: { label: 'Dismiss', onClick: () => {} }
      });
      // Clear highlight after 3 seconds
      setTimeout(() => setNewlyCreatedId(null), 3000);
    },
    onError: () => {
      toast.error('Failed to create automation');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => automationsAPI.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['automations'] });
      setDialogOpen(false);
      setEditingAutomation(null);
      toast.success('Automation updated successfully');
    },
    onError: () => {
      toast.error('Failed to update automation');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id) => automationsAPI.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['automations'] });
      toast.success('Automation deleted successfully');
    },
    onError: () => {
      toast.error('Failed to delete automation');
    },
  });

  const executeMutation = useMutation({
    mutationFn: (id) => automationsAPI.execute(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['automations'] });
      // Make the UI update as soon as the execution finishes and is persisted.
      queryClient.refetchQueries({ queryKey: ['automations'] });
      toast.success('Automation execution completed');
    },
    onError: () => {
      toast.error('Failed to start automation');
    },
  });

  const handleSubmit = (data) => {
    if (editingAutomation) {
      updateMutation.mutate({ id: editingAutomation.id, data });
    } else {
      createMutation.mutate(data);
    }
  };

  const handleEdit = (automation) => {
    setEditingAutomation(automation);
    setDialogOpen(true);
  };

  const handleDeleteClick = (automation, e) => {
    e.stopPropagation();
    setAutomationToDelete(automation);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = () => {
    if (automationToDelete) {
      deleteMutation.mutate(automationToDelete.id);
    }
  };

  const filteredAutomations = automations.filter(auto => {
    const statusMatch = filterStatus === "all" || auto.status === filterStatus;
    const testCaseMatch = filterTestCase === "all" || auto.test_case_id === filterTestCase;
    return statusMatch && testCaseMatch;
  });

  const statusColors = {
    not_started: 'bg-slate-100 text-slate-700 border-slate-200',
    in_development: 'bg-blue-100 text-blue-700 border-blue-200',
    ready: 'bg-purple-100 text-purple-700 border-purple-200',
    passing: 'bg-green-100 text-green-700 border-green-200',
    failing: 'bg-red-100 text-red-700 border-red-200',
    maintenance: 'bg-orange-100 text-orange-700 border-orange-200',
  };

  const resultColors = {
    passed: 'bg-green-100 text-green-700 border-green-200',
    failed: 'bg-red-100 text-red-700 border-red-200',
    skipped: 'bg-slate-100 text-slate-700 border-slate-200',
  };

  const getTestCaseTitle = (testCaseId) => {
    const testCase = testCases.find(tc => tc.id === testCaseId);
    return testCase ? testCase.title : null;
  };

  const selectedVideoAutomation = selectedVideoAutomationId
    ? automations.find((a) => a.id === selectedVideoAutomationId)
    : null;

  const selectedVideoSrc = selectedVideoAutomation
    ? `${automationsAPI.getVideoUrl(selectedVideoAutomation.id)}?t=${encodeURIComponent(
        selectedVideoAutomation.last_run_at ||
          selectedVideoAutomation.last_run_date ||
          selectedVideoAutomation.video_path ||
          Date.now()
      )}`
    : "";

  return (
    <div className="p-6 lg:p-8 space-y-6">
      <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 mb-2">Test Automations</h1>
          <p className="text-slate-600">Manage automated test scripts</p>
        </div>
        <Button 
          onClick={() => {
            setEditingAutomation(null);
            setDialogOpen(true);
          }}
          className="bg-blue-600 hover:bg-blue-700 gap-2"
        >
          <Plus className="w-4 h-4" />
          New Automation
        </Button>
      </div>

      <Card className="border-none shadow-md">
        <CardHeader className="border-b border-slate-100">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <CardTitle className="text-lg font-semibold">All Automations</CardTitle>
            <div className="flex items-center gap-3 flex-wrap">
              <div className="flex items-center gap-2">
                <Filter className="w-4 h-4 text-slate-600" />
                <Select value={filterTestCase} onValueChange={setFilterTestCase}>
                  <SelectTrigger className="w-[200px]">
                    <SelectValue placeholder="Filter by Test Case" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Test Cases</SelectItem>
                    {testCases.map((tc) => (
                      <SelectItem key={tc.id} value={tc.id}>
                        {tc.title.length > 30 ? tc.title.substring(0, 30) + '...' : tc.title}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Tabs value={filterStatus} onValueChange={setFilterStatus}>
                <TabsList className="bg-slate-100">
                  <TabsTrigger value="all">All</TabsTrigger>
                  <TabsTrigger value="ready">Ready</TabsTrigger>
                  <TabsTrigger value="passing">Passing</TabsTrigger>
                  <TabsTrigger value="failing">Failing</TabsTrigger>
                </TabsList>
              </Tabs>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-6">
          {isLoading ? (
            <div className="text-center py-12 text-slate-500">Loading...</div>
          ) : filteredAutomations.length === 0 ? (
            <div className="text-center py-12">
              <Bot className="w-16 h-16 mx-auto mb-4 text-slate-300" />
              <p className="text-slate-500 mb-4">No automations found</p>
              <Button onClick={() => setDialogOpen(true)} variant="outline">
                <Plus className="w-4 h-4 mr-2" />
                Create your first automation
              </Button>
            </div>
          ) : (
            <div className="grid md:grid-cols-2 gap-4">
              {filteredAutomations.map((auto) => (
                <Card 
                  key={auto.id}
                  className={`border ${newlyCreatedId === auto.id ? 'border-blue-500 shadow-lg shadow-blue-200 bg-blue-50 ring-2 ring-blue-300' : 'border-slate-200'} hover:shadow-lg transition-all cursor-pointer group relative`}
                >
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={(e) => handleDeleteClick(auto, e)}
                    className="absolute top-2 right-2 text-red-600 hover:text-red-700 hover:bg-red-50 opacity-0 group-hover:opacity-100 transition-opacity z-10"
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                  <CardContent className="p-6" onClick={() => handleEdit(auto)}>
                    <div className="flex items-start justify-between mb-3">
                      <Bot className="w-8 h-8 text-green-600" />
                      {auto.last_run_result && (
                        <div>
                          {auto.last_run_result === 'passed' && <CheckCircle2 className="w-6 h-6 text-green-600" />}
                          {auto.last_run_result === 'failed' && <XCircle className="w-6 h-6 text-red-600" />}
                        </div>
                      )}
                    </div>
                    <h3 className="text-lg font-semibold text-slate-900 mb-2">{auto.title}</h3>
                    {auto.test_case_id && getTestCaseTitle(auto.test_case_id) && (
                      <p className="text-sm text-purple-600 mb-3">
                        🧪 {getTestCaseTitle(auto.test_case_id)}
                      </p>
                    )}
                    <div className="flex flex-wrap gap-2 mb-3">
                      <Badge className={`border ${statusColors[auto.status]}`}>
                        {auto.status.replace(/_/g, ' ')}
                      </Badge>
                      <Badge variant="outline" className="text-slate-600">
                        {auto.framework}
                      </Badge>
                      {auto.last_run_result && (
                        <Badge className={`border ${resultColors[auto.last_run_result]}`}>
                          {auto.last_run_result}
                        </Badge>
                      )}
                    </div>
                    {(auto.last_run_at || auto.last_run_date) && (
                      <p className="text-xs text-slate-500">
                        Last run: {format(new Date(auto.last_run_at || auto.last_run_date), 'MMM d, yyyy')}
                        {auto.execution_time && ` • ${auto.execution_time}s`}
                      </p>
                    )}
                    
                    <div className="flex gap-2 mt-4" onClick={(e) => e.stopPropagation()}>
                      <Button
                        size="sm"
                        variant="outline"
                        className="gap-2"
                        onClick={() => executeMutation.mutate(auto.id)}
                        disabled={executeMutation.isPending || auto.status === 'in_progress'}
                      >
                        <Play className="w-3 h-3" />
                        {auto.status === 'in_progress' ? 'Running...' : 'Execute'}
                      </Button>
                      {auto?.metadata?.last_execution_id && (
                        <Button size="sm" variant="outline" className="gap-2" asChild>
                          <Link
                            to={`${createPageUrl("Executions")}?execution_id=${encodeURIComponent(
                              auto.metadata.last_execution_id
                            )}`}
                          >
                            View Result
                          </Link>
                        </Button>
                      )}
                      {auto.video_path && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="gap-2"
                          onClick={() => {
                            setSelectedVideoAutomationId(auto.id);
                            setVideoDialogOpen(true);
                          }}
                        >
                          <Video className="w-3 h-3" />
                          Watch Video
                        </Button>
                      )}
                      {auto.last_actions && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="gap-2"
                          onClick={() => {
                            setSelectedActions(auto.last_actions);
                            setActionsDialogOpen(true);
                          }}
                        >
                          <List className="w-3 h-3" />
                          View Actions
                        </Button>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <AutomationDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        automation={editingAutomation}
        testCases={testCases}
        onSubmit={handleSubmit}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Automation</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{automationToDelete?.title}"? This action cannot be undone.
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

      <AlertDialog open={videoDialogOpen} onOpenChange={setVideoDialogOpen}>
        <AlertDialogContent className="max-w-4xl">
          <AlertDialogHeader>
            <AlertDialogTitle>Execution Video</AlertDialogTitle>
            <AlertDialogDescription>
              Recording of the automation test execution
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="aspect-video bg-black rounded-lg overflow-hidden">
            {selectedVideoAutomation && (
              <video
                key={selectedVideoSrc}
                controls
                autoPlay
                className="w-full h-full"
                src={selectedVideoSrc}
              >
                Your browser does not support the video tag.
              </video>
            )}
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel>Close</AlertDialogCancel>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={actionsDialogOpen} onOpenChange={setActionsDialogOpen}>
        <AlertDialogContent className="max-w-3xl">
          <AlertDialogHeader>
            <AlertDialogTitle>Actions Taken</AlertDialogTitle>
            <AlertDialogDescription>
              LLM-guided steps executed during the test
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="bg-slate-50 border border-slate-200 rounded-md p-4 overflow-auto max-h-[50vh] whitespace-pre-wrap text-sm">
            {selectedActions || 'No actions recorded.'}
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel>Close</AlertDialogCancel>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}