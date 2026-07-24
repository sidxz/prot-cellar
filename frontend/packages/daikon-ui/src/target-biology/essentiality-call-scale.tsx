"use client";

import { cn } from "../lib/cn";
import {
  ESSENTIALITY_STYLE,
  type EssentialityBucket,
  type EssentialityLike,
  FITNESS_AXIS_LABELS,
  type PivotCell,
  essentialityConsensus,
  fitnessPosition,
  pivotConditionMethod,
} from "./essentiality";

const humanize = (b: string) => b.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

// Segments low → high fitness, matching FITNESS_AXIS_LABELS order.
const SEGMENTS: EssentialityBucket[] = [
  "growth-advantage",
  "non-essential",
  "growth-defect",
  "essential",
];

/** One condition×method strip cell, colored by its call (or empty when absent). */
function StripCell({ bucket }: { bucket: PivotCell | null }) {
  if (bucket === null) {
    return <div className="h-6 rounded-sm border border-dashed border-border bg-transparent" />;
  }
  if (bucket === "conflict") {
    return (
      <div
        className="flex h-6 items-center justify-center rounded-sm border border-warning/40 bg-warning/15 text-[0.625rem] font-medium text-warning"
        title="Sources disagree for this condition × method"
      >
        !
      </div>
    );
  }
  const style = ESSENTIALITY_STYLE[bucket];
  return (
    <div
      className={cn(
        "flex h-6 items-center justify-center rounded-sm border text-[0.625rem] font-medium",
        style.bg,
        style.border,
        style.text,
      )}
      title={humanize(bucket)}
    >
      {bucket === "growth-defect"
        ? "GD"
        : bucket === "growth-advantage"
          ? "GA"
          : bucket === "non-essential"
            ? "NE"
            : bucket === "essential"
              ? "E"
              : "?"}
    </div>
  );
}

/**
 * Read-only per-gene essentiality summary that sits above the editable table.
 * Places the consensus call on the diverging fitness axis, reads confidence as a
 * meter, and — when a gene carries multiple records — pivots them into a
 * condition×method strip so agreement/conflict across sources reads at a glance.
 */
export function EssentialityCallScale({ records }: { records: EssentialityLike[] }) {
  const consensus = essentialityConsensus(records);
  if (!consensus) return null;

  const pos = fitnessPosition(consensus.bucket);
  const pct = pos != null ? pos * 100 : null;
  const style = ESSENTIALITY_STYLE[consensus.bucket];

  const agreementLabel =
    consensus.agreement === "single"
      ? "single source"
      : consensus.agreement === "agree"
        ? `${consensus.total} sources agree`
        : `sources disagree (${consensus.count}/${consensus.total})`;

  const showStrip = records.length >= 2;
  const pivot = showStrip ? pivotConditionMethod(records) : null;

  return (
    <div className="flex flex-col gap-3 rounded-md bg-muted/40 p-4">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Consensus call
        </span>
        <span data-testid="ess-consensus-call" className={cn("text-sm font-semibold", style.text)}>
          {humanize(consensus.bucket)}
        </span>
      </div>

      {/* Diverging fitness axis: 4 ordered segments + a caret at the call. */}
      <div className="flex flex-col gap-1">
        <div className="relative">
          <div className="flex gap-0.5">
            {SEGMENTS.map((b) => (
              <div key={b} className={cn("h-5 flex-1 rounded-sm", ESSENTIALITY_STYLE[b].bg)} />
            ))}
          </div>
          {pct != null && (
            <div
              aria-hidden
              className="absolute -top-1.5 h-0 w-0 -translate-x-1/2 border-x-[5px] border-t-[7px] border-x-transparent border-t-foreground"
              style={{ left: `${pct}%` }}
            />
          )}
        </div>
        <div className="flex justify-between font-sans text-[0.625rem] text-muted-foreground">
          {FITNESS_AXIS_LABELS.map((l) => (
            <span key={l}>{l}</span>
          ))}
        </div>
      </div>

      {/* Confidence + agreement on one line — a single scalar doesn't need a full meter. */}
      <span className="font-sans text-[0.6875rem] text-muted-foreground">
        {consensus.confidence != null && (
          <>
            <span className="font-medium tabular-nums text-foreground">
              {consensus.confidence.toFixed(2)}
            </span>{" "}
            confidence <span className="text-muted-foreground/60">·</span>{" "}
          </>
        )}
        {agreementLabel}
      </span>

      {/* Condition × method strip (only when there's more than one record). */}
      {pivot && (
        <div
          data-testid="ess-condition-strip"
          className="flex flex-col gap-1 border-t border-border pt-3"
        >
          <span className="font-sans text-[0.625rem] uppercase tracking-wide text-muted-foreground">
            by condition × method
          </span>
          <div className="overflow-x-auto">
            <div className="inline-grid gap-0.5">
              {/* header row: blank corner + condition labels */}
              <div
                className="grid items-end gap-0.5"
                style={{
                  gridTemplateColumns: `minmax(3.5rem,auto) repeat(${pivot.conditions.length}, minmax(2.5rem,1fr))`,
                }}
              >
                <span />
                {pivot.conditions.map((c) => (
                  <span
                    key={c}
                    className="truncate text-center font-sans text-[0.625rem] text-muted-foreground"
                    title={c}
                  >
                    {c}
                  </span>
                ))}
              </div>
              {pivot.methods.map((m) => (
                <div
                  key={m}
                  className="grid items-center gap-0.5"
                  style={{
                    gridTemplateColumns: `minmax(3.5rem,auto) repeat(${pivot.conditions.length}, minmax(2.5rem,1fr))`,
                  }}
                >
                  <span
                    className="truncate pr-1 text-right font-sans text-[0.625rem] text-muted-foreground"
                    title={m}
                  >
                    {m}
                  </span>
                  {pivot.conditions.map((c) => (
                    <StripCell key={`${c} ${m}`} bucket={pivot.cell(c, m)} />
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
