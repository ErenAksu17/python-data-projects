/**
 * The 26 diagnostic features, in the exact order the model expects.
 *
 * A faithful port of `vfactory/features.py`. Order matters: the weight bundle
 * indexes features positionally, so a reordering here would silently produce
 * nonsense rather than an error. The parity script guards against that.
 */

import {
  amplitudeSpectrum,
  envelopeSpectrum,
  mean,
  median,
  velocityRmsMmS,
  type Spectrum,
} from "./dsp.ts";

const EPS = 1e-12;

export const SPECTRAL_BANDS: Array<[number, number]> = [
  [0, 200],
  [200, 600],
  [600, 1500],
  [1500, 2500],
  [2500, 3500],
  [3500, 6000],
];

export const ENVELOPE_BAND: [number, number] = [2000, 4500];

export const FEATURE_NAMES = [
  "rms",
  "peak",
  "peak_to_peak",
  "crest_factor",
  "kurtosis",
  "skewness",
  "shape_factor",
  "impulse_factor",
  "clearance_factor",
  "zero_crossing_rate",
  "band_0_200_db",
  "band_200_600_db",
  "band_600_1500_db",
  "band_1500_2500_db",
  "band_2500_3500_db",
  "band_3500_6000_db",
  "spectral_centroid",
  "spectral_spread",
  "spectral_entropy",
  "env_shaft_1x_db",
  "env_bpfo_db",
  "env_bpfo_h2_db",
  "env_bpfi_db",
  "env_bpfi_h2_db",
  "env_bsf_db",
  "env_ftf_db",
] as const;

export type FeatureName = (typeof FEATURE_NAMES)[number];

/** Envelope probes as [defect key, harmonic], matching ENVELOPE_PROBES. */
const ENVELOPE_PROBES: Array<[string, number]> = [
  ["shaft", 1],
  ["bpfo", 1],
  ["bpfo", 2],
  ["bpfi", 1],
  ["bpfi", 2],
  ["bsf", 1],
  ["ftf", 1],
];

export interface BearingOrders {
  bpfo: number;
  bpfi: number;
  bsf: number;
  ftf: number;
}

export interface MachineSpec {
  sampleRateHz: number;
  windowSize: number;
  shaftRpm: number;
  resonanceHz: number;
  resonanceDecay: number;
  noiseG: number;
  baselineImbalanceG: number;
  orders: BearingOrders;
}

export const DEFAULT_MACHINE: MachineSpec = {
  sampleRateHz: 12000,
  windowSize: 2048,
  shaftRpm: 1797,
  resonanceHz: 3000,
  resonanceDecay: 900,
  noiseG: 0.035,
  baselineImbalanceG: 0.035,
  // SKF 6205-2RS geometry, as multiples of shaft speed.
  orders: { bpfo: 3.5848, bpfi: 5.4152, bsf: 2.3567, ftf: 0.3983 },
};

/** Matches `np.signbit`: negative zero counts as negative. */
function signbit(value: number): boolean {
  return value < 0 || Object.is(value, -0);
}

function timeFeatures(signal: Float64Array): number[] {
  const n = signal.length;
  const avg = mean(signal);

  let sumSquares = 0;
  let peak = 0;
  let min = Infinity;
  let max = -Infinity;
  let absMean = 0;
  let sqrtMean = 0;
  let m2 = 0;
  let m3 = 0;
  let m4 = 0;
  let crossings = 0;

  for (let i = 0; i < n; i++) {
    const v = signal[i];
    sumSquares += v * v;
    const abs = Math.abs(v);
    if (abs > peak) peak = abs;
    if (v < min) min = v;
    if (v > max) max = v;
    absMean += abs;
    sqrtMean += Math.sqrt(abs);
    const c = v - avg;
    m2 += c * c;
    m3 += c * c * c;
    m4 += c * c * c * c;
    if (i > 0 && signbit(v) !== signbit(signal[i - 1])) crossings++;
  }

  const rms = Math.sqrt(sumSquares / n);
  absMean = absMean / n + EPS;
  sqrtMean = (sqrtMean / n) ** 2 + EPS;
  const std = Math.sqrt(m2 / n) + EPS;

  return [
    rms,
    peak,
    max - min,
    peak / (rms + EPS),
    m4 / n / std ** 4,
    m3 / n / std ** 3,
    rms / absMean,
    peak / absMean,
    peak / sqrtMean,
    crossings / (n - 1),
  ];
}

