import { Lightbulb } from "lucide-react";
import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import type { Dataset } from "@/lib/types";

export function InsightCard({ data }: { data: Dataset }) {
  const cases = data.insights.res_e_over_100;

  return (
    <Card className="relative overflow-hidden border-l-4 border-l-chart-2">
      <div className="pointer-events-none absolute -right-8 -top-10 size-40 rounded-full bg-chart-2/10 blur-2xl" />
      <div className="relative flex flex-col gap-3 px-5 sm:flex-row sm:gap-4">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-chart-3/15 text-chart-3">
          <Lightbulb className="size-5" />
        </div>
        <div className="flex flex-col gap-3">
          <h3 className="text-base font-semibold tracking-tight">
            Neden bazı ülkelerde elektrik payı %100’ü aşıyor?
          </h3>
          <p className="text-sm leading-relaxed text-muted-foreground">
            Çünkü bu, genel değil <b className="text-foreground">elektrik sektörü</b>{" "}
            oranıdır: yenilenebilir elektrik <i>üretimi</i> ÷ yurtiçi{" "}
            <i>tüketim</i>. Hidroelektrik ağırlıklı{" "}
            <b className="text-foreground">net ihracatçı</b> ülkelerde üretim,
            tüketimi aşabildiği için oran %100’ü geçer — bu bir veri hatası
            değildir. Genel (overall) pay ise her zaman ≤ %100’dür, bu yüzden
            sektörleri ayırmadan ortalama almak yanlış olur.
          </p>
          <div className="flex flex-wrap gap-2">
            {cases.map((c) => (
              <Badge key={c.geo} variant="accent" className="gap-1.5">
                <span className="font-bold">{c.name}</span>
                <span className="tabular-nums">%{c.value}</span>
                <span className="opacity-70">({c.year})</span>
              </Badge>
            ))}
          </div>
        </div>
      </div>
    </Card>
  );
}
