import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Protein } from "../../types";
import { SubcellularLocationCard } from "./subcellular-location-card";

vi.mock("@/shared/lib/api/organisms/organisms", () => ({
  useGetOrganismApiV1OrganismsOrganismIdGet: () => ({ data: { ncbi_tax_id: 83332 } }),
}));

const protein = {
  organism_id: "org-1",
  uniprot_url: "https://www.uniprot.org/uniprotkb/P12345/entry",
  comments: [
    {
      comment_type: "SUBCELLULAR LOCATION",
      payload: { subcellularLocations: [{ location: { value: "Cell membrane", id: "SL-0039" } }] },
    },
  ],
} as unknown as Protein;

describe("SubcellularLocationCard", () => {
  it("renders location names, the SwissBioPics cell diagram (taxid + SL ids), and a UniProt link", () => {
    render(<SubcellularLocationCard protein={protein} />);
    expect(screen.getByText("Cell membrane")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /cell diagram/i }).getAttribute("src")).toBe(
      "https://www.swissbiopics.org/api/83332/sl/39",
    );
    expect(screen.getByRole("link", { name: /UniProt/i })).toBeInTheDocument();
  });

  it("returns null when there is no subcellular location", () => {
    const { container } = render(<SubcellularLocationCard protein={{} as unknown as Protein} />);
    expect(container).toBeEmptyDOMElement();
  });
});
