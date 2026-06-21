import { OrganismRef } from "@/shared/components/common/organism-ref";
import type { ColDef, ICellRendererParams } from "ag-grid-community";
import Link from "next/link";
import type { Strain } from "../types";

function NameCell({ data, value }: ICellRendererParams<Strain, string>) {
  if (!data || !value) return <span>—</span>;
  return (
    <Link
      href={`/strains/${data.id}`}
      className="font-medium text-primary underline-offset-2 hover:underline"
      onClick={(e) => e.stopPropagation()}
    >
      {value}
    </Link>
  );
}

function SpeciesOrganismCell({ data }: ICellRendererParams<Strain>) {
  if (!data?.species_organism_id) return <span>—</span>;
  return <OrganismRef id={data.species_organism_id} />;
}

function NcbiTaxonCell({ data }: ICellRendererParams<Strain>) {
  if (data?.ncbi_taxon_id == null) return <span>—</span>;
  return (
    <a
      href={`https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=${data.ncbi_taxon_id}`}
      target="_blank"
      rel="noopener noreferrer"
      className="font-mono text-xs text-primary hover:underline underline-offset-2"
      onClick={(e) => e.stopPropagation()}
    >
      {data.ncbi_taxon_id}
    </a>
  );
}

function TextCell({ value }: ICellRendererParams<Strain, string>) {
  if (!value) return <span>—</span>;
  return <span className="font-mono text-xs">{value}</span>;
}

export const strainColumnDefs: ColDef<Strain>[] = [
  {
    headerName: "Name",
    field: "name",
    flex: 1,
    minWidth: 200,
    cellRenderer: NameCell,
  },
  {
    headerName: "Species Organism",
    field: "species_organism_id",
    width: 200,
    cellRenderer: SpeciesOrganismCell,
    sortable: false,
  },
  {
    headerName: "NCBI Taxon",
    field: "ncbi_taxon_id",
    width: 140,
    cellRenderer: NcbiTaxonCell,
    sortable: false,
  },
  {
    headerName: "BioSample",
    field: "biosample_acc",
    width: 140,
    cellRenderer: TextCell,
    sortable: false,
  },
  {
    headerName: "Assembly",
    field: "assembly_acc",
    width: 160,
    cellRenderer: TextCell,
    sortable: false,
  },
  {
    headerName: "Culture Collection",
    field: "culture_collection",
    width: 160,
    cellRenderer: TextCell,
    sortable: false,
  },
];
