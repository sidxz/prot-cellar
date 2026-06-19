import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Stub the mutation hooks so no network/QueryClient is needed.
vi.mock("../hooks/use-organizations", () => ({
  useCreateOrganization: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateOrganization: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

import { OrganizationFormDialog } from "./organization-form-dialog";

describe("OrganizationFormDialog", () => {
  it("renders create-mode title and the name field when open with no organization", () => {
    render(<OrganizationFormDialog open onOpenChange={() => {}} />);
    expect(screen.getByRole("heading", { name: /new organization/i })).toBeInTheDocument();
    expect(screen.getByLabelText("Name")).toBeInTheDocument();
  });

  it("renders edit-mode title when an organization is supplied", () => {
    render(
      <OrganizationFormDialog
        open
        onOpenChange={() => {}}
        organization={
          {
            id: "o1",
            workspace_id: "w1",
            name: "Acme Bio",
            org_type: "pharma_partner",
            contact_name: null,
            contact_email: null,
            notes: null,
            is_active: true,
            version: 1,
          } as never
        }
      />,
    );
    expect(screen.getByRole("heading", { name: /edit organization/i })).toBeInTheDocument();
  });
});
