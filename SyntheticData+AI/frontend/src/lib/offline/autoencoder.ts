/**
 * The autoencoder, evaluated in the browser from the exported JSON bundle.
 *
 * Same weights, same arithmetic, same threshold as the server. This is what
 * lets the published site work with no backend running at all -- and it is
 * only possible because training exports plain JSON instead of a pickle.
 */

export interface LayerJson {
  weight: number[][];
  bias: number[];
  activation: "relu" | "linear";
}

export interface BundleJson {
  schema_version: number;
  feature_names: string[];
  scaler: { mean: number[]; scale: number[] };
  layers: LayerJson[];
  residual_scale: number[] | null;
  threshold: number;
  metadata: Record<string, unknown>;
}

export const SUPPORTED_SCHEMA = 1;

interface Layer {
  weight: Float64Array[];
  bias: Float64Array;
  relu: boolean;
}

export class Autoencoder {
  private readonly layers: Layer[];
  readonly featureNames: string[];
  readonly mean: Float64Array;
  readonly scale: Float64Array;
  readonly residualScale: Float64Array | null;
  readonly threshold: number;
  readonly metadata: Record<string, unknown>;

  constructor(bundle: BundleJson) {
    if (bundle.schema_version !== SUPPORTED_SCHEMA) {
      throw new Error(
        `model bundle schema ${bundle.schema_version} is not supported (this build reads ${SUPPORTED_SCHEMA})`,
      );
    }
    this.featureNames = bundle.feature_names;
    this.mean = Float64Array.from(bundle.scaler.mean);
    this.scale = Float64Array.from(bundle.scaler.scale);
    this.residualScale = bundle.residual_scale
      ? Float64Array.from(bundle.residual_scale)
      : null;
    this.threshold = bundle.threshold;
    this.metadata = bundle.metadata ?? {};
    this.layers = bundle.layers.map((layer, index) => ({
      weight: layer.weight.map((row) => Float64Array.from(row)),
      bias: Float64Array.from(layer.bias),
      relu: layer.activation === "relu" && index < bundle.layers.length - 1,
    }));
  }

  get architecture(): number[] {
    return [this.featureNames.length, ...this.layers.map((l) => l.bias.length)];
  }

  get latentDim(): number {
    return Math.min(...this.layers.map((l) => l.bias.length));
  }

  get parameterCount(): number {
    return this.layers.reduce(
      (total, l) => total + l.bias.length * l.weight[0].length + l.bias.length,
      0,
    );
  }

  standardise(features: Float64Array): Float64Array {
    const out = new Float64Array(features.length);
    for (let i = 0; i < features.length; i++) {
      out[i] = (features[i] - this.mean[i]) / this.scale[i];
    }
    return out;
  }

  private forward(input: Float64Array): Float64Array {
    let current = input;
    for (const layer of this.layers) {
      const next = new Float64Array(layer.bias.length);
      for (let o = 0; o < layer.bias.length; o++) {
        const row = layer.weight[o];
        let sum = layer.bias[o];
        for (let i = 0; i < row.length; i++) sum += row[i] * current[i];
        next[o] = layer.relu ? Math.max(sum, 0) : sum;
      }
      current = next;
    }
    return current;
  }

  /** Per-feature squared reconstruction error, residual-normalised. */
  errors(features: Float64Array): Float64Array {
    const scaled = this.standardise(features);
    const reconstructed = this.forward(scaled);
    const out = new Float64Array(scaled.length);
    for (let i = 0; i < scaled.length; i++) {
      let residual = reconstructed[i] - scaled[i];
      if (this.residualScale) residual /= this.residualScale[i];
      out[i] = residual * residual;
    }
    return out;
  }

  score(features: Float64Array): number {
    const errors = this.errors(features);
    let total = 0;
    for (let i = 0; i < errors.length; i++) total += errors[i];
    return total / errors.length;
  }

  /** 0-100, hitting exactly 50 at the alarm threshold. Mirrors `health_index`. */
  healthIndex(score: number): number {
    if (this.threshold <= 0) return 0;
    const ratio = Math.max(score, 1e-12) / this.threshold;
    return Math.min(100, Math.max(0, 100 * 2 ** -(ratio ** 1.6)));
  }

  /** Which features the model failed hardest to reconstruct, and by how much. */
  topContributors(features: Float64Array, k = 4): Array<{ feature: string; share: number }> {
    const errors = this.errors(features);
    let total = 0;
    for (let i = 0; i < errors.length; i++) total += errors[i];
    total = total || 1;
    return Array.from(errors)
      .map((value, i) => ({ feature: this.featureNames[i], share: value / total }))
      .sort((a, b) => b.share - a.share)
      .slice(0, k);
  }

  /** Standardised deviation per feature -- "how many healthy sigmas out". */
  zScores(features: Float64Array): Record<string, number> {
    const out: Record<string, number> = {};
    this.featureNames.forEach((name, i) => {
      out[name] = (features[i] - this.mean[i]) / this.scale[i];
    });
    return out;
  }
}
