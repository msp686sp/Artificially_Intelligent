import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Stat } from "@/components/Stat";

describe("<Stat>", () => {
  it("renders label + value", () => {
    render(<Stat label="Sources" value={12} />);
    expect(screen.getByText("Sources")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
  });
  it("renders delta with positive tone class", () => {
    const { container } = render(<Stat label="Score" value="74" delta="+12%" deltaTone="positive" />);
    const delta = screen.getByText("+12%");
    expect(delta).toBeInTheDocument();
    expect(delta.className).toContain("text-success");
    expect(container).toBeTruthy();
  });
  it("renders delta with negative tone class", () => {
    render(<Stat label="Score" value="74" delta="-3" deltaTone="negative" />);
    expect(screen.getByText("-3").className).toContain("text-danger");
  });
  it("renders optional hint", () => {
    render(<Stat label="Score" value="74" hint="vs. last week" />);
    expect(screen.getByText("vs. last week")).toBeInTheDocument();
  });
  it("omits delta when not provided", () => {
    render(<Stat label="Score" value="74" />);
    // Only one tabular-nums span: the value
    expect(screen.queryByText("+")).not.toBeInTheDocument();
  });
});
