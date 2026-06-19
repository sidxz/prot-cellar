"use client";

import { Skeleton } from "@/shared/components/ui/skeleton";
import { useGetOrganismApiV1OrganismsOrganismIdGet } from "@/shared/lib/api/organisms/organisms";
import { cn } from "@/shared/lib/utils";
import Link from "next/link";

interface OrganismRefProps {
  id: string | null | undefined;
  className?: string;
}

export function OrganismRef({ id, className }: OrganismRefProps) {
  const { data, isLoading, isError } = useGetOrganismApiV1OrganismsOrganismIdGet(id ?? "", {
    query: { enabled: !!id },
  });

  if (!id) {
    return <span className={cn("text-muted-foreground", className)}>—</span>;
  }

  if (isLoading) {
    return <Skeleton className={cn("inline-block h-4 w-24", className)} />;
  }

  if (isError || !data) {
    return (
      <span className={cn("text-muted-foreground font-mono text-xs", className)}>
        {id.slice(0, 8)}
      </span>
    );
  }

  return (
    <Link
      href={`/organisms/${id}`}
      className={cn("text-primary hover:underline underline-offset-4", className)}
    >
      {data.scientific_name}
    </Link>
  );
}
