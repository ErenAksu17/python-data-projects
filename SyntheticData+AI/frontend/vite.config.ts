import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

// Where `npm run dev` proxies /api and /healthz. Override when the API is on a
// port other than the default, e.g. API_PROXY_TARGET=http://127.0.0.1:8010.
const apiTarget = process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000";

// `base` is set from BASE_PATH so the same bundle can be served from a domain
// root (Cloudflare Pages, the FastAPI container) or from a repository
// subpath (GitHub Pages, /python-data-projects/).
export default defineConfig(() => ({
  plugins: [react(), tailwindcss()],
  base: process.env.BASE_PATH ?? "/",
  resolve: {
    alias: { "@": path.resolve(rootDir, "./src") },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    // The model bundle is fetched at runtime, not inlined, so the browser can
    // cache it separately from the app shell.
    assetsInlineLimit: 4096,
  },
  server: {
    proxy: {
      "/api": { target: apiTarget, changeOrigin: true, ws: true },
      "/healthz": { target: apiTarget, changeOrigin: true },
    },
  },
}));
