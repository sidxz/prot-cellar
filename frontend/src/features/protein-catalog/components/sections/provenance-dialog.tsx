"use client";

import { Trash2 } from "lucide-react";
import { useId, useState } from "react";

import { Button } from "@/shared/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
import { Textarea } from "@/shared/components/ui/textarea";

import type { FieldDescriptor } from "../../hooks/use-target-biology-schema";
import { humanize, strOrNull } from "./editable-record-table";

/** A citation row carries a synthetic, session-local `_key` for stable React
 * keys (the data itself has no id) — never sent to the server; `handleSave`
 * rebuilds each row from `item_fields` only. */
type Row = Record<string, unknown> & { _key: number };
type Draft = Record<string, unknown>;

let rowCounter = 0;
const nextKey = () => rowCounter++;

function toRows(value: unknown): Row[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => ({ ...(item as Record<string, unknown>), _key: nextKey() }));
}

function initDraft(fields: FieldDescriptor[], value: Record<string, unknown>): Draft {
  const draft: Draft = {};
  for (const f of fields) {
    const raw = value[f.name];
    draft[f.name] = f.type === "list" ? toRows(raw) : (raw ?? "");
  }
  return draft;
}

/** `null`-if-blank, trimmed — mirrors `strOrNull` but tolerates a `null` input
 * (an untouched deep-copied sub-field), not just a string. */
function subFieldOrNull(raw: unknown): string | null {
  return raw == null ? null : strOrNull(String(raw));
}

interface ProvenanceDialogProps {
  open: boolean;
  fields: FieldDescriptor[];
  value: Record<string, unknown>;
  onSave: (body: Record<string, unknown>) => void;
  onClose: () => void;
}

export function ProvenanceDialog({ open, fields, value, onSave, onClose }: ProvenanceDialogProps) {
  const [draft, setDraft] = useState<Draft>(() => initDraft(fields, value));
  const idPrefix = useId();

  const set = (name: string, v: unknown) => setDraft((d) => ({ ...d, [name]: v }));
  const rowsOf = (field: FieldDescriptor) => (draft[field.name] as Row[] | undefined) ?? [];

  function addRow(field: FieldDescriptor) {
    const blank: Row = { _key: nextKey() };
    for (const f of field.item_fields ?? []) blank[f.name] = "";
    set(field.name, [...rowsOf(field), blank]);
  }

  function removeRow(field: FieldDescriptor, key: number) {
    set(
      field.name,
      rowsOf(field).filter((r) => r._key !== key),
    );
  }

  function setRowField(field: FieldDescriptor, key: number, subName: string, v: unknown) {
    set(
      field.name,
      rowsOf(field).map((r) => (r._key === key ? { ...r, [subName]: v } : r)),
    );
  }

  function handleSave() {
    const body: Record<string, unknown> = {};
    for (const f of fields) {
      if (f.type === "list") {
        const itemFields = f.item_fields ?? [];
        body[f.name] = rowsOf(f).map((row) =>
          Object.fromEntries(itemFields.map((sf) => [sf.name, subFieldOrNull(row[sf.name])])),
        );
      } else if (f.type === "string" || f.type === "text") {
        body[f.name] = subFieldOrNull(draft[f.name]);
      } else {
        body[f.name] = draft[f.name];
      }
    }
    onSave(body);
  }

  function fieldControl(field: FieldDescriptor, id: string) {
    const val = draft[field.name];
    switch (field.type) {
      case "enum":
        return (
          <Select value={String(val ?? "")} onValueChange={(v) => set(field.name, v)}>
            <SelectTrigger id={id} className="w-full capitalize">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(field.options ?? []).map((o) => (
                <SelectItem key={o} value={o} className="capitalize">
                  {humanize(o)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        );
      case "boolean":
        return (
          <Select value={val ? "yes" : "no"} onValueChange={(v) => set(field.name, v === "yes")}>
            <SelectTrigger id={id} className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="yes">Yes</SelectItem>
              <SelectItem value="no">No</SelectItem>
            </SelectContent>
          </Select>
        );
      case "date":
        return (
          <Input
            id={id}
            type="date"
            value={val ? String(val) : ""}
            onChange={(e) => set(field.name, e.target.value)}
          />
        );
      case "text":
        return (
          <Textarea
            id={id}
            value={val == null ? "" : String(val)}
            onChange={(e) => set(field.name, e.target.value)}
          />
        );
      case "number":
      case "integer":
        return (
          <Input
            id={id}
            type="number"
            step={field.type === "integer" ? "1" : "any"}
            min={field.min}
            max={field.max}
            value={val == null ? "" : String(val)}
            onChange={(e) => set(field.name, e.target.value === "" ? "" : Number(e.target.value))}
          />
        );
      default:
        // string, reference, and anything undocumented: a plain text input.
        return (
          <Input
            id={id}
            value={val == null ? "" : String(val)}
            onChange={(e) => set(field.name, e.target.value)}
          />
        );
    }
  }

  function listField(field: FieldDescriptor) {
    const itemFields = field.item_fields ?? [];
    // "Citations" → "Add citation". The provenance descriptor has exactly one
    // list field today; this keeps the button's label off a hard-coded string.
    const addLabel = `Add ${field.label.toLowerCase().replace(/s\b/, "")}`;
    return (
      <div key={field.name} className="grid gap-2">
        <Label>{field.label}</Label>
        <div className="flex flex-col gap-2">
          {rowsOf(field).map((row) => (
            <div
              key={row._key}
              className="flex items-start gap-2 rounded-md border border-border p-2"
            >
              <div className="grid flex-1 grid-cols-2 gap-2">
                {itemFields.map((sf) => (
                  <Input
                    key={sf.name}
                    placeholder={sf.label}
                    aria-label={sf.label}
                    value={row[sf.name] == null ? "" : String(row[sf.name])}
                    onChange={(e) => setRowField(field, row._key, sf.name, e.target.value)}
                  />
                ))}
              </div>
              <Button
                type="button"
                size="icon"
                variant="ghost"
                className="h-9 w-9 shrink-0 text-destructive hover:text-destructive"
                onClick={() => removeRow(field, row._key)}
              >
                <Trash2 className="h-3.5 w-3.5" />
                <span className="sr-only">Remove {field.label.toLowerCase()}</span>
              </Button>
            </div>
          ))}
        </div>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="w-fit"
          onClick={() => addRow(field)}
        >
          {addLabel}
        </Button>
      </div>
    );
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Provenance</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 py-2">
          {fields.map((field) => {
            if (field.type === "list") return listField(field);
            const id = `${idPrefix}-${field.name}`;
            return (
              <div key={field.name} className="grid gap-2">
                <Label htmlFor={id}>{field.label}</Label>
                {fieldControl(field, id)}
              </div>
            );
          })}
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="button" onClick={handleSave}>
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
