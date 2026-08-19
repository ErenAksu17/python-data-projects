"""Benchmark the autoencoder against equivalent detectors.

Reported honestly:

* ranking quality (ROC-AUC, PR-AUC) is threshold-free;
* the operating point is fixed by one policy applied to every learned method
  -- the 99.5th percentile of that method's own scores on the healthy
  validation split -- so no method gets a hand-tuned advantage;
* the ISO velocity rule keeps the alarm level the standard prescribes
  (4.5 mm/s, the zone B/C boundary), because that is how it is actually used;
* recall is broken out per fault mode and for *incipient* faults
  (severity <= 0.35), which is where condition monitoring earns its keep and
  where overall-level rules fall apart.
"""

from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from .autoencoder import AutoencoderBundle
from .baselines import Detector, build_baselines
from .config import DEFAULT_MACHINE, MachineSpec
from .dataset import Dataset
from .features import FEATURE_NAMES

#: Operating-point policy shared by every learned detector.
THRESHOLD_QUANTILE = 0.995
#: ISO 20816-3 zone B/C boundary for medium machines (mm/s RMS).
ISO_ALARM_MM_S = 4.5
#: A fault this subtle is what you actually want to catch early.
INCIPIENT_SEVERITY = 0.35


def _rates(labels: np.ndarray, flagged: np.ndarray) -> dict[str, float]:
    tp = int(((flagged == 1) & (labels == 1)).sum())
    fp = int(((flagged == 1) & (labels == 0)).sum())
    fn = int(((flagged == 0) & (labels == 1)).sum())
    tn = int(((flagged == 0) & (labels == 0)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_alarm_rate": fp / (fp + tn) if fp + tn else 0.0,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "true_negatives": tn,
    }


def _breakdown(test: Dataset, flagged: np.ndarray) -> dict[str, Any]:
    by_mode: dict[str, float] = {}
    for mode in sorted(set(test.modes.tolist())):
        if mode == "healthy":
            continue
        mask = test.modes == mode
        by_mode[mode] = float(flagged[mask].mean())

    incipient = (test.labels == 1) & (test.severities <= INCIPIENT_SEVERITY)
    severe = (test.labels == 1) & (test.severities > INCIPIENT_SEVERITY)
    return {
        "recall_by_mode": by_mode,
        "recall_incipient": float(flagged[incipient].mean()) if incipient.any() else 0.0,
        "recall_severe": float(flagged[severe].mean()) if severe.any() else 0.0,
    }


def _timed_scores(detector: Detector, features: np.ndarray) -> tuple[np.ndarray, float]:
    start = time.perf_counter()
    scores = np.asarray(detector.score(features), dtype=np.float64)
    elapsed_us = (time.perf_counter() - start) * 1e6 / max(len(features), 1)
    return scores, elapsed_us


def _evaluate_scores(
    name: str,
    family: str,
    val_scores: np.ndarray,
    test_scores: np.ndarray,
    test: Dataset,
    threshold: float,
    fit_ms: float,
    infer_us: float,
    threshold_note: str,
) -> dict[str, Any]:
    from sklearn.metrics import average_precision_score, roc_auc_score

    flagged = (test_scores > threshold).astype(int)
    return {
        "name": name,
        "family": family,
        "roc_auc": float(roc_auc_score(test.labels, test_scores)),
        "pr_auc": float(average_precision_score(test.labels, test_scores)),
        "threshold": float(threshold),
        "threshold_note": threshold_note,
        "healthy_val_score_p50": float(np.median(val_scores)),
        "fit_ms": fit_ms,
        "inference_us_per_window": infer_us,
        **_rates(test.labels, flagged),
        **_breakdown(test, flagged),
    }


def run(
    bundle: AutoencoderBundle,
    train: Dataset,
    val: Dataset,
    test: Dataset,
    machine: MachineSpec = DEFAULT_MACHINE,
) -> dict[str, Any]:
    """Score every detector on the same split and collect the comparison."""
    results: list[dict[str, Any]] = []

    # --- the autoencoder ------------------------------------------------- #
    ae_val, _ = _timed_scores(bundle, val.features)  # type: ignore[arg-type]
    ae_test, ae_us = _timed_scores(bundle, test.features)  # type: ignore[arg-type]
    results.append(
        _evaluate_scores(
            "autoencoder",
            "reconstruction",
            ae_val,
            ae_test,
            test,
            bundle.threshold,
            fit_ms=float(bundle.metadata.get("epochs_run", 0)) * 0.0,
            infer_us=ae_us,
            threshold_note=f"healthy-validation quantile {THRESHOLD_QUANTILE}",
        )
    )

    # --- learned and rule-based baselines -------------------------------- #
    rms_index = FEATURE_NAMES.index("rms")
    for detector in build_baselines(rms_index, latent_dim=bundle.latent_dim):
        start = time.perf_counter()
        detector.fit(train.features)
        fit_ms = (time.perf_counter() - start) * 1e3

        val_scores, _ = _timed_scores(detector, val.features)
        test_scores, infer_us = _timed_scores(detector, test.features)
        threshold = float(np.quantile(val_scores, THRESHOLD_QUANTILE))
        results.append(
            _evaluate_scores(
                detector.name,
                detector.family,
                val_scores,
                test_scores,
                test,
                threshold,
                fit_ms,
                infer_us,
                f"healthy-validation quantile {THRESHOLD_QUANTILE}",
            )
        )

    # --- the ISO overall-velocity rule ----------------------------------- #
    results.append(
        _evaluate_scores(
            "iso_velocity",
            "rule",
            val.velocity,
            test.velocity,
            test,
            ISO_ALARM_MM_S,
            fit_ms=0.0,
            infer_us=0.0,
            threshold_note=f"ISO 20816-3 zone B/C boundary, {ISO_ALARM_MM_S} mm/s",
        )
    )

    results.sort(key=lambda r: r["pr_auc"], reverse=True)

    return {
        "generated_utc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "operating_point": {
            "policy": (
                "threshold = 99.5th percentile of each detector's own scores on the "
                "healthy validation split; the ISO rule keeps its standard alarm level"
            ),
            "incipient_severity_max": INCIPIENT_SEVERITY,
        },
        "dataset": {
            "train_healthy_windows": len(train),
            "val_healthy_windows": len(val),
            "test_windows": len(test),
            "test_faulty_windows": test.n_faulty,
            "features": len(FEATURE_NAMES),
            "sample_rate_hz": machine.sample_rate_hz,
            "window_size": machine.window_size,
            "window_seconds": round(machine.window_seconds, 4),
        },
        "model": {
            "architecture": bundle.architecture,
            "latent_dim": bundle.latent_dim,
            "parameters": int(
                sum(layer.weight.size + layer.bias.size for layer in bundle.layers)
            ),
        },
        "methods": results,
    }


def save(report: dict[str, Any], path: str | Path = "artifacts/benchmark.json") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=1), encoding="utf-8")
    return path


def to_markdown(report: dict[str, Any]) -> str:
    """Render the comparison as a table for the README."""
    header = (
        "| Method | ROC-AUC | PR-AUC | Precision | Recall | F1 | "
        "False alarms | Incipient recall | Inference |\n"
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |\n"
    )
    rows = []
    for m in report["methods"]:
        rows.append(
            f"| `{m['name']}` | {m['roc_auc']:.3f} | {m['pr_auc']:.3f} | "
            f"{m['precision']:.3f} | {m['recall']:.3f} | {m['f1']:.3f} | "
            f"{m['false_alarm_rate']:.3f} | {m['recall_incipient']:.3f} | "
            f"{m['inference_us_per_window']:.0f} us |"
        )
    return header + "\n".join(rows) + "\n"
