import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const mutateAsync = vi.fn().mockResolvedValue({});
vi.mock("../../hooks/use-imports", () => ({
  useStartImport: () => ({ mutateAsync, isPending: false }),
}));

import { GoOntologyForm } from "./go-ontology-form";

describe("GoOntologyForm", () => {
  it("submits a go_ontology import with force=false by default", async () => {
    mutateAsync.mockClear();
    const onSuccess = vi.fn();
    render(<GoOntologyForm onSuccess={onSuccess} />);
    fireEvent.click(screen.getByRole("button", { name: /start import/i }));
    await waitFor(() =>
      expect(mutateAsync).toHaveBeenCalledWith({
        data: { import_type: "go_ontology", params: { force: false } },
      }),
    );
    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
  });
});
