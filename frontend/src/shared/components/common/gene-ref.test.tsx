import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/shared/lib/api/genes/genes", () => ({
  // Distinct symbol vs locus: GeneRef leads with the preferred display name
  // (the locus), keeping the symbol as a secondary.
  useGetGeneApiV1GenesGeneIdGet: () => ({
    data: { id: "g1", primary_name: "rho", display_label: "Rv1297" },
    isLoading: false,
    isError: false,
  }),
}));

import { GeneRef } from "./gene-ref";

describe("GeneRef", () => {
  it("leads with the preferred display name, keeps the symbol, links to the gene page", () => {
    render(<GeneRef id="g1" />);
    const link = screen.getByRole("link", { name: /Rv1297/ });
    expect(link).toHaveAttribute("href", "/genes/g1");
    // The preferred name leads; the symbol is still shown as a secondary.
    expect(link).toHaveTextContent("Rv1297");
    expect(link).toHaveTextContent("rho");
    // The raw id should not be shown as the visible label.
    expect(screen.queryByText("g1")).not.toBeInTheDocument();
  });

  it("renders a fallback when id is not provided", () => {
    render(<GeneRef id={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("accepts a className prop without crashing", () => {
    render(<GeneRef id="g1" className="custom-class" />);
    const link = screen.getByRole("link", { name: /Rv1297/ });
    expect(link.className).toContain("custom-class");
  });
});
