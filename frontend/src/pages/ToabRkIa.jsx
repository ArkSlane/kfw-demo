import React, { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { releasesAPI } from "@/api/releasesClient";
import { releaseAssessmentsAPI } from "@/api/releaseAssessmentsClient";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Filter, FileText, Plus, Trash2 } from "lucide-react";

import ToabRkIaDialog from "@/components/toabrkia/ToabRkIaDialog";
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

export default function ToabRkIa() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingAssessment, setEditingAssessment] = useState(null);
  const [filterRelease, setFilterRelease] = useState("all");
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [assessmentToDelete, setAssessmentToDelete] = useState(null);

  const queryClient = useQueryClient();

  const { data: releases = [] } = useQuery({
    queryKey: ["releases"],
    queryFn: () => releasesAPI.list(),
    initialData: [],
  });

  const { data: assessments = [], isLoading } = useQuery({
    queryKey: ["releaseAssessments"],
    queryFn: () => releaseAssessmentsAPI.list(),
    initialData: [],
  });

  const filteredAssessments = useMemo(() => {
    if (filterRelease === "all") return assessments;
    return (assessments || []).filter((a) => a.release_id === filterRelease);
  }, [assessments, filterRelease]);

  const releaseById = useMemo(() => {
    const map = new Map();
    for (const r of releases || []) map.set(r.id, r);
    return map;
  }, [releases]);

  const upsertMutation = useMutation({
    mutationFn: (vars) => {
      const v = /** @type {any} */ (vars);
      return releaseAssessmentsAPI.upsertByRelease(v.releaseId, v.payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["releaseAssessments"] });
      setDialogOpen(false);
      setEditingAssessment(null);
      toast.success("Saved TOAB / RK / IA");
    },
    onError: (error) => {
      console.error(error);
      toast.error("Failed to save TOAB / RK / IA");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (assessmentId) => releaseAssessmentsAPI.delete(assessmentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["releaseAssessments"] });
      toast.success("Deleted TOAB / RK / IA");
      setDeleteDialogOpen(false);
      setAssessmentToDelete(null);
    },
    onError: (error) => {
      console.error(error);
      toast.error("Failed to delete TOAB / RK / IA");
    },
  });

  const handleDeleteClick = (assessment, e) => {
    e.stopPropagation();
    setAssessmentToDelete(assessment);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = () => {
    if (!assessmentToDelete?.id) return;
    deleteMutation.mutate(assessmentToDelete.id);
  };

  const handleSubmit = (data) => {
    upsertMutation.mutate(
      /** @type {any} */ ({
        releaseId: data.release_id,
        payload: { toab: data.toab, rk: data.rk, ia: data.ia },
      })
    );
  };

  return (
    <div className="p-6 lg:p-8 space-y-6">
      <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 mb-2">TOAB / RK / IA</h1>
          <p className="text-slate-600">Test Objekt Abgrenzung, Risiko Klassifizierung, Impact Analyse per Release</p>
        </div>
        <Button
          onClick={() => {
            setEditingAssessment(null);
            setDialogOpen(true);
          }}
          className="bg-blue-600 hover:bg-blue-700 gap-2"
        >
          <Plus className="w-4 h-4" />
          Create
        </Button>
      </div>

      <Card className="border-none shadow-md">
        <CardHeader className="border-b border-slate-100">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <CardTitle className="text-lg font-semibold">All TOAB / RK / IA</CardTitle>
            <div className="flex items-center gap-3 flex-wrap">
              <div className="flex items-center gap-2">
                <Filter className="w-4 h-4 text-slate-600" />
                <Select value={filterRelease} onValueChange={setFilterRelease}>
                  <SelectTrigger className="w-[220px]">
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
          ) : filteredAssessments.length === 0 ? (
            <div className="text-center py-12">
              <FileText className="w-16 h-16 mx-auto mb-4 text-slate-300" />
              <p className="text-slate-500 mb-4">No TOAB / RK / IA entries found</p>
              <Button
                onClick={() => {
                  setEditingAssessment(null);
                  setDialogOpen(true);
                }}
                variant="outline"
              >
                <Plus className="w-4 h-4 mr-2" />
                Create your first entry
              </Button>
            </div>
          ) : (
            <div className="grid gap-4">
              {filteredAssessments.map((a) => {
                const rel = releaseById.get(a.release_id);
                const relLabel = rel ? `${rel.name}${rel.version ? ` (v${rel.version})` : ""}` : a.release_id;
                const updatedLabel = a.updated_at ? new Date(a.updated_at).toLocaleString() : null;

                const pretty = (v) => {
                  if (!v) return "—";
                  const s = String(v);
                  return s
                    .replace(/_/g, " ")
                    .replace(/^\w/, (c) => c.toUpperCase());
                };

                const toabTitle = (() => {
                  const prefix = a?.toab?.prefix ? `${a.toab.prefix}` : "";
                  const comp = a?.toab?.component_name ? `${a.toab.component_name}` : "";
                  const both = [prefix, comp].filter(Boolean).join(" - ");
                  return both || "TOAB";
                })();

                const rkInternal = pretty(a?.rk?.internal_effects);
                const rkExternal = pretty(a?.rk?.external_effects);
                const rkAvail = pretty(a?.rk?.availability);
                const rkComplexity = pretty(a?.rk?.complexity);

                const iaAuto = pretty(a?.ia?.automated_test_intensity);
                const iaManual = pretty(a?.ia?.manual_test_intensity);
                const iaCodeChange = a?.ia?.code_change ? "Yes" : "No";

                return (
                  <Card
                    key={a.id}
                    className="border border-slate-200 hover:shadow-lg transition-all cursor-pointer"
                    onClick={() => {
                      setEditingAssessment(a);
                      setDialogOpen(true);
                    }}
                  >
                    <CardContent className="p-6 space-y-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <h3 className="text-lg font-semibold text-slate-900 leading-tight line-clamp-1">{toabTitle}</h3>
                          <div className="flex items-center gap-2 mt-1">
                            <p className="text-sm text-slate-600">{relLabel}</p>
                          </div>
                          <p className="text-sm text-slate-600 mt-2 line-clamp-3">{a?.toab?.description || "—"}</p>
                        </div>

                        <div className="flex flex-col items-end gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            className="gap-2"
                            onClick={(e) => handleDeleteClick(a, e)}
                            disabled={deleteMutation.isPending}
                            title="Delete"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                          {updatedLabel ? <p className="text-xs text-slate-500">Updated: {updatedLabel}</p> : null}
                        </div>
                      </div>

                      <div className="grid gap-4 md:grid-cols-2">
                        <div className="space-y-2">
                          <p className="text-xs font-semibold text-slate-900">Risk Classification</p>
                          <div className="flex flex-wrap gap-2">
                            <Badge variant="outline" className="text-xs border-slate-200 bg-sky-50 text-sky-900">
                              Internal: {rkInternal}
                            </Badge>
                            <Badge variant="outline" className="text-xs border-slate-200 bg-amber-50 text-amber-900">
                              External: {rkExternal}
                            </Badge>
                            <Badge variant="outline" className="text-xs border-slate-200 bg-emerald-50 text-emerald-900">
                              Availability: {rkAvail}
                            </Badge>
                            <Badge variant="outline" className="text-xs border-slate-200 bg-violet-50 text-violet-900">
                              Complexity: {rkComplexity}
                            </Badge>
                          </div>
                        </div>

                        <div className="space-y-2">
                          <p className="text-xs font-semibold text-slate-900">Impact Analysis</p>
                          <div className="flex flex-wrap gap-2">
                            <Badge
                              variant="outline"
                              className={
                                a?.ia?.code_change
                                  ? "text-xs border-slate-200 bg-rose-50 text-rose-900"
                                  : "text-xs border-slate-200 bg-slate-50 text-slate-900"
                              }
                            >
                              Code change: {iaCodeChange}
                            </Badge>
                            <Badge variant="outline" className="text-xs border-slate-200 bg-indigo-50 text-indigo-900">
                              Automated: {iaAuto}
                            </Badge>
                            <Badge variant="outline" className="text-xs border-slate-200 bg-teal-50 text-teal-900">
                              Manual: {iaManual}
                            </Badge>
                          </div>
                          {a?.ia?.comments ? (
                            <p className="text-sm text-slate-600 line-clamp-2">{a.ia.comments}</p>
                          ) : (
                            <p className="text-sm text-slate-600">—</p>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <AlertDialog
        open={deleteDialogOpen}
        onOpenChange={(next) => {
          setDeleteDialogOpen(next);
          if (!next) setAssessmentToDelete(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete TOAB / RK / IA?</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setAssessmentToDelete(null)}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteConfirm}
              disabled={deleteMutation.isPending}
              className="bg-red-600 hover:bg-red-700"
            >
              {deleteMutation.isPending ? "Deleting..." : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <ToabRkIaDialog
        open={dialogOpen}
        onOpenChange={(next) => {
          setDialogOpen(next);
          if (!next) setEditingAssessment(null);
        }}
        assessment={editingAssessment}
        releases={releases}
        onSubmit={handleSubmit}
        isLoading={upsertMutation.isPending}
      />
    </div>
  );
}
