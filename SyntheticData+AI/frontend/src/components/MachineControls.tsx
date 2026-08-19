import { Pause, Play, RotateCcw, Wrench } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import type { FaultMode } from "@/lib/types";
import { DEFAULT_CONTROLS, type Controls } from "@/lib/useMonitor";
import { faultLabel, num } from "@/lib/utils";

const FAULT_MODES: FaultMode[] = [
  "healthy",
  "outer_race",
  "inner_race",
  "ball",
  "imbalance",
  "looseness",
];

const MODE_HINT: Record<FaultMode, string> = {
  healthy: "Nominal machine — only the residual 1x imbalance every rotor has.",
  outer_race: "Steady impacts at BPFO; the stationary race sits in the load zone.",
  inner_race: "Impacts at BPFI, amplitude-modulated once per revolution.",
  ball: "Impacts at ball spin frequency, modulated at cage speed.",
  imbalance: "Pure 1x growth — loud, but not impulsive.",
  looseness: "Harmonic family plus a 0.5x subharmonic and a raised noise floor.",
};

interface Props {
  controls: Controls;
  onChange: (patch: Partial<Controls>) => void;
}

/** Inject a fault and watch the model react — the point of the whole demo. */
export function MachineControls({ controls, onChange }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Wrench className="text-primary size-4" />
          Fault injection
        </CardTitle>
        <CardDescription>
          Drive the simulated machine. The model was never shown any of these
          faults — it only ever learned what healthy looks like.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-5">
        <div className="space-y-2">
          <Label>Fault mode</Label>
          <Select
            value={controls.mode}
            onValueChange={(value) => onChange({ mode: value as FaultMode })}
          >
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {FAULT_MODES.map((mode) => (
                <SelectItem key={mode} value={mode}>
                  {faultLabel(mode)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-muted-foreground text-xs">{MODE_HINT[controls.mode]}</p>
        </div>

        <SliderRow
          label="Severity"
          value={controls.severity}
          display={controls.severity === 0 ? "none" : `${Math.round(controls.severity * 100)}%`}
          min={0}
          max={1}
          step={0.01}
          disabled={controls.mode === "healthy"}
          onChange={(severity) => onChange({ severity })}
        />

        <SliderRow
          label="Shaft speed"
          value={controls.shaftRpm}
          display={`${Math.round(controls.shaftRpm)} rpm`}
          min={900}
          max={3000}
          step={1}
          onChange={(shaftRpm) => onChange({ shaftRpm })}
        />

        <SliderRow
          label="Load"
          value={controls.load}
          display={`${num(controls.load, 2)}×`}
          min={0.5}
          max={1.6}
          step={0.05}
          onChange={(load) => onChange({ load })}
        />

        <SliderRow
          label="Sample interval"
          value={controls.intervalMs}
          display={`${controls.intervalMs} ms`}
          min={200}
          max={2000}
          step={50}
          onChange={(intervalMs) => onChange({ intervalMs })}
        />

        <div className="flex gap-2 pt-1">
          <Button
            variant={controls.paused ? "default" : "outline"}
            className="flex-1"
            onClick={() => onChange({ paused: !controls.paused })}
          >
            {controls.paused ? <Play /> : <Pause />}
            {controls.paused ? "Resume" : "Pause"}
          </Button>
          <Button
            variant="ghost"
            onClick={() => onChange(DEFAULT_CONTROLS)}
            aria-label="Reset the machine to nominal"
          >
            <RotateCcw />
            Reset
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return <span className="text-sm font-medium">{children}</span>;
}

interface SliderRowProps {
  label: string;
  value: number;
  display: string;
  min: number;
  max: number;
  step: number;
  disabled?: boolean;
  onChange: (value: number) => void;
}

function SliderRow({
  label,
  value,
  display,
  min,
  max,
  step,
  disabled,
  onChange,
}: SliderRowProps) {
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between">
        <Label>{label}</Label>
        <span className="text-muted-foreground tabular text-sm">{display}</span>
      </div>
      <Slider
        value={[value]}
        min={min}
        max={max}
        step={step}
        disabled={disabled}
        label={label}
        onValueChange={([next]) => onChange(next)}
      />
    </div>
  );
}
