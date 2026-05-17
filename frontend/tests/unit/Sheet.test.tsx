import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Sheet } from "@/components/Sheet";

describe("<Sheet>", () => {
  it("renders title and children when open", () => {
    render(
      <Sheet open onClose={() => {}} title="Filters">
        <p>Filter content here</p>
      </Sheet>,
    );
    expect(screen.getByText("Filters")).toBeInTheDocument();
    expect(screen.getByText("Filter content here")).toBeInTheDocument();
  });

  it("does not render content when closed", () => {
    render(
      <Sheet open={false} onClose={() => {}} title="Filters">
        <p>Hidden content</p>
      </Sheet>,
    );
    expect(screen.queryByText("Hidden content")).not.toBeInTheDocument();
  });

  it("invokes onClose when the close button is clicked", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <Sheet open onClose={onClose} title="Filters">
        <p>body</p>
      </Sheet>,
    );
    await user.click(screen.getByLabelText("Close panel"));
    expect(onClose).toHaveBeenCalled();
  });

  it("invokes onClose on Escape", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(
      <Sheet open onClose={onClose} title="Filters">
        <p>body</p>
      </Sheet>,
    );
    await act(async () => {
      await user.keyboard("{Escape}");
    });
    expect(onClose).toHaveBeenCalled();
  });
});
