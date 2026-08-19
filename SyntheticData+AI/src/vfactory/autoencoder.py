"""Portable autoencoder: a JSON weight bundle plus a NumPy forward pass.

Training happens in PyTorch (see :mod:`vfactory.train`), but nothing at serving
time needs an autograd engine. Exporting the fitted weights to plain JSON and
running the forward pass in NumPy means:

* the deployed API installs ``numpy`` instead of a ~900 MB deep-learning stack,
  so a free-tier container cold-starts in seconds rather than minutes;
* the exact same weights can be shipped to the browser and evaluated in
  TypeScript, which is how the static demo works with no backend at all;
* the artifact is a readable, diffable, version-controllable text file rather
  than a pickle -- ``torch.load`` on an untrusted ``.pth`` executes arbitrary
  code, which the original project did without ``weights_only``.

A round-trip test asserts the NumPy and PyTorch outputs agree, so the two
implementations cannot silently drift apart.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np

SCHEMA_VERSION = 1

Activation = Literal["relu", "linear"]


def _apply(x: np.ndarray, activation: Activation) -> np.ndarray:
    if activation == "relu":
        return np.maximum(x, 0.0)
    if activation == "linear":
        return x
    raise ValueError(f"unsupported activation {activation!r}")


@dataclass(frozen=True)
class Layer:
    """A dense layer stored row-major as ``(out_features, in_features)``."""

    weight: np.ndarray
    bias: np.ndarray
    activation: Activation

    def forward(self, x: np.ndarray) -> np.ndarray:
        return _apply(x @ self.weight.T + self.bias, self.activation)

    def to_json(self) -> dict[str, Any]:
        return {
            "weight": self.weight.tolist(),
            "bias": self.bias.tolist(),
            "activation": self.activation,
        }

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> Layer:
        return cls(
            weight=np.asarray(payload["weight"], dtype=np.float64),
            bias=np.asarray(payload["bias"], dtype=np.float64),
            activation=payload["activation"],
        )


@dataclass(frozen=True)
class AutoencoderBundle:
    """Everything needed to score a feature vector: scaler, weights, threshold."""

    feature_names: tuple[str, ...]
    mean: np.ndarray
    scale: np.ndarray
    layers: tuple[Layer, ...]
    threshold: float
    metadata: dict[str, Any]
    #: Per-feature RMS reconstruction residual on healthy training data.
    #: Dividing by it before squaring turns the score into a Mahalanobis-like
    #: distance: features the network already reconstructs well (the structured
    #: ones) dominate the score, while features that are irreducible noise even
    #: on a healthy machine stop diluting it. Without this the mean-squared
    #: error over 26 features buries a defect signature under 25 noisy ones.
    residual_scale: np.ndarray | None = None

    # ---------------------------------------------------------------- #
    # Scoring
    # ---------------------------------------------------------------- #

    @property
    def n_features(self) -> int:
        return len(self.feature_names)

    @property
    def latent_dim(self) -> int:
        return int(min(layer.bias.shape[0] for layer in self.layers))

    @property
    def architecture(self) -> list[int]:
        return [self.n_features] + [int(layer.bias.shape[0]) for layer in self.layers]

    def standardise(self, features: np.ndarray) -> np.ndarray:
        return (np.atleast_2d(features) - self.mean) / self.scale

    def reconstruct(self, scaled: np.ndarray) -> np.ndarray:
        out = np.atleast_2d(scaled)
        for layer in self.layers:
            out = layer.forward(out)
        return out

    def residuals(self, features: np.ndarray) -> np.ndarray:
        """Signed reconstruction residual per feature, in standardised units."""
        scaled = self.standardise(features)
        return self.reconstruct(scaled) - scaled

    def errors(self, features: np.ndarray) -> np.ndarray:
        """Per-feature squared reconstruction error, residual-normalised."""
        residual = self.residuals(features)
        if self.residual_scale is not None:
            residual = residual / self.residual_scale
        return residual**2

    def score(self, features: np.ndarray) -> np.ndarray:
        """Mean squared reconstruction error per row -- the anomaly score."""
        return self.errors(features).mean(axis=1)

    def score_one(self, features: np.ndarray) -> float:
        return float(self.score(features)[0])

    def health_index(self, score: float) -> float:
        """Score mapped onto a 0-100 health scale, 50 exactly at the threshold.

        The exponent bends the curve so a nominal machine -- whose score sits
        around a third of the threshold -- reads in the high eighties rather
        than the low seventies, while a score several times over the threshold
        still collapses to zero. A dashboard that shows 70/100 for a perfectly
        healthy motor trains operators to ignore it.
        """
        if self.threshold <= 0.0:
            return 0.0
        ratio = max(score, 1e-12) / self.threshold
        return float(np.clip(100.0 * 2.0 ** (-(ratio**1.6)), 0.0, 100.0))

    def top_contributors(self, features: np.ndarray, k: int = 3) -> list[tuple[str, float]]:
        """Which features the model failed hardest to reconstruct, and by how much.

        A one-class model can only say "this is not normal". Attributing the
        error back to named features is what turns that into something an
        operator can act on.
        """
        per_feature = self.errors(features)[0]
        total = float(per_feature.sum()) or 1.0
        order = np.argsort(per_feature)[::-1][:k]
        return [(self.feature_names[i], float(per_feature[i] / total)) for i in order]

    # ---------------------------------------------------------------- #
    # Serialisation
    # ---------------------------------------------------------------- #

    def to_json(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "feature_names": list(self.feature_names),
            "scaler": {"mean": self.mean.tolist(), "scale": self.scale.tolist()},
            "layers": [layer.to_json() for layer in self.layers],
            "residual_scale": (
                None if self.residual_scale is None else self.residual_scale.tolist()
            ),
            "threshold": self.threshold,
            "metadata": self.metadata,
        }

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_json(), indent=1), encoding="utf-8")
        return path

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> AutoencoderBundle:
        version = payload.get("schema_version")
        if version != SCHEMA_VERSION:
            raise ValueError(
                f"model bundle schema {version} is not supported "
                f"(this build reads schema {SCHEMA_VERSION})"
            )
        scaler = payload["scaler"]
        residual_scale = payload.get("residual_scale")
        return cls(
            feature_names=tuple(payload["feature_names"]),
            mean=np.asarray(scaler["mean"], dtype=np.float64),
            scale=np.asarray(scaler["scale"], dtype=np.float64),
            layers=tuple(Layer.from_json(item) for item in payload["layers"]),
            threshold=float(payload["threshold"]),
            metadata=dict(payload.get("metadata", {})),
            residual_scale=(
                None if residual_scale is None else np.asarray(residual_scale, dtype=np.float64)
            ),
        )

    @classmethod
    def load(cls, path: str | Path) -> AutoencoderBundle:
        return cls.from_json(json.loads(Path(path).read_text(encoding="utf-8")))
