"use client";

import { TagsRelation } from "@/features/tagging";
import { OrganismRef } from "@/shared/components/common/organism-ref";
import { Badge } from "@/shared/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { useBreadcrumbOverride } from "@/shared/lib/stores/breadcrumb-store";
import { Database, ExternalLink } from "lucide-react";
import Link from "next/link";
import { useProteome } from "../hooks/use-proteomes";
import { PROTEOME_TYPE_LABELS } from "../types";

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
    <div className="flex flex-col gap-6" aria-label="Loading proteome detail">
      <div className="flex flex-col gap-2">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-64" />
      </div>
      <Skeleton className="h-48 w-full rounded-xl" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

export interface ProteomeDetailPageProps {
  proteomeId: string;
}

export function ProteomeDetailPage({ proteomeId }: ProteomeDetailPageProps) {
  const { data: proteome, isLoading, isError } = useProteome(proteomeId);
  useBreadcrumbOverride(proteomeId, proteome?.uniprot_proteome_id ?? "");

  // ── Loading ──────────────────────────────────────────────────────────────
  if (isLoading) {
    return <DetailSkeleton />;
  }

  // ── Error / not found ────────────────────────────────────────────────────
  if (isError || !proteome) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-24 text-center text-muted-foreground">
        <Database className="h-12 w-12 opacity-25" aria-hidden="true" />
        <div>
          <p className="text-base font-semibold text-foreground">Proteome not found</p>
          <p className="text-sm mt-1">
            No proteome with ID <span className="font-mono">{proteomeId}</span> could be located in
            the database.
          </p>
        </div>
        <Link href="/proteomes" className="text-sm text-primary underline-offset-4 hover:underline">
          Back to proteomes
        </Link>
      </div>
    );
  }

  // ── Detail view ───────────────────────────────────────────────────────────
  const typeLabel =
    PROTEOME_TYPE_LABELS[proteome.proteome_type as keyof typeof PROTEOME_TYPE_LABELS] ??
    proteome.proteome_type;

  return (
    <div className="flex flex-col gap-8 pb-16">
      {/* ── Page header ── */}
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold tracking-tight text-foreground font-mono">
            {proteome.uniprot_proteome_id}
          </h1>
          {proteome.proteome_url && (
            <a
              href={String(proteome.proteome_url)}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-primary transition-colors"
              aria-label={`View ${proteome.uniprot_proteome_id} on UniProt`}
            >
              <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
              UniProt
            </a>
          )}
          <Badge variant="secondary">{typeLabel}</Badge>
          {proteome.is_reference && <Badge variant="outline">Reference</Badge>}
        </div>
      </header>

      {/* ── Metadata card ── */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base font-semibold text-foreground">
            Proteome Metadata
          </CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="flex flex-col">
            {/* Organism */}
            <MetadataRow label="Organism">
              <OrganismRef id={proteome.organism_id} />
            </MetadataRow>

            {/* Strain */}
            {proteome.strain_id && (
              <MetadataRow label="Strain">
                <Link
                  href={`/strains/${proteome.strain_id}`}
                  className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-0.5 text-xs font-mono text-primary hover:bg-accent hover:text-accent-foreground transition-colors"
                >
                  {String(proteome.strain_id)}
                </Link>
              </MetadataRow>
            )}

            {/* Assembly accession */}
            {proteome.assembly_acc && (
              <MetadataRow label="Assembly">
                <span className="font-mono text-xs">{String(proteome.assembly_acc)}</span>
              </MetadataRow>
            )}

            {/* Source version */}
            {proteome.source_version && (
              <MetadataRow label="Source version">
                <span className="font-mono text-xs">{String(proteome.source_version)}</span>
              </MetadataRow>
            )}
          </dl>
        </CardContent>
      </Card>

      {/* ── Tags ── */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base font-semibold text-foreground">Tags</CardTitle>
        </CardHeader>
        <CardContent>
          <TagsRelation entity="proteomes" id={proteome.id} />
        </CardContent>
      </Card>
    </div>
  );
}
