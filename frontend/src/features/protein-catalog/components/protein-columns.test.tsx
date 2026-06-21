import { render, screen } from "@testing-library/react";
import type { ColDef } from "ag-grid-community";
import { describe, expect, it, vi } from "vitest";
import type { Protein } from "../types";
import { proteinColumnDefs } from "./protein-columns";

// next/link → plain anchor so cells render without an app-router context.
vi.mock("next/link", () => ({
  // biome-ignore lint/suspicious/noExplicitAny: test stub
  default: ({ href, children, ...rest }: any) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

function makeProtein(overrides: Partial<Protein> = {}): Protein {
  return {
    primary_accession: "P0DG01",
    protein_names: { recommended: "Transcription termination factor Rho", short_names: ["Rho"] },
    gene: { id: "g-1", primary_name: "rho", synonyms: ["nusG", "Rv1297"] },
    ...overrides,
    // biome-ignore lint/suspicious/noExplicitAny: minimal fixture for column rendering
  } as any;
}

function col(headerName: string): ColDef<Protein> {
  const found = proteinColumnDefs.find((c) => c.headerName === headerName);
  if (!found) throw new Error(`column ${headerName} not found`);
  return found;
}

function renderCell(c: ColDef<Protein>, data: Protein | undefined) {
  // biome-ignore lint/suspicious/noExplicitAny: ag-grid cellRenderer is loosely typed
  const Renderer = c.cellRenderer as React.FC<any>;
  return render(<Renderer data={data} />);
}

describe("protein columns — Gene", () => {
  it("renders the gene name linked plus synonyms", () => {
    renderCell(col("Gene"), makeProtein());
    const link = screen.getByText("rho");
    expect(link).toHaveAttribute("href", "/genes/g-1");
    expect(screen.getByText("nusG, Rv1297")).toBeInTheDocument();
  });

  it("shows a dash when the protein has no linked gene", () => {
    const { container } = renderCell(col("Gene"), makeProtein({ gene: null }));
    expect(container.textContent).toBe("—");
  });

  it("hides a synonym that duplicates the primary name", () => {
    const data = makeProtein({
      // biome-ignore lint/suspicious/noExplicitAny: minimal fixture
      gene: { id: "g-2", primary_name: "rho", synonyms: ["rho", "nusG"] } as any,
    });
    renderCell(col("Gene"), data);
    expect(screen.getByText("nusG")).toBeInTheDocument();
    expect(screen.queryByText("rho, nusG")).not.toBeInTheDocument();
  });
});

describe("protein columns — Short Name", () => {
  // biome-ignore lint/suspicious/noExplicitAny: ag-grid ValueGetterParams is partial here
  const get = (data: Protein | undefined) => (col("Short Name").valueGetter as any)({ data });

  it("joins protein short names", () => {
    expect(get(makeProtein())).toBe("Rho");
    expect(get(makeProtein({ protein_names: { short_names: ["PptT", "Sfp"] } }))).toBe(
      "PptT / Sfp",
    );
  });

  it("falls back to a dash when there is no short name", () => {
    expect(get(makeProtein({ protein_names: { recommended: "x" } }))).toBe("—");
  });
});
