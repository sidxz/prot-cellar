import { Badge } from "@/shared/components/ui/badge";
import type { ColDef, ICellRendererParams } from "ag-grid-community";
import Link from "next/link";
import { TARGET_TYPE_LABELS } from "../types";
import type { Target } from "../types";

function PrefNameCell({ data, value }: ICellRendererParams<Target, string>) {
  if (!data || !value) return <span>—</span>;
  return (
    <Link
      href={`/targets/${data.id}`}
      className="font-medium text-primary underline-offset-2 hover:underline"
      onClick={(e) => e.stopPropagation()}
    >
      {value}
    </Link>
  );
}

function TargetTypeCell({ value }: ICellRendererParams<Target, string>) {
  if (!value) return <span>—</span>;
  const label = TARGET_TYPE_LABELS[value as keyof typeof TARGET_TYPE_LABELS] ?? value;
  return (
    <Badge variant="outline" className="text-xs">
      {label}
    </Badge>
  );
}

function ComponentCountCell({ data }: ICellRendererParams<Target>) {
  if (!data) return <span>—</span>;
  const count = data.components?.length ?? 0;
  return <span>{count}</span>;
}

function OrganismCell({ data }: ICellRendererParams<Target>) {
  if (!data?.organism_id) return <span>—</span>;
  // Plan 3: resolve organism_id to organism name
  return (
    <Link
      href={`/organisms/${data.organism_id}`}
      className="rounded bg-muted px-1.5 py-0.5 text-xs font-mono text-foreground hover:bg-muted/80"
      onClick={(e) => e.stopPropagation()}
    >
      {data.organism_id}
    </Link>
  );
}

function ChemblIdCell({ data }: ICellRendererParams<Target>) {
  if (!data?.chembl_id) return <span>—</span>;
  if (data.chembl_url) {
    return (
      <a
        href={data.chembl_url}
        target="_blank"
        rel="noopener noreferrer"
        className="font-mono text-xs text-primary underline-offset-2 hover:underline"
        onClick={(e) => e.stopPropagation()}
      >
        {data.chembl_id}
      </a>
    );
  }
  return <span className="font-mono text-xs">{data.chembl_id}</span>;
}

export const targetColumnDefs: ColDef<Target>[] = [
  {
    headerName: "Preferred Name",
    field: "pref_name",
    flex: 1,
    minWidth: 200,
    cellRenderer: PrefNameCell,
  },
  {
    headerName: "Target Type",
    field: "target_type",
    width: 180,
    cellRenderer: TargetTypeCell,
    sortable: false,
  },
  {
    headerName: "Components",
    field: "components",
    width: 120,
    cellRenderer: ComponentCountCell,
    sortable: false,
  },
  {
    headerName: "Organism",
    field: "organism_id",
    width: 180,
    cellRenderer: OrganismCell,
    sortable: false,
  },
  {
    headerName: "ChEMBL ID",
    field: "chembl_id",
    width: 140,
    cellRenderer: ChemblIdCell,
    sortable: false,
  },
];
