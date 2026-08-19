import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import type { AblationReport, BenchmarkReport } from "@/lib/types";
import { cn, num, pct } from "@/lib/utils";

/**
 * The comparison against equivalent detectors.
 *
 * Shown in the product, not just the README, because the honest result is the
 * interesting one: the autoencoder ties the classical novelty detectors on
 * accuracy and wins on deployment cost — while the industry-standard overall
 * level rule misses most bearing faults entirely.
 */
export function BenchmarkTable({ report }: { report: BenchmarkReport | null }) {
  if (!report) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Method comparison</CardTitle>
          <CardDescription>
            Run <code className="text-xs">scripts/train_and_benchmark.py</code> to
            generate the report.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Method comparison</CardTitle>
        <CardDescription>
          {report.dataset.test_windows} test windows,{" "}
          {report.dataset.test_faulty_windows} faulty. {report.operating_point.policy}.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Method</TableHead>
              <TableHead className="text-right">ROC-AUC</TableHead>
              <TableHead className="text-right">PR-AUC</TableHead>
              <TableHead className="text-right">Recall</TableHead>
              <TableHead className="text-right">Incipient</TableHead>
              <TableHead className="text-right">False alarms</TableHead>
              <TableHead className="text-right">Inference</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {report.methods.map((method) => {
              const ours = method.name === "autoencoder";
              return (
                <TableRow key={method.name} data-highlight={ours}>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <span className={cn("font-mono text-xs", ours && "font-semibold")}>
                        {method.name}
                      </span>
                      {ours && <Badge className="px-1.5 py-0 text-[0.65rem]">this project</Badge>}
                    </div>
                  </TableCell>
                  <TableCell className="tabular text-right">{num(method.roc_auc, 3)}</TableCell>
                  <TableCell className="tabular text-right">{num(method.pr_auc, 3)}</TableCell>
                  <TableCell className="tabular text-right">{pct(method.recall, 1)}</TableCell>
                  <TableCell className="tabular text-right">
                    {pct(method.recall_incipient, 1)}
                  </TableCell>
                  <TableCell className="tabular text-right">
                    {pct(method.false_alarm_rate, 1)}
                  </TableCell>
                  <TableCell className="tabular text-muted-foreground text-right">
                    {method.inference_us_per_window < 1
                      ? "<1 µs"
                      : `${Math.round(method.inference_us_per_window)} µs`}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
        <p className="text-muted-foreground mt-3 text-xs">
          <strong>Incipient</strong> = recall on faults at severity ≤{" "}
          {report.operating_point.incipient_severity_max}, where early detection
          actually matters.
        </p>
      </CardContent>
    </Card>
  );
}

/** What each step of the rewrite bought, measured rather than asserted. */
export function AblationTable({ report }: { report: AblationReport | null }) {
  if (!report) return null;

  const first = report.stages[0];
  const last = report.stages.at(-1);
  const gain =
    first && last && first.recall_incipient > 0
      ? last.recall_incipient / first.recall_incipient
      : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>What the rewrite changed</CardTitle>
        <CardDescription>
          Every stage trained and thresholded identically, on the same test
          windows. Only the listed change differs.
          {gain && (
            <>
              {" "}
              Early-fault detection improved <strong>{num(gain, 1)}×</strong> from the
              original design.
            </>
          )}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Stage</TableHead>
              <TableHead>Change</TableHead>
              <TableHead className="text-right">Recall</TableHead>
              <TableHead className="text-right">Incipient</TableHead>
              <TableHead className="text-right">False alarms</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {report.stages.map((stage, index) => (
              <TableRow key={stage.name} data-highlight={index === report.stages.length - 1}>
                <TableCell className="font-mono text-xs">{stage.name}</TableCell>
                <TableCell className="text-muted-foreground max-w-md text-xs whitespace-normal">
                  {stage.description}
                </TableCell>
                <TableCell className="tabular text-right">{pct(stage.recall, 1)}</TableCell>
                <TableCell className="tabular text-right">
                  {pct(stage.recall_incipient, 1)}
                </TableCell>
                <TableCell className="tabular text-right">
                  {pct(stage.false_alarm_rate, 1)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

/** Per-fault recall for the shipped model, so the weak spots are visible. */
export function RecallByMode({ report }: { report: BenchmarkReport | null }) {
  const model = report?.methods.find((m) => m.name === "autoencoder");
  if (!model) return null;

  const rows = Object.entries(model.recall_by_mode).sort((a, b) => b[1] - a[1]);
  return (
    <Card>
      <CardHeader>
        <CardTitle>Detection rate by fault</CardTitle>
        <CardDescription>
          Averaged over the full severity range, including barely-there defects.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {rows.map(([mode, recall]) => (
          <div key={mode} className="space-y-1">
            <div className="flex items-baseline justify-between text-sm">
              <span className="font-medium capitalize">{mode.replace(/_/g, " ")}</span>
              <span className="text-muted-foreground tabular">{pct(recall, 1)}</span>
            </div>
            <div className="bg-secondary h-1.5 overflow-hidden rounded-full">
              <div
                className="h-full rounded-full bg-[var(--chart-1)]"
                style={{ width: `${recall * 100}%` }}
              />
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
