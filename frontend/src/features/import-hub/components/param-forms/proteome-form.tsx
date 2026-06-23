"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/shared/components/ui/button";
import { DialogFooter } from "@/shared/components/ui/dialog";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";

import { useStartImport } from "../../hooks/use-imports";

const schema = z.object({
  proteome_id: z.string().min(1, "Proteome ID is required"),
  force: z.boolean(),
  dry_run: z.boolean(),
  limit: z.string().optional(), // numeric text; coerced on submit
});
type Values = z.infer<typeof schema>;

export function ProteomeForm({ onSuccess }: { onSuccess: () => void }) {
  const start = useStartImport();
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { proteome_id: "", force: false, dry_run: false, limit: "" },
  });

  const onSubmit = async (values: Values) => {
    const params = {
      proteome_id: values.proteome_id.trim(),
      force: values.force,
      dry_run: values.dry_run,
      limit: values.limit ? Number(values.limit) : null,
    };
    try {
      await start.mutateAsync({ data: { import_type: "proteome", params } });
      onSuccess();
    } catch {
      // global mutation toast surfaces the error
    }
  };

  return (
    <form onSubmit={form.handleSubmit(onSubmit)}>
      <div className="grid gap-5 py-4">
        <div className="grid gap-2">
          <Label htmlFor="proteome_id">UniProt proteome ID</Label>
          <Input id="proteome_id" placeholder="e.g. UP000001584" {...form.register("proteome_id")} />
          {form.formState.errors.proteome_id && (
            <p className="text-xs text-destructive">{form.formState.errors.proteome_id.message}</p>
          )}
        </div>
        <div className="grid gap-2">
          <Label htmlFor="prot_limit">
            Limit <span className="text-muted-foreground font-normal text-xs">(optional)</span>
          </Label>
          <Input id="prot_limit" type="number" min={1} placeholder="All" {...form.register("limit")} />
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" {...form.register("force")} /> Force re-import
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" {...form.register("dry_run")} /> Dry run (no writes)
        </label>
      </div>
      <DialogFooter>
        <Button type="submit" disabled={start.isPending}>
          {start.isPending ? "Starting…" : "Start import"}
        </Button>
      </DialogFooter>
    </form>
  );
}
