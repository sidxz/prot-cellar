"use client";

import { useRouter } from "next/navigation";

import { RECORD_KINDS, humanize } from "@/features/extension-fields/types";
import { useTargetBiologySchema } from "@/features/protein-catalog/hooks/use-target-biology-schema";
import { Button } from "@/shared/components/ui/button";
import { ImportType } from "@/shared/lib/api/model";

import { useStartImport } from "../hooks/use-imports";
import { type ImportRun, loadTargetBiologyApplyParams } from "../types";

interface KindSummary {
  rows: number;
  records: number;
  merged_identical: number;
  create: number;
  update: number;
  failed: number;
}

interface ProblemEntry {
  sheet: string;
  row: number | null;
  reason: string;
}

interface WarningEntry {
  sheet: string;
  count: number;
  reason: string;
}

/**
 * The shape `TargetBiologyAdapter.run` returns (backend `import_adapters.py`).
 * `run.summary` comes back untyped (`{[key: string]: unknown}` — orval can't
 * know a worker job's own payload shape), so this is narrowed once here
 * rather than cast at every access, mirroring `use-target-biology-schema.ts`.
 */
interface TargetBiologySummary {
  kinds?: Record<string, KindSummary>;
  unmatched?: { count: number; examples: string[] };
  problems?: ProblemEntry[];
  problems_truncated?: number;
  already_present?: Record<string, number>;
  ignored_columns?: Record<string, string[]>;
  warnings?: WarningEntry[];
}

/**
 * `target_key` for this import type is `"{organism_id}:{upload_ref}:{dry|
 * run}"` (`application/imports/params.py:target_key`) — the only place
 * "was this run a preview or an apply" is recorded, since neither is a
 * separate `ImportStatus`. Reused by `import-detail.tsx` too, so it lives
 * here once rather than being re-derived per caller.
 */
export function isTargetBiologyPreviewRun(targetKey: string): boolean {
  return targetKey.split(":").pop() === "dry";
}

const IMPORTS_LIST_PATH = "/admin/imports";

