"use client";

import { OrganismRef } from "@/shared/components/common/organism-ref";
import { Badge } from "@/shared/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { CrossReferenceLinks } from "@/shared/components/xrefs/cross-reference-links";
import { useBreadcrumbOverride } from "@/shared/lib/stores/breadcrumb-store";
import { Dna, ExternalLink } from "lucide-react";
import Link from "next/link";
import { useGene } from "../hooks/use-genes";
import { useProteins } from "../hooks/use-proteins";
import { AXIS_TITLES, AxisAnnotationsSection } from "./sections/axis-annotations-section";
import { GeneTargetBiologyTab } from "./sections/gene-target-biology-tab";
import { GenomicContextSection } from "./sections/genomic-context-section";

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
  const functionalCategory = gene.annotations?.find((a) => a.key === "functional_category")?.value;
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

          {/* Organism */}
          <MetadataRow label="Organism">
            <OrganismRef id={gene.organism_id} />
          </MetadataRow>

          {/* Functional category (Mycobrowser CONTEXT annotation) */}
          {functionalCategory && (
            <MetadataRow label="Functional Category">
              <Badge variant="outline" className="text-xs font-normal capitalize">
                {functionalCategory}
              </Badge>
            </MetadataRow>
          )}

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
// Linked proteins section
// ---------------------------------------------------------------------------

function LinkedProteinsSection({ geneId }: { geneId: string }) {
  const { data, isLoading, isError } = useProteins({ geneId });
  const proteins = data?.items ?? [];

  return (
    <section aria-labelledby="proteins-heading">
      <h2 id="proteins-heading" className="text-base font-semibold mb-3 text-foreground">
        Proteins
      </h2>
      <Card>
        <CardContent className="pt-4">
          {isLoading ? (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : isError ? (
            <p className="text-sm text-muted-foreground italic">Could not load proteins.</p>
          ) : proteins.length === 0 ? (
            <p className="text-sm text-muted-foreground italic">
              No proteins are linked to this gene.
            </p>
          ) : (
            <ul className="flex flex-col divide-y divide-border/50">
              {proteins.map((p) => (
                <li
                  key={p.id}
                  className="flex items-center justify-between gap-3 py-2 first:pt-0 last:pb-0"
                >
                  <div className="flex min-w-0 flex-col">
                    <Link
                      href={`/proteins/${p.primary_accession}`}
                      className="font-mono text-sm text-primary hover:underline underline-offset-4"
                    >
                      {p.primary_accession}
                    </Link>
                    {p.recommended_name && (
                      <span className="truncate text-xs text-muted-foreground">
                        {p.recommended_name}
                      </span>
                    )}
                  </div>
                  <Badge
                    variant={p.is_reviewed ? "default" : "secondary"}
                    className="shrink-0 text-xs"
                  >
                    {p.is_reviewed ? "Swiss-Prot" : "TrEMBL"}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </section>
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
  // Show the gene name (not its UUID) in the breadcrumb once loaded.
  useBreadcrumbOverride(geneId, data?.primary_name ?? "");

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
          <Badge variant="default">Gene</Badge>
        </div>
      </header>

      {/* Single scroll (no tabs): the gene overview is light, and the typed
          target-biology records are the primary triage content, so they lead
          rather than hide behind a tab. (The protein page, which is dense,
          keeps its tabs.) */}
      <GeneMetadataCard gene={data} />
      <GenomicContextSection gene={data} />
      <AxisAnnotationsSection gene={data} axis="vulnerability" title={AXIS_TITLES.vulnerability} />

      <section aria-labelledby="target-biology-heading" className="flex flex-col gap-4">
        <h2 id="target-biology-heading" className="text-base font-semibold text-foreground">
          Target Biology
        </h2>
        <GeneTargetBiologyTab geneId={data.id} />
      </section>

      <LinkedProteinsSection geneId={data.id} />

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
