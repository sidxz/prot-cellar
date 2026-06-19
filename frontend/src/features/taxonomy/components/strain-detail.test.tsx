import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../hooks/use-strains", () => ({
  useStrain: () => ({
    data: {
      id: "s1",
      workspace_id: "w1",
      species_organism_id: "org-1",
      name: "E. coli K-12",
      biosample_acc: "SAMN001",
      assembly_acc: "GCF_000005845",
      version: 1,
    },
    isLoading: false,
    isError: false,
  }),
  useCreateStrain: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateStrain: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

vi.mock("@/shared/components/common/organism-ref", () => ({
  OrganismRef: ({ id }: { id: string }) => <span>{id}</span>,
}));

import { StrainDetailPage } from "./strain-detail";

describe("StrainDetailPage", () => {
  it("shows the strain name heading", () => {
    render(<StrainDetailPage strainId="s1" />);
    expect(screen.getByRole("heading", { name: "E. coli K-12" })).toBeInTheDocument();
  });
});
