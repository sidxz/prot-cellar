"use client";

import { OrganismRef } from "@/shared/components/common/organism-ref";
import { DataGrid } from "@/shared/components/data-grid/data-grid";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { cn } from "@/shared/lib/utils";
import { Dna, FlaskConical, Search, SlidersHorizontal } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { useProteins } from "../hooks/use-proteins";
import type { ProteinListFilters, ProteinListItem } from "../types";
import { PROTEIN_ROW_HEIGHT, proteinColumnDefs } from "./protein-columns";

// ---------------------------------------------------------------------------
// LocalStorage helpers
// ---------------------------------------------------------------------------
const LS_KEY = "pc-proteins-filters";

function readFilters(): ProteinListFilters {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(LS_KEY);
    if (!raw) return {};
    return JSON.parse(raw) as ProteinListFilters;
  } catch {
    return {};
  }
}

function writeFilters(filters: ProteinListFilters) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(LS_KEY, JSON.stringify(filters));
}

// ---------------------------------------------------------------------------
// Reviewed tri-state control
// ---------------------------------------------------------------------------
type ReviewedState = "all" | "reviewed" | "unreviewed";

function reviewedToFilter(state: ReviewedState): boolean | undefined {
  if (state === "reviewed") return true;
  if (state === "unreviewed") return false;
  return undefined;
}

function filterToReviewed(v: boolean | undefined): ReviewedState {
  if (v === true) return "reviewed";
  if (v === false) return "unreviewed";
  return "all";
}

