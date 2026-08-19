"""Feature extraction: turn a raw acceleration window into a diagnostic vector.

An autoencoder over a *single scalar* sample (what the original project did)
cannot learn anything -- a 1-to-4-to-1 network trivially learns the identity
and its reconstruction error carries no information about machine health.
The signal only becomes separable once each window is condensed into the
features a vibration analyst would actually look at:

* **time domain** -- RMS, peak, crest, kurtosis and the other shape factors
  that react to impulsiveness;
* **frequency domain** -- band energies, spectral centroid/spread/entropy;
* **envelope domain** -- amplitude demodulation around the structural
  resonance, read at the bearing's geometric defect frequencies. This is the
  standard way a localised bearing defect is detected, and it is what lets the
  model distinguish an outer-race spall from plain imbalance.

Everything is NumPy-only so the same code can run inside a request handler
without dragging a training stack into production.
"""

from __future__ import annotations

import numpy as np

from .config import (
    DEFAULT_MACHINE,
    ENVELOPE_BAND_HZ,
    SPECTRAL_BANDS,
    MachineSpec,
)

_EPS = 1e-12

#: Equivalent noise bandwidth of a Hann window, in bins. A tapered window
#: smears a tone across about three bins, so summing power across a band
#: over-counts it by this factor unless it is divided back out. Amplitude
#: readings of a single peak are unaffected -- only band power needs it.
_HANN_ENBW = 1.5

TIME_FEATURES: tuple[str, ...] = (
    "rms",
    "peak",
    "peak_to_peak",
    "crest_factor",
    "kurtosis",
    "skewness",
    "shape_factor",
    "impulse_factor",
    "clearance_factor",
    "zero_crossing_rate",
)

SPECTRAL_FEATURES: tuple[str, ...] = (
    *(f"band_{int(lo)}_{int(hi)}_db" for lo, hi in SPECTRAL_BANDS),
    "spectral_centroid",
    "spectral_spread",
    "spectral_entropy",
)

#: Envelope-spectrum probes, as (feature name, defect key, harmonic).
ENVELOPE_PROBES: tuple[tuple[str, str, int], ...] = (
    ("env_shaft_1x_db", "shaft", 1),
    ("env_bpfo_db", "bpfo", 1),
    ("env_bpfo_h2_db", "bpfo", 2),
    ("env_bpfi_db", "bpfi", 1),
    ("env_bpfi_h2_db", "bpfi", 2),
    ("env_bsf_db", "bsf", 1),
    ("env_ftf_db", "ftf", 1),
)

ENVELOPE_FEATURES: tuple[str, ...] = tuple(name for name, _, _ in ENVELOPE_PROBES)

FEATURE_NAMES: tuple[str, ...] = TIME_FEATURES + SPECTRAL_FEATURES + ENVELOPE_FEATURES
N_FEATURES = len(FEATURE_NAMES)


# --------------------------------------------------------------------------- #
# Spectral helpers (also used by the API to draw charts)
# --------------------------------------------------------------------------- #


def amplitude_spectrum(
    window: np.ndarray, sample_rate_hz: float
) -> tuple[np.ndarray, np.ndarray]:
    """Single-sided amplitude spectrum of a Hann-windowed signal."""
    n = window.shape[-1]
    taper = np.hanning(n)
    # Coherent gain of a Hann window is 0.5; correct so peak heights are right.
    scaled = (window - window.mean(axis=-1, keepdims=True)) * taper
    spec = np.fft.rfft(scaled, axis=-1)
    amp = 2.0 * np.abs(spec) / (n * 0.5)
    freqs = np.fft.rfftfreq(n, 1.0 / sample_rate_hz)
    return freqs, amp


