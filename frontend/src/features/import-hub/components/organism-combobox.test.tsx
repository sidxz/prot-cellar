// frontend/src/features/import-hub/components/organism-combobox.test.tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const useOrganismsMock = vi.fn();
vi.mock("@/features/taxonomy/hooks/use-organisms", () => ({
  useOrganisms: (...args: unknown[]) => useOrganismsMock(...args),
}));

import { OrganismCombobox } from "./organism-combobox";

describe("OrganismCombobox", () => {
  it("lists results and calls onSelect with id + label", () => {
    useOrganismsMock.mockReturnValue({
      data: {
        items: [
          { id: "org-1", scientific_name: "Mycobacterium tuberculosis", ncbi_tax_id: 1773 },
        ],
      },
      isLoading: false,
    });
    const onSelect = vi.fn();
    render(<OrganismCombobox onSelect={onSelect} />);
    fireEvent.focus(screen.getByRole("combobox"));
    fireEvent.click(screen.getByText("Mycobacterium tuberculosis — 1773"));
    expect(onSelect).toHaveBeenCalledWith("org-1", "Mycobacterium tuberculosis — 1773");
  });
});
