import {
  getGetGeneTargetBiologyApiV1GenesGeneIdTargetBiologyGetQueryKey,
  useCreateEssentialityApiV1GenesGeneIdTargetBiologyEssentialityPost,
  useDeleteEssentialityApiV1TargetBiologyEssentialityRecordIdDelete,
  useGetGeneTargetBiologyApiV1GenesGeneIdTargetBiologyGet,
  useGetProteinTargetBiologyApiV1ProteinsProteinIdTargetBiologyGet,
  useUpdateEssentialityApiV1TargetBiologyEssentialityRecordIdPatch,
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

/**
 * Create / update / delete mutations for a gene's Essentiality records.
 * Each invalidates the gene's target-biology bundle on success so the table refetches.
 */
export function useEssentialityMutations(geneId: string) {
  const qc = useQueryClient();
  const onSuccess = () => {
    qc.invalidateQueries({
      queryKey: getGetGeneTargetBiologyApiV1GenesGeneIdTargetBiologyGetQueryKey(geneId),
    });
  };
  return {
    create: useCreateEssentialityApiV1GenesGeneIdTargetBiologyEssentialityPost({
      mutation: { onSuccess },
    }),
    update: useUpdateEssentialityApiV1TargetBiologyEssentialityRecordIdPatch({
      mutation: { onSuccess },
    }),
    remove: useDeleteEssentialityApiV1TargetBiologyEssentialityRecordIdDelete({
      mutation: { onSuccess },
    }),
  };
}
