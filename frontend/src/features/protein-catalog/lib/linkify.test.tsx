import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { linkifyPubmed } from "./linkify";

describe("linkifyPubmed", () => {
  it("turns PubMed:NNNN tokens into links while preserving surrounding text", () => {
    const { container } = render(
      <p>{linkifyPubmed("Involved in X (PubMed:19436070, PubMed:23770708).")}</p>,
    );
    const links = container.querySelectorAll("a");
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAttribute("href", "https://pubmed.ncbi.nlm.nih.gov/19436070/");
    expect(links[0]).toHaveTextContent("PubMed:19436070");
    expect(links[1]).toHaveAttribute("href", "https://pubmed.ncbi.nlm.nih.gov/23770708/");
    expect(container).toHaveTextContent("Involved in X (PubMed:19436070, PubMed:23770708).");
  });

  it("returns plain text when there are no PubMed references", () => {
    const { container } = render(<p>{linkifyPubmed("No refs here.")}</p>);
    expect(container.querySelectorAll("a")).toHaveLength(0);
    expect(container).toHaveTextContent("No refs here.");
  });
});
