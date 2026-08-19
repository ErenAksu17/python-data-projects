"""Dataset construction for one-class anomaly detection.

The split is deliberately strict, because the original project got this wrong
in two ways that quietly inflate any metric you report:

1. it fitted the scaler on the *whole* dataset, faults included, so
   normalisation statistics leaked the anomalies into the model;
2. it picked the detection threshold from ``df[df.anomaly == 0]`` *at
   inference time* -- reading the ground-truth labels of the very rows it was
   about to score.

Here the training set is healthy-only, the threshold comes from a healthy
validation split the model never trained on, and labels are used exclusively
in the final evaluation. Healthy data also spans the machine's normal
operating envelope (speed and load vary), so ordinary process variation is
learned as normal rather than flagged as a fault.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import DEFAULT_MACHINE, MachineSpec
from .features import extract, velocity_rms_mm_s
from .simulator import FaultSpec, VibrationSimulator

#: Normal operating envelope of a healthy machine.
HEALTHY_RPM_RANGE: tuple[float, float] = (1_740.0, 1_860.0)
HEALTHY_LOAD_RANGE: tuple[float, float] = (0.7, 1.3)

#: Fault modes and the severity range each is sampled over in the test set.
#: The low end is deliberately subtle -- catching an incipient defect is the
#: whole point of condition monitoring.
TEST_FAULTS: tuple[tuple[str, tuple[float, float]], ...] = (
    ("outer_race", (0.10, 1.0)),
    ("inner_race", (0.10, 1.0)),
    ("ball", (0.15, 1.0)),
    ("imbalance", (0.15, 1.0)),
    ("looseness", (0.15, 1.0)),
)


@dataclass(frozen=True)
class Dataset:
    """A feature matrix with labels and provenance for every row."""

    features: np.ndarray          # (n, N_FEATURES)
    labels: np.ndarray            # (n,) 0 = healthy, 1 = faulty
    modes: np.ndarray             # (n,) fault mode name
    severities: np.ndarray        # (n,) 0..1
    #: ISO 20816 RMS velocity per window. Not a model feature -- carried so the
    #: benchmark can score the industry-standard overall-level rule too.
    velocity: np.ndarray = None  # type: ignore[assignment]
    #: Raw acceleration windows, kept only when ``collect_windows=True``. The
    #: ablation study needs them to feed the original sample-level pipeline the
    #: exact same signals the feature pipeline sees.
    windows: np.ndarray | None = None

    def __len__(self) -> int:
        return int(self.features.shape[0])

    @property
    def n_faulty(self) -> int:
        return int(self.labels.sum())

    def subset(self, mask: np.ndarray) -> Dataset:
        return Dataset(
            self.features[mask],
            self.labels[mask],
            self.modes[mask],
            self.severities[mask],
            self.velocity[mask],
            None if self.windows is None else self.windows[mask],
        )


def _sample_windows(
    sim: VibrationSimulator,
    rng: np.random.Generator,
    mode: str,
    n: int,
    severity_range: tuple[float, float],
    machine: MachineSpec,
    collect_windows: bool = False,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray | None]:
    feats, modes, sevs, vels = [], [], [], []
    windows: list[np.ndarray] = []
    t = 0.0
    for _ in range(n):
        rpm = float(rng.uniform(*HEALTHY_RPM_RANGE))
        load = float(rng.uniform(*HEALTHY_LOAD_RANGE))
        severity = float(rng.uniform(*severity_range))
        fault = FaultSpec(mode=mode, severity=severity, shaft_rpm=rpm, load=load)
        window = sim.window(fault, t0=t)
        t += machine.window_seconds
        feats.append(extract(window, machine, shaft_rpm=rpm))
        vels.append(velocity_rms_mm_s(window, machine.sample_rate_hz))
        modes.append(mode)
        sevs.append(severity)
        if collect_windows:
            windows.append(window)
    return (
        np.stack(feats),
        np.asarray(modes),
        np.asarray(sevs),
        np.asarray(vels),
        np.stack(windows) if collect_windows else None,
    )


#: Offset applied to the dataset seed to produce the development split used
#: for model selection. Keeping it separate from the reported test split is
#: what stops "we tried eight latent sizes" from turning into a leaked metric.
DEV_SEED_OFFSET = 500


def build_dev(
    machine: MachineSpec = DEFAULT_MACHINE, seed: int = 20260819
) -> Dataset:
    """Labelled split for design decisions (latent size, scoring, thresholds)."""
    return build(machine, seed=seed + DEV_SEED_OFFSET)[2]


def build(
    machine: MachineSpec = DEFAULT_MACHINE,
    n_train: int = 1_200,
    n_val: int = 400,
    n_test_healthy: int = 400,
    n_test_per_fault: int = 160,
    seed: int = 20260819,
    collect_windows: bool = False,
) -> tuple[Dataset, Dataset, Dataset]:
    """Build the healthy-only train/validation split and the labelled test set.

    Each split gets its own simulator seed, so the test machine is a different
    physical realisation from the one the model was fitted on. Set
    ``collect_windows`` to also keep the raw signals (~46 MB) -- the ablation
    study needs them to score a pipeline that does not use features.
    """
    train_f, train_m, train_s, train_v, train_w = _sample_windows(
        VibrationSimulator(machine, seed=seed),
        np.random.default_rng(seed),
        "healthy",
        n_train,
        (0.0, 0.0),
        machine,
        collect_windows=collect_windows,
    )
    val_f, val_m, val_s, val_v, val_w = _sample_windows(
        VibrationSimulator(machine, seed=seed + 1),
        np.random.default_rng(seed + 1),
        "healthy",
        n_val,
        (0.0, 0.0),
        machine,
        collect_windows=collect_windows,
    )

    sim_test = VibrationSimulator(machine, seed=seed + 2)
    rng_test = np.random.default_rng(seed + 2)
    parts = [
        _sample_windows(
            sim_test,
            rng_test,
            "healthy",
            n_test_healthy,
            (0.0, 0.0),
            machine,
            collect_windows=collect_windows,
        )
    ]
    for mode, sev_range in TEST_FAULTS:
        parts.append(
            _sample_windows(
                sim_test,
                rng_test,
                mode,
                n_test_per_fault,
                sev_range,
                machine,
                collect_windows=collect_windows,
            )
        )

    test_f = np.concatenate([p[0] for p in parts])
    test_m = np.concatenate([p[1] for p in parts])
    test_s = np.concatenate([p[2] for p in parts])
    test_v = np.concatenate([p[3] for p in parts])
    test_w = np.concatenate([p[4] for p in parts]) if collect_windows else None
    test_labels = (test_m != "healthy").astype(np.int64)

    def zeros(n: int) -> np.ndarray:
        return np.zeros(n, dtype=np.int64)

    return (
        Dataset(train_f, zeros(len(train_f)), train_m, train_s, train_v, train_w),
        Dataset(val_f, zeros(len(val_f)), val_m, val_s, val_v, val_w),
        Dataset(test_f, test_labels, test_m, test_s, test_v, test_w),
    )
