"use client";

import { Badge } from "@/shared/components/ui/badge";
import { Card, CardContent } from "@/shared/components/ui/card";
import type { ProvenanceCitationResponse, ProvenanceResponse } from "@/shared/lib/api/model";

import { useGeneTargetBiology, useProteinTargetBiology } from "../../hooks/use-target-biology";
import { essentialityBadgeVariant } from "./axis-annotations-section";

// ---------------------------------------------------------------------------
// Uniform record model — each typed record is projected to a headline node,
// an optional meta subline, and its shared provenance envelope. This keeps all
// eight record types rendering through one presentational path.
// ---------------------------------------------------------------------------

interface TbRecord {
  id: string;
  headline: React.ReactNode;
  meta?: (string | null | undefined)[];
  provenance: ProvenanceResponse;
}

interface TbGroup {
  title: string;
  items: TbRecord[];
}

function CitationLink({ c }: { c: ProvenanceCitationResponse }) {
  if (c.pmid) {
    return (
      <a
        href={`https://pubmed.ncbi.nlm.nih.gov/${c.pmid}/`}
        target="_blank"
        rel="noopener noreferrer"
        className="text-primary hover:underline"
      >
        PMID:{c.pmid}
      </a>
    );
  }
  if (c.doi) {
    return (
      <a
        href={`https://doi.org/${c.doi}`}
        target="_blank"
        rel="noopener noreferrer"
        className="text-primary hover:underline"
      >
        DOI
      </a>
    );
  }
  if (c.url) {
    return (
      <a
        href={c.url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-primary hover:underline"
      >
        {c.label ?? "Source"}
      </a>
    );
  }
  return <span>{c.label ?? "—"}</span>;
}

/** Compact provenance footer: source type · citations · note. */
function ProvenanceLine({ provenance }: { provenance: ProvenanceResponse }) {
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
      <span className="uppercase tracking-wide">{provenance.source_type.replace(/_/g, " ")}</span>
      {provenance.citations.map((c, i) => (
        <CitationLink key={c.pmid ?? c.doi ?? c.url ?? c.label ?? i} c={c} />
      ))}
      {provenance.note && <span className="italic">{provenance.note}</span>}
    </div>
  );
}

function RecordRow({ record }: { record: TbRecord }) {
  const meta = (record.meta ?? []).filter(Boolean).join(" · ");
  return (
    <li className="flex flex-col gap-0.5">
      <div className="flex flex-wrap items-center gap-2">{record.headline}</div>
      {meta && <span className="text-xs text-muted-foreground">{meta}</span>}
      <ProvenanceLine provenance={record.provenance} />
    </li>
  );
}

/**
 * Shared card wrapper — renders nothing when no group has records.
 * `heading` labels the card; pass `null` when the surrounding context (e.g. a
 * "Target Biology" tab) already provides the label.
 */
function TargetBiologyCard({
  groups,
  heading = "Target Biology",
}: {
  groups: TbGroup[];
  heading?: string | null;
}) {
  const populated = groups.filter((g) => g.items.length > 0);
  if (populated.length === 0) return null;

  const card = (
    <Card>
      <CardContent className="flex flex-col gap-4 pt-4">
        {populated.map((group) => (
          <div key={group.title} className="flex flex-col gap-2">
            <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {group.title}
            </span>
            <ul className="flex flex-col gap-2.5">
              {group.items.map((r) => (
                <RecordRow key={r.id} record={r} />
              ))}
            </ul>
          </div>
        ))}
      </CardContent>
    </Card>
  );

  if (heading === null) return card;
  return (
    <section aria-labelledby="target-biology-heading">
      <h2 id="target-biology-heading" className="text-base font-semibold mb-3 text-foreground">
        {heading}
      </h2>
      {card}
    </section>
  );
}

const fmtScore = (n: number | null | undefined): string => (n == null ? "—" : n.toFixed(2));

// ---------------------------------------------------------------------------
// Gene-side: essentiality, vulnerability, hypomorph, CRISPRi strain, resistance
// ---------------------------------------------------------------------------

