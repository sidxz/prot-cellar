import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
// TagFilter has its own dedicated test suite; stub it here so this test
// isn't coupled to its internals.
vi.mock("@/features/tagging", () => ({
  TagFilter: () => null,
}));
vi.mock("../hooks/use-proteins", () => ({
  useProteins: () => ({
    data: {
      items: [
        {
          id: "1",
          primary_accession: "P12345",
          entry_name: "ALBU_HUMAN",
          is_reviewed: true,
          seq_length: 609,
          organism_id: "o1",
          protein_names: { recommended: "Albumin" },
          secondary_accessions: [],
          keywords: [],
          cross_references: [],
          version: 1,
        },
      ],
      next_cursor: null,
    },
    isLoading: false,
    isError: false,
  }),
}));
// Taxonomy hooks feed the organism + strain filter dropdowns.
vi.mock("@/features/taxonomy/hooks/use-organisms", () => ({
  useOrganisms: () => ({
    data: { items: [{ id: "o1", scientific_name: "Mycobacterium tuberculosis" }] },
  }),
}));
vi.mock("@/features/taxonomy/hooks/use-strains", () => ({
  useStrains: () => ({
    data: {
      items: [
        { id: "s1", species_organism_id: "o1", name: "H37Rv", workspace_id: "w", version: 1 },
      ],
    },
  }),
}));
// AG Grid does not render cell content in jsdom; stub DataGrid to render rows as plain divs.
vi.mock("@/shared/components/data-grid/data-grid", () => ({
  DataGrid: ({ rowData }: { rowData: Array<Record<string, unknown>> }) => (
    <div data-testid="data-grid">
      {(rowData ?? []).map((row) => (
        <div key={String(row.primary_accession ?? row.id)}>
          {String(row.primary_accession ?? "")}
        </div>
      ))}
    </div>
  ),
}));
import { ProteinListPage } from "./protein-list";
function renderPage() {
  const qc = new QueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <ProteinListPage />
    </QueryClientProvider>,
  );
}
describe("ProteinListPage", () => {
  it("renders a protein row", () => {
    renderPage();
    expect(screen.getByText("P12345")).toBeInTheDocument();
  });

  it("renders the organism and strain filters", () => {
    renderPage();
    expect(screen.getByRole("combobox", { name: "Filter by organism" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Filter by strain" })).toBeInTheDocument();
  });
});
