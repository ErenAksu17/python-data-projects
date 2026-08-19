"""Request and response models for the API.

Validation lives here rather than in the handlers so that a malformed control
message closes the socket with a clear reason instead of raising somewhere
deep in the simulator.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from ..config import FAULT_MODES

#: Hard cap on a client-supplied window. Two seconds at 12 kHz is already far
#: more than the model consumes, and it bounds the work one request can cause.
MAX_SAMPLES = 24_000

FaultMode = Literal["healthy", "outer_race", "inner_race", "ball", "imbalance", "looseness"]


class MachineInfo(BaseModel):
    sample_rate_hz: int
    window_size: int
    window_seconds: float
    shaft_rpm: float
    shaft_hz: float
    resonance_hz: float
    freq_resolution_hz: float
    fault_modes: list[str]
    defect_orders: dict[str, float]
    defect_frequencies_hz: dict[str, float]
    envelope_band_hz: list[float]


class ModelInfo(BaseModel):
    version: str
    architecture: list[int]
    latent_dim: int
    parameters: int
    threshold: float
    feature_names: list[str]
    metadata: dict[str, Any]


class Curve(BaseModel):
    """A decimated x/y pair, small enough to push at 4 Hz."""

    x: list[float]
    y: list[float]


class VerdictModel(BaseModel):
    score: float
    threshold: float
    is_anomaly: bool
    health_index: float
    status: str
    diagnosis: str
    diagnosis_label: str
    confidence: float
    evidence: list[str]
    contributors: list[dict[str, Any]]
    velocity_rms_mm_s: float
    iso_zone: str


class Frame(BaseModel):
    """One analysed acquisition window, as pushed over the WebSocket."""

    seq: int
    t: float
    fault: dict[str, Any]
    verdict: VerdictModel
    waveform: list[float]
    spectrum: Curve
    envelope: Curve
    features: dict[str, float]


class SimulationRequest(BaseModel):
    mode: FaultMode = "healthy"
    severity: float = Field(0.0, ge=0.0, le=1.0)
    shaft_rpm: float = Field(1797.0, ge=60.0, le=6000.0)
    load: float = Field(1.0, ge=0.25, le=2.0)
    windows: int = Field(1, ge=1, le=64)

    @field_validator("mode")
    @classmethod
    def _known_mode(cls, value: str) -> str:
        if value not in FAULT_MODES:
            raise ValueError(f"unknown fault mode: {value}")
        return value


class AnalyseRequest(BaseModel):
    """Score a caller-supplied acceleration window."""

    samples: list[float] = Field(..., min_length=64, max_length=MAX_SAMPLES)
    shaft_rpm: float | None = Field(None, ge=60.0, le=6000.0)

    @field_validator("samples")
    @classmethod
    def _finite(cls, values: list[float]) -> list[float]:
        import math

        if any(not math.isfinite(v) for v in values):
            raise ValueError("samples must all be finite")
        return values


class StreamControl(BaseModel):
    """Client -> server message on the WebSocket."""

    mode: FaultMode | None = None
    severity: float | None = Field(None, ge=0.0, le=1.0)
    shaft_rpm: float | None = Field(None, ge=60.0, le=6000.0)
    load: float | None = Field(None, ge=0.25, le=2.0)
    interval_ms: int | None = Field(None, ge=100, le=5_000)
    paused: bool | None = None
