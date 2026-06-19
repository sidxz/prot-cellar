import { OrganismRef } from "@/shared/components/common/organism-ref";
import { Badge } from "@/shared/components/ui/badge";
import type { ColDef, ICellRendererParams } from "ag-grid-community";
import Link from "next/link";
import type { Proteome } from "../types";
import { PROTEOME_TYPE_LABELS } from "../types";

function UniprotIdCell({ data, value }: ICellRendererParams<Proteome, string>) {
  if (!value || !data) return <span>—</span>;
  return (
    <span className="inline-flex items-center gap-1.5">
      <Link
        href={`/proteomes/${data.id}`}
        className="font-medium text-primary underline-offset-2 hover:underline font-mono text-xs"
        onClick={(e) => e.stopPropagation()}
      >
        {value}
      </Link>
      {data.proteome_url && (
        <a
          href={String(data.proteome_url)}
          target="_blank"
          rel="noopener noreferrer"
          className="text-muted-foreground hover:text-primary transition-colors"
          aria-label={`View ${value} on UniProt`}
          onClick={(e) => e.stopPropagation()}
        >
          ↗
        </a>
      )}
    </span>
  );
}

function OrganismCell({ data }: ICellRendererParams<Proteome>) {
  if (!data?.organism_id) return <span className="text-muted-foreground">—</span>;
  return <OrganismRef id={data.organism_id} />;
}

function ProteomeTypeCell({ value }: ICellRendererParams<Proteome, string>) {
  if (!value) return <span className="text-muted-foreground">—</span>;
  const label = PROTEOME_TYPE_LABELS[value as keyof typeof PROTEOME_TYPE_LABELS] ?? value;
  return <Badge variant="secondary">{label}</Badge>;
}

function IsReferenceCell({ value }: ICellRendererParams<Proteome, boolean>) {
  if (!value) return <span className="text-muted-foreground">—</span>;
  return <Badge variant="outline">Reference</Badge>;
}

function TextCell({ value }: ICellRendererParams<Proteome, string>) {
  if (!value) return <span className="text-muted-foreground">—</span>;
  return <span className="font-mono text-xs">{value}</span>;
}

export const proteomeColumnDefs: ColDef<Proteome>[] = [
  {
    headerName: "UniProt Proteome ID",
    field: "uniprot_proteome_id",
    flex: 1,
    minWidth: 180,
    cellRenderer: UniprotIdCell,
  },
  {
    headerName: "Organism",
    field: "organism_id",
    width: 200,
    cellRenderer: OrganismCell,
    sortable: false,
  },
  {
    headerName: "Type",
    field: "proteome_type",
    width: 150,
    cellRenderer: ProteomeTypeCell,
    sortable: false,
  },
  {
    headerName: "Reference",
    field: "is_reference",
    width: 120,
    cellRenderer: IsReferenceCell,
    sortable: false,
  },
  {
    headerName: "Assembly",
    field: "assembly_acc",
    width: 180,
    cellRenderer: TextCell,
    sortable: false,
  },
];
