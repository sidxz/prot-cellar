"use client";

import { Badge } from "@/shared/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";

import type { Protein } from "../../types";

export function IsoformsSection({ protein }: { protein: Protein }) {
  const isoforms = protein.isoforms ?? [];
  if (isoforms.length === 0) return null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold">Isoforms ({isoforms.length})</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="flex flex-col gap-2">
          {isoforms.map((iso) => (
            <li key={iso.isoform_accession} className="flex flex-col gap-0.5 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs text-primary">{iso.isoform_accession}</span>
                {iso.name && <span className="font-medium">{iso.name}</span>}
                {iso.is_displayed && (
                  <Badge variant="outline" className="text-[10px]">
                    canonical
                  </Badge>
                )}
              </div>
              {iso.note && <span className="text-xs text-muted-foreground">{iso.note}</span>}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
