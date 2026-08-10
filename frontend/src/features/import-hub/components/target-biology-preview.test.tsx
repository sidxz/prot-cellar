import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const startMutate = vi.fn().mockResolvedValue({ id: "apply-run-1" });
vi.mock("../hooks/use-imports", () => ({
  useStartImport: () => ({ mutateAsync: startMutate, isPending: false }),
}));

vi.mock("@/features/protein-catalog/hooks/use-target-biology-schema", () => ({
  useTargetBiologySchema: () => ({
    data: {
      provenance: { fields: [] },
      kinds: {
        vulnerability: { label: "Vulnerability", attaches_to: "gene", fields: [] },
        hypomorph: { label: "Hypomorph", attaches_to: "gene", fields: [] },
        unpublished_structure: {
          label: "Unpublished structure",
          attaches_to: "protein",
          fields: [],
        },
      },
      concurrency: { field: "version" },
    },
  }),
}));

import { TargetBiologyPreview } from "./target-biology-preview";

function baseRun(overrides: Record<string, unknown> = {}) {
  return {
    id: "run-1",
    import_type: "target_biology",
    target_key: "org-1:up-1:dry",
    status: "succeeded",
    phase: null,
    progress: { processed: 15, total: 15 },
    upload_ref: "up-1",
    requested_by: "user-1",
    created_at: "2026-08-09T00:00:00Z",
    error: null,
    params: { proteome_id: "pt-1", match_by: "locus_tag", update_existing: false },
    summary: {
      kinds: {
        vulnerability: {
          rows: 10,
          records: 9,
          merged_identical: 1,
          create: 9,
          update: 0,
          failed: 0,
        },
        hypomorph: { rows: 5, records: 5, merged_identical: 0, create: 4, update: 0, failed: 1 },
      },
      unmatched: { count: 0, examples: [] },
      problems: [],
      problems_truncated: 0,
      already_present: {},
      ignored_columns: {},
      warnings: [],
    },
    ...overrides,
    // biome-ignore lint/suspicious/noExplicitAny: test fixture shortcut, avoids the full ImportRunResponse shape
  } as any;
}

describe("TargetBiologyPreview", () => {
  beforeEach(() => {
    startMutate.mockClear();
    push.mockClear();
  });

  it("renders per-kind counts", () => {
    render(<TargetBiologyPreview run={baseRun()} />);
    // Column order: Kind, Rows, Records, Merged, Create, Update, Failed.
    const vulnRow = screen.getByText("Vulnerability").closest("tr") as HTMLTableRowElement;
    expect(Array.from(vulnRow.cells, (c) => c.textContent)).toEqual([
      "Vulnerability",
      "10",
      "9",
      "1",
      "9",
      "0",
      "0",
    ]);
    const hypoRow = screen.getByText("Hypomorph").closest("tr") as HTMLTableRowElement;
    expect(Array.from(hypoRow.cells, (c) => c.textContent)).toEqual([
      "Hypomorph",
      "5",
      "5",
      "0",
      "4",
      "0",
      "1",
    ]);
  });

  it("states the truncation notice when problems_truncated is non-zero", () => {
    const run = baseRun({
      summary: {
        ...baseRun().summary,
        problems: [{ sheet: "hypomorph", row: 3, reason: "unmatched locus RV9999" }],
        problems_truncated: 7,
      },
    });
    render(<TargetBiologyPreview run={run} />);
    expect(screen.getByText(/7 more not shown/i)).toBeInTheDocument();
  });

  it("does not show a truncation notice when nothing was truncated", () => {
    const run = baseRun({
      summary: {
        ...baseRun().summary,
        problems: [{ sheet: "hypomorph", row: 3, reason: "unmatched locus RV9999" }],
        problems_truncated: 0,
      },
    });
    render(<TargetBiologyPreview run={run} />);
    expect(screen.queryByText(/more not shown/i)).not.toBeInTheDocument();
  });

  it("shows the already_present warning in add mode", () => {
    const run = baseRun({
      params: { proteome_id: "pt-1", match_by: "locus_tag", update_existing: false },
      summary: { ...baseRun().summary, already_present: { vulnerability: 3 } },
    });
    render(<TargetBiologyPreview run={run} />);
    expect(screen.getByText(/add mode will duplicate/i)).toBeInTheDocument();
  });

  it("hides the already_present warning in update mode", () => {
    const run = baseRun({
      params: { proteome_id: "pt-1", match_by: "locus_tag", update_existing: true },
      summary: { ...baseRun().summary, already_present: { vulnerability: 3 } },
    });
    render(<TargetBiologyPreview run={run} />);
    expect(screen.queryByText(/add mode will duplicate/i)).not.toBeInTheDocument();
  });

  it("shows the unresolved-ligand warning the backend only ever emits in update mode", () => {
    const run = baseRun({
      summary: {
        ...baseRun().summary,
        warnings: [
          {
            sheet: "unpublished_structure",
            count: 2,
            reason: "ligand text did not resolve to a compound id",
          },
        ],
      },
    });
    render(<TargetBiologyPreview run={run} />);
    expect(screen.getByText(/did not resolve to a compound id/i)).toBeInTheDocument();
    expect(screen.getByText(/unpublished structure: 2 rows/i)).toBeInTheDocument();
  });

  it("renders no ligand warning when the backend sent none", () => {
    render(<TargetBiologyPreview run={baseRun()} />);
    expect(screen.queryByText(/did not resolve to a compound id/i)).not.toBeInTheDocument();
  });

  it("offers Apply and Discard on a preview run", () => {
    render(<TargetBiologyPreview run={baseRun()} />);
    expect(screen.getByRole("button", { name: "Apply" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Discard" })).toBeInTheDocument();
  });

  it("Apply resubmits the run's own params from the server, not anything client-remembered", async () => {
    const run = baseRun({
      params: { proteome_id: "pt-9", match_by: "gene_name", update_existing: true },
    });
    render(<TargetBiologyPreview run={run} />);
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));

    await waitFor(() =>
      expect(startMutate).toHaveBeenCalledWith({
        data: {
          import_type: "target_biology",
          params: {
            upload_ref: "up-1",
            proteome_id: "pt-9",
            match_by: "gene_name",
            update_existing: true,
            dry_run: false,
          },
        },
      }),
    );
    await waitFor(() => expect(push).toHaveBeenCalledWith("/admin/imports/apply-run-1"));
  });

  it("offers no Apply/Discard on a run that was already applied", () => {
    const run = baseRun({ target_key: "org-1:up-1:run" });
    render(<TargetBiologyPreview run={run} />);
    expect(screen.queryByRole("button", { name: "Apply" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Discard" })).not.toBeInTheDocument();
  });

  it("renders nothing while the run is still in progress", () => {
    const { container } = render(<TargetBiologyPreview run={baseRun({ status: "running" })} />);
    expect(container).toBeEmptyDOMElement();
  });
});
