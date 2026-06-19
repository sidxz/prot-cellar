// Types
export type { Protein, Gene, CrossRef, ProteinListFilters, GeneListFilters } from "./types";

// Query keys
export {
  PROTEINS_KEY,
  proteinDetailKey,
  proteinFastaKey,
  GENES_KEY,
  geneDetailKey,
} from "./hooks/query-keys";

// Protein hooks
export { useProteins, useProtein, useProteinFasta, useResolveProtein } from "./hooks/use-proteins";

// Gene hooks
export { useGenes, useGene } from "./hooks/use-genes";

// Format helpers
export { proteinPrimaryName, proteinExistenceLabel } from "./lib/protein-format";

// Components
export { ProteinListPage } from "./components/protein-list";
export { ProteinDetailPage } from "./components/protein-detail";
