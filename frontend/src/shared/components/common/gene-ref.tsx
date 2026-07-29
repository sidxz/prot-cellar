"use client";

import { Skeleton } from "@/shared/components/ui/skeleton";
import { useGetGeneApiV1GenesGeneIdGet } from "@/shared/lib/api/genes/genes";
import { cn } from "@/shared/lib/utils";
import Link from "next/link";

interface GeneRefProps {
  id: string | null | undefined;
  className?: string;
}

export function GeneRef({ id, className }: GeneRefProps) {
  const { data, isLoading, isError } = useGetGeneApiV1GenesGeneIdGet(id ?? "", {
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
      <span className={cn("text-muted-foreground text-xs italic", className)}>Unknown gene</span>
    );
  }

  // Lead with the gene's preferred display name (the locus/ORF, matching the Genes
  // catalog); keep the symbol as a muted secondary when it differs.
  return (
    <Link
      href={`/genes/${id}`}
      className={cn("font-mono text-primary hover:underline underline-offset-4", className)}
    >
      {data.display_label}
      {data.display_label !== data.primary_name && (
        <span className="text-muted-foreground"> · {data.primary_name}</span>
      )}
    </Link>
  );
}
