import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("../hooks/use-targets", () => ({
  useTargets: () => ({
    data: {
      items: [
        {
          id: "t1",
          pref_name: "EGFR",
          target_type: "single_protein",
          components: [{ id: "c1", protein_id: "p1", relationship: "single_protein" }],
          cross_references: [],
          version: 1,
          workspace_id: "w1",
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
        <div key={String(row.id ?? row.pref_name)}>{String(row.pref_name ?? "")}</div>
      ))}
    </div>
  ),
}));
// Stub dialog — prevents its hooks (useCreateTarget, useUpdateTarget) from running in tests.
vi.mock("./target-form-dialog", () => ({
  TargetFormDialog: () => null,
}));
import { TargetListPage } from "./target-list";
describe("TargetListPage", () => {
  it("renders a target row", () => {
    const qc = new QueryClient();
    render(
      <QueryClientProvider client={qc}>
        <TargetListPage />
      </QueryClientProvider>,
    );
    expect(screen.getByText("EGFR")).toBeInTheDocument();
  });
});
