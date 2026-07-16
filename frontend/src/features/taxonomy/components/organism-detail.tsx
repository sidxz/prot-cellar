"use client";

import { Badge } from "@/shared/components/ui/badge";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { useBreadcrumbOverride } from "@/shared/lib/stores/breadcrumb-store";
import { ExternalLink, Leaf } from "lucide-react";
import Link from "next/link";
import { useOrganism } from "../hooks/use-organisms";
import { NAME_CLASS_LABELS, ORGANISM_SOURCE_LABELS } from "../types";
import { OrganismLineage } from "./organism-lineage";
import { OrganismReferenceStrain } from "./organism-reference-strain";

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function MetadataRow({ label, children }: { label: string; children: React.ReactNode }) {
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
    <div className="flex flex-col gap-6" aria-label="Loading organism detail">
      <div className="flex flex-col gap-2">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-64" />
      </div>
      <Skeleton className="h-56 w-full rounded-xl" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

export interface OrganismDetailPageProps {
  organismId: string;
}

export function OrganismDetailPage({ organismId }: OrganismDetailPageProps) {
  const { data: organism, isLoading, isError } = useOrganism(organismId);
  useBreadcrumbOverride(organismId, organism?.scientific_name ?? "");

  // ── Loading ──────────────────────────────────────────────────────────────
  if (isLoading) {
    return <DetailSkeleton />;
  }

  // ── Error / not found ────────────────────────────────────────────────────
  if (isError || !organism) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-24 text-center text-muted-foreground">
        <Leaf className="h-12 w-12 opacity-25" />
        <div>
          <p className="text-base font-semibold text-foreground">Organism not found</p>
          <p className="text-sm mt-1">
            No organism with ID <span className="font-mono">{organismId}</span> could be located in
            the database.
          </p>
        </div>
        <Link href="/organisms" className="text-sm text-primary underline-offset-4 hover:underline">
          Back to organisms
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
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            {organism.scientific_name}
          </h1>
          {organism.rank && <Badge variant="secondary">{organism.rank}</Badge>}
          {organism.ncbi_url && (
            <a
              href={organism.ncbi_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-primary transition-colors"
              aria-label="View on NCBI Taxonomy"
            >
              <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
              NCBI
            </a>
          )}
          <Badge variant="outline">{ORGANISM_SOURCE_LABELS[organism.source]}</Badge>
          {organism.is_merged && <Badge variant="destructive">Merged</Badge>}
          {organism.is_merged && organism.merged_into_id && (
            <Link
              href={`/organisms/${organism.merged_into_id}`}
              className="text-xs text-primary underline-offset-2 hover:underline"
            >
              → Merged into
            </Link>
          )}
          {organism.is_deleted && <Badge variant="destructive">Deleted</Badge>}
        </div>

        {/* Ancestor lineage breadcrumb */}
        <OrganismLineage organism={organism} />
      </header>

      {/* ── Names table ── */}
      <section aria-labelledby="names-heading">
        <h2 id="names-heading" className="text-base font-semibold mb-3 text-foreground">
          Names
        </h2>
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b border-border text-left">
              <th
                scope="col"
                className="pb-2 pr-4 text-xs font-medium text-muted-foreground uppercase tracking-wide"
              >
                Name
              </th>
              <th
                scope="col"
                className="pb-2 pr-4 text-xs font-medium text-muted-foreground uppercase tracking-wide"
              >
                Class
              </th>
              <th
                scope="col"
                className="pb-2 text-xs font-medium text-muted-foreground uppercase tracking-wide"
              >
                Preferred
              </th>
            </tr>
          </thead>
          <tbody>
            {organism.names.map((n) => (
              <tr
                key={`${n.name_class}-${n.name}`}
                className="border-b border-border/50 last:border-0"
              >
                <td className="py-1.5 pr-4 text-foreground">{n.name}</td>
                <td className="py-1.5 pr-4 text-muted-foreground">
                  {NAME_CLASS_LABELS[n.name_class]}
                </td>
                <td className="py-1.5 text-foreground">{n.is_preferred ? "★" : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* ── Metadata ── */}
      <section aria-labelledby="metadata-heading">
        <h2 id="metadata-heading" className="text-base font-semibold mb-3 text-foreground">
          Metadata
        </h2>
        <dl className="flex flex-col">
          {organism.parent_id && (
            <MetadataRow label="Parent">
              <Link
                href={`/organisms/${organism.parent_id}`}
                className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-0.5 text-xs font-mono text-primary hover:bg-accent hover:text-accent-foreground transition-colors"
              >
                {organism.parent_id}
              </Link>
            </MetadataRow>
          )}
          {organism.division && <MetadataRow label="Division">{organism.division}</MetadataRow>}
          <MetadataRow label="Reference strain">
            <OrganismReferenceStrain
              organismId={organism.id}
              referenceStrainId={organism.reference_strain_id}
            />
          </MetadataRow>
          {organism.source_release && (
            <MetadataRow label="Source release">{organism.source_release}</MetadataRow>
          )}
        </dl>
      </section>

      {/* direct-children list deferred (no API) */}
    </div>
  );
}
