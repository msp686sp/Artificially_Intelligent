import { useMemo } from "react";
import CodeMirror, { type Extension } from "@uiw/react-codemirror";
import { sql, SQLDialect } from "@codemirror/lang-sql";
import { keymap } from "@codemirror/view";
import { Prec } from "@codemirror/state";
import {
  buildSqlSchemaSpec,
  buildTableList,
} from "@/lib/schemaAutocomplete";
import type { SchemaTree } from "@/api/types";
import { cn } from "@/lib/cn";

export interface SqlEditorProps {
  value: string;
  onChange: (value: string) => void;
  schema?: SchemaTree;
  onRun?: () => void;
  height?: string;
  className?: string;
  readOnly?: boolean;
  placeholder?: string;
}

const DuckDBDialect = SQLDialect.define({
  keywords:
    "select from where group by order having limit offset join inner left right full outer on as distinct union all except intersect with case when then else end and or not in like ilike between is null cast over partition window true false",
});

export default function SqlEditor({
  value,
  onChange,
  schema,
  onRun,
  height = "16rem",
  className,
  readOnly,
  placeholder,
}: SqlEditorProps) {
  const extensions = useMemo<Extension[]>(() => {
    const tables = buildSqlSchemaSpec(schema);
    const sqlExt = sql({
      dialect: DuckDBDialect,
      upperCaseKeywords: false,
      schema: tables,
      tables: buildTableList(schema),
    });
    const runKey = Prec.highest(
      keymap.of([
        {
          key: "Mod-Enter",
          preventDefault: true,
          run: () => {
            onRun?.();
            return true;
          },
        },
      ]),
    );
    return [sqlExt, runKey];
  }, [schema, onRun]);

  return (
    <div
      className={cn(
        "overflow-hidden rounded-lg border border-bg-subtle bg-bg-panel",
        className,
      )}
      data-testid="sql-editor"
    >
      <CodeMirror
        value={value}
        height={height}
        theme="dark"
        extensions={extensions}
        onChange={onChange}
        readOnly={readOnly}
        placeholder={placeholder}
        basicSetup={{
          lineNumbers: true,
          highlightActiveLine: true,
          autocompletion: true,
          bracketMatching: true,
          closeBrackets: true,
        }}
      />
    </div>
  );
}
