// ESLint settings for our own JavaScript. Run with `npx eslint` from the repository root.
import js from "@eslint/js";
import globals from "globals";

export default [
  // HTML reports bundle the trace viewer's scripts; never lint them
  { ignores: ["tests/playwright-report/", "tests/test-results/"] },
  {

    files: ["shop/themes/ciocia/assets/js/**/*.js"],
    ...js.configs.recommended,
    languageOptions: {
      // Plain browser scripts loaded by the theme, not ES modules
      ecmaVersion: "latest",
      sourceType: "script",
      globals: globals.browser,
    },
  },
  {
    files: ["tests/**/*.js"],
    ...js.configs.recommended,
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: globals.node,
    },
    rules: {
      // A separate `rules` key would replace the recommended rules, so spread them first
      ...js.configs.recommended.rules,
      // Playwright fixtures must destructure their first argument even when they use no other fixture
      "no-empty-pattern": ["error", { allowObjectPatternsAsParameters: true }],
      // W4: no fixed sleeps as synchronisation, wait on a condition instead
      "no-restricted-properties": [
        "error",
        { property: "waitForTimeout", message: "No fixed sleeps (W4). Wait on a condition: expect(...), waitForURL, waitForResponse." },
      ],
    },
  },
];
