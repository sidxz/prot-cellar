import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../hooks/use-strains", () => ({
  useStrains: () => ({
    data: {
      items: [
        { id: "strain-1", name: "H37Rv", species_organism_id: "org-1" },
        { id: "strain-2", name: "CDC1551", species_organism_id: "org-1" },
      ],
    },
  }),
}));

vi.mock("@/shared/lib/api/organisms/organisms", () => ({
  getGetOrganismApiV1OrganismsOrganismIdGetQueryKey: () => ["organism"],
  getListOrganismsApiV1OrganismsGetQueryKey: () => ["organisms"],
  useUpdateOrganismApiV1OrganismsOrganismIdPatch: () => ({ mutate: vi.fn() }),
}));

import { OrganismReferenceStrain } from "./organism-reference-strain";

function renderWithClient(ui: ReactElement) {
  const qc = new QueryClient();
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

// Organisms are reference data (design doc §1.5) — every organism is `isShared`
// in practice, but the component is exercised at both values so the gate itself
// (not just today's data) is what's under test. Same shape as
// strain-detail.test.tsx's is_shared coverage.
describe("OrganismReferenceStrain", () => {
  it("shows the current strain and a reference-data marker, not a picker, when shared", () => {
    renderWithClient(
      <OrganismReferenceStrain organismId="org-1" referenceStrainId="strain-1" isShared />,
    );
    expect(screen.getByText("H37Rv")).toBeInTheDocument();
    expect(screen.getByText(/managed by import/i)).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("shows an editable picker and no marker when not shared", () => {
    renderWithClient(
      <OrganismReferenceStrain organismId="org-1" referenceStrainId="strain-1" isShared={false} />,
    );
    expect(screen.getByRole("combobox", { name: "Reference strain" })).toBeInTheDocument();
    expect(screen.queryByText(/managed by import/i)).not.toBeInTheDocument();
  });
});
