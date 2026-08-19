import { Bar, BarChart, Cell, LabelList, Tooltip, XAxis, YAxis } from "recharts";
import { Medal } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { ChartContainer, ChartTooltipContent } from "./ui/chart";
import type { Dataset } from "@/lib/types";

const PALETTE = [
  "var(--chart-1)", "var(--chart-2)", "var(--chart-3)",
  "var(--chart-4)", "var(--chart-5)", "var(--chart-6)",
];

export function RankingChart({ data }: { data: Dataset }) {
  const rows = data.ranking.slice(0, 15);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Medal className="size-4 text-chart-3" />
          Ülke sıralaması — ilk 15
          <span className="font-normal text-muted-foreground">
            ({data.meta.reference_year})
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ChartContainer config={{}} className="h-[380px]">
          <BarChart
            data={rows}
            layout="vertical"
            margin={{ left: 8, right: 28, top: 4, bottom: 4 }}
          >
            <XAxis type="number" hide domain={[0, "dataMax"]} />
            <YAxis
              type="category"
              dataKey="name"
              width={104}
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 11 }}
            />
            <Tooltip
              cursor={{ fill: "var(--muted)", opacity: 0.4 }}
              content={<ChartTooltipContent />}
            />
            <Bar dataKey="value" name="Pay" radius={[0, 6, 6, 0]} maxBarSize={22} isAnimationActive={false}>
              {rows.map((_, i) => (
                <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
              ))}
              <LabelList
                dataKey="value"
                position="right"
                formatter={(v) => `${v}%`}
                className="fill-muted-foreground"
                fontSize={10}
              />
            </Bar>
          </BarChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
