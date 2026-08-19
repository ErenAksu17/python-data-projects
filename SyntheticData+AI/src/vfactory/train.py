"""Train the anomaly-detection autoencoder and export a portable bundle.

Training is one-class: the network only ever sees healthy windows, learns to
reconstruct them, and anything it cannot reconstruct is by definition unlike
normal operation. The detection threshold is read off a *healthy validation
split the network never trained on* -- never off the labelled test set.

PyTorch is a training-time dependency only; the result is written out as JSON
weights (see :mod:`vfactory.autoencoder`).
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np

from .autoencoder import AutoencoderBundle, Layer
from .config import DEFAULT_MACHINE, MachineSpec
from .dataset import Dataset, build
from .features import FEATURE_NAMES


@dataclass(frozen=True)
class TrainConfig:
    hidden_dims: tuple[int, ...] = (16, 8)
    #: Chosen on a labelled *development* split (dataset seed + 500), never on
    #: the reported test split. 4 under-fits the healthy manifold; 8 starts
    #: reconstructing faults too, which costs recall on incipient defects.
    latent_dim: int = 6
    epochs: int = 400
    batch_size: int = 64
    learning_rate: float = 2e-3
    weight_decay: float = 1e-5
    #: Denoising: corrupt the input, ask for the clean target. Stops the network
    #: from learning a near-identity map and makes the score more stable.
    input_noise: float = 0.06
    #: Stop when validation loss has not improved for this many epochs.
    patience: int = 40
    #: Quantile of the healthy validation scores used as the alarm threshold.
    #: 0.995 targets roughly one false alarm per 200 windows (~1 per minute).
    threshold_quantile: float = 0.995
    seed: int = 20260819


def _standardiser(train_features: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Mean/scale fitted on healthy training rows only -- no leakage."""
    mean = train_features.mean(axis=0)
    scale = train_features.std(axis=0)
    # A constant feature would divide by zero; keep it at zero variance instead.
    scale = np.where(scale < 1e-9, 1.0, scale)
    return mean, scale


