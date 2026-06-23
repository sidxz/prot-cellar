"use client";

import { useOrganisms } from "@/features/taxonomy/hooks/use-organisms";
import { useStrains } from "@/features/taxonomy/hooks/use-strains";
import { Label } from "@/shared/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
import type { StrainResponse } from "@/shared/lib/api/model";

/** Sentinel value for the "no filter" option (Radix Select disallows empty string). */
const ALL = "all";

/**
 * Narrow the visible strains to those belonging to the selected organism.
 * Strains anchor to a species-rank organism via `species_organism_id`, which is
 * exactly what a protein's `organism_id` points at — so this keeps the strain
 * dropdown from offering picks that could never co-occur with the chosen organism.
 * With no organism selected, every strain is offered.
 */
export function scopeStrainsToOrganism(
  strains: StrainResponse[],
  organismId: string | undefined,
): StrainResponse[] {
  if (!organismId) return strains;
  return strains.filter((s) => s.species_organism_id === organismId);
}

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
  const { data: orgData } = useOrganisms();
  const { data: strainData } = useStrains();

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
