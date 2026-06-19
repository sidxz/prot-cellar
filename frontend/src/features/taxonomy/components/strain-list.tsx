"use client";

import { DataGrid } from "@/shared/components/data-grid/data-grid";
import { Button } from "@/shared/components/ui/button";
import { FlaskConical } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useStrains } from "../hooks/use-strains";
import { strainColumnDefs } from "./strain-columns";
import { StrainFormDialog } from "./strain-form-dialog";

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------
function StrainsEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-20 text-center text-muted-foreground">
      <FlaskConical className="h-10 w-10 opacity-30" />
      <p className="text-sm font-medium">No strains found</p>
      <p className="text-xs">Create your first strain using the "New Strain" button above.</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// StrainListPage
// ---------------------------------------------------------------------------
export function StrainListPage() {
  const router = useRouter();

  // ── Cursor pagination ────────────────────────────────────────────────────
  const [cursorStack, setCursorStack] = useState<(string | undefined)[]>([undefined]);
  const currentCursor = cursorStack[cursorStack.length - 1];

  // ── Data ─────────────────────────────────────────────────────────────────
  const { data, isLoading, isError } = useStrains(currentCursor);

  const strains = useMemo(() => {
    if (!data?.items) return undefined;
    // biome-ignore lint/suspicious/noExplicitAny: narrowing cast at feature boundary
    return data.items as any[];
  }, [data]);

  // ── New Strain dialog ────────────────────────────────────────────────────
  const [newStrainOpen, setNewStrainOpen] = useState(false);

  // ── Pagination handlers ──────────────────────────────────────────────────
  function goNext() {
    const nextCursor = data?.next_cursor;
    if (!nextCursor) return;
    setCursorStack((prev) => [...prev, String(nextCursor)]);
  }

  function goPrev() {
    if (cursorStack.length <= 1) return;
    setCursorStack((prev) => prev.slice(0, -1));
  }

  const hasNext = !!data?.next_cursor;
  const hasPrev = cursorStack.length > 1;

  // ── Render ───────────────────────────────────────────────────────────────
  if (isError) {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">Strains</h1>
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          Failed to load strains. Check that the backend is running.
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Strains</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Browse workspace strains</p>
        </div>
        <Button type="button" size="sm" onClick={() => setNewStrainOpen(true)}>
          New Strain
        </Button>
      </div>

      {/* Data grid */}
      <DataGrid
        rowData={strains}
        columnDefs={strainColumnDefs}
        loading={isLoading}
        height="calc(100vh - 240px)"
        suppressFilters
        searchPlaceholder={false}
        onRowClick={(strain) => router.push(`/strains/${strain.id}`)}
        emptyState={<StrainsEmptyState />}
      />

      {/* Pagination controls */}
      {(hasPrev || hasNext) && (
        <div className="flex items-center justify-end gap-2">
          <Button type="button" variant="outline" size="sm" onClick={goPrev} disabled={!hasPrev}>
            Previous
          </Button>
          <Button type="button" variant="outline" size="sm" onClick={goNext} disabled={!hasNext}>
            Next
          </Button>
        </div>
      )}

      {/* New Strain dialog — create mode */}
      <StrainFormDialog open={newStrainOpen} onOpenChange={setNewStrainOpen} />
    </div>
  );
}
