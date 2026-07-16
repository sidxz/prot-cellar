"use client";

import { Skeleton } from "@/shared/components/ui/skeleton";

import { useProteinTargetBiology } from "../../hooks/use-target-biology";
import { ProvenanceLegend } from "./editable-record-table";
import {
  ProteinActivityAssayTable,
  ProteinProductionTable,
  UnpublishedStructureTable,
} from "./protein-record-tables";

/** Protein detail "Target Biology" tab — the three protein-side records as editable tables. */
export function ProteinTargetBiologyTab({ proteinId }: { proteinId: string }) {
  const { data, isLoading } = useProteinTargetBiology(proteinId);

  if (isLoading) {
    return <Skeleton className="h-48 w-full rounded-md" aria-label="Loading target biology" />;
  }

  return (
    <div className="flex flex-col gap-8">
      <ProvenanceLegend />
      <ProteinProductionTable proteinId={proteinId} records={data?.protein_production ?? []} />
      <ProteinActivityAssayTable
        proteinId={proteinId}
        records={data?.protein_activity_assay ?? []}
      />
      <UnpublishedStructureTable
        proteinId={proteinId}
        records={data?.unpublished_structure ?? []}
      />
    </div>
  );
}
