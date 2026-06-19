"use client";

import { Badge } from "@/shared/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { CrossReferenceLinks } from "@/shared/components/xrefs/cross-reference-links";
import { Dna, ExternalLink } from "lucide-react";
import Link from "next/link";
import { useGene } from "../hooks/use-genes";

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface MetadataRowProps {
  label: string;
  children: React.ReactNode;
}

function MetadataRow({ label, children }: MetadataRowProps) {
  return (
    <div className="grid grid-cols-[10rem_1fr] gap-2 py-1.5 border-b border-border/50 last:border-0">
      <dt className="text-xs font-medium text-muted-foreground uppercase tracking-wide self-start pt-0.5">
        {label}
      </dt>
      <dd className="text-sm text-foreground leading-relaxed">{children}</dd>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function DetailSkeleton() {
  return (
    <div className="flex flex-col gap-6" aria-label="Loading gene detail">
      {/* Header skeleton */}
      <div className="flex flex-col gap-2">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-64" />
      </div>
      {/* Card skeleton */}
      <Skeleton className="h-56 w-full rounded-xl" />
      {/* Xrefs skeleton */}
      <Skeleton className="h-24 w-full rounded-xl" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Gene metadata card
// ---------------------------------------------------------------------------

interface GeneMetadataCardProps {
  gene: NonNullable<ReturnType<typeof useGene>["data"]>;
}

function GeneMetadataCard({ gene }: GeneMetadataCardProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold text-foreground">Gene Metadata</CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="flex flex-col">
          {/* Synonyms */}
          {gene.synonyms && gene.synonyms.length > 0 && (
            <MetadataRow label="Synonyms">
              <div className="flex flex-wrap gap-1">
                {gene.synonyms.map((syn) => (
                  <Badge key={syn} variant="secondary" className="text-xs">
                    {syn}
                  </Badge>
                ))}
              </div>
            </MetadataRow>
          )}

          {/* Organism — Plan 3 will add the organism name; link by ID for now */}
          <MetadataRow label="Organism">
            <Link
              href={`/organisms/${gene.organism_id}`}
              className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-0.5 text-xs font-mono text-primary hover:bg-accent hover:text-accent-foreground transition-colors"
            >
              {gene.organism_id}
            </Link>
          </MetadataRow>

          {/* NCBI Gene */}
          {gene.ncbi_gene_id && (
            <MetadataRow label="NCBI Gene">
              {gene.ncbi_gene_url ? (
                <a
                  href={gene.ncbi_gene_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 font-mono text-xs text-primary hover:underline underline-offset-4"
                  aria-label={`View NCBI Gene ${gene.ncbi_gene_id}`}
                >
                  <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                  {gene.ncbi_gene_id}
                </a>
              ) : (
                <span className="font-mono text-xs">{gene.ncbi_gene_id}</span>
              )}
            </MetadataRow>
          )}

          {/* Ensembl */}
          {gene.ensembl_gene_id && (
            <MetadataRow label="Ensembl">
              {gene.ensembl_url ? (
                <a
                  href={gene.ensembl_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 font-mono text-xs text-primary hover:underline underline-offset-4"
                  aria-label={`View Ensembl gene ${gene.ensembl_gene_id}`}
                >
                  <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                  {gene.ensembl_gene_id}
                </a>
              ) : (
                <span className="font-mono text-xs">{gene.ensembl_gene_id}</span>
              )}
            </MetadataRow>
          )}

          {/* HGNC */}
          {gene.hgnc_id && (
            <MetadataRow label="HGNC">
              <span className="font-mono text-xs">{gene.hgnc_id}</span>
            </MetadataRow>
          )}
        </dl>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

export interface GeneDetailPageProps {
  geneId: string;
}

export function GeneDetailPage({ geneId }: GeneDetailPageProps) {
  const { data, isLoading, isError } = useGene(geneId);

  // ── Loading ──────────────────────────────────────────────────────────────
  if (isLoading) {
    return <DetailSkeleton />;
  }

  // ── Error / not found ────────────────────────────────────────────────────
  if (isError || !data) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-24 text-center text-muted-foreground">
        <Dna className="h-12 w-12 opacity-25" />
        <div>
          <p className="text-base font-semibold text-foreground">Gene not found</p>
          <p className="text-sm mt-1">
            No gene with ID <span className="font-mono">{geneId}</span> could be located in the
            database.
          </p>
        </div>
        <Link href="/genes" className="text-sm text-primary underline-offset-4 hover:underline">
          Back to gene catalog
        </Link>
      </div>
    );
  }

  // ── Detail view ──────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-8 pb-16">
      {/* ── Page header ── */}
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold tracking-tight text-foreground font-mono">
            {data.primary_name}
          </h1>
          <Badge className="bg-teal-600 text-white hover:bg-teal-700">Gene</Badge>
        </div>
        <p className="text-sm text-muted-foreground font-mono">{data.id}</p>
      </header>

      {/* ── Metadata card ── */}
      <GeneMetadataCard gene={data} />

      {/* ── Cross-references ── */}
      {data.cross_references && data.cross_references.length > 0 && (
        <section aria-labelledby="xrefs-heading">
          <h2 id="xrefs-heading" className="text-base font-semibold mb-3 text-foreground">
            Cross-References
          </h2>
          <Card>
            <CardContent className="pt-4">
              <CrossReferenceLinks items={data.cross_references} />
            </CardContent>
          </Card>
        </section>
      )}
    </div>
  );
}
