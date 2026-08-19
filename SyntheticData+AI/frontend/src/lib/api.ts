/**
 * Talking to the FastAPI service.
 *
 * `VITE_API_BASE` points the bundle at a deployed API; left empty it uses the
 * same origin, which is what the dev proxy and the container both want. When
 * no API answers, the app falls back to the in-browser engine rather than
 * showing an error page -- a static deploy is a first-class mode, not a
 * degraded one.
 */

import type { AblationReport, BenchmarkReport, MachineInfo } from "./types";
import type { BundleJson } from "./offline/autoencoder";

export const API_BASE: string = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

/** Where the offline engine reads its weights when no API is reachable. */
const LOCAL_MODEL_URL = `${import.meta.env.BASE_URL}model.json`;

export class ApiUnavailable extends Error {}

async function getJson<T>(path: string, timeoutMs = 4000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${API_BASE}${path}`, { signal: controller.signal });
    if (!response.ok) throw new ApiUnavailable(`${path} responded ${response.status}`);
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiUnavailable) throw error;
    throw new ApiUnavailable(`${path} unreachable: ${(error as Error).message}`);
  } finally {
    clearTimeout(timer);
  }
}

export function fetchMachine(): Promise<MachineInfo> {
  return getJson<MachineInfo>("/api/machine");
}

export function fetchBenchmark(): Promise<BenchmarkReport> {
  return getJson<BenchmarkReport>("/api/benchmark");
}

export function fetchAblation(): Promise<AblationReport> {
  return getJson<AblationReport>("/api/ablation");
}

/** Probe the API quickly so the UI can pick a mode without a long stall. */
export async function probeApi(): Promise<boolean> {
  try {
    const health = await getJson<{ status: string; model_loaded: boolean }>("/healthz", 1500);
    return health.model_loaded;
  } catch {
    return false;
  }
}

/**
 * Load the weight bundle, preferring the API so a redeployed model is picked
 * up without rebuilding the frontend, and falling back to the copy shipped
 * alongside the static bundle.
 */
export async function loadModelBundle(): Promise<BundleJson> {
  try {
    return await getJson<BundleJson>("/api/model/weights", 3000);
  } catch {
    const response = await fetch(LOCAL_MODEL_URL);
    if (!response.ok) throw new Error("no model bundle available");
    return (await response.json()) as BundleJson;
  }
}

/** Static copies of the reports, used when the API is not there to serve them. */
export async function loadStaticReport<T>(name: string): Promise<T | null> {
  try {
    const response = await fetch(`${import.meta.env.BASE_URL}${name}`);
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

export function streamUrl(): string {
  if (API_BASE) {
    return `${API_BASE.replace(/^http/, "ws")}/api/stream`;
  }
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${window.location.host}/api/stream`;
}
