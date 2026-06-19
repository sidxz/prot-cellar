import type { CrossReferenceResponse, GeneResponse, ProteinResponse } from "@/shared/lib/api/model";

/**
 * Re-narrowed protein type: `protein_names` is typed with known fields
 * instead of the generated `{ [key: string]: unknown }` catch-all.
 */
export type Protein = Omit<ProteinResponse, "protein_names"> & {
  protein_names: {
    recommended?: string | null;
    alternative?: string[];
    submitted?: string[];
  };
};

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
}

/** Filter parameters for listing genes. */
export interface GeneListFilters {
  name?: string;
  organismId?: string;
}
