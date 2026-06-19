import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
vi.mock("@/shared/lib/api/proteins/proteins", () => ({
  resolveProteinApiV1ProteinsResolveIdentifierGet: vi.fn(),
}));
import { TargetComponentsEditor } from "./target-components-editor";
describe("TargetComponentsEditor", () => {
  it("shows the cardinality hint for the target type", () => {
    render(<TargetComponentsEditor value={[]} onChange={vi.fn()} targetType="protein_complex" />);
    expect(screen.getByText(/at least 2/i)).toBeInTheDocument();
  });
  it("renders an existing component row with its relationship", () => {
    render(
      <TargetComponentsEditor
        value={[
          {
            protein_id: "p1",
            relationship: "protein_subunit",
            accession: "P12345",
            label: "Albumin",
          },
        ]}
        onChange={vi.fn()}
        targetType="protein_complex"
      />,
    );
    expect(screen.getByDisplayValue("P12345")).toBeInTheDocument();
  });
});
