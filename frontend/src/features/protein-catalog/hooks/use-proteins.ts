import { useQuery } from "@tanstack/react-query";

import { parseFasta } from "@/shared/components/sequence/sequence";
import { API_V1, customInstance } from "@/shared/lib/api/custom-instance";
import {
  useGetProteinApiV1ProteinsAccessionGet,
  useListProteinsApiV1ProteinsGet,
  useResolveProteinApiV1ProteinsResolveIdentifierGet,
} from "@/shared/lib/api/proteins/proteins";

import type { Protein, ProteinListFilters } from "../types";
import { toProtein } from "../types";
import { proteinFastaKey } from "./query-keys";

/** List proteins with optional filters and cursor-based pagination. */
export function useProteins(filters: ProteinListFilters = {}, cursor?: string) {
  return useListProteinsApiV1ProteinsGet({
    reviewed: filters.reviewed ?? undefined,
    min_length: filters.minLength ?? undefined,
    max_length: filters.maxLength ?? undefined,
    organism_id: filters.organismId ?? undefined,
    gene_id: filters.geneId ?? undefined,
    cursor: cursor ?? undefined,
  });
}

/**
 * Fetch a single protein by accession.
 * Returns the result narrowed to our typed `Protein` wrapper so callers
 * don't need scattered `as unknown as Protein` casts.
 */
export function useProtein(accession: string) {
  const query = useGetProteinApiV1ProteinsAccessionGet(accession, undefined);
  return {
    ...query,
    data: query.data != null ? toProtein(query.data as Parameters<typeof toProtein>[0]) : undefined,
  } as Omit<typeof query, "data"> & { data: Protein | undefined };
}

/**
 * Fetch a protein's FASTA sequence, parsed into `{ header, sequence }`.
 * Uses a custom query (not the generated hook) because the endpoint
 * requires `responseType: "text"` and a `format=fasta` query param.
 */
export function useProteinFasta(accession: string) {
  return useQuery({
    queryKey: proteinFastaKey(accession),
    queryFn: () =>
      customInstance<string>({
        url: `${API_V1}/proteins/${accession}`,
        method: "GET",
        params: { format: "fasta" },
        responseType: "text",
      }),
    enabled: !!accession,
    select: parseFasta,
  });
}

/** Resolve a protein by any identifier (accession, entry name, etc.).
 *  Pass `{ enabled: false }` to defer the fetch until a condition is met
 *  (e.g. the primary `useProtein` call has already returned not-found).
 */
export function useResolveProtein(identifier: string, options?: { enabled?: boolean }) {
  const enabled = options?.enabled !== undefined ? options.enabled : !!identifier;
  return useResolveProteinApiV1ProteinsResolveIdentifierGet(identifier, {
    query: { enabled: !!identifier && enabled },
  });
}
