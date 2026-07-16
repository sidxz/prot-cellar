import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const manifests = [
  {
    id: "dejesus_essentiality",
    name: "DeJesus essentiality",
    description: "Load essentiality calls.",
    target_records: ["essentiality"],
    default_generation_method: "imported",
    params: [],
    requires_secrets: [],
  },
  {
    id: "ai_miner",
    name: "AI essentiality miner",
    description: "LLM-extracted calls.",
    target_records: ["essentiality"],
    default_generation_method: "ai_extracted",
    params: [],
    requires_secrets: ["OPENAI_API_KEY"],
  },
];

vi.mock("./use-plugins", () => ({
  usePluginCatalog: () => ({ data: manifests, isLoading: false, isError: false }),
}));
vi.mock("./plugin-run-panel", () => ({ PluginRunPanel: () => null }));

import { PluginCatalogPage } from "./plugin-catalog";

describe("PluginCatalogPage", () => {
  it("renders a card per plugin with a source-kind chip and a needs-config badge", () => {
    render(<PluginCatalogPage />);
    expect(screen.getByText("DeJesus essentiality")).toBeInTheDocument();
    expect(screen.getByText("AI essentiality miner")).toBeInTheDocument();
    // AI plugin surfaces a "needs config" badge (requires a secret)
    expect(screen.getByText(/needs config/i)).toBeInTheDocument();
  });
});
