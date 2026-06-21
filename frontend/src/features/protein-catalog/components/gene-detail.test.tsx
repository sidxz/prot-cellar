import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/shared/lib/api/organisms/organisms", () => ({
  useGetOrganismApiV1OrganismsOrganismIdGet: () => ({
    data: undefined,
    isLoading: false,
    isError: false,
  }),
}));

// The genomic-context neighborhood track reads this generated hook.
vi.mock("@/shared/lib/api/genes/genes", () => ({
  useGetGeneNeighborhoodApiV1GenesGeneIdNeighborhoodGet: vi.fn(() => ({
    data: undefined,
    isLoading: false,
    isError: false,
  })),
}));

vi.mock("../hooks/use-proteins", () => ({
  useProteins: () => ({
    data: {
      items: [
        {
          id: "p1",
          primary_accession: "P04637",
          is_reviewed: true,
          recommended_name: "Cellular tumor antigen p53",
        },
      ],
      next_cursor: null,
    },
    isLoading: false,
    isError: false,
  }),
}));

vi.mock("../hooks/use-genes", () => ({
  useGene: vi.fn(() => ({
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
      genomic_accession: "NC_000962.3",
      genomic_start: 759807,
      genomic_end: 763325,
      genomic_strand: "+",
      length_bp: 3519,
      annotations: [
        {
          axis: "vulnerability",
          key: "essentiality",
          value: "essential",
          value_type: "categorical",
          dataset: "DeJesus 2017",
        },
      ],
      version: 1,
    },
    isLoading: false,
    isError: false,
  })),
  // GenomicContextSection imports useGeneNeighborhood from this module too;
  // it must exist even though the generated hook above is what actually runs.
  useGeneNeighborhood: vi.fn(() => ({
    data: undefined,
    isLoading: false,
    isError: false,
  })),
}));

import { GeneDetailPage } from "./gene-detail";

describe("GeneDetailPage", () => {
  it("shows the gene name and a synonym", () => {
    render(<GeneDetailPage geneId="g1" />);
    expect(screen.getByText("TP53")).toBeInTheDocument();
    expect(screen.getByText(/LFS1/)).toBeInTheDocument();
  });

  it("lists linked proteins with hyperlinks to the protein page", () => {
    render(<GeneDetailPage geneId="g1" />);
    const proteinLink = screen.getByRole("link", { name: /P04637/ });
    expect(proteinLink).toHaveAttribute("href", "/proteins/P04637");
    expect(screen.getByText(/Cellular tumor antigen p53/)).toBeInTheDocument();
  });

  it("renders the genomic-context location and the vulnerability annotation", () => {
    render(<GeneDetailPage geneId="g1" />);
    expect(screen.getByText("Genomic Context")).toBeInTheDocument();
    expect(screen.getByText(/NC_000962\.3/)).toBeInTheDocument();
    expect(screen.getByText("Vulnerability")).toBeInTheDocument();
    expect(screen.getByText("essential")).toBeInTheDocument();
    expect(screen.getByText(/DeJesus 2017/)).toBeInTheDocument();
  });

  it("renders neither section for a bare gene without location or annotations", async () => {
    const { useGene } = await import("../hooks/use-genes");
    (useGene as ReturnType<typeof vi.fn>).mockReturnValueOnce({
      data: {
        id: "g2",
        primary_name: "minimal",
        organism_id: "o1",
        synonyms: [],
        cross_references: [],
        annotations: [],
        version: 1,
      },
      isLoading: false,
      isError: false,
    });

    render(<GeneDetailPage geneId="g2" />);
    expect(screen.queryByText("Genomic Context")).not.toBeInTheDocument();
    expect(screen.queryByText("Vulnerability")).not.toBeInTheDocument();
  });
});
