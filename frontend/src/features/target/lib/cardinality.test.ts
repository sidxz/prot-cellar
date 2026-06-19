import { describe, expect, it } from "vitest";
import { cardinalityRule, componentCountValid } from "./cardinality";

describe("cardinality", () => {
  it("single_protein requires exactly 1", () => {
    expect(componentCountValid("single_protein", 1)).toBe(true);
    expect(componentCountValid("single_protein", 0)).toBe(false);
    expect(componentCountValid("single_protein", 2)).toBe(false);
  });
  it("complex/family/ppi require >= 2", () => {
    for (const t of ["protein_complex", "protein_family", "protein_protein_interaction"] as const) {
      expect(componentCountValid(t, 1)).toBe(false);
      expect(componentCountValid(t, 2)).toBe(true);
      expect(componentCountValid(t, 5)).toBe(true);
    }
  });
  it("other types allow any count incl. 0", () => {
    expect(componentCountValid("organism", 0)).toBe(true);
    expect(componentCountValid("unknown", 3)).toBe(true);
  });
  it("cardinalityRule returns bounds", () => {
    expect(cardinalityRule("single_protein")).toEqual({ min: 1, max: 1 });
    expect(cardinalityRule("protein_complex").min).toBe(2);
  });
});
