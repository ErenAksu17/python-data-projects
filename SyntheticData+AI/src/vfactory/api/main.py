"""FastAPI service: the replacement for the Streamlit app.

Why not Streamlit. The original dashboard was a ``for`` loop with
``time.sleep(0.5)`` inside the script body. Streamlit re-runs the whole script
on every interaction, so that loop blocked the session, could not be paused,
held no state between runs, redrew a Matplotlib figure per frame, and served
exactly one viewer per process. None of that is a Streamlit bug -- it is what
happens when a streaming problem is forced into a re-run-the-script framework.

This service splits the concerns properly:

* the **API** owns simulation and inference and pushes analysed frames over a
  WebSocket, so state lives in one place and many clients can watch at once;
* the **frontend** is a static bundle that renders those frames;
* inference is NumPy over a JSON weight bundle, so the container needs neither
  PyTorch nor scikit-learn and starts in about a second.

Both artifacts are read once at startup and served from memory.
"""

from __future__ import annotations

import asyncio
import contextlib
import itertools
import json
import os
import time
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .. import __version__
from ..autoencoder import AutoencoderBundle
from ..config import DEFAULT_MACHINE, ENVELOPE_BAND_HZ, FAULT_MODES
from ..detector import analyse
from ..features import amplitude_spectrum, describe, envelope_spectrum
from ..simulator import FaultSpec, Stream
from .schemas import (
    AnalyseRequest,
    MachineInfo,
    ModelInfo,
    SimulationRequest,
    StreamControl,
)
from .security import (
    BodySizeLimitMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    allowed_origins,
    max_streams,
    websocket_origin_allowed,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[3]
ARTIFACTS_DIR = Path(os.getenv("VFACTORY_ARTIFACTS", PACKAGE_ROOT / "artifacts"))

#: Samples of raw waveform pushed per frame (about 32 ms at 12 kHz) -- enough
#: to see individual impacts without decimating them into aliasing artefacts.
WAVEFORM_SAMPLES = 384
#: Spectrum buckets sent per frame; peak-pooled so a narrow line survives.
SPECTRUM_BUCKETS = 192
SPECTRUM_MAX_HZ = 6_000.0
#: Envelope spectrum only needs to reach past the highest defect harmonic.
ENVELOPE_MAX_HZ = 500.0

_state: dict[str, Any] = {}


# --------------------------------------------------------------------------- #
# Artifact loading
# --------------------------------------------------------------------------- #


def _load_json(name: str) -> dict[str, Any] | None:
    path = ARTIFACTS_DIR / name
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _load_bundle() -> AutoencoderBundle:
    path = ARTIFACTS_DIR / "model.json"
    if not path.exists():
        raise RuntimeError(
            f"model bundle not found at {path}. "
            "Run: python scripts/train_and_benchmark.py"
        )
    return AutoencoderBundle.load(path)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    _state["bundle"] = _load_bundle()
    _state["benchmark"] = _load_json("benchmark.json")
    _state["ablation"] = _load_json("ablation.json")
    _state["streams"] = 0
    yield
    _state.clear()


app = FastAPI(
    title="Virtual Factory API",
    version=__version__,
    summary="Synthetic vibration streaming and autoencoder anomaly detection",
    lifespan=lifespan,
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
    max_age=600,
)


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Report *why* a request was rejected without echoing the request back.

    FastAPI's default handler includes the offending input, which here can be a
    24 000-element array -- and if it contains a non-finite value the error
    response itself fails to serialise, turning a clean 422 into a 500. It is
    also a free amplification vector, so the input is dropped entirely.
    """
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {
                    "loc": [str(part) for part in error.get("loc", ())],
                    "msg": error.get("msg", "invalid value"),
                    "type": error.get("type", "value_error"),
                }
                for error in exc.errors()
            ]
        },
    )


def bundle() -> AutoencoderBundle:
    model = _state.get("bundle")
    if model is None:
        raise HTTPException(status_code=503, detail="model not loaded")
    return model


# --------------------------------------------------------------------------- #
# Frame assembly
# --------------------------------------------------------------------------- #


def _peak_pool(
    freqs: np.ndarray, amp: np.ndarray, max_hz: float, buckets: int
) -> tuple[list[float], list[float]]:
    """Down-sample a spectrum by taking the peak in each bucket.

    Averaging would erase exactly what matters here -- a single narrow defect
    line is the whole signal.
    """
    keep = freqs <= max_hz
    freqs, amp = freqs[keep], amp[keep]
    if freqs.size <= buckets:
        return [round(float(f), 2) for f in freqs], [round(float(a), 6) for a in amp]

    edges = np.linspace(0, freqs.size, buckets + 1).astype(int)
    out_f, out_a = [], []
    for lo, hi in itertools.pairwise(edges):
        if hi <= lo:
            continue
        chunk = amp[lo:hi]
        best = int(np.argmax(chunk))
        out_f.append(round(float(freqs[lo + best]), 2))
        out_a.append(round(float(chunk[best]), 6))
    return out_f, out_a


def build_frame(
    window: np.ndarray, fault: FaultSpec, seq: int, elapsed: float
) -> dict[str, Any]:
    """Analyse one window and package everything the dashboard draws."""
    model = bundle()
    machine = DEFAULT_MACHINE
    verdict, features = analyse(window, model, machine, shaft_rpm=fault.shaft_rpm)

    freqs, amp = amplitude_spectrum(window, machine.sample_rate_hz)
    spec_x, spec_y = _peak_pool(freqs, amp, SPECTRUM_MAX_HZ, SPECTRUM_BUCKETS)

    env_freqs, env_amp = envelope_spectrum(window, machine.sample_rate_hz)
    env_keep = env_freqs <= ENVELOPE_MAX_HZ
    env_x = [round(float(f), 2) for f in env_freqs[env_keep]]
    env_y = [round(float(a), 6) for a in env_amp[env_keep]]

    return {
        "seq": seq,
        "t": round(elapsed, 3),
        "fault": {
            "mode": fault.mode,
            "severity": fault.severity,
            "shaft_rpm": fault.shaft_rpm or machine.shaft_rpm,
            "load": fault.load,
        },
        "verdict": verdict.to_json(),
        "waveform": [round(float(v), 5) for v in window[:WAVEFORM_SAMPLES]],
        "spectrum": {"x": spec_x, "y": spec_y},
        "envelope": {"x": env_x, "y": env_y},
        "features": {k: round(v, 5) for k, v in describe(features).items()},
    }


# --------------------------------------------------------------------------- #
# REST
# --------------------------------------------------------------------------- #


@app.get("/healthz", tags=["ops"])
def healthz() -> dict[str, Any]:
    model = _state.get("bundle")
    return {
        "status": "ok" if model else "degraded",
        "version": __version__,
        "model_loaded": model is not None,
        "active_streams": _state.get("streams", 0),
    }


@app.get("/api/machine", response_model=MachineInfo, tags=["reference"])
def machine_info() -> MachineInfo:
    m = DEFAULT_MACHINE
    return MachineInfo(
        sample_rate_hz=m.sample_rate_hz,
        window_size=m.window_size,
        window_seconds=round(m.window_seconds, 5),
        shaft_rpm=m.shaft_rpm,
        shaft_hz=round(m.shaft_hz, 4),
        resonance_hz=m.resonance_hz,
        freq_resolution_hz=round(m.freq_resolution_hz, 4),
        fault_modes=list(FAULT_MODES),
        defect_orders={k: round(v, 4) for k, v in m.bearing.defect_orders().items()},
        defect_frequencies_hz={
            k: round(v, 2) for k, v in m.bearing.defect_frequencies(m.shaft_rpm).items()
        },
        envelope_band_hz=list(ENVELOPE_BAND_HZ),
    )


@app.get("/api/model", response_model=ModelInfo, tags=["model"])
def model_info() -> ModelInfo:
    model = bundle()
    return ModelInfo(
        version=__version__,
        architecture=model.architecture,
        latent_dim=model.latent_dim,
        parameters=int(
            sum(layer.weight.size + layer.bias.size for layer in model.layers)
        ),
        threshold=model.threshold,
        feature_names=list(model.feature_names),
        metadata=model.metadata,
    )


@app.get("/api/model/weights", tags=["model"])
def model_weights() -> JSONResponse:
    """The full weight bundle, so the browser can score frames offline."""
    return JSONResponse(bundle().to_json())


@app.get("/api/benchmark", tags=["model"])
def benchmark_report() -> dict[str, Any]:
    report = _state.get("benchmark")
    if report is None:
        raise HTTPException(status_code=404, detail="benchmark report not generated")
    return report


@app.get("/api/ablation", tags=["model"])
def ablation_report() -> dict[str, Any]:
    report = _state.get("ablation")
    if report is None:
        raise HTTPException(status_code=404, detail="ablation report not generated")
    return report


@app.post("/api/simulate", tags=["simulation"])
def simulate(request: SimulationRequest) -> dict[str, Any]:
    """Generate and analyse a short burst of windows in one call."""
    fault = FaultSpec(
        mode=request.mode,
        severity=request.severity,
        shaft_rpm=request.shaft_rpm,
        load=request.load,
    )
    stream = Stream(DEFAULT_MACHINE, seed=None, fault=fault)
    frames = []
    for seq in range(request.windows):
        window = stream.next_window()
        frames.append(build_frame(window, fault, seq, stream.elapsed_seconds))
    return {"frames": frames}


@app.post("/api/analyze", tags=["model"])
def analyze(request: AnalyseRequest) -> dict[str, Any]:
    """Score a window supplied by the caller."""
    window = np.asarray(request.samples, dtype=np.float64)
    expected = DEFAULT_MACHINE.window_size
    if window.size < expected:
        raise HTTPException(
            status_code=422,
            detail=f"need at least {expected} samples at {DEFAULT_MACHINE.sample_rate_hz} Hz",
        )
    fault = FaultSpec(mode="healthy", severity=0.0, shaft_rpm=request.shaft_rpm)
    return build_frame(window[:expected], fault, seq=0, elapsed=0.0)


# --------------------------------------------------------------------------- #
# WebSocket stream
# --------------------------------------------------------------------------- #


class _StreamSession:
    """Mutable stream state, driven by control messages from the client."""

    def __init__(self) -> None:
        self.stream = Stream(DEFAULT_MACHINE, seed=None)
        self.interval = 0.5
        self.paused = False
        self.seq = 0

    def apply(self, control: StreamControl) -> None:
        current = self.stream.fault
        self.stream.set_fault(
            FaultSpec(
                mode=control.mode or current.mode,
                severity=(
                    current.severity if control.severity is None else control.severity
                ),
                shaft_rpm=control.shaft_rpm or current.shaft_rpm,
                load=current.load if control.load is None else control.load,
            )
        )
        if control.interval_ms is not None:
            self.interval = control.interval_ms / 1000.0
        if control.paused is not None:
            self.paused = control.paused


#: Control messages accepted per connection per minute. A slider drag emits a
#: handful; anything past this is a client trying to make the server work.
MAX_CONTROL_MESSAGES_PER_MINUTE = 240


async def _consume_control(websocket: WebSocket, session: _StreamSession) -> None:
    """Read control messages until the client goes away."""
    received: deque[float] = deque()
    while True:
        payload = await websocket.receive_json()

        now = time.monotonic()
        while received and received[0] < now - 60.0:
            received.popleft()
        received.append(now)
        if len(received) > MAX_CONTROL_MESSAGES_PER_MINUTE:
            await websocket.close(code=1008, reason="control message rate exceeded")
            return

        try:
            session.apply(StreamControl.model_validate(payload))
        except ValidationError as exc:
            await websocket.send_json({"type": "error", "detail": exc.errors(include_url=False)})


@app.websocket("/api/stream")
async def stream(websocket: WebSocket) -> None:
    # CORS middleware never sees a WebSocket handshake, and browsers do not
    # apply the same-origin policy to WebSockets -- so the allowlist has to be
    # enforced here or it is not enforced at all.
    if not websocket_origin_allowed(websocket.headers.get("origin")):
        await websocket.close(code=1008, reason="origin not allowed")
        return
    if _state.get("bundle") is None:
        await websocket.close(code=1011, reason="model not loaded")
        return
    if _state.get("streams", 0) >= max_streams():
        await websocket.close(code=1013, reason="too many streams")
        return

    await websocket.accept()
    _state["streams"] = _state.get("streams", 0) + 1
    session = _StreamSession()
    reader = asyncio.create_task(_consume_control(websocket, session))

    try:
        await websocket.send_json({"type": "hello", "machine": machine_info().model_dump()})
        while True:
            if reader.done():
                break
            if session.paused:
                await asyncio.sleep(0.1)
                continue
            # Advance by the acquisition period, so the timestamps a client
            # plots are real elapsed time rather than window-length ticks.
            window = session.stream.next_window(advance_seconds=session.interval)
            frame = build_frame(
                window, session.stream.fault, session.seq, session.stream.elapsed_seconds
            )
            session.seq += 1
            await websocket.send_json({"type": "frame", **frame})
            await asyncio.sleep(session.interval)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        reader.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await reader
        _state["streams"] = max(0, _state.get("streams", 1) - 1)


# --------------------------------------------------------------------------- #
# Optional single-container deployment
# --------------------------------------------------------------------------- #

# When VFACTORY_STATIC_DIR points at a built dashboard, the same process serves
# both the API and the UI -- one container, one origin, no CORS. Left unset
# (the default, and what the dev proxy uses) the API serves JSON only, so the
# frontend can be hosted separately on a CDN.
_static_dir = os.getenv("VFACTORY_STATIC_DIR")
if _static_dir and Path(_static_dir).is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="dashboard")
