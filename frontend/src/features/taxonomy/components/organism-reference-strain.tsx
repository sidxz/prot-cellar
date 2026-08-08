"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/components/ui/select";
import {
  getGetOrganismApiV1OrganismsOrganismIdGetQueryKey,
  getListOrganismsApiV1OrganismsGetQueryKey,
  useUpdateOrganismApiV1OrganismsOrganismIdPatch,
} from "@/shared/lib/api/organisms/organisms";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { useStrains } from "../hooks/use-strains";
import { scopeStrainsToOrganism } from "../lib/scope-strains";
import { TAXON_FILTER_PAGE_SIZE } from "../types";

const NONE = "__none__";

/**
 * Designate a species' reference (preferred) strain — the default the gene
 * dashboard filters to. Only rendered for organisms that actually have strains.
 * Admin-only (the backend enforces); a 403 surfaces as a toast.
 *
 * Organisms are reference data (design doc §1.5) — every organism is `isShared`,
 * so the picker is read-only there. Same treatment as strain-detail.tsx's Edit
 * button.
 */
export function OrganismReferenceStrain({
  organismId,
  referenceStrainId,
  isShared,
}: {
  organismId: string;
  referenceStrainId: string | null | undefined;
  isShared: boolean;
}) {
  const qc = useQueryClient();
  const { data: strainData } = useStrains({}, undefined, TAXON_FILTER_PAGE_SIZE);
  const strains = scopeStrainsToOrganism(strainData?.items ?? [], organismId);

  const update = useUpdateOrganismApiV1OrganismsOrganismIdPatch({
    mutation: {
      onSuccess: () => {
        // Invalidate the detail query AND the organisms list — the gene dashboard
        // reads reference_strain_id from the LIST to default its strain filter.
        qc.invalidateQueries({
          queryKey: getGetOrganismApiV1OrganismsOrganismIdGetQueryKey(organismId),
        });
        qc.invalidateQueries({ queryKey: getListOrganismsApiV1OrganismsGetQueryKey() });
        toast.success("Reference strain updated");
      },
      onError: () => toast.error("Could not update — an admin role is required."),
    },
  });

  if (strains.length === 0) {
    return <span className="text-sm text-muted-foreground">—</span>;
  }

  if (isShared) {
    const current = strains.find((s) => s.id === referenceStrainId);
    return (
      <div className="flex items-center gap-2">
        <span className="text-sm text-foreground">{current?.name ?? "None"}</span>
        <span className="text-xs italic text-muted-foreground">
          Reference data — managed by import
        </span>
      </div>
    );
  }

  return (
    <Select
      value={referenceStrainId ?? NONE}
      onValueChange={(v) =>
        update.mutate({
          organismId,
          data: { reference_strain_id: v === NONE ? null : v },
        })
      }
    >
      <SelectTrigger className="h-8 w-56" aria-label="Reference strain">
        <SelectValue placeholder="None" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={NONE}>None</SelectItem>
        {strains.map((s) => (
          <SelectItem key={s.id} value={s.id}>
            {s.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
