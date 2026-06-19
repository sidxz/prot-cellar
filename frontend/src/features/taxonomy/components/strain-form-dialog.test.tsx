import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../hooks/use-strains", () => ({
  useCreateStrain: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateStrain: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

import { StrainFormDialog } from "./strain-form-dialog";

describe("StrainFormDialog", () => {
  it("renders the create form with Name and Species organism fields", () => {
    const qc = new QueryClient();
    render(
      <QueryClientProvider client={qc}>
        <StrainFormDialog open onOpenChange={vi.fn()} />
      </QueryClientProvider>,
    );
    expect(screen.getByLabelText(/^name$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/species organism/i)).toBeInTheDocument();
  });
});
