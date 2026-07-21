import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";

// Radix Popover needs pointer-event stubs in jsdom (scrollIntoView / ResizeObserver
// are already polyfilled globally in vitest.setup.ts). Same stub used in
// tags-relation.test.tsx for the same reason.
beforeAll(() => {
  if (!Element.prototype.hasPointerCapture) {
    Element.prototype.hasPointerCapture = vi.fn(() => false);
  }
  if (!Element.prototype.releasePointerCapture) {
    Element.prototype.releasePointerCapture = vi.fn();
  }
});

vi.mock("../hooks/use-tags", () => ({
  useTags: () => ({
    data: [
      { id: "t1", key: "tier", value: "1" },
      { id: "t2", key: "priority", value: "high" },
    ],
  }),
}));

import { TagFilter, type TagFilterValue } from "./tag-filter";

function setup(value: TagFilterValue = { tagIds: [], tagLogic: "any" }) {
  const onChange = vi.fn();
  render(<TagFilter value={value} onChange={onChange} />);
  fireEvent.click(screen.getByRole("button", { name: /tags/i }));
  return onChange;
}

describe("TagFilter", () => {
  it("selecting a tag calls onChange with the chosen tagIds", () => {
    const onChange = setup();

    fireEvent.click(screen.getByText("tier"));

    expect(onChange).toHaveBeenCalledWith({ tagIds: ["t1"], tagLogic: "any" });
  });

  it("toggling any/all updates tagLogic", () => {
    const onChange = setup({ tagIds: ["t1", "t2"], tagLogic: "any" });

    fireEvent.click(screen.getByRole("button", { name: "all" }));

    expect(onChange).toHaveBeenCalledWith({ tagIds: ["t1", "t2"], tagLogic: "all" });
  });

  it("clear resets the tag selection", () => {
    const onChange = setup({ tagIds: ["t1"], tagLogic: "all" });

    fireEvent.click(screen.getByText("Clear tag filter"));

    expect(onChange).toHaveBeenCalledWith({ tagIds: [], tagLogic: "all" });
  });
});
