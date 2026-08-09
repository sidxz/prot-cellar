"use client";

import { Plus } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useTargetBiologySchema } from "@/features/protein-catalog/hooks/use-target-biology-schema";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import type { ExtensionFieldDefResponse, RecordKind } from "@/shared/lib/api/model";
import { ExtensionFieldType } from "@/shared/lib/api/model";
import { useBreadcrumbOverride } from "@/shared/lib/stores/breadcrumb-store";

import {
  useCreateFieldDef,
  useDeleteFieldDef,
  useFieldDefs,
  useUpdateFieldDef,
} from "../hooks/use-field-defs";
import {
  type DraftFieldRow,
  blankDraftRow,
  effectiveOptions,
  humanize,
  isRecordKind,
  parseOptions,
  toDraftRow,
} from "../types";
import { FieldRows } from "./field-rows";

const NAME_PATTERN = /^[a-z][a-z0-9_]*$/;

/** Mirrors the backend's `_validate_shape` (field_def.py) so an obviously-doomed
 *  request never leaves the browser: blank label, a new row's name not yet
 *  matching the JSONB-key pattern or colliding with a sibling, or an enum row
 *  with no options. */
function isRowInvalid(row: DraftFieldRow, rows: DraftFieldRow[]): boolean {
  if (!row.label.trim()) return true;
  if (!row.id) {
    const name = row.name.trim();
    if (!NAME_PATTERN.test(name)) return true;
    if (rows.filter((r) => r.name.trim() === name).length > 1) return true;
  }
  if (row.field_type === ExtensionFieldType.enum && parseOptions(row.optionsText).length === 0) {
    return true;
  }
  return false;
}

function sameOptions(a: string[] | null, b: string[] | null): boolean {
  const x = a ?? [];
  const y = b ?? [];
  return x.length === y.length && x.every((v, i) => v === y[i]);
}

/** Whether a saved row differs from the server copy it was seeded from —
 *  including a pure reorder, since `position` is the row's current index. */
function isDirty(row: DraftFieldRow, original: ExtensionFieldDefResponse, index: number): boolean {
  return (
    row.label.trim() !== original.label ||
    row.field_type !== original.field_type ||
    row.show_in_table !== original.show_in_table ||
    index !== original.position ||
    !sameOptions(effectiveOptions(row), original.options ?? null)
  );
}

interface ExtensionFieldEditorProps {
  kind: string;
}

/**
 * One kind's field declarations, edited as a local draft: add / edit / reorder
 * are all client-side until the screen-level Save persists whatever changed
 * (skipping untouched rows) and Cancel reverts to the last-saved state.
 * Delete is the exception — it is immediate (its own confirm, its own
 * request) rather than staged, matching every other delete in this app.
 */
