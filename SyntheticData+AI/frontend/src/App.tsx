import { useEffect, useState } from "react";
import { Info } from "lucide-react";
import { Header } from "@/components/Header";
import { MachineControls } from "@/components/MachineControls";
import { MachinePlate } from "@/components/MachinePlate";
import { StatusHero } from "@/components/StatusHero";
import { Attribution, EventLog } from "@/components/Explanation";
import { AblationTable, BenchmarkTable, RecallByMode } from "@/components/Reports";
import {
  EnvelopeChart,
  ScoreTrend,
  SpectrumChart,
  WaveformChart,
} from "@/components/SignalCharts";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { fetchMachine } from "@/lib/api";
import type { MachineInfo } from "@/lib/types";
import { useMonitor } from "@/lib/useMonitor";

const TABS = ["signal", "diagnosis", "evidence"] as const;

/** `?tab=diagnosis` deep-links a view, so a finding can be shared as a URL. */
function tabFromUrl(): (typeof TABS)[number] {
  if (typeof window === "undefined") return "signal";
  const tab = new URLSearchParams(window.location.search).get("tab");
  return TABS.includes(tab as (typeof TABS)[number])
    ? (tab as (typeof TABS)[number])
    : "signal";
}

/** Nominal SKF 6205 figures, used until (or unless) the API answers. */
const FALLBACK_MACHINE: MachineInfo = {
  sample_rate_hz: 12000,
  window_size: 2048,
  window_seconds: 0.17067,
  shaft_rpm: 1797,
  shaft_hz: 29.95,
  resonance_hz: 3000,
  freq_resolution_hz: 5.859,
  fault_modes: ["healthy", "outer_race", "inner_race", "ball", "imbalance", "looseness"],
  defect_orders: { bpfo: 3.5848, bpfi: 5.4152, bsf: 2.3567, ftf: 0.3983 },
  defect_frequencies_hz: { bpfo: 107.36, bpfi: 162.19, bsf: 70.58, ftf: 11.93 },
  envelope_band_hz: [2000, 4500],
};

export default function App() {
  const monitor = useMonitor();
  const [machine, setMachine] = useState<MachineInfo>(FALLBACK_MACHINE);

  useEffect(() => {
    fetchMachine()
      .then(setMachine)
      .catch(() => setMachine(FALLBACK_MACHINE));
  }, []);

  return (
    <div className="control-room min-h-dvh">
      <Header
        mode={monitor.mode}
        requestedMode={monitor.requestedMode}
        onModeChange={monitor.setRequestedMode}
        connection={monitor.connection}
      />

      <main className="mx-auto max-w-[1500px] space-y-5 px-4 py-6 sm:px-6">
        {monitor.notice && (
          <div className="border-primary/25 bg-primary/8 text-foreground/90 flex items-start gap-2.5 rounded-xl border px-4 py-3 text-sm">
            <Info className="text-primary mt-0.5 size-4 shrink-0" />
            <p>{monitor.notice}</p>
          </div>
        )}

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
          <div className="space-y-5">
            <StatusHero frame={monitor.frame} />

            <Tabs defaultValue={tabFromUrl()}>
              <TabsList>
                <TabsTrigger value="signal">Live signal</TabsTrigger>
                <TabsTrigger value="diagnosis">Diagnosis</TabsTrigger>
                <TabsTrigger value="evidence">Benchmarks</TabsTrigger>
              </TabsList>

              <TabsContent value="signal" className="space-y-5">
                <ScoreTrend trend={monitor.trend} />
                <div className="grid gap-5 xl:grid-cols-2">
                  <WaveformChart frame={monitor.frame} />
                  <SpectrumChart frame={monitor.frame} />
                </div>
              </TabsContent>

              <TabsContent value="diagnosis" className="space-y-5">
                <EnvelopeChart frame={monitor.frame} machine={machine} />
                <div className="grid gap-5 xl:grid-cols-2">
                  <Attribution frame={monitor.frame} />
                  <RecallByMode report={monitor.benchmark} />
                </div>
              </TabsContent>

              <TabsContent value="evidence" className="space-y-5">
                <BenchmarkTable report={monitor.benchmark} />
                <AblationTable report={monitor.ablation} />
              </TabsContent>
            </Tabs>
          </div>

          <aside className="space-y-5">
            <MachineControls controls={monitor.controls} onChange={monitor.setControls} />
            <EventLog events={monitor.events} onClear={monitor.clearEvents} />
            <MachinePlate
              machine={machine}
              frame={monitor.frame}
              modelMeta={monitor.modelMeta}
            />
          </aside>
        </div>

        <footer className="text-muted-foreground border-t pt-5 text-xs">
          <p>
            Synthetic data throughout: no real machine was measured. Signals follow
            a rolling-element bearing model (SKF 6205 geometry, impacts ringing
            down a 3 kHz resonance), and severity is calibrated against the ISO
            20816-3 velocity zones.
          </p>
        </footer>
      </main>
    </div>
  );
}
