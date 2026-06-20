"use client";

import { Badge } from "@/shared/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";

import type { Protein } from "../../types";

export function KeywordsSection({ protein }: { protein: Protein }) {
  const keywords = protein.keyword_refs ?? [];
  if (keywords.length === 0) return null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold">Keywords</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-1.5">
          {keywords.map((kw) => (
            <Badge
              key={kw.kw_id}
              variant="secondary"
              className="font-normal"
              title={kw.category ?? undefined}
            >
              {kw.name || kw.kw_id}
            </Badge>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
