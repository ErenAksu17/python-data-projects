import { Flag } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Progress } from "./ui/progress";
import type { Dataset } from "@/lib/types";

export function ProgressToTarget({ data }: { data: Dataset }) {
  const { eu, target } = data;
  const progress = Math.min(100, (eu.latest.value / target.pct) * 100);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Flag className="size-4 text-chart-3" />
          2030 hedefine ilerleme
          <span className="text-muted-foreground font-normal">(AB-27)</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <Progress
          value={progress}
          className="h-4"
          indicatorClassName="bg-gradient-to-r from-chart-1 via-chart-2 to-chart-5"
        />
        <div className="flex items-center justify-between text-xs">
          <span className="font-semibold text-foreground tabular-nums">
            {eu.latest.value}% <span className="text-muted-foreground">({eu.latest.year})</span>
          </span>
          <span className="text-muted-foreground">
            hedefin <b className="text-foreground">%{Math.round(progress)}</b>’i tamamlandı
          </span>
          <span className="font-semibold text-destructive tabular-nums">
            Hedef {target.pct}%
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
