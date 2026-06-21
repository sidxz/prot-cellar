"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card";
import type { CommentResponse } from "@/shared/lib/api/model";

import { linkifyPubmed } from "../../lib/linkify";
import { commentsByType } from "../../lib/protein-annotations";
import type { Protein } from "../../types";

const FUNCTION_COMMENTS: { type: string; label: string }[] = [
  { type: "FUNCTION", label: "Function" },
  { type: "CATALYTIC ACTIVITY", label: "Catalytic activity" },
  { type: "COFACTOR", label: "Cofactor" },
  { type: "ACTIVITY REGULATION", label: "Activity regulation" },
  { type: "PATHWAY", label: "Pathway" },
  { type: "SUBUNIT", label: "Subunit structure" },
  { type: "INDUCTION", label: "Induction" },
  { type: "DISRUPTION PHENOTYPE", label: "Disruption phenotype" },
];

/** Safely read a nested string at the given key path from an unknown payload. */
function readString(obj: unknown, ...path: string[]): string | undefined {
  let cur: unknown = obj;
  for (const key of path) {
    if (cur && typeof cur === "object" && key in cur) {
      cur = (cur as Record<string, unknown>)[key];
    } else {
      return undefined;
    }
  }
  return typeof cur === "string" ? cur : undefined;
}

/** Displayable lines for a comment: free text plus common structured payloads. */
export function commentLines(c: CommentResponse): string[] {
  const lines: string[] = [];
  if (c.text) lines.push(c.text);

  const reaction = readString(c.payload, "reaction", "name");
  if (reaction) lines.push(reaction);

  const cofactors =
    c.payload && typeof c.payload === "object"
      ? (c.payload as Record<string, unknown>).cofactors
      : undefined;
  if (Array.isArray(cofactors)) {
    const names = cofactors.map((cf) => readString(cf, "name")).filter(Boolean);
    if (names.length) lines.push(`Cofactors: ${names.join(", ")}`);
  }
  return lines;
}

export function FunctionSection({ protein }: { protein: Protein }) {
  const byType = commentsByType(protein);
  const groups = FUNCTION_COMMENTS.map((g) => ({ ...g, items: byType[g.type] ?? [] })).filter(
    (g) => g.items.length > 0,
  );
  if (groups.length === 0) return null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold">Function</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {groups.map((g) => (
          <div key={g.type} className="flex flex-col gap-1">
            <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {g.label}
            </h3>
            <div className="flex flex-col gap-1.5">
              {g.items.flatMap((c) =>
                commentLines(c).map((line) => (
                  <p key={`${g.type}-${line}`} className="text-sm leading-relaxed text-foreground">
                    {linkifyPubmed(line)}
                  </p>
                )),
              )}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
