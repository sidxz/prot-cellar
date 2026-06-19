import type { CrossReferenceResponse } from "@/shared/lib/api/model/crossReferenceResponse";
import { cn } from "@/shared/lib/utils";

/** Subset of CrossReferenceResponse used by this component. */
export type CrossReference = Pick<CrossReferenceResponse, "database" | "accession" | "url">;

export interface CrossReferenceLinksProps {
  items: CrossReference[];
  className?: string;
}

/** Group items by database name, preserving insertion order. */
function groupByDatabase(items: CrossReference[]): Map<string, CrossReference[]> {
  const map = new Map<string, CrossReference[]>();
  for (const item of items) {
    const group = map.get(item.database) ?? [];
    group.push(item);
    map.set(item.database, group);
  }
  return map;
}

export function CrossReferenceLinks({ items, className }: CrossReferenceLinksProps) {
  if (items.length === 0) return null;

  const groups = groupByDatabase(items);

  return (
    <dl className={cn("flex flex-col gap-3", className)}>
      {Array.from(groups.entries()).map(([database, refs]) => (
        <div key={database} className="flex flex-col gap-1">
          <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {database}
          </dt>
          <dd className="flex flex-wrap gap-1.5">
            {refs.map((ref) =>
              ref.url ? (
                <a
                  key={`${ref.database}-${ref.accession}`}
                  href={ref.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center rounded-md border border-border px-2 py-0.5 font-mono text-xs text-primary hover:bg-accent hover:text-accent-foreground transition-colors"
                >
                  {ref.accession}
                </a>
              ) : (
                <span
                  key={`${ref.database}-${ref.accession}`}
                  className="inline-flex items-center rounded-md border border-border px-2 py-0.5 font-mono text-xs text-muted-foreground"
                >
                  {ref.accession}
                </span>
              ),
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}
