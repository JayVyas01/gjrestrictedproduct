import { rmSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath, URL } from "node:url";
import react from "@vitejs/plugin-react";
import type { Plugin } from "vite";
import { defineConfig } from "vitest/config";

// public/mockServiceWorker.js serves mock mode only (npm run dev:mock). Vite copies public/
// into every build, so remove it from the build output: production never ships the MSW worker.
function dropMockWorker(): Plugin {
  let outDir = "dist";
  return {
    name: "drop-mock-worker",
    apply: "build",
    configResolved(config) {
      outDir = resolve(config.root, config.build.outDir);
    },
    closeBundle() {
      rmSync(resolve(outDir, "mockServiceWorker.js"), { force: true });
    },
  };
}

// `npm run dev` serves on 5173 and `npm run dev:mock` on 5174 (both fixed, see .claude/launch.json).
// The dev server forwards /api to the Django backend, so the browser sees one origin
// (same-origin session cookie and CSRF token).
export default defineConfig({
  plugins: [react(), dropMockWorker()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: false },
    },
  },
  build: {
    sourcemap: false,
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    restoreMocks: true,
  },
});
