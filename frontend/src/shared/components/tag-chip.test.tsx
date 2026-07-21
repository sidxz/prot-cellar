import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TagChip } from "./tag-chip";

describe("TagChip", () => {
  it("renders key=value text when value is present", () => {
    render(<TagChip tagKey="tier" value="1" />);
    expect(screen.getByText("tier")).toBeInTheDocument();
    expect(screen.getByText("=")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("renders just the key when value is null", () => {
    render(<TagChip tagKey="reviewed" value={null} />);
    expect(screen.getByText("reviewed")).toBeInTheDocument();
    expect(screen.queryByText("=")).not.toBeInTheDocument();
  });

  it("calls onRemove (not onClick) when the remove button is clicked", () => {
    const onRemove = vi.fn();
    const onClick = vi.fn();
    render(<TagChip tagKey="tier" value="1" onRemove={onRemove} onClick={onClick} />);

    fireEvent.click(screen.getByRole("button", { name: "Remove tier=1" }));

    expect(onRemove).toHaveBeenCalledTimes(1);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("renders no remove button when onRemove is absent", () => {
    render(<TagChip tagKey="tier" value="1" />);
    expect(screen.queryByRole("button", { name: /remove/i })).not.toBeInTheDocument();
  });

  it("renders as a button and calls onClick when clicked", () => {
    const onClick = vi.fn();
    render(<TagChip tagKey="tier" value="1" onClick={onClick} />);

    const chip = screen.getByRole("button", { name: "tier = 1" });
    fireEvent.click(chip);

    expect(onClick).toHaveBeenCalledTimes(1);
  });
});
