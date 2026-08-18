import { useEffect, useState } from "react";
import { Leaf, Loader2 } from "lucide-react";
import { Badge } from "./components/ui/badge";
import { ThemeToggle } from "./components/ThemeToggle";
import { KpiCards } from "./components/KpiCards";
import { ProgressToTarget } from "./components/ProgressToTarget";
import { TrendForecastChart } from "./components/TrendForecastChart";
import { RankingChart } from "./components/RankingChart";
import { SectorChart } from "./components/SectorChart";
import { InsightCard } from "./components/InsightCard";
import { CountryExplorer } from "./components/CountryExplorer";
import { loadDataset } from "./lib/data";
import type { Dataset } from "./lib/types";

export default function App() {
  const [data, setData] = useState<Dataset | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadDataset().then(setData).catch((e) => setError(String(e.message ?? e)));
  }, []);

  return (
    <div className="app-bg min-h-screen">
      <div className="mx-auto max-w-6xl px-4 pb-16 pt-8 sm:px-6">
        <header className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex size-11 items-center justify-center rounded-2xl bg-gradient-to-br from-chart-1 to-chart-2 text-white shadow-lg shadow-chart-1/20">
              <Leaf className="size-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight sm:text-2xl">
                Renewable Energy Analyzer
              </h1>
              <p className="text-sm text-muted-foreground">
                Avrupa'da yenilenebilir enerjinin payı — Eurostat verisiyle
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {data && (
              <Badge variant="secondary" className="hidden sm:inline-flex">
                Kaynak: Eurostat · {data.meta.reference_year}
              </Badge>
            )}
            <ThemeToggle />
          </div>
        </header>

        {error && (
          <div className="rounded-xl border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
            <b>Veri yüklenemedi.</b> {error}. Önce{" "}
            <code>python scripts/build_data.py</code> çalıştırıp API'yi başlatın.
          </div>
        )}

        {!data && !error && (
          <div className="flex h-72 items-center justify-center text-muted-foreground">
            <Loader2 className="mr-2 size-5 animate-spin" /> Veri yükleniyor…
          </div>
        )}

        {data && (
          <main className="flex flex-col gap-5">
            <KpiCards data={data} />
            <ProgressToTarget data={data} />
            <TrendForecastChart data={data} />
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
              <RankingChart data={data} />
              <SectorChart data={data} />
            </div>
            <InsightCard data={data} />
            <CountryExplorer data={data} />

            <footer className="mt-4 rounded-xl border bg-card/60 p-5 text-xs text-muted-foreground">
              <p className="mb-2">
                <b className="text-foreground">Yöntem &amp; sınırlar:</b> Tahmin,
                yıla göre doğrusal trend (OLS) ile yapılır ve walk-forward
                doğrulamayla naif temel modele karşı sınanır. Yıllık ~20
                gözlemle ARIMA/XGBoost gibi modeller aşırı öğrenme yapacağından
                bilinçli olarak tercih edilmemiştir.
              </p>
              <p>
                Kaynak: {data.meta.source} · Lisans: {data.meta.license} ·
                Üretim: {data.meta.generated_at}
              </p>
            </footer>
          </main>
        )}
      </div>
    </div>
  );
}
