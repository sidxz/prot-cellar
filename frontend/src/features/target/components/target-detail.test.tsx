import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../hooks/use-targets", () => ({
  useTarget: () => ({
    data: {
      id: "t1",
      workspace_id: "w1",
      pref_name: "EGFR",
      target_type: "single_protein",
      components: [{ id: "c1", protein_id: "p1", relationship: "single_protein" }],
      chembl_id: "CHEMBL203",
      chembl_url: "https://x/CHEMBL203",
      cross_references: [],
      version: 1,
    },
    isLoading: false,
    isError: false,
  }),
  useUpdateTarget: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useCreateTarget: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

import { TargetDetailPage } from "./target-detail";

describe("TargetDetailPage", () => {
  it("shows the target name and a component", () => {
    render(<TargetDetailPage targetId="t1" />);
    expect(screen.getByRole("heading", { name: "EGFR" })).toBeInTheDocument();
    expect(screen.getByText(/p1/)).toBeInTheDocument();
  });
});
