"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";

import { RECORD_KINDS, humanize } from "@/features/extension-fields/types";
import { useTargetBiologySchema } from "@/features/protein-catalog/hooks/use-target-biology-schema";
import { Button } from "@/shared/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/shared/components/ui/collapsible";
import { DialogFooter } from "@/shared/components/ui/dialog";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
import { ImportType } from "@/shared/lib/api/model";

import { useStartImport, useUploadEssentiality } from "../../hooks/use-imports";
import { OrganismCombobox } from "../organism-combobox";

const schema = z.object({
  upload_ref: z.string().min(1, "Upload a workbook first"),
  organism_id: z.string().min(1, "Organism is required"),
  match_by: z.enum(["locus_tag", "gene_name"]),
  update_existing: z.boolean(),
});
type Values = z.infer<typeof schema>;

/**
 * A target-biology workbook import always starts as a preview: `dry_run` is
 * never a field on this form, only ever `true` on submit (see
 * TargetBiologyPreview for the separate, explicit Apply action that flips it
 * to `false` on the same upload).
 */
export function TargetBiologyParamsForm({ onSuccess }: { onSuccess: () => void }) {
  const router = useRouter();
  const start = useStartImport();
  const upload = useUploadEssentiality(ImportType.target_biology);
  const { data: schemaData } = useTargetBiologySchema();
  const [fileName, setFileName] = useState<string | null>(null);

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      upload_ref: "",
      organism_id: "",
      match_by: "locus_tag",
      update_existing: false,
    },
  });

  async function handleFile(file: File | undefined) {
    if (!file) return;
    setFileName(file.name);
    // orval types the multipart body field `file` as string; cast to satisfy tsc.
    const res = await upload.mutateAsync({ data: { file: file as unknown as string } });
    form.setValue("upload_ref", res.upload_ref, { shouldValidate: true });
  }

  const onSubmit = async (values: Values) => {
    const params = {
      upload_ref: values.upload_ref,
      organism_id: values.organism_id,
      match_by: values.match_by,
      update_existing: values.update_existing,
      dry_run: true, // this form only ever previews — see the doc comment above
    };
    try {
      const run = await start.mutateAsync({
        data: { import_type: ImportType.target_biology, params },
      });
      onSuccess();
      router.push(`/admin/imports/${run.id}`);
    } catch {
      // global mutation toast surfaces the error
    }
  };

  const matchBy = form.watch("match_by");
  const busy = start.isPending || upload.isPending;

  return (
    <form onSubmit={form.handleSubmit(onSubmit)}>
      <div className="grid gap-5 py-4">
        <div className="grid gap-2">
          <Label htmlFor="workbook">Workbook</Label>
          <Input
            id="workbook"
            type="file"
            accept=".xlsx"
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
          {fileName && <p className="text-xs text-muted-foreground">{fileName}</p>}
          {form.formState.errors.upload_ref && (
            <p className="text-xs text-destructive">{form.formState.errors.upload_ref.message}</p>
          )}
        </div>

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

        <div className="grid gap-2">
          <Label htmlFor="match_by">Match genes by</Label>
          <Controller
            control={form.control}
            name="match_by"
            render={({ field }) => (
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger id="match_by" aria-label="Match genes by">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="locus_tag">Locus tag</SelectItem>
                  <SelectItem value="gene_name">Gene name</SelectItem>
                </SelectContent>
              </Select>
            )}
          />
        </div>

        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" {...form.register("update_existing")} />
          Update existing records (instead of only adding)
        </label>

        <Collapsible>
          <CollapsibleTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="w-fit px-0 text-muted-foreground"
            >
              Expected columns
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="grid gap-2 pt-3">
            <p className="text-xs text-muted-foreground">
              One sheet per kind, sheet name = kind. A gene-side sheet also needs a{" "}
              <span className="font-mono">{matchBy}</span> column; a protein-side sheet identifies
              rows by <span className="font-mono">accession</span>.
            </p>
            <div className="grid max-h-48 gap-1.5 overflow-y-auto text-xs">
              {RECORD_KINDS.map((kind) => {
                const descriptor = schemaData?.kinds[kind];
                const columns = [
                  ...(descriptor?.fields ?? []),
                  ...(descriptor?.extension_fields ?? []),
                ];
                return (
                  <div key={kind}>
                    <span className="font-medium">{descriptor?.label ?? humanize(kind)}</span>
                    {columns.length > 0 && (
                      <span className="text-muted-foreground">
                        {" — "}
                        {columns.map((c) => `${c.name} (${c.type})`).join(", ")}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </CollapsibleContent>
        </Collapsible>
      </div>
      <DialogFooter>
        <Button type="submit" disabled={busy}>
          {start.isPending ? "Starting…" : upload.isPending ? "Uploading…" : "Start import"}
        </Button>
      </DialogFooter>
    </form>
  );
}
