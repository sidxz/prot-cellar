import { describe, expect, it } from "vitest";

import { ImportStatus, ImportType } from "@/shared/lib/api/model";

import { IMPORT_TYPE_LABELS, STATUS_VARIANTS } from "./index";

describe("import-hub type maps", () => {
  it("has a label for every import type", () => {
    for (const t of Object.values(ImportType)) {
      expect(IMPORT_TYPE_LABELS[t]).toBeTruthy();
    }
  });

  it("has a badge variant for every status", () => {
    for (const s of Object.values(ImportStatus)) {
      expect(STATUS_VARIANTS[s]).toBeTruthy();
    }
  });
});
