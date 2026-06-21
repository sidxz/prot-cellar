import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Gene } from "../../types";
import {
  AXIS_TITLES,
  AxisAnnotationsSection,
  essentialityBadgeVariant,
} from "./axis-annotations-section";

const gene = {
  annotations: [
    {
      axis: "vulnerability",
      key: "essentiality",
      value: "essential",
      value_type: "categorical",
      dataset: "DeJesus 2017",
      condition: "in vitro 7H9",
      evidence: "PMID:28096490",
      source_url: "https://example.org/dejesus",
    },
    // An annotation on a different axis must be filtered out.
    {
      axis: "context",
      key: "functional_category",
      value: "Cell wall",
      value_type: "categorical",
    },
  ],
} as unknown as Gene;

describe("AxisAnnotationsSection", () => {
  it("renders the vulnerability value + dataset/condition subline", () => {
    render(<AxisAnnotationsSection gene={gene} axis="vulnerability" title="Vulnerability" />);
    expect(screen.getByText("essential")).toBeInTheDocument();
    expect(screen.getByText(/DeJesus 2017/)).toBeInTheDocument();
    expect(screen.getByText(/in vitro 7H9/)).toBeInTheDocument();
    // Title renders.
    expect(screen.getByText("Vulnerability")).toBeInTheDocument();
  });

  it("links to source_url when present", () => {
    render(<AxisAnnotationsSection gene={gene} axis="vulnerability" title="Vulnerability" />);
    const link = screen.getByRole("link", { name: /essential/ });
    expect(link).toHaveAttribute("href", "https://example.org/dejesus");
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("color-codes an `essential` essentiality value with the destructive variant", () => {
    render(<AxisAnnotationsSection gene={gene} axis="vulnerability" title="Vulnerability" />);
    // The chip renders as a Badge that exposes `data-variant`; the test gene has
    // a source_url so the badge is the anchor's nearest [data-slot="badge"].
    const link = screen.getByRole("link", { name: /essential/ });
    const badge = link.closest('[data-slot="badge"]');
    expect(badge).not.toBeNull();
    expect(badge).toHaveAttribute("data-variant", "destructive");
    // The destructive token class is applied (red triage signal).
    expect(badge?.className).toContain("bg-destructive");
  });

  it("maps essentiality values to the expected Badge variants", () => {
    expect(essentialityBadgeVariant("essential")).toBe("destructive");
    expect(essentialityBadgeVariant("growth-defect")).toBe("warning");
    expect(essentialityBadgeVariant("non-essential")).toBe("secondary");
    expect(essentialityBadgeVariant("growth-advantage")).toBe("outline");
    expect(essentialityBadgeVariant("uncertain")).toBe("ghost");
    expect(essentialityBadgeVariant(null)).toBe("ghost");
  });

  it("filters out annotations on other axes", () => {
    render(<AxisAnnotationsSection gene={gene} axis="vulnerability" title="Vulnerability" />);
    expect(screen.queryByText("Cell wall")).not.toBeInTheDocument();
  });

  it("returns null when no annotation matches the axis", () => {
    const { container } = render(
      <AxisAnnotationsSection
        gene={{ annotations: [] } as unknown as Gene}
        axis="vulnerability"
        title="Vulnerability"
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("exposes a title map for reuse", () => {
    expect(AXIS_TITLES.vulnerability).toBe("Vulnerability");
    expect(AXIS_TITLES.context).toBe("Genomic context");
  });
});
