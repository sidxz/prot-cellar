import { describe, expect, it } from "vitest";
import { unwrapList } from "./crud-hooks";

describe("unwrapList", () => {
  it("passes through a bare array", () => {
    expect(unwrapList([1, 2, 3])).toEqual([1, 2, 3]);
  });
  it("unwraps a paginated {items} envelope", () => {
    expect(unwrapList({ items: [1, 2], next_cursor: "x" } as never)).toEqual([1, 2]);
  });
  it("returns [] for undefined", () => {
    expect(unwrapList(undefined)).toEqual([]);
  });
});
