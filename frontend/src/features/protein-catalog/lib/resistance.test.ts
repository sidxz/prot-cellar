import { describe, expect, it } from "vitest";

import { buildNeedles, distinctCompounds, parseResiduePosition } from "./resistance";

describe("parseResiduePosition", () => {
  it("extracts the residue number from a mutation / coordinate string", () => {
    expect(parseResiduePosition("S315T")).toBe(315);
    expect(parseResiduePosition("L273A")).toBe(273);
    expect(parseResiduePosition("M306V")).toBe(306);
    expect(parseResiduePosition("450")).toBe(450);
    expect(parseResiduePosition("p.Ser315Thr")).toBe(315);
  });

  it("returns null when there is no number", () => {
    expect(parseResiduePosition(null)).toBeNull();
    expect(parseResiduePosition("")).toBeNull();
    expect(parseResiduePosition("frameshift")).toBeNull();
  });
});

describe("buildNeedles", () => {
  it("prefers protein_coordinate for position, falls back to mutation", () => {
    const [byCoord] = buildNeedles([{ mutation: "S450L", protein_coordinate: "273" }]);
    expect(byCoord.position).toBe(273);
    const [byMutation] = buildNeedles([{ mutation: "S450L", protein_coordinate: null }]);
    expect(byMutation.position).toBe(450);
  });

  it("carries mic_shift, compound and label; drops unparseable rows", () => {
    const needles = buildNeedles([
      { mutation: "S315T", mic_shift: 200, compound: { name: "INH" } },
      { mutation: "frameshift", protein_coordinate: null },
    ]);
    expect(needles).toHaveLength(1);
    expect(needles[0]).toMatchObject({
      position: 315,
      micShift: 200,
      compound: "INH",
      label: "S315T",
    });
  });
});

describe("distinctCompounds", () => {
  it("lists unique compound names in first-seen order", () => {
    const needles = buildNeedles([
      { mutation: "A1B", compound: { name: "INH" } },
      { mutation: "C2D", compound: { name: "RIF" } },
      { mutation: "E3F", compound: { name: "INH" } },
    ]);
    expect(distinctCompounds(needles)).toEqual(["INH", "RIF"]);
  });
});