export function TargetBiologyPreview({ run }: { run: ImportRun }) {
  const router = useRouter();
  const apply = useStartImport();
  const { data: schemaData } = useTargetBiologySchema();

  if (run.status !== "succeeded") return null;

  const summary = (run.summary ?? {}) as TargetBiologySummary;
  const kinds = summary.kinds ?? {};
  const presentKinds = RECORD_KINDS.filter((k) => k in kinds);
  const unmatched = summary.unmatched ?? { count: 0, examples: [] };
  const problems = summary.problems ?? [];
  const problemsTruncated = summary.problems_truncated ?? 0;
  const ignoredColumns = Object.entries(summary.ignored_columns ?? {});
  const warnings = summary.warnings ?? [];

  const preview = isTargetBiologyPreviewRun(run.target_key);
  const stored = loadTargetBiologyApplyParams(run.id);
  // "Already present" is only a meaningful warning in add mode (running it
  // twice doubles the tenant's own data); update mode matches instead. When
  // this browser has lost track of which mode the preview used, say nothing
  // rather than assert a mode we can't confirm — see loadTargetBiologyApplyParams.
  const alreadyPresent =
    stored?.update_existing === false
      ? Object.entries(summary.already_present ?? {}).filter(([, n]) => n > 0)
      : [];

  function kindLabel(kind: string): string {
    return schemaData?.kinds[kind]?.label ?? humanize(kind);
  }

  function goToImports() {
    router.push(IMPORTS_LIST_PATH);
  }

  async function handleApply() {
    if (!stored || !run.upload_ref) return;
    try {
      const applied = await apply.mutateAsync({
        data: {
          import_type: ImportType.target_biology,
          params: {
            upload_ref: run.upload_ref,
            organism_id: stored.organism_id,
            match_by: stored.match_by,
            update_existing: stored.update_existing,
            dry_run: false,
          },
        },
      });
      router.push(`/admin/imports/${applied.id}`);
    } catch {
      // global mutation toast surfaces the error
    }
  }

  return (
    <div className="flex flex-col gap-6">
      {presentKinds.length === 0 ? (
        <p className="text-sm text-muted-foreground">No recognised sheets in this workbook.</p>
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left text-xs text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">Kind</th>
                <th className="px-3 py-2 font-medium">Rows</th>
                <th className="px-3 py-2 font-medium">Records</th>
                <th className="px-3 py-2 font-medium">Merged</th>
                <th className="px-3 py-2 font-medium">Create</th>
                <th className="px-3 py-2 font-medium">Update</th>
                <th className="px-3 py-2 font-medium">Failed</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {presentKinds.map((kind) => {
                const c = kinds[kind];
                return (
                  <tr key={kind}>
                    <td className="px-3 py-2 font-medium">{kindLabel(kind)}</td>
                    <td className="px-3 py-2">{c.rows}</td>
                    <td className="px-3 py-2">{c.records}</td>
                    <td className="px-3 py-2">{c.merged_identical}</td>
                    <td className="px-3 py-2">{c.create}</td>
                    <td className="px-3 py-2">{c.update}</td>
                    <td className="px-3 py-2">{c.failed}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {unmatched.count > 0 && (
        <div className="flex flex-col gap-1">
          <h2 className="text-sm font-semibold">Unmatched genes ({unmatched.count})</h2>
          <p className="max-h-32 overflow-y-auto text-sm text-muted-foreground">
            {unmatched.examples.join(", ")}
          </p>
        </div>
      )}

      {problems.length > 0 && (
        <div className="flex flex-col gap-1">
          <h2 className="text-sm font-semibold">Problems ({problems.length})</h2>
          <ul className="max-h-48 overflow-y-auto rounded-md border text-sm">
            {problems.map((p, i) => (
              <li
                // biome-ignore lint/suspicious/noArrayIndexKey: problems carry no stable id
                key={i}
                className="border-b px-3 py-1.5 last:border-b-0"
              >
                <span className="font-medium">{kindLabel(p.sheet)}</span>
                {p.row !== null && <span className="text-muted-foreground"> row {p.row}</span>}
                {" — "}
                {p.reason}
              </li>
            ))}
          </ul>
          {problemsTruncated > 0 && (
            <p className="text-xs text-muted-foreground">{problemsTruncated} more not shown.</p>
          )}
        </div>
      )}

      {ignoredColumns.length > 0 && (
        <div className="flex flex-col gap-1">
          <h2 className="text-sm font-semibold">Ignored columns</h2>
          <ul className="text-sm text-muted-foreground">
            {ignoredColumns.map(([sheet, cols]) => (
              <li key={sheet}>
                <span className="font-medium text-foreground">{kindLabel(sheet)}</span>:{" "}
                {cols.join(", ")}
              </li>
            ))}
          </ul>
        </div>
      )}

      {alreadyPresent.length > 0 && (
        <div className="rounded-md border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning">
          <p className="font-medium">Already in this workspace — add mode will duplicate these</p>
          <ul>
            {alreadyPresent.map(([kind, n]) => (
              <li key={kind}>
                {kindLabel(kind)}: {n}
              </li>
            ))}
          </ul>
        </div>
      )}

      {warnings.map((w, i) => (
        <div
          // biome-ignore lint/suspicious/noArrayIndexKey: warnings carry no stable id
          key={i}
          className="rounded-md border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning"
        >
          <p className="font-medium">
            {kindLabel(w.sheet)}: {w.count} row{w.count === 1 ? "" : "s"}
          </p>
          <p>{w.reason}</p>
        </div>
      ))}

      {preview &&
        (stored ? (
          <div className="flex items-center justify-end gap-2 border-t pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={goToImports}
              disabled={apply.isPending}
            >
              Discard
            </Button>
            <Button type="button" onClick={handleApply} disabled={apply.isPending}>
              {apply.isPending ? "Applying…" : "Apply"}
            </Button>
          </div>
        ) : (
          <div className="flex items-center justify-between gap-4 border-t pt-4">
            <p className="text-xs text-muted-foreground">
              This browser no longer has the settings this preview used.
            </p>
            <Button type="button" variant="outline" onClick={goToImports}>
              Back to imports
            </Button>
          </div>
        ))}
    </div>
  );
}
