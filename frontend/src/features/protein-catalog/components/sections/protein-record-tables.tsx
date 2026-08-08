"use client";

import { Badge } from "@/shared/components/ui/badge";
import type {
  ProteinActivityAssayPatchBody,
  ProteinActivityAssayResponse,
  ProteinActivityAssayWriteBody,
  ProteinProductionPatchBody,
  ProteinProductionResponse,
  ProteinProductionWriteBody,
  UnpublishedStructurePatchBody,
  UnpublishedStructureResponse,
  UnpublishedStructureWriteBody,
} from "@/shared/lib/api/model";
import {
  useCreateProteinActivityAssayApiV1ProteinsProteinIdTargetBiologyProteinActivityAssayPost,
  useCreateProteinProductionApiV1ProteinsProteinIdTargetBiologyProteinProductionPost,
  useCreateUnpublishedStructureApiV1ProteinsProteinIdTargetBiologyUnpublishedStructurePost,
  useDeleteTargetBiologyRecordApiV1TargetBiologyKindRecordIdDelete,
  useUpdateProteinActivityAssayApiV1TargetBiologyProteinActivityAssayRecordIdPatch,
  useUpdateProteinProductionApiV1TargetBiologyProteinProductionRecordIdPatch,
  useUpdateUnpublishedStructureApiV1TargetBiologyUnpublishedStructureRecordIdPatch,
} from "@/shared/lib/api/target-biology/target-biology";

import { useInvalidateProteinTargetBiology } from "../../hooks/use-target-biology";
import { useTargetBiologySchema } from "../../hooks/use-target-biology-schema";
import {
  type Column,
  EditableRecordTable,
  isAiGenerated,
  numOrNull,
  provColumns,
  strOrNull,
} from "./editable-record-table";

const dash = (v: string | null | undefined) => v ?? "—";

// ── Protein production ────────────────────────────────────────────────────────

type ProdDraft = {
  status: string;
  expression_host: string;
  purity: string;
  condition: string;
  method: string;
  version?: number;
};
const PROD_EMPTY: ProdDraft = {
  status: "",
  expression_host: "",
  purity: "",
  condition: "",
  method: "",
};
const PROD_COLUMNS: Column<ProteinProductionResponse, ProdDraft>[] = [
  {
    label: "Status",
    field: "status",
    type: "text",
    placeholder: "e.g. purified",
    render: (r) => (
      <Badge variant="secondary" className="font-normal capitalize">
        {r.status}
      </Badge>
    ),
  },
  {
    label: "Host",
    field: "expression_host",
    type: "text",
    render: (r) => dash(r.expression_host),
  },
  {
    label: "Purity",
    field: "purity",
    type: "number",
    render: (r) => (r.purity != null ? String(r.purity) : "—"),
  },
  { label: "Condition", field: "condition", type: "text", render: (r) => dash(r.condition) },
  { label: "Method", field: "method", type: "text", render: (r) => dash(r.method) },
  ...provColumns<ProteinProductionResponse>(),
];

export function ProteinProductionTable({
  proteinId,
  records,
}: {
  proteinId: string;
  records: ProteinProductionResponse[];
}) {
  const onSuccess = useInvalidateProteinTargetBiology(proteinId);
  const { data: schema } = useTargetBiologySchema();
  const create = useCreateProteinProductionApiV1ProteinsProteinIdTargetBiologyProteinProductionPost(
    { mutation: { onSuccess } },
  );
  const update = useUpdateProteinProductionApiV1TargetBiologyProteinProductionRecordIdPatch({
    mutation: { onSuccess },
  });
  const remove = useDeleteTargetBiologyRecordApiV1TargetBiologyKindRecordIdDelete({
    mutation: { onSuccess },
  });
  return (
    <EditableRecordTable<ProteinProductionResponse, ProdDraft>
      title="Protein production"
      description="Recombinant expression / purification record for this protein."
      records={records}
      isAiRow={(r) => isAiGenerated(r.provenance.generation_method)}
      columns={PROD_COLUMNS}
      emptyDraft={PROD_EMPTY}
      provenanceFields={schema?.provenance.fields ?? []}
      toDraft={(p) => ({
        status: p.status,
        expression_host: p.expression_host ?? "",
        purity: p.purity != null ? String(p.purity) : "",
        condition: p.condition ?? "",
        method: p.method ?? "",
        version: p.version,
      })}
      toBody={(d): ProteinProductionPatchBody => ({
        status: d.status,
        expression_host: strOrNull(d.expression_host),
        purity: numOrNull(d.purity),
        condition: strOrNull(d.condition),
        method: strOrNull(d.method),
        version: d.version,
      })}
      onCreate={(body) =>
        create.mutateAsync({ proteinId, data: body as ProteinProductionWriteBody })
      }
      onUpdate={(id, body) =>
        update.mutateAsync({ recordId: id, data: body as ProteinProductionPatchBody })
      }
      onDelete={(id) => remove.mutateAsync({ kind: "protein_production", recordId: id })}
      busy={create.isPending || update.isPending || remove.isPending}
    />
  );
}

