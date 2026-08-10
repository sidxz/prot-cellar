"use client";

import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/shared/components/ui/tooltip";
import type { ProvenanceBody, ProvenanceSourceType } from "@/shared/lib/api/model";
import { showError, showSuccess } from "@/shared/lib/toast";
import { cn } from "@/shared/lib/utils";
import { BookOpen, Check, Info, ListPlus, Loader2, Pencil, Plus, Trash2, X } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";
import { useState } from "react";

import type { FieldDescriptor } from "../../hooks/use-target-biology-schema";
import { ExtensionValuesDialog } from "./extension-values-dialog";
import { ProvenanceDialog } from "./provenance-dialog";

export const humanize = (s: string) => s.replace(/_/g, " ");

/** The only provenance a brand-new record can carry at create time: `source_type` is the
 * one field `*WriteBody.provenance` requires, and the curator sets the rest — citations,
 * contributor, observed date — through the Provenance… dialog right after creating. Reads
 * the descriptor's own first offered `source_type` rather than a hard-coded literal, so this
 * tracks the backend's enum instead of drifting from it if it's ever reordered or renamed. */
export function defaultProvenance(provenanceFields: FieldDescriptor[]): ProvenanceBody {
  const sourceType = provenanceFields.find((f) => f.name === "source_type")?.options?.[0];
  return { source_type: (sourceType ?? "published") as ProvenanceSourceType };
}

type BadgeVariant = NonNullable<ComponentProps<typeof Badge>["variant"]>;

/** Map how-a-value-was-produced → badge color. AI = blue; imported/computed =
 * neutral; manual (and anything unknown) = foreground outline. */
export function generationMethodBadgeVariant(method: string | null | undefined): BadgeVariant {
  switch (method) {
    case "ai_extracted":
    case "ai_predicted":
      return "info";
    case "imported":
    case "computed":
      return "secondary";
    default:
      return "outline";
  }
}

/** Whether a record's provenance was AI-generated (extracted or predicted). */
export function isAiGenerated(method: string | null | undefined): boolean {
  return method === "ai_extracted" || method === "ai_predicted";
}

/** Coerce a text-input string to a nullable number / nullable trimmed string for a write body. */
export const numOrNull = (s: string): number | null => (s.trim() ? Number(s) : null);
export const strOrNull = (s: string): string | null => (s.trim() ? s.trim() : null);

const NEW = "__new__";

/** Minimal provenance shape as it comes back on any record response. */
interface ProvLike {
  source_type: string;
  generation_method: string;
  citations: { pmid?: string | null }[];
  note?: string | null;
}

function PmidCell({ p }: { p: ProvLike }) {
  const pmid = p.citations[0]?.pmid;
  if (!pmid) return <>—</>;
  return (
    <a
      href={`https://pubmed.ncbi.nlm.nih.gov/${pmid}/`}
      target="_blank"
      rel="noopener noreferrer"
      className="text-primary hover:underline"
    >
      PMID:{pmid}
    </a>
  );
}

function ProvenanceSourceBadge({ p }: { p: ProvLike }) {
  const method = p.generation_method || "manual";
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge
          variant={generationMethodBadgeVariant(method)}
          aria-label={`Source: ${humanize(p.source_type)}. Generated: ${humanize(method)}.`}
        >
          {humanize(p.source_type)}
        </Badge>
      </TooltipTrigger>
      <TooltipContent className="text-xs">
        <div>Source: {humanize(p.source_type)}</div>
        <div>Generated: {humanize(method)}</div>
        {p.citations[0]?.pmid ? <div>PMID: {p.citations[0].pmid}</div> : null}
        {p.note ? <div>{p.note}</div> : null}
      </TooltipContent>
    </Tooltip>
  );
}

/** The three shared, read-only provenance columns appended to every record's
 * table. Provenance itself is edited through the Provenance… dialog, not
 * inline — see the per-row action in EditableRecordTable. */
export function provColumns<R extends { provenance: ProvLike }>() {
  return [
    { label: "Source", render: (r: R) => <ProvenanceSourceBadge p={r.provenance} /> },
    { label: "Reference", render: (r: R) => <PmidCell p={r.provenance} /> },
    {
      label: "Note",
      render: (r: R) => <span className="text-muted-foreground">{r.provenance.note ?? "—"}</span>,
    },
  ];
}

