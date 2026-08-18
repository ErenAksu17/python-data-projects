import type { Dataset } from "./types";

declare global {
  interface Window {
    __DATA__?: Dataset;
  }
}

/**
 * Load the dataset. In the standalone/artifact build the whole payload is
 * embedded as `window.__DATA__`; when served by FastAPI we fetch the read-only
 * bootstrap endpoint instead. Both return the identical shape.
 */
export async function loadDataset(): Promise<Dataset> {
  if (typeof window !== "undefined" && window.__DATA__) {
    return window.__DATA__;
  }
  const res = await fetch("/api/dataset", {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) throw new Error(`Veri yüklenemedi (HTTP ${res.status})`);
  return (await res.json()) as Dataset;
}
