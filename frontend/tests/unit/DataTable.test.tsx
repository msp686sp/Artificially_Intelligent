import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { ColumnDef } from "@tanstack/react-table";
import { DataTable } from "@/components/DataTable";

interface Row {
  name: string;
  score: number;
}

const columns: ColumnDef<Row, any>[] = [
  { accessorKey: "name", header: "Name", id: "name" },
  { accessorKey: "score", header: "Score", id: "score" },
];

const data: Row[] = [
  { name: "alpha", score: 90 },
  { name: "bravo", score: 75 },
  { name: "charlie", score: 60 },
];

describe("<DataTable>", () => {
  it("renders the table layout on desktop", () => {
    render(<DataTable<Row> tableKey="t1" data={data} columns={columns} layout="table" />);
    const table = screen.getByTestId("data-table");
    expect(table.getAttribute("data-layout")).toBe("table");
    // Header is rendered
    expect(within(table).getByText("Name")).toBeInTheDocument();
    expect(within(table).getByText("Score")).toBeInTheDocument();
    // Body has all rows
    expect(within(table).getByText("alpha")).toBeInTheDocument();
    expect(within(table).getByText("bravo")).toBeInTheDocument();
    expect(within(table).getByText("charlie")).toBeInTheDocument();
  });

  it("collapses to cards on mobile layout", () => {
    render(<DataTable<Row> tableKey="t2" data={data} columns={columns} layout="cards" />);
    const table = screen.getByTestId("data-table");
    expect(table.getAttribute("data-layout")).toBe("cards");
    expect(screen.getByTestId("data-table-cards")).toBeInTheDocument();
    // Cards should still expose the data
    expect(screen.getByText("alpha")).toBeInTheDocument();
  });

  it("filters rows via the global filter", async () => {
    const user = userEvent.setup();
    render(<DataTable<Row> tableKey="t3" data={data} columns={columns} layout="table" />);
    const input = screen.getByLabelText("Filter rows");
    await user.type(input, "alpha");
    expect(screen.getByText("alpha")).toBeInTheDocument();
    expect(screen.queryByText("bravo")).not.toBeInTheDocument();
  });

  it("toggles density via the toolbar button", async () => {
    const user = userEvent.setup();
    render(<DataTable<Row> tableKey="t4" data={data} columns={columns} layout="table" />);
    const btn = screen.getByRole("button", { name: /compact/i });
    await user.click(btn);
    // After click, the same button toggles to Comfortable
    expect(screen.getByRole("button", { name: /comfortable/i })).toBeInTheDocument();
  });

  it("renders an empty state when there are no rows", () => {
    render(
      <DataTable<Row>
        tableKey="t5"
        data={[]}
        columns={columns}
        layout="table"
        emptyMessage="Nothing yet"
      />,
    );
    expect(screen.getByText("Nothing yet")).toBeInTheDocument();
  });

  it("renders an empty state on mobile when there are no rows", () => {
    render(
      <DataTable<Row>
        tableKey="t6"
        data={[]}
        columns={columns}
        layout="cards"
        emptyMessage="No data"
      />,
    );
    expect(screen.getByText("No data")).toBeInTheDocument();
  });
});
