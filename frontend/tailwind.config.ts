import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: "#0b0d12",
          subtle: "#11141b",
          panel: "#171a23",
        },
        fg: {
          DEFAULT: "#e6e8ee",
          muted: "#9aa0ad",
          subtle: "#6b7080",
        },
        accent: {
          DEFAULT: "#5b8def",
          hover: "#7a9ff2",
        },
        success: "#3aaf85",
        warning: "#d9a441",
        danger: "#e15c5c",
        score: {
          high: "#3aaf85",
          mid: "#d9a441",
          low: "#e15c5c",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      spacing: { 18: "4.5rem", 88: "22rem" },
    },
  },
  plugins: [],
} satisfies Config;
