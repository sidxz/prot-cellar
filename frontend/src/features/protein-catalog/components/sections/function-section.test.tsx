import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { CommentResponse } from "@/shared/lib/api/model";
import type { Protein } from "../../types";
import { FunctionSection, commentLines } from "./function-section";

const protein = {
  comments: [
    { comment_type: "FUNCTION", text: "Catalyzes the oxidation of X." },
    { comment_type: "CATALYTIC ACTIVITY", payload: { reaction: { name: "X + O2 = Y" } } },
    { comment_type: "COFACTOR", payload: { cofactors: [{ name: "Mg(2+)" }, { name: "Zn(2+)" }] } },
  ],
} as unknown as Protein;

describe("FunctionSection", () => {
  it("renders function text, catalytic reaction, and cofactors", () => {
    render(<FunctionSection protein={protein} />);
    expect(screen.getByText(/Catalyzes the oxidation of X/)).toBeInTheDocument();
    expect(screen.getByText(/X \+ O2 = Y/)).toBeInTheDocument();
    expect(screen.getByText(/Cofactors: Mg\(2\+\), Zn\(2\+\)/)).toBeInTheDocument();
  });

  it("returns null when there are no function comments", () => {
    const { container } = render(<FunctionSection protein={{} as unknown as Protein} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("commentLines", () => {
  it("extracts free text", () => {
    expect(commentLines({ comment_type: "FUNCTION", text: "abc" } as CommentResponse)).toEqual([
      "abc",
    ]);
  });

  it("extracts a catalytic reaction name from the payload", () => {
    expect(
      commentLines({
        comment_type: "CATALYTIC ACTIVITY",
        payload: { reaction: { name: "A = B" } },
      } as unknown as CommentResponse),
    ).toEqual(["A = B"]);
  });
});
