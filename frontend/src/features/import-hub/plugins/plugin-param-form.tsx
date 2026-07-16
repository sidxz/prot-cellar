"use client";

import { Input } from "@/shared/components/ui/input";
import { Label } from "@/shared/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
import type { ParamFieldResponse } from "@/shared/lib/api/model";

import { OrganismCombobox } from "../components/organism-combobox";
import { useUploadEssentiality } from "../hooks/use-imports";

type Values = Record<string, unknown>;

interface PluginParamFormProps {
  params: ParamFieldResponse[];
  values: Values;
  onChange: (next: Values) => void;
}

export function PluginParamForm({ params, values, onChange }: PluginParamFormProps) {
  const upload = useUploadEssentiality();
  const set = (key: string, value: unknown) => onChange({ ...values, [key]: value });

  async function handleFile(key: string, file: File | undefined) {
    if (!file) return;
    // orval types the multipart body field `file` as string; cast to satisfy tsc.
    const res = await upload.mutateAsync({ data: { file: file as unknown as string } });
    set(key, res.upload_ref);
  }

  return (
    <div className="flex flex-col gap-4">
      {params.map((pf) => (
        <div key={pf.key} className="grid gap-1.5">
          <Label htmlFor={pf.key}>
            {pf.label}
            {pf.required ? <span className="text-destructive"> *</span> : null}
          </Label>

          {pf.type === "organism" ? (
            <OrganismCombobox onSelect={(id) => set(pf.key, id)} />
          ) : pf.type === "enum" ? (
            <Select value={(values[pf.key] as string) ?? ""} onValueChange={(v) => set(pf.key, v)}>
              <SelectTrigger id={pf.key} aria-label={pf.label}>
                <SelectValue placeholder="Select…" />
              </SelectTrigger>
              <SelectContent>
                {(pf.options ?? []).map((o) => (
                  <SelectItem key={o} value={o}>
                    {o}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : pf.type === "bool" ? (
            <input
              id={pf.key}
              type="checkbox"
              className="size-4"
              checked={Boolean(values[pf.key])}
              onChange={(e) => set(pf.key, e.target.checked)}
            />
          ) : pf.type === "file_upload" ? (
            <Input
              id={pf.key}
              type="file"
              onChange={(e) => handleFile(pf.key, e.target.files?.[0])}
            />
          ) : (
            <Input
              id={pf.key}
              type={pf.type === "number" ? "number" : "text"}
              value={(values[pf.key] as string) ?? ""}
              onChange={(e) => set(pf.key, e.target.value)}
            />
          )}

          {pf.help ? <p className="text-xs text-muted-foreground">{pf.help}</p> : null}
        </div>
      ))}
    </div>
  );
}
