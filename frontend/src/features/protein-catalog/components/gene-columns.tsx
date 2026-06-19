import { Badge } from "@/shared/components/ui/badge";
import type { ColDef, ICellRendererParams } from "ag-grid-community";
import Link from "next/link";
import type { Gene } from "../types";

function PrimaryNameCell({ data, value }: ICellRendererParams<Gene, string>) {
  if (!value || !data) return <span>—</span>;
  return (
    <Link
      href={`/genes/${data.id}`}
      className="font-medium text-primary underline-offset-2 hover:underline"
      onClick={(e) => e.stopPropagation()}
    >
      {value}
    </Link>
  );
}

function SynonymsCell({ data }: ICellRendererParams<Gene>) {
  if (!data?.synonyms?.length) return <span className="text-muted-foreground">—</span>;
  return <span className="text-sm">{data.synonyms.join(", ")}</span>;
}

function OrganismCell({ data }: ICellRendererParams<Gene>) {
  if (!data?.organism_id) return <span className="text-muted-foreground">—</span>;
  // Plan 3 will resolve organism_id → display name
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

function NcbiCell({ data }: ICellRendererParams<Gene>) {
  if (!data?.ncbi_gene_id) return <span className="text-muted-foreground">—</span>;
  if (data.ncbi_gene_url) {
    return (
      <a
        href={String(data.ncbi_gene_url)}
        target="_blank"
        rel="noreferrer"
        className="font-mono text-xs text-primary underline-offset-2 hover:underline"
        onClick={(e) => e.stopPropagation()}
      >
        {String(data.ncbi_gene_id)}
      </a>
    );
  }
  return (
    <Badge variant="outline" className="text-xs font-mono">
      {String(data.ncbi_gene_id)}
    </Badge>
  );
}

function EnsemblCell({ data }: ICellRendererParams<Gene>) {
  if (!data?.ensembl_gene_id) return <span className="text-muted-foreground">—</span>;
  if (data.ensembl_url) {
    return (
      <a
        href={String(data.ensembl_url)}
        target="_blank"
        rel="noreferrer"
        className="font-mono text-xs text-primary underline-offset-2 hover:underline"
        onClick={(e) => e.stopPropagation()}
      >
        {String(data.ensembl_gene_id)}
      </a>
    );
  }
  return (
    <Badge variant="outline" className="text-xs font-mono">
      {String(data.ensembl_gene_id)}
    </Badge>
  );
}

function HgncCell({ data }: ICellRendererParams<Gene>) {
  if (!data?.hgnc_id) return <span className="text-muted-foreground">—</span>;
  return (
    <Badge variant="outline" className="text-xs font-mono">
      {String(data.hgnc_id)}
    </Badge>
  );
}

export const geneColumnDefs: ColDef<Gene>[] = [
  {
    headerName: "Gene Name",
    field: "primary_name",
    width: 140,
    cellRenderer: PrimaryNameCell,
  },
  {
    headerName: "Synonyms",
    field: "synonyms",
    flex: 1,
    minWidth: 180,
    cellRenderer: SynonymsCell,
    sortable: false,
  },
  {
    headerName: "Organism",
    field: "organism_id",
    width: 150,
    cellRenderer: OrganismCell,
    sortable: false,
  },
  {
    headerName: "NCBI Gene",
    field: "ncbi_gene_id",
    width: 130,
    cellRenderer: NcbiCell,
    sortable: false,
  },
  {
    headerName: "Ensembl",
    field: "ensembl_gene_id",
    width: 160,
    cellRenderer: EnsemblCell,
    sortable: false,
  },
  {
    headerName: "HGNC",
    field: "hgnc_id",
    width: 110,
    cellRenderer: HgncCell,
    sortable: false,
  },
];
