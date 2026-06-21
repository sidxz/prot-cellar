"use client";

import { Badge } from "@/shared/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";

import type { Gene } from "../../types";

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

function AnnotationChip({ annotation }: { annotation: Annotation }) {
  const title = annotation.evidence ?? undefined;

  if (annotation.source_url) {
    return (
      <Badge variant="secondary" asChild className="font-normal">
        <a href={annotation.source_url} target="_blank" rel="noopener noreferrer" title={title}>
          {annotation.value}
        </a>
      </Badge>
    );
  }

  return (
    <Badge variant="secondary" className="font-normal" title={title}>
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
          return (
            <div key={`${a.key}:${a.value}`} className="flex flex-col gap-0.5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  {a.key.replace(/_/g, " ")}
                </span>
                <AnnotationChip annotation={a} />
              </div>
              {sub && <span className="text-xs text-muted-foreground">{sub}</span>}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
