import { describe, expect, it, vi } from "vitest";

import { getListImportRunsApiV1ImportsGetQueryKey } from "@/shared/lib/api/imports/imports";

const mockInvalidateQueries = vi.fn();
vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ invalidateQueries: mockInvalidateQueries }),
}));

// biome-ignore lint/suspicious/noExplicitAny: captured callback shapes
let capturedStart: any = {};
// biome-ignore lint/suspicious/noExplicitAny: captured callback shapes
let capturedRun: any = {};

vi.mock("@/shared/lib/api/imports/imports", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/shared/lib/api/imports/imports")>();
  return {
    ...actual,
    // biome-ignore lint/suspicious/noExplicitAny: test stub
    useStartImportApiV1ImportsPost: (options: any) => {
      capturedStart = options;
      return { mutateAsync: vi.fn(), isPending: false };
    },
    useUploadEssentialityFileApiV1ImportsUploadsPost: () => ({ mutateAsync: vi.fn(), isPending: false }),
    useListImportRunsApiV1ImportsGet: () => ({ data: undefined, isLoading: false }),
    // biome-ignore lint/suspicious/noExplicitAny: test stub
    useGetImportRunApiV1ImportsImportRunIdGet: (_id: string, options: any) => {
      capturedRun = options;
      return { data: undefined, isLoading: false };
    },
  };
});

vi.mock("@/shared/lib/toast", () => ({ showSuccess: vi.fn() }));

import { useImportRun, useStartImport } from "./use-imports";

describe("useStartImport", () => {
  it("invalidates the list query key on success", () => {
    mockInvalidateQueries.mockClear();
    useStartImport();
    capturedStart.mutation?.onSuccess?.({}, {}, undefined);
    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: getListImportRunsApiV1ImportsGetQueryKey(),
    });
  });
});

describe("useImportRun polling", () => {
  it("polls every 2s while active and stops on a terminal status", () => {
    useImportRun("run-1");
    const refetch = capturedRun.query?.refetchInterval;
    expect(refetch).toBeDefined();
    expect(refetch({ state: { data: { status: "running" } } })).toBe(2000);
    expect(refetch({ state: { data: { status: "queued" } } })).toBe(2000);
    expect(refetch({ state: { data: { status: "succeeded" } } })).toBe(false);
    expect(refetch({ state: { data: undefined } })).toBe(false);
  });
});
