import { describe, expect, it } from "vitest";

import {
  ESSENTIALITY_STYLE,
  essentialityBucket,
  essentialityConsensus,
  fitnessPosition,
  pivotConditionMethod,
} from "./essentiality";

describe("essentialityBucket", () => {
  it("maps the underscored enum values to hyphenated buckets", () => {
    expect(essentialityBucket("essential")).toBe("essential");
    expect(essentialityBucket("growth_defect")).toBe("growth-defect");
    expect(essentialityBucket("non_essential")).toBe("non-essential");
    expect(essentialityBucket("growth_advantage")).toBe("growth-advantage");
    expect(essentialityBucket("uncertain")).toBe("uncertain");
  });

  it("is case- and separator-tolerant", () => {
    expect(essentialityBucket("GROWTH DEFECT")).toBe("growth-defect");
    expect(essentialityBucket("Non-Essential")).toBe("non-essential");
  });

  it("checks non-essential before essential (substring trap)", () => {
    // "non-essential" contains the substring "essential"; order must not misclassify it.
    expect(essentialityBucket("non-essential")).toBe("non-essential");
  });

  it("falls back to uncertain for null/empty/unrecognized", () => {
    expect(essentialityBucket(null)).toBe("uncertain");
    expect(essentialityBucket(undefined)).toBe("uncertain");
    expect(essentialityBucket("")).toBe("uncertain");
    expect(essentialityBucket("wobble")).toBe("uncertain");
  });
});

describe("fitnessPosition", () => {
  it("orders the calls along the fitness axis (essential highest, growth-advantage lowest)", () => {
    const es = fitnessPosition("essential");
    const gd = fitnessPosition("growth_defect");
    const ne = fitnessPosition("non_essential");
    const ga = fitnessPosition("growth_advantage");
    expect(es).not.toBeNull();
    expect(ga).not.toBeNull();
    // non-null assertions are safe given the checks above
    expect(es as number).toBeGreaterThan(gd as number);
    expect(gd as number).toBeGreaterThan(ne as number);
    expect(ne as number).toBeGreaterThan(ga as number);
  });

  it("stays within [0,1]", () => {
    expect(fitnessPosition("essential") as number).toBeLessThanOrEqual(1);
    expect(fitnessPosition("growth_advantage") as number).toBeGreaterThanOrEqual(0);
  });

  it("returns null for uncertain / missing (no caret to place)", () => {
    expect(fitnessPosition("uncertain")).toBeNull();
    expect(fitnessPosition(null)).toBeNull();
  });
});

describe("ESSENTIALITY_STYLE", () => {
  it("gives every bucket a static token class set", () => {
    expect(ESSENTIALITY_STYLE.essential.fill).toContain("destructive");
    expect(ESSENTIALITY_STYLE["growth-defect"].fill).toContain("warning");
    expect(ESSENTIALITY_STYLE["growth-advantage"].fill).toContain("chart-1");
    expect(ESSENTIALITY_STYLE["non-essential"].text).toContain("muted");
  });
});

describe("essentialityConsensus", () => {
  it("returns null for no records", () => {
    expect(essentialityConsensus([])).toBeNull();
  });

  it("reports a single record as 'single' with its confidence", () => {
    const c = essentialityConsensus([{ classification: "essential", confidence: 0.9 }]);
    expect(c).toMatchObject({
      bucket: "essential",
      agreement: "single",
      total: 1,
      confidence: 0.9,
    });
  });

  it("marks records with the same call as 'agree'", () => {
    const c = essentialityConsensus([
      { classification: "essential", method: "TnSeq" },
      { classification: "essential", method: "CRISPRi" },
    ]);
    expect(c?.agreement).toBe("agree");
    expect(c?.bucket).toBe("essential");
    expect(c?.total).toBe(2);
  });

  it("marks disagreeing records as 'conflict'", () => {
    const c = essentialityConsensus([
      { classification: "essential" },
      { classification: "growth_defect" },
    ]);
    expect(c?.agreement).toBe("conflict");
  });

  it("breaks a modal tie toward the more severe call", () => {
    const c = essentialityConsensus([
      { classification: "non_essential" },
      { classification: "essential" },
    ]);
    expect(c?.bucket).toBe("essential");
  });

  it("averages confidence across records backing the consensus (ignoring dissenters)", () => {
    const c = essentialityConsensus([
      { classification: "essential", confidence: 0.6 },
      { classification: "essential", confidence: 0.9 },
      { classification: "non_essential", confidence: 0.99 },
    ]);
    // mean of the two essential rows (0.6, 0.9), not the max, and not the 0.99 dissenter
    expect(c?.confidence).toBeCloseTo(0.75);
  });
});

describe("pivotConditionMethod", () => {
  it("pivots records into unique conditions × methods, preserving first-seen order", () => {
    const p = pivotConditionMethod([
      { classification: "essential", condition: "7H9", method: "TnSeq" },
      { classification: "growth_defect", condition: "cholesterol", method: "TnSeq" },
      { classification: "essential", condition: "cholesterol", method: "CRISPRi" },
    ]);
    expect(p.conditions).toEqual(["7H9", "cholesterol"]);
    expect(p.methods).toEqual(["TnSeq", "CRISPRi"]);
    expect(p.cell("7H9", "TnSeq")).toBe("essential");
    expect(p.cell("cholesterol", "TnSeq")).toBe("growth-defect");
    expect(p.cell("cholesterol", "CRISPRi")).toBe("essential");
    expect(p.cell("7H9", "CRISPRi")).toBeNull();
  });

  it("flags a cell as 'conflict' when two sources disagree on the same condition × method", () => {
    const p = pivotConditionMethod([
      { classification: "essential", condition: "7H9", method: "TnSeq" },
      { classification: "non_essential", condition: "7H9", method: "TnSeq" },
      { classification: "growth_defect", condition: "cholesterol", method: "TnSeq" },
      { classification: "growth_defect", condition: "cholesterol", method: "TnSeq" },
    ]);
    // disagreeing calls in one cell → conflict (not silently the last one)
    expect(p.cell("7H9", "TnSeq")).toBe("conflict");
    // agreeing duplicates keep the call
    expect(p.cell("cholesterol", "TnSeq")).toBe("growth-defect");
  });

  it("falls back to a placeholder for empty condition/method", () => {
    const p = pivotConditionMethod([{ classification: "essential" }]);
    expect(p.conditions).toEqual(["—"]);
    expect(p.methods).toEqual(["—"]);
    expect(p.cell("—", "—")).toBe("essential");
  });
});
