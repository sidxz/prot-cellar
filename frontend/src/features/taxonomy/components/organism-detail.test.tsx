import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../hooks/use-organisms", () => ({
  useOrganism: () => ({
    data: {
      id: "9606",
      scientific_name: "Homo sapiens",
      rank: "species",
      ncbi_tax_id: 9606,
      ncbi_url: "https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=9606",
      source: "ncbi",
      parent_id: null,
      division: "Primates",
      source_release: "2024-01",
      is_merged: false,
      is_deleted: false,
      merged_into_id: null,
      version: 1,
      names: [
        { name: "Homo sapiens", name_class: "scientific_name", is_preferred: true },
        { name: "human", name_class: "common_name", is_preferred: false },
      ],
    },
    isLoading: false,
    isError: false,
  }),
  useOrganismLineage: () => ({ data: [], isLoading: false, isError: false }),
}));

import { OrganismDetailPage } from "./organism-detail";

describe("OrganismDetailPage", () => {
  it("shows the scientific name heading and a names-table entry", () => {
    render(<OrganismDetailPage organismId="9606" />);
    expect(screen.getByRole("heading", { name: "Homo sapiens" })).toBeInTheDocument();
    expect(screen.getByText("Scientific name")).toBeInTheDocument();
  });
});
