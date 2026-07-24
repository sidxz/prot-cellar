"use client";

import { Badge } from "@/shared/components/ui/badge";
import type {
  CrispriStrainResponse,
  CrispriStrainWriteBody,
  EssentialityResponse,
  EssentialityWriteBody,
  HypomorphResponse,
  HypomorphWriteBody,
  ResistanceMutationResponse,
  ResistanceMutationWriteBody,
  VulnerabilityResponse,
  VulnerabilityWriteBody,
} from "@/shared/lib/api/model";
import { EssentialityClass } from "@/shared/lib/api/model";
import {
  useCreateCrispriStrainApiV1GenesGeneIdTargetBiologyCrispriStrainPost,
  useCreateEssentialityApiV1GenesGeneIdTargetBiologyEssentialityPost,
  useCreateHypomorphApiV1GenesGeneIdTargetBiologyHypomorphPost,
  useCreateResistanceMutationApiV1GenesGeneIdTargetBiologyResistanceMutationPost,
  useCreateVulnerabilityApiV1GenesGeneIdTargetBiologyVulnerabilityPost,
  useDeleteTargetBiologyRecordApiV1TargetBiologyKindRecordIdDelete,
  useUpdateCrispriStrainApiV1TargetBiologyCrispriStrainRecordIdPatch,
  useUpdateEssentialityApiV1TargetBiologyEssentialityRecordIdPatch,
  useUpdateHypomorphApiV1TargetBiologyHypomorphRecordIdPatch,
  useUpdateResistanceMutationApiV1TargetBiologyResistanceMutationRecordIdPatch,
  useUpdateVulnerabilityApiV1TargetBiologyVulnerabilityRecordIdPatch,
} from "@/shared/lib/api/target-biology/target-biology";

import { useInvalidateGeneTargetBiology } from "../../hooks/use-target-biology";
import { essentialityBadgeVariant } from "./axis-annotations-section";
import {
  type Column,
  EMPTY_PROV,
  EditableRecordTable,
  type ProvDraft,
  humanize,
  isAiGenerated,
  numOrNull,
  provColumns,
  provToBody,
  provToDraft,
  strOrNull,
} from "./editable-record-table";
import {
  EssentialityCallScale,
  ResistanceLollipop,
  VulnerabilityPanel,
} from "@structflo/daikon-ui/target-biology";

const dash = (v: string | null | undefined) => v ?? "—";

// ── Essentiality ────────────────────────────────────────────────────────────

type EssDraft = ProvDraft & {
  classification: string;
  condition: string;
  method: string;
  confidence: string;
};
const ESS_EMPTY: EssDraft = {
  classification: EssentialityClass.essential,
  condition: "",
  method: "",
  confidence: "",
  ...EMPTY_PROV,
};
const ESS_COLUMNS: Column<EssentialityResponse, EssDraft>[] = [
  {
    label: "Classification",
    field: "classification",
    type: "enum",
    options: Object.values(EssentialityClass),
    render: (r) => (
      <Badge
        variant={essentialityBadgeVariant(r.classification)}
        className="font-normal capitalize"
      >
        {humanize(r.classification)}
      </Badge>
    ),
  },
  { label: "Condition", field: "condition", type: "text", render: (r) => dash(r.condition) },
  { label: "Method", field: "method", type: "text", render: (r) => dash(r.method) },
  {
    label: "Conf.",
    field: "confidence",
    type: "number",
    placeholder: "0–1",
    render: (r) => (r.confidence != null ? r.confidence.toFixed(2) : "—"),
  },
  ...provColumns<EssentialityResponse>(),
];

