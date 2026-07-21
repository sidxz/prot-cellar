import { useListTagEntitiesApiV1TagsEntitiesGet } from "@/shared/lib/api/tags/tags";

/** List entities carrying the given tag ids, optionally filtered by entity type. */
export function useTagEntities(
  tagIds: string[],
  tagLogic: "any" | "all" = "any",
  types?: string[],
) {
  return useListTagEntitiesApiV1TagsEntitiesGet({
    tags: tagIds,
    tag_logic: tagLogic,
    types,
  });
}