def envelope(window: np.ndarray, sample_rate_hz: float, band_hz: tuple[float, float]) -> np.ndarray:
    """Hilbert envelope of the signal band-passed around the resonance.

    Band-passing first is what makes envelope analysis work: the resonance
    carries the impact energy at a high signal-to-noise ratio, while the large
    low-frequency shaft components that would otherwise dominate are removed.
    """
    n = window.shape[-1]
    spec = np.fft.fft(window - window.mean(axis=-1, keepdims=True), axis=-1)
    freqs = np.fft.fftfreq(n, 1.0 / sample_rate_hz)

    lo, hi = band_hz
    keep = (np.abs(freqs) >= lo) & (np.abs(freqs) <= hi)
    spec = spec * keep

    # Analytic signal: zero the negative frequencies, double the positive ones.
    analytic_gain = np.zeros(n)
    analytic_gain[0] = 1.0
    if n % 2 == 0:
        analytic_gain[n // 2] = 1.0
        analytic_gain[1 : n // 2] = 2.0
    else:
        analytic_gain[1 : (n + 1) // 2] = 2.0

    return np.abs(np.fft.ifft(spec * analytic_gain, axis=-1))


def envelope_spectrum(
    window: np.ndarray,
    sample_rate_hz: float,
    band_hz: tuple[float, float] = ENVELOPE_BAND_HZ,
) -> tuple[np.ndarray, np.ndarray]:
    """Spectrum of the envelope -- where bearing defect lines appear."""
    env = envelope(window, sample_rate_hz, band_hz)
    return amplitude_spectrum(env, sample_rate_hz)


def velocity_rms_mm_s(
    window: np.ndarray, sample_rate_hz: float, band_hz: tuple[float, float] = (10.0, 1_000.0)
) -> float:
    """RMS velocity over the ISO 20816 band, converted from acceleration in g."""
    freqs, amp = amplitude_spectrum(window, sample_rate_hz)
    lo, hi = band_hz
    keep = (freqs >= lo) & (freqs <= hi)
    if not keep.any():
        return 0.0
    # a[g] -> a[m/s^2] -> v[m/s] by dividing by omega -> v[mm/s].
    vel_amp = amp[keep] * 9.80665 * 1000.0 / (2.0 * np.pi * freqs[keep])
    power = np.sum((vel_amp / np.sqrt(2.0)) ** 2) / _HANN_ENBW
    return float(np.sqrt(power))


def _peak_near(
    freqs: np.ndarray, values: np.ndarray, target_hz: float, tolerance_hz: float
) -> float:
    """Largest value within +/- tolerance of a target frequency."""
    keep = np.abs(freqs - target_hz) <= tolerance_hz
    return float(values[keep].max()) if keep.any() else 0.0


# --------------------------------------------------------------------------- #
# Feature extraction
# --------------------------------------------------------------------------- #


def _time_features(window: np.ndarray) -> list[float]:
    centred = window - window.mean()
    rms = float(np.sqrt(np.mean(window**2)))
    peak = float(np.max(np.abs(window)))
    p2p = float(window.max() - window.min())
    abs_mean = float(np.mean(np.abs(window))) + _EPS
    sqrt_mean = float(np.mean(np.sqrt(np.abs(window)))) ** 2 + _EPS
    std = float(centred.std()) + _EPS

    return [
        rms,
        peak,
        p2p,
        peak / (rms + _EPS),                       # crest factor
        float(np.mean(centred**4) / std**4),       # kurtosis
        float(np.mean(centred**3) / std**3),       # skewness
        rms / abs_mean,                            # shape factor
        peak / abs_mean,                           # impulse factor
        peak / sqrt_mean,                          # clearance factor
        float(np.mean(np.abs(np.diff(np.signbit(window))))),  # zero-crossing rate
    ]


def _spectral_features(freqs: np.ndarray, amp: np.ndarray) -> list[float]:
    power = amp**2
    total = float(power.sum()) + _EPS

    band_energies = []
    for lo, hi in SPECTRAL_BANDS:
        keep = (freqs >= lo) & (freqs < hi)
        band_energies.append(10.0 * np.log10(float(power[keep].sum()) / total + _EPS))

    centroid = float((freqs * power).sum() / total)
    spread = float(np.sqrt(((freqs - centroid) ** 2 * power).sum() / total))
    p = power / total
    entropy = float(-(p * np.log2(p + _EPS)).sum() / np.log2(len(p)))

    return [*band_energies, centroid, spread, entropy]


def _envelope_features(
    freqs: np.ndarray, amp: np.ndarray, defect_hz: dict[str, float], tolerance_hz: float
) -> list[float]:
    """Prominence of each defect line above the envelope noise floor, in dB.

    Using a ratio against the local median rather than a raw amplitude keeps
    the feature meaningful when the overall vibration level changes -- which is
    what separates "a defect line grew" from "the whole machine got louder".
    """
    floor = float(np.median(amp)) + _EPS
    out = []
    for _, key, harmonic in ENVELOPE_PROBES:
        target = defect_hz[key] * harmonic
        peak = _peak_near(freqs, amp, target, tolerance_hz)
        out.append(20.0 * np.log10(peak / floor + _EPS))
    return out


def extract(
    window: np.ndarray,
    machine: MachineSpec = DEFAULT_MACHINE,
    shaft_rpm: float | None = None,
) -> np.ndarray:
    """Condense one acceleration window into the diagnostic feature vector."""
    window = np.asarray(window, dtype=np.float64).ravel()
    rpm = shaft_rpm if shaft_rpm else machine.shaft_rpm

    freqs, amp = amplitude_spectrum(window, machine.sample_rate_hz)
    env_freqs, env_amp = envelope_spectrum(window, machine.sample_rate_hz)

    defect_hz = machine.bearing.defect_frequencies(rpm)
    defect_hz["shaft"] = rpm / 60.0
    # Slip and speed drift smear the defect lines; allow two FFT bins either way.
    tolerance = 2.0 * machine.sample_rate_hz / window.size

    values = (
        _time_features(window)
        + _spectral_features(freqs, amp)
        + _envelope_features(env_freqs, env_amp, defect_hz, tolerance)
    )
    return np.asarray(values, dtype=np.float64)


def extract_batch(
    windows: np.ndarray,
    machine: MachineSpec = DEFAULT_MACHINE,
    shaft_rpm: float | None = None,
) -> np.ndarray:
    """Feature matrix for a stack of windows, shape ``(n_windows, N_FEATURES)``."""
    return np.stack([extract(w, machine, shaft_rpm) for w in np.atleast_2d(windows)])


def describe(values: np.ndarray) -> dict[str, float]:
    """Pair a feature vector with its names, for logging and API responses."""
    return {name: float(v) for name, v in zip(FEATURE_NAMES, values, strict=True)}
