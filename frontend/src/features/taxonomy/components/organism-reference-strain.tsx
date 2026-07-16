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
  useUpdateOrganismApiV1OrganismsOrganismIdPatch,
} from "@/shared/lib/api/organisms/organisms";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { useStrains } from "../hooks/use-strains";

const NONE = "__none__";

/**
 * Designate a species' reference (preferred) strain — the default the gene
 * dashboard filters to. Only rendered for organisms that actually have strains.
 * Admin-only (the backend enforces); a 403 surfaces as a toast.
 */
export function OrganismReferenceStrain({
  organismId,
  referenceStrainId,
}: {
  organismId: string;
  referenceStrainId: string | null | undefined;
}) {
  const qc = useQueryClient();
  const { data: strainData } = useStrains();
  const strains = (strainData?.items ?? []).filter((s) => s.species_organism_id === organismId);

  const update = useUpdateOrganismApiV1OrganismsOrganismIdPatch({
    mutation: {
      onSuccess: () => {
        qc.invalidateQueries({
          queryKey: getGetOrganismApiV1OrganismsOrganismIdGetQueryKey(organismId),
        });
        toast.success("Reference strain updated");
      },
      onError: () => toast.error("Could not update — an admin role is required."),
    },
  });

  if (strains.length === 0) {
    return <span className="text-sm text-muted-foreground">—</span>;
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
