/**
 * The in-browser frame producer.
 *
 * Simulates the sensor, extracts features, scores them with the exported
 * autoencoder and applies the same diagnosis rules as the server -- then emits
 * a `Frame` byte-for-byte compatible with the WebSocket one. The dashboard
 * cannot tell the two apart, which is the whole point: the published site
 * stays fully interactive whether or not a backend is awake.
 */

import type { Curve, FaultState, Frame, IsoZone, Status, Verdict } from "../types.ts";
import { Autoencoder, type BundleJson } from "./autoencoder.ts";
import { DEFAULT_MACHINE, describe, extract, type MachineSpec } from "./features.ts";
import { HEALTHY, Stream, type FaultSpec } from "./simulator.ts";

const WAVEFORM_SAMPLES = 384;
const SPECTRUM_BUCKETS = 192;
const SPECTRUM_MAX_HZ = 6000;
const ENVELOPE_MAX_HZ = 500;
const DEFECT_Z_THRESHOLD = 3.5;

const HUMAN_LABELS: Record<string, string> = {
  healthy: "No fault signature",
  outer_race: "Bearing outer-race defect",
  inner_race: "Bearing inner-race defect",
  ball: "Rolling-element (ball) defect",
  imbalance: "Rotor imbalance",
  looseness: "Mechanical looseness",
  unknown: "Unclassified anomaly",
};

/** ISO 20816-3 zones for medium machines, RMS velocity in mm/s. */
export function isoZone(velocity: number): IsoZone {
  if (velocity <= 2.8) return "A";
  if (velocity <= 4.5) return "B";
  if (velocity <= 7.1) return "C";
  return "D";
}

/** Kept in step with WATCH_RATIO / CRITICAL_RATIO in `vfactory/detector.py`. */
const WATCH_RATIO = 0.85;
const CRITICAL_RATIO = 4;

function status(score: number, threshold: number): Status {
  const ratio = threshold > 0 ? score / threshold : 0;
  if (ratio >= CRITICAL_RATIO) return "critical";
  if (ratio >= 1) return "warning";
  if (ratio >= WATCH_RATIO) return "watch";
  return "normal";
}

/** Peak-pool a spectrum: averaging would erase the narrow lines that matter. */
function peakPool(
  freqs: Float64Array,
  amp: Float64Array,
  maxHz: number,
  buckets: number,
): Curve {
  let count = 0;
  while (count < freqs.length && freqs[count] <= maxHz) count++;
  if (count <= buckets) {
    return {
      x: Array.from(freqs.subarray(0, count)),
      y: Array.from(amp.subarray(0, count)),
    };
  }

  const x: number[] = [];
  const y: number[] = [];
  for (let b = 0; b < buckets; b++) {
    const lo = Math.floor((b * count) / buckets);
    const hi = Math.floor(((b + 1) * count) / buckets);
    if (hi <= lo) continue;
    let best = lo;
    for (let k = lo; k < hi; k++) if (amp[k] > amp[best]) best = k;
    x.push(freqs[best]);
    y.push(amp[best]);
  }
  return { x, y };
}