export function EssentialityTable({
  geneId,
  records,
}: {
  geneId: string;
  records: EssentialityResponse[];
}) {
  const onSuccess = useInvalidateGeneTargetBiology(geneId);
  const create = useCreateEssentialityApiV1GenesGeneIdTargetBiologyEssentialityPost({
    mutation: { onSuccess },
  });
  const update = useUpdateEssentialityApiV1TargetBiologyEssentialityRecordIdPatch({
    mutation: { onSuccess },
  });
  const remove = useDeleteTargetBiologyRecordApiV1TargetBiologyKindRecordIdDelete({
    mutation: { onSuccess },
  });
  return (
    <EditableRecordTable<EssentialityResponse, EssDraft>
      title="Essentiality"
      description="Whether the gene is required for growth — a core target-validation signal."
      records={records}
      visualization={<EssentialityCallScale records={records} />}
      isAiRow={(r) => isAiGenerated(r.provenance.generation_method)}
      columns={ESS_COLUMNS}
      emptyDraft={ESS_EMPTY}
      toDraft={(e) => ({
        classification: e.classification,
        condition: e.condition ?? "",
        method: e.method ?? "",
        confidence: e.confidence != null ? String(e.confidence) : "",
        ...provToDraft(e.provenance),
      })}
      toBody={(d): EssentialityWriteBody => ({
        classification: d.classification as EssentialityClass,
        condition: strOrNull(d.condition),
        method: strOrNull(d.method),
        confidence: numOrNull(d.confidence),
        provenance: provToBody(d),
      })}
      onCreate={(body) => create.mutateAsync({ geneId, data: body as EssentialityWriteBody })}
      onUpdate={(id, body) =>
        update.mutateAsync({ recordId: id, data: body as EssentialityWriteBody })
      }
      onDelete={(id) => remove.mutateAsync({ kind: "essentiality", recordId: id })}
      busy={create.isPending || update.isPending || remove.isPending}
    />
  );
}

// ── Vulnerability ─────────────────────────────────────────────────────────────

type VulnDraft = ProvDraft & {
  vulnerability_score: string;
  condition: string;
  method: string;
  confidence: string;
};
const VULN_EMPTY: VulnDraft = {
  vulnerability_score: "",
  condition: "",
  method: "",
  confidence: "",
  ...EMPTY_PROV,
};
const VULN_COLUMNS: Column<VulnerabilityResponse, VulnDraft>[] = [
  {
    label: "Score",
    field: "vulnerability_score",
    type: "number",
    placeholder: "0–1",
    render: (r) => (r.vulnerability_score != null ? r.vulnerability_score.toFixed(2) : "—"),
  },
  { label: "Condition", field: "condition", type: "text", render: (r) => dash(r.condition) },
  { label: "Method", field: "method", type: "text", render: (r) => dash(r.method) },
  {
    label: "Conf.",
    field: "confidence",
    type: "number",
    placeholder: "0–1",
    render: (r) => (r.confidence != null ? r.confidence.toFixed(2) : "—"),
  },
  ...provColumns<VulnerabilityResponse>(),
];

export function VulnerabilityTable({
  geneId,
  records,
}: {
  geneId: string;
  records: VulnerabilityResponse[];
}) {
  const onSuccess = useInvalidateGeneTargetBiology(geneId);
  const create = useCreateVulnerabilityApiV1GenesGeneIdTargetBiologyVulnerabilityPost({
    mutation: { onSuccess },
  });
  const update = useUpdateVulnerabilityApiV1TargetBiologyVulnerabilityRecordIdPatch({
    mutation: { onSuccess },
  });
  const remove = useDeleteTargetBiologyRecordApiV1TargetBiologyKindRecordIdDelete({
    mutation: { onSuccess },
  });
  return (
    <EditableRecordTable<VulnerabilityResponse, VulnDraft>
      title="Vulnerability"
      description="A normalized 0–1 score for how much target knockdown impairs growth."
      records={records}
      visualization={<VulnerabilityPanel records={records} />}
      isAiRow={(r) => isAiGenerated(r.provenance.generation_method)}
      columns={VULN_COLUMNS}
      emptyDraft={VULN_EMPTY}
      toDraft={(v) => ({
        vulnerability_score: v.vulnerability_score != null ? String(v.vulnerability_score) : "",
        condition: v.condition ?? "",
        method: v.method ?? "",
        confidence: v.confidence != null ? String(v.confidence) : "",
        ...provToDraft(v.provenance),
      })}
      toBody={(d): VulnerabilityWriteBody => ({
        vulnerability_score: numOrNull(d.vulnerability_score),
        condition: strOrNull(d.condition),
        method: strOrNull(d.method),
        confidence: numOrNull(d.confidence),
        provenance: provToBody(d),
      })}
      onCreate={(body) => create.mutateAsync({ geneId, data: body as VulnerabilityWriteBody })}
      onUpdate={(id, body) =>
        update.mutateAsync({ recordId: id, data: body as VulnerabilityWriteBody })
      }
      onDelete={(id) => remove.mutateAsync({ kind: "vulnerability", recordId: id })}
      busy={create.isPending || update.isPending || remove.isPending}
    />
  );
}

// ── Hypomorph ─────────────────────────────────────────────────────────────────

