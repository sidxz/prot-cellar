import { useQueryClient } from "@tanstack/react-query";

import {
  getGetEntityTagsApiV1EntityCollectionEntityIdTagsGetQueryKey,
  getListTagsApiV1TagsGetQueryKey,
  useAssignEntityTagApiV1EntityCollectionEntityIdTagsPost,
  useGetEntityTagsApiV1EntityCollectionEntityIdTagsGet,
  useSetEntityTagsApiV1EntityCollectionEntityIdTagsPut,
  useUnassignEntityTagApiV1EntityCollectionEntityIdTagsTagIdDelete,
} from "@/shared/lib/api/tags/tags";
import { showSuccess } from "@/shared/lib/toast";

import type { TaggableEntity } from "../types";

/** List the tags assigned to a single entity. */
export function useEntityTags(entity: TaggableEntity, id: string) {
  return useGetEntityTagsApiV1EntityCollectionEntityIdTagsGet(entity, id);
}

/** Invalidate the entity's own tags AND the global tags list (assignment counts change it). */
function invalidateAfterTagChange(
  queryClient: ReturnType<typeof useQueryClient>,
  entity: TaggableEntity,
  id: string,
) {
  queryClient.invalidateQueries({
    queryKey: getGetEntityTagsApiV1EntityCollectionEntityIdTagsGetQueryKey(entity, id),
  });
  queryClient.invalidateQueries({ queryKey: getListTagsApiV1TagsGetQueryKey() });
}

/**
 * Assign a tag to an entity.
 * On success: invalidates the entity's tags and the tags list, then shows a
 * success toast. No onError — the global MutationCache handles the error toast.
 */
export function useAssignTag(entity: TaggableEntity, id: string) {
  const queryClient = useQueryClient();
  return useAssignEntityTagApiV1EntityCollectionEntityIdTagsPost({
    mutation: {
      onSuccess: () => {
        invalidateAfterTagChange(queryClient, entity, id);
        showSuccess("Tag added");
      },
    },
  });
}

/**
 * Replace all tags on an entity in a single call.
 * On success: invalidates the entity's tags and the tags list, then shows a
 * success toast. No onError — the global MutationCache handles the error toast.
 */
export function useSetEntityTags(entity: TaggableEntity, id: string) {
  const queryClient = useQueryClient();
  return useSetEntityTagsApiV1EntityCollectionEntityIdTagsPut({
    mutation: {
      onSuccess: () => {
        invalidateAfterTagChange(queryClient, entity, id);
        showSuccess("Tags updated");
      },
    },
  });
}

/**
 * Remove a tag from an entity.
 * On success: invalidates the entity's tags and the tags list, then shows a
 * success toast. No onError — the global MutationCache handles the error toast.
 */
export function useUnassignTag(entity: TaggableEntity, id: string) {
  const queryClient = useQueryClient();
  return useUnassignEntityTagApiV1EntityCollectionEntityIdTagsTagIdDelete({
    mutation: {
      onSuccess: () => {
        invalidateAfterTagChange(queryClient, entity, id);
        showSuccess("Tag removed");
      },
    },
  });
}
