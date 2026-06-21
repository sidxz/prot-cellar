"use client";

import { MapPin } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";

import { subcellularLocations } from "../../lib/protein-annotations";
import type { Protein } from "../../types";

// NOTE: an inline Swiss-BioPics <sib-swissbiopics-sl> embed was tried here, but its
// cell-image service has no image for many organisms (e.g. M. tuberculosis, taxid
// 83332) and the component's internal fetch 500s — surfacing a console error + a
// blank box. We show the location names + a link to UniProt's (working) diagram
// instead. See memory: protein-viewer-future-visualizations.
export function SubcellularLocationCard({ protein }: { protein: Protein }) {
  const locations = subcellularLocations(protein);
  if (locations.length === 0) return null;

  const uniprotUrl = protein.uniprot_url
    ? `${protein.uniprot_url}#subcellular_location`
    : undefined;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold">Subcellular Location</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        <ul className="flex flex-col gap-1">
          {locations.map((loc) => (
            <li key={loc} className="flex items-center gap-2 text-sm text-foreground">
              <MapPin className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
              {loc}
            </li>
          ))}
        </ul>
        {uniprotUrl && (
          <a
            href={uniprotUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="self-start text-xs text-primary hover:underline"
          >
            View location diagram on UniProt ↗
          </a>
        )}
      </CardContent>
    </Card>
  );
}
