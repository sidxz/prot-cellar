"use client";

import { Input } from "@/shared/components/ui/input";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { useGridPreferences } from "@/shared/hooks/use-grid-preferences";
import {
  AllCommunityModule,
  type ColDef,
  type ColGroupDef,
  type GetRowIdParams,
  type GridReadyEvent,
  type IDatasource,
  type ModelUpdatedEvent,
  ModuleRegistry,
  type RowClickedEvent,
  type RowSelectedEvent,
  type SelectionChangedEvent,
} from "ag-grid-community";
import { AgGridReact, type AgGridReactProps } from "ag-grid-react";
import { Search } from "lucide-react";
import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { cellarTheme } from "./ag-grid-theme";

ModuleRegistry.registerModules([AllCommunityModule]);

export interface DataGridProps<TData = unknown>
  extends Omit<AgGridReactProps<TData>, "theme" | "rowData" | "columnDefs"> {
  rowData: TData[] | undefined;
  /** When provided, the grid uses AG-Grid's Infinite Row Model: rows stream from
   *  this datasource's getRows (server pagination/sort/filter) instead of client
   *  `rowData`. Additive — existing client-side consumers omit it. */
  datasource?: IDatasource;
  /** Accepts flat ColDef arrays or ColDef/ColGroupDef mixed arrays (for grouped headers). */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  columnDefs: (ColDef<any> | ColGroupDef<any>)[];
  loading?: boolean;
  /** Rendered when rowData is empty (not loading) */
  emptyState?: ReactNode;
  /** Navigate on row click — receives the row data */
  onRowClick?: (data: TData) => void;
  /** Fixed grid height. Default: "400px" */
  height?: string | number;
  /** Suppress built-in column filters. Default: false */
  suppressFilters?: boolean;
  /** When provided, persists column state (width, order, visibility) to localStorage. */
  preferencesKey?: string;
  /** Render prop for selection toolbar. Shown above grid when rows are selected.
   *  Automatically enables rowSelection="multiple" on the grid. */
  selectionToolbar?: (selectedRows: TData[]) => ReactNode;
  /** Enable multi-row selection without rendering a built-in toolbar.
   *  When true, prepends the checkbox column and sets rowSelection="multiple".
   *  Consumers track selection via onSelectionChanged. */
  enableMultiSelect?: boolean;
  /** When true, multi-select is enabled (rowSelection="multiple") but the
   *  auto-prepended checkbox column is not rendered. Use when you want to
   *  host the checkbox inside an existing column via
   *  `checkboxSelection: true` / `headerCheckboxSelection: true`. */
  suppressSelectColumn?: boolean;
  /** Placeholder for the quick-filter search bar. Set to false to hide. */
  searchPlaceholder?: string | false;
  /** Extra controls rendered in the toolbar row, to the left of the export
   *  button. Use for primary actions (Import, New, etc.) so they share the
   *  same line as the filter and export controls.
   *
   *  When provided, the toolbar is rendered even in loading/empty states so
   *  the action remains reachable when the table has no rows yet. */
  toolbarActions?: ReactNode;
  /** Content rendered on the LEFT side of the toolbar row, where the quick-
   *  filter search would otherwise live. Use this when the search input is
   *  suppressed (`searchPlaceholder={false}`) and the page wants to put
   *  status text or other left-aligned controls there. */
  toolbarLeft?: ReactNode;
  /**
   * When this value changes to a falsy value, the grid calls `api.deselectAll()`.
   * Callers typically pass the tracked selection set size; dropping to 0 triggers clear.
   * Useful for syncing external clear-selection events (e.g. after a new search).
   */
  clearSelectionToken?: unknown;
}

