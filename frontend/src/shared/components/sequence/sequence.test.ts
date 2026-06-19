import { describe, expect, it } from "vitest";
import { chunkSequence, toFasta } from "./sequence";

describe("chunkSequence", () => {
  it("splits into fixed-width lines (default 60)", () => {
    expect(chunkSequence("A".repeat(130)).map((l) => l.length)).toEqual([60, 60, 10]);
  });
  it("honors a custom width", () => {
    expect(chunkSequence("ABCDE", 2)).toEqual(["AB", "CD", "E"]);
  });
  it("returns [] for an empty sequence", () => {
    expect(chunkSequence("")).toEqual([]);
  });
});

describe("toFasta", () => {
  it("emits a header line then wrapped sequence", () => {
    expect(toFasta("sp|P1|X", "ABCDE", 2)).toBe(">sp|P1|X\nAB\nCD\nE");
  });
});
