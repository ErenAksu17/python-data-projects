import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import type { IsoZone, Status } from "./types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Fixed decimals, tolerant of the gap before the first frame arrives. */
export function num(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return value.toFixed(digits);
}

/** Reconstruction errors span orders of magnitude; keep them readable. */
export function compact(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  if (value === 0) return "0";
  const magnitude = Math.abs(value);
  if (magnitude >= 1000 || magnitude < 0.01) return value.toExponential(2);
  return value.toFixed(magnitude >= 10 ? 1 : 3);
}

export function pct(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

const FAULT_LABELS: Record<string, string> = {
  healthy: "Healthy",
  outer_race: "Outer race",
  inner_race: "Inner race",
  ball: "Rolling element",
  imbalance: "Imbalance",
  looseness: "Looseness",
  unknown: "Unclassified",
};

export function faultLabel(mode: string): string {
  return FAULT_LABELS[mode] ?? mode;
}

export function featureLabel(name: string): string {
  return name
    .replace(/_db$/, " (dB)")
    .replace(/^band_(\d+)_(\d+)/, "band $1–$2 Hz")
    .replace(/^env_/, "envelope ")
    .replace(/_h2/, " 2×")
    .replace(/_/g, " ");
}

/** One place that decides what colour a machine state is, everywhere. */
export const STATUS_STYLE: Record<
  Status,
  { label: string; text: string; bg: string; ring: string; badge: string }
> = {
  normal: {
    label: "Normal",
    text: "text-[var(--success)]",
    bg: "bg-[var(--success)]",
    ring: "ring-[var(--success)]/30",
    badge: "bg-[var(--success)]/15 text-[var(--success)]",
  },
  watch: {
    label: "Watch",
    text: "text-[var(--warning)]",
    bg: "bg-[var(--warning)]",
    ring: "ring-[var(--warning)]/30",
    badge: "bg-[var(--warning)]/18 text-[var(--warning)]",
  },
  warning: {
    label: "Alarm",
    text: "text-[var(--critical)]",
    bg: "bg-[var(--critical)]",
    ring: "ring-[var(--critical)]/30",
    badge: "bg-[var(--critical)]/15 text-[var(--critical)]",
  },
  critical: {
    label: "Critical",
    text: "text-[var(--critical)]",
    bg: "bg-[var(--critical)]",
    ring: "ring-[var(--critical)]/40",
    badge: "bg-[var(--critical)]/25 text-[var(--critical)]",
  },
};

export const ISO_ZONE_NOTE: Record<IsoZone, string> = {
  A: "Newly commissioned",
  B: "Acceptable long-term",
  C: "Unsatisfactory — investigate",
  D: "Severe — damage likely",
};

/** Keep the last `size` items without mutating the array we were handed. */
export function pushBounded<T>(list: T[], item: T, size: number): T[] {
  const next = list.length >= size ? list.slice(list.length - size + 1) : list.slice();
  next.push(item);
  return next;
}
