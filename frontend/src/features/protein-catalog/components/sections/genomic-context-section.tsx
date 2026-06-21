"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { cn } from "@/shared/lib/utils";
import { MapPin } from "lucide-react";
import Link from "next/link";

import { useGeneNeighborhood } from "../../hooks/use-genes";
import type { Gene } from "../../types";

// ---------------------------------------------------------------------------
// Essentiality shading — kept color-consistent with the vulnerability panel
// chips (axis-annotations-section.tsx): essential→destructive, growth-defect→
// warning, growth-advantage→outline/blue-ish, non-essential→muted, unknown→
// neutral. Tokens (not raw colors) so the track + panel read as one system.
// ---------------------------------------------------------------------------

type EssentialityBucket =
  | "essential"
  | "growth-defect"
  | "growth-advantage"
  | "non-essential"
  | "unknown";

/** Bucket a free-text `essentiality` value (hyphen/underscore tolerant). */
function essentialityBucket(essentiality: string | null | undefined): EssentialityBucket {
  const v = (essentiality ?? "").toLowerCase().replace(/_/g, "-");
  if (v.includes("non-essential") || v.includes("nonessential")) return "non-essential";
  if (v.includes("growth-defect") || v.includes("growth defect")) return "growth-defect";
  if (v.includes("growth-advantage") || v.includes("growth advantage")) return "growth-advantage";
  if (v.includes("essential")) return "essential";
  return "unknown";
}

/** Box border/background/text classes per bucket. */
const BUCKET_BOX_STYLE: Record<EssentialityBucket, string> = {
  essential: "border-destructive/40 bg-destructive/10 text-destructive",
  "growth-defect": "border-warning/30 bg-warning/15 text-warning",
  "growth-advantage": "border-border bg-card text-foreground",
  "non-essential": "border-border bg-muted text-muted-foreground",
  unknown: "border-border bg-card text-foreground",
};

/** Map a gene's `essentiality` value to its box style. */
function essentialityStyle(essentiality: string | null | undefined): string {
  return BUCKET_BOX_STYLE[essentialityBucket(essentiality)];
}

// Legend entries: small swatch (same token families as the boxes) + label.
// `growth-advantage` is intentionally omitted from the default legend to keep
// it compact; it shares the neutral swatch and is rare in current data.
const LEGEND_ENTRIES: { label: string; swatch: string }[] = [
  { label: "Essential", swatch: "border-destructive/40 bg-destructive/10" },
  { label: "Growth-defect", swatch: "border-warning/30 bg-warning/15" },
  { label: "Non-essential", swatch: "border-border bg-muted" },
  { label: "Unknown", swatch: "border-border bg-card" },
];

function EssentialityLegend() {
  return (
    <div
      className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.625rem] text-muted-foreground"
      aria-label="Essentiality legend"
    >
      {LEGEND_ENTRIES.map((e) => (
        <span key={e.label} className="inline-flex items-center gap-1">
          <span className={cn("h-2.5 w-2.5 shrink-0 rounded-sm border", e.swatch)} aria-hidden />
          {e.label}
        </span>
      ))}
    </div>
  );
}

interface NeighborBox {
  id: string;
  primary_name: string;
  genomic_start?: number | null;
  genomic_strand?: string | null;
  essentiality?: string | null;
}

function NeighborBox({ neighbor, isCurrent }: { neighbor: NeighborBox; isCurrent: boolean }) {
  const className = cn(
    "flex w-24 shrink-0 flex-col items-center gap-0.5 rounded-md border px-2 py-1.5 text-center transition-colors",
    essentialityStyle(neighbor.essentiality),
    isCurrent && "ring-2 ring-primary ring-offset-1 ring-offset-background",
  );

  const body = (
    <>
      <span className="w-full truncate font-mono text-xs font-medium" title={neighbor.primary_name}>
        {neighbor.primary_name}
      </span>
      {neighbor.genomic_strand && (
        <span className="text-[0.625rem] leading-none text-muted-foreground">
          {neighbor.genomic_strand} strand
        </span>
      )}
    </>
  );

  if (isCurrent) {
    return (
      <div className={className} aria-current="true" title={`${neighbor.primary_name} (this gene)`}>
        {body}
      </div>
    );
  }

  return (
    <Link
      href={`/genes/${neighbor.id}`}
      className={cn(className, "hover:border-primary/60 hover:shadow-sm")}
    >
      {body}
    </Link>
  );
}

// ---------------------------------------------------------------------------
// Neighborhood track (only rendered with >= 2 neighbors)
// ---------------------------------------------------------------------------

function NeighborhoodTrack({ gene }: { gene: Gene }) {
  const { data, isLoading, isError } = useGeneNeighborhood(gene.id);

  if (isLoading) {
    return <Skeleton className="h-16 w-full rounded-md" />;
  }

  const neighbors = data?.neighbors ?? [];
  if (isError || neighbors.length < 2) return null;

  const ordered = [...neighbors].sort((a, b) => (a.genomic_start ?? 0) - (b.genomic_start ?? 0));

  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Genomic neighborhood
      </span>
      <div className="flex items-stretch gap-1 overflow-x-auto pb-1">
        {ordered.map((n) => (
          <NeighborBox key={n.id} neighbor={n} isCurrent={n.id === gene.id} />
        ))}
      </div>
      <EssentialityLegend />
    </div>
  );
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
