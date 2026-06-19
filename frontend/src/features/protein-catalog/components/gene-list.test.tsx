import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("../hooks/use-genes", () => ({
  useGenes: () => ({
    data: {
      items: [
        {
          id: "g1",
          primary_name: "TP53",
          organism_id: "o1",
          synonyms: ["P53"],
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
        <div key={String(row.id ?? row.primary_name)}>{String(row.primary_name ?? "")}</div>
      ))}
    </div>
  ),
}));

import { GeneListPage } from "./gene-list";

describe("GeneListPage", () => {
  it("renders a gene row", () => {
    const qc = new QueryClient();
    render(
      <QueryClientProvider client={qc}>
        <GeneListPage />
      </QueryClientProvider>,
    );
    expect(screen.getByText("TP53")).toBeInTheDocument();
  });
});
