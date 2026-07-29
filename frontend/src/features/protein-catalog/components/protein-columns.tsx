import { StrainRef } from "@/shared/components/common/strain-ref";
import { Badge } from "@/shared/components/ui/badge";
import { cn } from "@/shared/lib/utils";
import type { ColDef, ICellRendererParams } from "ag-grid-community";
import Link from "next/link";
import { secondaryNames } from "../lib/gene-label";
import type { ProteinListItem } from "../types";

// Row height needed to comfortably fit the three-line identity cell.
export const PROTEIN_ROW_HEIGHT = 74;

const stop = (e: React.MouseEvent) => e.stopPropagation();

/**
 * Identity cell — collapses the old Accession / Entry Name / Recommended Name /
 * Gene / Short Name columns into one scannable stack:
 *   line 1  gene name (bold, linked) + synonyms / locus tags
 *   line 2  recommended protein name
 *   line 3  accession (mono, linked) + entry name
 */
function IdentityCell({ data }: ICellRendererParams<ProteinListItem>) {
  if (!data) return <span className="text-muted-foreground">—</span>;
  const gene = data.gene;
  // Protein lead stays the symbol (primary_name); show loci + synonyms beneath it,
  // so the locus survives now that it's a distinct field (no longer in synonyms).
  const synonyms = gene
    ? secondaryNames(
        [...(gene.ordered_locus_names ?? []), ...(gene.synonyms ?? [])],
        gene.primary_name,
      )
    : [];
  return (
    <div className="flex flex-col justify-center gap-0.5 py-1.5 leading-tight">
      <div className="flex items-baseline gap-1.5 truncate">
        {gene ? (
          <Link
            href={`/genes/${gene.id}`}
            onClick={stop}
            className="font-semibold text-foreground underline-offset-2 hover:text-primary hover:underline"
            title={gene.primary_name}
          >
            {gene.primary_name}
          </Link>
        ) : (
          <span className="font-semibold text-muted-foreground">—</span>
        )}
        {synonyms.length > 0 && (
          <span className="truncate text-xs text-muted-foreground" title={synonyms.join(", ")}>
            {synonyms.join(", ")}
          </span>
        )}
      </div>
      <span
        className={cn(
          "truncate text-sm",
          data.recommended_name ? "text-foreground/90" : "text-muted-foreground italic",
        )}
        title={data.recommended_name ?? undefined}
      >
        {data.recommended_name ?? "Uncharacterized protein"}
      </span>
      <div className="flex items-center gap-2 truncate text-xs">
        <Link
          href={`/proteins/${data.primary_accession}`}
          onClick={stop}
          className="font-mono text-primary underline-offset-2 hover:underline"
        >
          {data.primary_accession}
        </Link>
        {data.entry_name && (
          <span className="truncate text-muted-foreground">{data.entry_name}</span>
        )}
      </div>
    </div>
  );
}

/** Source strain — links to the strain record; em dash when a protein has none. */
function StrainCell({ data }: ICellRendererParams<ProteinListItem>) {
  return <StrainRef id={data?.strain_id} className="text-sm" />;
}

/** EC numbers — the enzyme-class signal. Shows up to two, then "+N". */
function EcCell({ data }: ICellRendererParams<ProteinListItem>) {
  const ecs = data?.ec_numbers ?? [];
  if (ecs.length === 0) return <span className="text-muted-foreground">—</span>;
  return (
    <div className="flex flex-wrap items-center gap-1">
      {ecs.slice(0, 2).map((ec) => (
        <Badge
          key={ec}
          variant="outline"
          className="border-amber-500/25 bg-amber-500/10 font-mono text-[10px] text-amber-700 dark:text-amber-400"
        >
          {ec}
        </Badge>
      ))}
      {ecs.length > 2 && <span className="text-xs text-muted-foreground">+{ecs.length - 2}</span>}
    </div>
  );
}

/** 3D-structure availability — experimental (PDB) outranks predicted (AlphaFold). */
function StructureCell({ data }: ICellRendererParams<ProteinListItem>) {
  const s = data?.structure;
  if (s && s.pdb_count > 0) {
    return (
      <Badge className="border-blue-500/25 bg-blue-500/12 text-blue-700 dark:text-blue-400">
        PDB{s.pdb_count > 1 ? `·${s.pdb_count}` : ""}
      </Badge>
    );
  }
  if (s?.has_alphafold) {
    return (
      <Badge
        variant="outline"
        className="border-blue-500/20 text-blue-600/80 dark:text-blue-400/80"
      >
        AlphaFold
      </Badge>
    );
  }
  return <span className="text-muted-foreground">—</span>;
}

/** Chemical matter — known ligands / bioactivity, the SAR starting points. */
function ChemCell({ data }: ICellRendererParams<ProteinListItem>) {
  const chem = data?.chem;
  if (chem?.has_chembl) {
    return (
      <Badge className="border-violet-500/25 bg-violet-500/12 text-violet-700 dark:text-violet-400">
        ChEMBL
      </Badge>
    );
  }
  if (chem?.has_drugbank) {
    return (
      <Badge className="border-violet-500/25 bg-violet-500/12 text-violet-700 dark:text-violet-400">
        DrugBank
      </Badge>
    );
  }
  return <span className="text-muted-foreground">—</span>;
}

/** Compact reviewed/quality badge. */
function DbCell({ data }: ICellRendererParams<ProteinListItem>) {
  if (!data) return <span>—</span>;
  return data.is_reviewed ? (
    <Badge variant="success" className="text-[10px]">
      Swiss-Prot
    </Badge>
  ) : (
    <Badge variant="outline" className="text-[10px] text-muted-foreground">
      TrEMBL
    </Badge>
  );
}

export const proteinColumnDefs: ColDef<ProteinListItem>[] = [
  {
    headerName: "Protein / Gene",
    colId: "identity",
    flex: 1,
    minWidth: 300,
    cellRenderer: IdentityCell,
    sortable: false,
  },
  {
    headerName: "Strain",
    colId: "strain",
    width: 180,
    cellRenderer: StrainCell,
    sortable: false,
  },
  {
    headerName: "EC / Class",
    colId: "ec",
    width: 140,
    cellRenderer: EcCell,
    sortable: false,
  },
  {
    headerName: "Structure",
    colId: "structure",
    width: 120,
    cellRenderer: StructureCell,
    sortable: false,
  },
  {
    headerName: "Chem",
    colId: "chem",
    width: 110,
    cellRenderer: ChemCell,
    sortable: false,
  },
  {
    headerName: "Length",
    field: "seq_length",
    width: 100,
    type: "numericColumn",
    valueFormatter: (p) => (p.value != null ? p.value.toLocaleString() : "—"),
  },
  {
    headerName: "Database",
    colId: "database",
    width: 120,
    cellRenderer: DbCell,
    sortable: false,
  },
];
