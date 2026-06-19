/**
 * Regression test: useCreateStrain and useUpdateStrain must invalidate the
 * orval-generated cache keys, not the old hand-rolled ["strains"] keys.
 *
 * Strategy: capture the `onSuccess` callback that each hook passes to the
 * generated orval hook, then call it directly and assert that
 * `queryClient.invalidateQueries` was called with the generated URL keys.
 */
import { describe, expect, it, vi } from "vitest";

import {
  getGetStrainApiV1StrainsStrainIdGetQueryKey,
  getListStrainsApiV1StrainsGetQueryKey,
} from "@/shared/lib/api/strains/strains";

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

vi.mock("@/shared/lib/api/strains/strains", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/shared/lib/api/strains/strains")>();
  return {
    ...actual,
    useCreateStrainApiV1StrainsPost: (options: {
      mutation?: { onSuccess?: (...args: unknown[]) => void };
    }) => {
      capturedCreateOptions = options;
      return { mutateAsync: vi.fn(), isPending: false };
    },
    useUpdateStrainApiV1StrainsStrainIdPatch: (options: {
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
import { useCreateStrain, useUpdateStrain } from "./use-strains";

// ── Tests ─────────────────────────────────────────────────────────────────

describe("useCreateStrain — cache invalidation", () => {
  it("invalidates the generated list query key on success", () => {
    mockInvalidateQueries.mockClear();

    // Calling the hook registers the onSuccess callback in capturedCreateOptions.
    useCreateStrain();

    const onSuccess = capturedCreateOptions.mutation?.onSuccess;
    expect(onSuccess, "onSuccess should be registered").toBeDefined();

    // Simulate a successful mutation.
    onSuccess?.({} /* data */, {} /* variables */, undefined /* context */);

    const expectedListKey = getListStrainsApiV1StrainsGetQueryKey();
    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: expectedListKey,
    });

    // Must NOT use the old hand-rolled key.
    expect(mockInvalidateQueries).not.toHaveBeenCalledWith({
      queryKey: ["strains"],
    });
  });
});

describe("useUpdateStrain — cache invalidation", () => {
  it("invalidates BOTH the list key AND the detail key on success", () => {
    mockInvalidateQueries.mockClear();

    useUpdateStrain();

    const onSuccess = capturedUpdateOptions.mutation?.onSuccess;
    expect(onSuccess, "onSuccess should be registered").toBeDefined();

    const strainId = "test-strain-abc";
    // Simulate a successful mutation with variables containing strainId.
    onSuccess?.({} /* data */, { strainId } /* variables */, undefined);

    const expectedListKey = getListStrainsApiV1StrainsGetQueryKey();
    const expectedDetailKey = getGetStrainApiV1StrainsStrainIdGetQueryKey(strainId);

    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: expectedListKey });
    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: expectedDetailKey });

    // Verify the detail key resolves to the URL-based form, not the old hand-rolled form.
    expect(expectedDetailKey).toContain(`/api/v1/strains/${strainId}`);

    // Must NOT use old hand-rolled keys.
    expect(mockInvalidateQueries).not.toHaveBeenCalledWith({ queryKey: ["strains"] });
    expect(mockInvalidateQueries).not.toHaveBeenCalledWith({
      queryKey: ["strains", strainId],
    });
  });
});
