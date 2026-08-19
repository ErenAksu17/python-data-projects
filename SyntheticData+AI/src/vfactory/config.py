"""Machine, bearing and pipeline configuration.

Every number here is a physical property of the simulated machine, kept in one
place so the simulator, the feature extractor and the dashboard all agree on
what "1x shaft speed" or "BPFO" means.

Defaults describe an SKF 6205-2RS deep-groove ball bearing on a 2 hp induction
motor sampled at 12 kHz -- the same setup as the Case Western Reserve
University bearing dataset, so the synthetic signals stay in a regime that
real published work can be compared against.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# --------------------------------------------------------------------------- #
# Bearing geometry
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class BearingGeometry:
    """Rolling-element bearing geometry (SKF 6205-2RS by default)."""

    n_elements: int = 9
    element_diameter_mm: float = 7.94
    pitch_diameter_mm: float = 39.04
    contact_angle_deg: float = 0.0

    @property
    def _ratio(self) -> float:
        """(Bd / Pd) * cos(phi) -- the term every defect formula shares."""
        return (
            self.element_diameter_mm
            / self.pitch_diameter_mm
            * math.cos(math.radians(self.contact_angle_deg))
        )

    # Defect orders are multiples of shaft speed, fixed by geometry alone.
    @property
    def bpfo_order(self) -> float:
        """Ball pass frequency, outer race."""
        return 0.5 * self.n_elements * (1.0 - self._ratio)

    @property
    def bpfi_order(self) -> float:
        """Ball pass frequency, inner race."""
        return 0.5 * self.n_elements * (1.0 + self._ratio)

    @property
    def bsf_order(self) -> float:
        """Ball spin frequency."""
        pd_bd = self.pitch_diameter_mm / self.element_diameter_mm
        return 0.5 * pd_bd * (1.0 - self._ratio**2)

    @property
    def ftf_order(self) -> float:
        """Fundamental train (cage) frequency."""
        return 0.5 * (1.0 - self._ratio)

    def defect_orders(self) -> dict[str, float]:
        return {
            "bpfo": self.bpfo_order,
            "bpfi": self.bpfi_order,
            "bsf": self.bsf_order,
            "ftf": self.ftf_order,
        }

    def defect_frequencies(self, shaft_rpm: float) -> dict[str, float]:
        """Defect frequencies in Hz at a given shaft speed."""
        fr = shaft_rpm / 60.0
        return {name: order * fr for name, order in self.defect_orders().items()}


# --------------------------------------------------------------------------- #
# Acquisition / machine
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class MachineSpec:
    """Acquisition settings and the machine's mechanical signature."""

    sample_rate_hz: int = 12_000
    window_size: int = 2_048
    shaft_rpm: float = 1_797.0

    #: Structural resonance excited by bearing impacts (Hz).
    resonance_hz: float = 3_000.0
    #: Exponential decay rate of the impact ringdown (1/s). Higher = shorter ring.
    resonance_decay: float = 900.0

    #: Baseline broadband noise floor (g RMS).
    noise_g: float = 0.035
    #: Residual 1x imbalance present even on a healthy machine (g).
    #: Chosen so a healthy machine sits around 1.7 mm/s RMS -- comfortably
    #: inside ISO 20816 zone A.
    baseline_imbalance_g: float = 0.035

    bearing: BearingGeometry = field(default_factory=BearingGeometry)

    @property
    def shaft_hz(self) -> float:
        return self.shaft_rpm / 60.0

    @property
    def window_seconds(self) -> float:
        return self.window_size / self.sample_rate_hz

    @property
    def freq_resolution_hz(self) -> float:
        return self.sample_rate_hz / self.window_size

    @property
    def nyquist_hz(self) -> float:
        return self.sample_rate_hz / 2.0


#: Fault modes the simulator can inject.
FAULT_MODES: tuple[str, ...] = (
    "healthy",
    "outer_race",
    "inner_race",
    "ball",
    "imbalance",
    "looseness",
)

#: Frequency bands (Hz) used for the spectral-energy features.
SPECTRAL_BANDS: tuple[tuple[float, float], ...] = (
    (0.0, 200.0),
    (200.0, 600.0),
    (600.0, 1_500.0),
    (1_500.0, 2_500.0),
    (2_500.0, 3_500.0),
    (3_500.0, 6_000.0),
)

#: Band-pass window (Hz) applied before envelope demodulation. Centred on the
#: structural resonance, where bearing impacts show up most cleanly.
ENVELOPE_BAND_HZ: tuple[float, float] = (2_000.0, 4_500.0)

#: ISO 20816-3 severity zones for medium machines (15-300 kW), RMS velocity
#: in mm/s over the 10-1000 Hz band.
ISO_20816_ZONES: tuple[tuple[str, float], ...] = (
    ("A", 2.8),   # newly commissioned
    ("B", 4.5),   # acceptable for unrestricted long-term operation
    ("C", 7.1),   # unsatisfactory -- investigate
    ("D", float("inf")),  # severe -- damage likely
)


def iso_zone(velocity_rms_mm_s: float) -> str:
    """Map an RMS velocity (mm/s) onto its ISO 20816-3 severity zone."""
    for zone, upper in ISO_20816_ZONES:
        if velocity_rms_mm_s <= upper:
            return zone
    return "D"


DEFAULT_MACHINE = MachineSpec()
