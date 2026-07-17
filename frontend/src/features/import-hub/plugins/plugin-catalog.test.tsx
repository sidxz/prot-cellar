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
    enabled: true,
  },
  {
    id: "ai_miner",
    name: "AI essentiality miner",
    description: "LLM-extracted calls.",
    target_records: ["essentiality"],
    default_generation_method: "ai_extracted",
    params: [],
    requires_secrets: ["OPENAI_API_KEY"],
    enabled: false,
  },
];

vi.mock("./use-plugins", () => ({
  usePluginCatalog: () => ({ data: manifests, isLoading: false, isError: false }),
  useSetPluginEnabled: () => ({ mutate: vi.fn(), isPending: false }),
}));
vi.mock("./plugin-run-panel", () => ({ PluginRunPanel: () => null }));

import { PluginCatalogPage } from "./plugin-catalog";

describe("PluginCatalogPage", () => {
  it("splits enabled vs available with the right actions and a needs-config badge", () => {
    render(<PluginCatalogPage />);
    expect(screen.getByText("DeJesus essentiality")).toBeInTheDocument();
    expect(screen.getByText("AI essentiality miner")).toBeInTheDocument();
    // AI plugin surfaces a "needs config" badge (requires a secret)
    expect(screen.getByText(/needs config/i)).toBeInTheDocument();
    // Enabled plugin can be Run; available plugin can be Enabled.
    expect(screen.getByRole("button", { name: /^run$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^enable$/i })).toBeInTheDocument();
  });
});
