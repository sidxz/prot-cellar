// frontend/src/features/import-hub/components/start-import-dialog.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("./param-forms/go-ontology-form", () => ({
  GoOntologyForm: () => <div>go-form</div>,
}));
vi.mock("./param-forms/proteome-form", () => ({
  ProteomeForm: () => <div>proteome-form</div>,
}));
vi.mock("./param-forms/gene-enrichment-form", () => ({
  GeneEnrichmentForm: () => <div>gene-form</div>,
}));
vi.mock("./param-forms/target-biology-params", () => ({
  TargetBiologyParamsForm: () => <div>target-biology-form</div>,
}));

import { StartImportDialog } from "./start-import-dialog";

describe("StartImportDialog", () => {
  it("renders the title and the go_ontology form by default when open", () => {
    render(<StartImportDialog open onOpenChange={() => {}} />);
    expect(screen.getByRole("heading", { name: /new import/i })).toBeInTheDocument();
    expect(screen.getByText("go-form")).toBeInTheDocument();
  });

  it("renders nothing when closed", () => {
    render(<StartImportDialog open={false} onOpenChange={() => {}} />);
    expect(screen.queryByText("go-form")).not.toBeInTheDocument();
  });
});
