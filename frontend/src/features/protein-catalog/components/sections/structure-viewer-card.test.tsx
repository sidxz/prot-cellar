import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Protein } from "../../types";
import { StructureViewerCard } from "./structure-viewer-card";

const withStructures = {
  cross_references: [
    {
      database: "PDB",
      accession: "1ABC",
      url: "u",
      properties: { Method: "X-ray", Resolution: "2.10 A" },
    },
    { database: "PDB", accession: "2XYZ", url: "u", properties: { Method: "NMR" } },
    { database: "AlphaFoldDB", accession: "P12345", url: "u", properties: {} },
  ],
} as unknown as Protein;

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve([
            { cifUrl: "https://alphafold.ebi.ac.uk/files/AF-P12345-F1-model_v6.cif" },
          ]),
      }),
    ),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("StructureViewerCard", () => {
  it("renders a viewer for the first PDB structure + a switcher listing all structures", () => {
    const { container } = render(<StructureViewerCard protein={withStructures} />);
    const host = container.querySelector("[data-structure-id='1ABC']");
    expect(host).toBeInTheDocument();
    // must be a positioned, fixed-height container so the Mol* canvas can't take over the screen
    expect(host).toHaveClass("relative");
    expect(screen.getByRole("button", { name: /PDB 2XYZ/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /AlphaFold P12345/i })).toBeInTheDocument();
    expect(screen.getByText("X-ray")).toBeInTheDocument();
  });

  it("switches the viewer when another structure is selected", () => {
    const { container } = render(<StructureViewerCard protein={withStructures} />);
    fireEvent.click(screen.getByRole("button", { name: /AlphaFold P12345/i }));
    expect(container.querySelector("[data-structure-id='P12345']")).toBeInTheDocument();
  });

  it("returns null when there are no structures", () => {
    const { container } = render(<StructureViewerCard protein={{} as unknown as Protein} />);
    expect(container).toBeEmptyDOMElement();
  });
});
