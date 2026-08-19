/**
 * The wire contract.
 *
 * Both sources of frames -- the FastAPI WebSocket and the in-browser engine --
 * emit exactly this shape, so every component below renders one type and never
 * needs to know which mode is active.
 */

export type FaultMode =
  | "healthy"
  | "outer_race"
  | "inner_race"
  | "ball"
  | "imbalance"
  | "looseness";

export type Status = "normal" | "watch" | "warning" | "critical";

export type IsoZone = "A" | "B" | "C" | "D";

export interface Curve {
  x: number[];
  y: number[];
}

export interface Contributor {
  feature: string;
  share: number;
}

export interface Verdict {
  score: number;
  threshold: number;
  is_anomaly: boolean;
  health_index: number;
  status: Status;
  diagnosis: FaultMode | "unknown";
  diagnosis_label: string;
  confidence: number;
  evidence: string[];
  contributors: Contributor[];
  velocity_rms_mm_s: number;
  iso_zone: IsoZone;
}

export interface FaultState {
  mode: FaultMode;
  severity: number;
  shaft_rpm: number;
  load: number;
}

export interface Frame {
  seq: number;
  t: number;
  fault: FaultState;
  verdict: Verdict;
  waveform: number[];
  spectrum: Curve;
  envelope: Curve;
  features: Record<string, number>;
}

export interface MachineInfo {
  sample_rate_hz: number;
  window_size: number;
  window_seconds: number;
  shaft_rpm: number;
  shaft_hz: number;
  resonance_hz: number;
  freq_resolution_hz: number;
  fault_modes: string[];
  defect_orders: Record<string, number>;
  defect_frequencies_hz: Record<string, number>;
  envelope_band_hz: number[];
}

export interface BenchmarkMethod {
  name: string;
  family: string;
  roc_auc: number;
  pr_auc: number;
  precision: number;
  recall: number;
  f1: number;
  false_alarm_rate: number;
  recall_incipient: number;
  recall_severe: number;
  recall_by_mode: Record<string, number>;
  inference_us_per_window: number;
  threshold_note: string;
}

export interface BenchmarkReport {
  generated_utc: string;
  operating_point: { policy: string; incipient_severity_max: number };
  dataset: Record<string, number>;
  model: { architecture: number[]; latent_dim: number; parameters: number };
  methods: BenchmarkMethod[];
}

export interface AblationStage {
  name: string;
  description: string;
  roc_auc: number;
  pr_auc: number;
  recall: number;
  recall_incipient: number;
  false_alarm_rate: number;
}

export interface AblationReport {
  generated_utc: string;
  note: string;
  stages: AblationStage[];
}

/** Which source is currently producing frames. */
export type EngineMode = "live" | "offline";

export type ConnectionState = "connecting" | "open" | "closed" | "error";