function ReviewedToggle({
  value,
  onChange,
}: {
  value: ReviewedState;
  onChange: (v: ReviewedState) => void;
}) {
  const options: ReviewedState[] = ["all", "reviewed", "unreviewed"];
  return (
    <div className="flex items-center gap-1 rounded-md border bg-muted/40 p-0.5">
      {options.map((opt) => (
        <button
          key={opt}
          type="button"
          onClick={() => onChange(opt)}
          className={cn(
            "rounded px-2.5 py-1 text-xs font-medium transition-colors",
            value === opt
              ? "bg-background text-foreground shadow-xs"
              : "text-muted-foreground hover:text-foreground",
          )}
          aria-pressed={value === opt}
        >
          {opt === "all" ? "All" : opt === "reviewed" ? "Swiss-Prot" : "TrEMBL"}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Boolean filter chip
// ---------------------------------------------------------------------------
function FilterChip({
  active,
  onClick,
  icon: Icon,
  children,
}: {
  active: boolean;
  onClick: () => void;
  icon?: typeof FlaskConical;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-xs font-medium transition-colors",
        active
          ? "border-primary/30 bg-primary/10 text-primary"
          : "border-border bg-background text-muted-foreground hover:text-foreground",
      )}
    >
      {Icon && <Icon className="h-3.5 w-3.5" />}
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------
function ProteinsEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-20 text-center text-muted-foreground">
      <Dna className="h-10 w-10 opacity-30" />
      <p className="text-sm font-medium">No proteins match your filters</p>
      <p className="text-xs">Try a different search term or clear a filter.</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ProteinListPage
// ---------------------------------------------------------------------------
export function ProteinListPage() {
  const router = useRouter();

  // ── Filters ─────────────────────────────────────────────────────────────
  const [initialFilters] = useState(readFilters);
  const [filters, setFilters] = useState<ProteinListFilters>(initialFilters);
  const [reviewedState, setReviewedState] = useState<ReviewedState>(
    filterToReviewed(initialFilters.reviewed),
  );
  const [searchInput, setSearchInput] = useState(initialFilters.search ?? "");
  const [showMore, setShowMore] = useState(
    initialFilters.minLength != null || initialFilters.maxLength != null,
  );
  const [minLengthInput, setMinLengthInput] = useState<string>(
    initialFilters.minLength != null ? String(initialFilters.minLength) : "",
  );
  const [maxLengthInput, setMaxLengthInput] = useState<string>(
    initialFilters.maxLength != null ? String(initialFilters.maxLength) : "",
  );

  // Debounce the free-text search into the filter set (300ms).
  useEffect(() => {
    const handle = setTimeout(() => {
      setFilters((prev) => {
        const next = searchInput.trim() || undefined;
        if (prev.search === next) return prev;
        return { ...prev, search: next };
      });
    }, 300);
    return () => clearTimeout(handle);
  }, [searchInput]);

  // Persist filters to localStorage on change
  useEffect(() => {
    writeFilters(filters);
  }, [filters]);

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
  const { data, isLoading, isError } = useProteins(filters, currentCursor);

  const proteins = useMemo(() => data?.items as ProteinListItem[] | undefined, [data]);

  // Resolve the organism context only when the whole page shares one organism.
  const soleOrganismId = useMemo(() => {
    if (!proteins || proteins.length === 0) return undefined;
    const ids = new Set(proteins.map((p) => p.organism_id));
    return ids.size === 1 ? proteins[0].organism_id : undefined;
  }, [proteins]);

  const totalCount = data?.total_count ?? undefined;
  const anyFilterActive =
    !!filters.search ||
    !!filters.hasStructure ||
    !!filters.isEnzyme ||
    !!filters.hasChembl ||
    filters.reviewed != null ||
    filters.minLength != null ||
    filters.maxLength != null;

  // ── Filter handlers ──────────────────────────────────────────────────────
  function applyReviewed(state: ReviewedState) {
    setReviewedState(state);
    setFilters((prev) => ({ ...prev, reviewed: reviewedToFilter(state) }));
  }

  function toggleBool(key: "hasStructure" | "isEnzyme" | "hasChembl") {
    setFilters((prev) => ({ ...prev, [key]: prev[key] ? undefined : true }));
  }

  function applyMinLength(raw: string) {
    setMinLengthInput(raw);
    const n = raw === "" ? undefined : Number(raw);
    setFilters((prev) => ({ ...prev, minLength: Number.isFinite(n) ? (n as number) : undefined }));
  }

  function applyMaxLength(raw: string) {
    setMaxLengthInput(raw);
    const n = raw === "" ? undefined : Number(raw);
    setFilters((prev) => ({ ...prev, maxLength: Number.isFinite(n) ? (n as number) : undefined }));
  }

  // ── Pagination handlers ──────────────────────────────────────────────────
  function goNext() {
    const nextCursor = data?.next_cursor;
    if (!nextCursor) return;
    setCursorStack((prev) => [...prev, nextCursor]);
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
        <h1 className="text-2xl font-semibold tracking-tight">Proteins</h1>
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          Failed to load proteins. Check that the backend is running.
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Page header with organism + count context */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Proteins</h1>
        {/* div (not p): OrganismRef can render a block-level Skeleton while
            loading, which is invalid DOM nesting inside a <p>. */}
        <div className="mt-0.5 flex items-center gap-1.5 text-sm text-muted-foreground">
          {soleOrganismId ? (
            <>
              <OrganismRef id={soleOrganismId} className="text-sm font-medium text-foreground" />
              <span aria-hidden>·</span>
            </>
          ) : null}
          {totalCount != null ? (
            <span>
              {totalCount.toLocaleString()} {anyFilterActive ? "matching" : "proteins"}
            </span>
          ) : (
            <span>Target-triage catalog</span>
          )}
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex flex-col gap-3 rounded-lg border bg-muted/20 px-4 py-3">
        <div className="flex flex-wrap items-center gap-3">
          {/* Search */}
          <div className="relative min-w-[260px] flex-1">
            <Search className="-translate-y-1/2 absolute top-1/2 left-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search gene, locus (Rv1908c), accession, or name…"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="h-9 pl-8"
              aria-label="Search proteins"
            />
          </div>

          {/* Database tri-state */}
          <ReviewedToggle value={reviewedState} onChange={applyReviewed} />

          {/* Boolean facets */}
          <FilterChip active={!!filters.hasStructure} onClick={() => toggleBool("hasStructure")}>
            Has structure
          </FilterChip>
          <FilterChip
            active={!!filters.isEnzyme}
            onClick={() => toggleBool("isEnzyme")}
            icon={FlaskConical}
          >
            Enzyme
          </FilterChip>
          <FilterChip active={!!filters.hasChembl} onClick={() => toggleBool("hasChembl")}>
            Has inhibitors
          </FilterChip>

          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="ml-auto h-8 text-muted-foreground"
            onClick={() => setShowMore((s) => !s)}
          >
            <SlidersHorizontal className="mr-1 h-3.5 w-3.5" />
            Length
          </Button>
        </div>

        {/* Length range (collapsible) */}
        {showMore && (
          <div className="flex items-end gap-3 border-t pt-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="min-length" className="text-xs text-muted-foreground">
                Min length
              </Label>
              <Input
                id="min-length"
                type="number"
                min={1}
                placeholder="—"
                value={minLengthInput}
                onChange={(e) => applyMinLength(e.target.value)}
                className="h-8 w-24"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="max-length" className="text-xs text-muted-foreground">
                Max length
              </Label>
              <Input
                id="max-length"
                type="number"
                min={1}
                placeholder="—"
                value={maxLengthInput}
                onChange={(e) => applyMaxLength(e.target.value)}
                className="h-8 w-24"
              />
            </div>
          </div>
        )}
      </div>

      {/* Data grid */}
      <DataGrid<ProteinListItem>
        rowData={proteins}
        columnDefs={proteinColumnDefs}
        loading={isLoading}
        rowHeight={PROTEIN_ROW_HEIGHT}
        height="calc(100vh - 320px)"
        suppressFilters
        searchPlaceholder={false}
        onRowClick={(protein) => router.push(`/proteins/${protein.primary_accession}`)}
        emptyState={<ProteinsEmptyState />}
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
