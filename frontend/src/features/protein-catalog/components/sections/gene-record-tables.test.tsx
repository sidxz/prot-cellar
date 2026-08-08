import { fireEvent, render, screen } from "@testing-library/react";
import type { ComponentType } from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

// Charts are irrelevant to what this file tests (create-body composition) — stub them out
// rather than worry about how they behave with an empty records array.
vi.mock("@structflo/components/target-biology", () => ({
  EssentialityCallScale: () => null,
  VulnerabilityPanel: () => null,
  ResistanceLollipop: () => null,
}));

vi.mock("../../hooks/use-target-biology", () => ({
  useInvalidateGeneTargetBiology: () => vi.fn(),
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
  useCreateEssentialityApiV1GenesGeneIdTargetBiologyEssentialityPost: () => mutation,
  useUpdateEssentialityApiV1TargetBiologyEssentialityRecordIdPatch: () => mutation,
  useCreateVulnerabilityApiV1GenesGeneIdTargetBiologyVulnerabilityPost: () => mutation,
  useUpdateVulnerabilityApiV1TargetBiologyVulnerabilityRecordIdPatch: () => mutation,
  useCreateHypomorphApiV1GenesGeneIdTargetBiologyHypomorphPost: () => mutation,
  useUpdateHypomorphApiV1TargetBiologyHypomorphRecordIdPatch: () => mutation,
  useCreateCrispriStrainApiV1GenesGeneIdTargetBiologyCrispriStrainPost: () => mutation,
  useUpdateCrispriStrainApiV1TargetBiologyCrispriStrainRecordIdPatch: () => mutation,
  useCreateResistanceMutationApiV1GenesGeneIdTargetBiologyResistanceMutationPost: () => mutation,
  useUpdateResistanceMutationApiV1TargetBiologyResistanceMutationRecordIdPatch: () => mutation,
  useDeleteTargetBiologyRecordApiV1TargetBiologyKindRecordIdDelete: () => mutation,
}));

import {
  CrispriStrainTable,
  EssentialityTable,
  HypomorphTable,
  ResistanceMutationTable,
  VulnerabilityTable,
} from "./gene-record-tables";

// Each kind's real records[] type differs; an empty array satisfies every one of them and
// the mismatch isn't what this file is testing.
// biome-ignore lint/suspicious/noExplicitAny: see comment above
const TABLES: [string, ComponentType<any>][] = [
  ["Essentiality", EssentialityTable],
  ["Vulnerability", VulnerabilityTable],
  ["Hypomorph", HypomorphTable],
  ["CRISPRi strain", CrispriStrainTable],
  ["Resistance mutation", ResistanceMutationTable],
];

describe("gene-record-tables create payloads carry provenance", () => {
  // Regression test for the bug where `toBody` (now provenance-free, correctly, for PATCH)
  // was also used unchanged for POST: every *WriteBody.provenance is required with no
  // default, so Add → Save 422ed on all eight tables before defaultProvenance() was wired
  // into each onCreate. Runs the real per-kind component, not a reimplementation of its logic.
  it.each(TABLES)("%s: Add → Save sends provenance.source_type, not a 422", (_label, Table) => {
    mutateAsync.mockClear();
    render(<Table geneId="g1" records={[]} />);
    fireEvent.click(screen.getByRole("button", { name: /add/i }));
    fireEvent.click(screen.getByRole("button", { name: /save/i }));

    expect(mutateAsync).toHaveBeenCalledTimes(1);
    const sent = mutateAsync.mock.calls[0][0] as {
      data: { provenance?: { source_type?: string } };
    };
    expect(sent.data.provenance?.source_type).toBe("published");
  });
});
