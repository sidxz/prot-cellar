"use client";

import { ExternalLink, Target as TargetIcon } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { OrganismRef } from "@/shared/components/common/organism-ref";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import { Skeleton } from "@/shared/components/ui/skeleton";
import { CrossReferenceLinks } from "@/shared/components/xrefs/cross-reference-links";

import { useBreadcrumbOverride } from "@/shared/lib/stores/breadcrumb-store";
import { useTarget } from "../hooks/use-targets";
import { RELATIONSHIP_LABELS, TARGET_TYPE_LABELS } from "../types";
import type { Target } from "../types";
import { TargetFormDialog } from "./target-form-dialog";

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
    <div className="flex flex-col gap-6" aria-label="Loading target detail">
      <div className="flex flex-col gap-2">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-64" />
      </div>
      <Skeleton className="h-48 w-full rounded-xl" />
      <Skeleton className="h-32 w-full rounded-xl" />
      <Skeleton className="h-24 w-full rounded-xl" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Components table
// ---------------------------------------------------------------------------

interface ComponentsTableProps {
  target: Target;
}

function ComponentsTable({ target }: ComponentsTableProps) {
  const { components, target_type } = target;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold text-foreground">
          Protein Components{" "}
          <span className="ml-1 text-muted-foreground font-normal text-sm">
            ({components.length} · {TARGET_TYPE_LABELS[target_type] ?? target_type})
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        {components.length === 0 ? (
          <p className="text-sm text-muted-foreground italic">No components defined.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left">
                  <th
                    scope="col"
                    className="pb-2 pr-4 text-xs font-semibold uppercase tracking-wide text-muted-foreground"
                  >
                    Protein
                  </th>
                  <th
                    scope="col"
                    className="pb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground"
                  >
                    Relationship
                  </th>
                </tr>
              </thead>
              <tbody>
                {components.map((comp) => (
                  <tr
                    key={comp.id}
                    className="border-b border-border/50 last:border-0 hover:bg-muted/30 transition-colors"
                  >
                    <td className="py-2 pr-4">
                      {/* Links by protein id; accession cross-linking is refined when
                          protein-id↔accession resolution lands in a future plan. */}
                      <Link
                        href={`/proteins/${comp.protein_id}`}
                        className="font-mono text-xs rounded border border-border px-2 py-0.5 text-primary hover:bg-accent hover:text-accent-foreground transition-colors"
                      >
                        {comp.protein_id}
                      </Link>
                    </td>
                    <td className="py-2">
                      <Badge variant="secondary" className="text-xs">
                        {RELATIONSHIP_LABELS[comp.relationship] ?? comp.relationship}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Metadata card
// ---------------------------------------------------------------------------

interface MetadataCardProps {
  target: Target;
}

function MetadataCard({ target }: MetadataCardProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold text-foreground">Target Metadata</CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="flex flex-col">
          {/* Organism */}
          <MetadataRow label="Organism">
            <OrganismRef id={target.organism_id} />
          </MetadataRow>

          {/* Pharmacological class */}
          {target.pharmacological_class && (
            <MetadataRow label="Pharm. class">
              <span>{target.pharmacological_class}</span>
            </MetadataRow>
          )}

          {/* ChEMBL ID */}
          {target.chembl_id && (
            <MetadataRow label="ChEMBL ID">
              <span className="font-mono text-xs">{target.chembl_id}</span>
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

export interface TargetDetailPageProps {
  targetId: string;
}

export function TargetDetailPage({ targetId }: TargetDetailPageProps) {
  const { data: target, isLoading, isError } = useTarget(targetId);
  useBreadcrumbOverride(targetId, target?.pref_name ?? "");
  const [editOpen, setEditOpen] = useState(false);

  // ── Loading ──────────────────────────────────────────────────────────────
  if (isLoading) {
    return <DetailSkeleton />;
  }

  // ── Error / not found ────────────────────────────────────────────────────
  if (isError || !target) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-24 text-center text-muted-foreground">
        <TargetIcon className="h-12 w-12 opacity-25" aria-hidden="true" />
        <div>
          <p className="text-base font-semibold text-foreground">Target not found</p>
          <p className="text-sm mt-1">
            No target with ID <span className="font-mono">{targetId}</span> could be located in the
            database.
          </p>
        </div>
        <Link href="/targets" className="text-sm text-primary underline-offset-4 hover:underline">
          Back to targets
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
          <h1 className="text-2xl font-bold tracking-tight text-foreground">{target.pref_name}</h1>
          <Badge variant="secondary">
            {TARGET_TYPE_LABELS[target.target_type] ?? target.target_type}
          </Badge>
          {target.chembl_url && (
            <a
              href={target.chembl_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-primary transition-colors"
              aria-label="View on ChEMBL"
            >
              <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
              ChEMBL
            </a>
          )}
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="ml-auto"
            onClick={() => setEditOpen(true)}
          >
            Edit
          </Button>
        </div>
      </header>

      {/* ── Components table ── */}
      <section aria-labelledby="components-heading">
        <h2 id="components-heading" className="sr-only">
          Protein Components
        </h2>
        <ComponentsTable target={target} />
      </section>

      {/* ── Metadata card ── */}
      <MetadataCard target={target} />

      {/* ── Cross-references ── */}
      {target.cross_references && target.cross_references.length > 0 && (
        <section aria-labelledby="xrefs-heading">
          <h2 id="xrefs-heading" className="text-base font-semibold mb-3 text-foreground">
            Cross-References
          </h2>
          <Card>
            <CardContent className="pt-4">
              <CrossReferenceLinks
                // biome-ignore lint/suspicious/noExplicitAny: cast at feature boundary
                items={target.cross_references as any}
              />
            </CardContent>
          </Card>
        </section>
      )}

      {/* ── Edit dialog ── */}
      <TargetFormDialog target={target} open={editOpen} onOpenChange={setEditOpen} />
    </div>
  );
}
