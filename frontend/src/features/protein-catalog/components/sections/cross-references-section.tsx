import {
  AlignLeft,
  BarChart3,
  Box,
  Database,
  Dna,
  GitBranch,
  type LucideIcon,
  Network,
  Waypoints,
  Workflow,
} from "lucide-react";

import { Card, CardContent } from "@/shared/components/ui/card";
import { cn } from "@/shared/lib/utils";

import type { Protein } from "../../types";

type Xref = Protein["cross_references"][number];

const CATEGORIES = [
  "Structure",
  "Sequences",
  "Genome annotation",
  "Family & Domains",
  "Function & Pathways",
  "Interaction",
  "Proteomics",
  "Phylogenomics",
  "Other",
] as const;
type Category = (typeof CATEGORIES)[number];

const CATEGORY_ICON: Record<Category, LucideIcon> = {
  Structure: Box,
  Sequences: AlignLeft,
  "Genome annotation": Dna,
  "Family & Domains": Network,
  "Function & Pathways": Workflow,
  Interaction: Waypoints,
  Proteomics: BarChart3,
  Phylogenomics: GitBranch,
  Other: Database,
};

// UniProt cross-reference databases → display category (keyed uppercase).
const DB_CATEGORY: Record<string, Category> = {
  PDB: "Structure",
  PDBSUM: "Structure",
  ALPHAFOLDDB: "Structure",
  EMDB: "Structure",
  SMR: "Structure",
  BMRB: "Structure",
  PCDDB: "Structure",
  SASBDB: "Structure",
  EMBL: "Sequences",
  REFSEQ: "Sequences",
  CCDS: "Sequences",
  PIR: "Sequences",
  GENBANK: "Sequences",
  ENSEMBLBACTERIA: "Genome annotation",
  ENSEMBL: "Genome annotation",
  GENEID: "Genome annotation",
  KEGG: "Genome annotation",
  PATRIC: "Genome annotation",
  VEUPATHDB: "Genome annotation",
  INTERPRO: "Family & Domains",
  PFAM: "Family & Domains",
  PANTHER: "Family & Domains",
  GENE3D: "Family & Domains",
  PIRSF: "Family & Domains",
  SUPFAM: "Family & Domains",
  PROSITE: "Family & Domains",
  SMART: "Family & Domains",
  CDD: "Family & Domains",
  HAMAP: "Family & Domains",
  NCBIFAM: "Family & Domains",
  TIGRFAMS: "Family & Domains",
  PRINTS: "Family & Domains",
  ANTIFAM: "Family & Domains",
  SFLD: "Family & Domains",
  GO: "Function & Pathways",
  REACTOME: "Function & Pathways",
  BIOCYC: "Function & Pathways",
  BRENDA: "Function & Pathways",
  UNIPATHWAY: "Function & Pathways",
  STRING: "Interaction",
  INTACT: "Interaction",
  DIP: "Interaction",
  MINT: "Interaction",
  BIOGRID: "Interaction",
  COMPLEXPORTAL: "Interaction",
  PAXDB: "Proteomics",
  PRIDE: "Proteomics",
  PROTEOMICSDB: "Proteomics",
  JPOST: "Proteomics",
  MASSIVE: "Proteomics",
  BGEE: "Proteomics",
  ORTHODB: "Phylogenomics",
  EGGNOG: "Phylogenomics",
  HOGENOM: "Phylogenomics",
  INPARANOID: "Phylogenomics",
  OMA: "Phylogenomics",
  PHYLOMEDB: "Phylogenomics",
  TREEFAM: "Phylogenomics",
  GENETREE: "Phylogenomics",
};

