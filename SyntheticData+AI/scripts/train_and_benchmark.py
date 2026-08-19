"""Rebuild both artifacts from scratch: the model bundle and the benchmark.

    python scripts/train_and_benchmark.py

Deterministic end to end -- same seeds in, same artifacts out.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vfactory import ablation, benchmark  # noqa: E402
from vfactory.config import DEFAULT_MACHINE  # noqa: E402
from vfactory.dataset import build  # noqa: E402
from vfactory.train import TrainConfig, train  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=ROOT / "artifacts" / "model.json", type=Path)
    parser.add_argument(
        "--report", default=ROOT / "artifacts" / "benchmark.json", type=Path
    )
    parser.add_argument(
        "--ablation", default=ROOT / "artifacts" / "ablation.json", type=Path
    )
    parser.add_argument("--epochs", default=400, type=int)
    parser.add_argument("--skip-ablation", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    verbose = not args.quiet

    print("[1/4] building healthy-only train/val and labelled test splits...")
    splits = build(DEFAULT_MACHINE)
    train_set, val_set, test_set = splits
    print(
        f"      train {len(train_set)} healthy | val {len(val_set)} healthy | "
        f"test {len(test_set)} ({test_set.n_faulty} faulty)"
    )

    print("[2/4] training the autoencoder on healthy data only...")
    bundle, _ = train(
        machine=DEFAULT_MACHINE,
        config=TrainConfig(epochs=args.epochs),
        splits=splits,
        verbose=verbose,
    )
    model_path = bundle.save(args.model)
    print(f"      wrote {model_path.relative_to(ROOT)} ({model_path.stat().st_size / 1024:.1f} KB)")

    print("[3/4] benchmarking against baseline detectors...")
    report = benchmark.run(bundle, train_set, val_set, test_set, DEFAULT_MACHINE)
    report_path = benchmark.save(report, args.report)
    print(f"      wrote {report_path.relative_to(ROOT)}\n")
    print(benchmark.to_markdown(report))

    if args.skip_ablation:
        print("[4/4] ablation skipped")
        return 0

    print("[4/4] running the ablation study (this retrains four pipelines)...")
    study = ablation.run(DEFAULT_MACHINE)
    study_path = ablation.save(study, args.ablation)
    print(f"      wrote {study_path.relative_to(ROOT)}\n")
    print(ablation.to_markdown(study))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
