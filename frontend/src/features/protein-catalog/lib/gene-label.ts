/** Names to show under a gene's lead label, minus the lead itself, deduped. */
export function secondaryNames(names: (string | null | undefined)[], lead: string): string[] {
  const seen = new Set<string>([lead]);
  const out: string[] = [];
  for (const n of names) {
    if (n && !seen.has(n)) {
      seen.add(n);
      out.push(n);
    }
  }
  return out;
}
