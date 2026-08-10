import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

const startMutate = vi.fn().mockResolvedValue({ id: "run-1" });
const uploadMutate = vi.fn().mockResolvedValue({ upload_ref: "up-1" });
vi.mock("../../hooks/use-imports", () => ({
  useStartImport: () => ({ mutateAsync: startMutate, isPending: false }),
  useUploadEssentiality: () => ({ mutateAsync: uploadMutate, isPending: false }),
}));
vi.mock("../proteome-combobox", () => ({
  // biome-ignore lint/suspicious/noExplicitAny: test stub
  ProteomeCombobox: ({ onSelect }: any) => (
    <button type="button" onClick={() => onSelect("pt-7", "UP000001584 — M. tb")}>
      pick-proteome
    </button>
  ),
}));
vi.mock("@/features/protein-catalog/hooks/use-target-biology-schema", () => ({
  useTargetBiologySchema: () => ({ data: undefined }),
}));

import { TargetBiologyParamsForm } from "./target-biology-params";

function pickFile() {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  const file = new File(["x"], "workbook.xlsx", {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  fireEvent.change(input, { target: { files: [file] } });
}

describe("TargetBiologyParamsForm", () => {
  beforeEach(() => {
    startMutate.mockClear();
    uploadMutate.mockClear();
    push.mockClear();
  });

  it("rejects submit without a file or a proteome", async () => {
    render(<TargetBiologyParamsForm onSuccess={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /start import/i }));
    expect(await screen.findByText(/upload a workbook first/i)).toBeInTheDocument();
    expect(await screen.findByText(/proteome is required/i)).toBeInTheDocument();
    expect(startMutate).not.toHaveBeenCalled();
  });

  it("rejects submit when a proteome was typed but never picked", async () => {
    render(<TargetBiologyParamsForm onSuccess={() => {}} />);
    pickFile();
    await waitFor(() => expect(uploadMutate).toHaveBeenCalled());
    // No pick-proteome click — proteome_id stays "" even with text typed into
    // the combobox (see ProteomeCombobox's own "clears on edit" behaviour).
    fireEvent.click(screen.getByRole("button", { name: /start import/i }));
    expect(await screen.findByText(/proteome is required/i)).toBeInTheDocument();
    expect(startMutate).not.toHaveBeenCalled();
  });

  it("uploads the file and submits as a dry run", async () => {
    const onSuccess = vi.fn();
    render(<TargetBiologyParamsForm onSuccess={onSuccess} />);

    pickFile();
    await waitFor(() => expect(uploadMutate).toHaveBeenCalled());

    fireEvent.click(screen.getByText("pick-proteome"));
    fireEvent.click(screen.getByRole("button", { name: /start import/i }));

    await waitFor(() =>
      expect(startMutate).toHaveBeenCalledWith({
        data: {
          import_type: "target_biology",
          params: {
            upload_ref: "up-1",
            proteome_id: "pt-7",
            match_by: "locus_tag",
            update_existing: false,
            dry_run: true,
          },
        },
      }),
    );
    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
    expect(push).toHaveBeenCalledWith("/admin/imports/run-1");
  });
});
