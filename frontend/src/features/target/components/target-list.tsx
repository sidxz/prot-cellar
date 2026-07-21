"use client";

import { TagFilter, type TagFilterValue } from "@/features/tagging";
import { DataGrid } from "@/shared/components/data-grid/data-grid";
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
import type { TargetType } from "@/shared/lib/api/model";
import { Crosshair } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTargets } from "../hooks/use-targets";
import { TARGET_TYPE_LABELS } from "../types";
import type { TargetListFilters } from "../types";
import { targetColumnDefs } from "./target-columns";
import { TargetFormDialog } from "./target-form-dialog";

// ---------------------------------------------------------------------------
// LocalStorage helpers
// ---------------------------------------------------------------------------
const LS_KEY = "pc-targets-filters";

function readFilters(): TargetListFilters {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(LS_KEY);
    if (!raw) return {};
    return JSON.parse(raw) as TargetListFilters;
  } catch {
    return {};
  }
}

function writeFilters(filters: TargetListFilters) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(LS_KEY, JSON.stringify(filters));
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------
function TargetsEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-20 text-center text-muted-foreground">
      <Crosshair className="h-10 w-10 opacity-30" />
      <p className="text-sm font-medium">No targets match your filters</p>
      <p className="text-xs">Try adjusting the target type or ChEMBL ID filter.</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// TargetListPage
// ---------------------------------------------------------------------------
export function TargetListPage() {
  const router = useRouter();

  // ── Filters ─────────────────────────────────────────────────────────────
  // Lazy initializer — `readFilters` is called once at mount, not on every render
  const [initialFilters] = useState(readFilters);

  const [filters, setFilters] = useState<TargetListFilters>(initialFilters);
  const [targetTypeValue, setTargetTypeValue] = useState<string>(
    initialFilters.targetType ?? "all",
  );
  const [chemblIdInput, setChemblIdInput] = useState<string>(initialFilters.chemblId ?? "");
  const [tagFilter, setTagFilter] = useState<TagFilterValue>({
    tagIds: initialFilters.tags ?? [],
    tagLogic: initialFilters.tagLogic ?? "any",
  });

  // Persist filters to localStorage on change
  useEffect(() => {
    writeFilters(filters);
  }, [filters]);

  // ── Debounced chembl_id filter ────────────────────────────────────────────
  const chemblDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleChemblIdChange = useCallback((raw: string) => {
    setChemblIdInput(raw);
    if (chemblDebounceRef.current) clearTimeout(chemblDebounceRef.current);
    chemblDebounceRef.current = setTimeout(() => {
      setFilters((prev) => ({ ...prev, chemblId: raw.trim() || undefined }));
    }, 300);
  }, []);

  // ── Target type filter ───────────────────────────────────────────────────
  function handleTargetTypeChange(val: string) {
    setTargetTypeValue(val);
    setFilters((prev) => ({
      ...prev,
      targetType: val === "all" ? undefined : (val as TargetType),
    }));
  }

  function applyTagFilter(v: TagFilterValue) {
    setTagFilter(v);
    setFilters((prev) => ({
      ...prev,
      tags: v.tagIds.length ? v.tagIds : undefined,
      tagLogic: v.tagLogic,
    }));
  }

  // ── Cursor pagination ────────────────────────────────────────────────────
  // cursorStack[0] = first page (undefined), cursorStack[1] = second page cursor, …
  const [cursorStack, setCursorStack] = useState<(string | undefined)[]>([undefined]);
  const currentCursor = cursorStack[cursorStack.length - 1];

  // Reset pagination when filters change
  const prevFiltersRef = useRef(filters);
  useEffect(() => {
    if (prevFiltersRef.current !== filters) {
      prevFiltersRef.current = filters;
      setCursorStack([undefined]);
    }
  }, [filters]);

  // ── Data ─────────────────────────────────────────────────────────────────
  const { data, isLoading, isError } = useTargets(filters, currentCursor);

  const targets = useMemo(() => {
    if (!data?.items) return undefined;
    // biome-ignore lint/suspicious/noExplicitAny: narrowing cast at feature boundary
    return data.items as any[];
  }, [data]);

  // ── New Target dialog ────────────────────────────────────────────────────
  const [newTargetOpen, setNewTargetOpen] = useState(false);

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
        <h1 className="text-2xl font-semibold tracking-tight">Targets</h1>
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          Failed to load targets. Check that the backend is running.
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Targets</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Browse the target catalog</p>
        </div>
        <Button type="button" size="sm" onClick={() => setNewTargetOpen(true)}>
          New Target
        </Button>
      </div>

      {/* Toolbar */}
      <div className="flex flex-wrap items-end gap-3 rounded-lg border bg-muted/20 px-4 py-3">
        {/* Target type select */}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="target-type" className="text-xs text-muted-foreground">
            Target type
          </Label>
          <Select value={targetTypeValue} onValueChange={handleTargetTypeChange}>
            <SelectTrigger id="target-type" className="h-8 w-52" aria-label="Target type">
              <SelectValue placeholder="All types" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All types</SelectItem>
              {(Object.entries(TARGET_TYPE_LABELS) as [TargetType, string][]).map(
                ([key, label]) => (
                  <SelectItem key={key} value={key}>
                    {label}
                  </SelectItem>
                ),
              )}
            </SelectContent>
          </Select>
        </div>

        {/* ChEMBL ID filter */}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="chembl-id-filter" className="text-xs text-muted-foreground">
            ChEMBL ID
          </Label>
          <Input
            id="chembl-id-filter"
            placeholder="e.g. CHEMBL203"
            value={chemblIdInput}
            onChange={(e) => handleChemblIdChange(e.target.value)}
            className="h-8 w-40"
          />
        </div>

        {/* Tag facet */}
        <TagFilter value={tagFilter} onChange={applyTagFilter} />
      </div>

      {/* Data grid */}
      <DataGrid
        rowData={targets}
        columnDefs={targetColumnDefs}
        loading={isLoading}
        height="calc(100vh - 310px)"
        suppressFilters
        searchPlaceholder={false}
        onRowClick={(target) => router.push(`/targets/${target.id}`)}
        emptyState={<TargetsEmptyState />}
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

      {/* New Target dialog — create mode */}
      <TargetFormDialog open={newTargetOpen} onOpenChange={setNewTargetOpen} />
    </div>
  );
}
