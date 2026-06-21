import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Protein } from "../../types";
import { FeaturesSection } from "./features-section";

const protein = {
  features: [
    { feature_type: "ACT_SITE", start: 100, end: 100, description: "Proton acceptor" },
    { feature_type: "BINDING", start: 50, end: 55, description: "Substrate" },
    { feature_type: "HELIX", start: 10, end: 20 },
  ],
} as unknown as Protein;

describe("FeaturesSection", () => {
  it("renders features grouped by category with positions", () => {
    render(<FeaturesSection protein={protein} />);
    expect(screen.getByText("Proton acceptor")).toBeInTheDocument();
    expect(screen.getByText("100")).toBeInTheDocument();
    expect(screen.getByText("50..55")).toBeInTheDocument();
    expect(screen.getByText("10..20")).toBeInTheDocument();
    expect(screen.getByText(/Secondary structure/)).toBeInTheDocument();
  });

  it("returns null when there are no features", () => {
    const { container } = render(<FeaturesSection protein={{} as unknown as Protein} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("expands to show all features when truncated", () => {
    const many = {
      features: Array.from({ length: 20 }, (_, i) => ({
        feature_type: "BINDING",
        start: i + 1,
        end: i + 1,
        description: `binding-${i}`,
      })),
    } as unknown as Protein;
    render(<FeaturesSection protein={many} />);
    expect(screen.queryByText("binding-19")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Show all 20 features/i }));
    expect(screen.getByText("binding-19")).toBeInTheDocument();
  });
});
