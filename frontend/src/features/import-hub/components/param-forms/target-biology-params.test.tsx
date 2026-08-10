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
vi.mock("../organism-combobox", () => ({
  // biome-ignore lint/suspicious/noExplicitAny: test stub
  OrganismCombobox: ({ onSelect }: any) => (
    <button type="button" onClick={() => onSelect("org-7", "M. tb")}>
      pick-org
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
    localStorage.clear();
    startMutate.mockClear();
    uploadMutate.mockClear();
    push.mockClear();
  });

  it("rejects submit without a file or an organism", async () => {
    render(<TargetBiologyParamsForm onSuccess={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /start import/i }));
    expect(await screen.findByText(/upload a workbook first/i)).toBeInTheDocument();
    expect(await screen.findByText(/organism is required/i)).toBeInTheDocument();
    expect(startMutate).not.toHaveBeenCalled();
  });

  it("uploads the file, submits as a dry run, and remembers the params for Apply", async () => {
    const onSuccess = vi.fn();
    render(<TargetBiologyParamsForm onSuccess={onSuccess} />);

    pickFile();
    await waitFor(() => expect(uploadMutate).toHaveBeenCalled());

    fireEvent.click(screen.getByText("pick-org"));
    fireEvent.click(screen.getByRole("button", { name: /start import/i }));

    await waitFor(() =>
      expect(startMutate).toHaveBeenCalledWith({
        data: {
          import_type: "target_biology",
          params: {
            upload_ref: "up-1",
            organism_id: "org-7",
            match_by: "locus_tag",
            update_existing: false,
            dry_run: true,
          },
        },
      }),
    );
    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
    expect(push).toHaveBeenCalledWith("/admin/imports/run-1");
    // Apply (a separate run) needs these back — see types/index.ts.
    expect(JSON.parse(localStorage.getItem("pc-target-biology-apply:run-1") ?? "null")).toEqual({
      organism_id: "org-7",
      match_by: "locus_tag",
      update_existing: false,
    });
  });
});
