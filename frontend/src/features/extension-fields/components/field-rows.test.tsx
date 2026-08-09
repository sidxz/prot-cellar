import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ExtensionFieldType } from "@/shared/lib/api/model";

import type { DraftFieldRow } from "../types";
import { FieldRows } from "./field-rows";

const savedRow: DraftFieldRow = {
  key: "f1",
  id: "f1",
  name: "priority",
  label: "Priority",
  field_type: ExtensionFieldType.string,
  optionsText: "",
  show_in_table: true,
};

const newRow: DraftFieldRow = {
  key: "new-1",
  name: "",
  label: "",
  field_type: ExtensionFieldType.string,
  optionsText: "",
  show_in_table: false,
};

describe("FieldRows", () => {
  it("renders a saved row's name read-only and a new row's name editable", () => {
    render(<FieldRows rows={[savedRow, newRow]} onChange={vi.fn()} onDeleteSaved={vi.fn()} />);
    const names = screen.getAllByLabelText("Name");
    expect(names[0]).toHaveAttribute("readonly");
    expect(names[1]).not.toHaveAttribute("readonly");
  });

  it("shows the options input only for enum, and keeps it mounted (just invisible) otherwise", () => {
    const { rerender } = render(
      <FieldRows rows={[savedRow]} onChange={vi.fn()} onDeleteSaved={vi.fn()} />,
    );
    expect(screen.getByLabelText("Options")).toHaveClass("invisible");

    rerender(
      <FieldRows
        rows={[{ ...savedRow, field_type: ExtensionFieldType.enum, optionsText: "a, b" }]}
        onChange={vi.fn()}
        onDeleteSaved={vi.fn()}
      />,
    );
    const options = screen.getByLabelText("Options");
    expect(options).toHaveClass("visible");
    expect(options).not.toHaveClass("invisible");

    rerender(<FieldRows rows={[savedRow]} onChange={vi.fn()} onDeleteSaved={vi.fn()} />);
    expect(screen.getByLabelText("Options")).toHaveClass("invisible");
  });

  it("move-up swaps a row with its predecessor", () => {
    const onChange = vi.fn();
    const rowA = { ...savedRow, key: "a", id: "a", name: "a_field" };
    const rowB = { ...savedRow, key: "b", id: "b", name: "b_field" };
    render(<FieldRows rows={[rowA, rowB]} onChange={onChange} onDeleteSaved={vi.fn()} />);

    fireEvent.click(screen.getAllByRole("button", { name: /move up/i })[1]);

    expect(onChange).toHaveBeenCalledWith([rowB, rowA]);
  });

  it("move-up is disabled on the first row, move-down on the last", () => {
    const rowA = { ...savedRow, key: "a", id: "a" };
    const rowB = { ...savedRow, key: "b", id: "b" };
    render(<FieldRows rows={[rowA, rowB]} onChange={vi.fn()} onDeleteSaved={vi.fn()} />);

    expect(screen.getAllByRole("button", { name: /move up/i })[0]).toBeDisabled();
    expect(screen.getAllByRole("button", { name: /move down/i })[1]).toBeDisabled();
  });

  it("delete on a saved row confirms with the surprising half stated plainly, then delegates", () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const onDeleteSaved = vi.fn();
    render(<FieldRows rows={[savedRow]} onChange={vi.fn()} onDeleteSaved={onDeleteSaved} />);

    fireEvent.click(screen.getByRole("button", { name: /delete/i }));

    expect(window.confirm).toHaveBeenCalledWith(expect.stringMatching(/kept/i));
    expect(window.confirm).toHaveBeenCalledWith(expect.stringMatching(/unmapped/i));
    expect(onDeleteSaved).toHaveBeenCalledWith(savedRow);
  });

  it("delete on a saved row does nothing when the confirm is dismissed", () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const onDeleteSaved = vi.fn();
    render(<FieldRows rows={[savedRow]} onChange={vi.fn()} onDeleteSaved={onDeleteSaved} />);

    fireEvent.click(screen.getByRole("button", { name: /delete/i }));

    expect(onDeleteSaved).not.toHaveBeenCalled();
  });

  it("delete on a new, unsaved row skips the confirm and just removes it locally", () => {
    const confirmSpy = vi.spyOn(window, "confirm");
    const onChange = vi.fn();
    render(<FieldRows rows={[newRow]} onChange={onChange} onDeleteSaved={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: /delete/i }));

    expect(confirmSpy).not.toHaveBeenCalled();
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("renders the empty state with no rows", () => {
    render(<FieldRows rows={[]} onChange={vi.fn()} onDeleteSaved={vi.fn()} />);
    expect(screen.getByText("No fields declared yet.")).toBeInTheDocument();
  });
});
