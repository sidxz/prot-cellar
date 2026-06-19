import { describe, expect, it } from "vitest";
import { organismCommonName } from "./organism-format";
const n = (name: string, name_class: string) =>
  ({ name, name_class, is_preferred: false }) as never;
describe("organismCommonName", () => {
  it("prefers common_name", () => {
    expect(organismCommonName([n("Human", "common_name"), n("man", "genbank_common_name")])).toBe(
      "Human",
    );
  });
  it("falls back to genbank_common_name then null", () => {
    expect(organismCommonName([n("man", "genbank_common_name")])).toBe("man");
    expect(organismCommonName([n("Homo sapiens", "scientific_name")])).toBeNull();
  });
});
