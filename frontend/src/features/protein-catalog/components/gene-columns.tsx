import { OrganismRef } from "@/shared/components/common/organism-ref";
import { Badge } from "@/shared/components/ui/badge";
import type { ColDef, ICellRendererParams } from "ag-grid-community";
import Link from "next/link";
import { secondaryNames } from "../lib/gene-label";
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
  if (!data) return <span className="text-muted-foreground">—</span>;
  // Gene lead is display_label (the locus/ORF); show symbol + remaining ids beneath it.
  const rest = secondaryNames(
    [
      data.primary_name,
      ...(data.ordered_locus_names ?? []),
      ...(data.orf_names ?? []),
      ...(data.synonyms ?? []),
    ],
    data.display_label,
  );
  if (rest.length === 0) return <span className="text-muted-foreground">—</span>;
  return <span className="text-sm">{rest.join(", ")}</span>;
}

function OrganismCell({ data }: ICellRendererParams<Gene>) {
  if (!data?.organism_id) return <span className="text-muted-foreground">—</span>;
  return <OrganismRef id={data.organism_id} className="text-xs" />;
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
    field: "display_label",
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
