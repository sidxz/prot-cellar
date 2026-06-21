import { render, screen } from "@testing-library/react";
import type { ColDef } from "ag-grid-community";
import { describe, expect, it, vi } from "vitest";
import type { ProteinListItem } from "../types";
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

function makeItem(overrides: Partial<ProteinListItem> = {}): ProteinListItem {
  return {
    id: "p-1",
    primary_accession: "P9WIE5",
    entry_name: "RHO_MYCTU",
    is_reviewed: true,
    recommended_name: "Transcription termination factor Rho",
    short_names: ["Rho"],
    ec_numbers: ["3.6.4.-"],
    gene: { id: "g-1", primary_name: "rho", synonyms: ["nusG", "Rv1297"] },
    organism_id: "org-1",
    seq_length: 740,
    structure: { pdb_count: 6, has_alphafold: true },
    chem: { has_chembl: true, has_drugbank: false },
    ...overrides,
    // biome-ignore lint/suspicious/noExplicitAny: minimal fixture for column rendering
  } as any;
}

function col(headerName: string): ColDef<ProteinListItem> {
  const found = proteinColumnDefs.find((c) => c.headerName === headerName);
  if (!found) throw new Error(`column ${headerName} not found`);
  return found;
}

function renderCell(c: ColDef<ProteinListItem>, data: ProteinListItem | undefined) {
  // biome-ignore lint/suspicious/noExplicitAny: ag-grid cellRenderer is loosely typed
  const Renderer = c.cellRenderer as React.FC<any>;
  return render(<Renderer data={data} />);
}

describe("protein columns — Protein / Gene identity", () => {
  it("links gene + accession and shows the protein name and synonyms", () => {
    renderCell(col("Protein / Gene"), makeItem());
    expect(screen.getByText("rho")).toHaveAttribute("href", "/genes/g-1");
    expect(screen.getByText("nusG, Rv1297")).toBeInTheDocument();
    expect(screen.getByText("Transcription termination factor Rho")).toBeInTheDocument();
    expect(screen.getByText("P9WIE5")).toHaveAttribute("href", "/proteins/P9WIE5");
    expect(screen.getByText("RHO_MYCTU")).toBeInTheDocument();
  });

  it("falls back to 'Uncharacterized protein' and a dash gene when unlinked", () => {
    renderCell(col("Protein / Gene"), makeItem({ gene: null, recommended_name: null }));
    expect(screen.getByText("Uncharacterized protein")).toBeInTheDocument();
  });
});

describe("protein columns — EC / Structure / Chem", () => {
  it("renders EC chips, capping at two with a +N overflow", () => {
    renderCell(col("EC / Class"), makeItem({ ec_numbers: ["1.1.1.1", "2.2.2.2", "3.3.3.3"] }));
    expect(screen.getByText("1.1.1.1")).toBeInTheDocument();
    expect(screen.getByText("2.2.2.2")).toBeInTheDocument();
    expect(screen.getByText("+1")).toBeInTheDocument();
    expect(screen.queryByText("3.3.3.3")).not.toBeInTheDocument();
  });

  it("prefers experimental PDB (with count) over AlphaFold", () => {
    const { container } = renderCell(
      col("Structure"),
      makeItem({ structure: { pdb_count: 6, has_alphafold: true } }),
    );
    expect(container.textContent).toBe("PDB·6");
  });

  it("shows AlphaFold when there is no PDB, and a dash when neither", () => {
    let r = renderCell(
      col("Structure"),
      makeItem({ structure: { pdb_count: 0, has_alphafold: true } }),
    );
    expect(r.container.textContent).toBe("AlphaFold");
    r.unmount();
    r = renderCell(
      col("Structure"),
      makeItem({ structure: { pdb_count: 0, has_alphafold: false } }),
    );
    expect(r.container.textContent).toBe("—");
  });

  it("shows ChEMBL chemical matter, else dash", () => {
    let r = renderCell(col("Chem"), makeItem({ chem: { has_chembl: true, has_drugbank: false } }));
    expect(r.container.textContent).toBe("ChEMBL");
    r.unmount();
    r = renderCell(col("Chem"), makeItem({ chem: { has_chembl: false, has_drugbank: false } }));
    expect(r.container.textContent).toBe("—");
  });
});

describe("protein columns — Database", () => {
  it("badges Swiss-Prot vs TrEMBL by reviewed status", () => {
    expect(renderCell(col("Database"), makeItem({ is_reviewed: true })).container.textContent).toBe(
      "Swiss-Prot",
    );
    expect(
      renderCell(col("Database"), makeItem({ is_reviewed: false })).container.textContent,
    ).toBe("TrEMBL");
  });
});
