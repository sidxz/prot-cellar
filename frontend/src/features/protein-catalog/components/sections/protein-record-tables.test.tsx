import { fireEvent, render, screen } from "@testing-library/react";
import type { ComponentType } from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

vi.mock("../../hooks/use-target-biology", () => ({
  useInvalidateProteinTargetBiology: () => vi.fn(),
}));

const PROVENANCE_FIELDS = [
  {
    name: "source_type",
    label: "Source type",
    type: "enum",
    required: true,
    options: ["published", "preprint", "internal"],
  },
];
vi.mock("../../hooks/use-target-biology-schema", () => ({
  useTargetBiologySchema: () => ({
    data: {
      provenance: { fields: PROVENANCE_FIELDS },
      kinds: {},
      concurrency: { field: "version" },
    },
  }),
}));

const mutateAsync = vi.fn().mockResolvedValue({});
const mutation = { mutateAsync, isPending: false };
vi.mock("@/shared/lib/api/target-biology/target-biology", () => ({
  useCreateProteinActivityAssayApiV1ProteinsProteinIdTargetBiologyProteinActivityAssayPost: () =>
    mutation,
  useUpdateProteinActivityAssayApiV1TargetBiologyProteinActivityAssayRecordIdPatch: () => mutation,
  useCreateProteinProductionApiV1ProteinsProteinIdTargetBiologyProteinProductionPost: () =>
    mutation,
  useUpdateProteinProductionApiV1TargetBiologyProteinProductionRecordIdPatch: () => mutation,
  useCreateUnpublishedStructureApiV1ProteinsProteinIdTargetBiologyUnpublishedStructurePost: () =>
    mutation,
  useUpdateUnpublishedStructureApiV1TargetBiologyUnpublishedStructureRecordIdPatch: () => mutation,
  useDeleteTargetBiologyRecordApiV1TargetBiologyKindRecordIdDelete: () => mutation,
}));

import {
  ProteinActivityAssayTable,
  ProteinProductionTable,
  UnpublishedStructureTable,
} from "./protein-record-tables";

// Each kind's real records[] type differs; an empty array satisfies every one of them and
// the mismatch isn't what this file is testing.
// biome-ignore lint/suspicious/noExplicitAny: see comment above
const TABLES: [string, ComponentType<any>][] = [
  ["Protein production", ProteinProductionTable],
  ["Activity assay", ProteinActivityAssayTable],
  ["Unpublished structure", UnpublishedStructureTable],
];

describe("protein-record-tables create payloads carry provenance", () => {
  // Regression test for the bug where `toBody` (now provenance-free, correctly, for PATCH)
  // was also used unchanged for POST: every *WriteBody.provenance is required with no
  // default, so Add → Save 422ed on all eight tables before defaultProvenance() was wired
  // into each onCreate. Runs the real per-kind component, not a reimplementation of its logic.
  it.each(TABLES)("%s: Add → Save sends provenance.source_type, not a 422", (_label, Table) => {
    mutateAsync.mockClear();
    render(<Table proteinId="p1" records={[]} />);
    fireEvent.click(screen.getByRole("button", { name: /add/i }));
    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    expect(mutateAsync).toHaveBeenCalledTimes(1);
    const sent = mutateAsync.mock.calls[0][0] as {
      data: { provenance?: { source_type?: string } };
    };
    expect(sent.data.provenance?.source_type).toBe("published");
  });
});
