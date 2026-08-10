// frontend/src/features/import-hub/components/proteome-combobox.test.tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const useProteomesMock = vi.fn();
vi.mock("@/features/taxonomy/hooks/use-proteomes", () => ({
  useProteomes: (...args: unknown[]) => useProteomesMock(...args),
}));

import { ProteomeCombobox } from "./proteome-combobox";

describe("ProteomeCombobox", () => {
  it("renders each option as accession + full name, strain in parens", () => {
    useProteomesMock.mockReturnValue({
      data: {
        items: [
          {
            id: "pt-1",
            uniprot_proteome_id: "UP000001584",
            organism_name: "Mycobacterium tuberculosis",
            strain_name: "ATCC 25618 / H37Rv",
          },
        ],
      },
      isLoading: false,
    });
    const onSelect = vi.fn();
    render(<ProteomeCombobox onSelect={onSelect} />);
    fireEvent.focus(screen.getByRole("combobox"));
    expect(
      screen.getByText("UP000001584 — Mycobacterium tuberculosis (ATCC 25618 / H37Rv)"),
    ).toBeInTheDocument();
  });

  it("omits the strain parens when the proteome has no strain", () => {
    useProteomesMock.mockReturnValue({
      data: {
        items: [{ id: "pt-2", uniprot_proteome_id: "UP000005640", organism_name: "Homo sapiens" }],
      },
      isLoading: false,
    });
    const onSelect = vi.fn();
    render(<ProteomeCombobox onSelect={onSelect} />);
    fireEvent.focus(screen.getByRole("combobox"));
    expect(screen.getByText("UP000005640 — Homo sapiens")).toBeInTheDocument();
  });

  it("calls onSelect with id + label on pick", () => {
    useProteomesMock.mockReturnValue({
      data: {
        items: [{ id: "pt-1", uniprot_proteome_id: "UP000001584", organism_name: "M. tb" }],
      },
      isLoading: false,
    });
    const onSelect = vi.fn();
    render(<ProteomeCombobox onSelect={onSelect} />);
    fireEvent.focus(screen.getByRole("combobox"));
    fireEvent.click(screen.getByText("UP000001584 — M. tb"));
    expect(onSelect).toHaveBeenCalledWith("pt-1", "UP000001584 — M. tb");
  });

  it("clears the committed selection when the search text is edited", () => {
    useProteomesMock.mockReturnValue({ data: { items: [] }, isLoading: false });
    const onSelect = vi.fn();
    render(<ProteomeCombobox onSelect={onSelect} />);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "myco" } });
    expect(onSelect).toHaveBeenCalledWith("", "");
  });

  it("filters options against the typed text, matching accession or organism/strain name", async () => {
    useProteomesMock.mockReturnValue({
      data: {
        items: [
          { id: "pt-1", uniprot_proteome_id: "UP000001584", organism_name: "M. tuberculosis" },
          { id: "pt-2", uniprot_proteome_id: "UP000005640", organism_name: "Homo sapiens" },
        ],
      },
      isLoading: false,
    });
    const onSelect = vi.fn();
    render(<ProteomeCombobox onSelect={onSelect} />);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "sapiens" } });
    // The filter applies once the 300ms debounce commits — not synchronously
    // on keystroke (handleChange's own synchronous onSelect("","") reset above
    // is a separate concern from this debounced re-filter).
    await waitFor(() => expect(screen.queryByText(/UP000001584/)).not.toBeInTheDocument());
    expect(screen.getByText(/UP000005640/)).toBeInTheDocument();
  });
});
