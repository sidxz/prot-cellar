import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Protein } from "../../types";
import { CrossReferencesSection } from "./cross-references-section";

const protein = {
  cross_references: [
    // no backend url, but PDB / InterPro / GO are mapped → should link
    { database: "PDB", accession: "8IKA", url: null },
    { database: "InterPro", accession: "IPR051429", url: null },
    { database: "GO", accession: "GO:0005886", url: null },
    // unmapped database with no url → plain text (no broken link)
    { database: "WeirdDB", accession: "X1", url: null },
  ],
} as unknown as Protein;

describe("CrossReferencesSection", () => {
  it("groups databases into ordered categories", () => {
    render(<CrossReferencesSection protein={protein} />);
    expect(screen.getByText("Structure")).toBeInTheDocument();
    expect(screen.getByText("Family & Domains")).toBeInTheDocument();
    expect(screen.getByText("Function & Pathways")).toBeInTheDocument();
    expect(screen.getByText("Other")).toBeInTheDocument(); // unmapped WeirdDB falls through
  });

  it("links mapped accessions to their external resource, even without a backend url", () => {
    render(<CrossReferencesSection protein={protein} />);
    expect(screen.getByRole("link", { name: "8IKA" })).toHaveAttribute(
      "href",
      "https://www.rcsb.org/structure/8IKA",
    );
    expect(screen.getByRole("link", { name: "IPR051429" }).getAttribute("href")).toContain(
      "/interpro/entry/InterPro/IPR051429",
    );
    expect(screen.getByRole("link", { name: "GO:0005886" }).getAttribute("href")).toContain(
      "QuickGO/term/GO:0005886",
    );
  });

  it("renders unmapped databases as plain text (no broken link)", () => {
    render(<CrossReferencesSection protein={protein} />);
    expect(screen.queryByRole("link", { name: "X1" })).not.toBeInTheDocument();
    expect(screen.getByText("X1")).toBeInTheDocument();
  });

  it("returns null when there are no cross-references", () => {
    const { container } = render(<CrossReferencesSection protein={{} as unknown as Protein} />);
    expect(container).toBeEmptyDOMElement();
  });
});
