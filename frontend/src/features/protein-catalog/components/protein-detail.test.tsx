import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../hooks/use-proteins", () => ({
  useProtein: () => ({
    data: {
      id: "1",
      primary_accession: "P12345",
      entry_name: "ALBU_HUMAN",
      is_reviewed: true,
      seq_length: 7,
      seq_mass: 800,
      organism_id: "o1",
      gene_id: null,
      protein_names: { recommended: "Albumin" },
      secondary_accessions: [],
      keywords: ["Signal"],
      cross_references: [
        {
          database: "pdb",
          accession: "1AO6",
          curie: "pdb:1AO6",
          url: "https://x/1AO6",
        },
      ],
      version: 1,
    },
    isLoading: false,
    isError: false,
  }),
  useProteinFasta: () => ({
    data: { header: "sp|P12345|ALBU_HUMAN", sequence: "MAAAKLL" },
    isLoading: false,
    isError: false,
  }),
}));

import { ProteinDetailPage } from "./protein-detail";

describe("ProteinDetailPage", () => {
  it("shows the accession and a cross-reference link", () => {
    render(<ProteinDetailPage accession="P12345" />);
    expect(screen.getByRole("heading", { name: "P12345" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /1AO6/ })).toBeInTheDocument();
  });
});
