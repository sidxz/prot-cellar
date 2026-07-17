import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Gene } from "../../types";

// The neighborhood track is driven by the generated query hook (wrapped by
// `useGeneNeighborhood`). Mock it directly so we control loading/data/error.
vi.mock("@/shared/lib/api/genes/genes", () => ({
  useGetGeneNeighborhoodApiV1GenesGeneIdNeighborhoodGet: vi.fn(() => ({
    data: undefined,
    isLoading: false,
    isError: false,
  })),
}));

import { useGetGeneNeighborhoodApiV1GenesGeneIdNeighborhoodGet } from "@/shared/lib/api/genes/genes";
import { GenomicContextSection } from "./genomic-context-section";

const mockedNeighborhood = useGetGeneNeighborhoodApiV1GenesGeneIdNeighborhoodGet as ReturnType<
  typeof vi.fn
>;

const gene = {
  id: "g1",
  genomic_accession: "NC_000962.3",
  genomic_start: 759807,
  genomic_end: 763325,
  genomic_strand: "+",
  length_bp: 3519,
} as unknown as Gene;

describe("GenomicContextSection", () => {
  it("returns null without location", () => {
    const { container } = render(<GenomicContextSection gene={{ id: "g" } as unknown as Gene} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows accession, coords and length", () => {
    render(<GenomicContextSection gene={gene} />);
    expect(screen.getByText(/NC_000962\.3/)).toBeInTheDocument();
    expect(screen.getByText(/759,807/)).toBeInTheDocument();
    expect(screen.getByText(/763,325/)).toBeInTheDocument();
    expect(screen.getByText(/3,519 bp/)).toBeInTheDocument();
  });

  it("renders a neighborhood track when the hook returns >= 2 neighbors", () => {
    mockedNeighborhood.mockReturnValue({
      data: {
        center_id: "g1",
        accession: "NC_000962.3",
        neighbors: [
          {
            id: "g0",
            primary_name: "rpoC",
            genomic_start: 700000,
            genomic_end: 705000,
            genomic_strand: "+",
            essentiality: "essential",
          },
          {
            id: "g1",
            primary_name: "rpoB",
            genomic_start: 759807,
            genomic_end: 763325,
            genomic_strand: "+",
            essentiality: null,
          },
          {
            id: "g2",
            primary_name: "rpsL",
            genomic_start: 800000,
            genomic_end: 805000,
            genomic_strand: "-",
            essentiality: "non-essential",
          },
        ],
      },
      isLoading: false,
      isError: false,
    });

    render(<GenomicContextSection gene={gene} />);

    // Neighbors render as links to /genes/{id}
    const neighborLink = screen.getByRole("link", { name: /rpoC/ });
    expect(neighborLink).toHaveAttribute("href", "/genes/g0");
    expect(screen.getByRole("link", { name: /rpsL/ })).toHaveAttribute("href", "/genes/g2");

    // The current gene is shown but marked current (aria-current), not a link.
    const current = screen.getByText("rpoB");
    expect(current.closest("a")).toBeNull();

    // The proportional SVG track renders as a labelled group.
    expect(
      screen.getByRole("group", { name: /genomic neighborhood track/i }),
    ).toBeInTheDocument();

    // The essentiality legend renders alongside the track (fitness-axis buckets).
    const legend = screen.getByLabelText("Essentiality legend");
    expect(legend).toBeInTheDocument();
    expect(screen.getByText("Essential")).toBeInTheDocument();
    expect(screen.getByText("Growth-defect")).toBeInTheDocument();
    expect(screen.getByText("Non-essential")).toBeInTheDocument();
    expect(screen.getByText("Growth-adv.")).toBeInTheDocument();
  });

  it("does not render the legend when there is no neighborhood track", () => {
    mockedNeighborhood.mockReturnValue({
      data: { center_id: "g1", accession: "NC_000962.3", neighbors: [] },
      isLoading: false,
      isError: false,
    });

    render(<GenomicContextSection gene={gene} />);
    expect(screen.queryByLabelText("Essentiality legend")).not.toBeInTheDocument();
  });

  it("renders only the location row when there are fewer than 2 neighbors", () => {
    mockedNeighborhood.mockReturnValue({
      data: { center_id: "g1", accession: "NC_000962.3", neighbors: [] },
      isLoading: false,
      isError: false,
    });

    render(<GenomicContextSection gene={gene} />);
    expect(screen.getByText(/NC_000962\.3/)).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("renders only the location row on error", () => {
    mockedNeighborhood.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    });

    render(<GenomicContextSection gene={gene} />);
    expect(screen.getByText(/NC_000962\.3/)).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
