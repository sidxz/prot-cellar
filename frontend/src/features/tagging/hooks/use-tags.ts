import { useQueryClient } from "@tanstack/react-query";

import type { ListTagsApiV1TagsGetParams } from "@/shared/lib/api/model";
import {
  getListTagsApiV1TagsGetQueryKey,
  useDeleteTagApiV1TagsTagIdDelete,
  useListTagsApiV1TagsGet,
  useMergeTagApiV1TagsTagIdMergePost,
  useRenameTagApiV1TagsTagIdPatch,
} from "@/shared/lib/api/tags/tags";
import { showSuccess } from "@/shared/lib/toast";

/** List tags, optionally filtered by search text / mine-only / limit. */
export function useTags(params: ListTagsApiV1TagsGetParams = {}) {
  return useListTagsApiV1TagsGet(params);
}

/**
 * Rename a tag's key/value.
 * On success: invalidates the tags list and shows a success toast.
 * No onError — the global MutationCache handles the error toast.
 */
export function useRenameTag() {
  const queryClient = useQueryClient();
  return useRenameTagApiV1TagsTagIdPatch({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListTagsApiV1TagsGetQueryKey() });
        showSuccess("Tag renamed");
      },
    },
  });
}

/**
 * Delete a tag (and all its entity assignments).
 * On success: invalidates the tags list and shows a success toast.
 * No onError — the global MutationCache handles the error toast.
 */
export function useDeleteTag() {
  const queryClient = useQueryClient();
  return useDeleteTagApiV1TagsTagIdDelete({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListTagsApiV1TagsGetQueryKey() });
        showSuccess("Tag deleted");
      },
    },
  });
}

/**
 * Merge a tag into another tag, reassigning all of its entity tags.
 * On success: invalidates the tags list and shows a success toast.
 * No onError — the global MutationCache handles the error toast.
 */
export function useMergeTags() {
  const queryClient = useQueryClient();
  return useMergeTagApiV1TagsTagIdMergePost({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: getListTagsApiV1TagsGetQueryKey() });
        showSuccess("Tags merged");
      },
    },
  });
}