export function GeneTargetBiologySection({
  geneId,
  omit = [],
  heading,
}: {
  geneId: string;
  /** Group titles to skip (e.g. a record type rendered by its own editable table). */
  omit?: string[];
  heading?: string | null;
}) {
  const { data } = useGeneTargetBiology(geneId);
  if (!data) return null;

  const groups: TbGroup[] = [
    {
      title: "Essentiality",
      items: data.essentiality.map((e) => ({
        id: e.id,
        provenance: e.provenance,
        meta: [e.condition, e.method],
        headline: (
          <>
            <Badge
              variant={essentialityBadgeVariant(e.classification)}
              className="font-normal capitalize"
            >
              {e.classification.replace(/_/g, " ")}
            </Badge>
            {e.confidence != null && (
              <span className="text-xs text-muted-foreground">
                confidence {fmtScore(e.confidence)}
              </span>
            )}
          </>
        ),
      })),
    },
    {
      title: "Vulnerability",
      items: data.vulnerability.map((v) => ({
        id: v.id,
        provenance: v.provenance,
        meta: [v.condition, v.method],
        headline: (
          <>
            <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Score
            </span>
            <span className="font-mono text-sm text-foreground">
              {fmtScore(v.vulnerability_score)}
            </span>
            {v.confidence != null && (
              <span className="text-xs text-muted-foreground">
                confidence {fmtScore(v.confidence)}
              </span>
            )}
          </>
        ),
      })),
    },
    {
      title: "Hypomorph",
      items: data.hypomorph.map((h) => ({
        id: h.id,
        provenance: h.provenance,
        meta: [h.condition, h.method],
        headline: (
          <>
            <Badge variant={h.growth_defect ? "warning" : "secondary"} className="font-normal">
              {h.growth_defect ? "Growth defect" : "No growth defect"}
            </Badge>
            {h.growth_defect_severity && (
              <span className="text-xs text-muted-foreground">{h.growth_defect_severity}</span>
            )}
          </>
        ),
      })),
    },
    {
      title: "CRISPRi strain",
      items: data.crispri_strain.map((s) => ({
        id: s.id,
        provenance: s.provenance,
        headline: <span className="font-mono text-sm text-foreground">{s.name}</span>,
      })),
    },
    {
      title: "Resistance mutation",
      items: data.resistance_mutation.map((m) => ({
        id: m.id,
        provenance: m.provenance,
        meta: [m.parent_strain, m.protein_coordinate && `pos ${m.protein_coordinate}`, m.method],
        headline: (
          <>
            <span className="font-mono text-sm text-foreground">{m.mutation}</span>
            {m.compound?.name && (
              <Badge variant="outline" className="font-normal">
                resists {m.compound.name}
              </Badge>
            )}
            {m.mic_shift != null && (
              <span className="text-xs text-muted-foreground">MIC ×{m.mic_shift}</span>
            )}
          </>
        ),
      })),
    },
  ];

  return (
    <TargetBiologyCard groups={groups.filter((g) => !omit.includes(g.title))} heading={heading} />
  );
}

// ---------------------------------------------------------------------------
// Protein-side: production, activity assay, unpublished structure
// ---------------------------------------------------------------------------

export function ProteinTargetBiologySection({ proteinId }: { proteinId: string }) {
  const { data } = useProteinTargetBiology(proteinId);
  if (!data) return null;

  const groups: TbGroup[] = [
    {
      title: "Protein production",
      items: data.protein_production.map((p) => ({
        id: p.id,
        provenance: p.provenance,
        meta: [p.condition, p.method],
        headline: (
          <>
            <Badge variant="secondary" className="font-normal capitalize">
              {p.status}
            </Badge>
            {p.expression_host && (
              <span className="text-xs text-muted-foreground">{p.expression_host}</span>
            )}
            {p.purity != null && (
              <span className="text-xs text-muted-foreground">purity {p.purity}</span>
            )}
          </>
        ),
      })),
    },
    {
      title: "Activity assay",
      items: data.protein_activity_assay.map((a) => ({
        id: a.id,
        provenance: a.provenance,
        meta: [a.condition, a.method],
        headline: (
          <>
            <span className="text-sm text-foreground">{a.activity_measured}</span>
            {a.readout && (
              <Badge variant="outline" className="font-normal">
                {a.readout}
              </Badge>
            )}
            {a.throughput && <span className="text-xs text-muted-foreground">{a.throughput}</span>}
          </>
        ),
      })),
    },
    {
      title: "Unpublished structure",
      items: data.unpublished_structure.map((s) => ({
        id: s.id,
        provenance: s.provenance,
        headline: (
          <>
            {s.method && (
              <Badge variant="secondary" className="font-normal">
                {s.method}
              </Badge>
            )}
            {s.resolution != null && (
              <span className="font-mono text-xs text-muted-foreground">{s.resolution} Å</span>
            )}
            {s.ligands.map((l) => (
              <Badge key={l.compound_id} variant="outline" className="font-normal">
                {l.name ?? "ligand"}
              </Badge>
            ))}
            {!s.is_experimental && <span className="text-xs text-muted-foreground">predicted</span>}
          </>
        ),
      })),
    },
  ];

  return <TargetBiologyCard groups={groups} />;
}
