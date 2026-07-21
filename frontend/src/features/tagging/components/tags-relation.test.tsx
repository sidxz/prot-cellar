import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";

// Radix Popover needs pointer-event stubs in jsdom (scrollIntoView / ResizeObserver
// are already polyfilled globally in vitest.setup.ts).
beforeAll(() => {
  if (!Element.prototype.hasPointerCapture) {
    Element.prototype.hasPointerCapture = vi.fn(() => false);
  }
  if (!Element.prototype.releasePointerCapture) {
    Element.prototype.releasePointerCapture = vi.fn();
  }
});

const useEntityTagsMock = vi.fn();
const assignMutate = vi.fn();
const unassignMutate = vi.fn();

vi.mock("../hooks/use-entity-tags", () => ({
  useEntityTags: (...args: unknown[]) => useEntityTagsMock(...args),
  useAssignTag: () => ({ mutate: assignMutate, isPending: false }),
  useUnassignTag: () => ({ mutate: unassignMutate, isPending: false }),
}));

// TagAutocomplete pulls suggestions from useTags — stub to an empty list so
// the suggestion dropdown never opens during these interactions.
vi.mock("../hooks/use-tags", () => ({
  useTags: () => ({ data: [] }),
}));

import { TagsRelation } from "./tags-relation";

describe("TagsRelation", () => {
  it("renders existing tags as chips", () => {
    useEntityTagsMock.mockReturnValue({
      data: [
        {
          id: "t1",
          key: "tier",
          value: "1",
          workspace_id: "w1",
          created_by: "u1",
          created_at: "now",
          assigned_by: "u1",
          assigned_at: "now",
        },
      ],
    });

    render(<TagsRelation entity="proteins" id="p1" />);

    expect(screen.getByText("tier")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("shows an empty state when there are no tags", () => {
    useEntityTagsMock.mockReturnValue({ data: [] });

    render(<TagsRelation entity="proteins" id="p1" />);

    expect(screen.getByText("No tags")).toBeInTheDocument();
  });

  it("calls unassign with the entity/id/tagId when a chip's remove button is clicked", () => {
    unassignMutate.mockClear();
    useEntityTagsMock.mockReturnValue({
      data: [{ id: "t1", key: "tier", value: "1" }],
    });

    render(<TagsRelation entity="proteins" id="p1" />);
    fireEvent.click(screen.getByRole("button", { name: "Remove tier=1" }));

    expect(unassignMutate).toHaveBeenCalledWith({
      entityCollection: "proteins",
      entityId: "p1",
      tagId: "t1",
    });
  });

  it("assigns a new key=value tag from the + Tag popover", () => {
    assignMutate.mockClear();
    useEntityTagsMock.mockReturnValue({ data: [] });

    render(<TagsRelation entity="proteins" id="p1" />);

    fireEvent.click(screen.getByRole("button", { name: "Add tag" }));
    fireEvent.change(screen.getByPlaceholderText("key"), {
      target: { value: "priority" },
    });
    fireEvent.change(screen.getByPlaceholderText("value (optional)"), {
      target: { value: "high" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save tag" }));

    expect(assignMutate).toHaveBeenCalledTimes(1);
    expect(assignMutate.mock.calls[0][0]).toEqual({
      entityCollection: "proteins",
      entityId: "p1",
      data: { key: "priority", value: "high" },
    });
  });

  it("commits with a null value when only a key is entered", () => {
    assignMutate.mockClear();
    useEntityTagsMock.mockReturnValue({ data: [] });

    render(<TagsRelation entity="genes" id="g1" />);

    fireEvent.click(screen.getByRole("button", { name: "Add tag" }));
    fireEvent.change(screen.getByPlaceholderText("key"), {
      target: { value: "reviewed" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save tag" }));

    expect(assignMutate.mock.calls[0][0]).toEqual({
      entityCollection: "genes",
      entityId: "g1",
      data: { key: "reviewed", value: null },
    });
  });
});
