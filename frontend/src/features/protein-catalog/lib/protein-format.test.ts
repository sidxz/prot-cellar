import { describe, expect, it } from "vitest";
import type { Protein } from "../types";
import { proteinExistenceLabel, proteinPrimaryName } from "./protein-format";

const base = { primary_accession: "P1", entry_name: null, protein_names: {} } as unknown as Protein;
describe("proteinPrimaryName", () => {
  it("prefers recommended", () => {
    expect(proteinPrimaryName({ ...base, protein_names: { recommended: "Albumin" } })).toBe(
      "Albumin",
    );
  });
  it("falls back to entry_name then accession", () => {
    expect(proteinPrimaryName({ ...base, entry_name: "ALBU_HUMAN" })).toBe("ALBU_HUMAN");
    expect(proteinPrimaryName(base)).toBe("P1");
  });
});
describe("proteinExistenceLabel", () => {
  it("maps known codes and falls back to dash", () => {
    expect(proteinExistenceLabel(null)).toBe("—");
    expect(typeof proteinExistenceLabel("EVIDENCE_AT_PROTEIN_LEVEL")).toBe("string");
  });
});
