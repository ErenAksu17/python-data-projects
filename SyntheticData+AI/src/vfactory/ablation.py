"""Ablation: what each step of the rewrite actually bought.

Four pipelines, evaluated on the same signals, so the improvement can be read
as a number rather than asserted in a README:

``v1_scalar_ae``
    The original project, reproduced faithfully: an autoencoder over a single
    raw acceleration *sample* (1 -> 16 -> 8 -> 4 -> 8 -> 16 -> 1), a scaler
    fitted on the whole dataset (faults included), and a window scored by its
    mean per-sample reconstruction error.

``v2_features``
    Same network size, but fed the 26 diagnostic window features instead of a
    lone sample, and trained on healthy data only.

``v3_residual_norm``
    Adds residual normalisation, so a defect signature is not diluted by the
    two dozen features that are pure noise on a healthy machine.

``v4_latent6``
    The shipped model: latent width chosen on the development split.

Note that ``v1`` is given a *fairer* deal than the original code, which never
loaded its trained weights at all in the dashboard. Even trained properly, it
has no signal to work with -- which is the point.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import numpy as np

from .config import DEFAULT_MACHINE, MachineSpec
from .dataset import Dataset, build
from .train import TrainConfig, train

INCIPIENT_SEVERITY = 0.35
THRESHOLD_QUANTILE = 0.995


def _metrics(labels: np.ndarray, severities: np.ndarray, scores: np.ndarray, threshold: float):
    from sklearn.metrics import average_precision_score, roc_auc_score

    flagged = scores > threshold
    faulty = labels == 1
    incipient = faulty & (severities <= INCIPIENT_SEVERITY)
    tp = int((flagged & faulty).sum())
    fp = int((flagged & ~faulty).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = float(flagged[faulty].mean()) if faulty.any() else 0.0
    return {
        "roc_auc": float(roc_auc_score(labels, scores)),
        "pr_auc": float(average_precision_score(labels, scores)),
        "precision": precision,
        "recall": recall,
        "f1": (2 * precision * recall / (precision + recall)) if precision + recall else 0.0,
        "false_alarm_rate": float(flagged[~faulty].mean()) if (~faulty).any() else 0.0,
        "recall_incipient": float(flagged[incipient].mean()) if incipient.any() else 0.0,
    }


# --------------------------------------------------------------------------- #
# v1 -- the original design, reproduced
# --------------------------------------------------------------------------- #


def _train_scalar_autoencoder(samples: np.ndarray, seed: int, epochs: int = 12):
    """1 -> 16 -> 8 -> 4 -> 8 -> 16 -> 1, exactly the original architecture."""
    import torch
    from torch import nn

    torch.manual_seed(seed)
    model = nn.Sequential(
        nn.Linear(1, 16), nn.ReLU(),
        nn.Linear(16, 8), nn.ReLU(),
        nn.Linear(8, 4),
        nn.Linear(4, 8), nn.ReLU(),
        nn.Linear(8, 16), nn.ReLU(),
        nn.Linear(16, 1),
    )
    x = torch.tensor(samples.reshape(-1, 1), dtype=torch.float32)
    optimiser = torch.optim.Adam(model.parameters(), lr=1e-3)
    criterion = nn.MSELoss()
    loader = torch.utils.data.DataLoader(
        torch.utils.data.TensorDataset(x), batch_size=512, shuffle=True
    )
    for _ in range(epochs):
        for (batch,) in loader:
            loss = criterion(model(batch), batch)
            optimiser.zero_grad()
            loss.backward()
            optimiser.step()
    model.eval()
    return model


def _score_scalar_autoencoder(model, windows: np.ndarray, mean: float, std: float) -> np.ndarray:
    import torch

    scaled = (windows - mean) / std
    with torch.no_grad():
        x = torch.tensor(scaled.reshape(-1, 1), dtype=torch.float32)
        recon = model(x).numpy().reshape(windows.shape)
    return ((recon - scaled) ** 2).mean(axis=1)


def _run_v1(splits: tuple[Dataset, Dataset, Dataset], seed: int) -> dict[str, Any]:
    """Reproduce the original pipeline, including its whole-dataset scaler.

    Evaluated on exactly the same test rows as every other stage, so the only
    thing that differs is the pipeline.
    """
    train_set, val_set, test_set = splits
    train_windows = train_set.windows
    val_windows = val_set.windows
    test_windows = test_set.windows
    assert train_windows is not None and val_windows is not None and test_windows is not None

    # The original fitted its scaler on everything it had, faults included --
    # reproduced here so the comparison shows the real pipeline, warts and all.
    everything = np.concatenate([train_windows.ravel(), test_windows.ravel()])
    mean, std = float(everything.mean()), float(everything.std()) or 1.0

    model = _train_scalar_autoencoder((train_windows.ravel() - mean) / std, seed)
    val_scores = _score_scalar_autoencoder(model, val_windows, mean, std)
    test_scores = _score_scalar_autoencoder(model, test_windows, mean, std)
    threshold = float(np.quantile(val_scores, THRESHOLD_QUANTILE))

    return {
        "name": "v1_scalar_ae",
        "description": (
            "original design: autoencoder over single raw samples, scaler fitted "
            "on the whole dataset, window scored by mean per-sample error"
        ),
        "parameters": 445,
        **_metrics(test_set.labels, test_set.severities, test_scores, threshold),
    }


# --------------------------------------------------------------------------- #
# v2..v4 -- the rewrite, one change at a time
# --------------------------------------------------------------------------- #


def _run_feature_stage(
    name: str,
    description: str,
    splits: tuple[Dataset, Dataset, Dataset],
    config: TrainConfig,
    residual_norm: bool,
) -> dict[str, Any]:
    from dataclasses import replace

    _, val_set, test_set = splits
    bundle, _ = train(config=config, splits=splits, verbose=False)
    if not residual_norm:
        bundle = replace(bundle, residual_scale=None)
        threshold = float(
            np.quantile(bundle.score(val_set.features), config.threshold_quantile)
        )
        bundle = replace(bundle, threshold=threshold)

    scores = bundle.score(test_set.features)
    return {
        "name": name,
        "description": description,
        "parameters": int(
            sum(layer.weight.size + layer.bias.size for layer in bundle.layers)
        ),
        **_metrics(test_set.labels, test_set.severities, scores, bundle.threshold),
    }


def run(machine: MachineSpec = DEFAULT_MACHINE, seed: int = 20260819) -> dict[str, Any]:
    splits = build(machine, seed=seed, collect_windows=True)
    stages = [
        _run_v1(splits, seed),
        _run_feature_stage(
            "v2_features",
            "26 diagnostic features, healthy-only training, plain MSE score",
            splits,
            TrainConfig(latent_dim=4, seed=seed),
            residual_norm=False,
        ),
        _run_feature_stage(
            "v3_residual_norm",
            "+ residual normalisation against the healthy reconstruction error",
            splits,
            TrainConfig(latent_dim=4, seed=seed),
            residual_norm=True,
        ),
        _run_feature_stage(
            "v4_latent6",
            "+ latent width 6, selected on the development split (shipped model)",
            splits,
            TrainConfig(latent_dim=6, seed=seed),
            residual_norm=True,
        ),
    ]
    return {
        "generated_utc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "note": (
            "Each stage is trained and thresholded with the same policy; only the "
            "listed change differs. v1 reproduces the original project's design."
        ),
        "stages": stages,
    }


def save(report: dict[str, Any], path: str | Path = "artifacts/ablation.json") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=1), encoding="utf-8")
    return path


def to_markdown(report: dict[str, Any]) -> str:
    header = (
        "| Stage | ROC-AUC | PR-AUC | Recall | Incipient recall | False alarms |\n"
        "| --- | ---: | ---: | ---: | ---: | ---: |\n"
    )
    rows = [
        f"| `{s['name']}` | {s['roc_auc']:.3f} | {s['pr_auc']:.3f} | {s['recall']:.3f} | "
        f"{s['recall_incipient']:.3f} | {s['false_alarm_rate']:.3f} |"
        for s in report["stages"]
    ]
    return header + "\n".join(rows) + "\n"
