"use client";

import { useOrganisms } from "@/features/taxonomy/hooks/use-organisms";
import { useStrains } from "@/features/taxonomy/hooks/use-strains";
import { scopeStrainsToOrganism } from "@/features/taxonomy/lib/scope-strains";
import { TAXON_FILTER_PAGE_SIZE } from "@/features/taxonomy/types";
import { Label } from "@/shared/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";

/** Sentinel value for the "no filter" option (Radix Select disallows empty string). */
const ALL = "all";

interface ProteinTaxonFiltersProps {
  organismId: string | undefined;
  strainId: string | undefined;
  /** Picking an organism resets the strain (the parent owns both values). */
  onOrganismChange: (organismId: string | undefined) => void;
  onStrainChange: (strainId: string | undefined) => void;
}

export function ProteinTaxonFilters({
  organismId,
  strainId,
  onOrganismChange,
  onStrainChange,
}: ProteinTaxonFiltersProps) {
  const { data: orgData } = useOrganisms({ limit: TAXON_FILTER_PAGE_SIZE });
  const { data: strainData } = useStrains({}, undefined, TAXON_FILTER_PAGE_SIZE);

  const organisms = orgData?.items ?? [];
  const strains = scopeStrainsToOrganism(strainData?.items ?? [], organismId);

  return (
    <>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="organism-filter" className="text-xs text-muted-foreground">
          Organism
        </Label>
        <Select
          value={organismId ?? ALL}
          onValueChange={(v) => onOrganismChange(v === ALL ? undefined : v)}
        >
          <SelectTrigger id="organism-filter" className="h-8 w-52" aria-label="Filter by organism">
            <SelectValue placeholder="All organisms" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All organisms</SelectItem>
            {organisms.map((o) => (
              <SelectItem key={o.id} value={o.id}>
                {o.scientific_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="strain-filter" className="text-xs text-muted-foreground">
          Strain
        </Label>
        <Select
          value={strainId ?? ALL}
          onValueChange={(v) => onStrainChange(v === ALL ? undefined : v)}
        >
          <SelectTrigger id="strain-filter" className="h-8 w-52" aria-label="Filter by strain">
            <SelectValue placeholder="All strains" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All strains</SelectItem>
            {strains.map((s) => (
              <SelectItem key={s.id} value={s.id}>
                {s.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </>
  );
}
