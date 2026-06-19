import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
vi.mock("../hooks/use-targets", () => ({
  useCreateTarget: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateTarget: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));
import { TargetFormDialog } from "./target-form-dialog";
describe("TargetFormDialog", () => {
  it("renders the create form with a preferred-name field", () => {
    const qc = new QueryClient();
    render(
      <QueryClientProvider client={qc}>
        <TargetFormDialog open onOpenChange={vi.fn()} />
      </QueryClientProvider>,
    );
    expect(screen.getByLabelText(/preferred name/i)).toBeInTheDocument();
  });
});
