/**
 * Regression test: useCreateTarget and useUpdateTarget must invalidate the
 * orval-generated cache keys, not the old hand-rolled ["targets"] keys.
 *
 * Strategy: capture the `onSuccess` callback that each hook passes to the
 * generated orval hook, then call it directly and assert that
 * `queryClient.invalidateQueries` was called with the generated URL keys.
 */
import { describe, expect, it, vi } from "vitest";

import {
  getGetTargetApiV1TargetsTargetIdGetQueryKey,
  getListTargetsApiV1TargetsGetQueryKey,
} from "@/shared/lib/api/targets/targets";

// ── Mocks (hoisted before the module-under-test is imported) ──────────────

const mockInvalidateQueries = vi.fn();
const mockQueryClient = { invalidateQueries: mockInvalidateQueries };

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => mockQueryClient,
}));

// Capture the options passed to the orval mutation hooks so we can invoke
// onSuccess directly without wiring up a full React / QueryClient tree.
let capturedCreateOptions: { mutation?: { onSuccess?: (...args: unknown[]) => void } } = {};
let capturedUpdateOptions: { mutation?: { onSuccess?: (...args: unknown[]) => void } } = {};

vi.mock("@/shared/lib/api/targets/targets", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/shared/lib/api/targets/targets")>();
  return {
    ...actual,
    useCreateTargetApiV1TargetsPost: (options: {
      mutation?: { onSuccess?: (...args: unknown[]) => void };
    }) => {
      capturedCreateOptions = options;
      return { mutateAsync: vi.fn(), isPending: false };
    },
    useUpdateTargetApiV1TargetsTargetIdPatch: (options: {
      mutation?: { onSuccess?: (...args: unknown[]) => void };
    }) => {
      capturedUpdateOptions = options;
      return { mutateAsync: vi.fn(), isPending: false };
    },
  };
});

vi.mock("@/shared/lib/toast", () => ({
  showSuccess: vi.fn(),
}));

// Import after mocks are declared (vi.mock is hoisted, so order is safe)
import { useCreateTarget, useUpdateTarget } from "./use-targets";

// ── Tests ─────────────────────────────────────────────────────────────────

describe("useCreateTarget — cache invalidation", () => {
  it("invalidates the generated list query key on success", () => {
    mockInvalidateQueries.mockClear();

    // Calling the hook registers the onSuccess callback in capturedCreateOptions.
    useCreateTarget();

    const onSuccess = capturedCreateOptions.mutation?.onSuccess;
    expect(onSuccess, "onSuccess should be registered").toBeDefined();

    // Simulate a successful mutation.
    onSuccess?.({} /* data */, {} /* variables */, undefined /* context */);

    const expectedListKey = getListTargetsApiV1TargetsGetQueryKey();
    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: expectedListKey,
    });

    // Must NOT use the old hand-rolled key.
    expect(mockInvalidateQueries).not.toHaveBeenCalledWith({
      queryKey: ["targets"],
    });
  });
});

describe("useUpdateTarget — cache invalidation", () => {
  it("invalidates BOTH the list key AND the detail key on success", () => {
    mockInvalidateQueries.mockClear();

    useUpdateTarget();

    const onSuccess = capturedUpdateOptions.mutation?.onSuccess;
    expect(onSuccess, "onSuccess should be registered").toBeDefined();

    const targetId = "test-target-abc";
    // Simulate a successful mutation with variables containing targetId.
    onSuccess?.({} /* data */, { targetId } /* variables */, undefined);

    const expectedListKey = getListTargetsApiV1TargetsGetQueryKey();
    const expectedDetailKey = getGetTargetApiV1TargetsTargetIdGetQueryKey(targetId);

    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: expectedListKey });
    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: expectedDetailKey });

    // Verify the detail key resolves to the URL-based form, not the old hand-rolled form.
    expect(expectedDetailKey).toContain(`/api/v1/targets/${targetId}`);

    // Must NOT use old hand-rolled keys.
    expect(mockInvalidateQueries).not.toHaveBeenCalledWith({ queryKey: ["targets"] });
    expect(mockInvalidateQueries).not.toHaveBeenCalledWith({
      queryKey: ["targets", targetId],
    });
  });
});
