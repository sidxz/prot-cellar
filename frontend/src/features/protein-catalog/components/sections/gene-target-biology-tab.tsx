"use client";

import { Skeleton } from "@/shared/components/ui/skeleton";

import { useGeneTargetBiology } from "../../hooks/use-target-biology";
import { EssentialityCallScale } from "./essentiality-call-scale";
import { ProvenanceLegend } from "./editable-record-table";
import {
  CrispriStrainTable,
  EssentialityTable,
  HypomorphTable,
  ResistanceMutationTable,
  VulnerabilityTable,
} from "./gene-record-tables";

/** Gene detail "Target Biology" tab — the five gene-side records as editable tables. */
export function GeneTargetBiologyTab({ geneId }: { geneId: string }) {
  const { data, isLoading } = useGeneTargetBiology(geneId);

  if (isLoading) {
    return <Skeleton className="h-48 w-full rounded-md" aria-label="Loading target biology" />;
  }

  return (
    <div className="flex flex-col gap-8">
      <ProvenanceLegend />
      <div className="flex flex-col gap-3">
        <EssentialityCallScale records={data?.essentiality ?? []} />
        <EssentialityTable geneId={geneId} records={data?.essentiality ?? []} />
      </div>
      <VulnerabilityTable geneId={geneId} records={data?.vulnerability ?? []} />
      <HypomorphTable geneId={geneId} records={data?.hypomorph ?? []} />
      <CrispriStrainTable geneId={geneId} records={data?.crispri_strain ?? []} />
      <ResistanceMutationTable geneId={geneId} records={data?.resistance_mutation ?? []} />
    </div>
  );
}
