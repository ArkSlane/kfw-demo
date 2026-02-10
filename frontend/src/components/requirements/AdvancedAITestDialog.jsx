import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Sparkles, CheckCircle2, XCircle, AlertTriangle, Loader2, Split } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function AdvancedAITestDialog({ open, onOpenChange, requirement, aiSuggestions, onGenerate, isGenerating, isCreating }) {
  const [selectedTests, setSelectedTests] = useState([]);

  useEffect(() => {
    if (aiSuggestions) {
      // Pre-select all tests by default
      const allTestIds = [
        ...(aiSuggestions.positive_tests?.map((_, idx) => `positive-${idx}`) || []),
        ...(aiSuggestions.negative_tests?.map((_, idx) => `negative-${idx}`) || [])
      ];
      setSelectedTests(allTestIds);
    }
  }, [aiSuggestions]);

  const toggleTest = (testId) => {
    setSelectedTests(prev =>
      prev.includes(testId)
        ? prev.filter(id => id !== testId)
        : [...prev, testId]
    );
  };

  const toggleAllPositive = () => {
    const positiveIds = aiSuggestions.positive_tests?.map((_, idx) => `positive-${idx}`) || [];
    const allSelected = positiveIds.every(id => selectedTests.includes(id));
    
    if (allSelected) {
      setSelectedTests(prev => prev.filter(id => !id.startsWith('positive-')));
    } else {
      setSelectedTests(prev => [...new Set([...prev, ...positiveIds])]);
    }
  };

  const toggleAllNegative = () => {
    const negativeIds = aiSuggestions.negative_tests?.map((_, idx) => `negative-${idx}`) || [];
    const allSelected = negativeIds.every(id => selectedTests.includes(id));
    
    if (allSelected) {
      setSelectedTests(prev => prev.filter(id => !id.startsWith('negative-')));
    } else {
      setSelectedTests(prev => [...new Set([...prev, ...negativeIds])]);
    }
  };

  const handleGenerate = () => {
    const selectedTestsData = {
      positive: [],
      negative: []
    };

    selectedTests.forEach(testId => {
      const [type, index] = testId.split('-');
      const idx = parseInt(index);

      if (type === 'positive' && aiSuggestions.positive_tests?.[idx]) {
        selectedTestsData.positive.push(aiSuggestions.positive_tests[idx]);
      } else if (type === 'negative' && aiSuggestions.negative_tests?.[idx]) {
        selectedTestsData.negative.push(aiSuggestions.negative_tests[idx]);
      }
    });

    onGenerate(selectedTestsData);
  };

  const getTestTypeColor = (type) => {
    if (type === 'positive') return 'bg-green-50 border-green-200';
    return 'bg-red-50 border-red-200';
  };

  const getTestTypeIcon = (type) => {
    if (type === 'positive') return <CheckCircle2 className="w-4 h-4 text-green-600" />;
    return <XCircle className="w-4 h-4 text-red-600" />;
  };

  const positiveCount = aiSuggestions?.positive_tests?.length || 0;
  const negativeCount = aiSuggestions?.negative_tests?.length || 0;
  const selectedPositive = selectedTests.filter(id => id.startsWith('positive-')).length;
  const selectedNegative = selectedTests.filter(id => id.startsWith('negative-')).length;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-purple-600" />
            AI Test Case Suggestions
            {requirement && (
              <Badge variant="outline" className="ml-2 text-xs">
                {requirement.title.length > 30 ? requirement.title.substring(0, 30) + '...' : requirement.title}
              </Badge>
            )}
          </DialogTitle>
        </DialogHeader>

        {isGenerating ? (
          <div className="flex-1 flex items-center justify-center py-12">
            <div className="text-center">
              <Loader2 className="w-12 h-12 animate-spin text-purple-600 mx-auto mb-4" />
              <p className="text-lg font-medium text-slate-900 mb-2">Analyzing requirement...</p>
              <p className="text-sm text-slate-600">Generating positive and negative test cases</p>
            </div>
          </div>
        ) : aiSuggestions ? (
          <>
            <div className="flex-1 overflow-y-auto">
              <Tabs defaultValue="positive" className="w-full">
                <TabsList className="grid w-full grid-cols-2 mb-4">
                  <TabsTrigger value="positive" className="gap-2">
                    <CheckCircle2 className="w-4 h-4" />
                    Positive Tests ({positiveCount})
                    {selectedPositive > 0 && (
                      <Badge variant="secondary" className="ml-1 text-xs">
                        {selectedPositive} selected
                      </Badge>
                    )}
                  </TabsTrigger>
                  <TabsTrigger value="negative" className="gap-2">
                    <XCircle className="w-4 h-4" />
                    Negative Tests ({negativeCount})
                    {selectedNegative > 0 && (
                      <Badge variant="secondary" className="ml-1 text-xs">
                        {selectedNegative} selected
                      </Badge>
                    )}
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="positive" className="space-y-3 mt-0">
                  <div className="flex items-center justify-between mb-3 p-3 bg-green-50 border border-green-200 rounded-lg">
                    <div>
                      <p className="text-sm font-medium text-green-900">Positive Test Cases</p>
                      <p className="text-xs text-green-700">These test cases validate expected behavior and happy paths</p>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={toggleAllPositive}
                      className="text-xs"
                    >
                      {selectedPositive === positiveCount ? 'Deselect All' : 'Select All'}
                    </Button>
                  </div>

                  {aiSuggestions.positive_tests?.map((test, idx) => (
                    <Card
                      key={`positive-${idx}`}
                      className={`border-2 cursor-pointer transition-all ${
                        selectedTests.includes(`positive-${idx}`)
                          ? 'border-green-500 bg-green-50'
                          : 'border-slate-200 hover:border-green-300'
                      }`}
                      onClick={() => toggleTest(`positive-${idx}`)}
                    >
                      <CardContent className="p-4">
                        <div className="flex items-start gap-3">
                          <Checkbox
                            checked={selectedTests.includes(`positive-${idx}`)}
                            onCheckedChange={() => toggleTest(`positive-${idx}`)}
                            className="mt-1"
                          />
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-2">
                              <CheckCircle2 className="w-4 h-4 text-green-600" />
                              <h4 className="font-semibold text-slate-900">{test.title}</h4>
                              <Badge variant="outline" className="text-xs">
                                {test.priority || 'medium'}
                              </Badge>
                            </div>
                            <p className="text-sm text-slate-600 mb-3">{test.description}</p>
                            
                            {test.steps && test.steps.length > 0 && (
                              <div className="mt-3 p-3 bg-white rounded border border-slate-200">
                                <p className="text-xs font-medium text-slate-700 mb-2">Test Steps ({test.steps.length}):</p>
                                <ol className="space-y-2">
                                  {test.steps.map((step, stepIdx) => (
                                    <li key={stepIdx} className="text-xs text-slate-600">
                                      <span className="font-medium">{step.step_number || stepIdx + 1}.</span> {step.action}
                                      {step.expected_result ? (
                                        <span className="text-slate-500">{' '}→ {step.expected_result}</span>
                                      ) : null}
                                    </li>
                                  ))}
                                </ol>
                              </div>
                            )}
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}

                  {positiveCount === 0 && (
                    <div className="text-center py-8 text-slate-500">
                      <Split className="w-12 h-12 mx-auto mb-3 opacity-30" />
                      <p>No positive test cases generated</p>
                    </div>
                  )}
                </TabsContent>

                <TabsContent value="negative" className="space-y-3 mt-0">
                  <div className="flex items-center justify-between mb-3 p-3 bg-red-50 border border-red-200 rounded-lg">
                    <div>
                      <p className="text-sm font-medium text-red-900">Negative Test Cases</p>
                      <p className="text-xs text-red-700">These test cases validate error handling and edge cases</p>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={toggleAllNegative}
                      className="text-xs"
                    >
                      {selectedNegative === negativeCount ? 'Deselect All' : 'Select All'}
                    </Button>
                  </div>

                  {aiSuggestions.negative_tests?.map((test, idx) => (
                    <Card
                      key={`negative-${idx}`}
                      className={`border-2 cursor-pointer transition-all ${
                        selectedTests.includes(`negative-${idx}`)
                          ? 'border-red-500 bg-red-50'
                          : 'border-slate-200 hover:border-red-300'
                      }`}
                      onClick={() => toggleTest(`negative-${idx}`)}
                    >
                      <CardContent className="p-4">
                        <div className="flex items-start gap-3">
                          <Checkbox
                            checked={selectedTests.includes(`negative-${idx}`)}
                            onCheckedChange={() => toggleTest(`negative-${idx}`)}
                            className="mt-1"
                          />
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-2">
                              <XCircle className="w-4 h-4 text-red-600" />
                              <h4 className="font-semibold text-slate-900">{test.title}</h4>
                              <Badge variant="outline" className="text-xs">
                                {test.priority || 'medium'}
                              </Badge>
                            </div>
                            <p className="text-sm text-slate-600 mb-3">{test.description}</p>
                            
                            {test.steps && test.steps.length > 0 && (
                              <div className="mt-3 p-3 bg-white rounded border border-slate-200">
                                <p className="text-xs font-medium text-slate-700 mb-2">Test Steps ({test.steps.length}):</p>
                                <ol className="space-y-2">
                                  {test.steps.map((step, stepIdx) => (
                                    <li key={stepIdx} className="text-xs text-slate-600">
                                      <span className="font-medium">{step.step_number || stepIdx + 1}.</span> {step.action}
                                      {step.expected_result ? (
                                        <span className="text-slate-500">{' '}→ {step.expected_result}</span>
                                      ) : null}
                                    </li>
                                  ))}
                                </ol>
                              </div>
                            )}
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}

                  {negativeCount === 0 && (
                    <div className="text-center py-8 text-slate-500">
                      <AlertTriangle className="w-12 h-12 mx-auto mb-3 opacity-30" />
                      <p>No negative test cases generated</p>
                    </div>
                  )}
                </TabsContent>
              </Tabs>
            </div>

            <DialogFooter className="border-t pt-4 mt-4">
              <div className="flex items-center justify-between w-full">
                <div className="text-sm text-slate-600">
                  <span className="font-medium">{selectedTests.length}</span> of {positiveCount + negativeCount} test cases selected
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isCreating}>
                    Cancel
                  </Button>
                  <Button
                    onClick={handleGenerate}
                    disabled={selectedTests.length === 0 || isCreating}
                    className="bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 gap-2"
                  >
                    {isCreating ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Creating {selectedTests.length} test case{selectedTests.length !== 1 ? 's' : ''}...
                      </>
                    ) : (
                      <>
                        <Sparkles className="w-4 h-4" />
                        Generate {selectedTests.length} Test Case{selectedTests.length !== 1 ? 's' : ''}
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </DialogFooter>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center py-12">
            <div className="text-center">
              <Sparkles className="w-12 h-12 text-purple-300 mx-auto mb-4" />
              <p className="text-slate-600">No suggestions available</p>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}