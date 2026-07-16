"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/shared/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import type { PluginManifestResponse } from "@/shared/lib/api/model";

import { PluginParamForm } from "./plugin-param-form";
import { usePluginPreview, useStartPluginRun } from "./use-plugins";

type Values = Record<string, unknown>;

interface PluginRunPanelProps {
  manifest: PluginManifestResponse;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function num(v: unknown): number {
  return typeof v === "number" ? v : Number(v ?? 0) || 0;
}

export function PluginRunPanel({ manifest, open, onOpenChange }: PluginRunPanelProps) {
  const router = useRouter();
  const start = useStartPluginRun();
  const [values, setValues] = useState<Values>({});
  const [previewRunId, setPreviewRunId] = useState<string | null>(null);

  const preview = usePluginPreview(previewRunId);
  const summary =
    preview.data?.status === "succeeded" ? (preview.data.summary as Record<string, unknown>) : null;

  async function onPreview() {
    const run = await start.mutateAsync({
      pluginId: manifest.id,
      data: { params: values, dry_run: true },
    });
    setPreviewRunId(run.id);
  }

  async function onRun() {
    const run = await start.mutateAsync({
      pluginId: manifest.id,
      data: { params: values, dry_run: false },
    });
    onOpenChange(false);
    router.push(`/admin/imports/${run.id}`);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{manifest.name}</DialogTitle>
          <DialogDescription>{manifest.description}</DialogDescription>
        </DialogHeader>

        <PluginParamForm
          params={manifest.params}
          values={values}
          onChange={(next) => {
            setValues(next);
            setPreviewRunId(null); // params changed — stale preview
          }}
        />

        {previewRunId && !summary ? (
          <p className="text-sm text-muted-foreground animate-pulse">Previewing…</p>
        ) : null}
        {summary ? (
          <p className="text-sm">
            Preview: create {num(summary.created)} · update {num(summary.updated)} · skip{" "}
            {num(summary.skipped)} · fail {num(summary.failed)}
          </p>
        ) : null}

        <DialogFooter>
          <Button variant="outline" onClick={onPreview} disabled={start.isPending}>
            Preview
          </Button>
          <Button onClick={onRun} disabled={start.isPending}>
            Run
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
