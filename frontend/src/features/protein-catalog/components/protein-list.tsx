"use client";

import { DataGrid } from "@/shared/components/data-grid/data-grid";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import { Dna } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useProteins } from "../hooks/use-proteins";
import type { ProteinListFilters } from "../types";
import { proteinColumnDefs } from "./protein-columns";

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

interface ReviewedToggleProps {
  value: ReviewedState;
  onChange: (v: ReviewedState) => void;
}

function ReviewedToggle({ value, onChange }: ReviewedToggleProps) {
  const options: ReviewedState[] = ["all", "reviewed", "unreviewed"];
  return (
    <div className="flex items-center gap-1 rounded-md border bg-muted/40 p-0.5">
      {options.map((opt) => (
        <button
          key={opt}
          type="button"
          onClick={() => onChange(opt)}
          className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
            value === opt
              ? "bg-background text-foreground shadow-xs"
              : "text-muted-foreground hover:text-foreground"
          }`}
          aria-pressed={value === opt}
        >
          {opt === "all" ? "All" : opt === "reviewed" ? "Swiss-Prot" : "TrEMBL"}
        </button>
      ))}
    </div>
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
      <p className="text-xs">Try adjusting the reviewed filter or length range.</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ProteinListPage
// ---------------------------------------------------------------------------
export function ProteinListPage() {
  const router = useRouter();

  // ── Filters ─────────────────────────────────────────────────────────────
  const [filters, setFilters] = useState<ProteinListFilters>(() => readFilters());
  const [reviewedState, setReviewedState] = useState<ReviewedState>(() =>
    filterToReviewed(readFilters().reviewed),
  );
  const [minLengthInput, setMinLengthInput] = useState<string>(() => {
    const f = readFilters();
    return f.minLength != null ? String(f.minLength) : "";
  });
  const [maxLengthInput, setMaxLengthInput] = useState<string>(() => {
    const f = readFilters();
    return f.maxLength != null ? String(f.maxLength) : "";
  });

  // Persist filters to localStorage on change
  useEffect(() => {
    writeFilters(filters);
  }, [filters]);

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
  const { data, isLoading, isError } = useProteins(filters, currentCursor);

  const proteins = useMemo(() => {
    if (!data?.items) return undefined;
    // Cast from ProteinResponse[] to Protein[] — our narrowed type is compatible
    // biome-ignore lint/suspicious/noExplicitAny: narrowing cast at feature boundary
    return data.items as any[];
  }, [data]);

  // ── ID-jump box ──────────────────────────────────────────────────────────
  const [jumpValue, setJumpValue] = useState("");

  const handleJump = useCallback(() => {
    const trimmed = jumpValue.trim();
    if (!trimmed) return;
    router.push(`/proteins/${trimmed}`);
  }, [jumpValue, router]);

  // ── Filter handlers ──────────────────────────────────────────────────────
  function applyReviewed(state: ReviewedState) {
    setReviewedState(state);
    setFilters((prev) => ({ ...prev, reviewed: reviewedToFilter(state) }));
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
    const nextCursor = data?.next_cursor as string | null | undefined;
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
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Proteins</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Browse the protein catalog</p>
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex flex-wrap items-end gap-3 rounded-lg border bg-muted/20 px-4 py-3">
        {/* Reviewed tri-state */}
        <div className="flex flex-col gap-1.5">
          <Label className="text-xs text-muted-foreground">Database</Label>
          <ReviewedToggle value={reviewedState} onChange={applyReviewed} />
        </div>

        {/* Min length */}
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

        {/* Max length */}
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

        {/* Separator */}
        <div className="ml-auto flex flex-col gap-1.5">
          <Label htmlFor="id-jump" className="text-xs text-muted-foreground">
            Open accession / ID
          </Label>
          <div className="flex items-center gap-1.5">
            <Input
              id="id-jump"
              placeholder="P12345 or ALBU_HUMAN"
              value={jumpValue}
              onChange={(e) => setJumpValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleJump();
              }}
              className="h-8 w-56"
            />
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={handleJump}
              disabled={!jumpValue.trim()}
              className="h-8"
            >
              Open
            </Button>
          </div>
        </div>
      </div>

      {/* Data grid */}
      <DataGrid
        rowData={proteins}
        columnDefs={proteinColumnDefs}
        loading={isLoading}
        height="calc(100vh - 310px)"
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
