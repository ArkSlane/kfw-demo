
import React, { useState } from "react";
import { requirementsAPI } from "@/api/requirementsClient";
import { testcasesAPI } from "@/api/testcasesClient";
import { releasesAPI } from "@/api/releasesClient";
import generatorAPI from "@/api/generatorClient";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Plus, Filter, FileText, AlertCircle, TestTube, Trash2, Hash, Sparkles } from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import RequirementDialog from "../components/requirements/RequirementDialog";
import TestCaseDialog from "../components/testcases/TestCaseDialog";
import AdvancedAITestDialog from "../components/requirements/AdvancedAITestDialog";
import { toast } from "sonner";
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

export default function Requirements() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingRequirement, setEditingRequirement] = useState(null);
  const [filterRelease, setFilterRelease] = useState("all");
  const [testCaseDialogOpen, setTestCaseDialogOpen] = useState(false);
  const [selectedRequirement, setSelectedRequirement] = useState(null);
  const [generatingAI, setGeneratingAI] = useState(null);
  const [aiGeneratedData, setAiGeneratedData] = useState(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [requirementToDelete, setRequirementToDelete] = useState(null);
  const [advancedAIDialogOpen, setAdvancedAIDialogOpen] = useState(false);
  const [advancedAISuggestions, setAdvancedAISuggestions] = useState(null);
  const [creatingMultipleTests, setCreatingMultipleTests] = useState(false);
  const queryClient = useQueryClient();

  const { data: requirements, isLoading } = useQuery({
    queryKey: ['requirements'],
    queryFn: () => requirementsAPI.list(),
    initialData: [],
  });

  const { data: testCases } = useQuery({
    queryKey: ['testCases'],
    queryFn: () => testcasesAPI.list(),
    initialData: [],
  });

  const { data: releases } = useQuery({
    queryKey: ['releases'],
    queryFn: () => releasesAPI.list(),
    initialData: [],
  });

  const createMutation = useMutation({
    mutationFn: (data) => requirementsAPI.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['requirements'] });
      setDialogOpen(false);
      setEditingRequirement(null);
      toast.success('Requirement created successfully!');
    },
    onError: (error) => {
      toast.error('Failed to create requirement');
      console.error(error);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => requirementsAPI.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['requirements'] });
      setDialogOpen(false);
      setEditingRequirement(null);
      toast.success('Requirement updated successfully!');
    },
    onError: (error) => {
      toast.error('Failed to update requirement');
      console.error(error);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id) => requirementsAPI.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['requirements'] });
      toast.success('Requirement deleted successfully!');
      setDeleteDialogOpen(false);
      setRequirementToDelete(null);
    },
    onError: (error) => {
      toast.error('Failed to delete requirement');
      console.error(error);
    },
  });

  const createTestCaseMutation = useMutation({
    mutationFn: (data) => testcasesAPI.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['testCases'] });
      setTestCaseDialogOpen(false);
      setSelectedRequirement(null);
      setAiGeneratedData(null);
      toast.success('Test case created successfully!');
    },
    onError: (error) => {
      toast.error('Failed to create test case');
      console.error(error);
    },
  });

  const buildGherkinFromSteps = (featureTitle, scenarioTitle, steps) => {
    const safeFeature = (featureTitle || "Feature").trim();
    const safeScenario = (scenarioTitle || "Scenario").trim();
    const safeSteps = Array.isArray(steps) ? steps : [];
    const stepLines = safeSteps
      .filter((s) => s && typeof s.action === "string" && s.action.trim())
      .map((s) => {
        const action = s.action.trim();
        const expected = typeof s.expected_result === "string" ? s.expected_result.trim() : "";
        return `    * ${action}${expected ? ` -> ${expected}` : ""}`;
      });

    return `Feature: ${safeFeature}\n\n  Scenario: ${safeScenario}\n${stepLines.join("\n")}\n`;
  };

  const handleSubmit = (data) => {
    if (editingRequirement) {
      updateMutation.mutate({ id: editingRequirement.id, data });
    } else {
      createMutation.mutate(data);
    }
  };

  const handleEdit = (requirement) => {
    setEditingRequirement(requirement);
    setDialogOpen(true);
  };

  const handleDeleteClick = (requirement, e) => {
    e.stopPropagation();
    setRequirementToDelete(requirement);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = () => {
    if (requirementToDelete) {
      deleteMutation.mutate(requirementToDelete.id);
    }
  };

  const handleGenerateSelectedTests = async (selectedTestsData) => {
    if (!selectedRequirement) {
      toast.error('No requirement selected for creating test cases');
      return;
    }
    setCreatingMultipleTests(true);
    try {
      const positive = selectedTestsData?.positive || [];
      const negative = selectedTestsData?.negative || [];
      const allTests = [...positive, ...negative];

      const createPromises = allTests.map((test) => {
        const steps = test.steps || [];
        // build a simple Gherkin from steps if no description provided
        const gherkin = test.description || steps.map(s => `* ${s.action} -> ${s.expected_result}`).join('\n');
        const payload = {
          requirement_id: selectedRequirement.id,
          title: test.title,
          gherkin: gherkin,
          status: 'draft',
          metadata: {
            description: test.description || '',
            priority: (test.priority || 'medium').toLowerCase(),
            test_type: test.test_type || 'manual',
            steps: steps,
          }
        };
        return testcasesAPI.create(payload);
      });

      const created = await Promise.all(createPromises);
      queryClient.invalidateQueries({ queryKey: ['testCases'] });

      // Link created testcases into the requirement's release (if set)
      if (selectedRequirement.release_id && Array.isArray(created) && created.length > 0) {
        try {
          const rel = await releasesAPI.get(selectedRequirement.release_id);
          if (rel?.id) {
            const testcaseIds = Array.isArray(rel.testcase_ids) ? [...rel.testcase_ids] : [];
            for (const tc of created) {
              if (tc?.id && !testcaseIds.includes(tc.id)) testcaseIds.push(tc.id);
            }

            const requirementIds = Array.isArray(rel.requirement_ids) ? [...rel.requirement_ids] : [];
            if (!requirementIds.includes(selectedRequirement.id)) requirementIds.push(selectedRequirement.id);

            await releasesAPI.update(rel.id, {
              testcase_ids: testcaseIds,
              requirement_ids: requirementIds,
            });
            queryClient.invalidateQueries({ queryKey: ['releases'] });
          }
        } catch (e) {
          console.error(e);
          // Non-fatal: testcase creation succeeded
        }
      }

      toast.success(`Created ${createPromises.length} test case${createPromises.length !== 1 ? 's' : ''}`);
      setAdvancedAIDialogOpen(false);
      setAdvancedAISuggestions(null);
      setSelectedRequirement(null);
    } catch (error) {
      toast.error('Failed to create test cases');
      console.error(error);
    } finally {
      setCreatingMultipleTests(false);
    }
  };

  const handleCreateTestCase = async (requirement) => {
    setSelectedRequirement(requirement);
    setGeneratingAI(requirement.id);
    
    try {
      const generated = await generatorAPI.generateStructuredTestcase(requirement.id);
      const tc = generated?.testcase;
      if (!tc) throw new Error("Generator returned no testcase");

      const allowedPriorities = new Set(["critical", "high", "medium", "low"]);
      const priority = allowedPriorities.has((tc.priority || "").toLowerCase())
        ? tc.priority.toLowerCase()
        : "medium";

      const steps = Array.isArray(tc.steps) ? tc.steps : [];
      const normalizedSteps = steps
        .filter((s) => s && typeof s.action === "string" && s.action.trim())
        .map((s) => ({
          action: s.action.trim(),
          expected_result: typeof s.expected_result === "string" && s.expected_result.trim()
            ? s.expected_result.trim()
            : "Expected result",
        }));

      const finalSteps = normalizedSteps.length
        ? normalizedSteps
        : [{ action: "Verify the requirement behavior", expected_result: "The requirement is satisfied" }];

      const gherkin = buildGherkinFromSteps(requirement.title, tc.title, finalSteps);

      const payload = {
        requirement_id: requirement.id,
        title: tc.title,
        gherkin,
        status: "draft",
        metadata: {
          description: tc.description,
          priority,
          steps: finalSteps,
          generator: generated?.generator || "ollama",
          model: generated?.model,
          attempts: generated?.attempts,
          generated_at: new Date().toISOString(),
        },
      };

      const created = await testcasesAPI.create(payload);

      // Link into the release (if the requirement is assigned to one)
      if (requirement.release_id) {
        const rel = await releasesAPI.get(requirement.release_id);
        if (rel?.id) {
          const testcaseIds = Array.isArray(rel.testcase_ids) ? [...rel.testcase_ids] : [];
          if (!testcaseIds.includes(created.id)) testcaseIds.push(created.id);

          const requirementIds = Array.isArray(rel.requirement_ids) ? [...rel.requirement_ids] : [];
          if (!requirementIds.includes(requirement.id)) requirementIds.push(requirement.id);

          await releasesAPI.update(rel.id, {
            testcase_ids: testcaseIds,
            requirement_ids: requirementIds,
          });
          queryClient.invalidateQueries({ queryKey: ["releases"] });
        }
      }

      queryClient.invalidateQueries({ queryKey: ["testCases"] });
      setSelectedRequirement(null);
      toast.success("Quick Test created");
    } catch (error) {
      toast.error('Failed to generate Quick Test');
      console.error(error);
    } finally {
      setGeneratingAI(null);
    }
  };

  const handleAdvancedAI = async (requirement) => {
    setSelectedRequirement(requirement);
    setGeneratingAI(requirement.id);
    setAdvancedAIDialogOpen(true);
    
    try {
      const suggestions = await generatorAPI.generateTestSuite(requirement.id, 3, 2);
      setAdvancedAISuggestions(suggestions);
    } catch (error) {
      toast.error('Failed to generate AI test suite');
      console.error(error);
    } finally {
      setGeneratingAI(null);
    }
  };

  const handleTestCaseSubmit = (data) => {
    createTestCaseMutation.mutate(data);
  };

  const filteredRequirements = requirements.filter(req => {
    // Filter by release
    if (filterRelease !== "all" && req.release_id !== filterRelease) {
      return false;
    }
    
    return true;
  });

  // Debug logging
  console.log('Requirements total:', requirements.length);
  console.log('Filter release:', filterRelease);
  console.log('Filtered requirements:', filteredRequirements.length);
  if (filterRelease !== "all") {
    console.log('Requirements with selected release_id:', requirements.filter(r => r.release_id === filterRelease).length);
  }

  const priorityColors = {
    critical: 'bg-red-100 text-red-700 border-red-200',
    high: 'bg-orange-100 text-orange-700 border-orange-200',
    medium: 'bg-yellow-100 text-yellow-700 border-yellow-200',
    low: 'bg-blue-100 text-blue-700 border-blue-200',
  };

  const statusColors = {
    draft: 'bg-slate-50 text-slate-700 border-slate-200',
    approved: 'bg-green-50 text-green-700 border-green-200',
    in_development: 'bg-yellow-50 text-yellow-700 border-yellow-200',
    ready_for_testing: 'bg-blue-50 text-blue-700 border-blue-200',
    completed: 'bg-green-100 text-green-800 border-green-200',
    // fallback style
    default: 'bg-slate-100 text-slate-700 border-slate-200',
  };

  return (
    <div className="p-6 lg:p-8 space-y-6">
      <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 mb-2">Requirements</h1>
          <p className="text-slate-600">Manage project requirements and specifications</p>
        </div>
        <Button 
          onClick={() => {
            setEditingRequirement(null);
            setDialogOpen(true);
          }}
          className="bg-blue-600 hover:bg-blue-700 gap-2"
        >
          <Plus className="w-4 h-4" />
          New Requirement
        </Button>
      </div>

      <Card className="border-none shadow-md">
        <CardHeader className="border-b border-slate-100">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <CardTitle className="text-lg font-semibold">All Requirements</CardTitle>
            <div className="flex items-center gap-3 flex-wrap">
              <div className="flex items-center gap-2">
                <Filter className="w-4 h-4 text-slate-600" />
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
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-6">
          {isLoading ? (
            <div className="text-center py-12 text-slate-500">Loading...</div>
          ) : filteredRequirements.length === 0 ? (
            <div className="text-center py-12">
              <FileText className="w-16 h-16 mx-auto mb-4 text-slate-300" />
              <p className="text-slate-500 mb-4">No requirements found</p>
              <Button onClick={() => setDialogOpen(true)} variant="outline">
                <Plus className="w-4 h-4 mr-2" />
                Create your first requirement
              </Button>
            </div>
          ) : (
            <div className="grid gap-4">
              {filteredRequirements.map((req) => {
                const linkedTestCases = testCases.filter(tc => tc.requirement_ids && tc.requirement_ids.includes(req.id));
                const isGenerating = generatingAI === req.id;
                return (
                  <Card 
                    key={req.id}
                    className="border border-slate-200 hover:shadow-lg transition-all"
                  >
                    <CardContent className="p-6">
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex-1 cursor-pointer" onClick={() => handleEdit(req)}>
                          <div className="flex items-center gap-2 mb-2">
                            <h3 className="text-lg font-semibold text-slate-900">{req.title}</h3>
                            <Badge 
                              variant="outline" 
                              className="gap-1 text-xs text-slate-500 border-slate-300 cursor-pointer hover:bg-slate-100 hover:border-slate-400 transition-colors font-mono"
                              onClick={(e) => {
                                e.stopPropagation();
                                navigator.clipboard.writeText(req.id);
                                toast.success('ID copied to clipboard!');
                              }}
                              title="Click to copy ID"
                            >
                              <Hash className="w-3 h-3" />
                              {req.id}
                            </Badge>
                          </div>
                          <p className="text-slate-600 text-sm line-clamp-2">{req.description}</p>
                        </div>
                        <div className="ml-4 flex items-center gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            className="gap-2 bg-gradient-to-r from-purple-50 to-pink-50 border-purple-200 hover:from-purple-100 hover:to-pink-100"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleAdvancedAI(req);
                            }}
                            disabled={isGenerating}
                          >
                            {isGenerating ? (
                              <>
                                <div className="animate-spin rounded-full h-3 w-3 border-2 border-purple-600 border-t-transparent" />
                                Analyzing...
                              </>
                            ) : (
                              <>
                                <Sparkles className="w-3 h-3 text-purple-600" />
                                AI Test Suite
                              </>
                            )}
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="gap-2 bg-gradient-to-r from-green-50 to-blue-50 border-green-200 hover:from-green-100 hover:to-blue-100"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleCreateTestCase(req);
                            }}
                            disabled={isGenerating}
                          >
                            {isGenerating ? (
                              <>
                                <div className="animate-spin rounded-full h-3 w-3 border-2 border-green-600 border-t-transparent" />
                                Generating...
                              </>
                            ) : (
                              <>
                                <TestTube className="w-3 h-3 text-green-600" />
                                Quick Test
                              </>
                            )}
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={(e) => handleDeleteClick(req, e)}
                            className="text-red-600 hover:text-red-700 hover:bg-red-50"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-2 mb-3">
                        {req.release_id ? (
                          <Badge variant="outline" className="text-green-600 border-green-300 bg-green-50">
                            {releases.find(r => r.id === req.release_id)?.name || req.release_id}
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="text-slate-500 border-slate-300">
                            No release assigned
                          </Badge>
                        )}
                        {req.source && (
                          <Badge variant="outline" className="text-slate-600 border-slate-300">
                            {req.source}
                          </Badge>
                        )}
                        {req.tags && req.tags.length > 0 && req.tags.map((tag, idx) => (
                          <Badge key={idx} variant="outline" className="text-blue-600 border-blue-300 bg-blue-50">
                            {tag}
                          </Badge>
                        ))}
                      </div>
                      {linkedTestCases.length > 0 && (
                        <div className="mt-3 pt-3 border-t border-slate-100">
                          <p className="text-xs text-slate-500 mb-1">Linked Test Cases ({linkedTestCases.length}):</p>
                          <div className="flex flex-wrap gap-1">
                            {linkedTestCases.slice(0, 3).map(tc => (
                              <Badge key={tc.id} variant="outline" className="text-xs gap-1">
                                <Hash className="w-2.5 h-2.5" />
                                {tc.id.substring(0, 6)} - {tc.title.length > 20 ? tc.title.substring(0, 20) + '...' : tc.title}
                              </Badge>
                            ))}
                            {linkedTestCases.length > 3 && (
                              <Badge variant="outline" className="text-xs">+{linkedTestCases.length - 3} more</Badge>
                            )}
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <RequirementDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        requirement={editingRequirement}
        onSubmit={handleSubmit}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />

      {selectedRequirement && (
        <TestCaseDialog
          open={testCaseDialogOpen}
          onOpenChange={(open) => {
            setTestCaseDialogOpen(open);
            if (!open) {
              setAiGeneratedData(null);
            }
          }}
          testCase={null}
          requirements={requirements}
          onSubmit={handleTestCaseSubmit}
          isLoading={createTestCaseMutation.isPending}
          aiGeneratedData={aiGeneratedData}
          preLinkedRequirementId={selectedRequirement.id}
        />
      )}

      <AdvancedAITestDialog
        open={advancedAIDialogOpen}
        onOpenChange={(open) => {
          setAdvancedAIDialogOpen(open);
          if (!open) {
            setAdvancedAISuggestions(null);
            setSelectedRequirement(null);
          }
        }}
        requirement={selectedRequirement}
        aiSuggestions={advancedAISuggestions}
        onGenerate={handleGenerateSelectedTests}
        isGenerating={generatingAI !== null}
        isCreating={creatingMultipleTests}
      />

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Requirement</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{requirementToDelete?.title}"? This action cannot be undone.
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
    </div>
  );
}
