import { useQueryClient } from "@tanstack/react-query";

import {
  getGetOrganizationApiV1OrganizationsOrgIdGetQueryKey,
  getListOrganizationsApiV1OrganizationsGetQueryKey,
  useCreateOrganizationApiV1OrganizationsPost,
  useGetOrganizationApiV1OrganizationsOrgIdGet,
  useListOrganizationsApiV1OrganizationsGet,
  useUpdateOrganizationApiV1OrganizationsOrgIdPatch,
} from "@/shared/lib/api/organizations/organizations";
import { showSuccess } from "@/shared/lib/toast";

/** List organizations with optional cursor pagination and an include-inactive toggle. */
export function useOrganizations(cursor?: string, includeInactive?: boolean) {
  return useListOrganizationsApiV1OrganizationsGet({
    cursor: cursor ?? undefined,
    include_inactive: includeInactive ?? undefined,
  });
}

/** Fetch a single organization by id. */
export function useOrganization(id: string) {
  return useGetOrganizationApiV1OrganizationsOrgIdGet(id);
}

/**
 * Create a new organization.
 * On success: invalidates the organizations list and shows a success toast.
 * No onError — the global MutationCache handles the error toast.
 */
export function useCreateOrganization() {
  const queryClient = useQueryClient();
  return useCreateOrganizationApiV1OrganizationsPost({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: getListOrganizationsApiV1OrganizationsGetQueryKey(),
        });
        showSuccess("Organization created");
      },
    },
  });
}

/**
 * Update an existing organization.
 * On success: invalidates both the list and the specific detail, then toasts.
 * No onError — the global MutationCache handles the error toast.
 */
export function useUpdateOrganization() {
  const queryClient = useQueryClient();
  return useUpdateOrganizationApiV1OrganizationsOrgIdPatch({
    mutation: {
      onSuccess: (_data, variables) => {
        queryClient.invalidateQueries({
          queryKey: getListOrganizationsApiV1OrganizationsGetQueryKey(),
        });
        queryClient.invalidateQueries({
          queryKey: getGetOrganizationApiV1OrganizationsOrgIdGetQueryKey(variables.orgId),
        });
        showSuccess("Organization updated");
      },
    },
  });
}
