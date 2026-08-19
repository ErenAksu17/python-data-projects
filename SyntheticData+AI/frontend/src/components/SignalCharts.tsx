import { useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { Frame, MachineInfo } from "@/lib/types";
import type { TrendPoint } from "@/lib/useMonitor";
import { compact, num } from "@/lib/utils";

const AXIS = {
  stroke: "var(--muted-foreground)",
  fontSize: 11,
  tickLine: false,
  axisLine: false,
} as const;

function ChartFrame({ children }: { children: React.ReactElement }) {
  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        {children}
      </ResponsiveContainer>
    </div>
  );
}

const tooltipStyle = {
  background: "var(--popover)",
  border: "1px solid var(--border)",
  borderRadius: "0.6rem",
  fontSize: "0.8rem",
  color: "var(--popover-foreground)",
};

/** Raw acceleration: this is where bearing impacts are visible as spikes. */
export function WaveformChart({ frame }: { frame: Frame | null }) {
  const data = useMemo(
    () => (frame?.waveform ?? []).map((g, i) => ({ i, g })),
    [frame],
  );
  const peak = useMemo(
    () => Math.max(0.15, ...data.map((d) => Math.abs(d.g))) * 1.15,
    [data],
  );

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-3">
        <div>
          <CardTitle>Acceleration waveform</CardTitle>
          <CardDescription>
            32 ms of raw sensor data. Impacts appear as ringing spikes.
          </CardDescription>
        </div>
        <Badge variant="secondary" className="tabular shrink-0">
          {num(frame?.features.rms, 3)} g RMS
        </Badge>
      </CardHeader>
      <CardContent>
        <ChartFrame>
          <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            <XAxis dataKey="i" {...AXIS} tick={false} label={undefined} />
            <YAxis
              {...AXIS}
              domain={[-peak, peak]}
              tickFormatter={(value: number) => value.toFixed(1)}
              width={44}
            />
            <Line
              type="linear"
              dataKey="g"
              stroke="var(--chart-1)"
              strokeWidth={1.2}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ChartFrame>
      </CardContent>
    </Card>
  );
}

/**
 * Reconstruction error over time against the alarm threshold.
 *
 * Log scale, because a severe defect scores three orders of magnitude above a
 * healthy window: on a linear axis the entire healthy band and the threshold
 * itself collapse onto the zero line the moment a fault appears.
 */
