"""Competing detectors, wrapped in one interface so the comparison is fair.

Every method here is trained on exactly the same healthy-only feature matrix
and has its operating point fixed by exactly the same policy (a quantile of
its own scores on the healthy validation split). Without that discipline a
benchmark mostly measures whose threshold was tuned hardest.

The line-up spans what an equivalent project would realistically use:

* ``rms_3sigma`` -- the textbook overall-level rule, and effectively what the
  original version of this project was reaching for;
* ``iso_velocity`` -- the ISO 20816 zone-C alarm used across industry;
* ``pca`` -- linear reconstruction error at the same latent size as the
  autoencoder, which isolates how much the nonlinearity is actually worth;
* ``isolation_forest``, ``lof``, ``ocsvm`` -- the standard scikit-learn
  novelty detectors that most comparable repositories stop at.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import numpy as np


class Detector(Protocol):
    """Higher score = more anomalous."""

    name: str
    family: str

    def fit(self, healthy: np.ndarray) -> None: ...

    def score(self, features: np.ndarray) -> np.ndarray: ...


@dataclass
class _Standardiser:
    mean: np.ndarray | None = None
    scale: np.ndarray | None = None

    def fit(self, x: np.ndarray) -> None:
        self.mean = x.mean(axis=0)
        scale = x.std(axis=0)
        self.scale = np.where(scale < 1e-9, 1.0, scale)

    def __call__(self, x: np.ndarray) -> np.ndarray:
        return (np.atleast_2d(x) - self.mean) / self.scale


class RmsThreeSigma:
    """Flag when overall RMS leaves the healthy +/-3 sigma band.

    The simplest thing that could possibly work, and the honest baseline any
    "AI" solution has to beat before it earns its complexity.
    """

    name = "rms_3sigma"
    family = "rule"

    def __init__(self, rms_index: int) -> None:
        self._i = rms_index
        self._mean = 0.0
        self._std = 1.0

    def fit(self, healthy: np.ndarray) -> None:
        column = healthy[:, self._i]
        self._mean = float(column.mean())
        self._std = float(column.std()) or 1e-9

    def score(self, features: np.ndarray) -> np.ndarray:
        column = np.atleast_2d(features)[:, self._i]
        return np.abs(column - self._mean) / self._std


class IsoVelocityRule:
    """ISO 20816-3 overall-velocity alarm, scored as mm/s directly.

    Fitting is a no-op: the zone boundaries are set by the standard, not by
    the data. Included precisely because it is speed- and machine-agnostic --
    and because it is blind to high-frequency bearing defects, which is the
    single most useful thing this benchmark shows.
    """

    name = "iso_velocity"
    family = "rule"

    def __init__(self, velocity: Callable[[], np.ndarray] | None = None) -> None:
        self._velocity_lookup = velocity

    def fit(self, healthy: np.ndarray) -> None:
        return None

    def score(self, features: np.ndarray) -> np.ndarray:
        raise NotImplementedError("scored from precomputed velocities by the benchmark")


class PcaReconstruction:
    """Reconstruction error from a linear subspace of the healthy data."""

    name = "pca"
    family = "reconstruction"

    def __init__(self, n_components: int = 4) -> None:
        self.n_components = n_components
        self._scaler = _Standardiser()
        self._components: np.ndarray | None = None

    def fit(self, healthy: np.ndarray) -> None:
        self._scaler.fit(healthy)
        x = self._scaler(healthy)
        _, _, vt = np.linalg.svd(x, full_matrices=False)
        self._components = vt[: self.n_components]

    def score(self, features: np.ndarray) -> np.ndarray:
        x = self._scaler(features)
        projected = x @ self._components.T @ self._components
        return ((x - projected) ** 2).mean(axis=1)


class SklearnDetector:
    """Adapter for scikit-learn novelty detectors (sign-flipped to 'higher = worse')."""

    def __init__(self, name: str, factory: Callable[[], object]) -> None:
        self.name = name
        self.family = "sklearn"
        self._factory = factory
        self._model: object | None = None
        self._scaler = _Standardiser()

    def fit(self, healthy: np.ndarray) -> None:
        self._scaler.fit(healthy)
        self._model = self._factory()
        self._model.fit(self._scaler(healthy))  # type: ignore[attr-defined]

    def score(self, features: np.ndarray) -> np.ndarray:
        decision = self._model.decision_function(self._scaler(features))  # type: ignore[attr-defined]
        return -np.asarray(decision, dtype=np.float64)


def build_baselines(rms_index: int, latent_dim: int = 4, seed: int = 20260819) -> list[Detector]:
    """The comparison line-up, all unfitted."""
    from sklearn.ensemble import IsolationForest
    from sklearn.neighbors import LocalOutlierFactor
    from sklearn.svm import OneClassSVM

    return [
        RmsThreeSigma(rms_index),
        PcaReconstruction(n_components=latent_dim),
        SklearnDetector(
            "isolation_forest",
            lambda: IsolationForest(n_estimators=300, random_state=seed, contamination="auto"),
        ),
        SklearnDetector(
            "lof",
            lambda: LocalOutlierFactor(n_neighbors=25, novelty=True),
        ),
        SklearnDetector(
            "ocsvm",
            lambda: OneClassSVM(kernel="rbf", gamma="scale", nu=0.02),
        ),
    ]
