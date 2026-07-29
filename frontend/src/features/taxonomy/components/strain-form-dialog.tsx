"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
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
import { Textarea } from "@/shared/components/ui/textarea";

import { useCreateStrain, useUpdateStrain } from "../hooks/use-strains";
import type { Strain } from "../types";

// ── Schema ────────────────────────────────────────────────────────────────────

const formSchema = z.object({
  species_organism_id: z.string().min(1, "Species organism ID is required"),
  name: z.string().min(1, "Name is required"),
  ncbi_taxon_id: z.string().optional(),
  isolate: z.string().optional(),
  biosample_acc: z.string().optional(),
  assembly_acc: z.string().optional(),
  culture_collection: z.string().optional(),
  host_organism_id: z.string().optional(),
  metadata: z.string().optional(),
});

type FormValues = z.infer<typeof formSchema>;

// ── Defaults ──────────────────────────────────────────────────────────────────

const CREATE_DEFAULTS: FormValues = {
  species_organism_id: "",
  name: "",
  ncbi_taxon_id: "",
  isolate: "",
  biosample_acc: "",
  assembly_acc: "",
  culture_collection: "",
  host_organism_id: "",
  metadata: "",
};

function toFormValues(strain: Strain): FormValues {
  return {
    species_organism_id: strain.species_organism_id,
    name: strain.name,
    ncbi_taxon_id: strain.ncbi_taxon_id != null ? String(strain.ncbi_taxon_id) : "",
    isolate: strain.isolate ?? "",
    biosample_acc: strain.biosample_acc ?? "",
    assembly_acc: strain.assembly_acc ?? "",
    culture_collection: strain.culture_collection ?? "",
    host_organism_id: strain.host_organism_id ?? "",
    metadata: strain.metadata ? JSON.stringify(strain.metadata, null, 2) : "",
  };
}

// ── Props ─────────────────────────────────────────────────────────────────────

interface StrainFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Pass a strain to switch to edit mode. */
  strain?: Strain;
}

// ── Component ─────────────────────────────────────────────────────────────────

