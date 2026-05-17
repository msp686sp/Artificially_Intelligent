import { describe, expect, it } from "vitest";
import {
  buildSqlSchemaSpec,
  buildTableList,
} from "@/lib/schemaAutocomplete";
import type { SchemaTree } from "@/api/types";

const fixture: SchemaTree = [
  {
    kind: "table",
    name: "zip_scores",
    row_count: 42,
    columns: [
      { name: "zcta5", type: "VARCHAR", nullable: false },
      { name: "market_score", type: "DOUBLE", nullable: true },
    ],
  },
  {
    kind: "view",
    name: "v_top_zips",
    row_count: null,
    columns: [{ name: "zcta5", type: "VARCHAR", nullable: false }],
    schema: "main",
  },
];

describe("buildSqlSchemaSpec", () => {
  it("maps each table to its column completions", () => {
    const spec = buildSqlSchemaSpec(fixture);
    expect(Object.keys(spec)).toContain("zip_scores");
    expect(spec.zip_scores).toEqual([
      { label: "zcta5", type: "property", detail: "VARCHAR" },
      { label: "market_score", type: "property", detail: "DOUBLE" },
    ]);
  });

  it("registers schema-qualified aliases for tables with a schema", () => {
    const spec = buildSqlSchemaSpec(fixture);
    expect(spec["main.v_top_zips"]).toBeDefined();
    expect(spec["main.v_top_zips"]).toEqual(spec.v_top_zips);
  });

  it("returns an empty object for undefined / empty input", () => {
    expect(buildSqlSchemaSpec(undefined)).toEqual({});
    expect(buildSqlSchemaSpec([])).toEqual({});
  });

  it("ignores tables missing a name", () => {
    const spec = buildSqlSchemaSpec([
      // @ts-expect-error — intentionally invalid
      { kind: "table", name: "", columns: [] },
      ...fixture,
    ]);
    expect(Object.keys(spec)).not.toContain("");
  });

  it("handles tables that lack a columns array", () => {
    const spec = buildSqlSchemaSpec([
      // @ts-expect-error — runtime shape we want to survive
      { kind: "table", name: "weird", row_count: null },
    ]);
    expect(spec.weird).toEqual([]);
  });
});

describe("buildTableList", () => {
  it("returns one completion per table with kind detail", () => {
    const list = buildTableList(fixture);
    expect(list).toHaveLength(2);
    expect(list[0]).toMatchObject({ label: "zip_scores", detail: "table" });
    expect(list[1]).toMatchObject({ label: "v_top_zips", detail: "view" });
  });

  it("uses 'type' completion type for views, 'class' for tables", () => {
    const list = buildTableList(fixture);
    expect(list.find((c) => c.label === "zip_scores")?.type).toBe("class");
    expect(list.find((c) => c.label === "v_top_zips")?.type).toBe("type");
  });

  it("returns [] for undefined input", () => {
    expect(buildTableList(undefined)).toEqual([]);
  });
});
