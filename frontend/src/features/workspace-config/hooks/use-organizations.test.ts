import { describe, expect, it, vi } from "vitest";

import {
  getGetOrganizationApiV1OrganizationsOrgIdGetQueryKey,
  getListOrganizationsApiV1OrganizationsGetQueryKey,
} from "@/shared/lib/api/organizations/organizations";

const mockInvalidateQueries = vi.fn();
const mockQueryClient = { invalidateQueries: mockInvalidateQueries };

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: () => mockQueryClient,
}));

let capturedCreateOptions: { mutation?: { onSuccess?: (...args: unknown[]) => void } } = {};
let capturedUpdateOptions: { mutation?: { onSuccess?: (...args: unknown[]) => void } } = {};

vi.mock("@/shared/lib/api/organizations/organizations", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/shared/lib/api/organizations/organizations")>();
  return {
    ...actual,
    useCreateOrganizationApiV1OrganizationsPost: (options: {
      mutation?: { onSuccess?: (...args: unknown[]) => void };
    }) => {
      capturedCreateOptions = options;
      return { mutateAsync: vi.fn(), isPending: false };
    },
    useUpdateOrganizationApiV1OrganizationsOrgIdPatch: (options: {
      mutation?: { onSuccess?: (...args: unknown[]) => void };
    }) => {
      capturedUpdateOptions = options;
      return { mutateAsync: vi.fn(), isPending: false };
    },
  };
});

vi.mock("@/shared/lib/toast", () => ({ showSuccess: vi.fn() }));

import { useCreateOrganization, useUpdateOrganization } from "./use-organizations";

describe("useCreateOrganization — cache invalidation", () => {
  it("invalidates the generated list query key on success", () => {
    mockInvalidateQueries.mockClear();
    useCreateOrganization();
    const onSuccess = capturedCreateOptions.mutation?.onSuccess;
    expect(onSuccess, "onSuccess should be registered").toBeDefined();
    onSuccess?.({}, {}, undefined);

    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: getListOrganizationsApiV1OrganizationsGetQueryKey(),
    });
    expect(mockInvalidateQueries).not.toHaveBeenCalledWith({ queryKey: ["organizations"] });
  });
});

describe("useUpdateOrganization — cache invalidation", () => {
  it("invalidates BOTH the list key AND the detail key on success", () => {
    mockInvalidateQueries.mockClear();
    useUpdateOrganization();
    const onSuccess = capturedUpdateOptions.mutation?.onSuccess;
    expect(onSuccess, "onSuccess should be registered").toBeDefined();

    const orgId = "test-org-abc";
    onSuccess?.({}, { orgId }, undefined);

    const expectedDetailKey = getGetOrganizationApiV1OrganizationsOrgIdGetQueryKey(orgId);
    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: getListOrganizationsApiV1OrganizationsGetQueryKey(),
    });
    expect(mockInvalidateQueries).toHaveBeenCalledWith({ queryKey: expectedDetailKey });
    expect(expectedDetailKey).toContain(`/api/v1/organizations/${orgId}`);
    expect(mockInvalidateQueries).not.toHaveBeenCalledWith({ queryKey: ["organizations"] });
    expect(mockInvalidateQueries).not.toHaveBeenCalledWith({ queryKey: ["organizations", orgId] });
  });
});
