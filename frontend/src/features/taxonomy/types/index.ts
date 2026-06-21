import type {
  NameClass,
  OrganismNameResponse,
  OrganismResponse,
  OrganismSource,
  ProteomeResponse,
  ProteomeType,
  StrainResponse,
} from "@/shared/lib/api/model";

/** Narrowed alias — organism (no narrowing needed beyond the generated type). */
export type Organism = OrganismResponse;

/** Narrowed alias — organism name entry. */
export type OrganismName = OrganismNameResponse;

/** Narrowed alias — strain. */
export type Strain = StrainResponse;

/** Narrowed alias — proteome. */
export type Proteome = ProteomeResponse;

// ─── Label maps ──────────────────────────────────────────────────────────────

/** Human-readable labels for all 9 name_class values. */
export const NAME_CLASS_LABELS: Record<NameClass, string> = {
  scientific_name: "Scientific name",
  common_name: "Common name",
  genbank_common_name: "GenBank common name",
  synonym: "Synonym",
  authority: "Authority",
  equivalent_name: "Equivalent name",
  acronym: "Acronym",
  blast_name: "BLAST name",
  uniprot_mnemonic: "UniProt mnemonic",
};

/** Human-readable labels for the 3 organism source values. */
export const ORGANISM_SOURCE_LABELS: Record<OrganismSource, string> = {
  ncbi: "NCBI",
  gtdb: "GTDB",
  local: "Local",
};

/** Human-readable labels for the 4 proteome type values. */
export const PROTEOME_TYPE_LABELS: Record<ProteomeType, string> = {
  reference: "Reference",
  representative: "Representative",
  redundant: "Redundant",
  excluded: "Excluded",
};

// ─── Filter types ─────────────────────────────────────────────────────────────

/** Filter parameters for listing organisms. */
export interface OrganismListFilters {
  name?: string;
  rank?: string;
}

/** Filter parameters for listing proteomes. */
export interface ProteomeListFilters {
  organismId?: string;
}

// ─── Form value types ─────────────────────────────────────────────────────────

/** Form values for creating or editing a strain. */
export interface StrainFormValues {
  name: string;
  species_organism_id: string;
  ncbi_taxon_id?: number | null;
  isolate?: string | null;
  biosample_acc?: string | null;
  assembly_acc?: string | null;
  culture_collection?: string | null;
  host_organism_id?: string | null;
}
