"use client";

import { OrganismRef } from "@/shared/components/common/organism-ref";
import { SequenceViewer } from "@/shared/components/sequence/sequence-viewer";
import { Badge } from "@/shared/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { CrossReferenceLinks } from "@/shared/components/xrefs/cross-reference-links";
import { Dna, ExternalLink } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useProtein, useProteinFasta, useResolveProtein } from "../hooks/use-proteins";
import { proteinExistenceLabel } from "../lib/protein-format";
import type { Protein } from "../types";
import { CitationsSection } from "./sections/citations-section";
import { FeaturesSection } from "./sections/features-section";
import { FunctionSection } from "./sections/function-section";
import { GoGraphCard } from "./sections/go-graph-card";
import { GoTermsSection } from "./sections/go-terms-section";
import { IsoformsSection } from "./sections/isoforms-section";
import { KeywordsSection } from "./sections/keywords-section";
import { StructureViewerCard } from "./sections/structure-viewer-card";
import { SubcellularLocationCard } from "./sections/subcellular-location-card";

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
    <div className="flex flex-col gap-6" aria-label="Loading protein detail">
      {/* Header skeleton */}
      <div className="flex flex-col gap-2">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-64" />
      </div>
      {/* Card skeleton */}
      <Skeleton className="h-56 w-full rounded-xl" />
      {/* Sequence skeleton */}
      <Skeleton className="h-40 w-full rounded-xl" />
      {/* Xrefs skeleton */}
      <Skeleton className="h-24 w-full rounded-xl" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Protein metadata card
// ---------------------------------------------------------------------------

interface MetadataCardProps {
  protein: Protein;
}

