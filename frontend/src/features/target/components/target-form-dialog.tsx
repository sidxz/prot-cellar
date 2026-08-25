"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/shared/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
import type { ComponentRelationship, TargetType } from "@/shared/lib/api/model";

import {
  TARGET_TYPE_LABELS,
  TargetComponentsEditor,
  cardinalityHint,
  componentCountValid,
  useCreateTarget,
  useUpdateTarget,
} from "@/features/target";
import type { Target, TargetComponentInput } from "@/features/target";

// ── Schema ────────────────────────────────────────────────────────────────────

const TARGET_TYPE_VALUES = [
  "single_protein",
  "domain",
  "protein_complex",
  "protein_family",
  "protein_protein_interaction",
  "nucleic_acid",
  "organism",
  "cell_line",
  "tissue",
  "unknown",
] as const;

const RELATIONSHIP_VALUES = [
  "single_protein",
  "protein_subunit",
  "family_member",
  "interacting_protein",
] as const;

const componentRowSchema = z.object({
  protein_id: z.string().min(1, "Protein ID is required"),
  relationship: z.enum(RELATIONSHIP_VALUES),
  // UI-only fields — stripped before sending to API
  accession: z.string().optional(),
  label: z.string().optional(),
  _key: z.number().optional(),
});

const formSchema = z
  .object({
    // Blank -> the API derives it from the component proteins.
    pref_name: z.string(),
    target_type: z.enum(TARGET_TYPE_VALUES),
    components: z.array(componentRowSchema),
    organism_id: z.string().optional(),
    chembl_id: z.string().optional(),
    pharmacological_class: z.string().optional(),
  })
  .superRefine((val, ctx) => {
    if (!componentCountValid(val.target_type as TargetType, val.components.length)) {
      ctx.addIssue({
        path: ["components"],
        code: "custom",
        message: cardinalityHint(val.target_type as TargetType),
      });
    }
  });

type FormValues = z.infer<typeof formSchema>;

// ── Defaults ──────────────────────────────────────────────────────────────────

const CREATE_DEFAULTS: FormValues = {
  pref_name: "",
  target_type: "single_protein",
  components: [{ protein_id: "", relationship: "single_protein", accession: "", _key: 0 }],
  organism_id: "",
  chembl_id: "",
  pharmacological_class: "",
};

function toFormValues(target: Target): FormValues {
  return {
    pref_name: target.pref_name,
    target_type: target.target_type as FormValues["target_type"],
    components: target.components.map((c, idx) => ({
      protein_id: c.protein_id,
      relationship: c.relationship as ComponentRelationship,
      accession: c.protein_id,
      label: c.protein_id,
      _key: idx,
    })),
    organism_id: target.organism_id ?? "",
    chembl_id: target.chembl_id ?? "",
    pharmacological_class: target.pharmacological_class ?? "",
  };
}

// ── Props ─────────────────────────────────────────────────────────────────────

interface TargetFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Pass a target to switch to edit mode. */
  target?: Target;
}

// ── Component ─────────────────────────────────────────────────────────────────

