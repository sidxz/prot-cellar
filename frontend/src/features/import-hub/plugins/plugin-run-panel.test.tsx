import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const startMutate = vi.fn(async () => ({ id: "run-123" }));
vi.mock("./use-plugins", () => ({
  useStartPluginRun: () => ({ mutateAsync: startMutate, isPending: false }),
  usePluginPreview: () => ({
    data: { status: "succeeded", summary: { created: 3, updated: 1, skipped: 0, failed: 0 } },
  }),
}));
vi.mock("./plugin-param-form", () => ({
  PluginParamForm: () => <div data-testid="param-form" />,
}));

import { PluginRunPanel } from "./plugin-run-panel";

const manifest = {
  id: "dejesus_essentiality",
  name: "DeJesus essentiality",
  description: "d",
  target_records: ["essentiality"],
  default_generation_method: "imported",
  params: [],
  requires_secrets: [],
  // biome-ignore lint/suspicious/noExplicitAny: test fixture shortcut, avoids the full PluginManifestResponse shape
} as any;

describe("PluginRunPanel", () => {
  it("shows dry-run preview counts after Preview", async () => {
    render(<PluginRunPanel manifest={manifest} open onOpenChange={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /preview/i }));
    expect(startMutate).toHaveBeenCalledWith({
      pluginId: "dejesus_essentiality",
      data: { params: {}, dry_run: true },
    });
    expect(await screen.findByText(/create 3/i)).toBeInTheDocument();
  });

  it("navigates to the monitor after Run", async () => {
    render(<PluginRunPanel manifest={manifest} open onOpenChange={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /^run$/i }));
    expect(await screen.findByText("DeJesus essentiality")).toBeInTheDocument();
    // push is called with the run route
    expect(push).toHaveBeenCalledWith("/admin/imports/run-123");
  });
});
