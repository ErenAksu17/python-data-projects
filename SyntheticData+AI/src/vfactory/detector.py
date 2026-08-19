"""Turn a raw window into an operator-facing verdict.

The autoencoder is a one-class model: it can only say *this does not look like
a healthy machine*. That alone is not actionable, so this module adds two
explanation layers on top of the score:

* **attribution** -- which features the network failed hardest to reconstruct,
  read straight off the model;
* **diagnosis** -- a small, explicit rule set over the standardised features
  that names the likely mechanical cause. The rules are ordinary vibration
  analysis (an elevated BPFO envelope line means an outer-race defect), stated
  in code rather than hidden in a black box.

The division of labour is deliberate: the model decides *whether* something is
wrong, the rules explain *what*, and every rule that fired is reported so the
verdict can be argued with.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .autoencoder import AutoencoderBundle
from .config import DEFAULT_MACHINE, MachineSpec, iso_zone
from .features import FEATURE_NAMES, extract, velocity_rms_mm_s

#: How many healthy standard deviations a defect line must rise before the
#: rule set is willing to name it.
DEFECT_Z_THRESHOLD = 3.5

_HUMAN_LABELS: dict[str, str] = {
    "healthy": "No fault signature",
    "outer_race": "Bearing outer-race defect",
    "inner_race": "Bearing inner-race defect",
    "ball": "Rolling-element (ball) defect",
    "imbalance": "Rotor imbalance",
    "looseness": "Mechanical looseness",
    "unknown": "Unclassified anomaly",
}


@dataclass(frozen=True)
class Verdict:
    """Everything the dashboard needs to render one window."""

    score: float
    threshold: float
    is_anomaly: bool
    health_index: float
    status: str                      # normal | watch | warning | critical
    diagnosis: str                   # fault-mode key
    diagnosis_label: str
    confidence: float
    evidence: list[str] = field(default_factory=list)
    contributors: list[dict[str, float | str]] = field(default_factory=list)
    velocity_rms_mm_s: float = 0.0
    iso_zone: str = "A"

    def to_json(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "threshold": self.threshold,
            "is_anomaly": self.is_anomaly,
            "health_index": self.health_index,
            "status": self.status,
            "diagnosis": self.diagnosis,
            "diagnosis_label": self.diagnosis_label,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "contributors": self.contributors,
            "velocity_rms_mm_s": self.velocity_rms_mm_s,
            "iso_zone": self.iso_zone,
        }


#: Fraction of the alarm threshold at which a window is worth watching.
#: The threshold itself is a 99.5th percentile of healthy scores, and healthy
#: scores reach ~0.6x of it routinely -- so a "watch" band set much lower than
#: this fires on perfectly good machines and teaches operators to ignore it.
WATCH_RATIO = 0.85
CRITICAL_RATIO = 4.0


def _status(score: float, threshold: float) -> str:
    ratio = score / threshold if threshold > 0 else 0.0
    if ratio >= CRITICAL_RATIO:
        return "critical"
    if ratio >= 1.0:
        return "warning"
    if ratio >= WATCH_RATIO:
        return "watch"
    return "normal"


def _diagnose(z: dict[str, float]) -> tuple[str, float, list[str]]:
    """Name the most likely mechanical cause from standardised features."""
    evidence: list[str] = []

    # Bearing defects announce themselves as a raised envelope line at the
    # geometric defect frequency. Whichever line rises most, wins.
    bearing_probes = {
        "outer_race": max(z["env_bpfo_db"], z["env_bpfo_h2_db"]),
        "inner_race": max(z["env_bpfi_db"], z["env_bpfi_h2_db"]),
        "ball": max(z["env_bsf_db"], z["env_ftf_db"]),
    }
    best_bearing, best_z = max(bearing_probes.items(), key=lambda kv: kv[1])

    # Distributed faults move energy to low frequencies and raise overall level
    # without making the signal impulsive -- kurtosis stays low or drops.
    low_freq_lift = max(z["band_0_200_db"], z["band_200_600_db"])
    impulsive = z["kurtosis"]

    if best_z >= DEFECT_Z_THRESHOLD and best_z >= low_freq_lift:
        probe = {"outer_race": "BPFO", "inner_race": "BPFI", "ball": "BSF"}[best_bearing]
        evidence.append(
            f"{probe} envelope line is {best_z:.1f} sigma above the healthy baseline"
        )
        if impulsive > 2.0:
            evidence.append(f"waveform is impulsive (kurtosis {impulsive:+.1f} sigma)")
        # Confidence blends two things: how far the line rose at all, and how
        # clearly it beat the next candidate. Margin alone under-rates an
        # obvious defect whose harmonics also lift the neighbouring probes.
        runner_up = sorted(bearing_probes.values())[-2]
        margin = best_z - max(runner_up, DEFECT_Z_THRESHOLD)
        strength = np.clip((best_z - DEFECT_Z_THRESHOLD) / 8.0, 0.0, 1.0)
        separation = np.clip(margin / 5.0, 0.0, 1.0)
        confidence = 0.35 + 0.64 * float(0.5 * strength + 0.5 * separation)
        return best_bearing, round(confidence, 3), evidence

    if low_freq_lift >= 2.5:
        one_x = z["env_shaft_1x_db"]
        harmonics = z["band_200_600_db"]
        if harmonics > z["band_0_200_db"] or (z["rms"] > 3.0 and impulsive > -1.0):
            evidence.append(
                f"shaft-harmonic band lifted {harmonics:.1f} sigma with a low crest factor"
            )
            cause = "looseness"
        else:
            evidence.append(f"1x running-speed component up {max(one_x, low_freq_lift):.1f} sigma")
            cause = "imbalance"
        evidence.append(f"overall level {z['rms']:+.1f} sigma, kurtosis {impulsive:+.1f} sigma")
        return cause, float(np.clip(low_freq_lift / 8.0, 0.35, 0.95)), evidence

    return "unknown", 0.3, evidence


def analyse(
    window: np.ndarray,
    bundle: AutoencoderBundle,
    machine: MachineSpec = DEFAULT_MACHINE,
    shaft_rpm: float | None = None,
) -> tuple[Verdict, np.ndarray]:
    """Score one acceleration window and explain the result.

    Returns the verdict and the extracted feature vector, so callers that also
    want to chart the features do not pay for extraction twice.
    """
    features = extract(window, machine, shaft_rpm=shaft_rpm)
    return analyse_features(features, bundle, window, machine), features


def analyse_features(
    features: np.ndarray,
    bundle: AutoencoderBundle,
    window: np.ndarray | None = None,
    machine: MachineSpec = DEFAULT_MACHINE,
) -> Verdict:
    """Score an already-extracted feature vector."""
    score = bundle.score_one(features)
    is_anomaly = score > bundle.threshold

    # Standardised against the healthy training distribution, so "3.5" really
    # means "three and a half healthy standard deviations".
    z_values = (features - bundle.mean) / bundle.scale
    z = dict(zip(FEATURE_NAMES, z_values, strict=True))

    if is_anomaly:
        diagnosis, confidence, evidence = _diagnose(z)
    else:
        diagnosis, confidence, evidence = "healthy", 0.0, []

    velocity = (
        velocity_rms_mm_s(window, machine.sample_rate_hz) if window is not None else 0.0
    )

    return Verdict(
        score=score,
        threshold=bundle.threshold,
        is_anomaly=is_anomaly,
        health_index=bundle.health_index(score),
        status=_status(score, bundle.threshold),
        diagnosis=diagnosis,
        diagnosis_label=_HUMAN_LABELS.get(diagnosis, _HUMAN_LABELS["unknown"]),
        confidence=confidence,
        evidence=evidence,
        contributors=[
            {"feature": name, "share": share}
            for name, share in bundle.top_contributors(features, k=4)
        ],
        velocity_rms_mm_s=velocity,
        iso_zone=iso_zone(velocity),
    )
