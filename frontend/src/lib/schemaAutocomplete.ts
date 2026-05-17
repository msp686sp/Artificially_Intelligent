import type { SchemaTree } from "@/api/types";

/**
 * The shape that `@codemirror/lang-sql`'s `schema` option expects: a record
 * mapping table identifier -> array of column names (or {label}).
 *
 *   { my_table: ["col_a", "col_b"], "schema.tbl": ["x"] }
 *
 * We expose a helper to translate our `/api/schema` response into that shape
 * and a separate `tableList` helper for the top-level table completion list.
 */
export type SqlCompletionItem = { label: string; type?: string; detail?: string };
export type SqlSchemaSpec = Record<string, SqlCompletionItem[]>;

export function buildSqlSchemaSpec(tree: SchemaTree | undefined): SqlSchemaSpec {
  if (!tree) return {};
  const spec: SqlSchemaSpec = {};
  for (const table of tree) {
    if (!table?.name) continue;
    const columns = (table.columns ?? []).map((col) => ({
      label: col.name,
      type: "property",
      detail: col.type,
    }));
    spec[table.name] = columns;
    if (table.schema) {
      spec[`${table.schema}.${table.name}`] = columns;
    }
  }
  return spec;
}

export function buildTableList(tree: SchemaTree | undefined): SqlCompletionItem[] {
  if (!tree) return [];
  return tree
    .filter((t) => Boolean(t?.name))
    .map((t) => ({
      label: t.name,
      type: t.kind === "view" ? "type" : "class",
      detail: t.kind,
    }));
}

/**
 * SQL keyword list we add unconditionally so autocomplete is useful even
 * before the schema arrives. Kept short on purpose; CodeMirror's lang-sql
 * already provides SQL keyword completion.
 */
export const SQL_TEMPLATE_KEYWORDS: SqlCompletionItem[] = [
  { label: "SELECT", type: "keyword" },
  { label: "FROM", type: "keyword" },
  { label: "WHERE", type: "keyword" },
  { label: "GROUP BY", type: "keyword" },
  { label: "ORDER BY", type: "keyword" },
  { label: "LIMIT", type: "keyword" },
  { label: "JOIN", type: "keyword" },
  { label: "LEFT JOIN", type: "keyword" },
  { label: "INNER JOIN", type: "keyword" },
];
