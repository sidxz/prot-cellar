"use client";

import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import { Input } from "@/shared/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
import type { EssentialityResponse, EssentialityWriteBody } from "@/shared/lib/api/model";
import { EssentialityClass, ProvenanceSourceType } from "@/shared/lib/api/model";
import { Check, Loader2, Pencil, Plus, Trash2, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { useEssentialityMutations } from "../../hooks/use-target-biology";
import { essentialityBadgeVariant } from "./axis-annotations-section";

const CLASS_OPTIONS = Object.values(EssentialityClass);
const SOURCE_OPTIONS = Object.values(ProvenanceSourceType);
const NEW = "new";
const humanize = (s: string) => s.replace(/_/g, " ");

interface Draft {
  classification: EssentialityClass;
  condition: string;
  method: string;
  confidence: string;
  source_type: ProvenanceSourceType;
  pmid: string;
  note: string;
}

const EMPTY: Draft = {
  classification: EssentialityClass.essential,
  condition: "",
  method: "",
  confidence: "",
  source_type: ProvenanceSourceType.published,
  pmid: "",
  note: "",
};

function toDraft(e: EssentialityResponse): Draft {
  return {
    classification: e.classification as EssentialityClass,
    condition: e.condition ?? "",
    method: e.method ?? "",
    confidence: e.confidence != null ? String(e.confidence) : "",
    source_type: e.provenance.source_type as ProvenanceSourceType,
    pmid: e.provenance.citations[0]?.pmid ?? "",
    note: e.provenance.note ?? "",
  };
}

function toBody(d: Draft): EssentialityWriteBody {
  return {
    classification: d.classification,
    condition: d.condition.trim() || null,
    method: d.method.trim() || null,
    confidence: d.confidence.trim() ? Number(d.confidence) : null,
    provenance: {
      source_type: d.source_type,
      citations: d.pmid.trim() ? [{ pmid: d.pmid.trim() }] : [],
      note: d.note.trim() || null,
    },
  };
}

function errMsg(e: unknown): string {
  const detail = (e as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  return "Could not save. You may need an admin role.";
}

const TH =
  "px-2 py-1.5 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground";
const TD = "px-2 py-1.5 align-top";

export function EssentialityTable({
  geneId,
  records,
}: {
  geneId: string;
  records: EssentialityResponse[];
}) {
  const { create, update, remove } = useEssentialityMutations(geneId);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const busy = create.isPending || update.isPending || remove.isPending;

  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setDraft((d) => ({ ...d, [k]: v }));

  async function save() {
    const body = toBody(draft);
    try {
      if (editingId === NEW) {
        await create.mutateAsync({ geneId, data: body });
        toast.success("Essentiality record added");
      } else if (editingId) {
        await update.mutateAsync({ recordId: editingId, data: body });
        toast.success("Essentiality record updated");
      }
      setEditingId(null);
    } catch (e) {
      toast.error(errMsg(e));
    }
  }

  async function del(id: string) {
    if (!window.confirm("Delete this essentiality record?")) return;
    try {
      await remove.mutateAsync({ recordId: id });
      toast.success("Essentiality record deleted");
    } catch (e) {
      toast.error(errMsg(e));
    }
  }

  const editRow = (key: string) => (
    <tr key={key} className="border-t border-border bg-muted/30">
      <td className={TD}>
        <Select
          value={draft.classification}
          onValueChange={(v) => set("classification", v as EssentialityClass)}
        >
          <SelectTrigger className="h-8 w-full capitalize">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {CLASS_OPTIONS.map((c) => (
              <SelectItem key={c} value={c} className="capitalize">
                {humanize(c)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </td>
      <td className={TD}>
        <Input
          className="h-8"
          value={draft.condition}
          onChange={(e) => set("condition", e.target.value)}
          placeholder="e.g. in vitro 7H9"
        />
      </td>
      <td className={TD}>
        <Input
          className="h-8"
          value={draft.method}
          onChange={(e) => set("method", e.target.value)}
          placeholder="e.g. TnSeq"
        />
      </td>
      <td className={TD}>
        <Input
          className="h-8 w-20"
          type="number"
          min={0}
          max={1}
          step={0.01}
          value={draft.confidence}
          onChange={(e) => set("confidence", e.target.value)}
          placeholder="0–1"
        />
      </td>
      <td className={TD}>
        <Select
          value={draft.source_type}
          onValueChange={(v) => set("source_type", v as ProvenanceSourceType)}
        >
          <SelectTrigger className="h-8 w-full capitalize">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {SOURCE_OPTIONS.map((s) => (
              <SelectItem key={s} value={s} className="capitalize">
                {humanize(s)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </td>
      <td className={TD}>
        <Input
          className="h-8 w-24"
          value={draft.pmid}
          onChange={(e) => set("pmid", e.target.value)}
          placeholder="PMID"
        />
      </td>
      <td className={TD}>
        <Input
          className="h-8"
          value={draft.note}
          onChange={(e) => set("note", e.target.value)}
          placeholder="Note"
        />
      </td>
      <td className={`${TD} whitespace-nowrap`}>
        <Button size="icon" variant="ghost" className="h-7 w-7" onClick={save} disabled={busy}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
          <span className="sr-only">Save</span>
        </Button>
        <Button
          size="icon"
          variant="ghost"
          className="h-7 w-7"
          onClick={() => setEditingId(null)}
          disabled={busy}
        >
          <X className="h-4 w-4" />
          <span className="sr-only">Cancel</span>
        </Button>
      </td>
    </tr>
  );

  return (
    <section aria-labelledby="essentiality-heading" className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h3 id="essentiality-heading" className="text-sm font-semibold text-foreground">
          Essentiality
        </h3>
        <Button
          size="sm"
          variant="outline"
          className="h-7 gap-1"
          onClick={() => {
            setDraft(EMPTY);
            setEditingId(NEW);
          }}
          disabled={editingId === NEW}
        >
          <Plus className="h-3.5 w-3.5" />
          Add
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        Whether the gene is required for growth — a core target-validation signal.
      </p>
      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-muted/40">
              <th className={TH}>Classification</th>
              <th className={TH}>Condition</th>
              <th className={TH}>Method</th>
              <th className={TH}>Conf.</th>
              <th className={TH}>Source</th>
              <th className={TH}>Reference</th>
              <th className={TH}>Note</th>
              <th className={`${TH} w-16`}>&nbsp;</th>
            </tr>
          </thead>
          <tbody>
            {editingId === NEW && editRow(NEW)}
            {records.length === 0 && editingId !== NEW && (
              <tr className="border-t border-border">
                <td className="px-2 py-3 text-xs italic text-muted-foreground" colSpan={8}>
                  No essentiality records yet.
                </td>
              </tr>
            )}
            {records.map((e) =>
              editingId === e.id ? (
                editRow(e.id)
              ) : (
                <tr key={e.id} className="border-t border-border">
                  <td className={TD}>
                    <Badge
                      variant={essentialityBadgeVariant(e.classification)}
                      className="font-normal capitalize"
                    >
                      {humanize(e.classification)}
                    </Badge>
                  </td>
                  <td className={`${TD} text-foreground`}>{e.condition ?? "—"}</td>
                  <td className={`${TD} text-foreground`}>{e.method ?? "—"}</td>
                  <td className={`${TD} font-mono text-xs text-foreground`}>
                    {e.confidence != null ? e.confidence.toFixed(2) : "—"}
                  </td>
                  <td className={`${TD} text-xs uppercase text-muted-foreground`}>
                    {humanize(e.provenance.source_type)}
                  </td>
                  <td className={TD}>
                    {e.provenance.citations[0]?.pmid ? (
                      <a
                        href={`https://pubmed.ncbi.nlm.nih.gov/${e.provenance.citations[0].pmid}/`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:underline"
                      >
                        PMID:{e.provenance.citations[0].pmid}
                      </a>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className={`${TD} text-muted-foreground`}>{e.provenance.note ?? "—"}</td>
                  <td className={`${TD} whitespace-nowrap`}>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-7 w-7"
                      onClick={() => {
                        setDraft(toDraft(e));
                        setEditingId(e.id);
                      }}
                      disabled={busy}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                      <span className="sr-only">Edit</span>
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-7 w-7 text-destructive hover:text-destructive"
                      onClick={() => del(e.id)}
                      disabled={busy}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      <span className="sr-only">Delete</span>
                    </Button>
                  </td>
                </tr>
              ),
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
