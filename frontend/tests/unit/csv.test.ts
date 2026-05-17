import { describe, expect, it } from "vitest";
import { escapeCsvCell, toCsv } from "@/lib/csv";

describe("escapeCsvCell", () => {
  it("returns empty string for null/undefined", () => {
    expect(escapeCsvCell(null)).toBe("");
    expect(escapeCsvCell(undefined)).toBe("");
  });
  it("passes through simple values", () => {
    expect(escapeCsvCell("hello")).toBe("hello");
    expect(escapeCsvCell(42)).toBe("42");
    expect(escapeCsvCell(true)).toBe("true");
  });
  it("quotes values with commas", () => {
    expect(escapeCsvCell("a,b")).toBe('"a,b"');
  });
  it("quotes and escapes embedded quotes", () => {
    expect(escapeCsvCell('she said "hi"')).toBe('"she said ""hi"""');
  });
  it("quotes values containing newlines", () => {
    expect(escapeCsvCell("a\nb")).toBe('"a\nb"');
    expect(escapeCsvCell("a\r\nb")).toBe('"a\r\nb"');
  });
});

describe("toCsv", () => {
  it("returns empty string for empty input without columns", () => {
    expect(toCsv([])).toBe("");
  });
  it("renders header + rows", () => {
    const csv = toCsv([
      { name: "alice", age: 30 },
      { name: "bob", age: 28 },
    ]);
    expect(csv).toBe("name,age\nalice,30\nbob,28");
  });
  it("uses explicit column order if provided", () => {
    const csv = toCsv(
      [{ name: "alice", age: 30 }],
      ["age", "name"],
    );
    expect(csv).toBe("age,name\n30,alice");
  });
  it("escapes problematic cells", () => {
    const csv = toCsv([{ a: "x,y", b: 'has "quotes"' }]);
    expect(csv).toContain('"x,y"');
    expect(csv).toContain('"has ""quotes"""');
  });
  it("fills null/undefined as empty", () => {
    const csv = toCsv([{ a: 1, b: null, c: undefined }], ["a", "b", "c"]);
    expect(csv).toBe("a,b,c\n1,,");
  });
});