function spectralFeatures({ freqs, amp }: Spectrum): number[] {
  const bins = freqs.length;
  const power = new Float64Array(bins);
  let total = 0;
  for (let k = 0; k < bins; k++) {
    power[k] = amp[k] * amp[k];
    total += power[k];
  }
  total += EPS;

  const bands = SPECTRAL_BANDS.map(([lo, hi]) => {
    let sum = 0;
    for (let k = 0; k < bins; k++) {
      if (freqs[k] >= lo && freqs[k] < hi) sum += power[k];
    }
    return 10 * Math.log10(sum / total + EPS);
  });

  let centroid = 0;
  for (let k = 0; k < bins; k++) centroid += freqs[k] * power[k];
  centroid /= total;

  let spread = 0;
  let entropy = 0;
  for (let k = 0; k < bins; k++) {
    spread += (freqs[k] - centroid) ** 2 * power[k];
    const p = power[k] / total;
    entropy += p * Math.log2(p + EPS);
  }
  spread = Math.sqrt(spread / total);
  entropy = -entropy / Math.log2(bins);

  return [...bands, centroid, spread, entropy];
}

function envelopeFeatures(
  { freqs, amp }: Spectrum,
  defectHz: Record<string, number>,
  toleranceHz: number,
): number[] {
  const floor = median(amp) + EPS;
  return ENVELOPE_PROBES.map(([key, harmonic]) => {
    const target = defectHz[key] * harmonic;
    let peak = 0;
    for (let k = 0; k < freqs.length; k++) {
      if (Math.abs(freqs[k] - target) <= toleranceHz && amp[k] > peak) peak = amp[k];
    }
    return 20 * Math.log10(peak / floor + EPS);
  });
}

export function defectFrequencies(
  machine: MachineSpec,
  shaftRpm: number,
): Record<string, number> {
  const shaftHz = shaftRpm / 60;
  return {
    shaft: shaftHz,
    bpfo: machine.orders.bpfo * shaftHz,
    bpfi: machine.orders.bpfi * shaftHz,
    bsf: machine.orders.bsf * shaftHz,
    ftf: machine.orders.ftf * shaftHz,
  };
}

export interface Extraction {
  values: Float64Array;
  spectrum: Spectrum;
  envelope: Spectrum;
  velocityRmsMmS: number;
}

/** Condense one acceleration window into the diagnostic feature vector. */
export function extract(
  signal: Float64Array,
  machine: MachineSpec = DEFAULT_MACHINE,
  shaftRpm?: number,
): Extraction {
  const rpm = shaftRpm ?? machine.shaftRpm;
  const spectrum = amplitudeSpectrum(signal, machine.sampleRateHz);
  const envelope = envelopeSpectrum(signal, machine.sampleRateHz, ENVELOPE_BAND);
  // Slip and speed drift smear the defect lines; allow two FFT bins either way.
  const tolerance = (2 * machine.sampleRateHz) / signal.length;

  const values = Float64Array.from([
    ...timeFeatures(signal),
    ...spectralFeatures(spectrum),
    ...envelopeFeatures(envelope, defectFrequencies(machine, rpm), tolerance),
  ]);

  return {
    values,
    spectrum,
    envelope,
    velocityRmsMmS: velocityRmsMmS(signal, machine.sampleRateHz),
  };
}

export function describe(values: Float64Array): Record<string, number> {
  const out: Record<string, number> = {};
  FEATURE_NAMES.forEach((name, i) => {
    out[name] = values[i];
  });
  return out;
}
