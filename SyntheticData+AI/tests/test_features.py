"""Feature extraction: correctness on signals whose answer is known in advance."""

from __future__ import annotations

import numpy as np
import pytest

from vfactory.config import DEFAULT_MACHINE
from vfactory.features import (
    FEATURE_NAMES,
    N_FEATURES,
    amplitude_spectrum,
    describe,
    extract,
    extract_batch,
    velocity_rms_mm_s,
)
from vfactory.simulator import FaultSpec, VibrationSimulator


def test_feature_names_are_unique_and_sized():
    assert len(FEATURE_NAMES) == N_FEATURES
    assert len(set(FEATURE_NAMES)) == N_FEATURES


def test_amplitude_spectrum_recovers_a_known_sine():
    fs = DEFAULT_MACHINE.sample_rate_hz
    n = DEFAULT_MACHINE.window_size
    t = np.arange(n) / fs
    signal = 2.5 * np.sin(2 * np.pi * 300.0 * t)

    freqs, amp = amplitude_spectrum(signal, fs)
    peak = int(np.argmax(amp))
    assert freqs[peak] == pytest.approx(300.0, abs=DEFAULT_MACHINE.freq_resolution_hz)
    assert amp[peak] == pytest.approx(2.5, rel=0.05)


def test_time_features_on_an_analytic_sine():
    fs = DEFAULT_MACHINE.sample_rate_hz
    t = np.arange(DEFAULT_MACHINE.window_size) / fs
    signal = np.sin(2 * np.pi * 100.0 * t)
    values = describe(extract(signal, DEFAULT_MACHINE))

    assert values["rms"] == pytest.approx(1 / np.sqrt(2), rel=0.01)
    assert values["crest_factor"] == pytest.approx(np.sqrt(2), rel=0.02)
    # A pure sine has kurtosis 1.5, well below the Gaussian value of 3.
    assert values["kurtosis"] == pytest.approx(1.5, rel=0.02)


def test_velocity_conversion_matches_the_closed_form():
    """For a single sine, v_rms = a_rms * g / omega."""
    fs = DEFAULT_MACHINE.sample_rate_hz
    freq = 50.0
    t = np.arange(DEFAULT_MACHINE.window_size) / fs
    signal = 1.0 * np.sin(2 * np.pi * freq * t)  # 1 g peak

    expected = (1.0 / np.sqrt(2)) * 9.80665 * 1000.0 / (2 * np.pi * freq)
    assert velocity_rms_mm_s(signal, fs) == pytest.approx(expected, rel=0.03)


def test_extraction_is_finite_for_every_fault_mode():
    sim = VibrationSimulator(seed=17)
    for mode in ("healthy", "outer_race", "inner_race", "ball", "imbalance", "looseness"):
        values = extract(sim.window(FaultSpec(mode, 0.6)), DEFAULT_MACHINE)
        assert values.shape == (N_FEATURES,)
        assert np.isfinite(values).all(), mode


def test_extraction_survives_a_silent_sensor():
    """A dead channel must not produce NaN and poison everything downstream."""
    values = extract(np.zeros(DEFAULT_MACHINE.window_size), DEFAULT_MACHINE)
    assert np.isfinite(values).all()


def test_envelope_features_are_specific_to_the_fault():
    """BPFO rises for an outer-race defect and stays flat for an inner-race one."""
    sim = VibrationSimulator(seed=23)
    healthy = describe(extract(sim.window(FaultSpec("healthy", 0.0)), DEFAULT_MACHINE))
    outer = describe(extract(sim.window(FaultSpec("outer_race", 0.8)), DEFAULT_MACHINE))
    inner = describe(extract(sim.window(FaultSpec("inner_race", 0.8)), DEFAULT_MACHINE))

    assert outer["env_bpfo_db"] > healthy["env_bpfo_db"] + 12
    assert inner["env_bpfi_db"] > healthy["env_bpfi_db"] + 12
    assert outer["env_bpfi_db"] < outer["env_bpfo_db"] - 10
    assert inner["env_bpfo_db"] < inner["env_bpfi_db"] - 10


def test_batch_matches_row_by_row_extraction():
    sim = VibrationSimulator(seed=31)
    windows = sim.batch(FaultSpec("ball", 0.4), 3)
    batch = extract_batch(windows, DEFAULT_MACHINE)
    assert batch.shape == (3, N_FEATURES)
    for i, window in enumerate(windows):
        np.testing.assert_allclose(batch[i], extract(window, DEFAULT_MACHINE))
