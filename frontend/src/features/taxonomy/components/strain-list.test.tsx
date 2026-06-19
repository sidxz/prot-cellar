import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

vi.mock("../hooks/use-strains", () => ({
  useStrains: () => ({
    data: {
      items: [
        {
          id: "s1",
          workspace_id: "w1",
          species_organism_id: "org-1",
          name: "E. coli K-12",
          biosample_acc: "SAMN001",
          assembly_acc: "GCF_000005845",
          culture_collection: "ATCC 10798",
          version: 1,
        },
      ],
      next_cursor: null,
    },
    isLoading: false,
    isError: false,
  }),
  useCreateStrain: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateStrain: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

// AG Grid does not render cell content in jsdom; stub DataGrid to render rows as plain divs.
vi.mock("@/shared/components/data-grid/data-grid", () => ({
  DataGrid: ({ rowData }: { rowData: Array<Record<string, unknown>> }) => (
    <div data-testid="data-grid">
      {(rowData ?? []).map((row) => (
        <div key={String(row.id ?? row.name)}>{String(row.name ?? "")}</div>
      ))}
    </div>
  ),
}));

// Stub OrganismRef
vi.mock("@/shared/components/common/organism-ref", () => ({
  OrganismRef: ({ id }: { id: string }) => <span>{id}</span>,
}));

// Stub dialog
vi.mock("./strain-form-dialog", () => ({
  StrainFormDialog: () => null,
}));

import { StrainListPage } from "./strain-list";

describe("StrainListPage", () => {
  it("renders a strain row", () => {
    const qc = new QueryClient();
    render(
      <QueryClientProvider client={qc}>
        <StrainListPage />
      </QueryClientProvider>,
    );
    expect(screen.getByText("E. coli K-12")).toBeInTheDocument();
  });
});
