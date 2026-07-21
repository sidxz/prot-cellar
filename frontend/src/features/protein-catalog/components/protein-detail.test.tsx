import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/shared/lib/api/organisms/organisms", () => ({
  useGetOrganismApiV1OrganismsOrganismIdGet: () => ({
    data: undefined,
    isLoading: false,
    isError: false,
  }),
}));

// GeneRef resolves a gene id to its human-readable name via this hook.
vi.mock("@/shared/lib/api/genes/genes", () => ({
  useGetGeneApiV1GenesGeneIdGet: () => ({
    data: { id: "g1", primary_name: "rpoB" },
    isLoading: false,
    isError: false,
  }),
}));

// StrainRef resolves a strain id to its name via this hook.
vi.mock("@/shared/lib/api/strains/strains", () => ({
  useGetStrainApiV1StrainsStrainIdGet: () => ({
    data: { id: "s1", name: "ATCC 25618 / H37Rv" },
    isLoading: false,
    isError: false,
  }),
}));

vi.mock("../hooks/use-target-biology", () => ({
  useProteinTargetBiology: vi.fn(() => ({ data: undefined })),
}));

// TagsRelation has its own dedicated test suite; stub it here so this test
// stays focused on the protein detail chrome (no QueryClient wiring needed).
vi.mock("@/features/tagging", () => ({
  TagsRelation: () => null,
}));

// ── Happy-path mock (primary fetch succeeds) ──────────────────────────────
vi.mock("../hooks/use-proteins", () => ({
  useProtein: vi.fn(() => ({
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
  })),
  useProteinFasta: vi.fn(() => ({
    data: { header: "sp|P12345|ALBU_HUMAN", sequence: "MAAAKLL" },
    isLoading: false,
    isError: false,
  })),
  useResolveProtein: vi.fn(() => ({
    data: undefined,
    isLoading: false,
    isError: false,
  })),
}));

vi.mock("next/navigation", () => ({
  useRouter: vi.fn(() => ({
    replace: vi.fn(),
    push: vi.fn(),
  })),
}));

import { ProteinDetailPage } from "./protein-detail";

describe("ProteinDetailPage", () => {
  it("shows the accession and a cross-reference link", () => {
    render(<ProteinDetailPage accession="P12345" />);
    expect(screen.getByRole("heading", { name: "P12345" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /1AO6/ })).toBeInTheDocument();
  });

  it("links the gene by its name rather than its raw id", async () => {
    const { useProtein } = await import("../hooks/use-proteins");
    (useProtein as ReturnType<typeof vi.fn>).mockReturnValue({
      data: {
        id: "1",
        primary_accession: "P12345",
        entry_name: "ALBU_HUMAN",
        is_reviewed: true,
        seq_length: 7,
        seq_mass: 800,
        organism_id: "o1",
        gene_id: "g1",
        protein_names: { recommended: "Albumin" },
        secondary_accessions: [],
        keywords: [],
        cross_references: [],
        version: 1,
      },
      isLoading: false,
      isError: false,
    });

    render(<ProteinDetailPage accession="P12345" />);

    const geneLink = screen.getByRole("link", { name: /rpoB/ });
    expect(geneLink).toHaveAttribute("href", "/genes/g1");
    expect(screen.queryByText("g1")).not.toBeInTheDocument();
  });

  it("links the strain by its name when the protein has a strain", async () => {
    const { useProtein } = await import("../hooks/use-proteins");
    (useProtein as ReturnType<typeof vi.fn>).mockReturnValue({
      data: {
        id: "1",
        primary_accession: "P12345",
        entry_name: "ALBU_HUMAN",
        is_reviewed: true,
        seq_length: 7,
        seq_mass: 800,
        organism_id: "o1",
        strain_id: "s1",
        gene_id: null,
        protein_names: { recommended: "Albumin" },
        secondary_accessions: [],
        keywords: [],
        cross_references: [],
        version: 1,
      },
      isLoading: false,
      isError: false,
    });

    render(<ProteinDetailPage accession="P12345" />);

    const strainLink = screen.getByRole("link", { name: /H37Rv/ });
    expect(strainLink).toHaveAttribute("href", "/strains/s1");
  });

  it("redirects to the canonical accession when the resolve fallback succeeds", async () => {
    const { useProtein, useResolveProtein } = await import("../hooks/use-proteins");
    const { useRouter } = await import("next/navigation");

    const replaceSpy = vi.fn();
    (useRouter as ReturnType<typeof vi.fn>).mockReturnValue({ replace: replaceSpy, push: vi.fn() });

    // Primary fetch: not found
    (useProtein as ReturnType<typeof vi.fn>).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    });

    // Resolve fallback: returns canonical accession
    (useResolveProtein as ReturnType<typeof vi.fn>).mockReturnValue({
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
        keywords: [],
        cross_references: [],
        version: 1,
      },
      isLoading: false,
      isError: false,
    });

    render(<ProteinDetailPage accession="ALBU_HUMAN" />);

    expect(replaceSpy).toHaveBeenCalledWith("/proteins/P12345");
  });
});
