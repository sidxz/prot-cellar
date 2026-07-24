import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ResistanceLollipop } from "./resistance-lollipop";
import type { MutationLike } from "./resistance";

const rec = (over: Partial<MutationLike>): MutationLike =>
  ({
    id: "x",
    gene_id: "g",
    mutation: "S315T",
    compound: null,
    mic_shift: null,
    parent_strain: null,
    protein_coordinate: null,
    method: null,
    provenance: {},
    extensions: null,
    ...over,
  }) as unknown as MutationLike;

describe("ResistanceLollipop", () => {
  it("renders nothing with fewer than 2 positioned mutations", () => {
    const { container } = render(<ResistanceLollipop records={[rec({ mutation: "S315T" })]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders a needle per mutation with its label and a compound legend", () => {
    render(
      <ResistanceLollipop
        records={[
          rec({ mutation: "S315T", mic_shift: 200, compound: { name: "INH" } }),
          rec({ mutation: "M306V", mic_shift: 64, compound: { name: "EMB" } }),
        ]}
      />,
    );
    expect(screen.getByTestId("resistance-lollipop")).toBeInTheDocument();
    expect(screen.getByText("S315T")).toBeInTheDocument();
    expect(screen.getByText("M306V")).toBeInTheDocument();
    expect(screen.getByText("INH")).toBeInTheDocument();
    expect(screen.getByText("EMB")).toBeInTheDocument();
  });
});
