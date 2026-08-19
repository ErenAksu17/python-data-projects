import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Sparkles } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import {
  ChartContainer,
  ChartTooltipContent,
  type ChartConfig,
} from "./ui/chart";
import type { Dataset } from "@/lib/types";

const config: ChartConfig = {
  actual: { label: "Gerçekleşen", color: "var(--chart-1)" },
  forecast: { label: "Tahmin", color: "var(--chart-2)" },
};

export function TrendForecastChart({ data }: { data: Dataset }) {
  const { eu, target } = data;
  const { years, values } = eu.trend;
  const fc = eu.forecast;
  const lastIdx = years.length - 1;

  type Row = {
    year: number;
    actual: number | null;
    forecast: number | null;
    base: number | null;
    band: number | null;
  };

  const rows: Row[] = years.map((y, i) => ({
    year: y,
    actual: values[i],
    forecast: i === lastIdx ? values[i] : null,
    base: i === lastIdx ? values[i] : null,
    band: i === lastIdx ? 0 : null,
  }));
  fc.forecast_years.forEach((y, k) => {
    rows.push({
      year: y,
      actual: null,
      forecast: fc.forecast_values[k],
      base: fc.forecast_low[k],
      band: fc.forecast_high[k] - fc.forecast_low[k],
    });
  });

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Sparkles className="size-4 text-chart-2" />
            AB-27 yenilenebilir payı: trend ve tahmin
          </CardTitle>
          <div className="flex items-center gap-2">
            <Badge variant="outline">R² {fc.r2}</Badge>
            {fc.beats_naive && (
              <Badge variant="success">naif modeli geçiyor ✓</Badge>
            )}
          </div>
        </div>
        <CardDescription>
          {fc.method} · holdout MAPE {fc.model_mape?.toFixed(1)}%
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ChartContainer config={config} className="h-[320px]">
          <ComposedChart data={rows} margin={{ left: 4, right: 12, top: 10 }}>
            <defs>
              <linearGradient id="fillActual" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--color-actual)" stopOpacity={0.35} />
                <stop offset="95%" stopColor="var(--color-actual)" stopOpacity={0.04} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="year" tickLine={false} axisLine={false} minTickGap={24} />
            <YAxis
              tickLine={false}
              axisLine={false}
              width={38}
              domain={[0, Math.ceil(target.pct + 4)]}
              tickFormatter={(v) => `${v}%`}
            />
            <Tooltip
              content={
                <ChartTooltipContent hideKeys={["base", "band"]} />
              }
            />
            {/* Forecast confidence band (base transparent + band shaded) */}
            <Area dataKey="base" stackId="band" stroke="none" fill="transparent" isAnimationActive={false} connectNulls />
            <Area dataKey="band" name="Tahmin bandı" stackId="band" stroke="none" fill="var(--color-forecast)" fillOpacity={0.16} isAnimationActive={false} connectNulls />
            {/* Actual */}
            <Area
              dataKey="actual"
              name="Gerçekleşen"
              stroke="var(--color-actual)"
              strokeWidth={2.5}
              fill="url(#fillActual)"
              connectNulls
              dot={false}
              activeDot={{ r: 4 }}
              isAnimationActive={false}
            />
            {/* Forecast */}
            <Line
              dataKey="forecast"
              name="Tahmin"
              stroke="var(--color-forecast)"
              strokeWidth={2.5}
              strokeDasharray="6 4"
              dot={{ r: 3 }}
              connectNulls
              isAnimationActive={false}
            />
            <ReferenceLine
              y={target.pct}
              stroke="var(--destructive)"
              strokeDasharray="4 4"
              label={{
                value: `2030 hedefi ${target.pct}%`,
                position: "insideTopLeft",
                fill: "var(--destructive)",
                fontSize: 11,
                fontWeight: 600,
              }}
            />
          </ComposedChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
