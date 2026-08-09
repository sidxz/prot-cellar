import type { ExtensionFieldDefResponse } from "@/shared/lib/api/model";
import { ExtensionFieldType, RecordKind } from "@/shared/lib/api/model";

/** The eight target-biology record kinds, in declaration order. Kinds are a
 *  fixed set (no admin create/delete of a kind itself), so this doubles as
 *  the canonical iteration order for the kind-list screen. */
export const RECORD_KINDS: RecordKind[] = Object.values(RecordKind) as RecordKind[];

export function isRecordKind(value: string): value is RecordKind {
  return (RECORD_KINDS as string[]).includes(value);
}

/** Underscore -> space. Only used as a label fallback for the brief window
 *  before the target-biology schema (which carries the curated per-kind
 *  label) has loaded. */
export function humanize(s: string): string {
  return s.replace(/_/g, " ");
}

/**
 * One field declaration as edited in the admin screen. Deliberately not just
 * `ExtensionFieldDefResponse`: `options` is edited as raw comma-separated
 * text (parsed only at save — see `parseOptions`), and a not-yet-saved row
 * has no server `id` yet.
 */
export interface DraftFieldRow {
  /** Stable client-side identity for React keys/diffing. Sticks around after
   *  a save picks up a real `id`, so an in-progress edit is never remounted. */
  key: string;
  /** Present once the row exists on the server; undefined for a new row. */
  id?: string;
  name: string;
  label: string;
  field_type: ExtensionFieldType;
  /** Raw comma-separated input text; parsed to `string[]` only at save. */
  optionsText: string;
  show_in_table: boolean;
}

export function toDraftRow(f: ExtensionFieldDefResponse): DraftFieldRow {
  return {
    key: f.id,
    id: f.id,
    name: f.name,
    label: f.label,
    field_type: f.field_type as ExtensionFieldType,
    optionsText: (f.options ?? []).join(", "),
    show_in_table: f.show_in_table,
  };
}

export function blankDraftRow(): DraftFieldRow {
  return {
    key: crypto.randomUUID(),
    name: "",
    label: "",
    field_type: ExtensionFieldType.string,
    optionsText: "",
    show_in_table: false,
  };
}

/** Comma-separated free text -> string[]: trimmed, blanks dropped, order preserved. */
export function parseOptions(text: string): string[] {
  return text
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

/** `options` as it should be submitted. Only an enum field carries any —
 *  every other type must send exactly `null` (the backend 422s on a
 *  non-enum field carrying a non-null `options`, and on an enum field
 *  carrying none). */
export function effectiveOptions(row: DraftFieldRow): string[] | null {
  return row.field_type === ExtensionFieldType.enum ? parseOptions(row.optionsText) : null;
}
