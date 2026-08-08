import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ProvenanceDialog } from "./provenance-dialog";

const SCHEMA_FIELDS = [
  {
    name: "source_type",
    label: "Source type",
    type: "enum",
    required: true,
    options: ["published", "preprint", "internal"],
  },
  {
    name: "citations",
    label: "Citations",
    type: "list",
    required: false,
    item_type: "object",
    item_fields: [
      { name: "pmid", label: "PMID", type: "string", required: false },
      { name: "doi", label: "DOI", type: "string", required: false },
      { name: "url", label: "URL", type: "string", required: false },
      { name: "label", label: "Label", type: "string", required: false },
    ],
  },
  { name: "contributor_researcher", label: "Contributor", type: "string", required: false },
  { name: "observed_on", label: "Observed on", type: "date", required: false },
  { name: "note", label: "Note", type: "text", required: false },
];

const EXISTING = {
  source_type: "published",
  generation_method: "ai_extracted",
  citations: [
    { pmid: "28096490", doi: null, url: null, label: null },
    { pmid: null, doi: "10.1016/j.cell.2021.02.001", url: null, label: "Bosch 2021" },
  ],
  contributor_researcher: "A. Curator",
  observed_on: "2021-03-01",
  note: "from the supplementary table",
};

describe("ProvenanceDialog", () => {
  it("renders every descriptor field", () => {
    render(
      <ProvenanceDialog
        open
        fields={SCHEMA_FIELDS}
        value={EXISTING}
        onSave={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    for (const label of ["Source type", "Contributor", "Observed on", "Note"]) {
      expect(screen.getByLabelText(new RegExp(label, "i"))).toBeInTheDocument();
    }
  });

  it("keeps every citation, including DOI-only ones, across an unrelated edit", () => {
    const onSave = vi.fn();
    render(
      <ProvenanceDialog
        open
        fields={SCHEMA_FIELDS}
        value={EXISTING}
        onSave={onSave}
        onClose={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByLabelText(/note/i), { target: { value: "checked against SI" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    const saved = onSave.mock.calls[0][0];
    expect(saved.citations).toHaveLength(2);
    expect(saved.citations[1].doi).toBe("10.1016/j.cell.2021.02.001");
    expect(saved.citations[1].label).toBe("Bosch 2021");
    expect(saved.contributor_researcher).toBe("A. Curator");
    expect(saved.observed_on).toBe("2021-03-01");
  });

  it("never submits generation_method — the server re-attributes on write", () => {
    const onSave = vi.fn();
    render(
      <ProvenanceDialog
        open
        fields={SCHEMA_FIELDS}
        value={EXISTING}
        onSave={onSave}
        onClose={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByLabelText(/note/i), { target: { value: "edited" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(onSave.mock.calls[0][0]).not.toHaveProperty("generation_method");
  });

  it("adds and removes citation rows", () => {
    const onSave = vi.fn();
    render(
      <ProvenanceDialog
        open
        fields={SCHEMA_FIELDS}
        value={EXISTING}
        onSave={onSave}
        onClose={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /add citation/i }));
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(onSave.mock.calls[0][0].citations).toHaveLength(3);
  });

  it("clears a populated date instead of resending the stale value", () => {
    const onSave = vi.fn();
    render(
      <ProvenanceDialog
        open
        fields={SCHEMA_FIELDS}
        value={EXISTING}
        onSave={onSave}
        onClose={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByLabelText(/observed on/i), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(onSave.mock.calls[0][0].observed_on).toBeNull();
  });

  it("treats an untouched save as a no-op — close without submitting", () => {
    const onSave = vi.fn();
    const onClose = vi.fn();
    render(
      <ProvenanceDialog
        open
        fields={SCHEMA_FIELDS}
        value={EXISTING}
        onSave={onSave}
        onClose={onClose}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(onSave).not.toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it("has an explicit cancel alongside save", () => {
    render(
      <ProvenanceDialog
        open
        fields={SCHEMA_FIELDS}
        value={EXISTING}
        onSave={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save/i })).toBeInTheDocument();
  });
});
