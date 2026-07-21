import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

// TagFilter has its own dedicated test suite; stub it here so this test
// isn't coupled to its internals.
vi.mock("@/features/tagging", () => ({
  TagFilter: () => null,
}));

vi.mock("../hooks/use-proteomes", () => ({
  useProteomes: () => ({
    data: {
      items: [
        {
          id: "p1",
          uniprot_proteome_id: "UP000005640",
          organism_id: "9606",
          proteome_type: "reference",
          is_reference: true,
          assembly_acc: "GCF_000001405.40",
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
        <div key={String(row.id)}>{String(row.uniprot_proteome_id ?? "")}</div>
      ))}
    </div>
  ),
}));

// Stub OrganismRef
vi.mock("@/shared/components/common/organism-ref", () => ({
  OrganismRef: ({ id }: { id: string }) => <span>{id}</span>,
}));

import { ProteomeListPage } from "./proteome-list";

function renderPage() {
  const qc = new QueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <ProteomeListPage />
    </QueryClientProvider>,
  );
}

describe("ProteomeListPage", () => {
  it("renders a proteome row", () => {
    renderPage();
    expect(screen.getByText("UP000005640")).toBeInTheDocument();
  });
});
