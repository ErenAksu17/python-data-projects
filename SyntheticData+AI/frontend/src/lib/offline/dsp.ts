/**
 * Signal processing primitives, ported from `vfactory/features.py`.
 *
 * These exist so the deployed site works with no backend at all: the browser
 * simulates the sensor, extracts the same 26 features and runs the same
 * autoencoder weights. `scripts/check-parity.mjs` asserts this port agrees
 * with the Python implementation on a fixture, so the two cannot drift.
 */

/** In-place iterative radix-2 Cooley-Tukey FFT. `re`/`im` must be 2^k long. */
export function fft(re: Float64Array, im: Float64Array): void {
  const n = re.length;
  if (n <= 1) return;
  if ((n & (n - 1)) !== 0) throw new Error(`fft requires a power of two, got ${n}`);

  // Bit-reversal permutation.
  for (let i = 1, j = 0; i < n; i++) {
    let bit = n >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) {
      [re[i], re[j]] = [re[j], re[i]];
      [im[i], im[j]] = [im[j], im[i]];
    }
  }

  for (let len = 2; len <= n; len <<= 1) {
    const angle = (-2 * Math.PI) / len;
    const wRe = Math.cos(angle);
    const wIm = Math.sin(angle);
    for (let i = 0; i < n; i += len) {
      let curRe = 1;
      let curIm = 0;
      for (let k = 0; k < len / 2; k++) {
        const uRe = re[i + k];
        const uIm = im[i + k];
        const vRe = re[i + k + len / 2] * curRe - im[i + k + len / 2] * curIm;
        const vIm = re[i + k + len / 2] * curIm + im[i + k + len / 2] * curRe;
        re[i + k] = uRe + vRe;
        im[i + k] = uIm + vIm;
        re[i + k + len / 2] = uRe - vRe;
        im[i + k + len / 2] = uIm - vIm;
        const nextRe = curRe * wRe - curIm * wIm;
        curIm = curRe * wIm + curIm * wRe;
        curRe = nextRe;
      }
    }
  }
}

export function inverseFft(re: Float64Array, im: Float64Array): void {
  const n = re.length;
  for (let i = 0; i < n; i++) im[i] = -im[i];
  fft(re, im);
  for (let i = 0; i < n; i++) {
    re[i] /= n;
    im[i] = -im[i] / n;
  }
}

export function mean(values: ArrayLike<number>): number {
  let total = 0;
  for (let i = 0; i < values.length; i++) total += values[i];
  return total / values.length;
}

export interface Spectrum {
  freqs: Float64Array;
  amp: Float64Array;
}

/** Single-sided amplitude spectrum of a Hann-windowed signal. */
export function amplitudeSpectrum(signal: Float64Array, sampleRate: number): Spectrum {
  const n = signal.length;
  const avg = mean(signal);
  const re = new Float64Array(n);
  const im = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    // np.hanning(n) is the symmetric window: denominator is n - 1.
    const taper = 0.5 - 0.5 * Math.cos((2 * Math.PI * i) / (n - 1));
    re[i] = (signal[i] - avg) * taper;
  }
  fft(re, im);

  const bins = Math.floor(n / 2) + 1;
  const freqs = new Float64Array(bins);
  const amp = new Float64Array(bins);
  for (let k = 0; k < bins; k++) {
    freqs[k] = (k * sampleRate) / n;
    // Coherent gain of a Hann window is 0.5, corrected here so a tone reads
    // at its true amplitude.
    amp[k] = (2 * Math.hypot(re[k], im[k])) / (n * 0.5);
  }
  return { freqs, amp };
}

/** Hilbert envelope of the signal band-passed around the structural resonance. */
export function envelope(
  signal: Float64Array,
  sampleRate: number,
  band: [number, number],
): Float64Array {
  const n = signal.length;
  const avg = mean(signal);
  const re = new Float64Array(n);
  const im = new Float64Array(n);
  for (let i = 0; i < n; i++) re[i] = signal[i] - avg;
  fft(re, im);

  const [lo, hi] = band;
  for (let k = 0; k < n; k++) {
    const freq = Math.abs(k <= n / 2 ? (k * sampleRate) / n : ((k - n) * sampleRate) / n);
    let gain = freq >= lo && freq <= hi ? 1 : 0;
    // Analytic signal: keep DC and Nyquist, double positive frequencies,
    // discard negative ones.
    if (k === 0 || (n % 2 === 0 && k === n / 2)) {
      gain *= 1;
    } else if (k < n / 2) {
      gain *= 2;
    } else {
      gain = 0;
    }
    re[k] *= gain;
    im[k] *= gain;
  }

  inverseFft(re, im);
  const out = new Float64Array(n);
  for (let i = 0; i < n; i++) out[i] = Math.hypot(re[i], im[i]);
  return out;
}

export function envelopeSpectrum(
  signal: Float64Array,
  sampleRate: number,
  band: [number, number],
): Spectrum {
  return amplitudeSpectrum(envelope(signal, sampleRate, band), sampleRate);
}

/** Equivalent noise bandwidth of a Hann window, in bins. */
const HANN_ENBW = 1.5;

/** RMS velocity in mm/s over the ISO 20816 band, from acceleration in g. */
export function velocityRmsMmS(
  signal: Float64Array,
  sampleRate: number,
  band: [number, number] = [10, 1000],
): number {
  const { freqs, amp } = amplitudeSpectrum(signal, sampleRate);
  let power = 0;
  for (let k = 0; k < freqs.length; k++) {
    if (freqs[k] < band[0] || freqs[k] > band[1]) continue;
    const velocityAmp = (amp[k] * 9.80665 * 1000) / (2 * Math.PI * freqs[k]);
    power += (velocityAmp / Math.SQRT2) ** 2;
  }
  return Math.sqrt(power / HANN_ENBW);
}

export function median(values: ArrayLike<number>): number {
  const sorted = Array.from(values).sort((a, b) => a - b);
  const mid = sorted.length >> 1;
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}
