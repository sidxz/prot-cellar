"use client";

import { Skeleton } from "@/shared/components/ui/skeleton";

import { useGeneTargetBiology } from "../../hooks/use-target-biology";
import { ProvenanceLegend } from "./editable-record-table";
import { EssentialityCallScale } from "./essentiality-call-scale";
import {
  CrispriStrainTable,
  EssentialityTable,
  HypomorphTable,
  ResistanceMutationTable,
  VulnerabilityTable,
} from "./gene-record-tables";
import { ResistanceLollipop } from "./resistance-lollipop";
import { VulnerabilityPanel } from "./vulnerability-panel";

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
      <div className="flex flex-col gap-3">
        <VulnerabilityPanel records={data?.vulnerability ?? []} />
        <VulnerabilityTable geneId={geneId} records={data?.vulnerability ?? []} />
      </div>
      <HypomorphTable geneId={geneId} records={data?.hypomorph ?? []} />
      <CrispriStrainTable geneId={geneId} records={data?.crispri_strain ?? []} />
      <div className="flex flex-col gap-3">
        <ResistanceLollipop records={data?.resistance_mutation ?? []} />
        <ResistanceMutationTable geneId={geneId} records={data?.resistance_mutation ?? []} />
      </div>
    </div>
  );
}
