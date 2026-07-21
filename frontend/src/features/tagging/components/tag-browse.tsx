"use client";

import { AlertTriangle } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { DataGrid } from "@/shared/components/data-grid/data-grid";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import type { ColDef, ICellRendererParams } from "ag-grid-community";

import { useTagEntities } from "../hooks/use-tag-entities";
import type { TaggedEntity } from "../types";
import { TagFilter, type TagFilterValue } from "./tag-filter";

// Verified against the backend's tag_browse_repository.py (entity_type
// literals from tag_links_all) and the app/(dashboard)/ route dirs. All 6
// taggable entities have a directly-addressable detail route.
const ROUTE_PREFIX: Record<string, string> = {
  Protein: "/proteins",
  Gene: "/genes",
  Target: "/targets",
  Organism: "/organisms",
  Strain: "/strains",
  Proteome: "/proteomes",
};

/**
 * Detail-page href for a tagged entity. Every type but Protein is addressed
 * by its internal id; proteins are addressed by primary_accession, and
 * `TaggedEntity.label` for a Protein row IS its primary_accession (see
 * SQLAlchemyTagBrowseRepository._branch — the "Protein" branch's label_col
 * is `ProteinModel.primary_accession`).
 */
export function hrefFor(row: { entity_type: string; entity_id: string; label: string }): string {
  const prefix = ROUTE_PREFIX[row.entity_type] ?? "";
  const key = row.entity_type === "Protein" ? row.label : row.entity_id;
  return `${prefix}/${key}`;
}

// Per-type tint so the Type column reads at a glance.
const TYPE_STYLE: Record<string, string> = {
  Protein: "bg-violet-100 text-violet-700 dark:bg-violet-950 dark:text-violet-300",
  Gene: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  Target: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  Organism: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  Strain: "bg-cyan-100 text-cyan-700 dark:bg-cyan-950 dark:text-cyan-300",
  Proteome: "bg-teal-100 text-teal-700 dark:bg-teal-950 dark:text-teal-300",
};

function FacetChip({
  label,
  count,
  active,
  onClick,
}: {
  label: string;
  count: number;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <Button
      type="button"
      size="sm"
      variant={active ? "default" : "outline"}
      className="h-7 rounded-full px-3 text-xs"
      onClick={onClick}
    >
      {label}
      <span className="ml-1.5 opacity-70">{count}</span>
    </Button>
  );
}

/**
 * Cross-entity tag browse: pick one or more tags, see every entity (across
 * all 6 taggable types) that carries them, linked to its detail page. Ported
 * from chem-cellar's tag-browse.tsx; adapted to prot-cellar's 6 entity types,
 * its `DataGrid`/`Badge` primitives (no `PageHeader`/`formatDate` here), and
 * the protein accession-vs-id routing quirk documented on `hrefFor`.
 */
export function TagBrowse() {
  const router = useRouter();
  const params = useSearchParams();
  const initialTag = params.get("tag");
  const [filter, setFilter] = useState<TagFilterValue>({
    tagIds: initialTag ? [initialTag] : [],
    tagLogic: "any",
  });
  const [typeFilter, setTypeFilter] = useState<string | null>(null);

  const hasTags = filter.tagIds.length > 0;
  const types = typeFilter ? [typeFilter] : undefined;
  const { data, isLoading, error } = useTagEntities(filter.tagIds, filter.tagLogic, types);

  // Unfiltered counts per type, for the facet chips — fetched once more
  // without a type filter so switching chips doesn't blank out the others'
  // counts. Cheap: same query key space, cached by react-query.
  const { data: allData } = useTagEntities(filter.tagIds, filter.tagLogic);

  const counts = useMemo(() => {
    const m = new Map<string, number>();
    for (const r of allData ?? []) m.set(r.entity_type, (m.get(r.entity_type) ?? 0) + 1);
    return m;
  }, [allData]);

  const rows = data ?? [];

  const columnDefs = useMemo<ColDef<TaggedEntity>[]>(
    () => [
      {
        headerName: "Type",
        field: "entity_type",
        width: 150,
        cellRenderer: ({ value }: ICellRendererParams<TaggedEntity>) => (
          <Badge variant="secondary" className={`font-normal ${TYPE_STYLE[value as string] ?? ""}`}>
            {value}
          </Badge>
        ),
      },
      {
        headerName: "Name",
        field: "label",
        flex: 1,
        minWidth: 220,
        cellRenderer: ({ data: row }: ICellRendererParams<TaggedEntity>) => {
          if (!row) return null;
          return (
            <Link href={hrefFor(row)} className="text-primary hover:underline">
              {row.label}
            </Link>
          );
        },
      },
      {
        headerName: "Tagged on",
        field: "assigned_at",
        width: 170,
        valueFormatter: (p) => new Date(p.value as string).toLocaleDateString(),
      },
    ],
    [],
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Browse by Tag</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Pick one or more tags to see everything that carries them.
          </p>
        </div>
        <TagFilter
          value={filter}
          onChange={(v) => {
            setFilter(v);
            setTypeFilter(null);
          }}
        />
      </div>

      {!hasTags && (
        <div className="rounded-md border border-dashed py-12 text-center text-sm text-muted-foreground">
          Select one or more tags above to see every protein, gene, target, organism, strain and
          proteome that carries them.
        </div>
      )}

      {hasTags && error && (
        <div className="flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          Couldn’t load tagged items: {(error as Error).message}
        </div>
      )}

      {hasTags && !error && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="mr-1 text-sm text-muted-foreground">
              {allData
                ? `${allData.length} item${allData.length === 1 ? "" : "s"} across ${counts.size} type${
                    counts.size === 1 ? "" : "s"
                  }`
                : ""}
            </span>
            <FacetChip
              label="All"
              count={allData?.length ?? 0}
              active={!typeFilter}
              onClick={() => setTypeFilter(null)}
            />
            {[...counts.entries()].map(([type, n]) => (
              <FacetChip
                key={type}
                label={type}
                count={n}
                active={typeFilter === type}
                onClick={() => setTypeFilter(type)}
              />
            ))}
          </div>

          <DataGrid<TaggedEntity>
            rowData={rows}
            columnDefs={columnDefs}
            loading={isLoading}
            onRowClick={(row) => router.push(hrefFor(row))}
            height={560}
            searchPlaceholder="Filter results…"
            emptyState={
              <p className="py-10 text-center text-sm text-muted-foreground">
                Nothing carries {filter.tagIds.length > 1 ? "these tags" : "this tag"} yet.
              </p>
            }
          />
        </div>
      )}
    </div>
  );
}
