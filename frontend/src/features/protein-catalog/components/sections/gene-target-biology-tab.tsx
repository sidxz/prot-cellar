"use client";

import { Skeleton } from "@/shared/components/ui/skeleton";

import { useGeneTargetBiology } from "../../hooks/use-target-biology";
import { EssentialityTable } from "./essentiality-table";
import { GeneTargetBiologySection } from "./target-biology-section";

/**
 * Gene detail "Target Biology" tab. Essentiality is a fully editable table
 * (add / inline-edit / delete); the remaining gene-side records render
 * read-only for now — their editors follow the same pattern.
 */
export function GeneTargetBiologyTab({ geneId }: { geneId: string }) {
  const { data, isLoading } = useGeneTargetBiology(geneId);

  if (isLoading) {
    return <Skeleton className="h-48 w-full rounded-md" aria-label="Loading target biology" />;
  }

  return (
    <div className="flex flex-col gap-8">
      <EssentialityTable geneId={geneId} records={data?.essentiality ?? []} />
      <GeneTargetBiologySection geneId={geneId} omit={["Essentiality"]} heading={null} />
    </div>
  );
}