export function DataGrid<TData = unknown>({
  rowData,
  datasource,
  columnDefs,
  loading,
  emptyState,
  onRowClick,
  height = "400px",
  suppressFilters = false,
  preferencesKey,
  selectionToolbar,
  enableMultiSelect,
  suppressSelectColumn,
  searchPlaceholder = "Filter...",
  toolbarActions,
  toolbarLeft,
  clearSelectionToken,
  ...rest
}: DataGridProps<TData>) {
  const selectionEnabled = !!selectionToolbar || !!enableMultiSelect;
  const isInfinite = !!datasource;
  const {
    onSelectionChanged: consumerOnSelectionChanged,
    onRowSelected: consumerOnRowSelected,
    onModelUpdated: consumerOnModelUpdated,
    rowSelection: _rowSelectionFromRest,
    ...restWithoutSelection
  } = rest;
  void _rowSelectionFromRest;
  const gridRef = useRef<AgGridReact<TData>>(null);
  const [quickFilter, setQuickFilter] = useState("");
  const [selectedRows, setSelectedRows] = useState<TData[]>([]);

  // Infinite-model selection: accumulate picks by id across blocks in a ref-backed map
  const getRowIdFn = (restWithoutSelection as { getRowId?: (p: GetRowIdParams<TData>) => string })
    .getRowId;
  const trackAcrossBlocks = isInfinite && selectionEnabled && !!getRowIdFn;
  const selectedByIdRef = useRef<Map<string, TData>>(new Map());
  const reapplyingRef = useRef(false);
  const rowId = useCallback(
    (data: TData): string => getRowIdFn?.({ data } as GetRowIdParams<TData>) ?? "",
    [getRowIdFn],
  );
  const prefs = useGridPreferences(preferencesKey ?? "__unused__");
  const hasPrefs = !!preferencesKey;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const defaultColDef = useMemo<ColDef<any>>(
    () => ({
      sortable: true,
      resizable: true,
      filter: !suppressFilters,
      suppressMovable: true,
      minWidth: 80,
    }),
    [suppressFilters],
  );

  // Inject header tooltips and prepend selection checkbox column when needed
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const finalColumnDefs = useMemo<(ColDef<any> | ColGroupDef<any>)[]>(() => {
    const withTooltips = columnDefs.map((c) =>
      !("children" in c) && c.headerTooltip == null && typeof c.headerName === "string"
        ? { ...c, headerTooltip: c.headerName }
        : c,
    );
    if (!selectionEnabled || suppressSelectColumn) return withTooltips;
    const selectCol: ColDef<TData> = {
      colId: "__select__",
      pinned: "left",
      lockPosition: "left",
      lockPinned: true,
      width: 45,
      maxWidth: 45,
      minWidth: 45,
      resizable: false,
      sortable: false,
      filter: false,
      suppressMovable: true,
      headerCheckboxSelection: !isInfinite,
      checkboxSelection: true,
    };
    return [selectCol, ...withTooltips];
  }, [columnDefs, selectionEnabled, suppressSelectColumn, isInfinite]);

  // Sync external clear-selection signal
  useEffect(() => {
    if (clearSelectionToken !== undefined && !clearSelectionToken && gridRef.current?.api) {
      selectedByIdRef.current.clear();
      setSelectedRows([]);
      gridRef.current.api.deselectAll();
    }
  }, [clearSelectionToken]);

  // Re-fit columns on columnDefs changes
  useEffect(() => {
    if (hasPrefs) return;
    if (!gridRef.current?.api) return;
    gridRef.current.api.sizeColumnsToFit();
  }, [finalColumnDefs, hasPrefs]);

  const handleRowClicked = useCallback(
    (event: RowClickedEvent<TData>) => {
      if (!onRowClick || !event.data) return;
      const target = event.event?.target as HTMLElement | null;
      if (target?.closest("button, a, [role='button']")) return;
      onRowClick(event.data);
    },
    [onRowClick],
  );

  const handleGridReady = useCallback(
    (event: GridReadyEvent<TData>) => {
      if (hasPrefs) {
        prefs.applyState(gridRef);
      } else {
        event.api.sizeColumnsToFit();
      }
    },
    [hasPrefs, prefs, gridRef],
  );

  const handleSelectionChanged = useCallback(
    (event: SelectionChangedEvent<TData>) => {
      setSelectedRows(event.api.getSelectedRows());
      consumerOnSelectionChanged?.(event);
    },
    [consumerOnSelectionChanged],
  );

  const handleRowSelected = useCallback(
    (event: RowSelectedEvent<TData>) => {
      if (!reapplyingRef.current && event.node?.data) {
        const id = rowId(event.node.data);
        if (id) {
          const map = selectedByIdRef.current;
          if (event.node.isSelected()) map.set(id, event.node.data);
          else map.delete(id);
          setSelectedRows([...map.values()]);
        }
      }
      consumerOnRowSelected?.(event);
    },
    [rowId, consumerOnRowSelected],
  );

  const handleModelUpdated = useCallback(
    (event: ModelUpdatedEvent<TData>) => {
      const map = selectedByIdRef.current;
      if (map.size > 0) {
        reapplyingRef.current = true;
        try {
          event.api.forEachNode((node) => {
            if (node.data && map.has(rowId(node.data)) && !node.isSelected()) {
              node.setSelected(true);
            }
          });
        } finally {
          reapplyingRef.current = false;
        }
      }
      consumerOnModelUpdated?.(event);
    },
    [rowId, consumerOnModelUpdated],
  );

  // In infinite mode rowData is undefined and AG-Grid owns the no-rows overlay
  const hasRows = isInfinite ? true : !!rowData?.length;
  const showSearch = searchPlaceholder !== false && hasRows;
  const renderToolbar = showSearch || !!toolbarActions || !!toolbarLeft;

  const toolbar = renderToolbar ? (
    <div className="mb-2 flex items-center gap-2">
      {showSearch ? (
        <div className="relative w-64">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder={searchPlaceholder as string}
            value={quickFilter}
            onChange={(e) => setQuickFilter(e.target.value)}
            className="h-9 pl-8"
          />
        </div>
      ) : toolbarLeft ? (
        <div className="flex items-center gap-3">{toolbarLeft}</div>
      ) : null}
      <div className="ml-auto flex items-center gap-2">{toolbarActions}</div>
    </div>
  ) : null;

  if (loading) {
    return (
      <div>
        {toolbar}
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (!hasRows && emptyState) {
    return (
      <div>
        {toolbar}
        {emptyState}
      </div>
    );
  }

  return (
    <div>
      {toolbar}
      {selectionToolbar && !enableMultiSelect && selectedRows.length > 0 ? (
        <div className="mb-2 flex items-center gap-2 rounded-md border bg-muted/50 px-3 py-2">
          {selectionToolbar(selectedRows)}
        </div>
      ) : null}
      <div style={{ height, width: "100%" }}>
        <AgGridReact<TData>
          ref={gridRef}
          theme={cellarTheme}
          rowModelType={isInfinite ? "infinite" : undefined}
          datasource={isInfinite ? datasource : undefined}
          rowData={isInfinite ? undefined : (rowData ?? [])}
          columnDefs={finalColumnDefs}
          defaultColDef={defaultColDef}
          onRowClicked={onRowClick ? handleRowClicked : undefined}
          onGridReady={handleGridReady}
          onSelectionChanged={
            trackAcrossBlocks
              ? consumerOnSelectionChanged
              : selectionEnabled
                ? handleSelectionChanged
                : consumerOnSelectionChanged
          }
          onRowSelected={trackAcrossBlocks ? handleRowSelected : consumerOnRowSelected}
          onModelUpdated={trackAcrossBlocks ? handleModelUpdated : consumerOnModelUpdated}
          rowSelection={selectionEnabled ? "multiple" : undefined}
          suppressRowClickSelection={selectionEnabled ? true : undefined}
          tooltipShowDelay={300}
          onColumnResized={hasPrefs ? prefs.onColumnChanged(gridRef) : undefined}
          onColumnMoved={hasPrefs ? prefs.onColumnChanged(gridRef) : undefined}
          onColumnVisible={hasPrefs ? prefs.onColumnChanged(gridRef) : undefined}
          rowClass={onRowClick ? "cursor-pointer" : undefined}
          quickFilterText={isInfinite ? undefined : quickFilter || undefined}
          suppressCellFocus
          animateRows={false}
          {...restWithoutSelection}
        />
      </div>
    </div>
  );
}
