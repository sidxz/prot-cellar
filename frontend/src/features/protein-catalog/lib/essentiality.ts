// Shared essentiality logic — one source of truth for the call vocabulary, its
// position on the diverging *fitness* axis (growth-advantage → essential), and
// the token classes that shade it. Consolidates the near-duplicate bucketing
// that previously lived in genomic-context-section + axis-annotations-section.
//
// The axis is a fitness scale, NOT a "good/bad" scale: essential is the extreme
// of "the pathogen needs it", growth-advantage the opposite pole. Target
// desirability (green = good) is a triage-app concern, kept out of prot-cellar.

export type EssentialityBucket =
  | "essential"
  | "growth-defect"
  | "non-essential"
  | "growth-advantage"
  | "uncertain";

/** Bucket a free-text / enum essentiality value (case-, hyphen- and underscore-tolerant). */
export function essentialityBucket(value: string | null | undefined): EssentialityBucket {
  const v = (value ?? "").toLowerCase().replace(/_/g, "-");
  // non-essential must be tested before essential (it contains the substring).
  if (v.includes("non-essential") || v.includes("nonessential")) return "non-essential";
  if (v.includes("growth-defect") || v.includes("growth defect")) return "growth-defect";
  if (v.includes("growth-advantage") || v.includes("growth advantage")) return "growth-advantage";
  if (v.includes("essential")) return "essential";
  return "uncertain";
}

// Discrete positions on the [0,1] fitness axis. Growth-advantage (loses it, grows
// better) at the low end; essential (needs it most) near the high end. `uncertain`
// has no position — the caller should not place a caret.
const FITNESS_POSITION: Record<EssentialityBucket, number | null> = {
  "growth-advantage": 0.08,
  "non-essential": 0.37,
  "growth-defect": 0.64,
  essential: 0.92,
  uncertain: null,
};

/** Position of a call on the diverging fitness axis, or null for uncertain/missing. */
export function fitnessPosition(value: string | null | undefined): number | null {
  return FITNESS_POSITION[essentialityBucket(value)];
}

// Static Tailwind class sets per bucket (static so the compiler keeps them).
// Reuses existing semantic tokens; growth-advantage borrows chart-1 (the cool
// pole) since there's no dedicated "advantage" token.
export const ESSENTIALITY_STYLE: Record<
  EssentialityBucket,
  { fill: string; text: string; bg: string; border: string }
> = {
  essential: {
    fill: "fill-destructive",
    text: "text-destructive",
    bg: "bg-destructive/10",
    border: "border-destructive/40",
  },
  "growth-defect": {
    fill: "fill-warning",
    text: "text-warning",
    bg: "bg-warning/15",
    border: "border-warning/30",
  },
  "non-essential": {
    fill: "fill-muted-foreground",
    text: "text-muted-foreground",
    bg: "bg-muted",
    border: "border-border",
  },
  "growth-advantage": {
    fill: "fill-chart-1",
    text: "text-chart-1",
    bg: "bg-chart-1/10",
    border: "border-chart-1/40",
  },
  uncertain: {
    fill: "fill-muted-foreground/60",
    text: "text-muted-foreground",
    bg: "bg-card",
    border: "border-border",
  },
};

/** Axis tick labels, low → high fitness (for the call-scale legend). */
export const FITNESS_AXIS_LABELS = ["Growth-adv.", "Non-ess.", "Growth-def.", "Essential"] as const;

// ── Multi-record aggregation ────────────────────────────────────────────────
// A gene carries a *list* of essentiality records — one per condition, method,
// or source. These fold that list into a headline consensus and a
// condition×method pivot so the "many rows" case reads at a glance.

/** Minimal shape these helpers need — decoupled from the generated DTO. */
export interface EssentialityLike {
  classification: string;
  condition?: string | null;
  method?: string | null;
  confidence?: number | null;
}

const SEVERITY: Record<EssentialityBucket, number> = {
  essential: 4,
  "growth-defect": 3,
  "non-essential": 2,
  "growth-advantage": 1,
  uncertain: 0,
};

export interface EssentialityConsensus {
  bucket: EssentialityBucket;
  confidence: number | null;
  /** single = one record · agree = all records concur · conflict = they disagree */
  agreement: "single" | "agree" | "conflict";
  /** records matching the consensus bucket */
  count: number;
  total: number;
}

/**
 * The headline call across a gene's essentiality records: the modal bucket
 * (ties broken toward the more severe call), the mean confidence of the records
 * backing that call, and whether the sources agree.
 */
export function essentialityConsensus(records: EssentialityLike[]): EssentialityConsensus | null {
  if (records.length === 0) return null;

  const buckets = records.map((r) => essentialityBucket(r.classification));
  const counts = new Map<EssentialityBucket, number>();
  for (const b of buckets) counts.set(b, (counts.get(b) ?? 0) + 1);

  let bucket = buckets[0];
  let best = -1;
  for (const [b, c] of counts) {
    if (c > best || (c === best && SEVERITY[b] > SEVERITY[bucket])) {
      bucket = b;
      best = c;
    }
  }

  const matching = records.filter((r) => essentialityBucket(r.classification) === bucket);
  const confs = matching
    .map((r) => r.confidence)
    .filter((c): c is number => c != null && Number.isFinite(c));
  // Mean across the records backing the call — a headline "confidence" of the
  // single most-confident row overstates a call several weaker sources support.
  const confidence = confs.length ? confs.reduce((a, b) => a + b, 0) / confs.length : null;

  const distinct = new Set(buckets).size;
  const agreement = records.length === 1 ? "single" : distinct === 1 ? "agree" : "conflict";

  return { bucket, confidence, agreement, count: matching.length, total: records.length };
}

const PIVOT_FALLBACK = "—";
// NUL joins the composite pivot key: it can never appear in a condition or
// method, so "a b"+"c" and "a"+"b c" can't collide onto one cell.
const KEY_SEP = "\u0000";

/** A pivot cell is a single call, or "conflict" when sources disagree in one cell. */
export type PivotCell = EssentialityBucket | "conflict";

export interface ConditionMethodPivot {
  conditions: string[];
  methods: string[];
  cell: (condition: string, method: string) => PivotCell | null;
}

/** Pivot records into unique conditions (columns) × methods (rows), first-seen order. */
export function pivotConditionMethod(records: EssentialityLike[]): ConditionMethodPivot {
  const conditions: string[] = [];
  const methods: string[] = [];
  const map = new Map<string, PivotCell>();

  for (const r of records) {
    const cond = r.condition?.trim() || PIVOT_FALLBACK;
    const meth = r.method?.trim() || PIVOT_FALLBACK;
    if (!conditions.includes(cond)) conditions.push(cond);
    if (!methods.includes(meth)) methods.push(meth);
    const key = `${cond}${KEY_SEP}${meth}`;
    const next = essentialityBucket(r.classification);
    const prev = map.get(key);
    // Two sources, same condition×method: keep the call if they agree, else
    // flag the disagreement instead of silently keeping whichever came last.
    map.set(key, prev === undefined || prev === next ? next : "conflict");
  }

  return {
    conditions,
    methods,
    cell: (c, m) => map.get(`${c}${KEY_SEP}${m}`) ?? null,
  };
}
