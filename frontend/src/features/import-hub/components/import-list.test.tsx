// frontend/src/features/import-hub/components/import-list.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

vi.mock("../hooks/use-imports", () => ({
  useImportList: () => ({
    data: {
      items: [
        { id: "r1", target_key: "UP000001584", import_type: "proteome", status: "succeeded" },
        { id: "r2", target_key: "83332", import_type: "gene_enrichment", status: "running" },
      ],
      next_cursor: null,
    },
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  }),
}));

vi.mock("@/shared/components/data-grid/data-grid", () => ({
  // biome-ignore lint/suspicious/noExplicitAny: test stub
  DataGrid: ({ rowData }: any) => (
    <div data-testid="grid">
      {/* biome-ignore lint/suspicious/noExplicitAny: test stub */}
      {rowData?.map((r: any) => (
        <div key={r.id}>{r.target_key}</div>
      ))}
    </div>
  ),
}));

vi.mock("./start-import-dialog", () => ({ StartImportDialog: () => null }));

import { ImportListPage } from "./import-list";

describe("ImportListPage", () => {
  it("renders run target keys into the grid", () => {
    render(<ImportListPage />);
    expect(screen.getByText("UP000001584")).toBeInTheDocument();
    expect(screen.getByText("83332")).toBeInTheDocument();
  });
});
