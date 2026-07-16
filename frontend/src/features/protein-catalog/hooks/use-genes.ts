import {
  useGetGeneApiV1GenesGeneIdGet,
  useGetGeneNeighborhoodApiV1GenesGeneIdNeighborhoodGet,
  useListGenesApiV1GenesGet,
} from "@/shared/lib/api/genes/genes";

import type { GeneListFilters } from "../types";

/** List genes with optional filters and cursor-based pagination. */
export function useGenes(filters: GeneListFilters = {}, cursor?: string) {
  return useListGenesApiV1GenesGet({
    name: filters.name ?? undefined,
    organism_id: filters.organismId ?? undefined,
    strain_id: filters.strainId ?? undefined,
    cursor: cursor ?? undefined,
  });
}

/** Fetch a single gene by ID. */
export function useGene(id: string) {
  return useGetGeneApiV1GenesGeneIdGet(id);
}

/**
 * Fetch a gene's genomic neighborhood (genes flanking it on the same replicon).
 * `window` is the number of genes to pull on each side (default 8, matching the API).
 */
export function useGeneNeighborhood(geneId: string, window = 8) {
  return useGetGeneNeighborhoodApiV1GenesGeneIdNeighborhoodGet(geneId, { window });
}
