import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EssentialityCallScale } from "./essentiality-call-scale";
import type { EssentialityLike } from "./essentiality";

const rec = (over: Partial<EssentialityLike>): EssentialityLike =>
  ({
    id: "x",
    gene_id: "g",
    classification: "essential",
    condition: null,
    method: null,
    confidence: null,
    provenance: {},
    extensions: null,
    ...over,
  }) as unknown as EssentialityLike;

describe("EssentialityCallScale", () => {
  it("renders nothing without records", () => {
    const { container } = render(<EssentialityCallScale records={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the consensus call and its confidence for a single record", () => {
    render(
      <EssentialityCallScale records={[rec({ classification: "essential", confidence: 0.87 })]} />,
    );
    expect(screen.getByTestId("ess-consensus-call")).toHaveTextContent(/essential/i);
    expect(screen.getByText("0.87")).toBeInTheDocument();
  });

  it("does not show the condition strip for a single record", () => {
    render(<EssentialityCallScale records={[rec({ classification: "essential" })]} />);
    expect(screen.queryByTestId("ess-condition-strip")).not.toBeInTheDocument();
  });

  it("flags disagreement across sources and shows the condition strip", () => {
    render(
      <EssentialityCallScale
        records={[
          rec({ classification: "essential", condition: "7H9", method: "TnSeq", confidence: 0.9 }),
          rec({ classification: "growth_defect", condition: "cholesterol", method: "TnSeq" }),
        ]}
      />,
    );
    const strip = screen.getByTestId("ess-condition-strip");
    expect(strip).toBeInTheDocument();
    expect(screen.getByText("7H9")).toBeInTheDocument();
    expect(screen.getByText("cholesterol")).toBeInTheDocument();
    expect(screen.getByText(/disagree/i)).toBeInTheDocument();
  });

  it("reports agreement when multiple sources concur", () => {
    render(
      <EssentialityCallScale
        records={[
          rec({ classification: "essential", condition: "7H9", method: "TnSeq" }),
          rec({ classification: "essential", condition: "7H9", method: "CRISPRi" }),
        ]}
      />,
    );
    expect(screen.getByText(/agree/i)).toBeInTheDocument();
  });
});
