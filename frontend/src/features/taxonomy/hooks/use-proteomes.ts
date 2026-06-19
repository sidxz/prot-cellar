import {
  useGetProteomeApiV1ProteomesProteomeIdGet,
  useListProteomesApiV1ProteomesGet,
} from "@/shared/lib/api/proteomes/proteomes";

import type { ProteomeListFilters } from "../types";

/** List proteomes with optional filters and cursor-based pagination. */
export function useProteomes(filters: ProteomeListFilters = {}, cursor?: string) {
  return useListProteomesApiV1ProteomesGet({
    organism_id: filters.organismId ?? undefined,
    cursor: cursor ?? undefined,
  });
}

/** Fetch a single proteome by id. */
export function useProteome(id: string) {
  return useGetProteomeApiV1ProteomesProteomeIdGet(id);
}
