import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CommandPalette } from "./command-palette";

// next/navigation requires the App Router context — stub out for this test.
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

describe("CommandPalette", () => {
  it("lists navigation destinations when open", () => {
    render(<CommandPalette defaultOpen />);
    expect(screen.getByText("Proteins")).toBeInTheDocument();
    expect(screen.getByText("Targets")).toBeInTheDocument();
  });
});
