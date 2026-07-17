"use client";

import { zodResolver } from "@hookform/resolvers/zod";
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

import { useStartImport } from "../../hooks/use-imports";
import { OrganismCombobox } from "../organism-combobox";

// Essentiality is ingested via the DeJesus plugin (Admin → Plugins), not here —
// gene enrichment only sets genomic location + functional category from the GFF.
const schema = z
  .object({
    organism_id: z.string().optional(),
    tax_id: z.string().optional(), // numeric text; coerced on submit
    gff_url: z.string().url("Enter a valid URL").optional().or(z.literal("")),
    force: z.boolean(),
  })
  .refine((v) => Boolean(v.organism_id) !== Boolean(v.tax_id), {
    message: "Pick an organism OR enter a tax_id — exactly one.",
    path: ["organism_id"],
  });
type Values = z.infer<typeof schema>;

export function GeneEnrichmentForm({ onSuccess }: { onSuccess: () => void }) {
  const start = useStartImport();
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      organism_id: "",
      tax_id: "",
      gff_url: "",
      force: false,
    },
  });

  const onSubmit = async (values: Values) => {
    const params: Record<string, unknown> = { force: values.force };
    if (values.organism_id) params.organism_id = values.organism_id;
    if (values.tax_id) params.tax_id = Number(values.tax_id);
    if (values.gff_url) params.gff_url = values.gff_url;
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

        {/* Force */}
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" {...form.register("force")} /> Force re-import
        </label>

        {/* Advanced */}
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
          </CollapsibleContent>
        </Collapsible>
      </div>

      <DialogFooter>
        <Button type="submit" disabled={start.isPending}>
          {start.isPending ? "Starting…" : "Start import"}
        </Button>
      </DialogFooter>
    </form>
  );
}
