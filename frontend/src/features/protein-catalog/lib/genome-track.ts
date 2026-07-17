// Layout math for the genomic-neighborhood track: map each gene's genomic
// [start,end] onto a pixel band proportional to real coordinates, so an ORF's
// width reflects its length and the gaps reflect intergenic distance — a locus
// view, not a row of equal chips.

export interface TrackGene {
  id: string;
  name: string;
  strand: string | null;
  essentiality: string | null;
  start: number;
  end: number;
  isCurrent: boolean;
}

export interface PositionedGene extends TrackGene {
  /** left edge in px */
  x: number;
  /** width in px (clamped to a minimum so tiny ORFs stay visible/clickable) */
  w: number;
}

/** Position genes proportionally across `width` px; tiny ORFs get `minW`. */
export function layoutNeighbors(genes: TrackGene[], width: number, minW = 6): PositionedGene[] {
  if (genes.length === 0) return [];

  const lo = Math.min(...genes.map((g) => Math.min(g.start, g.end)));
  const hi = Math.max(...genes.map((g) => Math.max(g.start, g.end)));
  const span = hi - lo || 1;

  return genes.map((g) => {
    const s = Math.min(g.start, g.end);
    const e = Math.max(g.start, g.end);
    return {
      ...g,
      x: ((s - lo) / span) * width,
      w: Math.max(minW, ((e - s) / span) * width),
    };
  });
}
