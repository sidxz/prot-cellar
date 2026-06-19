export const PROTEINS_KEY = ["proteins"] as const;

export const proteinDetailKey = (accession: string) => [...PROTEINS_KEY, accession] as const;

export const proteinFastaKey = (accession: string) =>
  [...PROTEINS_KEY, accession, "fasta"] as const;

export const GENES_KEY = ["genes"] as const;

export const geneDetailKey = (id: string) => [...GENES_KEY, id] as const;
