import type {
  CrossReferenceResponse,
  GeneResponse,
  ProteinListItemResponse,
  ProteinResponse,
} from "@/shared/lib/api/model";

/**
 * Re-narrowed protein type: `protein_names` is typed with known fields
 * instead of the generated `{ [key: string]: unknown }` catch-all.
 */
export type Protein = Omit<ProteinResponse, "protein_names"> & {
  protein_names: {
    recommended?: string | null;
    alternative?: string[];
    submitted?: string[];
    short_names?: string[];
    ec_numbers?: string[];
  };
};

/**
 * Cast a raw ProteinResponse to our narrowed Protein type.
 * The generated `protein_names` and `cross_references` fields are typed
 * loosely by the codegen; we perform one typed boundary cast here so
 * callers don't need scattered `as unknown as Protein` casts.
 */
export function toProtein(r: ProteinResponse): Protein {
  return r as unknown as Protein;
}

/**
 * A row in the protein catalog list — the slim, decision-oriented projection
 * returned by `GET /api/v1/proteins` (gene summary + derived structure/chem flags).
 * Already well-typed by the generated DTO; no narrowing needed.
 */
export type ProteinListItem = ProteinListItemResponse;

/** Gene (alias of generated DTO — no narrowing needed). */
export type Gene = GeneResponse;

/** Cross-reference (alias of generated DTO). */
export type CrossRef = CrossReferenceResponse;

/** Filter parameters for listing proteins. */
export interface ProteinListFilters {
  reviewed?: boolean;
  minLength?: number;
  maxLength?: number;
  organismId?: string;
  geneId?: string;
  /** Free-text query across accession, entry name, protein name, gene name + synonyms. */
  search?: string;
  /** Only proteins with a 3D structure (PDB / AlphaFold / …). */
  hasStructure?: boolean;
  /** Only enzymes (proteins carrying an EC number). */
  isEnzyme?: boolean;
  /** Only proteins with chemical matter in ChEMBL. */
  hasChembl?: boolean;
}

/** Filter parameters for listing genes. */
export interface GeneListFilters {
  name?: string;
  organismId?: string;
}
