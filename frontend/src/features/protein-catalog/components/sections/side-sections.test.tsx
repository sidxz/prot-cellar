import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Protein } from "../../types";
import { CitationsSection } from "./citations-section";
import { GoTermsSection } from "./go-terms-section";
import { IsoformsSection } from "./isoforms-section";
import { KeywordsSection } from "./keywords-section";

const protein = {
  cross_references: [
    {
      database: "GO",
      accession: "GO:0016491",
      url: "u",
      properties: { GoTerm: "F:oxidoreductase activity" },
    },
    { database: "GO", accession: "GO:0006281", url: "u", properties: { GoTerm: "P:DNA repair" } },
  ],
  keyword_refs: [{ kw_id: "KW-0560", name: "Oxidoreductase", category: "Molecular function" }],
  citations: [
    {
      title: "A great paper",
      journal: "J. Biol.",
      publication_date: "2020",
      pubmed_id: "12345678",
    },
  ],
  isoforms: [{ isoform_accession: "P12345-1", name: "Iso 1", is_displayed: true }],
} as unknown as Protein;

const empty = {} as unknown as Protein;

describe("side sections", () => {
  it("GoTermsSection renders aspect groups + chips", () => {
    render(<GoTermsSection protein={protein} />);
    expect(screen.getByText("oxidoreductase activity")).toBeInTheDocument();
    expect(screen.getByText(/Molecular Function/)).toBeInTheDocument();
    expect(screen.getByText("DNA repair")).toBeInTheDocument();
  });

  it("KeywordsSection renders named keywords", () => {
    render(<KeywordsSection protein={protein} />);
    expect(screen.getByText("Oxidoreductase")).toBeInTheDocument();
  });

  it("CitationsSection renders title + PubMed link", () => {
    render(<CitationsSection protein={protein} />);
    expect(screen.getByText("A great paper")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "PubMed" })).toHaveAttribute(
      "href",
      "https://pubmed.ncbi.nlm.nih.gov/12345678/",
    );
  });

  it("IsoformsSection renders isoform accession + name", () => {
    render(<IsoformsSection protein={protein} />);
    expect(screen.getByText("P12345-1")).toBeInTheDocument();
    expect(screen.getByText("Iso 1")).toBeInTheDocument();
  });

  it("all sections return null when their data is empty", () => {
    expect(render(<GoTermsSection protein={empty} />).container).toBeEmptyDOMElement();
    expect(render(<KeywordsSection protein={empty} />).container).toBeEmptyDOMElement();
    expect(render(<CitationsSection protein={empty} />).container).toBeEmptyDOMElement();
    expect(render(<IsoformsSection protein={empty} />).container).toBeEmptyDOMElement();
  });
});
