"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { cn } from "@/shared/lib/utils";
import { MapPin } from "lucide-react";
import Link from "next/link";

import { useGeneNeighborhood } from "../../hooks/use-genes";
import {
  ESSENTIALITY_STYLE,
  type EssentialityBucket,
  essentialityBucket,
} from "../../lib/essentiality";
import { type PositionedGene, type TrackGene, layoutNeighbors } from "../../lib/genome-track";
import type { Gene } from "../../types";

const humanize = (b: string) => b.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

// ---------------------------------------------------------------------------
// Legend — the fitness-axis buckets shared with the essentiality call-scale, so
// the track and the summary read as one system.
// ---------------------------------------------------------------------------

const LEGEND_ENTRIES: { label: string; bucket: EssentialityBucket }[] = [
  { label: "Essential", bucket: "essential" },
  { label: "Growth-defect", bucket: "growth-defect" },
  { label: "Non-essential", bucket: "non-essential" },
  { label: "Growth-adv.", bucket: "growth-advantage" },
  { label: "Uncertain", bucket: "uncertain" },
];

function EssentialityLegend() {
  return (
    <div
      className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.625rem] text-muted-foreground"
      aria-label="Essentiality legend"
    >
      {LEGEND_ENTRIES.map((e) => (
        <span key={e.label} className="inline-flex items-center gap-1">
          <span
            className={cn(
              "h-2.5 w-2.5 shrink-0 rounded-sm border",
              ESSENTIALITY_STYLE[e.bucket].bg,
              ESSENTIALITY_STYLE[e.bucket].border,
            )}
            aria-hidden
          />
          {e.label}
        </span>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Track geometry
// ---------------------------------------------------------------------------

const TRACK_W = 640;
const TRACK_H = 60;
const ARROW_Y = 18;
const ARROW_H = 22;
const BASELINE_Y = ARROW_Y + ARROW_H + 2;

/** Strand-aware arrow (pentagon) points for a positioned gene. */
function arrowPoints(g: PositionedGene): string {
  const { x, w } = g;
  const ar = Math.min(8, w * 0.4);
  const y0 = ARROW_Y;
  const y1 = ARROW_Y + ARROW_H;
  const my = ARROW_Y + ARROW_H / 2;
  return g.strand === "-"
    ? `${x + w},${y0} ${x + ar},${y0} ${x},${my} ${x + ar},${y1} ${x + w},${y1}`
    : `${x},${y0} ${x + w - ar},${y0} ${x + w},${my} ${x + w - ar},${y1} ${x},${y1}`;
}

function TrackArrow({ g }: { g: PositionedGene }) {
  const bucket = essentialityBucket(g.essentiality);
  const style = ESSENTIALITY_STYLE[bucket];
  const points = arrowPoints(g);
  const showLabel = g.w >= 26 || g.isCurrent;

  const shape = (
    <>
      <polygon points={points} className={style.fill} fillOpacity={0.75} />
      {g.isCurrent && (
        <polygon points={points} className="fill-none stroke-primary" strokeWidth={2} />
      )}
      {showLabel && (
        <text
          x={g.x + g.w / 2}
          y={ARROW_Y - 4}
          textAnchor="middle"
          fontSize={8}
          className={cn(
            "font-mono",
            g.isCurrent ? "fill-foreground font-semibold" : "fill-muted-foreground",
          )}
        >
          {g.name}
        </text>
      )}
      <title>{`${g.name}${g.strand ? ` (${g.strand})` : ""} · ${humanize(bucket)}`}</title>
    </>
  );

  if (g.isCurrent) {
    // Not a link; the ring + bold label + <title> convey "this gene".
    return <g>{shape}</g>;
  }
  return (
    <Link href={`/genes/${g.id}`} aria-label={g.name}>
      {shape}
    </Link>
  );
}

// ---------------------------------------------------------------------------
// Neighborhood track (only rendered with >= 2 coordinate-bearing neighbors)
// ---------------------------------------------------------------------------

function NeighborhoodTrack({ gene }: { gene: Gene }) {
  const { data, isLoading, isError } = useGeneNeighborhood(gene.id);

  if (isLoading) {
    return <Skeleton className="h-16 w-full rounded-md" />;
  }

  const genes: TrackGene[] = (data?.neighbors ?? [])
    .filter((n) => n.genomic_start != null && n.genomic_end != null)
    .map((n) => ({
      id: n.id,
      name: n.primary_name,
      strand: n.genomic_strand ?? null,
      essentiality: n.essentiality ?? null,
      start: n.genomic_start as number,
      end: n.genomic_end as number,
      isCurrent: n.id === gene.id,
    }))
    .sort((a, b) => a.start - b.start);

  if (isError || genes.length < 2) return null;

  const positioned = layoutNeighbors(genes, TRACK_W);

  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Genomic neighborhood
      </span>
      <figure className="m-0 overflow-x-auto pb-1" aria-label="Genomic neighborhood track">
        <svg
          className="font-mono"
          viewBox={`0 0 ${TRACK_W} ${TRACK_H}`}
          width="100%"
          style={{ minWidth: TRACK_W }}
        >
          <title>Genomic neighborhood track</title>
          <line
            x1={0}
            y1={BASELINE_Y}
            x2={TRACK_W}
            y2={BASELINE_Y}
            className="stroke-border"
            strokeWidth={1}
          />
          {positioned.map((g) => (
            <TrackArrow key={g.id} g={g} />
          ))}
        </svg>
      </figure>
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
