import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CommandPalette } from "./command-palette";
describe("CommandPalette", () => {
  it("lists navigation destinations when open", () => {
    render(<CommandPalette defaultOpen />);
    expect(screen.getByText("Proteins")).toBeInTheDocument();
    expect(screen.getByText("Targets")).toBeInTheDocument();
  });
});
