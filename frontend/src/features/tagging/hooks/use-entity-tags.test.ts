/**
 * Regression test: useAssignTag must invalidate the orval-generated cache
 * keys for BOTH the entity's own tags and the global tags list, and show a
 * success toast.
 *
 * Strategy: capture the `onSuccess` callback that the hook passes to the
 * generated orval mutation hook, then call it directly and assert
 * `queryClient.invalidateQueries` was called with the generated URL keys.
 * Mirrors `features/target/hooks/use-targets.test.ts`.
 */
import { describe, expect, it, vi } from "vitest";

import {
  getGetEntityTagsApiV1EntityCollectionEntityIdTagsGetQueryKey,
  getListTagsApiV1TagsGetQueryKey,
} from "@/shared/lib/api/tags/tags";

// ── Mocks (hoisted before the module-under-test is imported) ──────────────

const mockInvalidateQueries = vi.fn();
const mockQueryClient = { invalidateQueries: mockInvalidateQueries };

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => mockQueryClient,
}));

// Capture the options passed to the orval mutation hook so we can invoke
// onSuccess directly without wiring up a full React / QueryClient tree.
let capturedAssignOptions: { mutation?: { onSuccess?: (...args: unknown[]) => void } } = {};

vi.mock("@/shared/lib/api/tags/tags", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/shared/lib/api/tags/tags")>();
  return {
    ...actual,
    useAssignEntityTagApiV1EntityCollectionEntityIdTagsPost: (options: {
      mutation?: { onSuccess?: (...args: unknown[]) => void };
    }) => {
      capturedAssignOptions = options;
      return { mutateAsync: vi.fn(), isPending: false };
    },
  };
});

vi.mock("@/shared/lib/toast", () => ({
  showSuccess: vi.fn(),
}));

// Import after mocks are declared (vi.mock is hoisted, so order is safe)
import { showSuccess } from "@/shared/lib/toast";
import { useAssignTag } from "./use-entity-tags";

// ── Tests ─────────────────────────────────────────────────────────────────

describe("useAssignTag — cache invalidation", () => {
  it("invalidates the entity-tags key and the tags list key, and shows a success toast", () => {
    mockInvalidateQueries.mockClear();
    vi.mocked(showSuccess).mockClear();

    // Calling the hook registers the onSuccess callback in capturedAssignOptions.
    useAssignTag("proteins", "test-protein-abc");

    const onSuccess = capturedAssignOptions.mutation?.onSuccess;
    expect(onSuccess, "onSuccess should be registered").toBeDefined();

    // Simulate a successful mutation.
    onSuccess?.({} /* data */, {} /* variables */, undefined /* context */);

    const expectedEntityTagsKey = getGetEntityTagsApiV1EntityCollectionEntityIdTagsGetQueryKey(
      "proteins",
      "test-protein-abc",
    );
    const expectedTagsListKey = getListTagsApiV1TagsGetQueryKey();

    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: expectedEntityTagsKey });
    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: expectedTagsListKey });
    expect(showSuccess).toHaveBeenCalledWith("Tag added");

    // Must NOT use a hand-rolled key.
    expect(mockInvalidateQueries).not.toHaveBeenCalledWith({ queryKey: ["entity-tags"] });
  });
});
