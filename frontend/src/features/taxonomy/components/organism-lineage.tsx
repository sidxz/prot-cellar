"use client";

import { Skeleton } from "@/shared/components/ui/skeleton";
import Link from "next/link";
import { Fragment } from "react";
import { useOrganismLineage } from "../hooks/use-organisms";
import type { Organism } from "../types";

interface OrganismLineageProps {
  organism: Organism;
}

export function OrganismLineage({ organism }: OrganismLineageProps) {
  const { data, isLoading } = useOrganismLineage(organism);

  if (!organism.parent_id) {
    return null;
  }

  if (isLoading) {
    return (
      <nav aria-label="Lineage">
        <Skeleton className="h-4 w-64" />
      </nav>
    );
  }

  return (
    <nav
      aria-label="Lineage"
      className="flex items-center gap-1 flex-wrap text-sm text-muted-foreground"
    >
      {(data ?? []).map((a) => (
        <Fragment key={a.id}>
          <Link href={`/organisms/${a.id}`} className="hover:text-foreground transition-colors">
            {a.scientific_name}
          </Link>
          <span aria-hidden="true">›</span>
        </Fragment>
      ))}
      <span className="text-foreground font-medium">{organism.scientific_name}</span>
    </nav>
  );
}
