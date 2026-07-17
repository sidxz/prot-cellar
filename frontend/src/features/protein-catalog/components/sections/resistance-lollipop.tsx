"use client";

import type { ResistanceMutationResponse } from "@/shared/lib/api/model";
import { cn } from "@/shared/lib/utils";

import { type Needle, buildNeedles, distinctCompounds } from "../../lib/resistance";

// Static class literals only (Tailwind can't see interpolated names).
const CHART_FILL = ["fill-chart-1", "fill-chart-2", "fill-chart-3", "fill-chart-4", "fill-chart-5"];
const CHART_BG = ["bg-chart-1", "bg-chart-2", "bg-chart-3", "bg-chart-4", "bg-chart-5"];

const L_W = 640;
const L_H = 132;
const MARGIN = 30;
const PLOT_W = L_W - MARGIN * 2;
const BASELINE = 100;

/** log2(MIC fold-shift), clamped, drives stem height and head radius. */
function micMagnitude(micShift: number | null): number {
  return Math.min(10, Math.max(0, Math.log2(Math.max(1, micShift ?? 1))));
}

function NeedleMark({
  needle,
  x,
  fill,
}: {
  needle: Needle;
  x: number;
  fill: string;
}) {
  const mag = micMagnitude(needle.micShift);
  const height = 16 + mag * 11;
  const r = 4 + mag * 0.9;
  const headY = BASELINE - height;
  return (
    <g>
      <title>
        {`${needle.label} · residue ${needle.position}${
          needle.micShift != null ? ` · ×${needle.micShift} MIC` : ""
        }${needle.compound ? ` · ${needle.compound}` : ""}`}
      </title>
      <line
        x1={x}
        y1={BASELINE}
        x2={x}
        y2={headY}
        className="stroke-muted-foreground"
        strokeWidth={1.5}
      />
      <circle cx={x} cy={headY} r={r} className={cn(fill, "stroke-card")} strokeWidth={1.5} />
      <text
        x={x}
        y={headY - r - 3}
        textAnchor="middle"
        fontSize={8}
        className="fill-foreground font-mono"
      >
        {needle.label}
      </text>
    </g>
  );
}

/**
 * Resistance-mutation lollipop over the residue axis: stem/head scale with the
 * MIC fold-shift, head color = the resisted compound. Reveals catalytic-site
 * hotspots vs. scattered low-level resistance. Renders when >= 2 mutations carry
 * a parseable residue position; the table remains the fallback.
 */
export function ResistanceLollipop({ records }: { records: ResistanceMutationResponse[] }) {
  const needles = buildNeedles(records);
  if (needles.length < 2) return null;

  const compounds = distinctCompounds(needles);
  const maxPos = Math.max(...needles.map((n) => n.position));
  const span = maxPos - 1 || 1;
  const x = (pos: number) => MARGIN + ((pos - 1) / span) * PLOT_W;
  const colorFor = (compound: string | null) => {
    const i = compound ? compounds.indexOf(compound) : -1;
    return i >= 0 ? CHART_FILL[i % CHART_FILL.length] : "fill-muted-foreground";
  };

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Resistance mutations
        </span>
        <span className="font-mono text-[0.625rem] text-muted-foreground">
          {needles.length} mapped · stem = log₂ MIC
        </span>
      </div>

      <div className="overflow-x-auto">
        <svg
          data-testid="resistance-lollipop"
          viewBox={`0 0 ${L_W} ${L_H}`}
          width="100%"
          style={{ minWidth: L_W }}
          role="img"
          aria-label="Resistance mutations along the protein sequence"
        >
          {/* residue backbone */}
          <line
            x1={MARGIN}
            y1={BASELINE}
            x2={L_W - MARGIN}
            y2={BASELINE}
            className="stroke-border"
            strokeWidth={2}
          />
          {needles.map((n) => (
            <NeedleMark key={n.id} needle={n} x={x(n.position)} fill={colorFor(n.compound)} />
          ))}
          {/* residue axis endpoints */}
          <text x={MARGIN} y={BASELINE + 16} fontSize={9} className="fill-muted-foreground">
            1
          </text>
          <text
            x={L_W - MARGIN}
            y={BASELINE + 16}
            textAnchor="end"
            fontSize={9}
            className="fill-muted-foreground"
          >
            {maxPos}
          </text>
          <text
            x={L_W / 2}
            y={BASELINE + 16}
            textAnchor="middle"
            fontSize={9}
            className="fill-muted-foreground"
          >
            residue position
          </text>
        </svg>
      </div>

      {compounds.length > 0 && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.625rem] text-muted-foreground">
          {compounds.map((c, i) => (
            <span key={c} className="inline-flex items-center gap-1">
              <span
                className={cn("h-2.5 w-2.5 shrink-0 rounded-full", CHART_BG[i % CHART_BG.length])}
                aria-hidden
              />
              {c}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
