import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import {
  type Column,
  EditableRecordTable,
  generationMethodBadgeVariant,
} from "./editable-record-table";

interface Rec {
  id: string;
  name: string;
  count: number | null;
  active: boolean;
  kind: string;
}
type Draft = { name: string; count: string; active: boolean; kind: string };

const columns: Column<Rec, Draft>[] = [
  { label: "Name", field: "name", type: "text", placeholder: "name", render: (r) => r.name },
  { label: "Count", field: "count", type: "number", render: (r) => r.count ?? "—" },
  { label: "Active", field: "active", type: "bool", render: (r) => (r.active ? "Yes" : "No") },
  {
    label: "Kind",
    field: "kind",
    type: "enum",
    options: ["alpha", "beta"],
    render: (r) => r.kind,
  },
  { label: "Ref", render: () => "read-only" },
];
const EMPTY: Draft = { name: "", count: "", active: false, kind: "alpha" };
const toDraft = (r: Rec): Draft => ({
  name: r.name,
  count: r.count != null ? String(r.count) : "",
  active: r.active,
  kind: r.kind,
});
const toBody = (d: Draft) => ({
  name: d.name,
  count: d.count ? Number(d.count) : null,
  active: d.active,
  kind: d.kind,
});

function setup(records: Rec[]) {
  const onCreate = vi.fn().mockResolvedValue({});
  const onUpdate = vi.fn().mockResolvedValue({});
  const onDelete = vi.fn().mockResolvedValue({});
  render(
    <EditableRecordTable<Rec, Draft>
      title="Widget"
      description="desc"
      records={records}
      columns={columns}
      emptyDraft={EMPTY}
      toDraft={toDraft}
      toBody={toBody}
      onCreate={onCreate}
      onUpdate={onUpdate}
      onDelete={onDelete}
      busy={false}
    />,
  );
  return { onCreate, onUpdate, onDelete };
}

const rec: Rec = { id: "r1", name: "foo", count: 5, active: true, kind: "beta" };

describe("EditableRecordTable", () => {
  it("renders records including read-only columns", () => {
    setup([rec]);
    expect(screen.getByText("foo")).toBeInTheDocument();
    expect(screen.getByText("read-only")).toBeInTheDocument();
  });

  it("shows an empty state and an Add button", () => {
    setup([]);
    expect(screen.getByText(/no widget records yet/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add/i })).toBeInTheDocument();
  });

  it("creates via toBody when Add → Save", () => {
    const { onCreate } = setup([]);
    fireEvent.click(screen.getByRole("button", { name: /add/i }));
    fireEvent.change(screen.getByPlaceholderText("name"), { target: { value: "widgetA" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(onCreate).toHaveBeenCalledWith({
      name: "widgetA",
      count: null,
      active: false,
      kind: "alpha",
    });
  });

  it("updates the edited row on Save", () => {
    const { onUpdate } = setup([rec]);
    fireEvent.click(screen.getByRole("button", { name: /edit/i }));
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(onUpdate).toHaveBeenCalledWith("r1", {
      name: "foo",
      count: 5,
      active: true,
      kind: "beta",
    });
  });

  it("deletes after confirmation", () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const { onDelete } = setup([rec]);
    fireEvent.click(screen.getByRole("button", { name: /delete/i }));
    expect(onDelete).toHaveBeenCalledWith("r1");
  });
});

describe("generationMethodBadgeVariant", () => {
  it("colors AI methods blue (info)", () => {
    expect(generationMethodBadgeVariant("ai_extracted")).toBe("info");
    expect(generationMethodBadgeVariant("ai_predicted")).toBe("info");
  });

  it("colors imported/computed neutral (secondary)", () => {
    expect(generationMethodBadgeVariant("imported")).toBe("secondary");
    expect(generationMethodBadgeVariant("computed")).toBe("secondary");
  });

  it("colors manual / unknown / null as outline", () => {
    expect(generationMethodBadgeVariant("manual")).toBe("outline");
    expect(generationMethodBadgeVariant("nonsense")).toBe("outline");
    expect(generationMethodBadgeVariant(undefined)).toBe("outline");
    expect(generationMethodBadgeVariant(null)).toBe("outline");
  });
});
