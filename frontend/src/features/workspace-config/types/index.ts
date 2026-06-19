import type {
  CreateOrganizationBody,
  OrganizationResponse,
  OrganizationType,
  UpdateOrganizationBody,
} from "@/shared/lib/api/model";

/** Narrowed alias — organization (no narrowing needed beyond the generated type). */
export type Organization = OrganizationResponse;

// Re-export the generated body/enum types so feature code imports them from one place.
export type { CreateOrganizationBody, OrganizationType, UpdateOrganizationBody };

/** Human-readable labels for all 6 organization_type values. */
export const ORG_TYPE_LABELS: Record<OrganizationType, string> = {
  internal: "Internal",
  pharma_partner: "Pharma partner",
  cro: "CRO",
  academic: "Academic",
  vendor: "Vendor",
  government: "Government",
};

/** Filter parameters for listing organizations. */
export interface OrganizationListFilters {
  includeInactive?: boolean;
}

/** Form values for creating or editing an organization. */
export interface OrganizationFormValues {
  name: string;
  org_type: OrganizationType;
  contact_name?: string;
  contact_email?: string;
  notes?: string;
}
