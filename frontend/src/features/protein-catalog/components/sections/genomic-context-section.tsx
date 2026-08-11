"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { MapPin } from "lucide-react";
import Link from "next/link";

import { GenomicContext, type GenomicNeighborLike } from "@structflo/components/target-biology";
import { useGeneNeighborhood } from "../../hooks/use-genes";
import type { Gene } from "../../types";

// ---------------------------------------------------------------------------
// Neighborhood track (only rendered with >= 2 coordinate-bearing neighbors) —
// the track itself lives in @structflo/components, shared with daikon.
// ---------------------------------------------------------------------------

function NeighborhoodTrack({ gene }: { gene: Gene }) {
  const { data, isLoading, isError } = useGeneNeighborhood(gene.id);

  if (isLoading) {
    return <Skeleton className="h-16 w-full rounded-md" />;
  }
  if (isError) return null;

  const neighbors: GenomicNeighborLike[] = (data?.neighbors ?? []).map((n) => ({
    id: n.id,
    display_label: n.display_label,
    start: n.genomic_start ?? null,
    end: n.genomic_end ?? null,
    strand: n.genomic_strand ?? null,
    essentiality: n.essentiality ?? null,
  }));

  return <GenomicContext centerId={gene.id} neighbors={neighbors} LinkComponent={Link} />;
}

// ---------------------------------------------------------------------------
// Main section
// ---------------------------------------------------------------------------

const fmt = (n: number | null | undefined): string => (n == null ? "—" : n.toLocaleString("en-US"));

export function GenomicContextSection({ gene }: { gene: Gene }) {
  if (!gene.genomic_accession) return null;

  const coords =
    gene.genomic_start != null && gene.genomic_end != null
      ? `${fmt(gene.genomic_start)}–${fmt(gene.genomic_end)}`
      : null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold">Genomic Context</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {/* Location row: accession · start–end · strand · length */}
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-foreground">
          <MapPin className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
          <span className="font-mono">{gene.genomic_accession}</span>
          {coords && (
            <>
              <span className="text-muted-foreground" aria-hidden="true">
                ·
              </span>
              <span className="font-mono">{coords}</span>
            </>
          )}
          {gene.genomic_strand && (
            <>
              <span className="text-muted-foreground" aria-hidden="true">
                ·
              </span>
              <span className="font-mono">{gene.genomic_strand} strand</span>
            </>
          )}
          {gene.length_bp != null && (
            <>
              <span className="text-muted-foreground" aria-hidden="true">
                ·
              </span>
              <span className="text-muted-foreground">{fmt(gene.length_bp)} bp</span>
            </>
          )}
        </div>

        <NeighborhoodTrack gene={gene} />
      </CardContent>
    </Card>
  );
}
