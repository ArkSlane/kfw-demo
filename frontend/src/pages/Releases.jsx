// frontend/src/pages/Releases.jsx
import React, { useState } from "react";
import { releasesAPI } from "@/api/releasesClient";
import { requirementsAPI } from "@/api/requirementsClient";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Plus, Package, Calendar, Trash2 } from "lucide-react";
import ReleaseDialog from "../components/releases/ReleaseDialog";
import { format } from "date-fns";
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

export default function Releases() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingRelease, setEditingRelease] = useState(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [releaseToDelete, setReleaseToDelete] = useState(null);
  const queryClient = useQueryClient();

  const { data: releases, isLoading } = useQuery({
    queryKey: ['releases'],
    queryFn: () => releasesAPI.list(),
    initialData: [],
    retry: 1,
  });

  const { data: requirements = [] } = useQuery({
    queryKey: ['requirements'],
    queryFn: () => requirementsAPI.list(),
    initialData: [],
    retry: 1,
  });

  const createMutation = useMutation({
    mutationFn: (data) => releasesAPI.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['releases'] });
      setDialogOpen(false);
      setEditingRelease(null);
      toast.success('Release created successfully!');
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to create release');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => releasesAPI.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['releases'] });
      setDialogOpen(false);
      setEditingRelease(null);
      toast.success('Release updated successfully!');
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to update release');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id) => releasesAPI.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['releases'] });
      toast.success('Release deleted successfully!');
      setDeleteDialogOpen(false);
      setReleaseToDelete(null);
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Failed to delete release');
    },
  });

  const handleSubmit = (data) => {
    if (editingRelease) {
      updateMutation.mutate({ id: editingRelease.id, data });
    } else {
      createMutation.mutate(data);
    }
  };

  const handleEdit = (release) => {
    setEditingRelease(release);
    setDialogOpen(true);
  };

  const handleDeleteClick = (release, e) => {
    e.stopPropagation();
    setReleaseToDelete(release);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = () => {
    if (releaseToDelete) {
      deleteMutation.mutate(releaseToDelete.id);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return null;
    try {
      return format(new Date(dateString), 'MMM d, yyyy');
    } catch {
      return dateString;
    }
  };

  const getRequirementsByIds = (ids) => {
    return requirements.filter(req => ids.includes(req.id));
  };

  return (
    <div className="p-6 lg:p-8 space-y-6">
      <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 mb-2">Releases</h1>
          <p className="text-slate-600">Manage product releases and versions</p>
        </div>
        <Button 
          onClick={() => {
            setEditingRelease(null);
            setDialogOpen(true);
          }}
          className="bg-blue-600 hover:bg-blue-700 gap-2"
        >
          <Plus className="w-4 h-4" />
          New Release
        </Button>
      </div>

      <Card className="border-none shadow-md">
        <CardHeader className="border-b border-slate-100">
          <CardTitle className="text-lg font-semibold">All Releases</CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          {isLoading ? (
            <div className="text-center py-12 text-slate-500">Loading...</div>
          ) : releases.length === 0 ? (
            <div className="text-center py-12">
              <Package className="w-16 h-16 mx-auto mb-4 text-slate-300" />
              <p className="text-slate-500 mb-4">No releases found</p>
              <Button onClick={() => setDialogOpen(true)} variant="outline">
                <Plus className="w-4 h-4 mr-2" />
                Create your first release
              </Button>
            </div>
          ) : (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {releases.map((release) => {
                const releaseRequirements = getRequirementsByIds(release.requirement_ids || []);
                return (
                  <Card 
                    key={release.id}
                    className="border border-slate-200 hover:shadow-lg transition-all cursor-pointer group relative"
                  >
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={(e) => handleDeleteClick(release, e)}
                      className="absolute top-2 right-2 text-red-600 hover:text-red-700 hover:bg-red-50 opacity-0 group-hover:opacity-100 transition-opacity z-10"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                    <CardContent className="p-6" onClick={() => handleEdit(release)}>
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex items-center gap-2">
                          <Package className="w-8 h-8 text-blue-600" />
                          <div>
                            <h3 className="text-lg font-semibold text-slate-900 group-hover:text-blue-600 transition-colors">
                              {release.name}
                            </h3>
                          </div>
                        </div>
                      </div>
                      
                      {release.description && (
                        <p className="text-sm text-slate-600 mb-3 line-clamp-2">{release.description}</p>
                      )}

                      <div className="space-y-2 mb-3">
                        {(release.requirement_ids?.length > 0 || release.testcase_ids?.length > 0) && (
                          <>
                            {release.requirement_ids?.length > 0 && (
                              <div className="text-sm">
                                <span className="text-slate-600 font-medium">Requirements:</span>
                                <div className="mt-1 space-y-1">
                                  {releaseRequirements.slice(0, 2).map(req => (
                                    <div key={req.id} className="text-xs text-slate-500 truncate">
                                      • {req.title}
                                    </div>
                                  ))}
                                  {releaseRequirements.length > 2 && (
                                    <div className="text-xs text-slate-400">
                                      +{releaseRequirements.length - 2} more
                                    </div>
                                  )}
                                </div>
                              </div>
                            )}
                            {release.testcase_ids?.length > 0 && (
                              <div className="text-sm">
                                <span className="text-slate-600 font-medium">Test Cases:</span>
                                <div className="text-xs text-slate-500">
                                  {release.testcase_ids.length} associated
                                </div>
                              </div>
                            )}
                          </>
                        )}
                      </div>

                      {(release.from_date || release.to_date) && (
                        <div className="mt-3 pt-3 border-t border-slate-100 flex items-center gap-2 text-xs text-slate-500">
                          <Calendar className="w-3 h-3" />
                          <span>
                            {formatDate(release.from_date)} - {formatDate(release.to_date)}
                          </span>
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

      <ReleaseDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        release={editingRelease}
        onSubmit={handleSubmit}
        isLoading={createMutation.isPending || updateMutation.isPending}
      />

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Release</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{releaseToDelete?.name}"? This action cannot be undone.
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