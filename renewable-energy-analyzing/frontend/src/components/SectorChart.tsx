import { Bar, BarChart, Cell, LabelList, Tooltip, XAxis, YAxis } from "recharts";
import { Layers } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { ChartContainer, ChartTooltipContent } from "./ui/chart";
import type { Dataset } from "@/lib/types";

const LABELS: Record<string, string> = {
  Overall: "Genel",
  Electricity: "Elektrik",
  "Heating & cooling": "Isıtma/soğutma",
  Transport: "Ulaşım",
};
const COLORS = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)"];

export function SectorChart({ data }: { data: Dataset }) {
  const rows = data.eu.sectors.map((s) => ({
    label: LABELS[s.label] ?? s.label,
    value: s.value,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Layers className="size-4 text-chart-4" />
          Sektöre göre pay
          <span className="font-normal text-muted-foreground">(AB-27)</span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ChartContainer config={{}} className="h-[380px]">
          <BarChart data={rows} margin={{ left: 4, right: 8, top: 18 }}>
            <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 12 }} />
            <YAxis hide domain={[0, "dataMax + 6"]} />
            <Tooltip
              cursor={{ fill: "var(--muted)", opacity: 0.4 }}
              content={<ChartTooltipContent />}
            />
            <Bar dataKey="value" name="Pay" radius={[8, 8, 0, 0]} maxBarSize={72} isAnimationActive={false}>
              {rows.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
              <LabelList
                dataKey="value"
                position="top"
                formatter={(v) => `${v}%`}
                className="fill-foreground"
                fontSize={12}
                fontWeight={600}
              />
            </Bar>
          </BarChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
