"use client";

import { useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";

import { goTermsByAspect } from "../../lib/protein-annotations";
import type { Protein } from "../../types";

// Keep the rendered ancestor chart legible — too many leaf terms make it unreadable.
const MAX_GRAPH_TERMS = 12;

export function GoGraphCard({ protein }: { protein: Protein }) {
  const [failed, setFailed] = useState(false);

  const byAspect = goTermsByAspect(protein);
  const ids = [...byAspect.F, ...byAspect.P, ...byAspect.C]
    .map((t) => t.id)
    .slice(0, MAX_GRAPH_TERMS);
  if (ids.length === 0) return null;

  // QuickGO renders the terms + their is_a/part_of ancestors as a single graph image.
  const chartUrl = `https://www.ebi.ac.uk/QuickGO/services/ontology/go/terms/${ids.join(",")}/chart`;
  const quickGoUrl = `https://www.ebi.ac.uk/QuickGO/term/${ids[0]}`;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold">GO Graph</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {failed ? (
          <p className="text-sm text-muted-foreground">
            Graph preview unavailable.{" "}
            <a
              href={quickGoUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              View on QuickGO
            </a>
          </p>
        ) : (
          <>
            <img
              src={chartUrl}
              alt="Gene Ontology ancestor graph"
              className="h-auto max-w-full rounded-md border border-border bg-white"
              onError={() => setFailed(true)}
            />
            <a
              href={quickGoUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="self-start text-xs text-primary hover:underline"
            >
              Open in QuickGO ↗
            </a>
          </>
        )}
      </CardContent>
    </Card>
  );
}
