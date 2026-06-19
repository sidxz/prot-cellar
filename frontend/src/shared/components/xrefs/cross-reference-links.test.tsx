import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CrossReferenceLinks } from "./cross-reference-links";

describe("CrossReferenceLinks", () => {
  it("renders a resolvable link per xref", () => {
    render(
      <CrossReferenceLinks
        items={[{ database: "pdb", accession: "1ABC", url: "https://x/1ABC" }]}
      />,
    );
    expect(screen.getByRole("link", { name: /1ABC/ })).toHaveAttribute("href", "https://x/1ABC");
  });
});