type HypoDraft = ProvDraft & {
  growth_defect: boolean;
  growth_defect_severity: string;
  condition: string;
  method: string;
};
const HYPO_EMPTY: HypoDraft = {
  growth_defect: true,
  growth_defect_severity: "",
  condition: "",
  method: "",
  ...EMPTY_PROV,
};
const HYPO_COLUMNS: Column<HypomorphResponse, HypoDraft>[] = [
  {
    label: "Growth defect",
    field: "growth_defect",
    type: "bool",
    render: (r) => (
      <Badge variant={r.growth_defect ? "warning" : "secondary"} className="font-normal">
        {r.growth_defect ? "Yes" : "No"}
      </Badge>
    ),
  },
  {
    label: "Severity",
    field: "growth_defect_severity",
    type: "text",
    render: (r) => dash(r.growth_defect_severity),
  },
  { label: "Condition", field: "condition", type: "text", render: (r) => dash(r.condition) },
  { label: "Method", field: "method", type: "text", render: (r) => dash(r.method) },
  ...provColumns<HypomorphResponse>(),
];

export function HypomorphTable({
  geneId,
  records,
}: {
  geneId: string;
  records: HypomorphResponse[];
}) {
  const onSuccess = useInvalidateGeneTargetBiology(geneId);
  const create = useCreateHypomorphApiV1GenesGeneIdTargetBiologyHypomorphPost({
    mutation: { onSuccess },
  });
  const update = useUpdateHypomorphApiV1TargetBiologyHypomorphRecordIdPatch({
    mutation: { onSuccess },
  });
  const remove = useDeleteTargetBiologyRecordApiV1TargetBiologyKindRecordIdDelete({
    mutation: { onSuccess },
  });
  return (
    <EditableRecordTable<HypomorphResponse, HypoDraft>
      title="Hypomorph"
      description="Knockdown phenotype — a partial loss-of-function growth defect."
      records={records}
      isAiRow={(r) => isAiGenerated(r.provenance.generation_method)}
      columns={HYPO_COLUMNS}
      emptyDraft={HYPO_EMPTY}
      toDraft={(h) => ({
        growth_defect: h.growth_defect,
        growth_defect_severity: h.growth_defect_severity ?? "",
        condition: h.condition ?? "",
        method: h.method ?? "",
        ...provToDraft(h.provenance),
      })}
      toBody={(d): HypomorphWriteBody => ({
        growth_defect: d.growth_defect,
        growth_defect_severity: strOrNull(d.growth_defect_severity),
        condition: strOrNull(d.condition),
        method: strOrNull(d.method),
        provenance: provToBody(d),
      })}
      onCreate={(body) => create.mutateAsync({ geneId, data: body as HypomorphWriteBody })}
      onUpdate={(id, body) =>
        update.mutateAsync({ recordId: id, data: body as HypomorphWriteBody })
      }
      onDelete={(id) => remove.mutateAsync({ kind: "hypomorph", recordId: id })}
      busy={create.isPending || update.isPending || remove.isPending}
    />
  );
}

// ── CRISPRi strain ────────────────────────────────────────────────────────────

type CrispriDraft = ProvDraft & {
  name: string;
};
const CRISPRI_EMPTY: CrispriDraft = { name: "", ...EMPTY_PROV };
const CRISPRI_COLUMNS: Column<CrispriStrainResponse, CrispriDraft>[] = [
  {
    label: "Name",
    field: "name",
    type: "text",
    placeholder: "strain name",
    render: (r) => <span className="font-mono text-xs">{r.name}</span>,
  },
  ...provColumns<CrispriStrainResponse>(),
];

export function CrispriStrainTable({
  geneId,
  records,
}: {
  geneId: string;
  records: CrispriStrainResponse[];
}) {
  const onSuccess = useInvalidateGeneTargetBiology(geneId);
  const create = useCreateCrispriStrainApiV1GenesGeneIdTargetBiologyCrispriStrainPost({
    mutation: { onSuccess },
  });
  const update = useUpdateCrispriStrainApiV1TargetBiologyCrispriStrainRecordIdPatch({
    mutation: { onSuccess },
  });
  const remove = useDeleteTargetBiologyRecordApiV1TargetBiologyKindRecordIdDelete({
    mutation: { onSuccess },
  });
  return (
    <EditableRecordTable<CrispriStrainResponse, CrispriDraft>
      title="CRISPRi strain"
      description="A physical knockdown reagent (sgRNA strain) targeting this gene."
      records={records}
      isAiRow={(r) => isAiGenerated(r.provenance.generation_method)}
      columns={CRISPRI_COLUMNS}
      emptyDraft={CRISPRI_EMPTY}
      toDraft={(s) => ({ name: s.name, ...provToDraft(s.provenance) })}
      toBody={(d): CrispriStrainWriteBody => ({ name: d.name, provenance: provToBody(d) })}
      onCreate={(body) => create.mutateAsync({ geneId, data: body as CrispriStrainWriteBody })}
      onUpdate={(id, body) =>
        update.mutateAsync({ recordId: id, data: body as CrispriStrainWriteBody })
      }
      onDelete={(id) => remove.mutateAsync({ kind: "crispri_strain", recordId: id })}
      busy={create.isPending || update.isPending || remove.isPending}
    />
  );
}

