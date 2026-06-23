import { describe, expect, it } from "vitest";

import { navigation } from "./navigation";

describe("navigation", () => {
  it("includes an Imports entry under Administration", () => {
    const admin = navigation.groups.find((g) => g.label === "Administration");
    expect(admin?.items.some((i) => i.href === "/admin/imports")).toBe(true);
  });
});