// ── Protein activity assay ────────────────────────────────────────────────────

type AssayDraft = {
  activity_measured: string;
  readout: string;
  throughput: string;
  condition: string;
  method: string;
  version?: number;
};
const ASSAY_EMPTY: AssayDraft = {
  activity_measured: "",
  readout: "",
  throughput: "",
  condition: "",
  method: "",
};
const ASSAY_COLUMNS: Column<ProteinActivityAssayResponse, AssayDraft>[] = [
  {
    label: "Activity",
    field: "activity_measured",
    type: "text",
    placeholder: "e.g. ATPase activity",
    render: (r) => r.activity_measured,
  },
  {
    label: "Readout",
    field: "readout",
    type: "text",
    render: (r) =>
      r.readout ? (
        <Badge variant="outline" className="font-normal">
          {r.readout}
        </Badge>
      ) : (
        "—"
      ),
  },
  { label: "Throughput", field: "throughput", type: "text", render: (r) => dash(r.throughput) },
  { label: "Condition", field: "condition", type: "text", render: (r) => dash(r.condition) },
  { label: "Method", field: "method", type: "text", render: (r) => dash(r.method) },
  ...provColumns<ProteinActivityAssayResponse>(),
];

export function ProteinActivityAssayTable({
  proteinId,
  records,
}: {
  proteinId: string;
  records: ProteinActivityAssayResponse[];
}) {
  const onSuccess = useInvalidateProteinTargetBiology(proteinId);
  const { data: schema } = useTargetBiologySchema();
  const create =
    useCreateProteinActivityAssayApiV1ProteinsProteinIdTargetBiologyProteinActivityAssayPost({
      mutation: { onSuccess },
    });
  const update = useUpdateProteinActivityAssayApiV1TargetBiologyProteinActivityAssayRecordIdPatch({
    mutation: { onSuccess },
  });
  const remove = useDeleteTargetBiologyRecordApiV1TargetBiologyKindRecordIdDelete({
    mutation: { onSuccess },
  });
  return (
    <EditableRecordTable<ProteinActivityAssayResponse, AssayDraft>
      title="Activity assay"
      description="A biochemical assay defined to measure this protein's activity."
      records={records}
      isAiRow={(r) => isAiGenerated(r.provenance.generation_method)}
      columns={ASSAY_COLUMNS}
      emptyDraft={ASSAY_EMPTY}
      provenanceFields={schema?.provenance.fields ?? []}
      toDraft={(a) => ({
        activity_measured: a.activity_measured,
        readout: a.readout ?? "",
        throughput: a.throughput ?? "",
        condition: a.condition ?? "",
        method: a.method ?? "",
        version: a.version,
      })}
      toBody={(d): ProteinActivityAssayPatchBody => ({
        activity_measured: d.activity_measured,
        readout: strOrNull(d.readout),
        throughput: strOrNull(d.throughput),
        condition: strOrNull(d.condition),
        method: strOrNull(d.method),
        version: d.version,
      })}
      onCreate={(body) =>
        create.mutateAsync({ proteinId, data: body as ProteinActivityAssayWriteBody })
      }
      onUpdate={(id, body) =>
        update.mutateAsync({ recordId: id, data: body as ProteinActivityAssayPatchBody })
      }
      onDelete={(id) => remove.mutateAsync({ kind: "protein_activity_assay", recordId: id })}
      busy={create.isPending || update.isPending || remove.isPending}
    />
  );
}

