import { describe, expect, it, vi } from "vitest";

// biome-ignore lint/suspicious/noExplicitAny: captured callback shapes
let capturedStartRun: any = {};
// biome-ignore lint/suspicious/noExplicitAny: captured callback shapes
let capturedPreview: any = {};

vi.mock("@/shared/lib/api/plugins/plugins", () => ({
  useListPluginsApiV1PluginsGet: vi.fn(() => ({ data: [], isLoading: false })),
  // biome-ignore lint/suspicious/noExplicitAny: test stub
  useStartPluginRunApiV1PluginsPluginIdRunsPost: (options: any) => {
    capturedStartRun = options;
    return { mutateAsync: vi.fn(), isPending: false };
  },
}));
vi.mock("@/shared/lib/api/imports/imports", () => ({
  // biome-ignore lint/suspicious/noExplicitAny: test stub
  useGetImportRunApiV1ImportsImportRunIdGet: (_id: string, options: any) => {
    capturedPreview = options;
    return { data: undefined };
  },
}));

vi.mock("@/shared/lib/toast", () => ({ showSuccess: vi.fn() }));

import { useListPluginsApiV1PluginsGet } from "@/shared/lib/api/plugins/plugins";
import { showSuccess } from "@/shared/lib/toast";
import { usePluginCatalog, usePluginPreview, useStartPluginRun } from "./use-plugins";

describe("usePluginCatalog", () => {
  it("returns the plugin manifests from the generated hook", () => {
    const result = usePluginCatalog();
    expect(useListPluginsApiV1PluginsGet).toHaveBeenCalled();
    expect(result).toEqual({ data: [], isLoading: false });
  });
});

describe("useStartPluginRun", () => {
  it("shows a success toast when the run starts", () => {
    useStartPluginRun();
    capturedStartRun.mutation?.onSuccess?.({}, {}, undefined);
    expect(showSuccess).toHaveBeenCalledWith("Plugin run started");
  });
});

describe("usePluginPreview", () => {
  it("enables the query only when a runId is provided", () => {
    usePluginPreview("run-1");
    expect(capturedPreview.query?.enabled).toBe(true);

    usePluginPreview(null);
    expect(capturedPreview.query?.enabled).toBe(false);
  });

  it("polls every 2s while active and stops on a terminal status", () => {
    usePluginPreview("run-1");
    const refetch = capturedPreview.query?.refetchInterval;
    expect(refetch).toBeDefined();
    expect(refetch({ state: { data: { status: "queued" } } })).toBe(2000);
    expect(refetch({ state: { data: { status: "running" } } })).toBe(2000);
    expect(refetch({ state: { data: { status: "succeeded" } } })).toBe(false);
    expect(refetch({ state: { data: undefined } })).toBe(false);
  });
});
