"use client";

import { useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";

import type { Protein } from "../../types";

const MAX_SHOWN = 5;

export function CitationsSection({ protein }: { protein: Protein }) {
  const [expanded, setExpanded] = useState(false);
  const citations = protein.citations ?? [];
  if (citations.length === 0) return null;
  const shown = expanded ? citations : citations.slice(0, MAX_SHOWN);

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold">Literature ({citations.length})</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="flex flex-col gap-3">
          {shown.map((c, i) => (
            <li
              key={`cite-${c.pubmed_id ?? c.doi ?? c.reference_number ?? i}`}
              className="flex flex-col gap-0.5 text-sm"
            >
              <span className="font-medium leading-snug text-foreground">
                {c.title ?? "Untitled reference"}
              </span>
              <span className="text-xs text-muted-foreground">
                {[c.journal, c.publication_date].filter(Boolean).join(" · ")}
              </span>
              <div className="flex gap-3 text-xs">
                {c.pubmed_id && (
                  <a
                    href={`https://pubmed.ncbi.nlm.nih.gov/${c.pubmed_id}/`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                  >
                    PubMed
                  </a>
                )}
                {c.doi && (
                  <a
                    href={`https://doi.org/${c.doi}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                  >
                    DOI
                  </a>
                )}
              </div>
            </li>
          ))}
        </ul>
        {citations.length > MAX_SHOWN && (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="mt-2 text-xs text-primary hover:underline"
          >
            {expanded ? "Show fewer" : `Show all ${citations.length} references`}
          </button>
        )}
      </CardContent>
    </Card>
  );
}
