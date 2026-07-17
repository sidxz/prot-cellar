import { describe, expect, it } from "vitest";
import { spectrum } from "./protein-fold";

describe("spectrum (N→C brand ramp)", () => {
  it("hits the endpoints exactly", () => {
    expect(spectrum(0)).toEqual([0x37, 0xd7, 0xfa]);
    expect(spectrum(1)).toEqual([0xff, 0x87, 0x05]);
  });

  it("hits an interior stop exactly", () => {
    expect(spectrum(0.4)).toEqual([0x4b, 0x72, 0xfe]);
  });

  it("interpolates between stops", () => {
    // halfway from stop0 → stop1
    expect(spectrum(0.2)).toEqual([65, 165, 252]);
  });

  it("clamps out-of-range input", () => {
    expect(spectrum(-1)).toEqual(spectrum(0));
    expect(spectrum(2)).toEqual(spectrum(1));
  });
});
