import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
      "server-only": fileURLToPath(new URL("./tests/server-only.ts", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    clearMocks: true,
    coverage: {
      provider: "v8",
      include: ["src/lib/**/*.ts", "src/components/diagnostics/**/*.{ts,tsx}", "src/app/api/**/*.ts"],
      exclude: ["**/*.d.ts", "**/*.test.*"],
      reporter: ["text", "lcov", "json-summary"],
      thresholds: { lines: 80, statements: 80, functions: 80, branches: 70 },
    },
  },
});
