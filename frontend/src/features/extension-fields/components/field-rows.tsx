"use client";

import { ChevronDown, ChevronUp, Trash2 } from "lucide-react";
import { Fragment } from "react";

import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
import { ExtensionFieldType } from "@/shared/lib/api/model";
import { cn } from "@/shared/lib/utils";

import type { DraftFieldRow } from "../types";

const FIELD_TYPES = Object.values(ExtensionFieldType);

const TH =
  "px-2 py-1.5 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground";
const TD = "px-2 py-1.5 align-middle";

interface FieldRowsProps {
  rows: DraftFieldRow[];
  onChange: (rows: DraftFieldRow[]) => void;
  /** Called once the delete is confirmed, for a row that already exists on
   *  the server. A not-yet-saved row is removed locally with no confirm —
   *  there is nothing stored yet for it to orphan. */
  onDeleteSaved: (row: DraftFieldRow) => void;
}

/** The inline, always-editable list of one kind's field declarations: name,
 *  label, type, options (enum only), show-in-table, reorder, delete. Holds no
 *  state of its own — every edit flows back out through `onChange` so the
 *  screen-level Save/Cancel in `ExtensionFieldEditor` governs when any of it
 *  actually persists. */
export function FieldRows({ rows, onChange, onDeleteSaved }: FieldRowsProps) {
  function update(index: number, patch: Partial<DraftFieldRow>) {
    onChange(rows.map((r, i) => (i === index ? { ...r, ...patch } : r)));
  }

  function move(index: number, delta: -1 | 1) {
    const target = index + delta;
    if (target < 0 || target >= rows.length) return;
    const next = [...rows];
    [next[index], next[target]] = [next[target], next[index]];
    onChange(next);
  }

  function remove(index: number) {
    const row = rows[index];
    if (row.id) {
      const ok = window.confirm(
        `Delete "${row.label || row.name}"? Values already stored under this field are kept and will show as unmapped.`,
      );
      if (!ok) return;
      onDeleteSaved(row);
      return;
    }
    onChange(rows.filter((_, i) => i !== index));
  }

  if (rows.length === 0) {
    return <p className="text-xs italic text-muted-foreground">No fields declared yet.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-muted/40">
            <th className={TH}>Name</th>
            <th className={TH}>Label</th>
            <th className={TH}>Type</th>
            <th className={TH}>Show in table</th>
            <th className={`${TH} w-28`}>&nbsp;</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => {
            const isSaved = !!row.id;
            const isEnum = row.field_type === ExtensionFieldType.enum;
            return (
              <Fragment key={row.key}>
                <tr className="border-t border-border">
                  <td className={TD}>
                    <Input
                      aria-label="Name"
                      placeholder="snake_case"
                      className="h-9 w-36 font-mono text-xs read-only:bg-muted/50 read-only:text-muted-foreground"
                      readOnly={isSaved}
                      value={row.name}
                      onChange={(e) => update(index, { name: e.target.value })}
                    />
                  </td>
                  <td className={TD}>
                    <Input
                      aria-label="Label"
                      placeholder="Display label"
                      className="h-9 min-w-32"
                      value={row.label}
                      onChange={(e) => update(index, { label: e.target.value })}
                    />
                  </td>
                  <td className={TD}>
                    <Select
                      value={row.field_type}
                      onValueChange={(v) => update(index, { field_type: v as ExtensionFieldType })}
                    >
                      <SelectTrigger aria-label="Field type" className="h-9 w-32 capitalize">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {FIELD_TYPES.map((t) => (
                          <SelectItem key={t} value={t} className="capitalize">
                            {t}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </td>
                  <td className={`${TD} text-center`}>
                    <input
                      type="checkbox"
                      aria-label="Show in table"
                      className="size-4"
                      checked={row.show_in_table}
                      onChange={(e) => update(index, { show_in_table: e.target.checked })}
                    />
                  </td>
                  <td className={`${TD} whitespace-nowrap`}>
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      className="h-7 w-7"
                      onClick={() => move(index, -1)}
                      disabled={index === 0}
                    >
                      <ChevronUp className="h-3.5 w-3.5" />
                      <span className="sr-only">Move up</span>
                    </Button>
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      className="h-7 w-7"
                      onClick={() => move(index, 1)}
                      disabled={index === rows.length - 1}
                    >
                      <ChevronDown className="h-3.5 w-3.5" />
                      <span className="sr-only">Move down</span>
                    </Button>
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      className="h-7 w-7 text-destructive hover:text-destructive"
                      onClick={() => remove(index)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      <span className="sr-only">Delete…</span>
                    </Button>
                  </td>
                </tr>
                {/* Always rendered so revealing/hiding it never resizes the
                    table — only `visibility` toggles, which keeps the row's
                    height constant (and drops it from the tab order/AT tree
                    for free when hidden). */}
                <tr className="border-t border-border/50">
                  <td colSpan={5} className="px-2 pb-2 pt-0">
                    <Input
                      aria-label="Options"
                      placeholder="Options, comma-separated"
                      className={cn("h-8", isEnum ? "visible" : "invisible")}
                      value={row.optionsText}
                      onChange={(e) => update(index, { optionsText: e.target.value })}
                    />
                  </td>
                </tr>
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
