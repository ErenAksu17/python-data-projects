import { Bell, BrainCircuit } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { Frame } from "@/lib/types";
import type { MachineEvent } from "@/lib/useMonitor";
import { STATUS_STYLE, cn, compact, featureLabel, pct } from "@/lib/utils";

/**
 * Attribution: which features the model failed to reconstruct.
 *
 * A one-class model only says "not normal". Showing where the error came from
 * is what turns that into something an engineer can check against the machine.
 */
export function Attribution({ frame }: { frame: Frame | null }) {
  const contributors = frame?.verdict.contributors ?? [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <BrainCircuit className="text-primary size-4" />
          Why the model reacted
        </CardTitle>
        <CardDescription>
          Share of the reconstruction error carried by each feature.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {contributors.length === 0 && (
          <p className="text-muted-foreground text-sm">Waiting for the first window…</p>
        )}
        {contributors.map((item) => (
          <div key={item.feature} className="space-y-1">
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span className="truncate font-medium">{featureLabel(item.feature)}</span>
              <span className="text-muted-foreground tabular shrink-0">
                {pct(item.share, 1)}
              </span>
            </div>
            <div className="bg-secondary h-1.5 overflow-hidden rounded-full">
              <div
                className="bg-primary h-full rounded-full transition-[width] duration-500"
                style={{ width: `${Math.min(100, item.share * 100)}%` }}
              />
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

/** Alarm transitions, newest first — not one row per frame. */
export function EventLog({
  events,
  onClear,
}: {
  events: MachineEvent[];
  onClear: () => void;
}) {
  const newestFirst = [...events].reverse();

  return (
    <Card className="flex flex-col">
      <CardHeader className="flex-row items-start justify-between gap-3">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Bell className="text-primary size-4" />
            Event log
          </CardTitle>
          <CardDescription>State changes, not every window.</CardDescription>
        </div>
        {events.length > 0 && (
          <Button variant="ghost" size="sm" onClick={onClear}>
            Clear
          </Button>
        )}
      </CardHeader>
      <CardContent className="max-h-72 flex-1 space-y-2 overflow-y-auto">
        {newestFirst.length === 0 && (
          <p className="text-muted-foreground text-sm">
            Nothing logged yet. Inject a fault to see the model react.
          </p>
        )}
        {newestFirst.map((event) => {
          const style = STATUS_STYLE[event.status];
          return (
            <div
              key={`${event.seq}-${event.t}`}
              className="border-border/70 flex gap-3 rounded-lg border p-2.5"
            >
              <span className={cn("mt-1.5 size-2 shrink-0 rounded-full", style.bg)} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline gap-x-2">
                  <span className="text-sm font-medium">{event.label}</span>
                  <Badge className={cn("px-1.5 py-0 text-[0.65rem]", style.badge)}>
                    {style.label}
                  </Badge>
                  <span className="text-muted-foreground tabular ml-auto text-xs">
                    t+{event.t.toFixed(1)}s
                  </span>
                </div>
                {event.evidence[0] && (
                  <p className="text-muted-foreground mt-0.5 text-xs">{event.evidence[0]}</p>
                )}
                <p className="text-muted-foreground tabular mt-0.5 text-xs">
                  error {compact(event.score)}
                  {event.confidence > 0 && ` · ${pct(event.confidence)} confidence`}
                </p>
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
