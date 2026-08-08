import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const useStrainMock = vi.fn();
vi.mock("../hooks/use-strains", () => ({
  useStrain: () => useStrainMock(),
  useCreateStrain: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateStrain: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

vi.mock("@/shared/components/common/organism-ref", () => ({
  OrganismRef: ({ id }: { id: string }) => <span>{id}</span>,
}));

// TagsRelation has its own dedicated test suite; stub it here so this test
// stays focused on the strain detail chrome (no QueryClient wiring needed).
vi.mock("@/features/tagging", () => ({
  TagsRelation: () => null,
}));

import { StrainDetailPage } from "./strain-detail";

const base = {
  id: "s1",
  workspace_id: "w1",
  species_organism_id: "org-1",
  name: "E. coli K-12",
  biosample_acc: "SAMN001",
  assembly_acc: "GCF_000005845",
  version: 1,
};

describe("StrainDetailPage", () => {
  it("shows the strain name heading", () => {
    useStrainMock.mockReturnValue({
      data: { ...base, is_shared: false },
      isLoading: false,
      isError: false,
    });
    render(<StrainDetailPage strainId="s1" />);
    expect(screen.getByRole("heading", { name: "E. coli K-12" })).toBeInTheDocument();
  });

  it("hides Edit and shows a reference-data marker for a shared strain", () => {
    useStrainMock.mockReturnValue({
      data: { ...base, is_shared: true },
      isLoading: false,
      isError: false,
    });
    render(<StrainDetailPage strainId="s1" />);
    expect(screen.queryByRole("button", { name: /edit/i })).not.toBeInTheDocument();
    expect(screen.getByText(/managed by import/i)).toBeInTheDocument();
  });

  it("shows Edit and no marker for a strain that is not shared", () => {
    useStrainMock.mockReturnValue({
      data: { ...base, is_shared: false },
      isLoading: false,
      isError: false,
    });
    render(<StrainDetailPage strainId="s1" />);
    expect(screen.getByRole("button", { name: /edit/i })).toBeInTheDocument();
    expect(screen.queryByText(/managed by import/i)).not.toBeInTheDocument();
  });
});
