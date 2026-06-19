import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/shared/lib/api/organisms/organisms", () => ({
  useGetOrganismApiV1OrganismsOrganismIdGet: () => ({
    data: undefined,
    isLoading: false,
    isError: false,
  }),
}));

vi.mock("../hooks/use-genes", () => ({
  useGene: () => ({
    data: {
      id: "g1",
      primary_name: "TP53",
      organism_id: "o1",
      synonyms: ["P53", "LFS1"],
      ncbi_gene_id: "7157",
      ncbi_gene_url: "https://x/7157",
      ensembl_gene_id: null,
      hgnc_id: "HGNC:11998",
      cross_references: [],
      version: 1,
    },
    isLoading: false,
    isError: false,
  }),
}));

import { GeneDetailPage } from "./gene-detail";

describe("GeneDetailPage", () => {
  it("shows the gene name and a synonym", () => {
    render(<GeneDetailPage geneId="g1" />);
    expect(screen.getByText("TP53")).toBeInTheDocument();
    expect(screen.getByText(/LFS1/)).toBeInTheDocument();
  });
});
