import { useQueryClient } from "@tanstack/react-query";

import {
  getGetStrainApiV1StrainsStrainIdGetQueryKey,
  getListStrainsApiV1StrainsGetQueryKey,
  useCreateStrainApiV1StrainsPost,
  useGetStrainApiV1StrainsStrainIdGet,
  useListStrainsApiV1StrainsGet,
  useUpdateStrainApiV1StrainsStrainIdPatch,
} from "@/shared/lib/api/strains/strains";
import { showSuccess } from "@/shared/lib/toast";

import type { StrainListFilters } from "../types";

/** List strains with optional tag filters, cursor-based pagination, and page size. */
export function useStrains(filters: StrainListFilters = {}, cursor?: string, limit?: number) {
  return useListStrainsApiV1StrainsGet({
    tags: filters.tags ?? undefined,
    tag_logic: filters.tagLogic ?? undefined,
    cursor: cursor ?? undefined,
    limit: limit ?? undefined,
  });
}

/** Fetch a single strain by id. */
export function useStrain(id: string) {
  return useGetStrainApiV1StrainsStrainIdGet(id);
}

/**
 * Create a new strain.
 * On success: invalidates the strains list and shows a success toast.
 * No onError — the global MutationCache handles the error toast.
 */
export function useCreateStrain() {
  const queryClient = useQueryClient();
  return useCreateStrainApiV1StrainsPost({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListStrainsApiV1StrainsGetQueryKey() });
        showSuccess("Strain created");
      },
    },
  });
}

/**
 * Update an existing strain.
 * On success: invalidates both the strains list and the specific strain detail,
 * then shows a success toast.
 * No onError — the global MutationCache handles the error toast.
 */
export function useUpdateStrain() {
  const queryClient = useQueryClient();
  return useUpdateStrainApiV1StrainsStrainIdPatch({
    mutation: {
      onSuccess: (_data, variables) => {
        queryClient.invalidateQueries({ queryKey: getListStrainsApiV1StrainsGetQueryKey() });
        queryClient.invalidateQueries({
          queryKey: getGetStrainApiV1StrainsStrainIdGetQueryKey(variables.strainId),
        });
        showSuccess("Strain updated");
      },
    },
  });
}
