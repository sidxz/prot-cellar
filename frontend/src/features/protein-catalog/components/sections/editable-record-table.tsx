"use client";

import type { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
import type { ProvenanceBody } from "@/shared/lib/api/model";
import { ProvenanceSourceType } from "@/shared/lib/api/model";
import { Check, Loader2, Pencil, Plus, Trash2, X } from "lucide-react";
import type { ComponentProps } from "react";
import { useState } from "react";
import { toast } from "sonner";

export const humanize = (s: string) => s.replace(/_/g, " ");
export const SOURCE_OPTIONS = Object.values(ProvenanceSourceType);

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

/** Coerce a text-input string to a nullable number / nullable trimmed string for a write body. */
export const numOrNull = (s: string): number | null => (s.trim() ? Number(s) : null);
export const strOrNull = (s: string): string | null => (s.trim() ? s.trim() : null);

const NEW = "__new__";

/** Draft provenance fields shared by every record type's draft.
 * A `type` (not `interface`) so record drafts satisfy the table's `Record<string, unknown>`. */
export type ProvDraft = {
  source_type: string;
  pmid: string;
  note: string;
};

export const EMPTY_PROV: ProvDraft = { source_type: "published", pmid: "", note: "" };

/** Minimal provenance shape as it comes back on any record response. */
interface ProvLike {
  source_type: string;
  citations: { pmid?: string | null }[];
  note?: string | null;
}

export function provToDraft(p: ProvLike): ProvDraft {
  return { source_type: p.source_type, pmid: p.citations[0]?.pmid ?? "", note: p.note ?? "" };
}

export function provToBody(d: ProvDraft): ProvenanceBody {
  return {
    source_type: d.source_type as ProvenanceSourceType,
    citations: d.pmid.trim() ? [{ pmid: d.pmid.trim() }] : [],
    note: d.note.trim() || null,
  };
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

/** The three shared provenance columns appended to every record's table. */
export function provColumns<R extends { provenance: ProvLike }>(): Column<R, ProvDraft>[] {
  return [
    {
      label: "Source",
      field: "source_type",
      type: "enum",
      options: SOURCE_OPTIONS,
      render: (r) => (
        <span className="text-xs uppercase text-muted-foreground">
          {humanize(r.provenance.source_type)}
        </span>
      ),
    },
    {
      label: "Reference",
      field: "pmid",
      type: "text",
      placeholder: "PMID",
      render: (r) => <PmidCell p={r.provenance} />,
    },
    {
      label: "Note",
      field: "note",
      type: "text",
      render: (r) => <span className="text-muted-foreground">{r.provenance.note ?? "—"}</span>,
    },
  ];
}

export interface Column<R, D> {
  label: string;
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

interface Props<R extends { id: string }, D extends Record<string, unknown>> {
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
}

function errMsg(e: unknown): string {
  const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  return "Could not save. You may need an admin role.";
}

export function EditableRecordTable<R extends { id: string }, D extends Record<string, unknown>>({
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
}: Props<R, D>) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<D>(emptyDraft);
  const set = (field: string, value: unknown) => setDraft((d) => ({ ...d, [field]: value }));

  async function save() {
    try {
      const body = toBody(draft);
      if (editingId === NEW) {
        await onCreate(body);
        toast.success(`${title} record added`);
      } else if (editingId) {
        await onUpdate(editingId, body);
        toast.success(`${title} record updated`);
      }
      setEditingId(null);
    } catch (e) {
      toast.error(errMsg(e));
    }
  }

  async function del(id: string) {
    if (!window.confirm(`Delete this ${title.toLowerCase()} record?`)) return;
    try {
      await onDelete(id);
      toast.success(`${title} record deleted`);
    } catch (e) {
      toast.error(errMsg(e));
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
        <td key={col.label} className={TD}>
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
          onClick={() => setEditingId(null)}
          disabled={busy}
        >
          <X className="h-4 w-4" />
          <span className="sr-only">Cancel</span>
        </Button>
      </td>
    </tr>
  );

  return (
    <section aria-label={title} className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        <Button
          size="sm"
          variant="outline"
          className="h-7 gap-1"
          onClick={() => {
            setDraft(emptyDraft);
            setEditingId(NEW);
          }}
          disabled={editingId === NEW}
        >
          <Plus className="h-3.5 w-3.5" />
          Add
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">{description}</p>
      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-muted/40">
              {columns.map((col) => (
                <th key={col.label} className={TH}>
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
            {records.map((r) =>
              editingId === r.id ? (
                editRow(r.id)
              ) : (
                <tr key={r.id} className="border-t border-border">
                  {columns.map((col) => (
                    <td key={col.label} className={`${TD} text-foreground`}>
                      {col.render(r)}
                    </td>
                  ))}
                  <td className={`${TD} whitespace-nowrap`}>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-7 w-7"
                      onClick={() => {
                        setDraft(toDraft(r));
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
                      className="h-7 w-7 text-destructive hover:text-destructive"
                      onClick={() => del(r.id)}
                      disabled={busy}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      <span className="sr-only">Delete</span>
                    </Button>
                  </td>
                </tr>
              ),
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
