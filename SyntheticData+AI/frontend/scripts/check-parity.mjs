/**
 * Assert the TypeScript feature pipeline matches the Python one.
 *
 * Two implementations of the same DSP will drift the moment one of them is
 * edited, and the failure is silent: the dashboard keeps rendering, it just
 * shows different numbers offline than online. This runs both against the same
 * frozen windows and fails the build if they disagree.
 *
 *   python scripts/make_parity_fixture.py   # regenerate the fixture
 *   npm run check:parity
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// Node strips TypeScript types natively, so the very same source files the
// browser bundle uses are imported here -- not a compiled copy that could
// diverge from them.
const here = dirname(fileURLToPath(import.meta.url));
const fixture = JSON.parse(readFileSync(join(here, "parity-fixture.json"), "utf8"));
const bundle = JSON.parse(readFileSync(join(here, "..", "public", "model.json"), "utf8"));

const { extract } = await import("../src/lib/offline/features.ts");
const { Autoencoder } = await import("../src/lib/offline/autoencoder.ts");

const model = new Autoencoder(bundle);
const machine = {
  sampleRateHz: fixture.sample_rate_hz,
  windowSize: fixture.window_size,
  shaftRpm: fixture.shaft_rpm,
  resonanceHz: 3000,
  resonanceDecay: 900,
  noiseG: 0.035,
  baselineImbalanceG: 0.035,
  orders: { bpfo: 3.5848, bpfi: 5.4152, bsf: 2.3567, ftf: 0.3983 },
};

// Feature magnitudes span decibels to raw g, so compare relatively with an
// absolute floor for values that legitimately sit near zero.
const REL_TOLERANCE = 1e-6;
const ABS_TOLERANCE = 1e-6;

let failures = 0;
const report = [];

function close(actual, expected) {
  const diff = Math.abs(actual - expected);
  return diff <= ABS_TOLERANCE + REL_TOLERANCE * Math.abs(expected);
}

for (const testCase of fixture.cases) {
  const window = Float64Array.from(testCase.window);
  const { values, velocityRmsMmS } = extract(window, machine, fixture.shaft_rpm);

  let worstName = "";
  let worstDiff = 0;
  fixture.feature_names.forEach((name, i) => {
    const expected = testCase.features[name];
    const diff = Math.abs(values[i] - expected) / (Math.abs(expected) || 1);
    if (diff > worstDiff) {
      worstDiff = diff;
      worstName = name;
    }
    if (!close(values[i], expected)) {
      failures++;
      console.error(
        `  x ${testCase.mode}.${name}: ts=${values[i]} py=${expected} (rel ${diff.toExponential(2)})`,
      );
    }
  });

  const score = model.score(values);
  if (!close(score, testCase.score)) {
    failures++;
    console.error(`  x ${testCase.mode}.score: ts=${score} py=${testCase.score}`);
  }
  if (!close(model.healthIndex(score), testCase.health_index)) {
    failures++;
    console.error(`  x ${testCase.mode}.health_index mismatch`);
  }
  if (!close(velocityRmsMmS, testCase.velocity_rms_mm_s)) {
    failures++;
    console.error(
      `  x ${testCase.mode}.velocity: ts=${velocityRmsMmS} py=${testCase.velocity_rms_mm_s}`,
    );
  }
  if (score > model.threshold !== testCase.is_anomaly) {
    failures++;
    console.error(`  x ${testCase.mode}: anomaly verdict differs`);
  }
  const topContributor = model.topContributors(values, 1)[0].feature;
  if (topContributor !== testCase.top_contributor) {
    failures++;
    console.error(
      `  x ${testCase.mode}: top contributor ts=${topContributor} py=${testCase.top_contributor}`,
    );
  }

  report.push(
    `  ${failures === 0 ? "ok" : "  "} ${testCase.mode.padEnd(12)} worst feature drift ` +
      `${worstDiff.toExponential(1)} (${worstName})`,
  );
}

console.log(`parity: ${fixture.cases.length} cases x ${fixture.feature_names.length} features`);
console.log(report.join("\n"));

if (failures > 0) {
  console.error(`\nFAILED: ${failures} mismatches between the TypeScript and Python pipelines`);
  process.exit(1);
}
console.log("\nOK: TypeScript and Python pipelines agree");
