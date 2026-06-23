"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/shared/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/shared/components/ui/collapsible";
import { DialogFooter } from "@/shared/components/ui/dialog";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";

import { useStartImport, useUploadEssentiality } from "../../hooks/use-imports";
import { OrganismCombobox } from "../organism-combobox";

const schema = z
  .object({
    organism_id: z.string().optional(),
    tax_id: z.string().optional(), // numeric text; coerced on submit
    gff_url: z.string().url("Enter a valid URL").optional().or(z.literal("")),
    essentiality_url: z.string().url("Enter a valid URL").optional().or(z.literal("")),
    essentiality_upload_ref: z.string().optional(),
    force: z.boolean(),
  })
  .refine((v) => Boolean(v.organism_id) !== Boolean(v.tax_id), {
    message: "Pick an organism OR enter a tax_id — exactly one.",
    path: ["organism_id"],
  });
type Values = z.infer<typeof schema>;

export function GeneEnrichmentForm({ onSuccess }: { onSuccess: () => void }) {
  const start = useStartImport();
  const upload = useUploadEssentiality();
  const [uploadName, setUploadName] = useState<string | null>(null);
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      organism_id: "",
      tax_id: "",
      gff_url: "",
      essentiality_url: "",
      essentiality_upload_ref: "",
      force: false,
    },
  });

  async function handleFile(file: File | undefined) {
    if (!file) return;
    // orval types the multipart body field `file` as `string` (FastAPI binary
    // quirk); the File works at runtime via FormData — cast to satisfy tsc.
    const res = await upload.mutateAsync({ data: { file: file as unknown as string } });
    form.setValue("essentiality_upload_ref", res.upload_ref);
    setUploadName(file.name);
  }

  const onSubmit = async (values: Values) => {
    const params: Record<string, unknown> = { force: values.force };
    if (values.organism_id) params.organism_id = values.organism_id;
    if (values.tax_id) params.tax_id = Number(values.tax_id);
    if (values.gff_url) params.gff_url = values.gff_url;
    if (values.essentiality_url) params.essentiality_url = values.essentiality_url;
    if (values.essentiality_upload_ref) {
      params.essentiality_upload_ref = values.essentiality_upload_ref;
    }
    try {
      await start.mutateAsync({ data: { import_type: "gene_enrichment", params } });
      onSuccess();
    } catch {
      // global mutation toast surfaces the error
    }
  };

  return (
    <form onSubmit={form.handleSubmit(onSubmit)}>
      <div className="grid gap-5 py-4">
        {/* Organism picker */}
        <div className="grid gap-2">
          <Label>Organism</Label>
          <Controller
            control={form.control}
            name="organism_id"
            render={({ field }) => <OrganismCombobox onSelect={(id) => field.onChange(id)} />}
          />
          {form.formState.errors.organism_id && (
            <p className="text-xs text-destructive">{form.formState.errors.organism_id.message}</p>
          )}
        </div>

        {/* Manual tax_id fallback */}
        <div className="grid gap-2">
          <Label htmlFor="tax_id">
            …or NCBI tax ID{" "}
            <span className="text-muted-foreground font-normal text-xs">(if not in the list)</span>
          </Label>
          <Input
            id="tax_id"
            type="number"
            min={1}
            placeholder="e.g. 83332"
            {...form.register("tax_id")}
          />
        </div>

        {/* Inline essentiality upload */}
        <div className="grid gap-2">
          <Label htmlFor="essentiality_file">
            Essentiality file{" "}
            <span className="text-muted-foreground font-normal text-xs">
              (.xlsx / .tsv, optional)
            </span>
          </Label>
          <Input
            id="essentiality_file"
            type="file"
            accept=".xlsx,.tsv,.txt"
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
          {upload.isPending && <p className="text-xs text-muted-foreground">Uploading…</p>}
          {uploadName && !upload.isPending && (
            <p className="text-xs text-green-600">Uploaded ✓ {uploadName}</p>
          )}
        </div>

        {/* Force */}
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" {...form.register("force")} /> Force re-import
        </label>

        {/* Advanced URLs */}
        <Collapsible>
          <CollapsibleTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="w-fit px-0 text-muted-foreground"
            >
              Advanced
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="grid gap-4 pt-3">
            <div className="grid gap-2">
              <Label htmlFor="gff_url">GFF URL</Label>
              <Input
                id="gff_url"
                placeholder="https://…/annotations.gff"
                {...form.register("gff_url")}
              />
              {form.formState.errors.gff_url && (
                <p className="text-xs text-destructive">{form.formState.errors.gff_url.message}</p>
              )}
            </div>
            <div className="grid gap-2">
              <Label htmlFor="essentiality_url">Essentiality URL</Label>
              <Input
                id="essentiality_url"
                placeholder="https://…/essentiality.tsv"
                {...form.register("essentiality_url")}
              />
              {form.formState.errors.essentiality_url && (
                <p className="text-xs text-destructive">
                  {form.formState.errors.essentiality_url.message}
                </p>
              )}
            </div>
          </CollapsibleContent>
        </Collapsible>
      </div>

      <DialogFooter>
        <Button type="submit" disabled={start.isPending || upload.isPending}>
          {start.isPending ? "Starting…" : "Start import"}
        </Button>
      </DialogFooter>
    </form>
  );
}