// External-resource URL templates (keyed uppercase), used when the backend didn't
// supply a url. Only databases with a verified or standard pattern are included;
// others render as plain text rather than risk a broken link.
const DB_URL: Record<string, (a: string) => string> = {
  PDB: (a) => `https://www.rcsb.org/structure/${a}`,
  PDBSUM: (a) => `https://www.ebi.ac.uk/pdbsum/${a.toLowerCase()}`,
  ALPHAFOLDDB: (a) => `https://alphafold.ebi.ac.uk/entry/${a}`,
  EMDB: (a) => `https://www.ebi.ac.uk/emdb/${a}`,
  SMR: (a) => `https://swissmodel.expasy.org/repository/uniprot/${a}`,
  EMBL: (a) => `https://www.ebi.ac.uk/ena/browser/view/${a}`,
  REFSEQ: (a) => `https://www.ncbi.nlm.nih.gov/protein/${a}`,
  CCDS: (a) => `https://www.ncbi.nlm.nih.gov/CCDS/CcdsBrowse.cgi?REQUEST=CCDS&DATA=${a}`,
  ENSEMBLBACTERIA: (a) => `https://bacteria.ensembl.org/id/${a}`,
  ENSEMBL: (a) => `https://www.ensembl.org/id/${a}`,
  GENEID: (a) => `https://www.ncbi.nlm.nih.gov/gene/${a}`,
  KEGG: (a) => `https://www.kegg.jp/entry/${a}`,
  INTERPRO: (a) => `https://www.ebi.ac.uk/interpro/entry/InterPro/${a}/`,
  PFAM: (a) => `https://www.ebi.ac.uk/interpro/entry/pfam/${a}/`,
  PANTHER: (a) => `https://www.pantherdb.org/panther/family.do?clsAccession=${a}`,
  GENE3D: (a) => `https://www.cathdb.info/version/latest/superfamily/${a.replace(/^G3DSA:/, "")}`,
  PROSITE: (a) => `https://prosite.expasy.org/${a}`,
  HAMAP: (a) => `https://hamap.expasy.org/signature/${a}`,
  CDD: (a) => `https://www.ncbi.nlm.nih.gov/Structure/cdd/cddsrv.cgi?uid=${a}`,
  GO: (a) => `https://www.ebi.ac.uk/QuickGO/term/${a}`,
  REACTOME: (a) => `https://reactome.org/content/detail/${a}`,
  BIOCYC: (a) => `https://biocyc.org/getid?id=${a}`,
  STRING: (a) => `https://string-db.org/network/${a}`,
  INTACT: (a) => `https://www.ebi.ac.uk/intact/search?query=${a}`,
  PAXDB: (a) => `https://pax-db.org/search?q=${a}`,
  PRIDE: (a) => `https://www.ebi.ac.uk/pride/archive/projects/${a}`,
  ORTHODB: (a) => `https://www.orthodb.org/?query=${a}`,
};

function resolveXrefUrl(xref: Xref): string | undefined {
  if (xref.url) return xref.url;
  const builder = DB_URL[xref.database.toUpperCase()];
  return builder ? builder(xref.accession) : undefined;
}

interface CategoryGroup {
  category: Category;
  Icon: LucideIcon;
  count: number;
  databases: { db: string; refs: Xref[] }[];
}

function categorize(xrefs: Xref[]): CategoryGroup[] {
  const byCategory = new Map<Category, Map<string, Xref[]>>();
  for (const x of xrefs) {
    const category = DB_CATEGORY[x.database.toUpperCase()] ?? "Other";
    const dbMap = byCategory.get(category) ?? new Map<string, Xref[]>();
    const refs = dbMap.get(x.database) ?? [];
    refs.push(x);
    dbMap.set(x.database, refs);
    byCategory.set(category, dbMap);
  }
  const out: CategoryGroup[] = [];
  for (const category of CATEGORIES) {
    const dbMap = byCategory.get(category);
    if (!dbMap) continue;
    const databases = Array.from(dbMap.entries()).map(([db, refs]) => ({ db, refs }));
    out.push({
      category,
      Icon: CATEGORY_ICON[category],
      count: databases.reduce((n, d) => n + d.refs.length, 0),
      databases,
    });
  }
  return out;
}

function XrefChip({ xref }: { xref: Xref }) {
  const href = resolveXrefUrl(xref);
  const base =
    "inline-flex items-center rounded-md border px-1.5 py-0.5 font-mono text-[11px] transition-colors";
  if (href) {
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className={cn(
          base,
          "border-border text-primary hover:bg-accent hover:text-accent-foreground",
        )}
      >
        {xref.accession}
      </a>
    );
  }
  return (
    <span className={cn(base, "border-border/60 text-muted-foreground")}>{xref.accession}</span>
  );
}

export function CrossReferencesSection({ protein }: { protein: Protein }) {
  const xrefs = protein.cross_references ?? [];
  if (xrefs.length === 0) return null;
  const groups = categorize(xrefs);

  return (
    <section aria-labelledby="xrefs-heading">
      <h2 id="xrefs-heading" className="mb-3 text-base font-semibold text-foreground">
        Cross-References
      </h2>
      <Card>
        <CardContent className="gap-10 pt-5 md:columns-2">
          {groups.map(({ category, Icon, count, databases }) => (
            <div key={category} className="mb-6 flex break-inside-avoid flex-col gap-2 last:mb-0">
              <div className="flex items-center gap-1.5 border-b border-border/60 pb-1">
                <Icon className="h-3.5 w-3.5 shrink-0 text-primary" aria-hidden="true" />
                <h3 className="text-xs font-semibold uppercase tracking-wide text-foreground">
                  {category}
                </h3>
                <span className="text-[11px] text-muted-foreground">{count}</span>
              </div>
              {databases.map(({ db, refs }) => (
                <div
                  key={db}
                  className="flex flex-col gap-1 sm:grid sm:grid-cols-[7rem_1fr] sm:gap-2"
                >
                  <span className="pt-0.5 text-xs font-medium text-muted-foreground">{db}</span>
                  <div className="flex flex-wrap gap-1">
                    {refs.map((ref) => (
                      <XrefChip key={`${ref.database}-${ref.accession}`} xref={ref} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ))}
        </CardContent>
      </Card>
    </section>
  );
}
