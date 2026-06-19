import type { OrganismName } from "../types";

/**
 * Return the most human-readable common name for an organism.
 * Priority: `common_name` first, then `genbank_common_name`, else null.
 */
export function organismCommonName(names: OrganismName[]): string | null {
  const common = names.find((n) => n.name_class === "common_name");
  if (common) return common.name;
  const genbank = names.find((n) => n.name_class === "genbank_common_name");
  if (genbank) return genbank.name;
  return null;
}
