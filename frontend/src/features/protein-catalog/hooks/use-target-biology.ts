import {
  getGetGeneTargetBiologyApiV1GenesGeneIdTargetBiologyGetQueryKey,
  getGetProteinTargetBiologyApiV1ProteinsProteinIdTargetBiologyGetQueryKey,
  useGetGeneTargetBiologyApiV1GenesGeneIdTargetBiologyGet,
  useGetProteinTargetBiologyApiV1ProteinsProteinIdTargetBiologyGet,
} from "@/shared/lib/api/target-biology/target-biology";
import { useQueryClient } from "@tanstack/react-query";

/** All gene-side target-biology records (essentiality, vulnerability, hypomorph, CRISPRi, resistance) in one request. */
export function useGeneTargetBiology(geneId: string) {
  return useGetGeneTargetBiologyApiV1GenesGeneIdTargetBiologyGet(geneId);
}

/** All protein-side target-biology records (production, activity assay, unpublished structure) in one request. */
export function useProteinTargetBiology(proteinId: string) {
  return useGetProteinTargetBiologyApiV1ProteinsProteinIdTargetBiologyGet(proteinId);
}

/** onSuccess callback that refetches a gene's target-biology bundle after a write. */
export function useInvalidateGeneTargetBiology(geneId: string) {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({
      queryKey: getGetGeneTargetBiologyApiV1GenesGeneIdTargetBiologyGetQueryKey(geneId),
    });
  };
}

/** onSuccess callback that refetches a protein's target-biology bundle after a write. */
export function useInvalidateProteinTargetBiology(proteinId: string) {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({
      queryKey: getGetProteinTargetBiologyApiV1ProteinsProteinIdTargetBiologyGetQueryKey(proteinId),
    });
  };
}
