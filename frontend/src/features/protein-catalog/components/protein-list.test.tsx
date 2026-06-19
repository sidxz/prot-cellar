import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
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
});
