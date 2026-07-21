"use client";

import { TagFilter, type TagFilterValue } from "@/features/tagging";
import { useOrganisms } from "@/features/taxonomy/hooks/use-organisms";
import { TAXON_FILTER_PAGE_SIZE } from "@/features/taxonomy/types";
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
import { ProteinTaxonFilters } from "./protein-taxon-filters";

// ---------------------------------------------------------------------------
// LocalStorage helpers
// ---------------------------------------------------------------------------
const LS_KEY = "pc-genes-filters";
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function readFilters(): GeneListFilters {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(LS_KEY);
    if (!raw) return {};
    const f = JSON.parse(raw) as GeneListFilters;
    // Drop stale non-UUID ids (e.g. a tax id left by the removed free-text
    // "Organism ID" input) — they'd 422 the list with no visible/clearable cause.
    if (f.organismId && !UUID_RE.test(f.organismId)) f.organismId = undefined;
    if (f.strainId && !UUID_RE.test(f.strainId)) f.strainId = undefined;
    return f;
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
  // Lazy initializer — `readFilters` is called once at mount, not on every render
  const [initialFilters] = useState(readFilters);

  const [filters, setFilters] = useState<GeneListFilters>(initialFilters);
  const [nameInput, setNameInput] = useState<string>(initialFilters.name ?? "");
  const [tagFilter, setTagFilter] = useState<TagFilterValue>({
    tagIds: initialFilters.tags ?? [],
    tagLogic: initialFilters.tagLogic ?? "any",
  });
  const { data: orgData } = useOrganisms({ limit: TAXON_FILTER_PAGE_SIZE });

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

  // ── Organism + strain filter ───────────────────────────────────────────────
  // Picking an organism defaults the strain to that organism's reference strain
  // (the designated/preferred one), so multi-strain species aren't a wall of
  // ortholog duplicates by default. The strain select can override it.
  const handleOrganismChange = useCallback(
    (organismId: string | undefined) => {
      const referenceStrain =
        orgData?.items.find((o) => o.id === organismId)?.reference_strain_id ?? undefined;
      setFilters((prev) => ({ ...prev, organismId, strainId: referenceStrain }));
    },
    [orgData],
  );

  const handleStrainChange = useCallback((strainId: string | undefined) => {
    setFilters((prev) => ({ ...prev, strainId }));
  }, []);

  const applyTagFilter = useCallback((v: TagFilterValue) => {
    setTagFilter(v);
    setFilters((prev) => ({
      ...prev,
      tags: v.tagIds.length ? v.tagIds : undefined,
      tagLogic: v.tagLogic,
    }));
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

        {/* Organism + strain (strain defaults to the organism's reference strain) */}
        <ProteinTaxonFilters
          organismId={filters.organismId}
          strainId={filters.strainId}
          onOrganismChange={handleOrganismChange}
          onStrainChange={handleStrainChange}
        />

        {/* Tag facet — NOTE: while a name search is active, the backend routes
            through GeneRepository.find_by_name, which does not apply tag
            filtering. Tags only filter the primary (name-less) list view. */}
        <TagFilter value={tagFilter} onChange={applyTagFilter} />
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