// ── Unpublished structure ─────────────────────────────────────────────────────

type StructDraft = {
  method: string;
  resolution: string;
  is_published: boolean;
  is_experimental: boolean;
  version?: number;
};
const STRUCT_EMPTY: StructDraft = {
  method: "",
  resolution: "",
  is_published: false,
  is_experimental: true,
};
const STRUCT_COLUMNS: Column<UnpublishedStructureResponse, StructDraft>[] = [
  {
    label: "Method",
    field: "method",
    type: "text",
    placeholder: "e.g. cryo-EM",
    render: (r) =>
      r.method ? (
        <Badge variant="secondary" className="font-normal">
          {r.method}
        </Badge>
      ) : (
        "—"
      ),
  },
  {
    label: "Resolution",
    field: "resolution",
    type: "number",
    placeholder: "Å",
    render: (r) => (r.resolution != null ? `${r.resolution} Å` : "—"),
  },
  {
    // Read-only: ligands are chem-cellar refs, editable once a picker exists.
    label: "Ligands",
    render: (r) =>
      r.ligands.length ? (
        <span className="flex flex-wrap gap-1">
          {r.ligands.map((l) => (
            <Badge key={l.compound_id} variant="outline" className="font-normal">
              {l.name ?? "ligand"}
            </Badge>
          ))}
        </span>
      ) : (
        "—"
      ),
  },
  {
    label: "Published",
    field: "is_published",
    type: "bool",
    render: (r) => (r.is_published ? "Yes" : "No"),
  },
  {
    label: "Experimental",
    field: "is_experimental",
    type: "bool",
    render: (r) => (r.is_experimental ? "Yes" : "Predicted"),
  },
  ...provColumns<UnpublishedStructureResponse>(),
];

export function UnpublishedStructureTable({
  proteinId,
  records,
}: {
  proteinId: string;
  records: UnpublishedStructureResponse[];
}) {
  const onSuccess = useInvalidateProteinTargetBiology(proteinId);
  const { data: schema } = useTargetBiologySchema();
  const create =
    useCreateUnpublishedStructureApiV1ProteinsProteinIdTargetBiologyUnpublishedStructurePost({
      mutation: { onSuccess },
    });
  const update = useUpdateUnpublishedStructureApiV1TargetBiologyUnpublishedStructureRecordIdPatch({
    mutation: { onSuccess },
  });
  const remove = useDeleteTargetBiologyRecordApiV1TargetBiologyKindRecordIdDelete({
    mutation: { onSuccess },
  });
  return (
    <EditableRecordTable<UnpublishedStructureResponse, StructDraft>
      title="Unpublished structure"
      description="An internal / unpublished structural model (ligand links are read-only for now)."
      records={records}
      isAiRow={(r) => isAiGenerated(r.provenance.generation_method)}
      columns={STRUCT_COLUMNS}
      emptyDraft={STRUCT_EMPTY}
      provenanceFields={schema?.provenance.fields ?? []}
      toDraft={(s) => ({
        method: s.method ?? "",
        resolution: s.resolution != null ? String(s.resolution) : "",
        is_published: s.is_published,
        is_experimental: s.is_experimental,
        version: s.version,
      })}
      toBody={(d): UnpublishedStructurePatchBody => ({
        method: strOrNull(d.method),
        resolution: numOrNull(d.resolution),
        is_published: d.is_published,
        is_experimental: d.is_experimental,
        version: d.version,
      })}
      onCreate={(body) =>
        create.mutateAsync({ proteinId, data: body as UnpublishedStructureWriteBody })
      }
      onUpdate={(id, body) =>
        update.mutateAsync({ recordId: id, data: body as UnpublishedStructurePatchBody })
      }
      onDelete={(id) => remove.mutateAsync({ kind: "unpublished_structure", recordId: id })}
      busy={create.isPending || update.isPending || remove.isPending}
    />
  );
}
