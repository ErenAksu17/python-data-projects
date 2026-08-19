"""Physics-based accelerometer simulator for a rotating machine.

The original project drew "vibration" from ``np.random.normal`` -- a number
with no mechanical meaning, on which no diagnostic feature can possibly work.
This module instead synthesises an accelerometer signal the way a real machine
produces one:

* deterministic shaft components at 1x, 2x, 3x running speed;
* localised bearing defects modelled as an impulse train at the geometric
  defect frequency, each impulse ringing down the structural resonance;
* load-zone amplitude modulation (inner-race defects at 1x, ball defects at
  cage frequency), which is exactly what makes envelope analysis work;
* small random slip on the impulse spacing, as rolling elements really do;
* a broadband noise floor.

Signals are produced in *g* (acceleration). A :class:`Stream` keeps a
continuous time cursor so successive windows splice together without a seam,
which matters when the dashboard plots them back to back.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .config import DEFAULT_MACHINE, FAULT_MODES, MachineSpec


def _index_jitter(index: np.ndarray) -> np.ndarray:
    """Reproducible pseudo-random values in [-0.5, 0.5) keyed by impulse index.

    Keying off the index rather than an RNG stream means a ringdown tail that
    crosses a window boundary is generated identically in both windows.
    """
    raw = np.sin(index.astype(np.float64) * 12.9898) * 43758.5453
    return (raw - np.floor(raw)) - 0.5


@dataclass(frozen=True)
class FaultSpec:
    """What the simulator should inject into the next window."""

    mode: str = "healthy"
    #: 0 = pristine, 1 = severe. Scales defect impulse energy.
    severity: float = 0.0
    shaft_rpm: float | None = None
    #: Machine load, 0.25-2.0. Deepens the load zone and lifts the noise floor.
    load: float = 1.0

    def __post_init__(self) -> None:
        if self.mode not in FAULT_MODES:
            raise ValueError(
                f"unknown fault mode {self.mode!r}; expected one of {FAULT_MODES}"
            )
        if not 0.0 <= self.severity <= 1.0:
            raise ValueError("severity must be within [0, 1]")
        if not 0.25 <= self.load <= 2.0:
            raise ValueError("load must be within [0.25, 2.0]")
        if self.shaft_rpm is not None and not 60.0 <= self.shaft_rpm <= 6_000.0:
            raise ValueError("shaft_rpm must be within [60, 6000]")

    @property
    def is_faulty(self) -> bool:
        return self.mode != "healthy" and self.severity > 0.0


class VibrationSimulator:
    """Generates accelerometer windows for a machine under a given fault."""

    def __init__(self, machine: MachineSpec = DEFAULT_MACHINE, seed: int | None = 7) -> None:
        self.machine = machine
        self._rng = np.random.default_rng(seed)

    # ------------------------------------------------------------------ #
    # Building blocks
    # ------------------------------------------------------------------ #

    def _shaft_component(
        self, t: np.ndarray, fault: FaultSpec, shaft_hz: float
    ) -> np.ndarray:
        """Running-speed harmonics: always present, amplified by some faults."""
        m = self.machine
        one_x = m.baseline_imbalance_g
        two_x = one_x * 0.35
        three_x = one_x * 0.18
        half_x = 0.0

        # Coefficients are calibrated so that severity 1.0 lands in ISO 20816
        # zone D (~10-13 mm/s RMS velocity) rather than at an absurd level.
        if fault.mode == "imbalance":
            # Mass imbalance is almost purely 1x and grows with speed squared.
            one_x += 0.18 * fault.severity * (shaft_hz / m.shaft_hz) ** 2
        elif fault.mode == "looseness":
            # Looseness lifts the whole harmonic family and adds a 0.5x
            # subharmonic as the joint rattles every other revolution.
            two_x += 0.185 * fault.severity
            three_x += 0.140 * fault.severity
            half_x = 0.081 * fault.severity

        phase = 2.0 * math.pi * shaft_hz * t
        signal = (
            one_x * np.sin(phase)
            + two_x * np.sin(2.0 * phase + 0.6)
            + three_x * np.sin(3.0 * phase + 1.9)
        )
        if half_x:
            signal += half_x * np.sin(0.5 * phase + 0.4)
        return signal

    def _impulse_train(
        self,
        t: np.ndarray,
        defect_hz: float,
        amplitude: float,
        modulation_hz: float,
        modulation_depth: float,
        slip: float,
    ) -> np.ndarray:
        """Impacts at ``defect_hz``, each ringing down the structural resonance."""
        m = self.machine
        if amplitude <= 0.0 or defect_hz <= 0.0:
            return np.zeros_like(t)

        period = 1.0 / defect_hz
        # Include impulses that started just before the window: their ringdown
        # tail still leaks in. Six time constants is fully decayed.
        tail = 6.0 / m.resonance_decay
        first = math.floor((t[0] - tail) / period)
        last = math.ceil(t[-1] / period)
        k = np.arange(first, last + 1)
        onsets = (k + slip * _index_jitter(k)) * period

        # Load-zone modulation: a defect on a rotating race (or on a rolling
        # element) passes through the loaded region once per modulation cycle.
        gains = np.ones_like(onsets)
        if modulation_hz > 0.0 and modulation_depth > 0.0:
            gains = 1.0 + modulation_depth * np.cos(
                2.0 * math.pi * modulation_hz * onsets
            )
            gains = np.clip(gains, 0.0, None)

        # Impact-to-impact energy scatter, ~10% in real measurements.
        gains = gains * (1.0 + 0.10 * _index_jitter(k + 10_007))

        dt = t[None, :] - onsets[:, None]
        active = dt >= 0.0
        safe_dt = np.where(active, dt, 0.0)
        ring = np.where(
            active,
            np.exp(-m.resonance_decay * safe_dt)
            * np.sin(2.0 * math.pi * m.resonance_hz * safe_dt),
            0.0,
        )
        return amplitude * (gains[:, None] * ring).sum(axis=0)

    def _defect_component(
        self, t: np.ndarray, fault: FaultSpec, shaft_hz: float
    ) -> np.ndarray:
        """The bearing-defect part of the signal, if any."""
        if fault.mode not in ("outer_race", "inner_race", "ball") or fault.severity <= 0.0:
            return np.zeros_like(t)

        freqs = self.machine.bearing.defect_frequencies(shaft_hz * 60.0)
        # Impact energy grows faster than linearly as a spall widens.
        amp = 0.9 * fault.severity**1.35 * fault.load

        if fault.mode == "outer_race":
            # Stationary race: the defect sits in the load zone permanently, so
            # impacts are steady. This is the easiest fault to see.
            return self._impulse_train(t, freqs["bpfo"], amp, 0.0, 0.0, slip=0.012)

        if fault.mode == "inner_race":
            # Rotating race: the defect sweeps in and out of the load zone once
            # per revolution -> strong 1x sidebands around BPFI.
            return self._impulse_train(
                t, freqs["bpfi"], amp * 0.85, shaft_hz, 0.85, slip=0.015
            )

        # Rolling element: modulated at cage speed, and it strikes both races,
        # so energy also appears at twice the ball spin frequency.
        base = self._impulse_train(
            t, freqs["bsf"], amp * 0.55, freqs["ftf"], 0.75, slip=0.025
        )
        return base + self._impulse_train(
            t, 2.0 * freqs["bsf"], amp * 0.40, freqs["ftf"], 0.75, slip=0.025
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def window(self, fault: FaultSpec | None = None, t0: float = 0.0) -> np.ndarray:
        """One acquisition window of acceleration samples, in g."""
        fault = fault or FaultSpec()
        m = self.machine
        shaft_hz = (fault.shaft_rpm / 60.0) if fault.shaft_rpm else m.shaft_hz
        t = t0 + np.arange(m.window_size, dtype=np.float64) / m.sample_rate_hz

        signal = self._shaft_component(t, fault, shaft_hz)
        signal += self._defect_component(t, fault, shaft_hz)

        noise = m.noise_g * (0.75 + 0.5 * fault.load)
        if fault.mode == "looseness":
            noise *= 1.0 + 0.9 * fault.severity
        signal += self._rng.normal(0.0, noise, size=m.window_size)
        return signal.astype(np.float64)

    def batch(
        self, fault: FaultSpec | None, n_windows: int, t0: float = 0.0
    ) -> np.ndarray:
        """``n_windows`` consecutive, seamlessly spliced windows."""
        step = self.machine.window_seconds
        return np.stack([self.window(fault, t0 + i * step) for i in range(n_windows)])


class Stream:
    """A live sensor: hands out windows and keeps the machine's clock.

    Real condition-monitoring systems do not stream continuously; they take a
    short acquisition every so often. ``advance_seconds`` models that: pass the
    acquisition period and the reported elapsed time is genuine wall-clock
    time, with the machine having kept turning between snapshots. Omit it and
    windows are contiguous, which is what an offline analysis of a continuous
    recording wants.
    """

    def __init__(
        self,
        machine: MachineSpec = DEFAULT_MACHINE,
        seed: int | None = None,
        fault: FaultSpec | None = None,
    ) -> None:
        self._sim = VibrationSimulator(machine, seed=seed)
        self._t = 0.0
        self.fault = fault or FaultSpec()

    @property
    def machine(self) -> MachineSpec:
        return self._sim.machine

    @property
    def elapsed_seconds(self) -> float:
        return self._t

    def set_fault(self, fault: FaultSpec) -> None:
        self.fault = fault

    def next_window(self, advance_seconds: float | None = None) -> np.ndarray:
        window = self._sim.window(self.fault, t0=self._t)
        step = self.machine.window_seconds if advance_seconds is None else advance_seconds
        self._t += max(step, self.machine.window_seconds)
        return window
