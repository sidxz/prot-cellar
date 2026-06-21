import type { CommentResponse, FeatureResponse } from "@/shared/lib/api/model";

import type { Protein } from "../types";

export interface GoRef {
  id: string;
  name: string;
  aspect: "F" | "P" | "C";
  evidence?: string;
  url?: string;
}

export interface StructureRef {
  id: string;
  method?: string;
  resolution?: string;
  chains?: string;
  url?: string;
}

/** Group comments by their UniProt comment_type (FUNCTION, COFACTOR, ...). */
export function commentsByType(p: Protein): Record<string, CommentResponse[]> {
  const out: Record<string, CommentResponse[]> = {};
  for (const c of p.comments ?? []) {
    const list = out[c.comment_type] ?? [];
    list.push(c);
    out[c.comment_type] = list;
  }
  return out;
}

type GoAspect = "F" | "P" | "C";

/** GO cross-references split by aspect; name + evidence parsed from the GoTerm property. */
export function goTermsByAspect(p: Protein): Record<GoAspect, GoRef[]> {
  const out: Record<GoAspect, GoRef[]> = { F: [], P: [], C: [] };
  for (const x of p.cross_references ?? []) {
    if (x.database !== "GO") continue;
    const goTerm = x.properties?.GoTerm ?? "";
    const aspect = goTerm.slice(0, 1);
    if (aspect !== "F" && aspect !== "P" && aspect !== "C") continue;
    out[aspect].push({
      id: x.accession,
      name: goTerm.slice(2),
      aspect,
      evidence: x.properties?.GoEvidence ?? undefined,
      url: x.url ?? undefined,
    });
  }
  return out;
}

const STRUCTURE_DB: Record<string, "pdb" | "alphafold" | "emdb"> = {
  PDB: "pdb",
  AlphaFoldDB: "alphafold",
  EMDB: "emdb",
};

/** Structure cross-references grouped by kind, with method/resolution/chains. */
export function structures(p: Protein): {
  pdb: StructureRef[];
  alphafold: StructureRef[];
  emdb: StructureRef[];
} {
  const out = {
    pdb: [] as StructureRef[],
    alphafold: [] as StructureRef[],
    emdb: [] as StructureRef[],
  };
  for (const x of p.cross_references ?? []) {
    const kind = STRUCTURE_DB[x.database];
    if (!kind) continue;
    out[kind].push({
      id: x.accession,
      method: x.properties?.Method ?? undefined,
      resolution: x.properties?.Resolution ?? undefined,
      chains: x.properties?.Chains ?? undefined,
      url: x.url ?? undefined,
    });
  }
  return out;
}

const FEATURE_CATEGORY: Record<string, string> = {
  ACT_SITE: "Sites",
  BINDING: "Sites",
  SITE: "Sites",
  METAL: "Sites",
  CA_BIND: "Sites",
  DNA_BIND: "Sites",
  NP_BIND: "Sites",
  MOD_RES: "Amino acid modifications",
  LIPID: "Amino acid modifications",
  CARBOHYD: "Amino acid modifications",
  DISULFID: "Amino acid modifications",
  CROSSLNK: "Amino acid modifications",
  DOMAIN: "Regions",
  REGION: "Regions",
  REPEAT: "Regions",
  MOTIF: "Regions",
  COILED: "Regions",
  ZN_FING: "Regions",
  COMPBIAS: "Regions",
  HELIX: "Secondary structure",
  STRAND: "Secondary structure",
  TURN: "Secondary structure",
  CHAIN: "Molecule processing",
  SIGNAL: "Molecule processing",
  TRANSIT: "Molecule processing",
  PROPEP: "Molecule processing",
  PEPTIDE: "Molecule processing",
  INIT_MET: "Molecule processing",
  TRANSMEM: "Topology",
  INTRAMEM: "Topology",
  TOPO_DOM: "Topology",
  MUTAGEN: "Mutagenesis",
  VARIANT: "Natural variants",
  CONFLICT: "Sequence uncertainty",
  UNSURE: "Sequence uncertainty",
};

/** Group sequence features into broad display categories. */
export function featuresByCategory(p: Protein): Record<string, FeatureResponse[]> {
  const out: Record<string, FeatureResponse[]> = {};
  for (const f of p.features ?? []) {
    const category = FEATURE_CATEGORY[f.feature_type] ?? "Other";
    const list = out[category] ?? [];
    list.push(f);
    out[category] = list;
  }
  return out;
}

function readLocationField(entry: unknown, field: "value" | "id"): string | undefined {
  if (entry && typeof entry === "object") {
    const loc = (entry as Record<string, unknown>).location;
    if (loc && typeof loc === "object") {
      const v = (loc as Record<string, unknown>)[field];
      return typeof v === "string" ? v : undefined;
    }
  }
  return undefined;
}

function subcellularLocationEntries(p: Protein): unknown[] {
  const entries: unknown[] = [];
  for (const c of commentsByType(p)["SUBCELLULAR LOCATION"] ?? []) {
    const payload = c.payload;
    if (payload && typeof payload === "object") {
      const locs = (payload as Record<string, unknown>).subcellularLocations;
      if (Array.isArray(locs)) entries.push(...locs);
    }
  }
  return entries;
}

/** Distinct subcellular location names from SUBCELLULAR LOCATION comment payloads. */
export function subcellularLocations(p: Protein): string[] {
  const out: string[] = [];
  for (const entry of subcellularLocationEntries(p)) {
    const value = readLocationField(entry, "value");
    if (value) out.push(value);
  }
  return [...new Set(out)];
}

/** SwissBioPics-formatted SL ids (no "SL-" prefix or leading zeros) for the diagram. */
export function subcellularLocationSlIds(p: Protein): string[] {
  const out: string[] = [];
  for (const entry of subcellularLocationEntries(p)) {
    const id = readLocationField(entry, "id");
    if (id) out.push(id.replace(/^SL-/, "").replace(/^0+/, ""));
  }
  return [...new Set(out)];
}
