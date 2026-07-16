import { fireEvent, render, screen } from "@testing-library/react";
import { type Mock, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../hooks/use-target-biology", () => ({
  useEssentialityMutations: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

import { useEssentialityMutations } from "../../hooks/use-target-biology";
import { EssentialityTable } from "./essentiality-table";

const mutations = {
  create: { mutateAsync: vi.fn().mockResolvedValue({}), isPending: false },
  update: { mutateAsync: vi.fn().mockResolvedValue({}), isPending: false },
  remove: { mutateAsync: vi.fn().mockResolvedValue({}), isPending: false },
};

const record = {
  id: "e1",
  gene_id: "g1",
  classification: "essential",
  condition: "in vitro 7H9",
  method: "TnSeq",
  confidence: 0.98,
  provenance: {
    source_type: "published",
    citations: [{ pmid: "28096490", doi: null, url: null, label: null }],
    contributor_researcher: null,
    contributor_organization_id: null,
    observed_on: null,
    note: null,
  },
  extensions: {},
};

beforeEach(() => {
  vi.clearAllMocks();
  (useEssentialityMutations as Mock).mockReturnValue(mutations);
});

describe("EssentialityTable", () => {
  it("renders a record with its fields and a PMID link", () => {
    render(<EssentialityTable geneId="g1" records={[record]} />);
    expect(screen.getByText("in vitro 7H9")).toBeInTheDocument();
    expect(screen.getByText("TnSeq")).toBeInTheDocument();
    expect(screen.getByText("0.98")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /PMID:28096490/ })).toHaveAttribute(
      "href",
      "https://pubmed.ncbi.nlm.nih.gov/28096490/",
    );
  });

  it("shows an empty state and an Add button when there are no records", () => {
    render(<EssentialityTable geneId="g1" records={[]} />);
    expect(screen.getByText(/no essentiality records yet/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add/i })).toBeInTheDocument();
  });

  it("reveals an editable row when Add is clicked, and creates on save", async () => {
    render(<EssentialityTable geneId="g1" records={[]} />);
    fireEvent.click(screen.getByRole("button", { name: /add/i }));
    // An editable row appears (inputs with placeholders).
    expect(screen.getByPlaceholderText("e.g. TnSeq")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(mutations.create.mutateAsync).toHaveBeenCalledTimes(1);
    const arg = mutations.create.mutateAsync.mock.calls[0][0];
    expect(arg.geneId).toBe("g1");
    expect(arg.data.classification).toBe("essential");
  });

  it("deletes a record after confirmation", () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<EssentialityTable geneId="g1" records={[record]} />);
    fireEvent.click(screen.getByRole("button", { name: /delete/i }));
    expect(mutations.remove.mutateAsync).toHaveBeenCalledWith({ recordId: "e1" });
  });
});
