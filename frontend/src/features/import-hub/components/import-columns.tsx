import type { ColDef, ICellRendererParams } from "ag-grid-community";
import Link from "next/link";

import { Badge } from "@/shared/components/ui/badge";

import { IMPORT_TYPE_LABELS, type ImportRun, STATUS_VARIANTS } from "../types";

function TargetCell({ data, value }: ICellRendererParams<ImportRun, string>) {
  if (!data) return <span>—</span>;
  return (
    <Link
      href={`/admin/imports/${data.id}`}
      className="font-medium text-primary underline-offset-2 hover:underline"
      onClick={(e) => e.stopPropagation()}
    >
      {value || "—"}
    </Link>
  );
}

function TypeCell({ data }: ICellRendererParams<ImportRun>) {
  if (!data) return <span>—</span>;
  return <Badge variant="secondary">{IMPORT_TYPE_LABELS[data.import_type]}</Badge>;
}

function StatusCell({ data }: ICellRendererParams<ImportRun>) {
  if (!data) return <span>—</span>;
  return <Badge variant={STATUS_VARIANTS[data.status]}>{data.status}</Badge>;
}

function DateCell({ value }: ICellRendererParams<ImportRun, string | null>) {
  if (!value) return <span className="text-muted-foreground">—</span>;
  return <span>{new Date(value).toLocaleString()}</span>;
}

export const importColumnDefs: ColDef<ImportRun>[] = [
  { headerName: "Target", field: "target_key", flex: 1, minWidth: 200, cellRenderer: TargetCell },
  { headerName: "Type", field: "import_type", width: 170, cellRenderer: TypeCell, sortable: false },
  { headerName: "Status", field: "status", width: 130, cellRenderer: StatusCell, sortable: false },
  { headerName: "Created", field: "created_at", width: 190, cellRenderer: DateCell },
  { headerName: "Finished", field: "finished_at", width: 190, cellRenderer: DateCell },
];
