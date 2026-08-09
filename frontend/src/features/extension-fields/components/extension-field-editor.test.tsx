import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Non-trivial logic worth its own check (ponytail: a save button that silently
// diffs a whole draft list against the server is exactly the kind of branch/loop
// a review can't eyeball) — covers: new rows create with position = index,
// unchanged rows are skipped, an edited row updates, a pure reorder still
// updates both swapped rows' positions, an invalid enum row blocks Save, and
// delete bypasses the draft entirely (immediate, not deferred to Save).

const createMutateAsync = vi.fn().mockResolvedValue(undefined);
const updateMutateAsync = vi.fn().mockResolvedValue(undefined);
const removeMutateAsync = vi.fn().mockResolvedValue(undefined);
// The component calls `remove.mutate(vars, { onSuccess })` (fire-and-forget,
// not `.mutateAsync`), so the mock needs to actually invoke that callback —
// a bare `vi.fn()` would silently swallow it and the row would never leave
// local state.
// biome-ignore lint/suspicious/noExplicitAny: mirrors TanStack Query's own loosely-typed mutate() signature
const removeMutate = vi.fn((variables: any, opts?: { onSuccess?: () => void }) => {
  removeMutateAsync(variables).then(() => opts?.onSuccess?.());
});

// biome-ignore lint/suspicious/noExplicitAny: test fixture shortcut, avoids the full ExtensionFieldDefResponse[] shape
let mockData: any[] = [];

vi.mock("../hooks/use-field-defs", () => ({
  useFieldDefs: () => ({ data: mockData, isLoading: false, isError: false }),
  useCreateFieldDef: () => ({ mutateAsync: createMutateAsync, isPending: false }),
  useUpdateFieldDef: () => ({ mutateAsync: updateMutateAsync, isPending: false }),
  useDeleteFieldDef: () => ({
    mutate: removeMutate,
    mutateAsync: removeMutateAsync,
    isPending: false,
  }),
}));

vi.mock("@/features/protein-catalog/hooks/use-target-biology-schema", () => ({
  useTargetBiologySchema: () => ({
    data: {
      provenance: { fields: [] },
      kinds: { essentiality: { label: "Essentiality", attaches_to: "gene", fields: [] } },
      concurrency: { field: "version" },
    },
  }),
}));

import { ExtensionFieldEditor } from "./extension-field-editor";

const baseField = {
  id: "f1",
  kind: "essentiality",
  name: "priority",
  label: "Priority",
  field_type: "string",
  options: null,
  position: 0,
  show_in_table: true,
  version: 1,
};

describe("ExtensionFieldEditor", () => {
  beforeEach(() => {
    createMutateAsync.mockClear();
    updateMutateAsync.mockClear();
    removeMutateAsync.mockClear();
    removeMutate.mockClear();
    mockData = [];
  });

  it("creates new rows on save, with position set from list order", async () => {
    render(<ExtensionFieldEditor kind="essentiality" />);

    fireEvent.click(screen.getByRole("button", { name: /add field/i }));
    fireEvent.click(screen.getByRole("button", { name: /add field/i }));
    const names = screen.getAllByLabelText("Name");
    const labels = screen.getAllByLabelText("Label");
    fireEvent.change(names[0], { target: { value: "first_field" } });
    fireEvent.change(labels[0], { target: { value: "First" } });
    fireEvent.change(names[1], { target: { value: "second_field" } });
    fireEvent.change(labels[1], { target: { value: "Second" } });

    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => expect(createMutateAsync).toHaveBeenCalledTimes(2));
    expect(createMutateAsync).toHaveBeenCalledWith({
      data: expect.objectContaining({ name: "first_field", position: 0 }),
    });
    expect(createMutateAsync).toHaveBeenCalledWith({
      data: expect.objectContaining({ name: "second_field", position: 1 }),
    });
    expect(updateMutateAsync).not.toHaveBeenCalled();
  });

  it("skips an untouched saved row on save", async () => {
    mockData = [baseField];
    render(<ExtensionFieldEditor kind="essentiality" />);

    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    // Nothing changed, so there is nothing to await for — assert the negative
    // stays true past a tick rather than racing the (non-existent) call.
    await waitFor(() => expect(screen.getByRole("button", { name: /^save$/i })).toBeEnabled());
    expect(updateMutateAsync).not.toHaveBeenCalled();
    expect(createMutateAsync).not.toHaveBeenCalled();
  });

  it("updates a saved row whose label changed", async () => {
    mockData = [baseField];
    render(<ExtensionFieldEditor kind="essentiality" />);

    fireEvent.change(screen.getByLabelText("Label"), { target: { value: "Renamed" } });
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => expect(updateMutateAsync).toHaveBeenCalledTimes(1));
    expect(updateMutateAsync).toHaveBeenCalledWith({
      fieldDefId: "f1",
      data: expect.objectContaining({ label: "Renamed", position: 0 }),
    });
  });

  it("reorders two saved rows and saves both new positions", async () => {
    mockData = [
      { ...baseField, id: "a", name: "a_field", label: "A", position: 0 },
      { ...baseField, id: "b", name: "b_field", label: "B", position: 1 },
    ];
    render(<ExtensionFieldEditor kind="essentiality" />);

    fireEvent.click(screen.getAllByRole("button", { name: /move down/i })[0]);
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => expect(updateMutateAsync).toHaveBeenCalledTimes(2));
    expect(updateMutateAsync).toHaveBeenCalledWith({
      fieldDefId: "a",
      data: expect.objectContaining({ position: 1 }),
    });
    expect(updateMutateAsync).toHaveBeenCalledWith({
      fieldDefId: "b",
      data: expect.objectContaining({ position: 0 }),
    });
  });

  it("disables Save when an enum row has no options", () => {
    mockData = [{ ...baseField, field_type: "enum", options: [] }];
    render(<ExtensionFieldEditor kind="essentiality" />);

    expect(screen.getByRole("button", { name: /^save$/i })).toBeDisabled();
  });

  it("deletes a saved row immediately once confirmed — not deferred to Save, and removes it from view on success", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    mockData = [baseField];
    render(<ExtensionFieldEditor kind="essentiality" />);

    fireEvent.click(screen.getByRole("button", { name: /delete/i }));

    expect(removeMutate).toHaveBeenCalledWith({ fieldDefId: "f1" }, expect.anything());
    await waitFor(() => expect(screen.queryByLabelText("Name")).not.toBeInTheDocument());
  });

  it("shows a not-found message for an unknown kind, not a crash", () => {
    render(<ExtensionFieldEditor kind="not-a-real-kind" />);
    expect(screen.getByText(/unknown record kind/i)).toBeInTheDocument();
  });
});
