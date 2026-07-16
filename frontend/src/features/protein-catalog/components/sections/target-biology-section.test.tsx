import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../../hooks/use-target-biology", () => ({
  useGeneTargetBiology: vi.fn(),
  useProteinTargetBiology: vi.fn(),
}));

import { useGeneTargetBiology, useProteinTargetBiology } from "../../hooks/use-target-biology";
import { GeneTargetBiologySection, ProteinTargetBiologySection } from "./target-biology-section";

const mockGene = useGeneTargetBiology as ReturnType<typeof vi.fn>;
const mockProtein = useProteinTargetBiology as ReturnType<typeof vi.fn>;

const prov = {
  source_type: "published",
  citations: [{ pmid: "28096490", doi: null, url: null, label: null }],
  contributor_researcher: null,
  contributor_organization_id: null,
  observed_on: null,
  note: null,
};

const emptyGene = {
  essentiality: [],
  vulnerability: [],
  hypomorph: [],
  crispri_strain: [],
  resistance_mutation: [],
};

describe("GeneTargetBiologySection", () => {
  it("renders nothing when every record group is empty", () => {
    mockGene.mockReturnValue({ data: emptyGene });
    const { container } = render(<GeneTargetBiologySection geneId="g1" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing while the bundle is still loading", () => {
    mockGene.mockReturnValue({ data: undefined });
    const { container } = render(<GeneTargetBiologySection geneId="g1" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders a populated group with headline and a linked citation", () => {
    mockGene.mockReturnValue({
      data: {
        ...emptyGene,
        vulnerability: [
          {
            id: "v1",
            gene_id: "g1",
            vulnerability_score: 0.82,
            condition: null,
            method: "CRISPRi-VI",
            confidence: null,
            provenance: prov,
            extensions: {},
          },
        ],
      },
    });
    render(<GeneTargetBiologySection geneId="g1" />);
    expect(screen.getByText("Target Biology")).toBeInTheDocument();
    expect(screen.getByText("Vulnerability")).toBeInTheDocument();
    expect(screen.getByText("0.82")).toBeInTheDocument();
    const pmid = screen.getByRole("link", { name: /PMID:28096490/ });
    expect(pmid).toHaveAttribute("href", "https://pubmed.ncbi.nlm.nih.gov/28096490/");
  });
});

describe("ProteinTargetBiologySection", () => {
  it("renders an unpublished structure with its ligand and resolution", () => {
    mockProtein.mockReturnValue({
      data: {
        protein_production: [],
        protein_activity_assay: [],
        unpublished_structure: [
          {
            id: "s1",
            protein_id: "p1",
            method: "cryo-EM",
            resolution: 2.4,
            ligands: [{ compound_id: "c1", name: "BDQ" }],
            is_published: false,
            is_experimental: true,
            provenance: { ...prov, source_type: "internal", citations: [] },
            extensions: {},
          },
        ],
      },
    });
    render(<ProteinTargetBiologySection proteinId="p1" />);
    expect(screen.getByText("Unpublished structure")).toBeInTheDocument();
    expect(screen.getByText("cryo-EM")).toBeInTheDocument();
    expect(screen.getByText("BDQ")).toBeInTheDocument();
    expect(screen.getByText("2.4 Å")).toBeInTheDocument();
  });
});
