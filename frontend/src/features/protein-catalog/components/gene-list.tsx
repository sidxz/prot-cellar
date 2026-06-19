"use client";

import { DataGrid } from "@/shared/components/data-grid/data-grid";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Dna } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useGenes } from "../hooks/use-genes";
import type { GeneListFilters } from "../types";
import { geneColumnDefs } from "./gene-columns";

// ---------------------------------------------------------------------------
// LocalStorage helpers
// ---------------------------------------------------------------------------
const LS_KEY = "pc-genes-filters";

function readFilters(): GeneListFilters {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(LS_KEY);
    if (!raw) return {};
    return JSON.parse(raw) as GeneListFilters;
  } catch {
    return {};
  }
}

function writeFilters(filters: GeneListFilters) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(LS_KEY, JSON.stringify(filters));
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------
function GenesEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-20 text-center text-muted-foreground">
      <Dna className="h-10 w-10 opacity-30" />
      <p className="text-sm font-medium">No genes match your filters</p>
      <p className="text-xs">Try adjusting the name search or organism filter.</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// GeneListPage
// ---------------------------------------------------------------------------
export function GeneListPage() {
  const router = useRouter();

  // ── Filters ─────────────────────────────────────────────────────────────
  // Read localStorage once at mount, derive all initial state from it
  const initialFilters = readFilters();

  const [filters, setFilters] = useState<GeneListFilters>(initialFilters);
  const [nameInput, setNameInput] = useState<string>(initialFilters.name ?? "");
  // Plan 3: replace with organism picker; free-text organism ID for now
  const [organismInput, setOrganismInput] = useState<string>(initialFilters.organismId ?? "");

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

  // ── Debounced organism filter ─────────────────────────────────────────────
  const orgDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleOrganismChange = useCallback((raw: string) => {
    setOrganismInput(raw);
    if (orgDebounceRef.current) clearTimeout(orgDebounceRef.current);
    orgDebounceRef.current = setTimeout(() => {
      setFilters((prev) => ({ ...prev, organismId: raw.trim() || undefined }));
    }, 300);
  }, []);

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
  const { data, isLoading, isError } = useGenes(filters, currentCursor);

  const genes = useMemo(() => {
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
        <h1 className="text-2xl font-semibold tracking-tight">Genes</h1>
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          Failed to load genes. Check that the backend is running.
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Genes</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Browse the gene catalog</p>
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex flex-wrap items-end gap-3 rounded-lg border bg-muted/20 px-4 py-3">
        {/* Name search */}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="gene-name" className="text-xs text-muted-foreground">
            Gene name
          </Label>
          <Input
            id="gene-name"
            placeholder="e.g. TP53"
            value={nameInput}
            onChange={(e) => handleNameChange(e.target.value)}
            className="h-8 w-48"
          />
        </div>

        {/* Organism filter — free-text ID for now; Plan 3 adds organism picker */}
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="gene-organism" className="text-xs text-muted-foreground">
            Organism ID
          </Label>
          <Input
            id="gene-organism"
            placeholder="e.g. 9606"
            value={organismInput}
            onChange={(e) => handleOrganismChange(e.target.value)}
            className="h-8 w-36"
          />
        </div>
      </div>

      {/* Data grid */}
      <DataGrid
        rowData={genes}
        columnDefs={geneColumnDefs}
        loading={isLoading}
        height="calc(100vh - 280px)"
        suppressFilters
        searchPlaceholder={false}
        onRowClick={(gene) => router.push(`/genes/${gene.id}`)}
        emptyState={<GenesEmptyState />}
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
