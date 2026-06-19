// Types & label maps
export type {
  Organism,
  OrganismName,
  Strain,
  Proteome,
  OrganismListFilters,
  ProteomeListFilters,
  StrainFormValues,
} from "./types";
export {
  NAME_CLASS_LABELS,
  ORGANISM_SOURCE_LABELS,
  PROTEOME_TYPE_LABELS,
} from "./types";

// Format helpers
export { organismCommonName } from "./lib/organism-format";

// Organism hooks
export {
  useOrganisms,
  useOrganism,
  useResolveOrganism,
  useOrganismLineage,
} from "./hooks/use-organisms";

// Strain hooks
export {
  useStrains,
  useStrain,
  useCreateStrain,
  useUpdateStrain,
} from "./hooks/use-strains";

// Proteome hooks
export { useProteomes, useProteome } from "./hooks/use-proteomes";

// Components
export { OrganismListPage } from "./components/organism-list";
export { OrganismDetailPage } from "./components/organism-detail";
export { StrainListPage } from "./components/strain-list";
export { StrainDetailPage } from "./components/strain-detail";
export { StrainFormDialog } from "./components/strain-form-dialog";
