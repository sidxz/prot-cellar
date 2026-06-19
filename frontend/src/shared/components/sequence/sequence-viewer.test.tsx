import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SequenceViewer } from "./sequence-viewer";

describe("SequenceViewer", () => {
  it("shows the residue length", () => {
    render(<SequenceViewer sequence={"ACDEFGHIK"} length={9} accession="P1" />);
    expect(screen.getByText(/9/)).toBeInTheDocument();
  });
});
