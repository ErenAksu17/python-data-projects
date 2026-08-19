/**
 * One hook, two sources of frames.
 *
 * `live` streams analysed windows from the FastAPI WebSocket; `offline` runs
 * the simulator, feature pipeline and autoencoder in the browser. Both emit
 * the same `Frame`, so everything downstream is written once. The hook picks
 * `live` when an API answers and `offline` otherwise, and the user can switch
 * by hand.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  loadModelBundle,
  loadStaticReport,
  probeApi,
  streamUrl,
  fetchAblation,
  fetchBenchmark,
} from "./api";
import { OfflineEngine } from "./offline/engine";
import type {
  AblationReport,
  BenchmarkReport,
  ConnectionState,
  EngineMode,
  FaultMode,
  Frame,
} from "./types";
import { pushBounded } from "./utils";

/** Frames kept for the trend charts (~2 minutes at the default rate). */
const HISTORY_LENGTH = 240;
const EVENT_LOG_LENGTH = 40;

export interface Controls {
  mode: FaultMode;
  severity: number;
  shaftRpm: number;
  load: number;
  intervalMs: number;
  paused: boolean;
}

export const DEFAULT_CONTROLS: Controls = {
  mode: "healthy",
  severity: 0,
  shaftRpm: 1797,
  load: 1,
  intervalMs: 700,
  paused: false,
};

const FAULT_MODES = new Set<string>([
  "healthy",
  "outer_race",
  "inner_race",
  "ball",
  "imbalance",
  "looseness",
]);

function clamp(value: number, min: number, max: number): number {
  return Number.isFinite(value) ? Math.min(max, Math.max(min, value)) : min;
}

/**
 * Read the starting machine state from the query string.
 *
 * Makes a dashboard state shareable as a link — `?mode=inner_race&severity=0.8`
 * opens on that fault — and is what lets a headless browser capture a
 * meaningful screenshot instead of an idle machine. Every value is clamped to
 * the same range the API enforces, so a hand-edited URL cannot push the
 * simulator anywhere the server would refuse to go.
 */
function controlsFromUrl(): Controls {
  if (typeof window === "undefined") return DEFAULT_CONTROLS;
  const params = new URLSearchParams(window.location.search);
  const mode = params.get("mode");
  const severity = params.get("severity");
  const rpm = params.get("rpm");
  const load = params.get("load");
  const interval = params.get("interval");

  return {
    ...DEFAULT_CONTROLS,
    mode: mode && FAULT_MODES.has(mode) ? (mode as FaultMode) : DEFAULT_CONTROLS.mode,
    severity: severity ? clamp(Number(severity), 0, 1) : DEFAULT_CONTROLS.severity,
    shaftRpm: rpm ? clamp(Number(rpm), 900, 3000) : DEFAULT_CONTROLS.shaftRpm,
    load: load ? clamp(Number(load), 0.5, 1.6) : DEFAULT_CONTROLS.load,
    intervalMs: interval
      ? clamp(Number(interval), 200, 2000)
      : DEFAULT_CONTROLS.intervalMs,
  };
}

function engineFromUrl(): EngineMode | "auto" {
  if (typeof window === "undefined") return "auto";
  const engine = new URLSearchParams(window.location.search).get("engine");
  return engine === "live" || engine === "offline" ? engine : "auto";
}

export interface TrendPoint {
  seq: number;
  t: number;
  score: number;
  threshold: number;
  health: number;
  velocity: number;
  rms: number;
  anomaly: number;
}

export interface MachineEvent {
  seq: number;
  t: number;
  status: Frame["verdict"]["status"];
  diagnosis: string;
  label: string;
  confidence: number;
  evidence: string[];
  score: number;
}

export interface Monitor {
  mode: EngineMode;
  requestedMode: EngineMode | "auto";
  setRequestedMode: (mode: EngineMode | "auto") => void;
  connection: ConnectionState;
  frame: Frame | null;
  trend: TrendPoint[];
  events: MachineEvent[];
  controls: Controls;
  setControls: (patch: Partial<Controls>) => void;
  benchmark: BenchmarkReport | null;
  ablation: AblationReport | null;
  modelMeta: Record<string, unknown> | null;
  notice: string | null;
  clearEvents: () => void;
}

