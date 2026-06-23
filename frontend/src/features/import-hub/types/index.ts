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

/** Human-readable labels for the 3 import types. */
export const IMPORT_TYPE_LABELS: Record<ImportType, string> = {
  [ImportType.proteome]: "Proteome",
  [ImportType.gene_enrichment]: "Gene enrichment",
  [ImportType.go_ontology]: "GO ontology",
};

/** Badge variant per run status (badge variants: default/secondary/destructive/outline/success/warning/ghost/link). */
export const STATUS_VARIANTS: Record<ImportStatus, BadgeVariant> = {
  [ImportStatus.queued]: "secondary",
  [ImportStatus.running]: "warning",
  [ImportStatus.succeeded]: "success",
  [ImportStatus.failed]: "destructive",
  [ImportStatus.cancelled]: "outline",
};
