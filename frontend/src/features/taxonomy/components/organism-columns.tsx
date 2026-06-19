import { Badge } from "@/shared/components/ui/badge";
import type { ColDef, ICellRendererParams } from "ag-grid-community";
import Link from "next/link";
import { organismCommonName } from "../lib/organism-format";
import type { Organism } from "../types";
import { ORGANISM_SOURCE_LABELS } from "../types";

function ScientificNameCell({ data, value }: ICellRendererParams<Organism, string>) {
  if (!value || !data) return <span>—</span>;
  return (
    <Link
      href={`/organisms/${data.id}`}
      className="font-medium text-primary underline-offset-2 hover:underline"
      onClick={(e) => e.stopPropagation()}
    >
      {value}
    </Link>
  );
}

function RankCell({ value }: ICellRendererParams<Organism, string>) {
  if (!value) return <span className="text-muted-foreground">—</span>;
  return <Badge variant="secondary">{value}</Badge>;
}

function NcbiTaxIdCell({ data, value }: ICellRendererParams<Organism, number>) {
  if (value == null) return <span className="text-muted-foreground">—</span>;
  if (data?.ncbi_url) {
    return (
      <a
        href={String(data.ncbi_url)}
        target="_blank"
        rel="noopener noreferrer"
        className="font-mono text-xs text-primary underline-offset-2 hover:underline"
        onClick={(e) => e.stopPropagation()}
      >
        {String(value)}
      </a>
    );
  }
  return <span className="font-mono text-xs">{String(value)}</span>;
}

function CommonNameCell({ data }: ICellRendererParams<Organism>) {
  if (!data?.names) return <span className="text-muted-foreground">—</span>;
  const common = organismCommonName(data.names);
  if (!common) return <span className="text-muted-foreground">—</span>;
  return <span>{common}</span>;
}

function SourceCell({ data }: ICellRendererParams<Organism>) {
  if (!data?.source) return <span className="text-muted-foreground">—</span>;
  return <Badge variant="outline">{ORGANISM_SOURCE_LABELS[data.source]}</Badge>;
}

export const organismColumnDefs: ColDef<Organism>[] = [
  {
    headerName: "Scientific Name",
    field: "scientific_name",
    flex: 1,
    minWidth: 200,
    cellRenderer: ScientificNameCell,
  },
  {
    headerName: "Rank",
    field: "rank",
    width: 130,
    cellRenderer: RankCell,
    sortable: false,
  },
  {
    headerName: "NCBI Tax ID",
    field: "ncbi_tax_id",
    width: 130,
    cellRenderer: NcbiTaxIdCell,
    sortable: false,
  },
  {
    headerName: "Common Name",
    field: "names",
    width: 180,
    cellRenderer: CommonNameCell,
    sortable: false,
  },
  {
    headerName: "Source",
    field: "source",
    width: 110,
    cellRenderer: SourceCell,
    sortable: false,
  },
];
