import type { TargetType } from "@/shared/lib/api/model";

/**
 * Returns the component count bounds for a given target type.
 * - single_protein / domain: exactly 1
 * - protein_complex / protein_family / protein_protein_interaction: at least 2
 * - everything else: 0..∞ (optional)
 */
export function cardinalityRule(t: TargetType): { min: number; max: number } {
  if (t === "single_protein" || t === "domain") {
    return { min: 1, max: 1 };
  }
  if (t === "protein_complex" || t === "protein_family" || t === "protein_protein_interaction") {
    return { min: 2, max: Number.MAX_SAFE_INTEGER };
  }
  return { min: 0, max: Number.MAX_SAFE_INTEGER };
}

/** Returns true when the component count `n` satisfies the rule for `t`. */
export function componentCountValid(t: TargetType, n: number): boolean {
  const { min, max } = cardinalityRule(t);
  return n >= min && n <= max;
}

/** Human-readable hint describing the component count requirement. */
export function cardinalityHint(t: TargetType): string {
  const { min, max } = cardinalityRule(t);
  if (min === 1 && max === 1) return "Exactly 1 protein";
  if (min >= 2) return "At least 2 proteins";
  return "Optional";
}
