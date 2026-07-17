import { describe, expect, it } from "vitest";

import { type TrackGene, layoutNeighbors } from "./genome-track";

const g = (over: Partial<TrackGene>): TrackGene => ({
  id: "x",
  name: "geneX",
  strand: "+",
  essentiality: null,
  start: 0,
  end: 100,
  isCurrent: false,
  ...over,
});

describe("layoutNeighbors", () => {
  it("returns [] for no genes", () => {
    expect(layoutNeighbors([], 300)).toEqual([]);
  });

  it("spans the full width for a single gene", () => {
    const [p] = layoutNeighbors([g({ start: 100, end: 200 })], 300);
    expect(p.x).toBe(0);
    expect(p.w).toBe(300);
  });

  it("positions genes proportionally to genomic coordinate", () => {
    const [a, b] = layoutNeighbors(
      [g({ id: "a", start: 0, end: 100 }), g({ id: "b", start: 200, end: 300 })],
      300,
    );
    expect(a.x).toBe(0);
    expect(a.w).toBeCloseTo(100);
    expect(b.x).toBeCloseTo(200);
    expect(b.w).toBeCloseTo(100);
  });

  it("clamps tiny genes to a minimum width", () => {
    const [tiny] = layoutNeighbors(
      [g({ id: "t", start: 0, end: 1 }), g({ id: "big", start: 10, end: 1000 })],
      300,
      6,
    );
    expect(tiny.w).toBe(6);
  });

  it("normalizes reversed coordinates (start > end)", () => {
    const [p] = layoutNeighbors([g({ start: 200, end: 100 })], 300);
    expect(p.x).toBe(0);
    expect(p.w).toBe(300);
  });
});
