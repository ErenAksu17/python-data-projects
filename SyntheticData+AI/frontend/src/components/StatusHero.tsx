import { Activity, AlertTriangle, CheckCircle2, ShieldAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import type { Frame } from "@/lib/types";
import { ISO_ZONE_NOTE, STATUS_STYLE, cn, compact, num, pct } from "@/lib/utils";

const STATUS_ICON = {
  normal: CheckCircle2,
  watch: Activity,
  warning: AlertTriangle,
  critical: ShieldAlert,
} as const;

/** The one thing an operator looks at first: is this machine all right? */
export function StatusHero({ frame }: { frame: Frame | null }) {
  const verdict = frame?.verdict;
  const status = verdict?.status ?? "normal";
  const style = STATUS_STYLE[status];
  const Icon = STATUS_ICON[status];
  const health = verdict?.health_index ?? 100;

  return (
    <Card className={cn("overflow-hidden ring-1", style.ring)}>
      <CardContent className="grid gap-6 sm:grid-cols-[auto_1fr] sm:items-center">
        <HealthDial health={health} status={status} />

        <div className="min-w-0 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge className={cn("gap-1.5 px-3 py-1 text-sm", style.badge)}>
              <Icon className="size-3.5" />
              {style.label}
            </Badge>
            {verdict?.is_anomaly && (
              <Badge variant="outline" className="font-medium">
                {verdict.diagnosis_label}
                {verdict.confidence > 0 && (
                  <span className="text-muted-foreground ml-1 font-normal">
                    · {pct(verdict.confidence)} confidence
                  </span>
                )}
              </Badge>
            )}
            <Badge variant="secondary" className="tabular">
              ISO zone {verdict?.iso_zone ?? "A"} · {num(verdict?.velocity_rms_mm_s)} mm/s
            </Badge>
          </div>

          <div>
            <p className="text-lg font-semibold tracking-tight">
              {verdict?.is_anomaly
                ? verdict.diagnosis_label
                : status === "watch"
                  ? "Elevated, below the alarm level"
                  : "No fault signature detected"}
            </p>
            <p className="text-muted-foreground text-sm">
              {verdict?.is_anomaly
                ? anomalyNote(verdict)
                : status === "watch"
                  ? "Reconstruction error is approaching the threshold — worth a second window before calling it."
                  : "Reconstruction error is within the healthy band learned during training."}
            </p>
          </div>

          {verdict && verdict.evidence.length > 0 && (
            <ul className="space-y-1 text-sm">
              {verdict.evidence.map((line) => (
                <li key={line} className="flex gap-2">
                  <span className={cn("mt-1.5 size-1.5 shrink-0 rounded-full", style.bg)} />
                  <span className="text-muted-foreground">{line}</span>
                </li>
              ))}
            </ul>
          )}

          <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-4">
            <Readout label="Recon. error" value={compact(verdict?.score)} />
            <Readout label="Alarm at" value={compact(verdict?.threshold)} />
            <Readout label="RMS" value={`${num(frame?.features.rms, 3)} g`} />
            <Readout label="Crest" value={num(frame?.features.crest_factor)} />
          </dl>
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * What the ISO velocity zone means *for this finding*.
 *
 * A bearing defect can be severe while the overall velocity still reads zone
 * A, because its energy sits far above the 10-1000 Hz band the standard
 * measures. Printing the bare zone note ("newly commissioned") next to a
 * critical alarm reads as a contradiction, so say why the two disagree.
 */
function anomalyNote(verdict: NonNullable<Frame["verdict"]>): string {
  const bearing = ["outer_race", "inner_race", "ball"].includes(verdict.diagnosis);
  if (bearing && (verdict.iso_zone === "A" || verdict.iso_zone === "B")) {
    return `Overall velocity is still ISO zone ${verdict.iso_zone} — a level-only alarm would miss this. The envelope spectrum is what exposes it.`;
  }
  return `ISO zone ${verdict.iso_zone}: ${ISO_ZONE_NOTE[verdict.iso_zone].toLowerCase()}.`;
}

function Readout({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-muted-foreground text-xs">{label}</dt>
      <dd className="tabular font-medium">{value}</dd>
    </div>
  );
}

/** Health as a ring: fills clockwise, coloured by the same status scale. */
function HealthDial({ health, status }: { health: number; status: Frame["verdict"]["status"] }) {
  const style = STATUS_STYLE[status];
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  const filled = (Math.max(0, Math.min(100, health)) / 100) * circumference;

  return (
    <div className="relative mx-auto size-36 shrink-0">
      <svg viewBox="0 0 128 128" className="size-full -rotate-90">
        <circle
          cx="64"
          cy="64"
          r={radius}
          fill="none"
          strokeWidth="10"
          className="stroke-secondary"
        />
        <circle
          cx="64"
          cy="64"
          r={radius}
          fill="none"
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={`${filled} ${circumference}`}
          className={cn("transition-[stroke-dasharray] duration-500", style.text)}
          stroke="currentColor"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={cn("tabular text-3xl font-bold", style.text)}>
          {Math.round(health)}
        </span>
        <span className="text-muted-foreground text-[0.7rem] tracking-wide uppercase">
          Health
        </span>
      </div>
    </div>
  );
}
