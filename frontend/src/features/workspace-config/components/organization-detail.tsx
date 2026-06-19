"use client";

import { Building2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import { Skeleton } from "@/shared/components/ui/skeleton";

import { useOrganization } from "../hooks/use-organizations";
import { ORG_TYPE_LABELS } from "../types";
import { OrganizationFormDialog } from "./organization-form-dialog";

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
    <div className="flex flex-col gap-6" aria-label="Loading organization detail">
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

export interface OrganizationDetailPageProps {
  organizationId: string;
}

export function OrganizationDetailPage({ organizationId }: OrganizationDetailPageProps) {
  const { data: org, isLoading, isError } = useOrganization(organizationId);
  const [editOpen, setEditOpen] = useState(false);

  // ── Loading ──────────────────────────────────────────────────────────────
  if (isLoading) {
    return <DetailSkeleton />;
  }

  // ── Error / not found ────────────────────────────────────────────────────
  if (isError || !org) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-24 text-center text-muted-foreground">
        <Building2 className="h-12 w-12 opacity-25" aria-hidden="true" />
        <div>
          <p className="text-base font-semibold text-foreground">Organization not found</p>
          <p className="text-sm mt-1">
            No organization with ID <span className="font-mono">{organizationId}</span> could be
            located.
          </p>
        </div>
        <Link
          href="/admin/organizations"
          className="text-sm text-primary underline-offset-4 hover:underline"
        >
          Back to organizations
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
          <h1 className="text-2xl font-bold tracking-tight text-foreground">{org.name}</h1>
          <Badge variant="secondary">{ORG_TYPE_LABELS[org.org_type]}</Badge>
          <Badge variant={org.is_active ? "default" : "secondary"}>
            {org.is_active ? "Active" : "Inactive"}
          </Badge>
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

      {/* ── Metadata card ── */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base font-semibold text-foreground">
            Organization Details
          </CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="flex flex-col">
            <MetadataRow label="Type">{ORG_TYPE_LABELS[org.org_type]}</MetadataRow>
            <MetadataRow label="Status">{org.is_active ? "Active" : "Inactive"}</MetadataRow>
            {org.contact_name && <MetadataRow label="Contact">{org.contact_name}</MetadataRow>}
            {org.contact_email && (
              <MetadataRow label="Email">
                <a
                  href={`mailto:${org.contact_email}`}
                  className="text-primary underline-offset-2 hover:underline"
                >
                  {org.contact_email}
                </a>
              </MetadataRow>
            )}
            {org.notes && (
              <MetadataRow label="Notes">
                <span className="whitespace-pre-wrap">{org.notes}</span>
              </MetadataRow>
            )}
            <MetadataRow label="Workspace">
              <span className="font-mono text-xs">{org.workspace_id}</span>
            </MetadataRow>
            <MetadataRow label="Version">
              <span className="font-mono text-xs">{org.version}</span>
            </MetadataRow>
          </dl>
        </CardContent>
      </Card>

      {/* ── Edit dialog ── */}
      <OrganizationFormDialog organization={org} open={editOpen} onOpenChange={setEditOpen} />
    </div>
  );
}
