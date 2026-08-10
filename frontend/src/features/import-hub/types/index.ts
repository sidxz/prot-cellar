import type { ComponentProps } from "react";

import type { Badge } from "@/shared/components/ui/badge";
import { ImportStatus, ImportType } from "@/shared/lib/api/model";
import type { ImportRunResponse, StartImportBody, UploadResponse } from "@/shared/lib/api/model";

/** Narrowed alias — one import run (list row or detail). */
export type ImportRun = ImportRunResponse;

export type { StartImportBody, UploadResponse };
export { ImportStatus, ImportType };

/** Badge variant union, derived from the Badge component's own prop type. */
export type BadgeVariant = NonNullable<ComponentProps<typeof Badge>["variant"]>;

/** Human-readable labels for the 5 import types. */
export const IMPORT_TYPE_LABELS: Record<ImportType, string> = {
  [ImportType.proteome]: "Proteome",
  [ImportType.gene_enrichment]: "Gene enrichment",
  [ImportType.go_ontology]: "GO ontology",
  [ImportType.plugin]: "Plugin",
  [ImportType.target_biology]: "Target biology",
};

// ---------------------------------------------------------------------------
// Target-biology apply memory
// ---------------------------------------------------------------------------
//
// GET /imports/{id} (ImportRunResponse) never echoes back the params a run
// was started with — id/import_type/target_key/status/phase/progress/summary/
// error/upload_ref/timestamps only. Applying a previewed target-biology run
// must resubmit the exact organism_id/match_by/update_existing it was
// previewed with (only dry_run flips) — reusing the wrong ones would silently
// apply something other than what was previewed, the same class of silent
// mismatch this whole import type exists to close. `upload_ref` doesn't need
// remembering (it's already on the run response); these three do, so they're
// stashed here, client-side, keyed by the run they belong to, at the moment
// the preview is created.
//
// ponytail: localStorage, not a backend field — survives reload/reopen in
// this browser but not a different one or a cleared one. When it's gone,
// target-biology-preview.tsx says so and points at "New import" rather than
// guessing at settings it can't know. Upgrade path: add `params` to
// ImportRunResponse (backend, out of Task 6's scope).
export interface TargetBiologyApplyParams {
  organism_id: string;
  match_by: "locus_tag" | "gene_name";
  update_existing: boolean;
}

function targetBiologyApplyKey(runId: string): string {
  return `pc-target-biology-apply:${runId}`;
}

export function saveTargetBiologyApplyParams(
  runId: string,
  params: TargetBiologyApplyParams,
): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(targetBiologyApplyKey(runId), JSON.stringify(params));
  } catch {
    // storage full/unavailable — the preview falls back to its own "start fresh" prompt
  }
}

export function loadTargetBiologyApplyParams(runId: string): TargetBiologyApplyParams | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(targetBiologyApplyKey(runId));
    return raw ? (JSON.parse(raw) as TargetBiologyApplyParams) : null;
  } catch {
    return null;
  }
}

/** Badge variant per run status (badge variants: default/secondary/destructive/outline/success/warning/ghost/link). */
export const STATUS_VARIANTS: Record<ImportStatus, BadgeVariant> = {
  [ImportStatus.queued]: "secondary",
  [ImportStatus.running]: "warning",
  [ImportStatus.succeeded]: "success",
  [ImportStatus.failed]: "destructive",
  [ImportStatus.cancelled]: "outline",
};
