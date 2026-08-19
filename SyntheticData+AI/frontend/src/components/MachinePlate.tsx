import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { Frame, MachineInfo } from "@/lib/types";
import { cn, num } from "@/lib/utils";

/**
 * The machine's nameplate.
 *
 * Bearing defect frequencies are fixed multiples of shaft speed set by
 * geometry alone, so they move with the speed slider. Showing them here makes
 * the envelope-spectrum markers legible instead of magic.
 */
export function MachinePlate({
  machine,
  frame,
  modelMeta,
}: {
  machine: MachineInfo | null;
  frame: Frame | null;
  modelMeta: Record<string, unknown> | null;
}) {
  const rpm = frame?.fault.shaft_rpm ?? machine?.shaft_rpm ?? 1797;
  const shaftHz = rpm / 60;
  const orders = machine?.defect_orders ?? {
    bpfo: 3.5848,
    bpfi: 5.4152,
    bsf: 2.3567,
    ftf: 0.3983,
  };
  const architecture = (modelMeta?.architecture as number[] | undefined) ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Machine &amp; model</CardTitle>
        <CardDescription>
          SKF 6205-2RS bearing on a 2 hp motor, sampled at{" "}
          {((machine?.sample_rate_hz ?? 12000) / 1000).toFixed(0)} kHz — the same
          setup as the CWRU bearing dataset.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <p className="text-muted-foreground mb-2 text-xs tracking-wide uppercase">
            Defect frequencies at {Math.round(rpm)} rpm
          </p>
          {/* Two columns, not four: the sidebar is ~340 px wide, and a
              four-column grid truncates every value it holds. */}
          <dl className="grid grid-cols-2 gap-2">
            <Cell label="BPFO" value={`${num(orders.bpfo * shaftHz, 1)} Hz`} note={`${num(orders.bpfo, 2)}×`} />
            <Cell label="BPFI" value={`${num(orders.bpfi * shaftHz, 1)} Hz`} note={`${num(orders.bpfi, 2)}×`} />
            <Cell label="BSF" value={`${num(orders.bsf * shaftHz, 1)} Hz`} note={`${num(orders.bsf, 2)}×`} />
            <Cell label="Cage" value={`${num(orders.ftf * shaftHz, 1)} Hz`} note={`${num(orders.ftf, 2)}×`} />
          </dl>
        </div>

        <div>
          <p className="text-muted-foreground mb-2 text-xs tracking-wide uppercase">
            Detector
          </p>
          {/* Two columns, not four: the sidebar is ~340 px wide, and a
              four-column grid truncates every value it holds. */}
          <dl className="grid grid-cols-2 gap-2">
            <Cell
              label="Architecture"
              value={architecture.length ? architecture.join("–") : "26–16–8–6–8–16–26"}
              note="dense autoencoder"
              wide
            />
            <Cell label="Trained on" value="healthy only" note="one-class" />
            <Cell
              label="Window"
              value={`${num((machine?.window_seconds ?? 0.1707) * 1000, 0)} ms`}
              note={`${machine?.window_size ?? 2048} samples`}
            />
            <Cell
              label="Resolution"
              value={`${num(machine?.freq_resolution_hz ?? 5.86, 2)} Hz`}
              note="per FFT bin"
            />
          </dl>
        </div>
      </CardContent>
    </Card>
  );
}

function Cell({
  label,
  value,
  note,
  wide,
}: {
  label: string;
  value: string;
  note: string;
  wide?: boolean;
}) {
  return (
    <div className={cn("bg-secondary/60 rounded-lg px-3 py-2", wide && "col-span-2")}>
      <dt className="text-muted-foreground text-[0.7rem] tracking-wide uppercase">{label}</dt>
      <dd className="tabular text-sm font-semibold">{value}</dd>
      <dd className="text-muted-foreground text-[0.7rem]">{note}</dd>
    </div>
  );
}
