"use client";

import { RELATIONSHIP_LABELS, cardinalityHint, componentCountValid } from "@/features/target";
import type { TargetComponentInput } from "@/features/target";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
import type { ComponentRelationship, TargetType } from "@/shared/lib/api/model";
import { resolveProteinApiV1ProteinsResolveIdentifierGet } from "@/shared/lib/api/proteins/proteins";
import { showError } from "@/shared/lib/toast";
import { cn } from "@/shared/lib/utils";
import { useEffect, useRef, useState } from "react";

interface TargetComponentsEditorProps {
  value: TargetComponentInput[];
  onChange: (rows: TargetComponentInput[]) => void;
  targetType: TargetType;
}

/**
 * Controlled editor for a target's protein component rows.
 *
 * Row mutations are always surfaced via `onChange(newRows)` — the parent owns
 * the source of truth.  We only keep transient per-row "resolving" state here
 * (a `Set<number>` of stable client-key ids that are currently loading).
 *
 * Stable React keys are carried IN each row as `_key` (a client-only field,
 * never sent to the API).  The `nextKey` counter never resets so removed-row
 * keys are never reused, preventing React key churn on remove/reorder.
 */
export function TargetComponentsEditor({
  value,
  onChange,
  targetType,
}: TargetComponentsEditorProps) {
  // Monotonically increasing counter for assigning _key values.
  const nextKey = useRef(1);

  // Normalize any rows that arrived without a _key (e.g. pre-populated edit
  // rows from the server).  Guarded so it only fires when at least one row is
  // missing _key — prevents an infinite onChange loop.
  useEffect(() => {
    if (value.some((r) => r._key == null)) {
      onChange(value.map((r) => (r._key == null ? { ...r, _key: nextKey.current++ } : r)));
    }
  }, [value, onChange]);

  // Transient loading state: which stable-key ids are currently resolving.
  const [resolvingKeys, setResolvingKeys] = useState<Set<number>>(new Set());

  // ── helpers ──────────────────────────────────────────────────────────────

  function updateRow(idx: number, patch: Partial<TargetComponentInput>) {
    // Preserve the existing _key when patching a row.
    const newRows = value.map((row, i) => (i === idx ? { ...row, ...patch } : row));
    onChange(newRows);
  }

  async function resolveRow(idx: number) {
    const accession = value[idx]?.accession?.trim();
    if (!accession) return;

    const stableKey = value[idx]._key;
    if (stableKey == null) return;
    setResolvingKeys((prev) => new Set(prev).add(stableKey));

    try {
      const protein = await resolveProteinApiV1ProteinsResolveIdentifierGet(accession);
      // Use entry_name (e.g. "P53_HUMAN") or fall back to primary_accession.
      // Both are plain top-level fields on ProteinResponse — no runtime cast needed.
      const label = protein.entry_name ?? protein.primary_accession;

      updateRow(idx, { protein_id: protein.id, label });
    } catch (err) {
      showError(err);
      // Clear protein_id so validation catches the unresolved state.
      updateRow(idx, { protein_id: "", label: undefined });
    } finally {
      setResolvingKeys((prev) => {
        const next = new Set(prev);
        next.delete(stableKey);
        return next;
      });
    }
  }

  function addRow() {
    onChange([
      ...value,
      { protein_id: "", relationship: "single_protein", accession: "", _key: nextKey.current++ },
    ]);
  }

  function removeRow(idx: number) {
    onChange(value.filter((_, i) => i !== idx));
  }

  // ── derived ──────────────────────────────────────────────────────────────

  const resolvedCount = value.filter((r) => r.protein_id !== "").length;
  const hint = cardinalityHint(targetType);
  const isValid = componentCountValid(targetType, resolvedCount);

  // ── render ───────────────────────────────────────────────────────────────

  return (
    <div className="space-y-4">
      {/* Cardinality hint */}
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <span>Cardinality:</span>
        <span className="font-medium text-foreground">{hint}</span>
        <span className="text-muted-foreground">
          ({resolvedCount} resolved
          {!isValid && (
            <span className={cn("ml-1 font-medium text-destructive")}>— requirement not met</span>
          )}
          )
        </span>
      </div>

      {/* Rows */}
      <div className="space-y-3">
        {value.map((row, idx) => {
          // _key is guaranteed by the normalization effect above; fall back to
          // index only as a last resort (should never occur in practice).
          const stableKey = row._key ?? idx;
          const isResolving = resolvingKeys.has(stableKey);
          const isResolved = row.protein_id !== "";

          return (
            <div
              key={stableKey}
              className="flex items-end gap-2 rounded-md border border-border bg-card p-3"
            >
              {/* Accession input */}
              <div className="flex-1 space-y-1">
                <Label htmlFor={`accession-${stableKey}`} className="text-xs">
                  UniProt Accession / ID
                </Label>
                <div className="flex items-center gap-2">
                  <Input
                    id={`accession-${stableKey}`}
                    value={row.accession ?? ""}
                    placeholder="e.g. P00533"
                    className={cn(
                      "font-mono text-sm",
                      isResolved && "border-primary focus-visible:ring-primary/30",
                    )}
                    onChange={(e) =>
                      updateRow(idx, {
                        accession: e.target.value,
                        // Clear resolved state when user edits the field.
                        protein_id: "",
                        label: undefined,
                      })
                    }
                    onBlur={() => {
                      if (row.accession?.trim() && !isResolved) {
                        void resolveRow(idx);
                      }
                    }}
                    aria-label="UniProt accession or identifier"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={isResolving || !row.accession?.trim()}
                    onClick={() => void resolveRow(idx)}
                    className="shrink-0"
                    aria-label="Resolve protein identifier"
                  >
                    {isResolving ? "Resolving…" : "Resolve"}
                  </Button>
                </div>

                {/* Resolved badge */}
                {isResolved && row.label && (
                  <div className="flex items-center gap-1.5 pt-1">
                    <span className="text-primary" aria-label="Resolved">
                      ✓
                    </span>
                    <Badge
                      variant="secondary"
                      className="border-primary/20 bg-primary/10 text-primary text-xs"
                    >
                      {row.label}
                    </Badge>
                  </div>
                )}
              </div>

              {/* Relationship select */}
              <div className="w-48 space-y-1">
                <Label htmlFor={`relationship-${stableKey}`} className="text-xs">
                  Relationship
                </Label>
                <Select
                  value={row.relationship}
                  onValueChange={(val) =>
                    updateRow(idx, { relationship: val as ComponentRelationship })
                  }
                >
                  <SelectTrigger
                    id={`relationship-${stableKey}`}
                    className="text-sm"
                    aria-label="Component relationship"
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(Object.entries(RELATIONSHIP_LABELS) as [ComponentRelationship, string][]).map(
                      ([key, label]) => (
                        <SelectItem key={key} value={key}>
                          {label}
                        </SelectItem>
                      ),
                    )}
                  </SelectContent>
                </Select>
              </div>

              {/* Remove button */}
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => removeRow(idx)}
                className="mb-0.5 shrink-0 text-muted-foreground hover:text-destructive"
                aria-label={`Remove component ${idx + 1}`}
              >
                ×
              </Button>
            </div>
          );
        })}
      </div>

      {/* Add component */}
      <Button type="button" variant="outline" size="sm" onClick={addRow}>
        + Add component
      </Button>
    </div>
  );
}
