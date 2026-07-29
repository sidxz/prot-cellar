import { describe, expect, it } from "vitest";
import { secondaryNames } from "./gene-label";

describe("secondaryNames", () => {
  it("drops the lead and dedupes", () => {
    // protein context: lead = symbol, secondary = loci + synonyms
    expect(secondaryNames(["Rv1297", "MTCY373.17"], "rho")).toEqual(["Rv1297", "MTCY373.17"]);
  });
  it("removes the lead when it appears in the list", () => {
    // gene context: lead = locus, secondary includes the symbol
    expect(secondaryNames(["rho", "Rv1297", "MTCY373.17"], "Rv1297")).toEqual([
      "rho",
      "MTCY373.17",
    ]);
  });
  it("filters empties and duplicates", () => {
    expect(secondaryNames(["rho", "rho", "", "MTCY"], "Rv1")).toEqual(["rho", "MTCY"]);
  });
});
