import {
  useGetProteomeApiV1ProteomesProteomeIdGet,
  useListProteomesApiV1ProteomesGet,
} from "@/shared/lib/api/proteomes/proteomes";

import type { ProteomeListFilters } from "../types";

/**
 * List proteomes with optional filters and cursor-based pagination.
 *
 * Caveat: when `organismId` is set the backend switches to a by-organism
 * branch (`ProteomeRepository.find_by_organism`) that does NOT apply
 * `tags`/`tag_logic` — tag filtering is only wired into the primary
 * (organism-less) list path.
 */
export function useProteomes(filters: ProteomeListFilters = {}, cursor?: string) {
  return useListProteomesApiV1ProteomesGet({
    organism_id: filters.organismId ?? undefined,
    tags: filters.tags ?? undefined,
    tag_logic: filters.tagLogic ?? undefined,
    cursor: cursor ?? undefined,
  });
}

/** Fetch a single proteome by id. */
export function useProteome(id: string) {
  return useGetProteomeApiV1ProteomesProteomeIdGet(id);
}
