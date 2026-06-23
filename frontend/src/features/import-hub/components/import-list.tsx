// frontend/src/features/import-hub/components/import-list.tsx
"use client";

import { Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { DataGrid } from "@/shared/components/data-grid/data-grid";
import { Button } from "@/shared/components/ui/button";

import { useImportList } from "../hooks/use-imports";
import { importColumnDefs } from "./import-columns";
import { StartImportDialog } from "./start-import-dialog";

function ImportsEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-20 text-center text-muted-foreground">
      <Upload className="h-10 w-10 opacity-30" />
      <p className="text-sm font-medium">No imports yet</p>
      <p className="text-xs">Start your first import with the "New import" button above.</p>
    </div>
  );
}

export function ImportListPage() {
  const router = useRouter();
  const [cursorStack, setCursorStack] = useState<(string | undefined)[]>([undefined]);
  const currentCursor = cursorStack[cursorStack.length - 1];
  const { data, isLoading, isError, refetch } = useImportList(currentCursor);

  const runs = useMemo(() => {
    if (!data?.items) return undefined;
    // biome-ignore lint/suspicious/noExplicitAny: narrowing cast at feature boundary
    return data.items as any[];
  }, [data]);

  const [newOpen, setNewOpen] = useState(false);

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

  if (isError) {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">Imports</h1>
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          Failed to load imports. Check that the backend is running.
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Imports</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Run and monitor data imports</p>
        </div>
        <div className="flex items-center gap-3">
          <Button type="button" variant="outline" size="sm" onClick={() => refetch()}>
            Refresh
          </Button>
          <Button type="button" size="sm" onClick={() => setNewOpen(true)}>
            New import
          </Button>
        </div>
      </div>

      <DataGrid
        rowData={runs}
        columnDefs={importColumnDefs}
        loading={isLoading}
        height="calc(100vh - 240px)"
        suppressFilters
        searchPlaceholder={false}
        onRowClick={(run) => router.push(`/admin/imports/${run.id}`)}
        emptyState={<ImportsEmptyState />}
      />

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

      <StartImportDialog open={newOpen} onOpenChange={setNewOpen} />
    </div>
  );
}
