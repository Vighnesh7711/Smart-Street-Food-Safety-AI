import { defineConfig } from "vitest/config";
import path from "node:path";

/**
 * Vitest is used for pure client-side logic only -- currently just
 * `lib/qr.ts`, which decides which stall a consumer is shown after a scan.
 *
 * Deliberately no jsdom environment and no React testing setup: component
 * tests would need a browser-like environment and a camera mock, which is a
 * larger commitment than this phase warrants. If the reviewer dashboard work
 * later needs component tests, add the environment here then.
 */
export default defineConfig({
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
