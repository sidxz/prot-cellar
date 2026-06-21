"use client";

import { MapPin } from "lucide-react";
import { useEffect, useRef } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import { useGetOrganismApiV1OrganismsOrganismIdGet } from "@/shared/lib/api/organisms/organisms";

import { subcellularLocationSlIds, subcellularLocations } from "../../lib/protein-annotations";
import type { Protein } from "../../types";

const SWISSBIOPICS_JS = "https://www.swissbiopics.org/static/swissbiopics.js";
const TEMPLATE_ID = "sibSwissBioPicsSlLiItem";

let swissBioPicsPromise: Promise<void> | null = null;

/** Inject the SwissBioPics template + ESM bundle once; resolves when the element is defined. */
function loadSwissBioPics(): Promise<void> {
  if (typeof window === "undefined") return Promise.resolve();
  if (window.customElements?.get("sib-swissbiopics-sl")) return Promise.resolve();
  if (swissBioPicsPromise) return swissBioPicsPromise;

  if (!document.getElementById(TEMPLATE_ID)) {
    // Required by the SwissBioPics component (it clones this per location).
    const tpl = document.createElement("template");
    tpl.id = TEMPLATE_ID;
    const li = document.createElement("li");
    li.className = "subcellular_location";
    const name = document.createElement("a");
    name.className = "subcell_name";
    const description = document.createElement("span");
    description.className = "subcell_description";
    li.append(name, description);
    tpl.content.appendChild(li);
    document.body.appendChild(tpl);
  }
  if (!document.querySelector("script[data-swissbiopics]")) {
    const script = document.createElement("script");
    script.type = "module";
    script.src = SWISSBIOPICS_JS;
    script.dataset.swissbiopics = "1";
    document.body.appendChild(script);
  }

  swissBioPicsPromise =
    window.customElements?.whenDefined("sib-swissbiopics-sl").then(() => undefined) ??
    Promise.resolve();
  return swissBioPicsPromise;
}

function SwissBioPicsDiagram({ organismId, slIds }: { organismId: string; slIds: string[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const { data: organism } = useGetOrganismApiV1OrganismsOrganismIdGet(organismId);
  const taxid = organism?.ncbi_tax_id ?? undefined;
  const sls = slIds.join(",");

  useEffect(() => {
    if (taxid == null) return;
    let cancelled = false;
    loadSwissBioPics()
      .then(() => {
        const host = ref.current;
        if (cancelled || !host) return;
        host.replaceChildren();
        const el = document.createElement("sib-swissbiopics-sl");
        el.setAttribute("taxid", String(taxid));
        el.setAttribute("sls", sls);
        host.appendChild(el);
      })
      .catch(() => {
        /* leave the diagram blank; the location names + UniProt link remain */
      });
    return () => {
      cancelled = true;
    };
  }, [taxid, sls]);

  if (taxid == null) return null;
  return (
    <div
      ref={ref}
      data-taxid={taxid}
      className="mt-1 w-full overflow-x-auto [&_svg]:h-auto [&_svg]:max-w-full"
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
            View full diagram on UniProt ↗
          </a>
        )}
      </CardContent>
    </Card>
  );
}
