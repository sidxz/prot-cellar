import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Protein } from "../../types";
import { GoGraphCard } from "./go-graph-card";

const protein = {
  cross_references: [
    {
      database: "GO",
      accession: "GO:0016491",
      properties: { GoTerm: "F:oxidoreductase activity" },
    },
    { database: "GO", accession: "GO:0006281", properties: { GoTerm: "P:DNA repair" } },
  ],
} as unknown as Protein;

describe("GoGraphCard", () => {
  it("renders the QuickGO chart image including the GO ids", () => {
    render(<GoGraphCard protein={protein} />);
    const img = screen.getByRole("img", { name: /gene ontology/i });
    expect(img.getAttribute("src")).toContain("GO:0016491");
    expect(img.getAttribute("src")).toContain("/chart");
  });

  it("falls back to a QuickGO link when the chart image fails to load", () => {
    render(<GoGraphCard protein={protein} />);
    fireEvent.error(screen.getByRole("img"));
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /QuickGO/i })).toBeInTheDocument();
  });

  it("returns null when there are no GO terms", () => {
    const { container } = render(<GoGraphCard protein={{} as unknown as Protein} />);
    expect(container).toBeEmptyDOMElement();
  });
});
