"use client";

import { cn } from "../lib/cn";
import { useMeasuredWidth } from "./use-measured-width";
import {
  type MutationLike,
  type Needle,
  assignLabelRows,
  buildNeedles,
  distinctCompounds,
} from "./resistance";

// Static class literals only (Tailwind can't see interpolated names).
const CHART_FILL = ["fill-chart-1", "fill-chart-2", "fill-chart-3", "fill-chart-4", "fill-chart-5"];
const CHART_BG = ["bg-chart-1", "bg-chart-2", "bg-chart-3", "bg-chart-4", "bg-chart-5"];

// Fixed px — the SVG renders at the container's real width (1:1), so heights,
// heads and fonts stay constant on any monitor and only the residue axis stretches.
const L_H = 150;
const MARGIN_X = 60;
const BASELINE = 116;
const MIN_HEIGHT = 18; // stem length at MIC ×1
const MAX_HEIGHT = 80; // stem length at the clamp — leaves headroom for head + label
const LABEL_ROW_H = 16; // vertical offset for a staggered (row-1) label
const LABEL_MIN_GAP = 56; // px closer than this → stagger the label to avoid overlap
const FONT_LABEL = 12;
const FONT_AXIS = 10;

/** log2(MIC fold-shift), clamped to [0,10] — drives stem height and head radius. */
function micMagnitude(micShift: number | null): number {
  return Math.min(10, Math.max(0, Math.log2(Math.max(1, micShift ?? 1))));
}

function NeedleMark({
  needle,
  x,
  fill,
  labelRow,
}: {
  needle: Needle;
  x: number;
  fill: string;
  labelRow: number;
}) {
  const mag = micMagnitude(needle.micShift);
  const height = MIN_HEIGHT + (mag / 10) * (MAX_HEIGHT - MIN_HEIGHT);
  const r = 4 + (mag / 10) * 7;
  const headY = BASELINE - height;
  const labelY = headY - r - 5 - labelRow * LABEL_ROW_H;
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
      {labelRow > 0 && (
        <line
          x1={x}
          y1={headY - r}
          x2={x}
          y2={labelY + 3}
          className="stroke-muted-foreground"
          strokeWidth={1}
          strokeOpacity={0.4}
        />
      )}
      <circle cx={x} cy={headY} r={r} className={cn(fill, "stroke-card")} strokeWidth={1.5} />
      <text x={x} y={labelY} textAnchor="middle" fontSize={FONT_LABEL} className="fill-foreground">
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
export function ResistanceLollipop({ records }: { records: MutationLike[] }) {
  const [ref, width] = useMeasuredWidth<HTMLDivElement>();
  const needles = [...buildNeedles(records)].sort((a, b) => a.position - b.position);
  if (needles.length < 2) return null;

  const compounds = distinctCompounds(needles);
  const maxPos = Math.max(...needles.map((n) => n.position));
  const span = maxPos - 1 || 1;
  const plotW = Math.max(10, width - MARGIN_X * 2);
  const posX = (pos: number) => MARGIN_X + ((pos - 1) / span) * plotW;
  const xs = needles.map((n) => posX(n.position));
  const labelRows = assignLabelRows(xs, LABEL_MIN_GAP);
  const colorFor = (compound: string | null) => {
    const i = compound ? compounds.indexOf(compound) : -1;
    return i >= 0 ? CHART_FILL[i % CHART_FILL.length] : "fill-muted-foreground";
  };

  return (
    <div className="flex flex-col gap-2 rounded-md bg-muted/40 p-4">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Resistance mutations
        </span>
        <span className="text-[0.6875rem] text-muted-foreground">
          {needles.length} mapped · stem = log₂ MIC
        </span>
      </div>

      <div ref={ref} className="w-full">
        {width > 0 && (
          <svg
            className="font-sans"
            data-testid="resistance-lollipop"
            viewBox={`0 0 ${width} ${L_H}`}
            width="100%"
            height={L_H}
            role="img"
            aria-label="Resistance mutations along the protein sequence"
          >
            {/* residue backbone */}
            <line
              x1={MARGIN_X}
              y1={BASELINE}
              x2={width - MARGIN_X}
              y2={BASELINE}
              className="stroke-border"
              strokeWidth={2}
            />
            {needles.map((n, i) => (
              <NeedleMark
                key={n.id}
                needle={n}
                x={xs[i]}
                fill={colorFor(n.compound)}
                labelRow={labelRows[i]}
              />
            ))}
            {/* residue axis endpoints (below the baseline, clear of the needles) */}
            <text
              x={MARGIN_X}
              y={BASELINE + 18}
              fontSize={FONT_AXIS}
              className="fill-muted-foreground"
            >
              1
            </text>
            <text
              x={width - MARGIN_X}
              y={BASELINE + 18}
              textAnchor="end"
              fontSize={FONT_AXIS}
              className="fill-muted-foreground"
            >
              {maxPos}
            </text>
            <text
              x={width / 2}
              y={BASELINE + 18}
              textAnchor="middle"
              fontSize={FONT_AXIS}
              className="fill-muted-foreground"
            >
              residue position
            </text>
          </svg>
        )}
      </div>

      {compounds.length > 0 && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.6875rem] text-muted-foreground">
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
