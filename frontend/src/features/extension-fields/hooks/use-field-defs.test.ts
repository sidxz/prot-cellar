import { describe, expect, it, vi } from "vitest";

import { getListFieldDefsApiV1ExtensionFieldsGetQueryKey } from "@/shared/lib/api/extension-fields/extension-fields";
import { getGetTargetBiologySchemaApiV1TargetBiologySchemaGetQueryKey } from "@/shared/lib/api/target-biology/target-biology";

// Real thing under test: does each mutation's onSuccess invalidate the schema query,
// not just the field-defs list. Every other test around this feature mocks
// `useTargetBiologySchema` wholesale (see extension-field-editor.test.tsx), which is
// exactly why a regression here went uncaught — a test that also mocks it would prove
// nothing. This one mocks only the generated API mutation hooks (to capture the
// `onSuccess` callback without a real network call) and spies on `invalidateQueries`.

const mockInvalidateQueries = vi.fn();
const mockQueryClient = { invalidateQueries: mockInvalidateQueries };

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => mockQueryClient,
}));

type CapturedOptions = { mutation?: { onSuccess?: (...args: unknown[]) => void } };
let capturedCreateOptions: CapturedOptions = {};
let capturedUpdateOptions: CapturedOptions = {};
let capturedDeleteOptions: CapturedOptions = {};

vi.mock("@/shared/lib/api/extension-fields/extension-fields", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/shared/lib/api/extension-fields/extension-fields")>();
  return {
    ...actual,
    useCreateFieldDefApiV1ExtensionFieldsPost: (options: CapturedOptions) => {
      capturedCreateOptions = options;
      return { mutateAsync: vi.fn(), isPending: false };
    },
    useUpdateFieldDefApiV1ExtensionFieldsFieldDefIdPatch: (options: CapturedOptions) => {
      capturedUpdateOptions = options;
      return { mutateAsync: vi.fn(), isPending: false };
    },
    useDeleteFieldDefApiV1ExtensionFieldsFieldDefIdDelete: (options: CapturedOptions) => {
      capturedDeleteOptions = options;
      return { mutateAsync: vi.fn(), isPending: false };
    },
  };
});

vi.mock("@/shared/lib/toast", () => ({ showSuccess: vi.fn() }));

import { useCreateFieldDef, useDeleteFieldDef, useUpdateFieldDef } from "./use-field-defs";

const fieldDefsKey = getListFieldDefsApiV1ExtensionFieldsGetQueryKey();
const schemaKey = getGetTargetBiologySchemaApiV1TargetBiologySchemaGetQueryKey();

describe("useCreateFieldDef — cache invalidation", () => {
  it("invalidates both the field-defs list and the published schema on success", () => {
    mockInvalidateQueries.mockClear();
    useCreateFieldDef();
    const onSuccess = capturedCreateOptions.mutation?.onSuccess;
    expect(onSuccess, "onSuccess should be registered").toBeDefined();
    onSuccess?.({}, {}, undefined);

    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: fieldDefsKey });
    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: schemaKey });
  });
});

describe("useUpdateFieldDef — cache invalidation", () => {
  it("invalidates both the field-defs list and the published schema on success", () => {
    mockInvalidateQueries.mockClear();
    useUpdateFieldDef();
    const onSuccess = capturedUpdateOptions.mutation?.onSuccess;
    expect(onSuccess, "onSuccess should be registered").toBeDefined();
    onSuccess?.({}, {}, undefined);

    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: fieldDefsKey });
    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: schemaKey });
  });
});

describe("useDeleteFieldDef — cache invalidation", () => {
  it("invalidates both the field-defs list and the published schema on success", () => {
    mockInvalidateQueries.mockClear();
    useDeleteFieldDef();
    const onSuccess = capturedDeleteOptions.mutation?.onSuccess;
    expect(onSuccess, "onSuccess should be registered").toBeDefined();
    onSuccess?.({}, {}, undefined);

    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: fieldDefsKey });
    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: schemaKey });
  });
});
