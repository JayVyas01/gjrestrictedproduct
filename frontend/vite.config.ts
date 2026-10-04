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

// Vendor libraries in long-lived chunks of their own (they change less often than the app).
const VENDOR_CHUNKS: Record<string, string[]> = {
  react: ["react", "react-dom", "scheduler", "react-router", "react-router-dom", "@remix-run"],
  mantine: [
    "@mantine",
    "@floating-ui",
    "react-remove-scroll",
    "react-remove-scroll-bar",
    "react-style-singleton",
    "react-transition-group",
    "react-number-format",
    "react-textarea-autosize",
    "use-callback-ref",
    "use-sidecar",
    "dayjs",
  ],
  query: ["@tanstack"],
  i18n: ["i18next", "react-i18next"],
};

/** The package a module belongs to ("@scope" for scoped packages), or null for app code. */
function packageOf(id: string): string | null {
  const at = id.lastIndexOf("/node_modules/");
  if (at < 0) return null;
  return id.slice(at + "/node_modules/".length).split("/")[0];
}

// The route pages load lazily (src/lazyPage.tsx): each feature area's modules form one chunk.
// Everything else in src (shell, sign-in, api, components, and each feature's paths.ts, which
// the shell links to) is named "app" explicitly: Rollup would otherwise pull shared modules into
// whichever feature chunk uses them, and the shell would then load that feature up front.
function chunkFor(id: string): string | undefined {
  const pkg = packageOf(id);
  if (pkg) {
    const vendor = Object.keys(VENDOR_CHUNKS).find((chunk) => VENDOR_CHUNKS[chunk].includes(pkg));
    return vendor && `vendor-${vendor}`;
  }
  const feature = /\/src\/features\/([^/]+)\/(?!paths\.ts$)/.exec(id);
  if (feature) return `feature-${feature[1]}`;
  return /\/src\//.test(id) ? "app" : undefined;
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
    rollupOptions: { output: { manualChunks: chunkFor } },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    restoreMocks: true,
  },
});
