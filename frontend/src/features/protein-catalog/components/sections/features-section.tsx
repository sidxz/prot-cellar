"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import type { FeatureResponse } from "@/shared/lib/api/model";

import { featuresByCategory } from "../../lib/protein-annotations";
import type { Protein } from "../../types";

const MAX_ROWS = 15;

function featurePosition(f: FeatureResponse): string {
  if (f.start == null) return "—";
  if (f.end == null || f.end === f.start) return String(f.start);
  return `${f.start}..${f.end}`;
}

export function FeaturesSection({ protein }: { protein: Protein }) {
  const byCategory = featuresByCategory(protein);
  const categories = Object.keys(byCategory);
  if (categories.length === 0) return null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold">Features</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {categories.map((cat) => {
          const rows = byCategory[cat];
          const shown = rows.slice(0, MAX_ROWS);
          return (
            <div key={cat} className="flex flex-col gap-1">
              <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {cat} <span className="text-muted-foreground/70">({rows.length})</span>
              </h3>
              <table className="w-full text-sm">
                <tbody>
                  {shown.map((f, i) => (
                    <tr
                      key={`${f.feature_type}-${f.start}-${i}`}
                      className="border-b border-border/40 last:border-0"
                    >
                      <td className="py-1 pr-3 font-mono text-xs text-muted-foreground whitespace-nowrap align-top">
                        {featurePosition(f)}
                      </td>
                      <td className="py-1 pr-3 align-top whitespace-nowrap">{f.feature_type}</td>
                      <td className="py-1 align-top text-foreground">{f.description ?? ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {rows.length > MAX_ROWS && (
                <p className="text-xs text-muted-foreground italic">
                  +{rows.length - MAX_ROWS} more {cat.toLowerCase()}
                </p>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
