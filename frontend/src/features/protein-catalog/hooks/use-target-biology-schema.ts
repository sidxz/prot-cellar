import { useGetTargetBiologySchemaApiV1TargetBiologySchemaGet } from "@/shared/lib/api/target-biology/target-biology";

/**
 * One field in a kind's (or provenance's) write-contract descriptor.
 *
 * `type` is documented rather than a literal union — the response comes back
 * as `{[key: string]: unknown}` (see below), and object-literal fixtures used
 * in tests widen string-literal properties to `string` anyway, so a narrow
 * union would reject perfectly valid descriptor data at the type level.
 * Known values: "string" | "text" | "number" | "integer" | "boolean" |
 * "enum" | "date" | "list" | "reference".
 */
export interface FieldDescriptor {
  name: string;
  label: string;
  type: string;
  required: boolean;
  /** Allowed values for an "enum" field. */
  options?: string[];
  /** Non-exclusive suggestions for a free-text vocabulary field. */
  suggested_values?: string[];
  min?: number;
  max?: number;
  /** Element shape for a "list" field. */
  item_type?: string;
  item_fields?: FieldDescriptor[];
  /** Referenced resource type for a "reference" field. */
  target?: string;
  /** Extension-field declarations only: whether it renders as a record-table
   *  column. Absent on core fields. */
  show_in_table?: boolean;
}

export interface KindDescriptor {
  label: string;
  attaches_to: string;
  fields: FieldDescriptor[];
  read_only?: string[];
  /** This workspace's admin-defined extra fields for the kind, already
   *  ordered by `position` (ties broken by name) — see `extension-fields`. */
  extension_fields: FieldDescriptor[];
}

/** The published `GET /target-biology/schema` write contract. */
export interface TargetBiologySchema {
  provenance: { fields: FieldDescriptor[] };
  kinds: Record<string, KindDescriptor>;
  concurrency: { field: string };
}

/** The published write contract. `staleTime: Infinity` is safe even though the
 *  admin-declared part of it (`extension_fields`) can change at runtime, because the
 *  one mutation path that changes it — declaring, editing, or deleting an extension
 *  field (`use-field-defs.ts`) — explicitly invalidates this query's key. Anything
 *  else refetching it on focus would be pure noise.
 *
 * The generated hook types its response as `{[key: string]: unknown}` (orval
 * can't know the shape of a schema endpoint's payload); narrow it once here
 * rather than casting at every call site. */
export function useTargetBiologySchema() {
  const query = useGetTargetBiologySchemaApiV1TargetBiologySchemaGet({
    query: { staleTime: Number.POSITIVE_INFINITY },
  });
  return { ...query, data: query.data as TargetBiologySchema | undefined };
}
