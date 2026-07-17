import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const startMutate = vi.fn().mockResolvedValue({});
vi.mock("../../hooks/use-imports", () => ({
  useStartImport: () => ({ mutateAsync: startMutate, isPending: false }),
}));
vi.mock("../organism-combobox", () => ({
  // biome-ignore lint/suspicious/noExplicitAny: test stub
  OrganismCombobox: ({ onSelect }: any) => (
    <button type="button" onClick={() => onSelect("org-7", "M. tb")}>
      pick-org
    </button>
  ),
}));

import { GeneEnrichmentForm } from "./gene-enrichment-form";

describe("GeneEnrichmentForm", () => {
  it("rejects submit when neither organism nor tax_id is provided", async () => {
    startMutate.mockClear();
    render(<GeneEnrichmentForm onSuccess={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /start import/i }));
    expect(await screen.findByText(/exactly one/i)).toBeInTheDocument();
    expect(startMutate).not.toHaveBeenCalled();
  });

  it("submits the tax_id path with a coerced number", async () => {
    startMutate.mockClear();
    const onSuccess = vi.fn();
    render(<GeneEnrichmentForm onSuccess={onSuccess} />);
    fireEvent.change(screen.getByLabelText(/ncbi tax id/i), { target: { value: "83332" } });
    fireEvent.click(screen.getByRole("button", { name: /start import/i }));
    await waitFor(() =>
      expect(startMutate).toHaveBeenCalledWith({
        data: { import_type: "gene_enrichment", params: { force: false, tax_id: 83332 } },
      }),
    );
    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
  });
});
