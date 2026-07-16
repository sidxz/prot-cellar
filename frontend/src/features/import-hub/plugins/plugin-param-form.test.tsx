import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../hooks/use-imports", () => ({
  useUploadEssentiality: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));
vi.mock("../components/organism-combobox", () => ({
  OrganismCombobox: () => <div data-testid="organism-combobox" />,
}));

import { PluginParamForm } from "./plugin-param-form";

const params = [
  { key: "organism_id", label: "Organism", type: "organism", required: true, options: [] },
  { key: "upload", label: "Table", type: "file_upload", required: true, options: [] },
  { key: "condition", label: "Condition", type: "string", required: false, options: [] },
  { key: "force", label: "Force", type: "bool", required: false, options: [] },
  // biome-ignore lint/suspicious/noExplicitAny: test fixture shortcut, avoids the full ParamFieldResponse shape
] as any;

describe("PluginParamForm", () => {
  it("renders an input per descriptor field, by type", () => {
    render(<PluginParamForm params={params} values={{}} onChange={() => {}} />);
    expect(screen.getByTestId("organism-combobox")).toBeInTheDocument();
    expect(screen.getByLabelText("Condition")).toBeInTheDocument();
    expect(screen.getByLabelText("Force")).toBeInTheDocument();
    // file_upload renders a native file input
    expect(document.querySelector('input[type="file"]')).not.toBeNull();
  });
});
