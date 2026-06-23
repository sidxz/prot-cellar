import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const mutateAsync = vi.fn().mockResolvedValue({});
vi.mock("../../hooks/use-imports", () => ({
  useStartImport: () => ({ mutateAsync, isPending: false }),
}));

import { ProteomeForm } from "./proteome-form";

describe("ProteomeForm", () => {
  it("requires a proteome_id before submitting", async () => {
    mutateAsync.mockClear();
    render(<ProteomeForm onSuccess={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /start import/i }));
    expect(await screen.findByText(/proteome id is required/i)).toBeInTheDocument();
    expect(mutateAsync).not.toHaveBeenCalled();
  });

  it("submits composed params and calls onSuccess", async () => {
    mutateAsync.mockClear();
    const onSuccess = vi.fn();
    render(<ProteomeForm onSuccess={onSuccess} />);
    fireEvent.change(screen.getByLabelText(/uniprot proteome id/i), {
      target: { value: "UP000001584" },
    });
    fireEvent.click(screen.getByRole("button", { name: /start import/i }));
    await waitFor(() =>
      expect(mutateAsync).toHaveBeenCalledWith({
        data: {
          import_type: "proteome",
          params: { proteome_id: "UP000001584", force: false, dry_run: false, limit: null },
        },
      }),
    );
    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
  });
});
