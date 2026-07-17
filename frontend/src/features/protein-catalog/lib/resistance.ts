// Resistance-mutation lollipop data: turn each mutation into a needle at its
// residue position, so a catalytic-site hotspot (many high-MIC mutations) reads
// apart from scattered low-level resistance at a glance.

export interface MutationLike {
  mutation?: string | null;
  protein_coordinate?: string | null;
  mic_shift?: number | null;
  compound?: { name?: string | null } | null;
}

/** First integer in a mutation / coordinate string (e.g. "S315T" → 315). */
export function parseResiduePosition(s: string | null | undefined): number | null {
  if (!s) return null;
  const m = s.match(/\d+/);
  return m ? Number.parseInt(m[0], 10) : null;
}

export interface Needle {
  id: string;
  label: string;
  position: number;
  micShift: number | null;
  compound: string | null;
}

/** One needle per mutation with a parseable position (protein_coordinate first). */
export function buildNeedles(mutations: MutationLike[]): Needle[] {
  const needles: Needle[] = [];
  mutations.forEach((m, i) => {
    const position = parseResiduePosition(m.protein_coordinate) ?? parseResiduePosition(m.mutation);
    if (position == null) return;
    const label = m.mutation?.trim() || m.protein_coordinate?.trim() || String(position);
    needles.push({
      id: `${label}-${position}-${i}`,
      label,
      position,
      micShift:
        typeof m.mic_shift === "number" && Number.isFinite(m.mic_shift) ? m.mic_shift : null,
      compound: m.compound?.name?.trim() || null,
    });
  });
  return needles;
}

/** Unique compound names in first-seen order (for the categorical color legend). */
export function distinctCompounds(needles: Needle[]): string[] {
  const seen: string[] = [];
  for (const n of needles) {
    if (n.compound && !seen.includes(n.compound)) seen.push(n.compound);
  }
  return seen;
}