export function StrainFormDialog({ open, onOpenChange, strain }: StrainFormDialogProps) {
  const isEdit = !!strain;
  const createMutation = useCreateStrain();
  const updateMutation = useUpdateStrain();

  const isPending = isEdit ? updateMutation.isPending : createMutation.isPending;

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: CREATE_DEFAULTS,
  });

  // Reset form whenever the dialog opens or strain changes
  useEffect(() => {
    if (open) {
      form.reset(strain ? toFormValues(strain) : CREATE_DEFAULTS);
    }
  }, [open, strain, form]);

  const onSubmit = async (values: FormValues) => {
    // Parse metadata JSON if provided
    let parsedMetadata: Record<string, unknown> | undefined;
    if (values.metadata?.trim()) {
      try {
        parsedMetadata = JSON.parse(values.metadata.trim()) as Record<string, unknown>;
      } catch {
        form.setError("metadata", { message: "Invalid JSON — please check the syntax." });
        return;
      }
    }

    try {
      if (isEdit && strain) {
        await updateMutation.mutateAsync({
          strainId: strain.id,
          data: {
            name: values.name,
            ncbi_taxon_id: values.ncbi_taxon_id?.trim()
              ? Number(values.ncbi_taxon_id.trim())
              : undefined,
            isolate: values.isolate?.trim() || undefined,
            biosample_acc: values.biosample_acc?.trim() || undefined,
            assembly_acc: values.assembly_acc?.trim() || undefined,
            culture_collection: values.culture_collection?.trim() || undefined,
            host_organism_id: values.host_organism_id?.trim() || undefined,
            metadata: parsedMetadata ?? undefined,
          },
        });
      } else {
        await createMutation.mutateAsync({
          data: {
            species_organism_id: values.species_organism_id,
            name: values.name,
            ncbi_taxon_id: values.ncbi_taxon_id?.trim()
              ? Number(values.ncbi_taxon_id.trim())
              : undefined,
            isolate: values.isolate?.trim() || undefined,
            biosample_acc: values.biosample_acc?.trim() || undefined,
            assembly_acc: values.assembly_acc?.trim() || undefined,
            culture_collection: values.culture_collection?.trim() || undefined,
            host_organism_id: values.host_organism_id?.trim() || undefined,
            metadata: parsedMetadata ?? undefined,
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
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? "Edit Strain" : "New Strain"}</DialogTitle>
        </DialogHeader>

        <form onSubmit={form.handleSubmit(onSubmit)}>
          <div className="grid gap-5 py-4">
            {/* Species Organism ID — read-only in edit mode */}
            <div className="grid gap-2">
              <Label htmlFor="species_organism_id">
                Species organism{" "}
                {isEdit && (
                  <span className="text-muted-foreground font-normal text-xs">(read-only)</span>
                )}
              </Label>
              <Input
                id="species_organism_id"
                placeholder="paste an organism id (search picker — future)"
                aria-label="Species organism"
                disabled={isEdit}
                {...form.register("species_organism_id")}
              />
              {form.formState.errors.species_organism_id && (
                <p className="text-xs text-destructive">
                  {form.formState.errors.species_organism_id.message}
                </p>
              )}
            </div>

            {/* Name */}
            <div className="grid gap-2">
              <Label htmlFor="strain_name">Name</Label>
              <Input
                id="strain_name"
                placeholder="e.g. K-12"
                aria-label="Name"
                {...form.register("name")}
              />
              {form.formState.errors.name && (
                <p className="text-xs text-destructive">{form.formState.errors.name.message}</p>
              )}
            </div>

            {/* NCBI taxon id */}
            <div className="grid gap-2">
              <Label htmlFor="ncbi_taxon_id">
                NCBI taxon id{" "}
                <span className="text-muted-foreground font-normal text-xs">(optional)</span>
              </Label>
              <Input
                id="ncbi_taxon_id"
                type="number"
                placeholder="e.g. 83332"
                {...form.register("ncbi_taxon_id")}
              />
            </div>

            {/* Isolate */}
            <div className="grid gap-2">
              <Label htmlFor="isolate">
                Isolate{" "}
                <span className="text-muted-foreground font-normal text-xs">(optional)</span>
              </Label>
              <Input id="isolate" placeholder="e.g. MG1655" {...form.register("isolate")} />
            </div>

            {/* BioSample accession */}
            <div className="grid gap-2">
              <Label htmlFor="biosample_acc">
                BioSample accession{" "}
                <span className="text-muted-foreground font-normal text-xs">(optional)</span>
              </Label>
              <Input
                id="biosample_acc"
                placeholder="e.g. SAMN001"
                {...form.register("biosample_acc")}
              />
            </div>

            {/* Assembly accession */}
            <div className="grid gap-2">
              <Label htmlFor="assembly_acc">
                Assembly accession{" "}
                <span className="text-muted-foreground font-normal text-xs">(optional)</span>
              </Label>
              <Input
                id="assembly_acc"
                placeholder="e.g. GCF_000005845"
                {...form.register("assembly_acc")}
              />
            </div>

            {/* Culture collection */}
            <div className="grid gap-2">
              <Label htmlFor="culture_collection">
                Culture collection{" "}
                <span className="text-muted-foreground font-normal text-xs">(optional)</span>
              </Label>
              <Input
                id="culture_collection"
                placeholder="e.g. ATCC 10798"
                {...form.register("culture_collection")}
              />
            </div>

            {/* Host Organism ID */}
            <div className="grid gap-2">
              <Label htmlFor="host_organism_id">
                Host organism{" "}
                <span className="text-muted-foreground font-normal text-xs">(optional)</span>
              </Label>
              <Input
                id="host_organism_id"
                placeholder="paste an organism id (search picker — future)"
                {...form.register("host_organism_id")}
              />
            </div>

            {/* Metadata (JSON) */}
            <div className="grid gap-2">
              <Label htmlFor="metadata">
                Metadata{" "}
                <span className="text-muted-foreground font-normal text-xs">
                  (optional — JSON object)
                </span>
              </Label>
              <Textarea
                id="metadata"
                placeholder='e.g. {"source": "lab", "notes": "..."}'
                rows={4}
                className="font-mono text-xs"
                {...form.register("metadata")}
              />
              {form.formState.errors.metadata && (
                <p className="text-xs text-destructive">{form.formState.errors.metadata.message}</p>
              )}
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
                  : "Create Strain"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
