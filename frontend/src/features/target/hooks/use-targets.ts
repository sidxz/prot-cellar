import { useQueryClient } from "@tanstack/react-query";

import {
  useCreateTargetApiV1TargetsPost,
  useGetTargetApiV1TargetsTargetIdGet,
  useListTargetsApiV1TargetsGet,
  useUpdateTargetApiV1TargetsTargetIdPatch,
} from "@/shared/lib/api/targets/targets";
import { showSuccess } from "@/shared/lib/toast";

import type { TargetListFilters } from "../types";
import { TARGETS_KEY, targetDetailKey } from "./query-keys";

/** List targets with optional filters and cursor-based pagination. */
export function useTargets(filters: TargetListFilters = {}, cursor?: string) {
  return useListTargetsApiV1TargetsGet({
    target_type: filters.targetType ?? undefined,
    chembl_id: filters.chemblId ?? undefined,
    cursor: cursor ?? undefined,
  });
}

/** Fetch a single target by id. */
export function useTarget(id: string) {
  return useGetTargetApiV1TargetsTargetIdGet(id);
}

/**
 * Create a new target.
 * On success: invalidates the targets list and shows a success toast.
 * No onError — the global MutationCache handles the error toast.
 */
export function useCreateTarget() {
  const queryClient = useQueryClient();
  return useCreateTargetApiV1TargetsPost({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: TARGETS_KEY });
        showSuccess("Target created");
      },
    },
  });
}

/**
 * Update an existing target.
 * On success: invalidates both the targets list and the specific target detail,
 * then shows a success toast.
 * No onError — the global MutationCache handles the error toast.
 */
export function useUpdateTarget() {
  const queryClient = useQueryClient();
  return useUpdateTargetApiV1TargetsTargetIdPatch({
    mutation: {
      onSuccess: (_data, variables) => {
        queryClient.invalidateQueries({ queryKey: TARGETS_KEY });
        queryClient.invalidateQueries({ queryKey: targetDetailKey(variables.targetId) });
        showSuccess("Target updated");
      },
    },
  });
}