def train(
    machine: MachineSpec = DEFAULT_MACHINE,
    config: TrainConfig | None = None,
    splits: tuple[Dataset, Dataset, Dataset] | None = None,
    verbose: bool = True,
) -> tuple[AutoencoderBundle, Dataset]:
    """Fit the autoencoder; return the exportable bundle and the test split."""
    import torch  # imported lazily: serving never needs it
    from torch import nn

    config = config or TrainConfig()
    torch.manual_seed(config.seed)

    train_set, val_set, test_set = splits or build(machine, seed=config.seed)
    mean, scale = _standardiser(train_set.features)

    x_train = torch.tensor((train_set.features - mean) / scale, dtype=torch.float32)
    x_val = torch.tensor((val_set.features - mean) / scale, dtype=torch.float32)

    n_features = x_train.shape[1]
    dims = [n_features, *config.hidden_dims, config.latent_dim, *reversed(config.hidden_dims), n_features]
    modules: list[nn.Module] = []
    for i in range(len(dims) - 1):
        modules.append(nn.Linear(dims[i], dims[i + 1]))
        if i < len(dims) - 2:  # linear output so the network can hit any value
            modules.append(nn.ReLU())
    model = nn.Sequential(*modules)

    optimiser = torch.optim.Adam(
        model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay
    )
    criterion = nn.MSELoss()
    generator = torch.Generator().manual_seed(config.seed)

    best_val = float("inf")
    best_state: dict[str, Any] | None = None
    epochs_without_gain = 0
    history: list[dict[str, float]] = []

    for epoch in range(config.epochs):
        model.train()
        order = torch.randperm(x_train.shape[0], generator=generator)
        epoch_loss = 0.0
        for start in range(0, x_train.shape[0], config.batch_size):
            batch = x_train[order[start : start + config.batch_size]]
            noisy = batch + config.input_noise * torch.randn(
                batch.shape, generator=generator
            )
            loss = criterion(model(noisy), batch)
            optimiser.zero_grad()
            loss.backward()
            optimiser.step()
            epoch_loss += loss.item() * batch.shape[0]
        epoch_loss /= x_train.shape[0]

        model.eval()
        with torch.no_grad():
            val_loss = criterion(model(x_val), x_val).item()
        history.append({"epoch": epoch + 1, "train_loss": epoch_loss, "val_loss": val_loss})

        if val_loss < best_val - 1e-6:
            best_val = val_loss
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            epochs_without_gain = 0
        else:
            epochs_without_gain += 1
            if epochs_without_gain >= config.patience:
                if verbose:
                    print(f"early stop at epoch {epoch + 1} (best val {best_val:.6f})")
                break

        if verbose and (epoch + 1) % 25 == 0:
            print(f"epoch {epoch + 1:3d}  train {epoch_loss:.6f}  val {val_loss:.6f}")

    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()

    # --- export to a framework-free bundle -------------------------------- #
    layers: list[Layer] = []
    linear_layers = [m for m in model if isinstance(m, nn.Linear)]
    for i, linear in enumerate(linear_layers):
        layers.append(
            Layer(
                weight=linear.weight.detach().numpy().astype(np.float64),
                bias=linear.bias.detach().numpy().astype(np.float64),
                activation="relu" if i < len(linear_layers) - 1 else "linear",
            )
        )

    provisional = AutoencoderBundle(
        feature_names=FEATURE_NAMES,
        mean=mean,
        scale=scale,
        layers=tuple(layers),
        threshold=1.0,
        metadata={},
    )

    # Residual scale is a *fitting* statistic, so it comes from the training
    # split; the threshold is an *operating point*, so it comes from the
    # untouched validation split. Keeping the two sources separate is what
    # stops the reported false-alarm rate from being optimistic.
    train_residuals = provisional.residuals(train_set.features)
    residual_scale = train_residuals.std(axis=0)
    residual_scale = np.where(residual_scale < 1e-9, 1.0, residual_scale)

    provisional = replace(provisional, residual_scale=residual_scale)
    val_scores = provisional.score(val_set.features)
    threshold = float(np.quantile(val_scores, config.threshold_quantile))

    metadata = {
        "created_utc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "framework": "pytorch (training) -> numpy (serving)",
        "architecture": provisional.architecture,
        "threshold_quantile": config.threshold_quantile,
        "train_windows": len(train_set),
        "val_windows": len(val_set),
        "best_val_loss": best_val,
        "epochs_run": len(history),
        "healthy_val_score_median": float(np.median(val_scores)),
        "healthy_val_score_p99": float(np.quantile(val_scores, 0.99)),
        "machine": {
            "sample_rate_hz": machine.sample_rate_hz,
            "window_size": machine.window_size,
            "shaft_rpm": machine.shaft_rpm,
            "resonance_hz": machine.resonance_hz,
            "bearing_orders": {
                k: round(v, 4) for k, v in machine.bearing.defect_orders().items()
            },
        },
        "config": asdict(config),
    }

    bundle = replace(provisional, threshold=threshold, metadata=metadata)

    if verbose:
        print(f"architecture {bundle.architecture}")
        print(f"threshold {threshold:.6f} (q={config.threshold_quantile})")

    return bundle, test_set


def train_and_save(
    model_path: str | Path = "artifacts/model.json",
    history_path: str | Path | None = None,
    machine: MachineSpec = DEFAULT_MACHINE,
    config: TrainConfig | None = None,
    verbose: bool = True,
) -> AutoencoderBundle:
    bundle, _ = train(machine=machine, config=config, verbose=verbose)
    path = bundle.save(model_path)
    if verbose:
        print(f"wrote {path} ({path.stat().st_size / 1024:.1f} KB)")
    if history_path:
        Path(history_path).write_text(
            json.dumps(bundle.metadata, indent=1), encoding="utf-8"
        )
    return bundle