function MetadataCard({ protein }: MetadataCardProps) {
  const names = protein.protein_names ?? {};

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold text-foreground">Protein Metadata</CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="flex flex-col">
          {/* Recommended name */}
          {names.recommended && (
            <MetadataRow label="Recommended name">
              <span className="font-medium">{names.recommended}</span>
            </MetadataRow>
          )}

          {/* Alternative names */}
          {names.alternative && names.alternative.length > 0 && (
            <MetadataRow label="Alternative names">
              <ul className="flex flex-col gap-0.5">
                {names.alternative.map((n) => (
                  <li key={n} className="text-sm">
                    {n}
                  </li>
                ))}
              </ul>
            </MetadataRow>
          )}

          {/* Submitted names */}
          {names.submitted && names.submitted.length > 0 && (
            <MetadataRow label="Submitted names">
              <ul className="flex flex-col gap-0.5">
                {names.submitted.map((n) => (
                  <li key={n} className="text-sm">
                    {n}
                  </li>
                ))}
              </ul>
            </MetadataRow>
          )}

          {/* Organism */}
          <MetadataRow label="Organism">
            <OrganismRef id={protein.organism_id} />
          </MetadataRow>

          {/* Gene */}
          {protein.gene_id && (
            <MetadataRow label="Gene">
              <Link
                href={`/genes/${protein.gene_id}`}
                className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-0.5 text-xs font-mono text-primary hover:bg-accent hover:text-accent-foreground transition-colors"
              >
                {protein.gene_id}
              </Link>
            </MetadataRow>
          )}

          {/* Protein existence */}
          {protein.protein_existence && (
            <MetadataRow label="Existence">
              <span>{proteinExistenceLabel(protein.protein_existence)}</span>
            </MetadataRow>
          )}

          {/* Entry version / sequence version */}
          {(protein.entry_version != null || protein.sequence_version != null) && (
            <MetadataRow label="Version">
              <span className="font-mono text-xs">
                {protein.entry_version != null ? `Entry v${protein.entry_version}` : ""}
                {protein.entry_version != null && protein.sequence_version != null ? " · " : ""}
                {protein.sequence_version != null ? `Seq v${protein.sequence_version}` : ""}
              </span>
            </MetadataRow>
          )}

          {/* Secondary accessions */}
          {protein.secondary_accessions && protein.secondary_accessions.length > 0 && (
            <MetadataRow label="Secondary acc.">
              <div className="flex flex-wrap gap-1">
                {protein.secondary_accessions.map((acc) => (
                  <span
                    key={acc}
                    className="font-mono text-xs rounded border border-border px-1.5 py-0.5 text-muted-foreground"
                  >
                    {acc}
                  </span>
                ))}
              </div>
            </MetadataRow>
          )}
        </dl>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// FASTA / sequence section
// ---------------------------------------------------------------------------

interface SequenceSectionProps {
  protein: Protein;
}

function SequenceSection({ protein }: SequenceSectionProps) {
  const {
    data: fasta,
    isLoading: fastaLoading,
    isError: fastaError,
  } = useProteinFasta(protein.primary_accession);

  if (fastaLoading) {
    return <Skeleton className="h-40 w-full rounded-xl" aria-label="Loading sequence" />;
  }

  if (fastaError || !fasta) {
    return <p className="text-sm text-muted-foreground italic">Sequence unavailable</p>;
  }

  return (
    <SequenceViewer
      sequence={fasta.sequence}
      length={protein.seq_length}
      mass={protein.seq_mass ?? undefined}
      accession={protein.primary_accession}
    />
  );
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

export interface ProteinDetailPageProps {
  accession: string;
}

export function ProteinDetailPage({ accession }: ProteinDetailPageProps) {
  const router = useRouter();

  // ── Primary fetch (by accession) ─────────────────────────────────────────
  const { data, isLoading, isError } = useProtein(accession);

  // ── Resolve fallback — fires only when primary fetch finished and found nothing ──
  const primaryNotFound = !isLoading && (isError || !data);
  const {
    data: resolvedData,
    isLoading: resolveLoading,
    isError: resolveError,
  } = useResolveProtein(accession, { enabled: primaryNotFound });

  // ── Redirect to canonical URL when resolve returns a different accession ──
  useEffect(() => {
    if (resolvedData && resolvedData.primary_accession !== accession) {
      router.replace(`/proteins/${resolvedData.primary_accession}`);
    }
  }, [resolvedData, accession, router]);

  // ── Loading ──────────────────────────────────────────────────────────────
  if (isLoading || (primaryNotFound && resolveLoading)) {
    return <DetailSkeleton />;
  }

  // ── Error / not found — only after BOTH paths have failed ────────────────
  if (primaryNotFound && (resolveError || !resolvedData)) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-24 text-center text-muted-foreground">
        <Dna className="h-12 w-12 opacity-25" />
        <div>
          <p className="text-base font-semibold text-foreground">Protein not found</p>
          <p className="text-sm mt-1">
            No protein with accession <span className="font-mono">{accession}</span> could be
            located in the database.
          </p>
        </div>
        <Link href="/proteins" className="text-sm text-primary underline-offset-4 hover:underline">
          Back to protein catalog
        </Link>
      </div>
    );
  }

  // ── Resolve succeeded with same accession (edge case guard) ──────────────
  // Redirect effect above handles the different-accession case; if same accession,
  // fall through and render using resolvedData cast to Protein below.
  const protein: Protein = (data ?? resolvedData) as Protein;

  // ── Detail view ───────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-8 pb-16">
      {/* ── Page header ── */}
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold tracking-tight text-foreground font-mono">
            {protein.primary_accession}
          </h1>
          <Badge variant={protein.is_reviewed ? "default" : "secondary"}>
            {protein.is_reviewed ? "Swiss-Prot" : "TrEMBL"}
          </Badge>
          {protein.uniprot_url && (
            <a
              href={protein.uniprot_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-primary transition-colors"
              aria-label="View on UniProt"
            >
              <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
              UniProt
            </a>
          )}
        </div>
        {protein.entry_name && (
          <p className="text-sm text-muted-foreground font-mono">{protein.entry_name}</p>
        )}
      </header>

      {/* ── Two-column body ── */}
      <div className="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-6 items-start">
        {/* Main column */}
        <div className="flex flex-col gap-6 min-w-0">
          <FunctionSection protein={protein} />
          <FeaturesSection protein={protein} />
          <StructureViewerCard protein={protein} />
          <GoGraphCard protein={protein} />
          <section aria-labelledby="seq-heading">
            <h2 id="seq-heading" className="text-base font-semibold mb-3 text-foreground">
              Sequence
            </h2>
            <SequenceSection protein={protein} />
          </section>
        </div>
        {/* Side column */}
        <div className="flex flex-col gap-6 min-w-0">
          <MetadataCard protein={protein} />
          <GoTermsSection protein={protein} />
          <SubcellularLocationCard protein={protein} />
          <KeywordsSection protein={protein} />
          <CitationsSection protein={protein} />
          <IsoformsSection protein={protein} />
        </div>
      </div>

      {/* ── Cross-references ── */}
      {protein.cross_references && protein.cross_references.length > 0 && (
        <section aria-labelledby="xrefs-heading">
          <h2 id="xrefs-heading" className="text-base font-semibold mb-3 text-foreground">
            Cross-References
          </h2>
          <Card>
            <CardContent className="pt-4">
              <CrossReferenceLinks
                // ProteinResponseCrossReferencesItem is typed as {[key:string]:string|null}
                // but the actual shape matches CrossReference — cast at the feature boundary.
                // biome-ignore lint/suspicious/noExplicitAny: cast at feature boundary
                items={protein.cross_references as any}
              />
            </CardContent>
          </Card>
        </section>
      )}
    </div>
  );
}
