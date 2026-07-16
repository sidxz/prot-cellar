"use client";

import { useMemo, useState } from "react";

import { generationMethodBadgeVariant } from "@/features/protein-catalog/components/sections/editable-record-table";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/shared/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
import type { PluginManifestResponse } from "@/shared/lib/api/model";

import { PluginRunPanel } from "./plugin-run-panel";
import { usePluginCatalog } from "./use-plugins";

const humanize = (s: string) => s.replace(/_/g, " ");

function PluginCard({ m, onRun }: { m: PluginManifestResponse; onRun: () => void }) {
  const method = m.default_generation_method;
  const isAi = method.startsWith("ai_");
  return (
    <Card className="flex flex-col">
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <CardTitle>{m.name}</CardTitle>
          <Badge variant={generationMethodBadgeVariant(method)}>
            {isAi ? "AI" : humanize(method)}
          </Badge>
        </div>
        <CardDescription>{m.description}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-wrap gap-1.5">
        {m.target_records.map((r) => (
          <Badge key={r} variant="outline">
            {humanize(r)}
          </Badge>
        ))}
        {m.requires_secrets.length > 0 ? <Badge variant="warning">needs config</Badge> : null}
      </CardContent>
      <CardFooter className="mt-auto">
        <Button size="sm" onClick={onRun}>
          Run
        </Button>
      </CardFooter>
    </Card>
  );
}

export function PluginCatalogPage() {
  const { data, isLoading, isError } = usePluginCatalog();
  const [recordFilter, setRecordFilter] = useState<string>("all");
  const [selected, setSelected] = useState<PluginManifestResponse | null>(null);

  const recordTypes = useMemo(() => {
    const set = new Set<string>();
    for (const m of data ?? []) for (const r of m.target_records) set.add(r);
    return [...set];
  }, [data]);

  const visible = useMemo(
    () =>
      (data ?? []).filter((m) => recordFilter === "all" || m.target_records.includes(recordFilter)),
    [data, recordFilter],
  );

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading plugins…</p>;
  if (isError) {
    return (
      <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
        Failed to load plugins.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Plugins</h1>
          <p className="text-sm text-muted-foreground">
            Ingestion sources that fill target-biology records. AI-produced values render blue.
          </p>
        </div>
        <Select value={recordFilter} onValueChange={setRecordFilter}>
          <SelectTrigger aria-label="Filter by record type" className="w-56">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All record types</SelectItem>
            {recordTypes.map((r) => (
              <SelectItem key={r} value={r}>
                {humanize(r)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {visible.map((m) => (
          <PluginCard key={m.id} m={m} onRun={() => setSelected(m)} />
        ))}
      </div>

      {selected ? (
        <PluginRunPanel
          key={selected.id}
          manifest={selected}
          open={selected !== null}
          onOpenChange={(open) => !open && setSelected(null)}
        />
      ) : null}
    </div>
  );
}
