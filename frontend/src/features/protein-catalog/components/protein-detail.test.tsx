import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/shared/lib/api/organisms/organisms", () => ({
  useGetOrganismApiV1OrganismsOrganismIdGet: () => ({
    data: undefined,
    isLoading: false,
    isError: false,
  }),
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
