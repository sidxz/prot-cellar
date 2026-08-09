import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import type { FieldDescriptor } from "../../hooks/use-target-biology-schema";
import {
  type Column,
  EditableRecordTable,
  ProvenanceLegend,
  defaultProvenance,
  extensionColumns,
  generationMethodBadgeVariant,
  isAiGenerated,
} from "./editable-record-table";

// Radix Popover needs pointer-event stubs in jsdom (scrollIntoView / ResizeObserver
// are already polyfilled globally in vitest.setup.ts). Same stub used in
// tag-filter.test.tsx for the same reason.
beforeAll(() => {
  if (!Element.prototype.hasPointerCapture) {
    Element.prototype.hasPointerCapture = vi.fn(() => false);
  }
  if (!Element.prototype.releasePointerCapture) {
    Element.prototype.releasePointerCapture = vi.fn();
  }
});

interface Rec {
  id: string;
  name: string;
  count: number | null;
  active: boolean;
  kind: string;
  version: number;
  provenance: Record<string, unknown>;
  is_shared?: boolean;
  extensions?: Record<string, unknown>;
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

const rec: Rec = {
  id: "r1",
  name: "foo",
  count: 5,
  active: true,
  kind: "beta",
  version: 1,
  provenance: {},
};

describe("EditableRecordTable", () => {
  it("renders records including read-only columns", () => {
    setup([rec]);
    expect(screen.getByText("foo")).toBeInTheDocument();
    expect(screen.getByText("read-only")).toBeInTheDocument();
  });

  it("renders the visualization slot inside the section", () => {
    render(
      <EditableRecordTable<Rec, Draft>
        title="Widget"
        description="desc"
        records={[rec]}
        columns={columns}
        emptyDraft={EMPTY}
        toDraft={toDraft}
        toBody={toBody}
        onCreate={vi.fn()}
        onUpdate={vi.fn()}
        onDelete={vi.fn()}
        busy={false}
        visualization={<div data-testid="viz">chart</div>}
      />,
    );
    const section = screen.getByRole("region", { name: "Widget" });
    expect(section).toContainElement(screen.getByTestId("viz"));
  });

  it("renders AI-provenance rows in dark blue", () => {
    render(
      <EditableRecordTable<Rec, Draft>
        title="Widget"
        description="desc"
        records={[rec]}
        columns={columns}
        emptyDraft={EMPTY}
        toDraft={toDraft}
        toBody={toBody}
        onCreate={vi.fn()}
        onUpdate={vi.fn()}
        onDelete={vi.fn()}
        busy={false}
        isAiRow={() => true}
      />,
    );
    expect(screen.getByText("foo").closest("tr")?.className).toMatch(/text-blue-700/);
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

  it("hides edit/provenance/delete for a shared row and shows a reference-data marker instead", () => {
    setup([{ ...rec, is_shared: true }]);
    expect(screen.queryByRole("button", { name: /edit/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /provenance/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /delete/i })).not.toBeInTheDocument();
    expect(screen.getByText(/managed by import/i)).toBeInTheDocument();
  });

  it("shows edit/provenance/delete for a row that is not shared", () => {
    setup([{ ...rec, is_shared: false }]);
    expect(screen.getByRole("button", { name: /edit/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /provenance/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /delete/i })).toBeInTheDocument();
    expect(screen.queryByText(/managed by import/i)).not.toBeInTheDocument();
  });
});

// A workspace with two declarations for this kind: one shown as a column, one not.
const EXT_FIELDS: FieldDescriptor[] = [
  { name: "priority", label: "Priority", type: "string", required: false, show_in_table: true },
  {
    name: "internal_note",
    label: "Internal note",
    type: "text",
    required: false,
    show_in_table: false,
  },
];

function renderWithExtensions(record: Rec, onUpdate = vi.fn().mockResolvedValue({})) {
  render(
    <EditableRecordTable<Rec, Draft>
      title="Widget"
      description="desc"
      records={[record]}
      columns={[...columns, ...extensionColumns<Rec>(EXT_FIELDS)]}
      emptyDraft={EMPTY}
      toDraft={toDraft}
      toBody={toBody}
      onCreate={vi.fn()}
      onUpdate={onUpdate}
      onDelete={vi.fn()}
      busy={false}
      extensionFields={EXT_FIELDS}
    />,
  );
  return { onUpdate };
}

describe("EditableRecordTable extension fields", () => {
  it("renders a show_in_table declaration as a column and omits one that isn't", () => {
    renderWithExtensions({ ...rec, extensions: { priority: "high", internal_note: "hush" } });

    expect(screen.getByRole("columnheader", { name: "Priority" })).toBeInTheDocument();
    expect(screen.getByText("high")).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Internal note" })).not.toBeInTheDocument();
  });

  it("shows an unmapped stored key in the detail popover, not as a column", () => {
    renderWithExtensions({ ...rec, extensions: { priority: "high", legacy_flag: "yes" } });

    expect(screen.queryByRole("columnheader", { name: /legacy_flag/i })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /extension values/i }));
    expect(screen.getByText("legacy_flag")).toBeInTheDocument();
    expect(screen.getByText("yes")).toBeInTheDocument();
    expect(screen.getByText("Unmapped")).toBeInTheDocument();
    // Every declared field is listed too, not just the ones that are columns.
    expect(screen.getByText("Internal note")).toBeInTheDocument();
  });

  it("shows extension values with no edit affordance on a shared row", () => {
    renderWithExtensions({
      ...rec,
      is_shared: true,
      extensions: { priority: "high", legacy_flag: "yes" },
    });

    // The show_in_table column still renders for a shared row...
    expect(screen.getByText("high")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /extension values/i }));
    expect(screen.getByText("legacy_flag")).toBeInTheDocument();
    // ...but nothing about it is editable: the detail has no form controls, and
    // the ordinary mutate buttons stay hidden exactly as they do without extensions,
    // including the Extra fields… action that would otherwise open an edit dialog.
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^edit$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /extra fields/i })).not.toBeInTheDocument();
  });

  it("opens the Extra fields… dialog for a non-shared row and submits only the changed key", () => {
    const { onUpdate } = renderWithExtensions({ ...rec, extensions: { priority: "high" } });

    fireEvent.click(screen.getByRole("button", { name: /extra fields/i }));
    expect(screen.getByRole("heading", { name: "Extra fields" })).toBeInTheDocument();
    // Every declared field gets a control, not just the one shown as a column.
    expect(screen.getByLabelText("Internal note")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Priority"), { target: { value: "low" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    expect(onUpdate).toHaveBeenCalledWith("r1", {
      extensions: { priority: "low" },
      version: 1,
    });
  });

  it("hides the detail trigger entirely when there is nothing to show", () => {
    render(
      <EditableRecordTable<Rec, Draft>
        title="Widget"
        description="desc"
        records={[{ ...rec, extensions: {} }]}
        columns={columns}
        emptyDraft={EMPTY}
        toDraft={toDraft}
        toBody={toBody}
        onCreate={vi.fn()}
        onUpdate={vi.fn()}
        onDelete={vi.fn()}
        busy={false}
      />,
    );
    expect(screen.queryByRole("button", { name: /extension values/i })).not.toBeInTheDocument();
  });
});

