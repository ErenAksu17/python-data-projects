import { useMemo, useState } from "react";
import { Area, AreaChart, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts";
import { Compass } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select";
import {
  ChartContainer,
  ChartTooltipContent,
  type ChartConfig,
} from "./ui/chart";
import type { Dataset } from "@/lib/types";

const config: ChartConfig = { value: { label: "Pay", color: "var(--chart-1)" } };

export function CountryExplorer({ data }: { data: Dataset }) {
  const countries = useMemo(
    () =>
      [...data.countries].sort((a, b) => a.name.localeCompare(b.name, "tr")),
    [data.countries]
  );
  const [geo, setGeo] = useState(countries[0].geo);
  const country = countries.find((c) => c.geo === geo) ?? countries[0];

  const rows = country.trend.years.map((y, i) => ({
    year: y,
    value: country.trend.values[i],
  }));

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <Compass className="size-4 text-chart-5" />
            Ülke keşfi
          </CardTitle>
          <Select value={geo} onValueChange={setGeo}>
            <SelectTrigger className="w-[200px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {countries.map((c) => (
                <SelectItem key={c.geo} value={c.geo}>
                  {c.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap gap-6">
          <Stat value={`${country.latest_value}%`} label={`${country.latest_year} payı`} />
          <Stat
            value={country.cagr === null ? "—" : `${country.cagr.toFixed(1)}%`}
            label="yıllık büyüme (CAGR)"
          />
          <Stat value={`#${country.rank ?? "—"}`} label={`sıralama (${data.meta.reference_year})`} />
        </div>
        <ChartContainer config={config} className="h-[240px]">
          <AreaChart data={rows} margin={{ left: 4, right: 12, top: 8 }}>
            <defs>
              <linearGradient id="fillCountry" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--color-value)" stopOpacity={0.35} />
                <stop offset="95%" stopColor="var(--color-value)" stopOpacity={0.04} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="year" tickLine={false} axisLine={false} minTickGap={24} />
            <YAxis tickLine={false} axisLine={false} width={38} tickFormatter={(v) => `${v}%`} />
            <Tooltip content={<ChartTooltipContent />} />
            <Area
              dataKey="value"
              name={country.name}
              stroke="var(--color-value)"
              strokeWidth={2.5}
              fill="url(#fillCountry)"
              dot={false}
              activeDot={{ r: 4 }}
            />
          </AreaChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-2xl font-bold tracking-tight tabular-nums">
        {value}
      </span>
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  );
}
