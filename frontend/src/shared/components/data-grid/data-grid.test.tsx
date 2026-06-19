import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DataGrid } from "./data-grid";

describe("DataGrid", () => {
  it("renders the empty state when there are no rows and not loading", () => {
    render(
      <DataGrid rowData={[]} columnDefs={[{ field: "name" }]} emptyState={<div>No rows</div>} />,
    );
    expect(screen.getByText("No rows")).toBeInTheDocument();
  });
});
