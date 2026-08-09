"use client";

import { Badge } from "@/shared/components/ui/badge";
import type {
  CrispriStrainPatchBody,
  CrispriStrainResponse,
  CrispriStrainWriteBody,
  EssentialityPatchBody,
  EssentialityResponse,
  EssentialityWriteBody,
  HypomorphPatchBody,
  HypomorphResponse,
  HypomorphWriteBody,
  ResistanceMutationPatchBody,
  ResistanceMutationResponse,
  ResistanceMutationWriteBody,
  VulnerabilityPatchBody,
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
import {
  EssentialityCallScale,
  ResistanceLollipop,
  VulnerabilityPanel,
} from "@structflo/components/target-biology";

import { useInvalidateGeneTargetBiology } from "../../hooks/use-target-biology";
import { useTargetBiologySchema } from "../../hooks/use-target-biology-schema";
import { essentialityBadgeVariant } from "./axis-annotations-section";
import {
  type Column,
  EditableRecordTable,
  defaultProvenance,
  extensionColumns,
  humanize,
  isAiGenerated,
  numOrNull,
  provColumns,
  strOrNull,
} from "./editable-record-table";

const dash = (v: string | null | undefined) => v ?? "—";

// ── Essentiality ────────────────────────────────────────────────────────────

type EssDraft = {
  classification: string;
  condition: string;
  method: string;
  confidence: string;
  version?: number;
};
const ESS_EMPTY: EssDraft = {
  classification: EssentialityClass.essential,
  condition: "",
  method: "",
  confidence: "",
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
];

export function EssentialityTable({
  geneId,
  records,
}: {
  geneId: string;
  records: EssentialityResponse[];
}) {
  const onSuccess = useInvalidateGeneTargetBiology(geneId);
  const { data: schema } = useTargetBiologySchema();
  const provenanceFields = schema?.provenance.fields ?? [];
  const extensionFields = schema?.kinds.essentiality?.extension_fields ?? [];
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
      columns={[
        ...ESS_COLUMNS,
        ...extensionColumns<EssentialityResponse>(extensionFields),
        ...provColumns<EssentialityResponse>(),
      ]}
      emptyDraft={ESS_EMPTY}
      provenanceFields={provenanceFields}
      extensionFields={extensionFields}
      toDraft={(e) => ({
        classification: e.classification,
        condition: e.condition ?? "",
        method: e.method ?? "",
        confidence: e.confidence != null ? String(e.confidence) : "",
        version: e.version,
      })}
      toBody={(d): EssentialityPatchBody => ({
        classification: d.classification as EssentialityClass,
        condition: strOrNull(d.condition),
        method: strOrNull(d.method),
        confidence: numOrNull(d.confidence),
        version: d.version,
      })}
      onCreate={(body) =>
        create.mutateAsync({
          geneId,
          data: {
            ...(body as Omit<EssentialityWriteBody, "provenance">),
            provenance: defaultProvenance(provenanceFields),
          },
        })
      }
      onUpdate={(id, body) =>
        update.mutateAsync({ recordId: id, data: body as EssentialityPatchBody })
      }
      onDelete={(id) => remove.mutateAsync({ kind: "essentiality", recordId: id })}
      busy={create.isPending || update.isPending || remove.isPending}
    />
  );
}

// ── Vulnerability ─────────────────────────────────────────────────────────────

type VulnDraft = {
  vulnerability_score: string;
  condition: string;
  method: string;
  confidence: string;
  version?: number;
};
const VULN_EMPTY: VulnDraft = {
  vulnerability_score: "",
  condition: "",
  method: "",
  confidence: "",
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
];

