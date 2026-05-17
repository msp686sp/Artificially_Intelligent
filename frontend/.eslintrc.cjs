module.exports = {
  root: true,
  env: { browser: true, es2022: true, node: true },
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react/recommended",
    "plugin:react-hooks/recommended",
    "prettier",
  ],
  parser: "@typescript-eslint/parser",
  parserOptions: {
    ecmaVersion: "latest",
    sourceType: "module",
    ecmaFeatures: { jsx: true },
  },
  settings: { react: { version: "18" } },
  plugins: ["@typescript-eslint", "react", "react-hooks", "react-refresh"],
  ignorePatterns: ["dist", "node_modules", "coverage", "test-results", "playwright-report"],
  rules: {
    "react/react-in-jsx-scope": "off",
    "react/prop-types": "off",
    "@typescript-eslint/no-unused-vars": [
      "error",
      { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
    ],
    "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
  },
  overrides: [
    {
      files: ["tests/**/*.{ts,tsx}", "src/**/*.test.{ts,tsx}"],
      env: { node: true },
      rules: {
        "@typescript-eslint/no-explicit-any": "off",
      },
    },
  ],
};