// ── Resistance mutation ───────────────────────────────────────────────────────

type ResDraft = ProvDraft & {
  mutation: string;
  mic_shift: string;
  parent_strain: string;
  protein_coordinate: string;
  method: string;
};
const RES_EMPTY: ResDraft = {
  mutation: "",
  mic_shift: "",
  parent_strain: "",
  protein_coordinate: "",
  method: "",
  ...EMPTY_PROV,
};
const RES_COLUMNS: Column<ResistanceMutationResponse, ResDraft>[] = [
  {
    label: "Mutation",
    field: "mutation",
    type: "text",
    placeholder: "e.g. S450L",
    render: (r) => <span className="font-mono text-xs">{r.mutation}</span>,
  },
  {
    // Read-only: compound links to chem-cellar and needs a picker (not inline-editable yet).
    label: "Compound",
    render: (r) =>
      r.compound?.name ? (
        <Badge variant="outline" className="font-normal">
          {r.compound.name}
        </Badge>
      ) : (
        "—"
      ),
  },
  {
    label: "MIC ×",
    field: "mic_shift",
    type: "number",
    render: (r) => (r.mic_shift != null ? `×${r.mic_shift}` : "—"),
  },
  {
    label: "Parent strain",
    field: "parent_strain",
    type: "text",
    render: (r) => dash(r.parent_strain),
  },
  {
    label: "Position",
    field: "protein_coordinate",
    type: "text",
    render: (r) => dash(r.protein_coordinate),
  },
  { label: "Method", field: "method", type: "text", render: (r) => dash(r.method) },
  ...provColumns<ResistanceMutationResponse>(),
];

export function ResistanceMutationTable({
  geneId,
  records,
}: {
  geneId: string;
  records: ResistanceMutationResponse[];
}) {
  const onSuccess = useInvalidateGeneTargetBiology(geneId);
  const create = useCreateResistanceMutationApiV1GenesGeneIdTargetBiologyResistanceMutationPost({
    mutation: { onSuccess },
  });
  const update = useUpdateResistanceMutationApiV1TargetBiologyResistanceMutationRecordIdPatch({
    mutation: { onSuccess },
  });
  const remove = useDeleteTargetBiologyRecordApiV1TargetBiologyKindRecordIdDelete({
    mutation: { onSuccess },
  });
  return (
    <EditableRecordTable<ResistanceMutationResponse, ResDraft>
      title="Resistance mutation"
      description="A heritable variant that confers drug resistance (compound link is read-only for now)."
      records={records}
      visualization={<ResistanceLollipop records={records} />}
      isAiRow={(r) => isAiGenerated(r.provenance.generation_method)}
      columns={RES_COLUMNS}
      emptyDraft={RES_EMPTY}
      toDraft={(m) => ({
        mutation: m.mutation,
        mic_shift: m.mic_shift != null ? String(m.mic_shift) : "",
        parent_strain: m.parent_strain ?? "",
        protein_coordinate: m.protein_coordinate ?? "",
        method: m.method ?? "",
        ...provToDraft(m.provenance),
      })}
      toBody={(d): ResistanceMutationWriteBody => ({
        mutation: d.mutation,
        mic_shift: numOrNull(d.mic_shift),
        parent_strain: strOrNull(d.parent_strain),
        protein_coordinate: strOrNull(d.protein_coordinate),
        method: strOrNull(d.method),
        provenance: provToBody(d),
      })}
      onCreate={(body) => create.mutateAsync({ geneId, data: body as ResistanceMutationWriteBody })}
      onUpdate={(id, body) =>
        update.mutateAsync({ recordId: id, data: body as ResistanceMutationWriteBody })
      }
      onDelete={(id) => remove.mutateAsync({ kind: "resistance_mutation", recordId: id })}
      busy={create.isPending || update.isPending || remove.isPending}
    />
  );
}
