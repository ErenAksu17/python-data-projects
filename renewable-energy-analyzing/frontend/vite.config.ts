import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { viteSingleFile } from "vite-plugin-singlefile";
import path from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

// Two build modes:
//   default        → external JS/CSS assets, served by FastAPI (CSP script-src
//                    'self' allows them — no inline script).
//   --mode standalone → everything inlined into one index.html (for the
//                    offline file + Claude artifact, where inline is fine).
export default defineConfig(({ mode }) => {
  const standalone = mode === "standalone";
  return {
    plugins: [
      react(),
      tailwindcss(),
      ...(standalone ? [viteSingleFile()] : []),
    ],
    base: standalone ? "./" : "/",
    resolve: {
      alias: { "@": path.resolve(rootDir, "./src") },
    },
    build: {
      outDir: standalone ? "dist-single" : "dist",
      emptyOutDir: true,
    },
    server: {
      proxy: {
        "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
        "/healthz": { target: "http://127.0.0.1:8000", changeOrigin: true },
      },
    },
  };
});
