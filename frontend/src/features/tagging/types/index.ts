import type {
  AssignTagBody,
  EntityTagResponse,
  TagResponse,
  TaggedEntityResponse,
} from "@/shared/lib/api/model";

/** Plural URL segments the tagging API accepts as `entityCollection`. */
export type TaggableEntity =
  | "proteins"
  | "genes"
  | "targets"
  | "organisms"
  | "strains"
  | "proteomes";

/** Tag (alias of generated DTO — no narrowing needed). */
export type Tag = TagResponse;

/** A tag on an entity, plus assignment provenance (alias of generated DTO). */
export type EntityTag = EntityTagResponse;

/** Body for assigning a tag to an entity (alias of generated DTO). */
export type TagInput = AssignTagBody;

/** An entity that carries a given tag (alias of generated DTO). */
export type TaggedEntity = TaggedEntityResponse;