/** Name the likely mechanical cause. Mirrors `vfactory/detector.py`. */
function diagnose(z: Record<string, number>): {
  diagnosis: string;
  confidence: number;
  evidence: string[];
} {
  const evidence: string[] = [];
  const bearing: Record<string, number> = {
    outer_race: Math.max(z.env_bpfo_db, z.env_bpfo_h2_db),
    inner_race: Math.max(z.env_bpfi_db, z.env_bpfi_h2_db),
    ball: Math.max(z.env_bsf_db, z.env_ftf_db),
  };
  const ranked = Object.entries(bearing).sort((a, b) => b[1] - a[1]);
  const [bestBearing, bestZ] = ranked[0];
  const lowFreqLift = Math.max(z.band_0_200_db, z.band_200_600_db);
  const impulsive = z.kurtosis;

  if (bestZ >= DEFECT_Z_THRESHOLD && bestZ >= lowFreqLift) {
    const probe = { outer_race: "BPFO", inner_race: "BPFI", ball: "BSF" }[
      bestBearing as "outer_race" | "inner_race" | "ball"
    ];
    evidence.push(`${probe} envelope line is ${bestZ.toFixed(1)} sigma above the healthy baseline`);
    if (impulsive > 2) {
      evidence.push(`waveform is impulsive (kurtosis ${impulsive >= 0 ? "+" : ""}${impulsive.toFixed(1)} sigma)`);
    }
    // Blend "how far it rose" with "how clearly it beat the next candidate":
    // margin alone under-rates an obvious defect whose harmonics also lift the
    // neighbouring probes.
    const runnerUp = ranked[1][1];
    const margin = bestZ - Math.max(runnerUp, DEFECT_Z_THRESHOLD);
    const strength = Math.min(1, Math.max(0, (bestZ - DEFECT_Z_THRESHOLD) / 8));
    const separation = Math.min(1, Math.max(0, margin / 5));
    return {
      diagnosis: bestBearing,
      confidence: Number((0.35 + 0.64 * (0.5 * strength + 0.5 * separation)).toFixed(3)),
      evidence,
    };
  }

  if (lowFreqLift >= 2.5) {
    const harmonics = z.band_200_600_db;
    let cause: string;
    if (harmonics > z.band_0_200_db || (z.rms > 3 && impulsive > -1)) {
      evidence.push(`shaft-harmonic band lifted ${harmonics.toFixed(1)} sigma with a low crest factor`);
      cause = "looseness";
    } else {
      evidence.push(`1x running-speed component up ${Math.max(z.env_shaft_1x_db, lowFreqLift).toFixed(1)} sigma`);
      cause = "imbalance";
    }
    evidence.push(
      `overall level ${z.rms >= 0 ? "+" : ""}${z.rms.toFixed(1)} sigma, kurtosis ${impulsive >= 0 ? "+" : ""}${impulsive.toFixed(1)} sigma`,
    );
    return {
      diagnosis: cause,
      confidence: Math.min(0.95, Math.max(0.35, lowFreqLift / 8)),
      evidence,
    };
  }

  return { diagnosis: "unknown", confidence: 0.3, evidence };
}

export interface OfflineEngineOptions {
  machine?: MachineSpec;
  seed?: number;
}

export class OfflineEngine {
  private readonly model: Autoencoder;
  private readonly machine: MachineSpec;
  private stream: Stream;
  private seq = 0;

  constructor(bundle: BundleJson, options: OfflineEngineOptions = {}) {
    this.model = new Autoencoder(bundle);
    this.machine = options.machine ?? DEFAULT_MACHINE;
    this.stream = new Stream(HEALTHY, this.machine, options.seed);
  }

  get autoencoder(): Autoencoder {
    return this.model;
  }

  setFault(fault: Partial<FaultSpec>): void {
    this.stream.fault = { ...this.stream.fault, ...fault };
  }

  next(advanceSeconds?: number): Frame {
    const window = this.stream.next(advanceSeconds);
    const fault = this.stream.fault;
    const { values, spectrum, envelope, velocityRmsMmS } = extract(
      window,
      this.machine,
      fault.shaftRpm,
    );

    const score = this.model.score(values);
    const isAnomaly = score > this.model.threshold;
    const z = this.model.zScores(values);
    const { diagnosis, confidence, evidence } = isAnomaly
      ? diagnose(z)
      : { diagnosis: "healthy", confidence: 0, evidence: [] as string[] };

    const verdict: Verdict = {
      score,
      threshold: this.model.threshold,
      is_anomaly: isAnomaly,
      health_index: this.model.healthIndex(score),
      status: status(score, this.model.threshold),
      diagnosis: diagnosis as Verdict["diagnosis"],
      diagnosis_label: HUMAN_LABELS[diagnosis] ?? HUMAN_LABELS.unknown,
      confidence,
      evidence,
      contributors: this.model.topContributors(values, 4),
      velocity_rms_mm_s: velocityRmsMmS,
      iso_zone: isoZone(velocityRmsMmS),
    };

    let envelopeCount = 0;
    while (
      envelopeCount < envelope.freqs.length &&
      envelope.freqs[envelopeCount] <= ENVELOPE_MAX_HZ
    ) {
      envelopeCount++;
    }

    const state: FaultState = {
      mode: fault.mode,
      severity: fault.severity,
      shaft_rpm: fault.shaftRpm,
      load: fault.load,
    };

    return {
      seq: this.seq++,
      t: this.stream.elapsedSeconds,
      fault: state,
      verdict,
      waveform: Array.from(window.subarray(0, WAVEFORM_SAMPLES)),
      spectrum: peakPool(spectrum.freqs, spectrum.amp, SPECTRUM_MAX_HZ, SPECTRUM_BUCKETS),
      envelope: {
        x: Array.from(envelope.freqs.subarray(0, envelopeCount)),
        y: Array.from(envelope.amp.subarray(0, envelopeCount)),
      },
      features: describe(values),
    };
  }
}

export { describe, extract } from "./features.ts";
