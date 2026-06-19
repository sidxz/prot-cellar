import type { Protein } from "../types";

/**
 * Returns the best display name for a protein, following this priority:
 * 1. recommended name
 * 2. first submitted name
 * 3. entry_name
 * 4. primary_accession (always present)
 */
export function proteinPrimaryName(p: Protein): string {
  const names = p.protein_names;
  if (names?.recommended) return names.recommended;
  if (names?.submitted && names.submitted.length > 0) return names.submitted[0];
  if (p.entry_name) return p.entry_name;
  return p.primary_accession;
}

const PE_LABELS: Record<string, string> = {
  evidence_at_protein_level: "Evidence at protein level",
  EVIDENCE_AT_PROTEIN_LEVEL: "Evidence at protein level",
  evidence_at_transcript_level: "Evidence at transcript level",
  EVIDENCE_AT_TRANSCRIPT_LEVEL: "Evidence at transcript level",
  inferred_from_homology: "Inferred from homology",
  INFERRED_FROM_HOMOLOGY: "Inferred from homology",
  predicted: "Predicted",
  PREDICTED: "Predicted",
  uncertain: "Uncertain",
  UNCERTAIN: "Uncertain",
};

/**
 * Maps a protein existence code (PE level) to a human-readable label.
 * Returns "—" for null/undefined/unknown codes.
 */
export function proteinExistenceLabel(pe?: string | null): string {
  if (pe == null) return "—";
  return PE_LABELS[pe] ?? "—";
}
