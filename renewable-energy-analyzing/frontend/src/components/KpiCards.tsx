import type { ReactNode } from "react";
import { Leaf, Target, TrendingUp, Trophy } from "lucide-react";
import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import type { Dataset } from "@/lib/types";
import { cn } from "@/lib/utils";

export function KpiCards({ data }: { data: Dataset }) {
  const { eu, target, ranking, meta } = data;
  const leader = ranking[0];
  const progress = Math.round((eu.latest.value / target.pct) * 100);

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {/* Hero KPI — gradient */}
      <Card className="relative overflow-hidden border-0 text-white shadow-lg">
        <div className="absolute inset-0 bg-gradient-to-br from-chart-1 to-chart-2" />
        <div className="absolute -right-6 -top-6 size-28 rounded-full bg-white/10 blur-xl" />
        <div className="relative flex flex-col gap-2 px-5">
          <div className="flex items-center gap-2 text-sm font-medium text-white/85">
            <Leaf className="size-4" />
            AB-27 yenilenebilir payı
          </div>
          <div className="text-4xl font-bold tracking-tight tabular-nums">
            {eu.latest.value}
            <span className="text-2xl font-semibold text-white/80">%</span>
          </div>
          <div className="text-xs text-white/80">
            {eu.latest.year}
            {eu.latest.provisional ? " · geçici veri" : " · kesinleşmiş"}
          </div>
        </div>
      </Card>

      <KpiTile
        icon={<TrendingUp className="size-4" />}
        label="2030 hedefine kalan"
        value={`${eu.gap_to_target}`}
        unit=" puan"
        sub={`yıllık +${eu.forecast.slope_pct_per_year.toFixed(2)} puan hızla`}
        accent="text-chart-3"
      >
        <Badge variant="warning">%{progress} tamamlandı</Badge>
      </KpiTile>

      <KpiTile
        icon={<Target className="size-4" />}
        label="2030 AB hedefi"
        value={`${target.pct}`}
        unit="%"
        sub="RED direktifi (EU/2023/2413)"
        accent="text-chart-5"
      />

      <KpiTile
        icon={<Trophy className="size-4" />}
        label={`Lider ülke (${meta.reference_year})`}
        value={leader.name}
        valueClass="text-2xl"
        sub={`${leader.value}% yenilenebilir pay`}
        accent="text-chart-4"
      >
        <Badge variant="success">#{leader.rank} sırada</Badge>
      </KpiTile>
    </div>
  );
}

function KpiTile({
  icon,
  label,
  value,
  unit,
  sub,
  accent,
  valueClass,
  children,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  unit?: string;
  sub: string;
  accent: string;
  valueClass?: string;
  children?: ReactNode;
}) {
  return (
    <Card className="justify-between">
      <div className="flex flex-col gap-2 px-5">
        <div
          className={cn(
            "flex items-center gap-2 text-sm font-medium text-muted-foreground",
            accent
          )}
        >
          {icon}
          <span className="text-muted-foreground">{label}</span>
        </div>
        <div
          className={cn(
            "font-bold tracking-tight tabular-nums",
            valueClass ?? "text-4xl"
          )}
        >
          {value}
          {unit && (
            <span className="text-2xl font-semibold text-muted-foreground">
              {unit}
            </span>
          )}
        </div>
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs text-muted-foreground">{sub}</span>
          {children}
        </div>
      </div>
    </Card>
  );
}