describe("extensionColumns", () => {
  it("keeps only show_in_table declarations, in the given order", () => {
    const cols = extensionColumns<{ extensions?: Record<string, unknown> }>(EXT_FIELDS);
    expect(cols.map((c) => c.label)).toEqual(["Priority"]);
  });

  it("renders a boolean value as Yes/No and a missing value as an em dash", () => {
    const boolField: FieldDescriptor[] = [
      { name: "flag", label: "Flag", type: "boolean", required: false, show_in_table: true },
    ];
    const [col] = extensionColumns<{ extensions?: Record<string, unknown> }>(boolField);
    expect(col.render({ extensions: { flag: true } })).toBe("Yes");
    expect(col.render({ extensions: {} })).toBe("—");
  });

  it("keys columns by field name, not label — two declarations may share a label", () => {
    const dup: FieldDescriptor[] = [
      { name: "method_a", label: "Method", type: "string", required: false, show_in_table: true },
      { name: "method_b", label: "Method", type: "string", required: false, show_in_table: true },
    ];
    const cols = extensionColumns<{ extensions?: Record<string, unknown> }>(dup);
    expect(cols.map((c) => c.key)).toEqual(["method_a", "method_b"]);
    expect(cols.map((c) => c.label)).toEqual(["Method", "Method"]);
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

describe("isAiGenerated", () => {
  it("is true only for AI methods", () => {
    expect(isAiGenerated("ai_extracted")).toBe(true);
    expect(isAiGenerated("ai_predicted")).toBe(true);
    expect(isAiGenerated("imported")).toBe(false);
    expect(isAiGenerated("manual")).toBe(false);
    expect(isAiGenerated(null)).toBe(false);
  });
});

describe("defaultProvenance", () => {
  it("picks the descriptor's first offered source_type", () => {
    const fields = [
      {
        name: "source_type",
        label: "Source type",
        type: "enum",
        required: true,
        options: ["published", "preprint"],
      },
    ];
    expect(defaultProvenance(fields)).toEqual({ source_type: "published" });
  });

  it("falls back to a valid literal when the descriptor hasn't loaded yet", () => {
    expect(defaultProvenance([])).toEqual({ source_type: "published" });
  });
});

describe("ProvenanceLegend", () => {
  it("renders the three color meanings", () => {
    render(<ProvenanceLegend />);
    expect(screen.getByText("manual")).toBeInTheDocument();
    expect(screen.getByText("imported")).toBeInTheDocument();
    expect(screen.getByText("AI")).toBeInTheDocument();
  });
});
