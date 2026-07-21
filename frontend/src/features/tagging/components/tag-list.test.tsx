import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

// Radix Command (cmdk, used by TagMergeDialog) needs pointer-event stubs in
// jsdom. Same stub used in tag-filter.test.tsx.
beforeAll(() => {
  if (!Element.prototype.hasPointerCapture) {
    Element.prototype.hasPointerCapture = vi.fn(() => false);
  }
  if (!Element.prototype.releasePointerCapture) {
    Element.prototype.releasePointerCapture = vi.fn();
  }
});

const tags = [
  { id: "t1", key: "tier", value: "1", created_at: "2026-01-01T00:00:00Z" },
  { id: "t2", key: "priority", value: "high", created_at: "2026-02-01T00:00:00Z" },
];

const renameMutate = vi.fn();
const deleteMutate = vi.fn();
const mergeMutate = vi.fn();

vi.mock("../hooks/use-tags", () => ({
  useTags: () => ({ data: tags, isLoading: false }),
  useRenameTag: () => ({ mutate: renameMutate, isPending: false }),
  useDeleteTag: () => ({ mutate: deleteMutate, isPending: false }),
  useMergeTags: () => ({ mutate: mergeMutate, isPending: false }),
}));

const hasRole = vi.fn(() => true);
vi.mock("@sentinel-auth/nextjs", () => ({
  useAuthzHasRole: () => hasRole(),
}));

import { TagList } from "./tag-list";

describe("TagList", () => {
  beforeEach(() => {
    renameMutate.mockClear();
    deleteMutate.mockClear();
    mergeMutate.mockClear();
    hasRole.mockReturnValue(true);
  });

  it("renders each tag as a row", () => {
    render(<TagList />);
    expect(screen.getByText("tier")).toBeInTheDocument();
    expect(screen.getByText("priority")).toBeInTheDocument();
  });

  it("hides admin actions for non-admins", () => {
    hasRole.mockReturnValue(false);
    render(<TagList />);
    expect(screen.queryByRole("button", { name: /rename/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /merge/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /delete/i })).not.toBeInTheDocument();
  });

  it("Rename: opens the dialog and confirming calls useRenameTag", () => {
    render(<TagList />);
    fireEvent.click(screen.getAllByRole("button", { name: /rename/i })[0]);
    expect(screen.getByRole("heading", { name: /rename tag/i })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Key"), { target: { value: "renamed" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    expect(renameMutate).toHaveBeenCalledWith(
      { tagId: "t1", data: { key: "renamed", value: "1" } },
      expect.anything(),
    );
  });

  it("Delete: confirms then calls useDeleteTag", () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<TagList />);
    fireEvent.click(screen.getAllByRole("button", { name: /delete/i })[0]);
    expect(deleteMutate).toHaveBeenCalledWith({ tagId: "t1" });
  });

  it("Delete: does nothing when the confirm is dismissed", () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<TagList />);
    fireEvent.click(screen.getAllByRole("button", { name: /delete/i })[0]);
    expect(deleteMutate).not.toHaveBeenCalled();
  });

  it("Merge: picking a target calls useMergeTags", () => {
    render(<TagList />);
    fireEvent.click(screen.getAllByRole("button", { name: /^merge$/i })[0]);
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByRole("heading", { name: /merge tag/i })).toBeInTheDocument();

    fireEvent.click(within(dialog).getByText("priority"));
    fireEvent.click(within(dialog).getByRole("button", { name: /^merge$/i }));

    expect(mergeMutate).toHaveBeenCalledWith(
      { tagId: "t1", data: { target_tag_id: "t2" } },
      expect.anything(),
    );
  });
});
