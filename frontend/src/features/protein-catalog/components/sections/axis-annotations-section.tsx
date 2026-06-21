"use client";

import { Badge } from "@/shared/components/ui/badge";
import type { badgeVariants } from "@/shared/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import type { VariantProps } from "class-variance-authority";

import type { Gene } from "../../types";

type BadgeVariant = NonNullable<VariantProps<typeof badgeVariants>["variant"]>;

/**
 * Map a vulnerability `essentiality` value to a Badge variant so the triage
 * signal pops at a glance. Reuses the existing Badge palette (no new colors):
 *   essential        → destructive (red)   — strongest signal
 *   growth-defect    → warning (amber)
 *   growth-advantage → outline (blue-ish/neutral border)
 *   non-essential    → secondary (muted)
 *   uncertain/other  → ghost (muted gray)
 * The match is substring + hyphen/underscore tolerant to absorb dataset wording.
 */
export function essentialityBadgeVariant(value: string | null | undefined): BadgeVariant {
  const v = (value ?? "").toLowerCase().replace(/_/g, "-");
  if (v.includes("non-essential") || v.includes("nonessential")) return "secondary";
  if (v.includes("growth-defect") || v.includes("growth defect")) return "warning";
  if (v.includes("growth-advantage") || v.includes("growth advantage")) return "outline";
  if (v.includes("essential")) return "destructive";
  return "ghost";
}

/**
 * Display titles for each annotation axis, keyed by the backend `axis` value.
 * Exported so callers (e.g. the gene detail page) reuse one source of truth.
 */
export const AXIS_TITLES: Record<string, string> = {
  vulnerability: "Vulnerability",
  selectivity: "Selectivity",
  robustness: "Robustness",
  context: "Genomic context",
  expression: "Expression",
};

type Annotation = Gene["annotations"][number];

/** Build the `dataset · condition` provenance subline (omitting empty parts). */
function provenance(a: Annotation): string {
  return [a.dataset, a.condition].filter(Boolean).join(" · ");
}

function AnnotationChip({
  annotation,
  variant = "secondary",
}: {
  annotation: Annotation;
  variant?: BadgeVariant;
}) {
  const title = annotation.evidence ?? undefined;

  if (annotation.source_url) {
    return (
      <Badge variant={variant} asChild className="font-normal">
        <a href={annotation.source_url} target="_blank" rel="noopener noreferrer" title={title}>
          {annotation.value}
        </a>
      </Badge>
    );
  }

  return (
    <Badge variant={variant} className="font-normal" title={title}>
      {annotation.value}
    </Badge>
  );
}

/**
 * Generic, axis-typed annotation panel. Filters `gene.annotations` to a single
 * `axis` (e.g. "vulnerability") and renders each as a value chip with a
 * `dataset · condition` provenance subline. Returns `null` when the axis is empty.
 */
export function AxisAnnotationsSection({
  gene,
  axis,
  title,
}: {
  gene: Gene;
  axis: string;
  title: string;
}) {
  const items = (gene.annotations ?? []).filter((a) => a.axis === axis);
  if (items.length === 0) return null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold">{title}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-2.5">
        {items.map((a) => {
          const sub = provenance(a);
          // The vulnerability `essentiality` chip is color-coded by value so the
          // triage signal pops; every other axis/key keeps the neutral chip.
          const variant =
            a.key === "essentiality" ? essentialityBadgeVariant(a.value) : "secondary";
          return (
            <div key={`${a.key}:${a.value}`} className="flex flex-col gap-0.5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  {a.key.replace(/_/g, " ")}
                </span>
                <AnnotationChip annotation={a} variant={variant} />
              </div>
              {sub && <span className="text-xs text-muted-foreground">{sub}</span>}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
