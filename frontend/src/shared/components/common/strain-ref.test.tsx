import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/shared/lib/api/strains/strains", () => ({
  useGetStrainApiV1StrainsStrainIdGet: () => ({
    data: { id: "s1", name: "ATCC 25618 / H37Rv" },
    isLoading: false,
    isError: false,
  }),
}));

import { StrainRef } from "./strain-ref";

describe("StrainRef", () => {
  it("renders the strain name as a link to the strain page", () => {
    render(<StrainRef id="s1" />);
    const link = screen.getByRole("link", { name: /H37Rv/ });
    expect(link).toHaveAttribute("href", "/strains/s1");
    expect(screen.queryByText("s1")).not.toBeInTheDocument();
  });

  it("renders a fallback when id is not provided", () => {
    render(<StrainRef id={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("accepts a className prop without crashing", () => {
    render(<StrainRef id="s1" className="custom-class" />);
    const link = screen.getByRole("link", { name: /H37Rv/ });
    expect(link.className).toContain("custom-class");
  });
});
