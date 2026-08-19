/**
 * Browser-side vibration simulator, ported from `vfactory/simulator.py`.
 *
 * Not bit-identical to the Python version -- the random streams differ -- but
 * the same signal model, so the statistics the model was trained on hold. The
 * deterministic parts (defect frequencies, ringdown, modulation) match exactly.
 */

import { DEFAULT_MACHINE, type MachineSpec } from "./features.ts";

export const FAULT_MODES = [
  "healthy",
  "outer_race",
  "inner_race",
  "ball",
  "imbalance",
  "looseness",
] as const;

export type FaultMode = (typeof FAULT_MODES)[number];

export interface FaultSpec {
  mode: FaultMode;
  severity: number;
  shaftRpm: number;
  load: number;
}

export const HEALTHY: FaultSpec = {
  mode: "healthy",
  severity: 0,
  shaftRpm: DEFAULT_MACHINE.shaftRpm,
  load: 1,
};

/** Small, fast, seedable PRNG -- Math.random cannot be seeded. */
function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Reproducible jitter keyed by impulse index, so ringdown tails splice cleanly. */
function indexJitter(index: number): number {
  const raw = Math.sin(index * 12.9898) * 43758.5453;
  return raw - Math.floor(raw) - 0.5;
}

export class VibrationSimulator {
  readonly machine: MachineSpec;
  private readonly random: () => number;
  private spare: number | null = null;

  constructor(machine: MachineSpec = DEFAULT_MACHINE, seed = 7) {
    this.machine = machine;
    this.random = mulberry32(seed);
  }

  /** Box-Muller, with the second variate cached rather than discarded. */
  private gaussian(): number {
    if (this.spare !== null) {
      const value = this.spare;
      this.spare = null;
      return value;
    }
    const u = Math.max(this.random(), Number.EPSILON);
    const v = this.random();
    const radius = Math.sqrt(-2 * Math.log(u));
    this.spare = radius * Math.sin(2 * Math.PI * v);
    return radius * Math.cos(2 * Math.PI * v);
  }

  private addImpulseTrain(
    out: Float64Array,
    t0: number,
    defectHz: number,
    amplitude: number,
    modulationHz: number,
    modulationDepth: number,
    slip: number,
  ): void {
    const m = this.machine;
    if (amplitude <= 0 || defectHz <= 0) return;

    const period = 1 / defectHz;
    const tail = 6 / m.resonanceDecay;
    const tEnd = t0 + (out.length - 1) / m.sampleRateHz;
    const first = Math.floor((t0 - tail) / period);
    const last = Math.ceil(tEnd / period);

    for (let k = first; k <= last; k++) {
      const onset = (k + slip * indexJitter(k)) * period;
      let gain = 1;
      if (modulationHz > 0 && modulationDepth > 0) {
        gain = Math.max(0, 1 + modulationDepth * Math.cos(2 * Math.PI * modulationHz * onset));
      }
      gain *= 1 + 0.1 * indexJitter(k + 10007);

      // Only the samples after the impact carry the ringdown, and it is dead
      // after six time constants -- no point evaluating the rest.
      const startSample = Math.max(0, Math.ceil((onset - t0) * m.sampleRateHz));
      const endSample = Math.min(
        out.length,
        Math.ceil((onset + tail - t0) * m.sampleRateHz) + 1,
      );
      for (let i = startSample; i < endSample; i++) {
        const dt = t0 + i / m.sampleRateHz - onset;
        if (dt < 0) continue;
        out[i] +=
          amplitude *
          gain *
          Math.exp(-m.resonanceDecay * dt) *
          Math.sin(2 * Math.PI * m.resonanceHz * dt);
      }
    }
  }

  window(fault: FaultSpec = HEALTHY, t0 = 0): Float64Array {
    const m = this.machine;
    const n = m.windowSize;
    const out = new Float64Array(n);
    const shaftHz = fault.shaftRpm / 60;

    let oneX = m.baselineImbalanceG;
    let twoX = oneX * 0.35;
    let threeX = oneX * 0.18;
    let halfX = 0;

    if (fault.mode === "imbalance") {
      oneX += 0.18 * fault.severity * (shaftHz / (m.shaftRpm / 60)) ** 2;
    } else if (fault.mode === "looseness") {
      twoX += 0.185 * fault.severity;
      threeX += 0.14 * fault.severity;
      halfX = 0.081 * fault.severity;
    }

    for (let i = 0; i < n; i++) {
      const t = t0 + i / m.sampleRateHz;
      const phase = 2 * Math.PI * shaftHz * t;
      out[i] =
        oneX * Math.sin(phase) +
        twoX * Math.sin(2 * phase + 0.6) +
        threeX * Math.sin(3 * phase + 1.9) +
        (halfX ? halfX * Math.sin(0.5 * phase + 0.4) : 0);
    }

    if (
      fault.severity > 0 &&
      (fault.mode === "outer_race" || fault.mode === "inner_race" || fault.mode === "ball")
    ) {
      const amp = 0.9 * fault.severity ** 1.35 * fault.load;
      const bpfo = m.orders.bpfo * shaftHz;
      const bpfi = m.orders.bpfi * shaftHz;
      const bsf = m.orders.bsf * shaftHz;
      const ftf = m.orders.ftf * shaftHz;

      if (fault.mode === "outer_race") {
        this.addImpulseTrain(out, t0, bpfo, amp, 0, 0, 0.012);
      } else if (fault.mode === "inner_race") {
        this.addImpulseTrain(out, t0, bpfi, amp * 0.85, shaftHz, 0.85, 0.015);
      } else {
        this.addImpulseTrain(out, t0, bsf, amp * 0.55, ftf, 0.75, 0.025);
        this.addImpulseTrain(out, t0, 2 * bsf, amp * 0.4, ftf, 0.75, 0.025);
      }
    }

    let noise = m.noiseG * (0.75 + 0.5 * fault.load);
    if (fault.mode === "looseness") noise *= 1 + 0.9 * fault.severity;
    for (let i = 0; i < n; i++) out[i] += noise * this.gaussian();

    return out;
  }
}

/** A live sensor: hands out consecutive windows and advances its own clock. */
export class Stream {
  fault: FaultSpec;
  private elapsed = 0;
  private readonly simulator: VibrationSimulator;

  constructor(
    fault: FaultSpec = HEALTHY,
    machine: MachineSpec = DEFAULT_MACHINE,
    seed = Math.floor(Math.random() * 2 ** 31),
  ) {
    this.fault = fault;
    this.simulator = new VibrationSimulator(machine, seed);
  }

  get elapsedSeconds(): number {
    return this.elapsed;
  }

  /**
   * `advanceSeconds` is the acquisition period. Real condition-monitoring
   * systems take a short snapshot every so often rather than streaming
   * continuously, so passing it makes the reported elapsed time genuine
   * wall-clock time. Omit it for contiguous windows.
   */
  next(advanceSeconds?: number): Float64Array {
    const machine = this.simulator.machine;
    const windowSeconds = machine.windowSize / machine.sampleRateHz;
    const output = this.simulator.window(this.fault, this.elapsed);
    this.elapsed += Math.max(advanceSeconds ?? windowSeconds, windowSeconds);
    return output;
  }
}
