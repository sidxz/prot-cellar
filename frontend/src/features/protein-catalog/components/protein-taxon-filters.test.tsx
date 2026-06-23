import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { StrainResponse } from "@/shared/lib/api/model";
import { ProteinTaxonFilters, scopeStrainsToOrganism } from "./protein-taxon-filters";

const strain = (id: string, speciesOrganismId: string, name: string): StrainResponse =>
  ({
    id,
    species_organism_id: speciesOrganismId,
    name,
    workspace_id: "w",
    version: 1,
  }) as StrainResponse;

const STRAINS = [
  strain("s1", "org-A", "ATCC 25618 / H37Rv"),
  strain("s2", "org-A", "CDC 1551 / Oshkosh"),
  strain("s3", "org-B", "Unrelated strain"),
];

vi.mock("@/features/taxonomy/hooks/use-organisms", () => ({
  useOrganisms: () => ({
    data: { items: [{ id: "org-A", scientific_name: "Mycobacterium tuberculosis" }] },
  }),
}));
vi.mock("@/features/taxonomy/hooks/use-strains", () => ({
  useStrains: () => ({ data: { items: STRAINS } }),
}));

describe("scopeStrainsToOrganism", () => {
  it("returns every strain when no organism is selected", () => {
    expect(scopeStrainsToOrganism(STRAINS, undefined)).toHaveLength(3);
  });

  it("keeps only strains anchored to the selected organism", () => {
    expect(scopeStrainsToOrganism(STRAINS, "org-A").map((s) => s.id)).toEqual(["s1", "s2"]);
    expect(scopeStrainsToOrganism(STRAINS, "org-B").map((s) => s.id)).toEqual(["s3"]);
  });
});

describe("ProteinTaxonFilters", () => {
  it("renders an organism select and a strain select", () => {
    render(
      <ProteinTaxonFilters
        organismId={undefined}
        strainId={undefined}
        onOrganismChange={vi.fn()}
        onStrainChange={vi.fn()}
      />,
    );
    expect(screen.getByRole("combobox", { name: "Filter by organism" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Filter by strain" })).toBeInTheDocument();
  });
});
