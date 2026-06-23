"use client";

import { useForm } from "react-hook-form";

import { Button } from "@/shared/components/ui/button";
import { DialogFooter } from "@/shared/components/ui/dialog";

import { useStartImport } from "../../hooks/use-imports";

export function GoOntologyForm({ onSuccess }: { onSuccess: () => void }) {
  const start = useStartImport();
  const { register, handleSubmit } = useForm<{ force: boolean }>({
    defaultValues: { force: false },
  });

  const onSubmit = async (values: { force: boolean }) => {
    try {
      await start.mutateAsync({
        data: { import_type: "go_ontology", params: { force: values.force } },
      });
      onSuccess();
    } catch {
      // global mutation toast surfaces the error
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <div className="grid gap-5 py-4">
        <p className="text-sm text-muted-foreground">
          Imports the Gene Ontology graph. Enable "force" to re-import even when already current.
        </p>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" {...register("force")} /> Force re-import
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
