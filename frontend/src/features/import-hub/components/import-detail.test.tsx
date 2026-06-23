// frontend/src/features/import-hub/components/import-detail.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const useImportRunMock = vi.fn();
vi.mock("../hooks/use-imports", () => ({ useImportRun: () => useImportRunMock() }));

import { ImportDetailPage } from "./import-detail";

const base = {
  id: "r1",
  import_type: "proteome",
  target_key: "UP000001584",
  phase: null,
  progress: { processed: 0, total: 0 },
  summary: {},
  error: null,
};

describe("ImportDetailPage", () => {
  it("renders the summary on success", () => {
    useImportRunMock.mockReturnValue({
      data: { ...base, status: "succeeded", summary: { proteins: 4008, genes: 3906 } },
      isLoading: false,
      isError: false,
    });
    render(<ImportDetailPage importRunId="r1" />);
    expect(screen.getByText("proteins")).toBeInTheDocument();
    expect(screen.getByText("4008")).toBeInTheDocument();
  });

  it("renders the error on failure", () => {
    useImportRunMock.mockReturnValue({
      data: { ...base, status: "failed", error: "GFF fetch failed" },
      isLoading: false,
      isError: false,
    });
    render(<ImportDetailPage importRunId="r1" />);
    expect(screen.getByText(/gff fetch failed/i)).toBeInTheDocument();
  });

  it("shows a working indicator while active with no total", () => {
    useImportRunMock.mockReturnValue({
      data: { ...base, status: "running" },
      isLoading: false,
      isError: false,
    });
    render(<ImportDetailPage importRunId="r1" />);
    expect(screen.getByText(/working/i)).toBeInTheDocument();
  });
});