export function ScoreTrend({ trend }: { trend: TrendPoint[] }) {
  const threshold = trend.at(-1)?.threshold ?? 1;
  const domain = useMemo<[number, number]>(() => {
    const scores = trend.map((p) => p.score).filter((s) => s > 0);
    const low = Math.min(threshold * 0.25, ...scores);
    const high = Math.max(threshold * 2, ...scores);
    return [low * 0.7, high * 1.4];
  }, [trend, threshold]);
  const span = (trend.at(-1)?.t ?? 0) - (trend[0]?.t ?? 0);

  return (
    <Card>
      <CardHeader className="flex-row items-start justify-between gap-3">
        <div>
          <CardTitle>Reconstruction error</CardTitle>
          <CardDescription>
            How far each window sits from what the autoencoder considers normal.
          </CardDescription>
        </div>
        <Badge variant="outline" className="tabular shrink-0">
          alarm {compact(threshold)}
        </Badge>
      </CardHeader>
      <CardContent>
        <ChartFrame>
          <LineChart data={trend} margin={{ top: 4, right: 8, bottom: 0, left: -6 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="t"
              {...AXIS}
              // Whole seconds repeat when only a few have elapsed; add a
              // decimal until the window is long enough to need none.
              tickFormatter={(value: number) => `${value.toFixed(span < 20 ? 1 : 0)}s`}
              minTickGap={34}
            />
            <YAxis
              {...AXIS}
              scale="log"
              domain={domain}
              allowDataOverflow
              tickFormatter={(value: number) => compact(value)}
              width={56}
            />
            <Tooltip
              contentStyle={tooltipStyle}
              labelFormatter={(value) => `t = ${Number(value).toFixed(1)} s`}
              formatter={(value: unknown, name: unknown) => [compact(Number(value)), String(name)]}
            />
            <ReferenceLine
              y={threshold}
              stroke="var(--chart-2)"
              strokeDasharray="5 4"
              strokeWidth={1.5}
              label={{
                value: "alarm",
                position: "insideTopLeft",
                fill: "var(--chart-2)",
                fontSize: 10,
              }}
            />
            <Line
              type="monotone"
              dataKey="score"
              name="error"
              stroke="var(--chart-1)"
              strokeWidth={1.8}
              dot={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="anomaly"
              name="alarm"
              stroke="var(--chart-4)"
              strokeWidth={0}
              dot={{ r: 2.5, fill: "var(--chart-4)" }}
              isAnimationActive={false}
              connectNulls={false}
            />
          </LineChart>
        </ChartFrame>
      </CardContent>
    </Card>
  );
}

/** Ordinary FFT: shows the resonance, but buries the defect line in it. */
export function SpectrumChart({ frame }: { frame: Frame | null }) {
  const data = useMemo(
    () => (frame?.spectrum.x ?? []).map((hz, i) => ({ hz, amp: frame!.spectrum.y[i] })),
    [frame],
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>Vibration spectrum</CardTitle>
        <CardDescription>
          Acceleration by frequency. Bearing impacts excite the structural
          resonance near 3 kHz rather than showing up at their own frequency.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ChartFrame>
          <AreaChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -12 }}>
            <defs>
              <linearGradient id="specFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--chart-6)" stopOpacity={0.5} />
                <stop offset="100%" stopColor="var(--chart-6)" stopOpacity={0.03} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="hz"
              {...AXIS}
              type="number"
              domain={[0, 6000]}
              tickFormatter={(value: number) => `${(value / 1000).toFixed(0)}k`}
            />
            <YAxis {...AXIS} width={48} tickFormatter={(value: number) => value.toFixed(2)} />
            <Tooltip
              contentStyle={tooltipStyle}
              labelFormatter={(value) => `${Number(value).toFixed(0)} Hz`}
              formatter={(value: unknown) => [`${Number(value).toFixed(4)} g`, "amplitude"]}
            />
            <Area
              type="monotone"
              dataKey="amp"
              stroke="var(--chart-6)"
              strokeWidth={1.4}
              fill="url(#specFill)"
              isAnimationActive={false}
            />
          </AreaChart>
        </ChartFrame>
      </CardContent>
    </Card>
  );
}

/** Envelope spectrum: the view that actually names the faulty component. */
export function EnvelopeChart({
  frame,
  machine,
}: {
  frame: Frame | null;
  machine: MachineInfo | null;
}) {
  const data = useMemo(
    () => (frame?.envelope.x ?? []).map((hz, i) => ({ hz, amp: frame!.envelope.y[i] })),
    [frame],
  );

  // Defect frequencies scale with shaft speed, so recompute them per frame
  // rather than trusting the nominal figures from the API.
  const markers = useMemo(() => {
    const orders = machine?.defect_orders;
    const rpm = frame?.fault.shaft_rpm ?? machine?.shaft_rpm ?? 1797;
    if (!orders) return [];
    const shaftHz = rpm / 60;
    return [
      { key: "BPFO", hz: orders.bpfo * shaftHz, color: "var(--chart-4)" },
      { key: "BPFI", hz: orders.bpfi * shaftHz, color: "var(--chart-3)" },
      { key: "BSF", hz: orders.bsf * shaftHz, color: "var(--chart-5)" },
      { key: "1×", hz: shaftHz, color: "var(--chart-2)" },
    ].filter((marker) => marker.hz <= 500);
  }, [machine, frame]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Envelope spectrum</CardTitle>
        <CardDescription>
          Demodulated around the resonance. A defect puts a line exactly on its
          own geometric frequency — which is what identifies the component.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ChartFrame>
          <AreaChart data={data} margin={{ top: 14, right: 8, bottom: 0, left: -12 }}>
            <defs>
              <linearGradient id="envFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--chart-3)" stopOpacity={0.5} />
                <stop offset="100%" stopColor="var(--chart-3)" stopOpacity={0.03} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="hz"
              {...AXIS}
              type="number"
              domain={[0, 500]}
              tickFormatter={(value: number) => `${value.toFixed(0)}`}
            />
            <YAxis {...AXIS} width={48} tickFormatter={(value: number) => value.toFixed(3)} />
            <Tooltip
              contentStyle={tooltipStyle}
              labelFormatter={(value) => `${Number(value).toFixed(1)} Hz`}
              formatter={(value: unknown) => [Number(value).toFixed(5), "envelope"]}
            />
            {markers.map((marker) => (
              <ReferenceLine
                key={marker.key}
                x={marker.hz}
                stroke={marker.color}
                strokeDasharray="4 4"
                label={{
                  value: marker.key,
                  position: "top",
                  fill: marker.color,
                  fontSize: 10,
                }}
              />
            ))}
            <Area
              type="monotone"
              dataKey="amp"
              stroke="var(--chart-3)"
              strokeWidth={1.4}
              fill="url(#envFill)"
              isAnimationActive={false}
            />
          </AreaChart>
        </ChartFrame>
      </CardContent>
    </Card>
  );
}
