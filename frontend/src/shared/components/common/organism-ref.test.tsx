import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/shared/lib/api/organisms/organisms", () => ({
  useGetOrganismApiV1OrganismsOrganismIdGet: () => ({
    data: { id: "o1", scientific_name: "Homo sapiens" },
    isLoading: false,
    isError: false,
  }),
}));

import { OrganismRef } from "./organism-ref";

describe("OrganismRef", () => {
  it("renders the scientific name as a link", () => {
    render(<OrganismRef id="o1" />);
    expect(screen.getByRole("link", { name: /Homo sapiens/ })).toHaveAttribute(
      "href",
      "/organisms/o1",
    );
  });

  it("renders a fallback when id is not provided", () => {
    render(<OrganismRef id={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("accepts a className prop without crashing", () => {
    render(<OrganismRef id="o1" className="custom-class" />);
    const link = screen.getByRole("link", { name: /Homo sapiens/ });
    expect(link).toBeInTheDocument();
    expect(link.className).toContain("custom-class");
  });
});