export function ExtensionFieldEditor({ kind }: ExtensionFieldEditorProps) {
  const { data: schema } = useTargetBiologySchema();
  const { data, isLoading, isError } = useFieldDefs(isRecordKind(kind) ? kind : undefined);
  const create = useCreateFieldDef();
  const update = useUpdateFieldDef();
  const remove = useDeleteFieldDef();

  const kindLabel = schema?.kinds[kind]?.label ?? humanize(kind);
  useBreadcrumbOverride(kind, isRecordKind(kind) ? kindLabel : "");

  const [rows, setRows] = useState<DraftFieldRow[] | null>(null);
  const [saving, setSaving] = useState(false);

  // Seed the draft once, on the first successful load for this kind (the
  // route page keys this component on `kind`, so a kind switch remounts it
  // rather than reusing this effect). Never reseeds after that — a
  // background refetch must not clobber in-progress edits.
  // biome-ignore lint/correctness/useExhaustiveDependencies: intentionally seeds once; see comment above
  useEffect(() => {
    if (rows === null && data) setRows(data.map(toDraftRow));
  }, [data]);

  if (!isRecordKind(kind)) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-24 text-center text-muted-foreground">
        <p className="text-base font-semibold text-foreground">Unknown record kind</p>
        <Link
          href="/admin/extension-fields"
          className="text-sm text-primary underline-offset-4 hover:underline"
        >
          Back to extension fields
        </Link>
      </div>
    );
  }

  if (isLoading || rows === null) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }
  if (isError) {
    return (
      <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
        Failed to load fields for {kindLabel}.
      </div>
    );
  }

  const hasInvalidRow = rows.some((r) => isRowInvalid(r, rows));
  const attachesTo = schema?.kinds[kind]?.attaches_to;
  // Narrowed once, explicitly: `isRecordKind(kind)` above already guards every
  // path that reaches here, but that narrowing doesn't survive into the
  // closures below (TS widens `kind` back to `string` inside a nested
  // function), so re-assert the type here rather than casting at each call site.
  const validKind: RecordKind = kind;

  function addRow() {
    setRows((r) => [...(r ?? []), blankDraftRow()]);
  }

  function handleDeleteSaved(row: DraftFieldRow) {
    // `.mutate()`, not `.mutateAsync()`: `onDeleteSaved` is fire-and-forget
    // (`FieldRows` doesn't await it), so a rejected `mutateAsync` promise
    // would be an unhandled rejection. `.mutate()` never throws to the
    // caller — the per-call `onSuccess` below only removes the row locally
    // once the delete actually lands; a failure leaves it in place (the
    // global MutationCache already surfaces the error toast).
    remove.mutate(
      { fieldDefId: row.id as string },
      { onSuccess: () => setRows((r) => r?.filter((x) => x.key !== row.key) ?? r) },
    );
  }

  function handleCancel() {
    setRows(data ? data.map(toDraftRow) : []);
  }

  async function handleSave() {
    if (!rows) return;
    setSaving(true);
    try {
      const results = await Promise.allSettled(
        rows.map((row, index) => {
          if (!row.id) {
            return create.mutateAsync({
              data: {
                kind: validKind,
                name: row.name.trim(),
                label: row.label.trim(),
                field_type: row.field_type,
                options: effectiveOptions(row),
                position: index,
                show_in_table: row.show_in_table,
              },
            });
          }
          const original = data?.find((d) => d.id === row.id);
          if (original && isDirty(row, original, index)) {
            return update.mutateAsync({
              fieldDefId: row.id,
              data: {
                label: row.label.trim(),
                field_type: row.field_type,
                options: effectiveOptions(row),
                position: index,
                show_in_table: row.show_in_table,
              },
            });
          }
          return Promise.resolve(null);
        }),
      );
      // Pick up real ids/versions for whatever the batch actually persisted;
      // anything that failed or was skipped keeps its current draft value.
      setRows((prev) =>
        prev
          ? prev.map((row, i) => {
              const res = results[i];
              return res.status === "fulfilled" && res.value
                ? toDraftRow(res.value as ExtensionFieldDefResponse)
                : row;
            })
          : prev,
      );
    } finally {
      setSaving(false);
    }
  }

  const isBusy = saving || remove.isPending;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-semibold tracking-tight">{kindLabel}</h1>
          {attachesTo && (
            <Badge variant="outline" className="capitalize">
              {attachesTo}
            </Badge>
          )}
        </div>
        <Button type="button" size="sm" onClick={addRow} disabled={isBusy}>
          <Plus className="h-3.5 w-3.5" />
          Add field
        </Button>
      </div>

      <FieldRows rows={rows} onChange={setRows} onDeleteSaved={handleDeleteSaved} />

      <div className="flex items-center justify-end gap-2">
        <Button type="button" variant="outline" onClick={handleCancel} disabled={isBusy}>
          Cancel
        </Button>
        <Button
          type="button"
          onClick={handleSave}
          disabled={isBusy || hasInvalidRow}
          title={hasInvalidRow ? "Fix incomplete rows before saving" : undefined}
        >
          {saving ? "Saving…" : "Save"}
        </Button>
      </div>
    </div>
  );
}
