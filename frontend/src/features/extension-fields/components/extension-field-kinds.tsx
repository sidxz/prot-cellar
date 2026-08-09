"use client";

import Link from "next/link";

import { useTargetBiologySchema } from "@/features/protein-catalog/hooks/use-target-biology-schema";
import { Badge } from "@/shared/components/ui/badge";
import { Card, CardFooter, CardHeader, CardTitle } from "@/shared/components/ui/card";

import { useFieldDefs } from "../hooks/use-field-defs";
import { RECORD_KINDS, humanize } from "../types";

/**
 * The eight target-biology record kinds, each linking to its field editor.
 * Kinds are a fixed set — no create/delete here, just a count per kind.
 */
export function ExtensionFieldKinds() {
  const { data: fieldDefs, isLoading, isError } = useFieldDefs();
  const { data: schema } = useTargetBiologySchema();

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }
  if (isError) {
    return (
      <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
        Failed to load extension fields.
      </div>
    );
  }

  const counts = new Map<string, number>();
  for (const f of fieldDefs ?? []) {
    counts.set(f.kind, (counts.get(f.kind) ?? 0) + 1);
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold tracking-tight">Extension fields</h1>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {RECORD_KINDS.map((kind) => {
          const descriptor = schema?.kinds[kind];
          const count = counts.get(kind) ?? 0;
          return (
            <Link key={kind} href={`/admin/extension-fields/${kind}`} className="block h-full">
              <Card className="h-full transition-colors hover:border-primary/50">
                <CardHeader>
                  <CardTitle className="text-base">{descriptor?.label ?? humanize(kind)}</CardTitle>
                </CardHeader>
                <CardFooter className="mt-auto flex items-center justify-between gap-2">
                  <Badge variant="secondary">
                    {count} field{count === 1 ? "" : "s"}
                  </Badge>
                  {descriptor?.attaches_to && (
                    <Badge variant="outline" className="capitalize">
                      {descriptor.attaches_to}
                    </Badge>
                  )}
                </CardFooter>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
