import type { StrainResponse } from "@/shared/lib/api/model";

/**
 * Narrow the visible strains to those belonging to the selected organism.
 * Strains anchor to a species-rank organism via `species_organism_id`, which is
 * exactly what a protein's `organism_id` points at — so this keeps a strain
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
