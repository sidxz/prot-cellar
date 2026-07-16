"use client";

import { Badge } from "@/shared/components/ui/badge";

import { useBreadcrumbOverride } from "@/shared/lib/stores/breadcrumb-store";
import { useImportRun } from "../hooks/use-imports";
import { IMPORT_TYPE_LABELS, STATUS_VARIANTS } from "../types";

function asNumber(v: unknown): number {
  return typeof v === "number" ? v : Number(v ?? 0) || 0;
}

export function ImportDetailPage({ importRunId }: { importRunId: string }) {
  const { data, isLoading, isError } = useImportRun(importRunId);
  useBreadcrumbOverride(importRunId, data?.target_key ?? "");

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (isError || !data) {
    return (
      <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
        Failed to load this import run.
      </div>
    );
  }

  const progress = (data.progress as Record<string, unknown>) ?? {};
  const processed = asNumber(progress.processed);
  const total = asNumber(progress.total);
  const isActive = data.status === "queued" || data.status === "running";
  const summaryEntries = Object.entries((data.summary as Record<string, unknown>) ?? {});

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight">
            {IMPORT_TYPE_LABELS[data.import_type]}
          </h1>
          <p className="text-sm text-muted-foreground">{data.target_key}</p>
        </div>
        <Badge variant={STATUS_VARIANTS[data.status]}>{data.status}</Badge>
      </div>

      {/* Phase + progress */}
      <div className="flex flex-col gap-2">
        {data.phase && (
          <p className="text-sm">
            Phase: <span className="font-medium">{data.phase}</span>
          </p>
        )}
        {total > 0 ? (
          <div className="flex flex-col gap-1">
            <div className="h-2 w-full overflow-hidden rounded bg-muted">
              <div
                className="h-full bg-primary transition-all"
                style={{ width: `${Math.min(100, Math.round((processed / total) * 100))}%` }}
              />
            </div>
            <p className="text-xs text-muted-foreground">
              {processed} / {total}
            </p>
          </div>
        ) : (
          isActive && <p className="text-sm text-muted-foreground animate-pulse">Working…</p>
        )}
      </div>

      {/* Error */}
      {data.error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {data.error}
        </div>
      )}

      {/* Summary */}
      {summaryEntries.length > 0 && (
        <div className="flex flex-col gap-2">
          <h2 className="text-sm font-semibold">Summary</h2>
          <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm">
            {summaryEntries.map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-muted-foreground">{k}</dt>
                <dd className="font-mono">
                  {typeof v === "object" ? JSON.stringify(v) : String(v)}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </div>
  );
}
