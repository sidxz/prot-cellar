// Types
export type { TaggableEntity, Tag, EntityTag, TagInput, TaggedEntity } from "./types";

// Hooks
export { useTags, useRenameTag, useDeleteTag, useMergeTags } from "./hooks/use-tags";
export {
  useEntityTags,
  useAssignTag,
  useUnassignTag,
  useSetEntityTags,
} from "./hooks/use-entity-tags";
export { useTagEntities } from "./hooks/use-tag-entities";
