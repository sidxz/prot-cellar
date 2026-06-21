"use client";

import { MapPin } from "lucide-react";
import { useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import { useGetOrganismApiV1OrganismsOrganismIdGet } from "@/shared/lib/api/organisms/organisms";

import { subcellularLocationSlIds, subcellularLocations } from "../../lib/protein-annotations";
import type { Protein } from "../../types";

/**
 * SwissBioPics renders the organism's cell with the given subcellular locations
 * highlighted. We use the image endpoint directly as an <img> (safe — img-loaded
 * SVGs can't run scripts) instead of the `<sib-swissbiopics-sl>` web component,
 * which injects its own unstyled location list. Degrades via onError.
 */
function SwissBioPicsDiagram({ organismId, slIds }: { organismId: string; slIds: string[] }) {
  const { data: organism } = useGetOrganismApiV1OrganismsOrganismIdGet(organismId);
  const [failed, setFailed] = useState(false);

  const taxid = organism?.ncbi_tax_id ?? undefined;
  const sls = slIds.map((id) => id.replace(/[^0-9]/g, "")).join(",");
  if (taxid == null || sls === "" || failed) return null;

  return (
    <img
      src={`https://www.swissbiopics.org/api/${taxid}/sl/${sls}`}
      alt="Subcellular location cell diagram"
      className="mt-1 w-full max-w-[280px] self-start rounded-md border border-border bg-white p-1"
      onError={() => setFailed(true)}
    />
  );
}

export function SubcellularLocationCard({ protein }: { protein: Protein }) {
  const locations = subcellularLocations(protein);
  if (locations.length === 0) return null;

  const slIds = subcellularLocationSlIds(protein);
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
        {slIds.length > 0 && <SwissBioPicsDiagram organismId={protein.organism_id} slIds={slIds} />}
        {uniprotUrl && (
          <a
            href={uniprotUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="self-start text-xs text-primary hover:underline"
          >
            View interactive diagram on UniProt ↗
          </a>
        )}
      </CardContent>
    </Card>
  );
}
