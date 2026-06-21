import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Protein } from "../../types";
import { SubcellularLocationCard } from "./subcellular-location-card";

const protein = {
  uniprot_url: "https://www.uniprot.org/uniprotkb/P12345/entry",
  comments: [
    {
      comment_type: "SUBCELLULAR LOCATION",
      payload: { subcellularLocations: [{ location: { value: "Cell membrane" } }] },
    },
  ],
} as unknown as Protein;

describe("SubcellularLocationCard", () => {
  it("renders the location names + a link to UniProt's diagram", () => {
    render(<SubcellularLocationCard protein={protein} />);
    expect(screen.getByText("Cell membrane")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /UniProt/i })).toBeInTheDocument();
  });

  it("returns null when there is no subcellular location", () => {
    const { container } = render(<SubcellularLocationCard protein={{} as unknown as Protein} />);
    expect(container).toBeEmptyDOMElement();
  });
});