export function useMonitor(): Monitor {
  const [requestedMode, setRequestedMode] = useState<EngineMode | "auto">(engineFromUrl);
  const [mode, setMode] = useState<EngineMode>("offline");
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const [frame, setFrame] = useState<Frame | null>(null);
  const [trend, setTrend] = useState<TrendPoint[]>([]);
  const [events, setEvents] = useState<MachineEvent[]>([]);
  const [controls, setControlsState] = useState<Controls>(controlsFromUrl);
  const [benchmark, setBenchmark] = useState<BenchmarkReport | null>(null);
  const [ablation, setAblation] = useState<AblationReport | null>(null);
  const [modelMeta, setModelMeta] = useState<Record<string, unknown> | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const controlsRef = useRef(controls);
  controlsRef.current = controls;
  const lastStatus = useRef<string>("normal");

  // Each engine keeps its own machine clock, so a trend carried across a
  // switch would plot two unrelated timelines on one axis.
  useEffect(() => {
    setTrend([]);
    lastStatus.current = "normal";
  }, [mode]);

  const ingest = useCallback((next: Frame) => {
    setFrame(next);
    setTrend((previous) =>
      pushBounded(
        previous,
        {
          seq: next.seq,
          t: next.t,
          score: next.verdict.score,
          threshold: next.verdict.threshold,
          health: next.verdict.health_index,
          velocity: next.verdict.velocity_rms_mm_s,
          rms: next.features.rms ?? 0,
          anomaly: next.verdict.is_anomaly ? next.verdict.score : Number.NaN,
        },
        HISTORY_LENGTH,
      ),
    );

    // Log transitions, not every frame -- an alarm that stays on is one event.
    // "watch" is deliberately excluded: it is a nudge on the gauge, not an
    // event worth a line in a log an engineer has to read.
    if (next.verdict.status !== lastStatus.current) {
      lastStatus.current = next.verdict.status;
      if (next.verdict.status === "warning" || next.verdict.status === "critical") {
        setEvents((previous) =>
          pushBounded(
            previous,
            {
              seq: next.seq,
              t: next.t,
              status: next.verdict.status,
              diagnosis: next.verdict.diagnosis,
              label: next.verdict.diagnosis_label,
              confidence: next.verdict.confidence,
              evidence: next.verdict.evidence,
              score: next.verdict.score,
            },
            EVENT_LOG_LENGTH,
          ),
        );
      }
    }
  }, []);

  // --- decide which engine to run ---------------------------------------- //
  useEffect(() => {
    let cancelled = false;
    if (requestedMode !== "auto") {
      setMode(requestedMode);
      return;
    }
    setConnection("connecting");
    probeApi().then((available) => {
      if (cancelled) return;
      setMode(available ? "live" : "offline");
      setNotice(
        available
          ? null
          : "No API reachable — running the model in your browser. Every number below is computed locally.",
      );
    });
    return () => {
      cancelled = true;
    };
  }, [requestedMode]);

  // --- reports ------------------------------------------------------------ //
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      const [live, staticBenchmark] = await Promise.allSettled([
        fetchBenchmark(),
        loadStaticReport<BenchmarkReport>("benchmark.json"),
      ]);
      if (cancelled) return;
      if (live.status === "fulfilled") setBenchmark(live.value);
      else if (staticBenchmark.status === "fulfilled" && staticBenchmark.value) {
        setBenchmark(staticBenchmark.value);
      }

      const [liveAblation, staticAblation] = await Promise.allSettled([
        fetchAblation(),
        loadStaticReport<AblationReport>("ablation.json"),
      ]);
      if (cancelled) return;
      if (liveAblation.status === "fulfilled") setAblation(liveAblation.value);
      else if (staticAblation.status === "fulfilled" && staticAblation.value) {
        setAblation(staticAblation.value);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  // --- offline engine ----------------------------------------------------- //
  useEffect(() => {
    if (mode !== "offline") return;
    let engine: OfflineEngine | null = null;
    let timer: number | undefined;
    let cancelled = false;

    const start = async () => {
      setConnection("connecting");
      try {
        const bundle = await loadModelBundle();
        if (cancelled) return;
        engine = new OfflineEngine(bundle);
        setModelMeta(bundle.metadata);
        setConnection("open");
      } catch (error) {
        if (!cancelled) {
          setConnection("error");
          setNotice(`Could not load the model bundle: ${(error as Error).message}`);
        }
        return;
      }

      const tick = () => {
        if (cancelled || !engine) return;
        const current = controlsRef.current;
        if (!current.paused) {
          engine.setFault({
            mode: current.mode,
            severity: current.severity,
            shaftRpm: current.shaftRpm,
            load: current.load,
          });
          ingest(engine.next(current.intervalMs / 1000));
        }
        timer = window.setTimeout(tick, current.intervalMs);
      };
      tick();
    };

    void start();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [mode, ingest]);

  // --- live WebSocket ----------------------------------------------------- //
  // Held in a ref so control changes can be pushed without tearing the socket
  // down and reconnecting on every slider move.
  const liveSocket = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (mode !== "live") return;
    let socket: WebSocket | null = null;
    let cancelled = false;

    setConnection("connecting");
    try {
      socket = new WebSocket(streamUrl());
      liveSocket.current = socket;
    } catch {
      setConnection("error");
      return;
    }

    socket.onopen = () => {
      if (cancelled) return;
      setConnection("open");
      const current = controlsRef.current;
      socket?.send(
        JSON.stringify({
          mode: current.mode,
          severity: current.severity,
          shaft_rpm: current.shaftRpm,
          load: current.load,
          interval_ms: current.intervalMs,
          paused: current.paused,
        }),
      );
    };
    socket.onmessage = (event) => {
      // A socket torn down by StrictMode's double-mount can still deliver a
      // frame before `close()` lands. Without this guard two sessions -- each
      // with its own machine clock -- interleave into one trend array and the
      // time axis stops being monotonic.
      if (cancelled) return;
      const payload = JSON.parse(event.data as string);
      if (payload.type === "frame") ingest(payload as Frame);
      else if (payload.type === "error") setNotice("The server rejected a control change.");
    };
    socket.onerror = () => {
      if (!cancelled) setConnection("error");
    };
    socket.onclose = () => {
      if (!cancelled) setConnection("closed");
    };

    return () => {
      cancelled = true;
      liveSocket.current = null;
      socket?.close();
    };
  }, [mode, ingest]);

  const setControls = useCallback((patch: Partial<Controls>) => {
    setControlsState((previous) => {
      const next = { ...previous, ...patch };
      controlsRef.current = next;
      return next;
    });
  }, []);

  // Live mode pushes the change to the server; offline reads it off the ref.
  useEffect(() => {
    if (mode !== "live") return;
    const socket = liveSocket.current;
    if (socket?.readyState === WebSocket.OPEN) {
      socket.send(
        JSON.stringify({
          mode: controls.mode,
          severity: controls.severity,
          shaft_rpm: controls.shaftRpm,
          load: controls.load,
          interval_ms: controls.intervalMs,
          paused: controls.paused,
        }),
      );
    }
  }, [mode, controls, connection]);

  const clearEvents = useCallback(() => setEvents([]), []);

  return useMemo(
    () => ({
      mode,
      requestedMode,
      setRequestedMode,
      connection,
      frame,
      trend,
      events,
      controls,
      setControls,
      benchmark,
      ablation,
      modelMeta,
      notice,
      clearEvents,
    }),
    [
      mode,
      requestedMode,
      connection,
      frame,
      trend,
      events,
      controls,
      setControls,
      benchmark,
      ablation,
      modelMeta,
      notice,
      clearEvents,
    ],
  );
}
