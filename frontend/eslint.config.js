import js from "@eslint/js";
import i18next from "eslint-plugin-i18next";
import jsxA11y from "eslint-plugin-jsx-a11y";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "coverage", "public/mockServiceWorker.js", "playwright-report", "test-results"] },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [
      js.configs.recommended,
      ...tseslint.configs.recommendedTypeChecked,
      reactHooks.configs.flat["recommended-latest"],
      jsxA11y.flatConfigs.recommended,
    ],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      // Design §6: server text renders as plain text, and nothing personal is kept in localStorage
      // (drafts use sessionStorage only).
      "no-restricted-syntax": [
        "error",
        {
          selector: "JSXAttribute[name.name='dangerouslySetInnerHTML']",
          message: "dangerouslySetInnerHTML is banned: render server text as plain text.",
        },
        {
          selector: "Property[key.name='dangerouslySetInnerHTML']",
          message: "dangerouslySetInnerHTML is banned: render server text as plain text.",
        },
        {
          selector: "Identifier[name='localStorage']",
          message: "localStorage is banned: drafts go in sessionStorage, nothing personal is stored.",
        },
      ],
    },
  },
  {
    // Design W6: user-visible text comes from en.json through t(). Text written straight into
    // JSX (between tags, or in a text-bearing attribute) fails the lint.
    files: ["src/{features,components,layout,auth,demo}/**/*.tsx"],
    ignores: ["**/*.test.tsx"],
    plugins: { i18next },
    rules: {
      "i18next/no-literal-string": [
        "error",
        {
          mode: "jsx-only",
          "jsx-attributes": {
            include: ["label", "description", "placeholder", "title", "alt", "aria-label", "error"],
          },
        },
      ],
    },
  },
  {
    files: ["*.config.{js,ts}"],
    languageOptions: { globals: globals.node },
  },
  {
    files: ["*.config.js"],
    extends: [js.configs.recommended, tseslint.configs.disableTypeChecked],
  },
);
