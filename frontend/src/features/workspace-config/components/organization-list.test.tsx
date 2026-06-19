import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

vi.mock("../hooks/use-organizations", () => ({
  useOrganizations: () => ({
    data: {
      items: [
        { id: "o1", name: "Acme Bio", org_type: "pharma_partner", is_active: true },
        { id: "o2", name: "Globex CRO", org_type: "cro", is_active: false },
      ],
      next_cursor: null,
    },
    isLoading: false,
    isError: false,
  }),
}));

// Stub DataGrid to render row names so we can assert data flow without ag-grid in jsdom.
vi.mock("@/shared/components/data-grid/data-grid", () => ({
  // biome-ignore lint/suspicious/noExplicitAny: test stub
  DataGrid: ({ rowData }: any) => (
    <div data-testid="grid">
      {rowData?.map(
        // biome-ignore lint/suspicious/noExplicitAny: test stub
        (r: any) => (
          <div key={r.id}>{r.name}</div>
        ),
      )}
    </div>
  ),
}));

// Stub dialog so it doesn't need React Query context in tests.
vi.mock("./organization-form-dialog", () => ({
  OrganizationFormDialog: () => null,
}));

import { OrganizationListPage } from "./organization-list";

describe("OrganizationListPage", () => {
  it("renders organization names from the hook into the grid", () => {
    render(<OrganizationListPage />);
    expect(screen.getByText("Acme Bio")).toBeInTheDocument();
    expect(screen.getByText("Globex CRO")).toBeInTheDocument();
  });
});
