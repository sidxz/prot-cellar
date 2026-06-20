"use client";

import { Badge } from "@/shared/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";

import { type GoRef, goTermsByAspect } from "../../lib/protein-annotations";
import type { Protein } from "../../types";

const ASPECTS: { key: "F" | "P" | "C"; label: string }[] = [
  { key: "F", label: "Molecular Function" },
  { key: "P", label: "Biological Process" },
  { key: "C", label: "Cellular Component" },
];

function GoChip({ term }: { term: GoRef }) {
  return (
    <Badge variant="secondary" asChild className="font-normal">
      <a
        href={`https://www.ebi.ac.uk/QuickGO/term/${term.id}`}
        target="_blank"
        rel="noopener noreferrer"
        title={term.evidence ? `${term.id} · ${term.evidence}` : term.id}
      >
        {term.name || term.id}
      </a>
    </Badge>
  );
}

export function GoTermsSection({ protein }: { protein: Protein }) {
  const byAspect = goTermsByAspect(protein);
  const total = byAspect.F.length + byAspect.P.length + byAspect.C.length;
  if (total === 0) return null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold">Gene Ontology</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {ASPECTS.filter((a) => byAspect[a.key].length > 0).map((a) => (
          <div key={a.key} className="flex flex-col gap-1.5">
            <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {a.label}
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {byAspect[a.key].map((t) => (
                <GoChip key={t.id} term={t} />
              ))}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
