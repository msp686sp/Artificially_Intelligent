import { describe, expect, it } from "vitest";
import { cn } from "@/lib/cn";

describe("cn()", () => {
  it("joins truthy classes", () => {
    expect(cn("a", "b")).toBe("a b");
  });
  it("drops falsy values", () => {
    expect(cn("a", false, null, undefined, "")).toBe("a");
  });
  it("supports conditional clsx syntax", () => {
    expect(cn("base", { active: true, disabled: false })).toBe("base active");
  });
  it("dedupes conflicting tailwind utilities (last wins)", () => {
    // tailwind-merge resolves px-2 / px-4 → keeps px-4
    expect(cn("px-2", "px-4")).toBe("px-4");
  });
  it("preserves non-conflicting tailwind classes", () => {
    expect(cn("text-sm", "font-medium")).toContain("text-sm");
    expect(cn("text-sm", "font-medium")).toContain("font-medium");
  });
  it("handles arrays", () => {
    expect(cn(["a", "b"], "c")).toBe("a b c");
  });
});
