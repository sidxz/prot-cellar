"use client";

import { DataGrid } from "@/shared/components/data-grid/data-grid";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Database } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useProteomes } from "../hooks/use-proteomes";
import type { ProteomeListFilters } from "../types";
import { proteomeColumnDefs } from "./proteome-columns";

// ---------------------------------------------------------------------------
// LocalStorage helpers
// ---------------------------------------------------------------------------
const LS_KEY = "pc-proteomes-filters";

function readFilters(): ProteomeListFilters {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(LS_KEY);
    if (!raw) return {};
    return JSON.parse(raw) as ProteomeListFilters;
  } catch {
    return {};
  }
}

function writeFilters(filters: ProteomeListFilters) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(LS_KEY, JSON.stringify(filters));
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------
function ProteomesEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-20 text-center text-muted-foreground">
      <Database className="h-10 w-10 opacity-30" />
      <p className="text-sm font-medium">No proteomes match your filters</p>
      <p className="text-xs">Try adjusting the organism ID filter.</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ProteomeListPage
// ---------------------------------------------------------------------------
export function ProteomeListPage() {
  const router = useRouter();

  // ── Filters ─────────────────────────────────────────────────────────────
  const [initialFilters] = useState(readFilters);

  const [filters, setFilters] = useState<ProteomeListFilters>(initialFilters);
  const [organismIdInput, setOrganismIdInput] = useState<string>(initialFilters.organismId ?? "");

  // Persist filters to localStorage on change
  useEffect(() => {
    writeFilters(filters);
  }, [filters]);

  // ── Debounced organism_id filter ─────────────────────────────────────────
  const organismDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleOrganismIdChange = useCallback((raw: string) => {
    setOrganismIdInput(raw);
    if (organismDebounceRef.current) clearTimeout(organismDebounceRef.current);
    organismDebounceRef.current = setTimeout(() => {
      setFilters((prev) => ({ ...prev, organismId: raw.trim() || undefined }));
    }, 300);
  }, []);

  // ── Cursor pagination ────────────────────────────────────────────────────
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
  const { data, isLoading, isError } = useProteomes(filters, currentCursor);

  const proteomes = useMemo(() => {
    if (!data?.items) return undefined;
    // biome-ignore lint/suspicious/noExplicitAny: narrowing cast at feature boundary
    return data.items as any[];
  }, [data]);

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
        <h1 className="text-2xl font-semibold tracking-tight">Proteomes</h1>
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          Failed to load proteomes. Check that the backend is running.
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Proteomes</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Browse reference proteomes from UniProt
          </p>
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex flex-wrap items-end gap-3 rounded-lg border bg-muted/20 px-4 py-3">
        {/* Organism ID filter */}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="proteome-organism-id" className="text-xs text-muted-foreground">
            Organism ID
          </Label>
          <Input
            id="proteome-organism-id"
            placeholder="e.g. 9606"
            value={organismIdInput}
            onChange={(e) => handleOrganismIdChange(e.target.value)}
            className="h-8 w-48"
            aria-describedby="proteome-organism-id-hint"
          />
          <p id="proteome-organism-id-hint" className="sr-only">
            Filter by organism id (search picker — future)
          </p>
        </div>
      </div>

      {/* Data grid */}
      <DataGrid
        rowData={proteomes}
        columnDefs={proteomeColumnDefs}
        loading={isLoading}
        height="calc(100vh - 280px)"
        suppressFilters
        searchPlaceholder={false}
        onRowClick={(proteome) => router.push(`/proteomes/${proteome.id}`)}
        emptyState={<ProteomesEmptyState />}
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
    </div>
  );
}
