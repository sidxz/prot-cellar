"use client";

import { Skeleton } from "@/shared/components/ui/skeleton";
import { useGetStrainApiV1StrainsStrainIdGet } from "@/shared/lib/api/strains/strains";
import { cn } from "@/shared/lib/utils";
import Link from "next/link";

interface StrainRefProps {
  id: string | null | undefined;
  className?: string;
}

export function StrainRef({ id, className }: StrainRefProps) {
  const { data, isLoading, isError } = useGetStrainApiV1StrainsStrainIdGet(id ?? "", {
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
      <span className={cn("text-muted-foreground text-xs italic", className)}>Unknown strain</span>
    );
  }

  return (
    <Link
      href={`/strains/${id}`}
      className={cn("text-primary hover:underline underline-offset-4", className)}
    >
      {data.name}
    </Link>
  );
}
