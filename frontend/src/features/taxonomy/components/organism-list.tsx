"use client";

import { DataGrid } from "@/shared/components/data-grid/data-grid";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Leaf } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useOrganisms } from "../hooks/use-organisms";
import type { OrganismListFilters } from "../types";
import { organismColumnDefs } from "./organism-columns";

// ---------------------------------------------------------------------------
// LocalStorage helpers
// ---------------------------------------------------------------------------
const LS_KEY = "pc-organisms-filters";

function readFilters(): OrganismListFilters {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(LS_KEY);
    if (!raw) return {};
    return JSON.parse(raw) as OrganismListFilters;
  } catch {
    return {};
  }
}

function writeFilters(filters: OrganismListFilters) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(LS_KEY, JSON.stringify(filters));
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------
function OrganismsEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-20 text-center text-muted-foreground">
      <Leaf className="h-10 w-10 opacity-30" />
      <p className="text-sm font-medium">No organisms match your filters</p>
      <p className="text-xs">Try adjusting the name or rank filter.</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// OrganismListPage
// ---------------------------------------------------------------------------
export function OrganismListPage() {
  const router = useRouter();

  // ── Filters ─────────────────────────────────────────────────────────────
  const [initialFilters] = useState(readFilters);

  const [filters, setFilters] = useState<OrganismListFilters>(initialFilters);
  const [nameInput, setNameInput] = useState<string>(initialFilters.name ?? "");
  const [rankInput, setRankInput] = useState<string>(initialFilters.rank ?? "");

  // Persist filters to localStorage on change
  useEffect(() => {
    writeFilters(filters);
  }, [filters]);

  // ── Debounced name filter ────────────────────────────────────────────────
  const nameDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleNameChange = useCallback((raw: string) => {
    setNameInput(raw);
    if (nameDebounceRef.current) clearTimeout(nameDebounceRef.current);
    nameDebounceRef.current = setTimeout(() => {
      setFilters((prev) => ({ ...prev, name: raw.trim() || undefined }));
    }, 300);
  }, []);

  // ── Debounced rank filter ─────────────────────────────────────────────────
  const rankDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleRankChange = useCallback((raw: string) => {
    setRankInput(raw);
    if (rankDebounceRef.current) clearTimeout(rankDebounceRef.current);
    rankDebounceRef.current = setTimeout(() => {
      setFilters((prev) => ({ ...prev, rank: raw.trim() || undefined }));
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
  const { data, isLoading, isError } = useOrganisms(filters, currentCursor);

  const organisms = useMemo(() => {
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
        <h1 className="text-2xl font-semibold tracking-tight">Organisms</h1>
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          Failed to load organisms. Check that the backend is running.
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Organisms</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Browse the organism taxonomy</p>
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex flex-wrap items-end gap-3 rounded-lg border bg-muted/20 px-4 py-3">
        {/* Name search */}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="organism-name" className="text-xs text-muted-foreground">
            Scientific name
          </Label>
          <Input
            id="organism-name"
            placeholder="e.g. Homo sapiens"
            value={nameInput}
            onChange={(e) => handleNameChange(e.target.value)}
            className="h-8 w-52"
          />
        </div>

        {/* Rank filter */}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="organism-rank" className="text-xs text-muted-foreground">
            Rank
          </Label>
          <Input
            id="organism-rank"
            placeholder="e.g. species"
            value={rankInput}
            onChange={(e) => handleRankChange(e.target.value)}
            className="h-8 w-36"
          />
        </div>
      </div>

      {/* Data grid */}
      <DataGrid
        rowData={organisms}
        columnDefs={organismColumnDefs}
        loading={isLoading}
        height="calc(100vh - 280px)"
        suppressFilters
        searchPlaceholder={false}
        onRowClick={(org) => router.push(`/organisms/${org.id}`)}
        emptyState={<OrganismsEmptyState />}
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
