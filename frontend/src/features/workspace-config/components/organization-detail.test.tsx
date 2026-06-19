import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const org = {
  id: "o1",
  workspace_id: "w1",
  name: "Acme Bio",
  org_type: "pharma_partner",
  contact_name: "Jane Doe",
  contact_email: "jane@acme.com",
  notes: "Primary partner",
  is_active: true,
  version: 3,
};

vi.mock("../hooks/use-organizations", () => ({
  useOrganization: () => ({ data: org, isLoading: false, isError: false }),
  useCreateOrganization: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateOrganization: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

import { OrganizationDetailPage } from "./organization-detail";

describe("OrganizationDetailPage", () => {
  it("renders the organization name and a mailto link for the contact email", () => {
    render(<OrganizationDetailPage organizationId="o1" />);
    expect(screen.getByRole("heading", { name: "Acme Bio" })).toBeInTheDocument();
    const mail = screen.getByRole("link", { name: /jane@acme\.com/i });
    expect(mail).toHaveAttribute("href", "mailto:jane@acme.com");
  });
});