export function VulnerabilityTable({
  geneId,
  records,
}: {
  geneId: string;
  records: VulnerabilityResponse[];
}) {
  const onSuccess = useInvalidateGeneTargetBiology(geneId);
  const { data: schema } = useTargetBiologySchema();
  const provenanceFields = schema?.provenance.fields ?? [];
  const extensionFields = schema?.kinds.vulnerability?.extension_fields ?? [];
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
      columns={[
        ...VULN_COLUMNS,
        ...extensionColumns<VulnerabilityResponse>(extensionFields),
        ...provColumns<VulnerabilityResponse>(),
      ]}
      emptyDraft={VULN_EMPTY}
      provenanceFields={provenanceFields}
      extensionFields={extensionFields}
      toDraft={(v) => ({
        vulnerability_score: v.vulnerability_score != null ? String(v.vulnerability_score) : "",
        condition: v.condition ?? "",
        method: v.method ?? "",
        confidence: v.confidence != null ? String(v.confidence) : "",
        version: v.version,
      })}
      toBody={(d): VulnerabilityPatchBody => ({
        vulnerability_score: numOrNull(d.vulnerability_score),
        condition: strOrNull(d.condition),
        method: strOrNull(d.method),
        confidence: numOrNull(d.confidence),
        version: d.version,
      })}
      onCreate={(body) =>
        create.mutateAsync({
          geneId,
          data: {
            ...(body as Omit<VulnerabilityWriteBody, "provenance">),
            provenance: defaultProvenance(provenanceFields),
          },
        })
      }
      onUpdate={(id, body) =>
        update.mutateAsync({ recordId: id, data: body as VulnerabilityPatchBody })
      }
      onDelete={(id) => remove.mutateAsync({ kind: "vulnerability", recordId: id })}
      busy={create.isPending || update.isPending || remove.isPending}
    />
  );
}

// ── Hypomorph ─────────────────────────────────────────────────────────────────

type HypoDraft = {
  growth_defect: boolean;
  growth_defect_severity: string;
  condition: string;
  method: string;
  version?: number;
};
const HYPO_EMPTY: HypoDraft = {
  growth_defect: true,
  growth_defect_severity: "",
  condition: "",
  method: "",
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
];

export function HypomorphTable({
  geneId,
  records,
}: {
  geneId: string;
  records: HypomorphResponse[];
}) {
  const onSuccess = useInvalidateGeneTargetBiology(geneId);
  const { data: schema } = useTargetBiologySchema();
  const provenanceFields = schema?.provenance.fields ?? [];
  const extensionFields = schema?.kinds.hypomorph?.extension_fields ?? [];
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
      columns={[
        ...HYPO_COLUMNS,
        ...extensionColumns<HypomorphResponse>(extensionFields),
        ...provColumns<HypomorphResponse>(),
      ]}
      emptyDraft={HYPO_EMPTY}
      provenanceFields={provenanceFields}
      extensionFields={extensionFields}
      toDraft={(h) => ({
        growth_defect: h.growth_defect,
        growth_defect_severity: h.growth_defect_severity ?? "",
        condition: h.condition ?? "",
        method: h.method ?? "",
        version: h.version,
      })}
      toBody={(d): HypomorphPatchBody => ({
        growth_defect: d.growth_defect,
        growth_defect_severity: strOrNull(d.growth_defect_severity),
        condition: strOrNull(d.condition),
        method: strOrNull(d.method),
        version: d.version,
      })}
      onCreate={(body) =>
        create.mutateAsync({
          geneId,
          data: {
            ...(body as Omit<HypomorphWriteBody, "provenance">),
            provenance: defaultProvenance(provenanceFields),
          },
        })
      }
      onUpdate={(id, body) =>
        update.mutateAsync({ recordId: id, data: body as HypomorphPatchBody })
      }
      onDelete={(id) => remove.mutateAsync({ kind: "hypomorph", recordId: id })}
      busy={create.isPending || update.isPending || remove.isPending}
    />
  );
}

// ── CRISPRi strain ────────────────────────────────────────────────────────────

type CrispriDraft = {
  name: string;
  version?: number;
};
const CRISPRI_EMPTY: CrispriDraft = { name: "" };
const CRISPRI_COLUMNS: Column<CrispriStrainResponse, CrispriDraft>[] = [
  {
    label: "Name",
    field: "name",
    type: "text",
    placeholder: "strain name",
    render: (r) => <span className="font-mono text-xs">{r.name}</span>,
  },
];

