import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ReactElement } from "react";

import type { ImportRun } from "../types";
import { importColumnDefs } from "./import-columns";

// biome-ignore lint/suspicious/noExplicitAny: cell renderer prop shape
function cellFor(field: string): (p: any) => ReactElement {
  const col = importColumnDefs.find((c) => c.field === field);
  if (!col?.cellRenderer) throw new Error(`no renderer for ${field}`);
  // biome-ignore lint/suspicious/noExplicitAny: ag-grid renderer cast
  return col.cellRenderer as any;
}

const run = {
  id: "r1",
  import_type: "proteome",
  target_key: "UP000001584",
  status: "succeeded",
  progress: {},
  summary: {},
  requested_by: "u1",
  created_at: "2026-06-22T10:00:00Z",
  finished_at: null,
} as unknown as ImportRun;

describe("import columns", () => {
  it("renders the raw status text in the status cell", () => {
    const Status = cellFor("status");
    render(<Status data={run} />);
    expect(screen.getByText("succeeded")).toBeInTheDocument();
  });

  it("renders the human type label in the type cell", () => {
    const Type = cellFor("import_type");
    render(<Type data={run} />);
    expect(screen.getByText("Proteome")).toBeInTheDocument();
  });
});
