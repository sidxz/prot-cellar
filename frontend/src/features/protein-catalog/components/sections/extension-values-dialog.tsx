"use client";

import { useId, useState } from "react";

import { Button } from "@/shared/components/ui/button";
import { Checkbox } from "@/shared/components/ui/checkbox";
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
import { humanize } from "./editable-record-table";

type Draft = Record<string, unknown>;

// Radix disallows `value=""` on a SelectItem, so an enum field needs a real
// sentinel item to represent "no value" — otherwise there is no click path
// back to "" once an option has been picked, and the clear-by-null idiom
// (unlike every other field type, which clears through its native empty
// state) would be unreachable for enum fields.
const ENUM_UNSET = "__unset__";

/** Seeds one draft value per declared field. Booleans always start from a
 * real `true`/`false` — a checkbox has no third "unset" state to render.
 * Everything else starts from its stored value or `""`, the same "no value"
 * state its control clears back to, so an untouched field reliably diffs as
 * unchanged against a freshly-seeded draft. */
function initDraft(fields: FieldDescriptor[], value: Record<string, unknown>): Draft {
  const draft: Draft = {};
  for (const f of fields) {
    const raw = value[f.name];
    draft[f.name] = f.type === "boolean" ? Boolean(raw) : (raw ?? "");
  }
  return draft;
}

/** One entry per field whose draft differs from what was loaded: the new
 * value, or `null` to clear a field that had one. Fields the curator never
 * touched are left out entirely — `extensions` on the wire is a merge patch,
 * not a replacement (see the write-contract validator), so only real edits
 * belong here. */
function buildChanges(
  fields: FieldDescriptor[],
  draft: Draft,
  original: Draft,
): Record<string, unknown> {
  const changes: Record<string, unknown> = {};
  for (const f of fields) {
    const next = draft[f.name];
    if (next === original[f.name]) continue;
    changes[f.name] = next === "" ? null : next;
  }
  return changes;
}

interface ExtensionValuesDialogProps {
  open: boolean;
  fields: FieldDescriptor[];
  value: Record<string, unknown>;
  /** Disables Save/Cancel while the parent's update is in flight — the same
   * `busy` the table already threads through every other row action. */
  busy?: boolean;
  onSave: (changes: Record<string, unknown>) => void;
  onClose: () => void;
}

/** Edits one record's declared extension-field values. Mirrors
 * `ProvenanceDialog`'s shape (explicit Save/Cancel, an untouched save is a
 * no-op) with a different field source and a merge-patch save: only the keys
 * that actually changed go out, clearing one sends an explicit `null`. */
export function ExtensionValuesDialog({
  open,
  fields,
  value,
  busy = false,
  onSave,
  onClose,
}: ExtensionValuesDialogProps) {
  const [draft, setDraft] = useState<Draft>(() => initDraft(fields, value));
  const idPrefix = useId();

  const set = (name: string, v: unknown) => setDraft((d) => ({ ...d, [name]: v }));

  function handleSave() {
    const changes = buildChanges(fields, draft, initDraft(fields, value));
    // An untouched save is a no-op — mirrors ProvenanceDialog, so a misclick
    // can't write anything.
    if (Object.keys(changes).length === 0) {
      onClose();
      return;
    }
    onSave(changes);
  }

  function fieldControl(field: FieldDescriptor, id: string) {
    const val = draft[field.name];
    switch (field.type) {
      case "enum":
        return (
          <Select
            value={val ? String(val) : ENUM_UNSET}
            onValueChange={(v) => set(field.name, v === ENUM_UNSET ? "" : v)}
          >
            <SelectTrigger id={id} className="w-full capitalize">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ENUM_UNSET} className="text-muted-foreground">
                No value
              </SelectItem>
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
          <Checkbox
            id={id}
            checked={Boolean(val)}
            onCheckedChange={(checked) => set(field.name, checked === true)}
          />
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
            value={val == null ? "" : String(val)}
            onChange={(e) => set(field.name, e.target.value === "" ? "" : Number(e.target.value))}
          />
        );
      default:
        // "string" and anything undocumented: a plain text input.
        return (
          <Input
            id={id}
            value={val == null ? "" : String(val)}
            onChange={(e) => set(field.name, e.target.value)}
          />
        );
    }
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
          <DialogTitle>Extra fields</DialogTitle>
        </DialogHeader>
        <div className="grid gap-4 py-2">
          {fields.map((field) => {
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
          <Button type="button" variant="outline" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button type="button" onClick={handleSave} disabled={busy}>
            {busy ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
