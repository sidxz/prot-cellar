import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
// TagFilter has its own dedicated test suite; stub it here so this test
// isn't coupled to its internals.
vi.mock("@/features/tagging", () => ({
  TagFilter: () => null,
}));
vi.mock("../hooks/use-organisms", () => ({
  useOrganisms: () => ({
    data: {
      items: [
        {
          id: "9606",
          scientific_name: "Homo sapiens",
          rank: "species",
          ncbi_tax_id: 9606,
          ncbi_url: "https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=9606",
          source: "ncbi",
          names: [{ name: "human", name_class: "common_name", is_preferred: true }],
          is_merged: false,
          is_deleted: false,
          version: 1,
        },
      ],
      next_cursor: null,
    },
    isLoading: false,
    isError: false,
  }),
}));
vi.mock("@/shared/components/data-grid/data-grid", () => ({
  DataGrid: ({ rowData }: { rowData: Array<Record<string, unknown>> }) => (
    <div data-testid="data-grid">
      {(rowData ?? []).map((row) => (
        <div key={String(row.id)}>{String(row.scientific_name ?? "")}</div>
      ))}
    </div>
  ),
}));

import { OrganismListPage } from "./organism-list";

function renderPage() {
  const qc = new QueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <OrganismListPage />
    </QueryClientProvider>,
  );
}

describe("OrganismListPage", () => {
  it("renders an organism row", () => {
    renderPage();
    expect(screen.getByText("Homo sapiens")).toBeInTheDocument();
  });
});
