import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

// Drives the ?tag= initial-selection query param. Mutated per-test (and
// reset in afterEach) instead of re-declaring the module mock, since
// `vi.mock` factories run once at import time.
let currentTagParam: string | null = "t1";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => ({ get: (k: string) => (k === "tag" ? currentTagParam : null) }),
}));

// TagFilter itself is real (not stubbed) — only its own hook is mocked, so it
// renders without hitting the network. Tag selection for these tests is
// driven via the ?tag= query param above, not by opening its popover
// (TagFilter's own popover interactions have a dedicated test suite).
vi.mock("../hooks/use-tags", () => ({
  useTags: () => ({ data: [{ id: "t1", key: "tier", value: "1" }] }),
}));

const ROWS = [
  {
    entity_type: "Protein",
    entity_id: "prot-uuid-1",
    label: "P12345",
    assigned_at: "2026-01-01T00:00:00Z",
  },
  {
    entity_type: "Gene",
    entity_id: "gene-uuid-1",
    label: "recA",
    assigned_at: "2026-01-02T00:00:00Z",
  },
  {
    entity_type: "Organism",
    entity_id: "9606",
    label: "Homo sapiens",
    assigned_at: "2026-01-03T00:00:00Z",
  },
];

const mockUseTagEntities = vi.fn((_tagIds: string[], _tagLogic: string, types?: string[]) => ({
  data: types ? ROWS.filter((r) => types.includes(r.entity_type)) : ROWS,
  isLoading: false,
  error: null,
}));

vi.mock("../hooks/use-tag-entities", () => ({
  useTagEntities: (tagIds: string[], tagLogic: string, types?: string[]) =>
    mockUseTagEntities(tagIds, tagLogic, types),
}));

// AG Grid does not render cell content in jsdom; stub DataGrid but still run
// the real cellRenderer functions from columnDefs so rendered links can be
// asserted, mirroring ag-grid's ICellRendererParams shape ({ value, data }).
vi.mock("@/shared/components/data-grid/data-grid", () => ({
  // biome-ignore lint/suspicious/noExplicitAny: test stub, shapes mirror ag-grid's loose generics
  DataGrid: ({ rowData, columnDefs }: { rowData: any[]; columnDefs: any[] }) => (
    <div data-testid="data-grid">
      {(rowData ?? []).map((row) => (
        <div key={`${row.entity_type}-${row.entity_id}`}>
          {columnDefs.map((col) => {
            const value = row[col.field];
            if (col.cellRenderer) {
              const Renderer = col.cellRenderer;
              return <Renderer key={col.field} value={value} data={row} />;
            }
            return (
              <span key={col.field}>
                {col.valueFormatter ? col.valueFormatter({ value }) : value}
              </span>
            );
          })}
        </div>
      ))}
    </div>
  ),
}));

import { TagBrowse, hrefFor } from "./tag-browse";

function renderPage() {
  const qc = new QueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <TagBrowse />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  currentTagParam = "t1";
  mockUseTagEntities.mockClear();
});

describe("hrefFor", () => {
  it("links a Protein by its accession (label), not its internal id", () => {
    expect(hrefFor({ entity_type: "Protein", entity_id: "prot-uuid-1", label: "P12345" })).toBe(
      "/proteins/P12345",
    );
  });

  it.each([
    ["Gene", "gene-uuid-1", "/genes/gene-uuid-1"],
    ["Target", "target-uuid-1", "/targets/target-uuid-1"],
    ["Organism", "9606", "/organisms/9606"],
    ["Strain", "strain-uuid-1", "/strains/strain-uuid-1"],
    ["Proteome", "proteome-uuid-1", "/proteomes/proteome-uuid-1"],
  ])("links a %s by its entity_id", (entity_type, entity_id, expected) => {
    expect(hrefFor({ entity_type, entity_id, label: "whatever" })).toBe(expected);
  });
});

describe("TagBrowse", () => {
  it("shows an empty state and fetches nothing when no tags are selected", () => {
    currentTagParam = null;

    renderPage();

    expect(screen.getByText(/select one or more tags above/i)).toBeInTheDocument();
    expect(screen.queryByTestId("data-grid")).not.toBeInTheDocument();
  });

  it("renders result rows across types with correct labels, once tags are selected", () => {
    renderPage();

    expect(screen.getByText("P12345")).toBeInTheDocument();
    expect(screen.getByText("recA")).toBeInTheDocument();
    expect(screen.getByText("Homo sapiens")).toBeInTheDocument();
  });

  it("links a Protein row to /proteins/{accession} and a Gene row to /genes/{entity_id}", () => {
    renderPage();

    expect(screen.getByRole("link", { name: "P12345" })).toHaveAttribute(
      "href",
      "/proteins/P12345",
    );
    expect(screen.getByRole("link", { name: "recA" })).toHaveAttribute(
      "href",
      "/genes/gene-uuid-1",
    );
  });

  it("passes no type filter (`undefined`) on initial render", () => {
    renderPage();

    expect(mockUseTagEntities).toHaveBeenCalledWith(["t1"], "any", undefined);
  });

  it("toggling a type facet chip filters the `types` passed to useTagEntities", () => {
    renderPage();
    mockUseTagEntities.mockClear();

    fireEvent.click(screen.getByRole("button", { name: /gene/i }));

    expect(mockUseTagEntities).toHaveBeenCalledWith(["t1"], "any", ["Gene"]);
  });
});
