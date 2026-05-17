import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * cn() — class-name helper that combines clsx (conditional classes)
 * with tailwind-merge (deduplicates conflicting Tailwind utilities,
 * keeping the last one). This is the standard pattern for design
 * systems that compose Tailwind classes across component variants.
 *
 * @example
 *   cn("px-2 py-1", isLarge && "px-4", className)
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
