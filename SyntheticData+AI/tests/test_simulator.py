"""The simulator has to be physically right, or nothing downstream means anything."""

from __future__ import annotations

import numpy as np
import pytest

from vfactory.config import DEFAULT_MACHINE, BearingGeometry, iso_zone
from vfactory.features import envelope_spectrum, velocity_rms_mm_s
from vfactory.simulator import FaultSpec, Stream, VibrationSimulator


def test_bearing_orders_match_published_skf_6205_values():
    orders = BearingGeometry().defect_orders()
    assert orders["bpfo"] == pytest.approx(3.585, abs=0.002)
    assert orders["bpfi"] == pytest.approx(5.415, abs=0.002)
    assert orders["bsf"] == pytest.approx(2.357, abs=0.002)
    assert orders["ftf"] == pytest.approx(0.398, abs=0.002)


def test_defect_orders_sum_to_element_count():
    """BPFO + BPFI = number of rolling elements, for any geometry."""
    geometry = BearingGeometry(n_elements=12, element_diameter_mm=9.0, pitch_diameter_mm=48.0)
    assert geometry.bpfo_order + geometry.bpfi_order == pytest.approx(geometry.n_elements)


def test_same_seed_reproduces_the_signal():
    a = VibrationSimulator(seed=42).window(FaultSpec("outer_race", 0.5))
    b = VibrationSimulator(seed=42).window(FaultSpec("outer_race", 0.5))
    np.testing.assert_allclose(a, b)


def test_bearing_faults_are_impulsive_and_distributed_faults_are_not():
    sim = VibrationSimulator(seed=5)

    def kurtosis(mode: str, severity: float) -> float:
        w = sim.window(FaultSpec(mode, severity))
        c = w - w.mean()
        return float((c**4).mean() / (c**2).mean() ** 2)

    healthy = kurtosis("healthy", 0.0)
    assert 2.4 < healthy < 3.6, "healthy vibration should be near-Gaussian"
    assert kurtosis("outer_race", 0.7) > healthy + 2
    assert kurtosis("inner_race", 0.7) > healthy + 2
    # Imbalance is a growing sinusoid: kurtosis falls towards 1.5, it does not rise.
    assert kurtosis("imbalance", 0.7) < healthy


@pytest.mark.parametrize(
    ("mode", "probe"), [("outer_race", "bpfo"), ("inner_race", "bpfi")]
)
def test_defect_energy_lands_on_its_own_envelope_line(mode: str, probe: str):
    """An outer-race fault must show up at BPFO, not merely 'somewhere'."""
    sim = VibrationSimulator(seed=11)
    window = sim.window(FaultSpec(mode, 0.8))
    freqs, amp = envelope_spectrum(window, DEFAULT_MACHINE.sample_rate_hz)

    expected = DEFAULT_MACHINE.bearing.defect_frequencies(DEFAULT_MACHINE.shaft_rpm)[probe]
    band = freqs <= 500.0
    peak_hz = float(freqs[band][np.argmax(amp[band])])
    assert peak_hz == pytest.approx(expected, abs=3 * DEFAULT_MACHINE.freq_resolution_hz)


def test_severity_scale_is_calibrated_to_iso_zones():
    """Severity 0 sits in zone A; severity 1 imbalance reaches zone D."""
    sim = VibrationSimulator(seed=9)
    fs = DEFAULT_MACHINE.sample_rate_hz

    healthy = velocity_rms_mm_s(sim.window(FaultSpec("healthy", 0.0)), fs)
    severe = velocity_rms_mm_s(sim.window(FaultSpec("imbalance", 1.0)), fs)

    assert iso_zone(healthy) == "A"
    assert iso_zone(severe) == "D"
    assert severe > healthy * 4


def test_bearing_defects_hide_from_the_overall_velocity_rule():
    """The reason envelope analysis exists, asserted as a test.

    A severe outer-race defect barely moves ISO 20816 RMS velocity, because
    its energy sits well above the 10-1000 Hz band the standard measures.
    """
    sim = VibrationSimulator(seed=13)
    fs = DEFAULT_MACHINE.sample_rate_hz
    healthy = velocity_rms_mm_s(sim.window(FaultSpec("healthy", 0.0)), fs)
    defect = velocity_rms_mm_s(sim.window(FaultSpec("outer_race", 1.0)), fs)
    assert iso_zone(defect) == "A"
    assert defect < healthy * 1.5


def test_stream_advances_its_clock_and_splices_windows():
    stream = Stream(seed=3, fault=FaultSpec("outer_race", 0.5))
    first = stream.next_window()
    assert stream.elapsed_seconds == pytest.approx(DEFAULT_MACHINE.window_seconds)
    second = stream.next_window()
    # No discontinuity at the seam beyond ordinary sample-to-sample variation.
    seam = abs(second[0] - first[-1])
    assert seam < 6 * float(np.abs(np.diff(first)).mean())


@pytest.mark.parametrize(
    "kwargs",
    [
        {"mode": "not_a_mode"},
        {"mode": "healthy", "severity": 1.5},
        {"mode": "healthy", "severity": -0.1},
        {"mode": "healthy", "load": 9.0},
        {"mode": "healthy", "shaft_rpm": 1.0},
    ],
)
def test_invalid_fault_specs_are_rejected(kwargs):
    with pytest.raises(ValueError):
        FaultSpec(**kwargs)
