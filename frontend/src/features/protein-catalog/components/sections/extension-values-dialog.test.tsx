import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ExtensionValuesDialog } from "./extension-values-dialog";

const FIELDS = [
  { name: "priority", label: "Priority", type: "string", required: false, show_in_table: true },
  { name: "notes", label: "Notes", type: "text", required: false, show_in_table: false },
  { name: "score", label: "Score", type: "number", required: false, show_in_table: false },
  { name: "rank", label: "Rank", type: "integer", required: false, show_in_table: false },
  { name: "reviewed", label: "Reviewed", type: "boolean", required: false, show_in_table: false },
  {
    name: "checked_on",
    label: "Checked on",
    type: "date",
    required: false,
    show_in_table: false,
  },
  {
    name: "tier",
    label: "Tier",
    type: "enum",
    required: false,
    show_in_table: false,
    options: ["gold", "silver", "bronze"],
  },
];

const EXISTING = {
  priority: "high",
  notes: "from the SI",
  score: 0.5,
  rank: 3,
  reviewed: true,
  checked_on: "2021-03-01",
  tier: "gold",
};

describe("ExtensionValuesDialog", () => {
  it("renders one control per declared field, matching its type", () => {
    render(
      <ExtensionValuesDialog
        open
        fields={FIELDS}
        value={EXISTING}
        onSave={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("Priority").tagName).toBe("INPUT"); // string → Input
    expect(screen.getByLabelText("Notes").tagName).toBe("TEXTAREA"); // text → Textarea
    expect(screen.getByLabelText("Score")).toHaveAttribute("type", "number");
    expect(screen.getByLabelText("Score")).toHaveAttribute("step", "any");
    expect(screen.getByLabelText("Rank")).toHaveAttribute("type", "number");
    expect(screen.getByLabelText("Rank")).toHaveAttribute("step", "1"); // integer → whole steps
    expect(screen.getByLabelText("Reviewed")).toHaveAttribute("role", "checkbox"); // boolean → Checkbox
    expect(screen.getByLabelText("Checked on")).toHaveAttribute("type", "date");
    expect(screen.getByRole("combobox", { name: /tier/i })).toBeInTheDocument(); // enum → Select
  });

  it("seeds each control from the record's current extensions", () => {
    render(
      <ExtensionValuesDialog
        open
        fields={FIELDS}
        value={EXISTING}
        onSave={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("Priority")).toHaveValue("high");
    expect(screen.getByLabelText("Reviewed")).toBeChecked();
  });

  it("treats an untouched save as a no-op — close without submitting", () => {
    const onSave = vi.fn();
    const onClose = vi.fn();
    render(
      <ExtensionValuesDialog
        open
        fields={FIELDS}
        value={EXISTING}
        onSave={onSave}
        onClose={onClose}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(onSave).not.toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it("submits only the field that changed", () => {
    const onSave = vi.fn();
    render(
      <ExtensionValuesDialog
        open
        fields={FIELDS}
        value={EXISTING}
        onSave={onSave}
        onClose={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByLabelText("Priority"), { target: { value: "low" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(onSave).toHaveBeenCalledWith({ priority: "low" });
  });

  it("clears a populated field by sending null, not the stale value", () => {
    const onSave = vi.fn();
    render(
      <ExtensionValuesDialog
        open
        fields={FIELDS}
        value={EXISTING}
        onSave={onSave}
        onClose={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByLabelText("Notes"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(onSave).toHaveBeenCalledWith({ notes: null });
  });

  it("unchecking a boolean submits false, not null — a checkbox has no unset state", () => {
    const onSave = vi.fn();
    render(
      <ExtensionValuesDialog
        open
        fields={FIELDS}
        value={EXISTING}
        onSave={onSave}
        onClose={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByLabelText("Reviewed"));
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(onSave).toHaveBeenCalledWith({ reviewed: false });
  });

  it("leaves a field nobody declared a value for out of the submitted changes", () => {
    const onSave = vi.fn();
    render(
      <ExtensionValuesDialog
        open
        fields={FIELDS}
        value={{ priority: "high" }}
        onSave={onSave}
        onClose={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByLabelText("Priority"), { target: { value: "low" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(onSave).toHaveBeenCalledWith({ priority: "low" });
  });

  it("has an explicit cancel alongside save", () => {
    render(
      <ExtensionValuesDialog
        open
        fields={FIELDS}
        value={EXISTING}
        onSave={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save/i })).toBeInTheDocument();
  });

  it("disables save and cancel while busy, and shows a saving indicator", () => {
    render(
      <ExtensionValuesDialog
        open
        fields={FIELDS}
        value={EXISTING}
        busy
        onSave={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /saving/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /cancel/i })).toBeDisabled();
  });
});
