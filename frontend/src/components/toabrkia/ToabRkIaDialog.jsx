import React, { useEffect, useMemo, useState } from "react";

import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Checkbox } from "@/components/ui/checkbox";

export default function ToabRkIaDialog({
  open,
  onOpenChange,
  assessment,
  releases,
  onSubmit,
  isLoading,
}) {
  const [formData, setFormData] = useState({
    release_id: "",
    toab: {
      prefix: "",
      component_name: "",
      description: "",
    },
    rk: {
      internal_effects: "low",
      external_effects: "low",
      availability: "best_effort",
      complexity: "simple",
    },
    ia: {
      code_change: false,
      automated_test_intensity: "none",
      manual_test_intensity: "none",
      comments: "",
    },
  });

  useEffect(() => {
    if (assessment) {
      setFormData({
        release_id: assessment.release_id || "",
        toab: {
          prefix: assessment?.toab?.prefix || "",
          component_name: assessment?.toab?.component_name || "",
          description: assessment?.toab?.description || "",
        },
        rk: {
          internal_effects: assessment?.rk?.internal_effects || "low",
          external_effects: assessment?.rk?.external_effects || "low",
          availability: assessment?.rk?.availability || "best_effort",
          complexity: assessment?.rk?.complexity || "simple",
        },
        ia: {
          code_change: Boolean(assessment?.ia?.code_change),
          automated_test_intensity: assessment?.ia?.automated_test_intensity || "none",
          manual_test_intensity: assessment?.ia?.manual_test_intensity || "none",
          comments: assessment?.ia?.comments || "",
        },
      });
      return;
    }

    setFormData({
      release_id: "",
      toab: {
        prefix: "",
        component_name: "",
        description: "",
      },
      rk: {
        internal_effects: "low",
        external_effects: "low",
        availability: "best_effort",
        complexity: "simple",
      },
      ia: {
        code_change: false,
        automated_test_intensity: "none",
        manual_test_intensity: "none",
        comments: "",
      },
    });
  }, [assessment, open]);

  const releaseOptions = useMemo(() => {
    return (releases || []).map((r) => ({
      id: r.id,
      label: r.version ? `${r.name} (v${r.version})` : r.name,
    }));
  }, [releases]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.release_id) return;
    onSubmit(formData);
  };

  const isEdit = Boolean(assessment);

  const intensityOptions = ["none", "low", "medium", "high"];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader className="">
          <DialogTitle>{isEdit ? "Edit TOAB / RK / IA" : "New TOAB / RK / IA"}</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="release_id">Release *</Label>
            <Select
              value={formData.release_id}
              onValueChange={(value) => setFormData({ ...formData, release_id: value })}
              disabled={isEdit}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a release" />
              </SelectTrigger>
              <SelectContent>
                {releaseOptions.map((rel) => (
                  <SelectItem key={rel.id} value={rel.id}>
                    {rel.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-3">
            <p className="text-sm font-semibold text-slate-900">Testobjekt Abgrenzung</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label htmlFor="toab_prefix">Prefix</Label>
                <Input
                  id="toab_prefix"
                  value={formData.toab.prefix}
                  onChange={(e) => setFormData({ ...formData, toab: { ...formData.toab, prefix: e.target.value } })}
                  placeholder="e.g. AUTH"
                  autoComplete="off"
                />
              </div>
              <div>
                <Label htmlFor="toab_component_name">Component Name</Label>
                <Input
                  id="toab_component_name"
                  value={formData.toab.component_name}
                  onChange={(e) => setFormData({ ...formData, toab: { ...formData.toab, component_name: e.target.value } })}
                  placeholder="e.g. Login"
                  autoComplete="off"
                />
              </div>
            </div>
            <div>
              <Label htmlFor="toab_description">Description</Label>
              <Textarea
                id="toab_description"
                value={formData.toab.description}
                onChange={(e) => setFormData({ ...formData, toab: { ...formData.toab, description: e.target.value } })}
                placeholder="Describe test object scope and boundaries…"
                className="min-h-[120px]"
              />
            </div>
          </div>

          <div className="space-y-3">
            <p className="text-sm font-semibold text-slate-900">Risk Classification</p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <Label>Internal Effects</Label>
                <RadioGroup
                  value={formData.rk.internal_effects}
                  onValueChange={(value) => setFormData({ ...formData, rk: { ...formData.rk, internal_effects: value } })}
                >
                  {[
                    { value: "low", label: "Low" },
                    { value: "medium", label: "Medium" },
                    { value: "high", label: "High" },
                  ].map((opt) => {
                    const id = `rk_internal_${opt.value}`;
                    return (
                      <div key={opt.value} className="flex items-center space-x-2">
                        <RadioGroupItem id={id} value={opt.value} />
                        <Label htmlFor={id}>{opt.label}</Label>
                      </div>
                    );
                  })}
                </RadioGroup>
              </div>

              <div className="space-y-2">
                <Label>External Effects</Label>
                <RadioGroup
                  value={formData.rk.external_effects}
                  onValueChange={(value) => setFormData({ ...formData, rk: { ...formData.rk, external_effects: value } })}
                >
                  {[
                    { value: "low", label: "Low" },
                    { value: "medium", label: "Medium" },
                    { value: "high", label: "High" },
                  ].map((opt) => {
                    const id = `rk_external_${opt.value}`;
                    return (
                      <div key={opt.value} className="flex items-center space-x-2">
                        <RadioGroupItem id={id} value={opt.value} />
                        <Label htmlFor={id}>{opt.label}</Label>
                      </div>
                    );
                  })}
                </RadioGroup>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <Label>Availibility</Label>
                <RadioGroup
                  value={formData.rk.availability}
                  onValueChange={(value) => setFormData({ ...formData, rk: { ...formData.rk, availability: value } })}
                >
                  {[
                    { value: "99.9%", label: "99.9%" },
                    { value: "99%", label: "99%" },
                    { value: "best_effort", label: "Best effort" },
                  ].map((opt) => {
                    const id = `rk_availability_${opt.value.replace(/[^a-z0-9]/gi, "_")}`;
                    return (
                      <div key={opt.value} className="flex items-center space-x-2">
                        <RadioGroupItem id={id} value={opt.value} />
                        <Label htmlFor={id}>{opt.label}</Label>
                      </div>
                    );
                  })}
                </RadioGroup>
              </div>

              <div className="space-y-2">
                <Label>Complexity</Label>
                <RadioGroup
                  value={formData.rk.complexity}
                  onValueChange={(value) => setFormData({ ...formData, rk: { ...formData.rk, complexity: value } })}
                >
                  {[
                    { value: "simple", label: "Simple" },
                    { value: "moderate", label: "Moderate" },
                    { value: "complex", label: "Complex" },
                  ].map((opt) => {
                    const id = `rk_complexity_${opt.value}`;
                    return (
                      <div key={opt.value} className="flex items-center space-x-2">
                        <RadioGroupItem id={id} value={opt.value} />
                        <Label htmlFor={id}>{opt.label}</Label>
                      </div>
                    );
                  })}
                </RadioGroup>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <p className="text-sm font-semibold text-slate-900">Impact Analysis</p>

            <div className="flex items-center space-x-2">
              <Checkbox
                id="ia_code_change"
                checked={formData.ia.code_change}
                onCheckedChange={(checked) =>
                  setFormData({
                    ...formData,
                    ia: { ...formData.ia, code_change: Boolean(checked) },
                  })
                }
              />
              <Label htmlFor="ia_code_change">Code Change</Label>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Label>Automated Test Intensity</Label>
                <Select
                  value={formData.ia.automated_test_intensity}
                  onValueChange={(value) => setFormData({ ...formData, ia: { ...formData.ia, automated_test_intensity: value } })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {intensityOptions.map((v) => (
                      <SelectItem key={v} value={v}>
                        {v}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label>Manual Test Intensity</Label>
                <Select
                  value={formData.ia.manual_test_intensity}
                  onValueChange={(value) => setFormData({ ...formData, ia: { ...formData.ia, manual_test_intensity: value } })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {intensityOptions.map((v) => (
                      <SelectItem key={v} value={v}>
                        {v}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div>
              <Label htmlFor="ia_comments">Comments</Label>
              <Input
                id="ia_comments"
                value={formData.ia.comments}
                onChange={(e) => setFormData({ ...formData, ia: { ...formData.ia, comments: e.target.value } })}
                placeholder="Additional notes…"
                autoComplete="off"
              />
            </div>
          </div>

          <DialogFooter className="">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading || !formData.release_id} className="bg-blue-600 hover:bg-blue-700">
              {isLoading ? "Saving..." : isEdit ? "Update" : "Create"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
