import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Protein } from "../../types";
import { CrossReferencesSection } from "./cross-references-section";

const protein = {
  cross_references: [
    { database: "PDB", accession: "8IKA", url: "https://www.ebi.ac.uk/pdbe/8IKA" },
    { database: "EMBL", accession: "AL123456", url: "https://embl/AL123456" },
    { database: "InterPro", accession: "IPR051429", url: "https://interpro/IPR051429" },
    { database: "GO", accession: "GO:0005886", url: "https://quickgo/GO:0005886" },
    { database: "WeirdDB", accession: "X1", url: null },
  ],
} as unknown as Protein;

describe("CrossReferencesSection", () => {
  it("groups databases into ordered categories with linked accessions", () => {
    render(<CrossReferencesSection protein={protein} />);
    expect(screen.getByText("Structure")).toBeInTheDocument();
    expect(screen.getByText("Sequences")).toBeInTheDocument();
    expect(screen.getByText("Family & Domains")).toBeInTheDocument();
    expect(screen.getByText("Function & Pathways")).toBeInTheDocument();
    expect(screen.getByText("Other")).toBeInTheDocument(); // unmapped WeirdDB falls through

    // an accession with a url renders as a link; without a url, as plain text
    expect(screen.getByRole("link", { name: "8IKA" })).toHaveAttribute(
      "href",
      "https://www.ebi.ac.uk/pdbe/8IKA",
    );
    expect(screen.queryByRole("link", { name: "X1" })).not.toBeInTheDocument();
    expect(screen.getByText("X1")).toBeInTheDocument();
  });

  it("returns null when there are no cross-references", () => {
    const { container } = render(<CrossReferencesSection protein={{} as unknown as Protein} />);
    expect(container).toBeEmptyDOMElement();
  });
});
