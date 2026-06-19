import type { ColDef, ICellRendererParams } from "ag-grid-community";
import Link from "next/link";

import { Badge } from "@/shared/components/ui/badge";
import { ORG_TYPE_LABELS, type Organization } from "../types";

function NameCell({ data, value }: ICellRendererParams<Organization, string>) {
  if (!data || !value) return <span>—</span>;
  return (
    <Link
      href={`/admin/organizations/${data.id}`}
      className="font-medium text-primary underline-offset-2 hover:underline"
      onClick={(e) => e.stopPropagation()}
    >
      {value}
    </Link>
  );
}

function TypeCell({ data }: ICellRendererParams<Organization>) {
  if (!data) return <span>—</span>;
  return <Badge variant="secondary">{ORG_TYPE_LABELS[data.org_type]}</Badge>;
}

function TextCell({ value }: ICellRendererParams<Organization, string | null>) {
  if (!value) return <span>—</span>;
  return <span>{value}</span>;
}

function StatusCell({ data }: ICellRendererParams<Organization>) {
  if (!data) return <span>—</span>;
  return (
    <Badge variant={data.is_active ? "default" : "secondary"}>
      {data.is_active ? "Active" : "Inactive"}
    </Badge>
  );
}

export const organizationColumnDefs: ColDef<Organization>[] = [
  { headerName: "Name", field: "name", flex: 1, minWidth: 220, cellRenderer: NameCell },
  { headerName: "Type", field: "org_type", width: 160, cellRenderer: TypeCell, sortable: false },
  {
    headerName: "Contact",
    field: "contact_name",
    width: 180,
    cellRenderer: TextCell,
    sortable: false,
  },
  {
    headerName: "Email",
    field: "contact_email",
    width: 220,
    cellRenderer: TextCell,
    sortable: false,
  },
  {
    headerName: "Status",
    field: "is_active",
    width: 120,
    cellRenderer: StatusCell,
    sortable: false,
  },
];
