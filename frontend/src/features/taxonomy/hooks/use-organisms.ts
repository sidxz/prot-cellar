import { useQuery } from "@tanstack/react-query";

import {
  getOrganismApiV1OrganismsOrganismIdGet,
  useGetOrganismApiV1OrganismsOrganismIdGet,
  useListOrganismsApiV1OrganismsGet,
  useResolveOrganismApiV1OrganismsResolveTaxIdGet,
} from "@/shared/lib/api/organisms/organisms";

import type { Organism, OrganismListFilters } from "../types";

/**
 * List organisms with optional filters and cursor-based pagination.
 *
 * Caveat: when `name` is set the backend switches to a name-search branch
 * (`OrganismRepository.find_by_name`) that does NOT apply `tags`/`tag_logic`
 * — tag filtering is only wired into the primary (name-less) list path.
 */
export function useOrganisms(filters: OrganismListFilters = {}, cursor?: string) {
  return useListOrganismsApiV1OrganismsGet({
    name: filters.name ?? undefined,
    rank: filters.rank ?? undefined,
    limit: filters.limit ?? undefined,
    tags: filters.tags ?? undefined,
    tag_logic: filters.tagLogic ?? undefined,
    cursor: cursor ?? undefined,
  });
}

/** Fetch a single organism by id. */
export function useOrganism(id: string) {
  return useGetOrganismApiV1OrganismsOrganismIdGet(id);
}

/** Resolve an organism by NCBI taxonomy id. */
export function useResolveOrganism(taxId: number) {
  return useResolveOrganismApiV1OrganismsResolveTaxIdGet(taxId);
}

/**
 * Walk up the parent_id chain for an organism, returning its ancestors in
 * root→immediate-parent order.
 *
 * - Enabled only when `organism.parent_id` is set.
 * - Bounded to ≤ 30 hops.
 * - Stops on a missing parent or a detected cycle (tracks visited ids).
 * - Uses the NON-hook `getOrganismApiV1OrganismsOrganismIdGet` inside the
 *   queryFn — no hooks called in a loop.
 */
export function useOrganismLineage(organism?: Organism) {
  return useQuery({
    queryKey: ["organism-lineage", organism?.id],
    enabled: !!organism?.parent_id,
    queryFn: async (): Promise<Organism[]> => {
      const ancestors: Organism[] = [];
      const seen = new Set<string>();
      const MAX_HOPS = 30;

      let currentParentId: string | null | undefined = organism?.parent_id;

      while (currentParentId && ancestors.length < MAX_HOPS) {
        if (seen.has(currentParentId)) break; // cycle detected
        seen.add(currentParentId);

        let parent: Organism;
        try {
          parent = await getOrganismApiV1OrganismsOrganismIdGet(currentParentId);
        } catch {
          break; // missing parent — stop
        }

        ancestors.push(parent);
        currentParentId = parent.parent_id ?? null;
      }

      // ancestors is currently leaf→root; reverse for root→immediate-parent
      return ancestors.reverse();
    },
  });
}
