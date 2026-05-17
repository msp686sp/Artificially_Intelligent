import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CodeBlock } from "@/components/CodeBlock";

describe("<CodeBlock>", () => {
  it("renders the supplied source text", () => {
    render(<CodeBlock value="SELECT 1" language="sql" data-testid="cb" />);
    // CodeMirror renders content into a contenteditable region; assert
    // the wrapper exists and contains the text somewhere.
    const wrapper = screen.getByTestId("cb");
    expect(wrapper).toBeInTheDocument();
    expect(wrapper.textContent).toContain("SELECT 1");
  });

  it("renders a Copy affordance when showCopy is on", () => {
    render(<CodeBlock value="key: value" language="yaml" showCopy data-testid="cb2" />);
    expect(screen.getByLabelText("Copy code")).toBeInTheDocument();
  });

  it("renders without language extension for plain text", () => {
    render(<CodeBlock value="hello world" data-testid="cb3" />);
    const wrapper = screen.getByTestId("cb3");
    expect(wrapper.textContent).toContain("hello world");
  });
});
