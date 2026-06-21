import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/shared/lib/api/genes/genes", () => ({
  useGetGeneApiV1GenesGeneIdGet: () => ({
    data: { id: "g1", primary_name: "rpoB" },
    isLoading: false,
    isError: false,
  }),
}));

import { GeneRef } from "./gene-ref";

describe("GeneRef", () => {
  it("renders the gene name as a link to the gene page", () => {
    render(<GeneRef id="g1" />);
    const link = screen.getByRole("link", { name: /rpoB/ });
    expect(link).toHaveAttribute("href", "/genes/g1");
    // The raw id should not be shown as the visible label.
    expect(screen.queryByText("g1")).not.toBeInTheDocument();
  });

  it("renders a fallback when id is not provided", () => {
    render(<GeneRef id={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("accepts a className prop without crashing", () => {
    render(<GeneRef id="g1" className="custom-class" />);
    const link = screen.getByRole("link", { name: /rpoB/ });
    expect(link.className).toContain("custom-class");
  });
});