/** Render a declared or unmapped extension value the way the table already
 * formats core fields of that type: Yes/No for boolean, humanized text for
 * enum, the raw value otherwise. `type` is `undefined` for an unmapped
 * (undeclared) key — there is no declaration to key off, so it renders as-is. */
function renderExtensionValue(type: string | undefined, value: unknown): ReactNode {
  if (value === null || value === undefined || value === "") return "—";
  if (type === "boolean") return value ? "Yes" : "No";
  if (type === "enum") return humanize(String(value));
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

/** Read-only columns for a kind's `show_in_table` extension-field declarations,
 * in the descriptor's own `position` order. Spread these in after the core
 * columns and before `provColumns()` — see any of the per-kind tables.
 * Declared fields that aren't `show_in_table`, and undeclared ("unmapped")
 * keys, don't get a column; both still surface in the per-row detail popover
 * instead (the table's `extensionFields` prop, same array passed here). */
export function extensionColumns<R extends { extensions?: Record<string, unknown> }>(
  fields: FieldDescriptor[],
) {
  return fields
    .filter((f) => f.show_in_table)
    .map((f) => ({
      // `f.name` is unique per kind by construction (DB constraint on
      // (workspace_id, kind, name)); `f.label` is admin-entered free text
      // with no uniqueness check anywhere, so it can't safely be the React
      // key — two declarations sharing a label, or one colliding with a
      // hardcoded core column's label (e.g. "Method"), would collide.
      key: f.name,
      label: f.label,
      render: (r: R) => renderExtensionValue(f.type, r.extensions?.[f.name]),
    }));
}

export interface Column<R, D> {
  label: string;
  /** React key when `label` alone isn't safely unique (see `extensionColumns`
   * above); falls back to `label` when omitted, which every hardcoded core
   * column does. */
  key?: string;
  /** Draft key this cell edits; omit for a read-only column (e.g. a compound ref). */
  field?: Extract<keyof D, string>;
  type?: "text" | "number" | "enum" | "bool";
  options?: readonly string[];
  placeholder?: string;
  render: (record: R) => React.ReactNode;
}

const TH =
  "px-2 py-1.5 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground";
const TD = "px-2 py-1.5 align-top";

/** Every declared extension field's current value, plus any stored key with
 * no matching declaration ("unmapped"). The one place a curator can see the
 * complete `extensions` bag, not just whatever happens to be a table column.
 * Read-only — an edit affordance is a later pass, not this one. */
function ExtensionDetail({
  fields,
  extensions,
}: {
  fields: FieldDescriptor[];
  extensions: Record<string, unknown>;
}) {
  const declared = new Set(fields.map((f) => f.name));
  const unmapped = Object.keys(extensions).filter((k) => !declared.has(k));
  return (
    <PopoverContent className="w-72 text-xs" align="end">
      <div className="flex flex-col gap-2">
        {fields.length === 0 && unmapped.length === 0 && (
          <p className="text-muted-foreground">No extension values.</p>
        )}
        {fields.map((f) => (
          <div key={f.name} className="flex items-baseline justify-between gap-3">
            <span className="text-muted-foreground">{f.label}</span>
            <span className="text-right text-foreground">
              {renderExtensionValue(f.type, extensions[f.name])}
            </span>
          </div>
        ))}
        {unmapped.length > 0 && (
          <div
            className={cn(
              "flex flex-col gap-2",
              fields.length > 0 && "border-t border-border pt-2",
            )}
          >
            {unmapped.map((key) => (
              <div key={key} className="flex items-baseline justify-between gap-3">
                <span className="flex items-center gap-1.5 text-muted-foreground">
                  {key}
                  <Badge variant="outline" className="font-normal">
                    Unmapped
                  </Badge>
                </span>
                <span className="text-right text-foreground">
                  {renderExtensionValue(undefined, extensions[key])}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </PopoverContent>
  );
}

interface Props<
  R extends {
    id: string;
    version: number;
    provenance: object;
    is_shared?: boolean;
    extensions?: Record<string, unknown>;
  },
  D extends Record<string, unknown>,
> {
  title: string;
  description: string;
  records: R[];
  columns: Column<R, D>[];
  emptyDraft: D;
  toDraft: (r: R) => D;
  toBody: (d: D) => unknown;
  onCreate: (body: unknown) => Promise<unknown>;
  onUpdate: (id: string, body: unknown) => Promise<unknown>;
  onDelete: (id: string) => Promise<unknown>;
  busy: boolean;
  /** Optional visualization rendered inside the section, above the table. */
  visualization?: ReactNode;
  /** When true for a record, its whole row renders in dark-blue (AI provenance). */
  isAiRow?: (record: R) => boolean;
  /** Provenance descriptor fields from the write-contract schema, used to render
   * the per-row Provenance… dialog. Optional so the generic mechanics test
   * doesn't need a schema fixture; real callers always pass the fetched fields. */
  provenanceFields?: FieldDescriptor[];
  /** This kind's declared extension fields — all of them, any `show_in_table`
   * value — used to list every declared value (plus unmapped stored keys) in
   * the per-row detail popover, and to build the per-row Extra fields… edit
   * dialog. `extensionColumns()` above turns the `show_in_table` subset into
   * actual columns; pass the same array everywhere. Optional for the same
   * reason `provenanceFields` is. */
  extensionFields?: FieldDescriptor[];
}

export function EditableRecordTable<
  R extends {
    id: string;
    version: number;
    provenance: object;
    is_shared?: boolean;
    extensions?: Record<string, unknown>;
  },
  D extends Record<string, unknown>,
>({
  title,
  description,
  records,
  columns,
  emptyDraft,
  toDraft,
  toBody,
  onCreate,
  onUpdate,
  onDelete,
  busy,
  visualization,
  isAiRow,
  provenanceFields = [],
  extensionFields = [],
}: Props<R, D>) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<D>(emptyDraft);
  const [provenanceTarget, setProvenanceTarget] = useState<R | null>(null);
  const [extensionsTarget, setExtensionsTarget] = useState<R | null>(null);
  // Extension values picked for the row currently being created/edited. Held
  // separately from `draft` so the per-kind `D` type and `toBody` never need to
  // know about extensions — `save()` below merges this in for both create and
  // update, the same way in both cases, which is what keeps this immune to the
  // toBody-diverges-between-POST-and-PATCH bug class (see `saveExtensions`'s
  // comment on the same PATCH-vs-POST shape).
  const [draftExtensions, setDraftExtensions] = useState<Record<string, unknown>>({});
  const [draftExtensionsOpen, setDraftExtensionsOpen] = useState(false);
  // The saved record behind the row being edited — undefined while creating.
  // Seeds the draft extensions dialog from what's actually stored, same as the
  // saved-row Extra fields… action does via `extensionsTarget` below.
  const editingRecord = records.find((r) => r.id === editingId);
  const set = (field: string, value: unknown) => setDraft((d) => ({ ...d, [field]: value }));

  async function save() {
    try {
      const body = toBody(draft);
      // Only merge in an `extensions` key when the curator actually opened the
      // dialog and changed something — an untouched kind (or an untouched
      // dialog) sends exactly what `toBody` produced, unchanged.
      const withExtensions =
        Object.keys(draftExtensions).length > 0
          ? { ...(body as Record<string, unknown>), extensions: draftExtensions }
          : body;
      if (editingId === NEW) {
        await onCreate(withExtensions);
        showSuccess(`${title} record added`);
      } else if (editingId) {
        await onUpdate(editingId, withExtensions);
        showSuccess(`${title} record updated`);
      }
      setEditingId(null);
      setDraftExtensions({});
    } catch (e) {
      showError(e);
    }
  }

  async function del(id: string) {
    if (!window.confirm(`Delete this ${title.toLowerCase()} record?`)) return;
    try {
      await onDelete(id);
      showSuccess(`${title} record deleted`);
    } catch (e) {
      showError(e);
    }
  }

  /** Persists a provenance-dialog save. Kept separate from `save()` above:
   * this always PATCHes an existing record (never creates), and on a 409 the
   * dialog must stay open with the user's edits intact — no silent retry,
   * no discarding their input. */
  async function saveProvenance(body: Record<string, unknown>) {
    if (!provenanceTarget) return;
    try {
      await onUpdate(provenanceTarget.id, { provenance: body, version: provenanceTarget.version });
      showSuccess(`${title} provenance updated`);
      setProvenanceTarget(null);
    } catch (e) {
      showError(e);
    }
  }

  /** Persists an Extra fields… dialog save. Same shape as `saveProvenance`
   * above: always PATCHes an existing record, and on a 409 the dialog stays
   * open with the curator's edits intact. `changes` already holds only the
   * keys that changed — the dialog computed that diff before ever calling
   * this, and the backend merges it onto the record's stored bag rather than
   * replacing it. */
  async function saveExtensions(changes: Record<string, unknown>) {
    if (!extensionsTarget) return;
    try {
      await onUpdate(extensionsTarget.id, {
        extensions: changes,
        version: extensionsTarget.version,
      });
      showSuccess(`${title} extra fields updated`);
      setExtensionsTarget(null);
    } catch (e) {
      showError(e);
    }
  }

  function editCell(col: Column<R, D>) {
    if (!col.field) return <span className="text-xs text-muted-foreground">—</span>;
    const field = col.field;
    const value = draft[field];
    if (col.type === "enum") {
      return (
        <Select value={String(value)} onValueChange={(v) => set(field, v)}>
          <SelectTrigger className="h-8 w-full capitalize">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {(col.options ?? []).map((o) => (
              <SelectItem key={o} value={o} className="capitalize">
                {humanize(o)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      );
    }
    if (col.type === "bool") {
      return (
        <Select value={value ? "yes" : "no"} onValueChange={(v) => set(field, v === "yes")}>
          <SelectTrigger className="h-8 w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="yes">Yes</SelectItem>
            <SelectItem value="no">No</SelectItem>
          </SelectContent>
        </Select>
      );
    }
    return (
      <Input
        className="h-8"
        type={col.type === "number" ? "number" : "text"}
        step={col.type === "number" ? "any" : undefined}
        value={value == null ? "" : String(value)}
        placeholder={col.placeholder}
        onChange={(e) => set(field, e.target.value)}
      />
    );
  }

  const editRow = (key: string) => (
    <tr key={key} className="border-t border-border bg-muted/30">
      {columns.map((col) => (
        <td key={col.key ?? col.label} className={TD}>
          {editCell(col)}
        </td>
      ))}
      <td className={`${TD} whitespace-nowrap`}>
        <Button size="icon" variant="ghost" className="h-7 w-7" onClick={save} disabled={busy}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
          <span className="sr-only">Save</span>
        </Button>
        <Button
          size="icon"
          variant="ghost"
          className="h-7 w-7"
          onClick={() => setDraftExtensionsOpen(true)}
          disabled={busy || extensionFields.length === 0}
        >
          <ListPlus className="h-3.5 w-3.5" />
          <span className="sr-only">Extra fields…</span>
        </Button>
        <Button
          size="icon"
          variant="ghost"
          className="h-7 w-7"
          onClick={() => {
            setEditingId(null);
            setDraftExtensions({});
          }}
          disabled={busy}
        >
          <X className="h-4 w-4" />
          <span className="sr-only">Cancel</span>
        </Button>
      </td>
    </tr>
  );

  return (
    // Tooltip needs a TooltipProvider ancestor and the app doesn't mount one
    // globally; provide it here so every ProvenanceSourceBadge cell works.
    <TooltipProvider>
      <section aria-label={title} className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-foreground">{title}</h3>
          <Button
            size="sm"
            variant="outline"
            className="h-7 gap-1"
            onClick={() => {
              setDraft(emptyDraft);
              setDraftExtensions({});
              setEditingId(NEW);
            }}
            disabled={editingId === NEW}
          >
            <Plus className="h-3.5 w-3.5" />
            Add
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">{description}</p>
        {visualization}
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-muted/40">
                {columns.map((col) => (
                  <th key={col.key ?? col.label} className={TH}>
                    {col.label}
                  </th>
                ))}
                <th className={`${TH} w-16`}>&nbsp;</th>
              </tr>
            </thead>
            <tbody>
              {editingId === NEW && editRow(NEW)}
              {records.length === 0 && editingId !== NEW && (
                <tr className="border-t border-border">
                  <td
                    className="px-2 py-3 text-xs italic text-muted-foreground"
                    colSpan={columns.length + 1}
                  >
                    No {title.toLowerCase()} records yet.
                  </td>
                </tr>
              )}
              {records.map((r) => {
                if (editingId === r.id) return editRow(r.id);
                const ai = isAiRow?.(r) ?? false;
                return (
                  <tr
                    key={r.id}
                    className={cn(
                      "border-t border-border",
                      ai && "text-blue-700 dark:text-blue-400",
                    )}
                  >
                    {columns.map((col) => (
                      <td key={col.key ?? col.label} className={cn(TD, !ai && "text-foreground")}>
                        {col.render(r)}
                      </td>
                    ))}
                    <td className={`${TD} whitespace-nowrap`}>
                      {(extensionFields.length > 0 ||
                        Object.keys(r.extensions ?? {}).length > 0) && (
                        <Popover>
                          <PopoverTrigger asChild>
                            <Button size="icon" variant="ghost" className="h-7 w-7">
                              <Info className="h-3.5 w-3.5" />
                              <span className="sr-only">Extension values</span>
                            </Button>
                          </PopoverTrigger>
                          <ExtensionDetail
                            fields={extensionFields}
                            extensions={r.extensions ?? {}}
                          />
                        </Popover>
                      )}
                      {r.is_shared ? (
                        <span className="text-xs italic text-muted-foreground">
                          Reference data — managed by import
                        </span>
                      ) : (
                        <>
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-7 w-7"
                            onClick={() => {
                              setDraft(toDraft(r));
                              setDraftExtensions({});
                              setEditingId(r.id);
                            }}
                            disabled={busy}
                          >
                            <Pencil className="h-3.5 w-3.5" />
                            <span className="sr-only">Edit</span>
                          </Button>
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-7 w-7"
                            onClick={() => setProvenanceTarget(r)}
                            disabled={busy || provenanceFields.length === 0}
                          >
                            <BookOpen className="h-3.5 w-3.5" />
                            <span className="sr-only">Provenance…</span>
                          </Button>
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-7 w-7"
                            onClick={() => setExtensionsTarget(r)}
                            disabled={busy || extensionFields.length === 0}
                          >
                            <ListPlus className="h-3.5 w-3.5" />
                            <span className="sr-only">Extra fields…</span>
                          </Button>
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-7 w-7 text-destructive hover:text-destructive"
                            onClick={() => del(r.id)}
                            disabled={busy}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                            <span className="sr-only">Delete</span>
                          </Button>
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {provenanceTarget && (
          <ProvenanceDialog
            open
            fields={provenanceFields}
            value={provenanceTarget.provenance as Record<string, unknown>}
            onSave={saveProvenance}
            onClose={() => setProvenanceTarget(null)}
          />
        )}
        {extensionsTarget && (
          <ExtensionValuesDialog
            open
            fields={extensionFields}
            value={extensionsTarget.extensions ?? {}}
            busy={busy}
            onSave={saveExtensions}
            onClose={() => setExtensionsTarget(null)}
          />
        )}
        {draftExtensionsOpen && (
          <ExtensionValuesDialog
            open
            fields={extensionFields}
            value={{ ...(editingRecord?.extensions ?? {}), ...draftExtensions }}
            onSave={(changes) => {
              // Merge, not replace — `changes` is only the keys this dialog
              // session actually touched, same merge-patch shape `onSave`
              // always produces. Nothing goes to the network here; `save()`
              // above sends it all when the row itself is saved.
              setDraftExtensions((d) => ({ ...d, ...changes }));
              setDraftExtensionsOpen(false);
            }}
            onClose={() => setDraftExtensionsOpen(false)}
          />
        )}
      </section>
    </TooltipProvider>
  );
}

/** Explains the Source-cell colors. Render once above a set of record tables. */
export function ProvenanceLegend() {
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
      <span>Source color:</span>
      <Badge variant="outline">manual</Badge>
      <Badge variant="secondary">imported</Badge>
      <Badge variant="info">AI</Badge>
    </div>
  );
}
