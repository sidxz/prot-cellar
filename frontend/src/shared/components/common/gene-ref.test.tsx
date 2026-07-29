import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/shared/lib/api/genes/genes", () => ({
  // Distinct symbol vs locus: GeneRef is a protein-context ref, so it must show
  // the symbol (primary_name), NOT the locus lead (display_label).
  useGetGeneApiV1GenesGeneIdGet: () => ({
    data: { id: "g1", primary_name: "rho", display_label: "Rv1297" },
    isLoading: false,
    isError: false,
  }),
}));

import { GeneRef } from "./gene-ref";

describe("GeneRef", () => {
  it("renders the gene symbol (not the locus lead) as a link to the gene page", () => {
    render(<GeneRef id="g1" />);
    const link = screen.getByRole("link", { name: /rho/ });
    expect(link).toHaveAttribute("href", "/genes/g1");
    // Protein context leads with the symbol; the locus tag must NOT be the label here.
    expect(screen.queryByText("Rv1297")).not.toBeInTheDocument();
    // The raw id should not be shown as the visible label.
    expect(screen.queryByText("g1")).not.toBeInTheDocument();
  });

  it("renders a fallback when id is not provided", () => {
    render(<GeneRef id={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("accepts a className prop without crashing", () => {
    render(<GeneRef id="g1" className="custom-class" />);
    const link = screen.getByRole("link", { name: /rho/ });
    expect(link.className).toContain("custom-class");
  });
});
