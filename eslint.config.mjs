// ESLint settings for our own JavaScript. Run with `npx eslint` from the repository root.
import js from "@eslint/js";
import globals from "globals";

export default [
  {
    // Only the child theme's scripts for now; add "tests/**/*.js" once the Playwright suite exists.
    files: ["shop/themes/ciocia/assets/js/**/*.js"],
    ...js.configs.recommended,
    languageOptions: {
      // Plain browser scripts loaded by the theme, not ES modules
      ecmaVersion: "latest",
      sourceType: "script",
      globals: globals.browser,
    },
  },
];
