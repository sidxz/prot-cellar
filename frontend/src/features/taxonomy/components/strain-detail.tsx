"use client";

import { ExternalLink, FlaskConical } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { TagsRelation } from "@/features/tagging";
import { OrganismRef } from "@/shared/components/common/organism-ref";
import { Button } from "@/shared/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import { Skeleton } from "@/shared/components/ui/skeleton";

import { useBreadcrumbOverride } from "@/shared/lib/stores/breadcrumb-store";
import { useStrain } from "../hooks/use-strains";
import { StrainFormDialog } from "./strain-form-dialog";

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
    <div className="flex flex-col gap-6" aria-label="Loading strain detail">
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

export interface StrainDetailPageProps {
  strainId: string;
}

export function StrainDetailPage({ strainId }: StrainDetailPageProps) {
  const { data: strain, isLoading, isError } = useStrain(strainId);
  useBreadcrumbOverride(strainId, strain?.name ?? "");
  const [editOpen, setEditOpen] = useState(false);

  // ── Loading ──────────────────────────────────────────────────────────────
  if (isLoading) {
    return <DetailSkeleton />;
  }

  // ── Error / not found ────────────────────────────────────────────────────
  if (isError || !strain) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-24 text-center text-muted-foreground">
        <FlaskConical className="h-12 w-12 opacity-25" aria-hidden="true" />
        <div>
          <p className="text-base font-semibold text-foreground">Strain not found</p>
          <p className="text-sm mt-1">
            No strain with ID <span className="font-mono">{strainId}</span> could be located in the
            database.
          </p>
        </div>
        <Link href="/strains" className="text-sm text-primary underline-offset-4 hover:underline">
          Back to strains
        </Link>
      </div>
    );
  }

  // ── Detail view ───────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-8 pb-16">
      {/* ── Page header ── */}
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">{strain.name}</h1>
          {strain.is_shared ? (
            <span className="ml-auto text-xs italic text-muted-foreground">
              Reference data — managed by import
            </span>
          ) : (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="ml-auto"
              onClick={() => setEditOpen(true)}
            >
              Edit
            </Button>
          )}
        </div>
      </header>

      {/* ── Metadata card ── */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base font-semibold text-foreground">Strain Metadata</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="flex flex-col">
            {/* Species organism */}
            <MetadataRow label="Species">
              <OrganismRef id={strain.species_organism_id} />
            </MetadataRow>

            {/* NCBI taxon */}
            {strain.ncbi_taxon_id != null && (
              <MetadataRow label="NCBI taxon">
                <a
                  href={`https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=${strain.ncbi_taxon_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 font-mono text-xs text-primary hover:underline underline-offset-4"
                  aria-label={`View NCBI taxon ${strain.ncbi_taxon_id}`}
                >
                  <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                  {strain.ncbi_taxon_id}
                </a>
              </MetadataRow>
            )}

            {/* Isolate */}
            {strain.isolate && (
              <MetadataRow label="Isolate">
                <span>{strain.isolate}</span>
              </MetadataRow>
            )}

            {/* BioSample */}
            {strain.biosample_acc && (
              <MetadataRow label="BioSample">
                <span className="font-mono text-xs">{strain.biosample_acc}</span>
              </MetadataRow>
            )}

            {/* Assembly */}
            {strain.assembly_acc && (
              <MetadataRow label="Assembly">
                <span className="font-mono text-xs">{strain.assembly_acc}</span>
              </MetadataRow>
            )}

            {/* Culture collection */}
            {strain.culture_collection && (
              <MetadataRow label="Culture coll.">
                <span>{strain.culture_collection}</span>
              </MetadataRow>
            )}

            {/* Host organism */}
            {strain.host_organism_id && (
              <MetadataRow label="Host organism">
                <OrganismRef id={strain.host_organism_id} />
              </MetadataRow>
            )}

            {/* Metadata (pretty JSON) */}
            {strain.metadata && (
              <MetadataRow label="Metadata">
                <pre className="text-xs font-mono bg-muted rounded-md p-2 overflow-auto max-h-60 whitespace-pre-wrap">
                  {JSON.stringify(strain.metadata, null, 2)}
                </pre>
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
          <TagsRelation entity="strains" id={strain.id} />
        </CardContent>
      </Card>

      {/* ── Edit dialog ── */}
      <StrainFormDialog strain={strain} open={editOpen} onOpenChange={setEditOpen} />
    </div>
  );
}
