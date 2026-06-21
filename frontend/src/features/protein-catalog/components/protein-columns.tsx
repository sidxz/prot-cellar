import { Badge } from "@/shared/components/ui/badge";
import type { ColDef, ICellRendererParams } from "ag-grid-community";
import Link from "next/link";
import { proteinPrimaryName } from "../lib/protein-format";
import type { Protein } from "../types";

function AccessionCell({ value }: ICellRendererParams<Protein, string>) {
  if (!value) return <span>—</span>;
  return (
    <Link
      href={`/proteins/${value}`}
      className="font-mono text-primary underline-offset-2 hover:underline"
      onClick={(e) => e.stopPropagation()}
    >
      {value}
    </Link>
  );
}

function ReviewedCell({ data }: ICellRendererParams<Protein>) {
  if (!data) return <span>—</span>;
  return data.is_reviewed ? (
    <Badge variant="success" className="text-xs">
      Swiss-Prot
    </Badge>
  ) : (
    <Badge variant="outline" className="text-xs text-muted-foreground">
      TrEMBL
    </Badge>
  );
}

function GeneCell({ data }: ICellRendererParams<Protein>) {
  const gene = data?.gene;
  if (!gene) return <span className="text-muted-foreground">—</span>;
  const synonyms = gene.synonyms?.filter((s) => s !== gene.primary_name) ?? [];
  return (
    <span className="inline-flex items-baseline gap-1.5 truncate">
      <Link
        href={`/genes/${gene.id}`}
        className="font-medium text-primary underline-offset-2 hover:underline"
        onClick={(e) => e.stopPropagation()}
        title={gene.primary_name}
      >
        {gene.primary_name}
      </Link>
      {synonyms.length > 0 && (
        <span className="truncate text-xs text-muted-foreground" title={synonyms.join(", ")}>
          {synonyms.join(", ")}
        </span>
      )}
    </span>
  );
}

function shortNameValue(p: Protein | undefined): string {
  const shorts = p?.protein_names?.short_names;
  return shorts && shorts.length > 0 ? shorts.join(" / ") : "—";
}

function OrganismCell({ data }: ICellRendererParams<Protein>) {
  if (!data?.organism_id) return <span>—</span>;
  // resolves to organism name in Plan 3
  const shortId = data.organism_id.replace(/^taxon:/, "");
  return (
    <Link
      href={`/organisms/${data.organism_id}`}
      className="rounded bg-muted px-1.5 py-0.5 text-xs font-mono text-foreground hover:bg-muted/80"
      onClick={(e) => e.stopPropagation()}
    >
      {shortId}
    </Link>
  );
}

export const proteinColumnDefs: ColDef<Protein>[] = [
  {
    headerName: "Accession",
    field: "primary_accession",
    width: 130,
    cellRenderer: AccessionCell,
  },
  {
    headerName: "Entry Name",
    field: "entry_name",
    width: 160,
    valueFormatter: (p) => p.value ?? "—",
  },
  {
    headerName: "Recommended Name",
    field: "protein_names",
    flex: 1,
    minWidth: 200,
    valueGetter: (p) => (p.data ? proteinPrimaryName(p.data) : "—"),
    sortable: false,
  },
  {
    headerName: "Gene",
    colId: "gene",
    width: 170,
    cellRenderer: GeneCell,
    sortable: false,
  },
  {
    headerName: "Short Name",
    colId: "short_name",
    width: 120,
    valueGetter: (p) => shortNameValue(p.data),
    sortable: false,
  },
  {
    headerName: "Database",
    field: "is_reviewed",
    width: 110,
    cellRenderer: ReviewedCell,
    sortable: false,
  },
  {
    headerName: "Length",
    field: "seq_length",
    width: 90,
    type: "numericColumn",
    valueFormatter: (p) => (p.value != null ? p.value.toLocaleString() : "—"),
  },
  {
    headerName: "Organism",
    field: "organism_id",
    width: 140,
    cellRenderer: OrganismCell,
    sortable: false,
  },
];
