import CodeMirror, { type Extension } from "@uiw/react-codemirror";
import { sql } from "@codemirror/lang-sql";
import { yaml } from "@codemirror/lang-yaml";
import { useMemo } from "react";
import { cn } from "@/lib/cn";

export type CodeLanguage = "sql" | "yaml" | "plain";

interface CodeBlockProps {
  value: string;
  language?: CodeLanguage;
  /** Visible line count (rough). Defaults to ~12 lines via maxHeight. */
  maxHeight?: string;
  className?: string;
  /** When true, copy-to-clipboard affordance is shown. */
  showCopy?: boolean;
  "data-testid"?: string;
}

/**
 * CodeBlock — read-only CodeMirror viewer. Used to display SQL
 * snippets, YAML configs, and rendered query text. For editable
 * editors (SQL workbench, filters editor) other agents should use
 * @uiw/react-codemirror directly with their own extensions.
 */
export function CodeBlock({
  value,
  language = "plain",
  maxHeight,
  className,
  showCopy,
  ...rest
}: CodeBlockProps) {
  const extensions = useMemo<Extension[]>(() => {
    switch (language) {
      case "sql":
        return [sql()];
      case "yaml":
        return [yaml()];
      default:
        return [];
    }
  }, [language]);

  const onCopy = async () => {
    if (typeof navigator === "undefined" || !navigator.clipboard) return;
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      /* ignore */
    }
  };

  return (
    <div
      className={cn("relative rounded-md border border-border-subtle bg-bg-subtle", className)}
      data-testid={rest["data-testid"]}
    >
      <CodeMirror
        value={value}
        editable={false}
        readOnly
        extensions={extensions}
        theme="dark"
        basicSetup={{
          lineNumbers: true,
          foldGutter: false,
          highlightActiveLine: false,
          highlightActiveLineGutter: false,
        }}
        height={maxHeight}
        className="overflow-hidden rounded-md text-xs"
      />
      {showCopy && (
        <button
          type="button"
          onClick={onCopy}
          className="absolute right-2 top-2 inline-flex h-7 items-center rounded border border-border bg-bg-panel px-2 text-xs text-fg-muted hover:text-fg"
          aria-label="Copy code"
        >
          Copy
        </button>
      )}
    </div>
  );
}
