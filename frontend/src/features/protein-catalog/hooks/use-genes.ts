import {
  useGetGeneApiV1GenesGeneIdGet,
  useListGenesApiV1GenesGet,
} from "@/shared/lib/api/genes/genes";

import type { GeneListFilters } from "../types";

/** List genes with optional filters and cursor-based pagination. */
export function useGenes(filters: GeneListFilters = {}, cursor?: string) {
  return useListGenesApiV1GenesGet({
    name: filters.name ?? undefined,
    organism_id: filters.organismId ?? undefined,
    cursor: cursor ?? undefined,
  });
}

/** Fetch a single gene by ID. */
export function useGene(id: string) {
  return useGetGeneApiV1GenesGeneIdGet(id);
}
