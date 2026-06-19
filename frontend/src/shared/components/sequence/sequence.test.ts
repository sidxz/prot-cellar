import { describe, expect, it } from "vitest";
import { chunkSequence, parseFasta, toFasta } from "./sequence";

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

describe("parseFasta", () => {
  it("strips the header and joins residue lines", () => {
    expect(parseFasta(">sp|P1|X\nMAAA\nKLL")).toEqual({ header: "sp|P1|X", sequence: "MAAAKLL" });
  });
  it("handles headerless input as pure sequence", () => {
    expect(parseFasta("MAAA\nKLL")).toEqual({ header: "", sequence: "MAAAKLL" });
  });
  it("trims whitespace/blank lines", () => {
    expect(parseFasta(">h\nMA A\n\n KL \n")).toEqual({ header: "h", sequence: "MAAKL" });
  });
});
