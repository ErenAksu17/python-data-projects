import * as React from "react";
import { ResponsiveContainer } from "recharts";
import { cn } from "@/lib/utils";

export type ChartConfig = Record<
  string,
  { label?: string; color?: string }
>;

/**
 * Wraps a Recharts chart, exposes each series colour as a `--color-<key>` CSS
 * variable (so marks can reference `var(--color-foo)`), and applies sensible
 * shadcn-flavoured defaults to the SVG (muted grid, no focus outline).
 */
function ChartContainer({
  config,
  className,
  children,
}: {
  config: ChartConfig;
  className?: string;
  children: React.ReactElement;
}) {
  const style = Object.fromEntries(
    Object.entries(config)
      .filter(([, v]) => v.color)
      .map(([k, v]) => [`--color-${k}`, v.color])
  ) as React.CSSProperties;

  return (
    <div
      data-slot="chart"
      style={style}
      className={cn(
        "w-full [&_.recharts-cartesian-grid_line]:stroke-border/60 [&_.recharts-cartesian-axis-tick_text]:fill-muted-foreground [&_.recharts-cartesian-axis-tick_text]:text-xs [&_svg]:outline-none [&_.recharts-surface]:outline-none",
        className
      )}
    >
      <ResponsiveContainer width="100%" height="100%">
        {children}
      </ResponsiveContainer>
    </div>
  );
}

interface TooltipEntry {
  name?: string;
  value?: number | string;
  color?: string;
  dataKey?: string | number;
}

/** shadcn-styled tooltip body for Recharts `<Tooltip content={...} />`. */
function ChartTooltipContent({
  active,
  payload,
  label,
  unit = "%",
  labelFormatter,
  hideKeys = [],
}: {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string | number;
  unit?: string;
  labelFormatter?: (label: string | number) => string;
  hideKeys?: string[];
}) {
  if (!active || !payload || payload.length === 0) return null;
  const rows = payload.filter(
    (p) => !hideKeys.includes(String(p.dataKey)) && p.value != null
  );
  if (rows.length === 0) return null;

  return (
    <div className="rounded-lg border bg-popover/95 px-3 py-2 text-xs shadow-xl backdrop-blur">
      <div className="mb-1 font-semibold text-foreground">
        {labelFormatter ? labelFormatter(label ?? "") : label}
      </div>
      <div className="flex flex-col gap-1">
        {rows.map((r, i) => (
          <div key={i} className="flex items-center gap-2">
            <span
              className="size-2.5 rounded-[3px]"
              style={{ background: r.color }}
            />
            <span className="text-muted-foreground">{r.name}</span>
            <span className="ml-auto font-semibold tabular-nums text-foreground">
              {typeof r.value === "number" ? r.value.toFixed(1) : r.value}
              {unit}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export { ChartContainer, ChartTooltipContent };