export function TargetFormDialog({ open, onOpenChange, target }: TargetFormDialogProps) {
  const isEdit = !!target;
  const createMutation = useCreateTarget();
  const updateMutation = useUpdateTarget();

  const isPending = isEdit ? updateMutation.isPending : createMutation.isPending;

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: CREATE_DEFAULTS,
  });

  // Reset form whenever the dialog opens or target changes
  useEffect(() => {
    if (open) {
      form.reset(target ? toFormValues(target) : CREATE_DEFAULTS);
    }
  }, [open, target, form]);

  const targetType = form.watch("target_type") as TargetType;

  const onSubmit = async (values: FormValues) => {
    // Strip UI-only fields from each component row
    const components = values.components.map(({ protein_id, relationship }) => ({
      protein_id,
      relationship,
    }));

    try {
      if (isEdit && target) {
        await updateMutation.mutateAsync({
          targetId: target.id,
          data: {
            pref_name: values.pref_name || undefined,
            target_type: values.target_type,
            components,
            organism_id: values.organism_id || undefined,
            chembl_id: values.chembl_id || undefined,
            pharmacological_class: values.pharmacological_class || undefined,
          },
        });
      } else {
        await createMutation.mutateAsync({
          data: {
            pref_name: values.pref_name || undefined,
            target_type: values.target_type,
            components,
            organism_id: values.organism_id || undefined,
            chembl_id: values.chembl_id || undefined,
            pharmacological_class: values.pharmacological_class || undefined,
          },
        });
      }
      onOpenChange(false);
    } catch {
      // Errors surface via the global mutation toast — do not add a second toast here.
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit Target" : "New Target"}</DialogTitle>
        </DialogHeader>

        <form onSubmit={form.handleSubmit(onSubmit)}>
          <div className="grid gap-5 py-4">
            {/* Preferred name */}
            <div className="grid gap-2">
              <Label htmlFor="pref_name">
                Preferred name
                {!isEdit && <span className="text-muted-foreground"> (optional)</span>}
              </Label>
              <Input
                id="pref_name"
                placeholder={isEdit ? "e.g. EGFR" : "Defaults to the component protein name"}
                aria-label="Preferred name"
                {...form.register("pref_name")}
              />
              {form.formState.errors.pref_name && (
                <p className="text-xs text-destructive">
                  {form.formState.errors.pref_name.message}
                </p>
              )}
            </div>

            {/* Target type */}
            <div className="grid gap-2">
              <Label htmlFor="target_type">Target type</Label>
              <Controller
                control={form.control}
                name="target_type"
                render={({ field }) => (
                  <Select
                    value={field.value}
                    onValueChange={(val) => {
                      field.onChange(val);
                      // Re-run validation so cardinality error updates immediately
                      void form.trigger("components");
                    }}
                  >
                    <SelectTrigger id="target_type" aria-label="Target type">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {(Object.entries(TARGET_TYPE_LABELS) as [TargetType, string][]).map(
                        ([key, label]) => (
                          <SelectItem key={key} value={key}>
                            {label}
                          </SelectItem>
                        ),
                      )}
                    </SelectContent>
                  </Select>
                )}
              />
              {form.formState.errors.target_type && (
                <p className="text-xs text-destructive">
                  {form.formState.errors.target_type.message}
                </p>
              )}
            </div>

            {/* Component editor */}
            <div className="grid gap-2">
              <Label>Protein components</Label>
              <Controller
                control={form.control}
                name="components"
                render={({ field }) => (
                  <TargetComponentsEditor
                    value={field.value as TargetComponentInput[]}
                    onChange={field.onChange}
                    targetType={targetType}
                  />
                )}
              />
              {form.formState.errors.components &&
                !Array.isArray(form.formState.errors.components) && (
                  <p className="text-xs text-destructive">
                    {(form.formState.errors.components as { message?: string }).message}
                  </p>
                )}
            </div>

            {/* Organism ID */}
            <div className="grid gap-2">
              <Label htmlFor="organism_id">
                Organism ID{" "}
                <span className="text-muted-foreground font-normal text-xs">
                  (optional — picker in Plan 3)
                </span>
              </Label>
              <Input
                id="organism_id"
                placeholder="e.g. organism UUID"
                {...form.register("organism_id")}
              />
            </div>

            {/* ChEMBL ID */}
            <div className="grid gap-2">
              <Label htmlFor="chembl_id">
                ChEMBL ID{" "}
                <span className="text-muted-foreground font-normal text-xs">(optional)</span>
              </Label>
              <Input id="chembl_id" placeholder="e.g. CHEMBL203" {...form.register("chembl_id")} />
            </div>

            {/* Pharmacological class */}
            <div className="grid gap-2">
              <Label htmlFor="pharmacological_class">
                Pharmacological class{" "}
                <span className="text-muted-foreground font-normal text-xs">(optional)</span>
              </Label>
              <Input
                id="pharmacological_class"
                placeholder="e.g. Kinase inhibitor"
                {...form.register("pharmacological_class")}
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isPending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isPending || form.formState.isSubmitting}>
              {isPending
                ? isEdit
                  ? "Saving…"
                  : "Creating…"
                : isEdit
                  ? "Save Changes"
                  : "Create Target"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