export function CrispriStrainTable({
  geneId,
  records,
}: {
  geneId: string;
  records: CrispriStrainResponse[];
}) {
  const onSuccess = useInvalidateGeneTargetBiology(geneId);
  const { data: schema } = useTargetBiologySchema();
  const provenanceFields = schema?.provenance.fields ?? [];
  const extensionFields = schema?.kinds.crispri_strain?.extension_fields ?? [];
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
      columns={[
        ...CRISPRI_COLUMNS,
        ...extensionColumns<CrispriStrainResponse>(extensionFields),
        ...provColumns<CrispriStrainResponse>(),
      ]}
      emptyDraft={CRISPRI_EMPTY}
      provenanceFields={provenanceFields}
      extensionFields={extensionFields}
      toDraft={(s) => ({ name: s.name, version: s.version })}
      toBody={(d): CrispriStrainPatchBody => ({ name: d.name, version: d.version })}
      onCreate={(body) =>
        create.mutateAsync({
          geneId,
          data: {
            ...(body as Omit<CrispriStrainWriteBody, "provenance">),
            provenance: defaultProvenance(provenanceFields),
          },
        })
      }
      onUpdate={(id, body) =>
        update.mutateAsync({ recordId: id, data: body as CrispriStrainPatchBody })
      }
      onDelete={(id) => remove.mutateAsync({ kind: "crispri_strain", recordId: id })}
      busy={create.isPending || update.isPending || remove.isPending}
    />
  );
}

// ── Resistance mutation ───────────────────────────────────────────────────────

type ResDraft = {
  mutation: string;
  mic_shift: string;
  parent_strain: string;
  protein_coordinate: string;
  method: string;
  version?: number;
};
const RES_EMPTY: ResDraft = {
  mutation: "",
  mic_shift: "",
  parent_strain: "",
  protein_coordinate: "",
  method: "",
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
];

export function ResistanceMutationTable({
  geneId,
  records,
}: {
  geneId: string;
  records: ResistanceMutationResponse[];
}) {
  const onSuccess = useInvalidateGeneTargetBiology(geneId);
  const { data: schema } = useTargetBiologySchema();
  const provenanceFields = schema?.provenance.fields ?? [];
  const extensionFields = schema?.kinds.resistance_mutation?.extension_fields ?? [];
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
      columns={[
        ...RES_COLUMNS,
        ...extensionColumns<ResistanceMutationResponse>(extensionFields),
        ...provColumns<ResistanceMutationResponse>(),
      ]}
      emptyDraft={RES_EMPTY}
      provenanceFields={provenanceFields}
      extensionFields={extensionFields}
      toDraft={(m) => ({
        mutation: m.mutation,
        mic_shift: m.mic_shift != null ? String(m.mic_shift) : "",
        parent_strain: m.parent_strain ?? "",
        protein_coordinate: m.protein_coordinate ?? "",
        method: m.method ?? "",
        version: m.version,
      })}
      toBody={(d): ResistanceMutationPatchBody => ({
        mutation: d.mutation,
        mic_shift: numOrNull(d.mic_shift),
        parent_strain: strOrNull(d.parent_strain),
        protein_coordinate: strOrNull(d.protein_coordinate),
        method: strOrNull(d.method),
        version: d.version,
      })}
      onCreate={(body) =>
        create.mutateAsync({
          geneId,
          data: {
            ...(body as Omit<ResistanceMutationWriteBody, "provenance">),
            provenance: defaultProvenance(provenanceFields),
          },
        })
      }
      onUpdate={(id, body) =>
        update.mutateAsync({ recordId: id, data: body as ResistanceMutationPatchBody })
      }
      onDelete={(id) => remove.mutateAsync({ kind: "resistance_mutation", recordId: id })}
      busy={create.isPending || update.isPending || remove.isPending}
    />
  );
}
