"""Freeze a Python-computed fixture the TypeScript port has to reproduce.

The browser demo re-implements the feature pipeline and the autoencoder in
TypeScript. Two implementations of the same maths drift silently unless
something checks, so this writes a fixture of raw windows plus the features,
scores and verdicts Python produces for them; ``frontend/scripts/check-parity.mjs``
asserts the TypeScript side lands on the same numbers.

    python scripts/make_parity_fixture.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vfactory.autoencoder import AutoencoderBundle  # noqa: E402
from vfactory.config import DEFAULT_MACHINE  # noqa: E402
from vfactory.detector import analyse  # noqa: E402
from vfactory.features import FEATURE_NAMES, describe, extract, velocity_rms_mm_s  # noqa: E402
from vfactory.simulator import FaultSpec, VibrationSimulator  # noqa: E402

CASES = [
    ("healthy", 0.0),
    ("outer_race", 0.75),
    ("inner_race", 0.75),
    ("ball", 0.7),
    ("imbalance", 0.8),
    ("looseness", 0.8),
]


def main() -> int:
    bundle = AutoencoderBundle.load(ROOT / "artifacts" / "model.json")
    sim = VibrationSimulator(DEFAULT_MACHINE, seed=987654)

    cases = []
    for index, (mode, severity) in enumerate(CASES):
        window = sim.window(FaultSpec(mode, severity), t0=index * DEFAULT_MACHINE.window_seconds)
        features = extract(window, DEFAULT_MACHINE)
        verdict, _ = analyse(window, bundle, DEFAULT_MACHINE)
        cases.append(
            {
                "mode": mode,
                "severity": severity,
                "window": [float(v) for v in window],
                "features": describe(features),
                "score": bundle.score_one(features),
                "health_index": bundle.health_index(bundle.score_one(features)),
                "velocity_rms_mm_s": velocity_rms_mm_s(window, DEFAULT_MACHINE.sample_rate_hz),
                "is_anomaly": verdict.is_anomaly,
                "diagnosis": verdict.diagnosis,
                "top_contributor": verdict.contributors[0]["feature"],
            }
        )

    payload = {
        "generated_by": "scripts/make_parity_fixture.py",
        "sample_rate_hz": DEFAULT_MACHINE.sample_rate_hz,
        "window_size": DEFAULT_MACHINE.window_size,
        "shaft_rpm": DEFAULT_MACHINE.shaft_rpm,
        "feature_names": list(FEATURE_NAMES),
        "threshold": bundle.threshold,
        "cases": cases,
    }

    out = ROOT / "frontend" / "scripts" / "parity-fixture.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size / 1024:.0f} KB, {len(cases)} cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
