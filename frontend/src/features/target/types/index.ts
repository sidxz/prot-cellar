import type {
  ComponentRelationship,
  ComponentResponse,
  TargetResponse,
  TargetType,
} from "@/shared/lib/api/model";

/** Target (alias of generated DTO — no narrowing needed). */
export type Target = TargetResponse;

/** Target component view (alias of generated DTO). */
export type TargetComponentView = ComponentResponse;

/** UI-side editor row for adding/editing a target component. */
export interface TargetComponentInput {
  protein_id: string;
  relationship: ComponentRelationship;
  /** Display-only: UniProt accession */
  accession?: string;
  /** Display-only: human-readable label */
  label?: string;
}

/** Human-readable labels for each TargetType value. */
export const TARGET_TYPE_LABELS: Record<TargetType, string> = {
  single_protein: "Single Protein",
  protein_complex: "Protein Complex",
  protein_family: "Protein Family",
  protein_protein_interaction: "Protein-Protein Interaction",
  nucleic_acid: "Nucleic Acid",
  organism: "Organism",
  cell_line: "Cell Line",
  tissue: "Tissue",
  unknown: "Unknown",
};

/** Human-readable labels for each ComponentRelationship value. */
export const RELATIONSHIP_LABELS: Record<ComponentRelationship, string> = {
  single_protein: "Single Protein",
  protein_subunit: "Protein Subunit",
  family_member: "Family Member",
  interacting_protein: "Interacting Protein",
};

/** Filter parameters for listing targets. */
export interface TargetListFilters {
  targetType?: TargetType;
  chemblId?: string;
}
