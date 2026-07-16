import {
  useGetGeneTargetBiologyApiV1GenesGeneIdTargetBiologyGet,
  useGetProteinTargetBiologyApiV1ProteinsProteinIdTargetBiologyGet,
} from "@/shared/lib/api/target-biology/target-biology";

/** All gene-side target-biology records (essentiality, vulnerability, hypomorph, CRISPRi, resistance) in one request. */
export function useGeneTargetBiology(geneId: string) {
  return useGetGeneTargetBiologyApiV1GenesGeneIdTargetBiologyGet(geneId);
}

/** All protein-side target-biology records (production, activity assay, unpublished structure) in one request. */
export function useProteinTargetBiology(proteinId: string) {
  return useGetProteinTargetBiologyApiV1ProteinsProteinIdTargetBiologyGet(proteinId);
}
