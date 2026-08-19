"""API surface: contracts, hardening and the WebSocket stream."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vfactory.api.main import app
from vfactory.config import DEFAULT_MACHINE

ARTIFACT = Path(__file__).resolve().parents[1] / "artifacts" / "model.json"

pytestmark = pytest.mark.skipif(
    not ARTIFACT.exists(), reason="run scripts/train_and_benchmark.py first"
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_healthz_reports_a_loaded_model(client: TestClient):
    payload = client.get("/healthz").json()
    assert payload["status"] == "ok"
    assert payload["model_loaded"] is True


def test_security_headers_are_present(client: TestClient):
    headers = client.get("/healthz").headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]


def test_machine_endpoint_exposes_the_bearing_geometry(client: TestClient):
    payload = client.get("/api/machine").json()
    assert payload["sample_rate_hz"] == DEFAULT_MACHINE.sample_rate_hz
    assert payload["defect_orders"]["bpfo"] == pytest.approx(3.585, abs=0.002)
    assert "outer_race" in payload["fault_modes"]


def test_model_endpoint_describes_the_bottleneck(client: TestClient):
    payload = client.get("/api/model").json()
    assert payload["architecture"][0] == payload["architecture"][-1]
    assert payload["latent_dim"] < payload["architecture"][0]
    assert payload["threshold"] > 0


def test_weights_endpoint_serves_a_loadable_bundle(client: TestClient):
    from vfactory.autoencoder import AutoencoderBundle

    payload = client.get("/api/model/weights").json()
    bundle = AutoencoderBundle.from_json(payload)
    assert bundle.threshold > 0


def test_simulate_returns_analysed_frames(client: TestClient):
    response = client.post(
        "/api/simulate",
        json={"mode": "outer_race", "severity": 0.9, "windows": 3},
    )
    assert response.status_code == 200
    frames = response.json()["frames"]
    assert len(frames) == 3

    frame = frames[0]
    assert frame["verdict"]["is_anomaly"] is True
    assert frame["verdict"]["diagnosis"] == "outer_race"
    assert len(frame["waveform"]) == 384
    assert len(frame["spectrum"]["x"]) == len(frame["spectrum"]["y"])
    assert frame["envelope"]["x"][-1] <= 500.0


def test_healthy_simulation_is_not_flagged(client: TestClient):
    frames = client.post(
        "/api/simulate", json={"mode": "healthy", "severity": 0.0, "windows": 8}
    ).json()["frames"]
    flagged = sum(f["verdict"]["is_anomaly"] for f in frames)
    assert flagged <= 1


@pytest.mark.parametrize(
    "payload",
    [
        {"mode": "meltdown"},
        {"mode": "healthy", "severity": 3.0},
        {"mode": "healthy", "windows": 500},
        {"mode": "healthy", "shaft_rpm": 99_999},
    ],
)
def test_invalid_simulation_requests_are_rejected(client: TestClient, payload):
    assert client.post("/api/simulate", json=payload).status_code == 422


def test_analyze_scores_a_caller_supplied_window(client: TestClient):
    from vfactory.simulator import FaultSpec, VibrationSimulator

    window = VibrationSimulator(seed=77).window(FaultSpec("inner_race", 0.9))
    response = client.post("/api/analyze", json={"samples": window.tolist()})
    assert response.status_code == 200
    assert response.json()["verdict"]["is_anomaly"] is True


def test_analyze_rejects_a_short_window(client: TestClient):
    assert client.post("/api/analyze", json={"samples": [0.0] * 128}).status_code == 422


def test_analyze_rejects_non_finite_samples(client: TestClient):
    # Sent as raw text: a NaN literal is not valid JSON, so the standard
    # encoder refuses to produce one, but a hand-rolled client can.
    body = '{"samples": [' + ", ".join(["0.0"] * 2_047) + ", NaN]}"
    response = client.post(
        "/api/analyze", content=body, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422


def test_analyze_rejects_an_oversized_payload(client: TestClient):
    payload = {"samples": [0.0] * 30_000}
    assert client.post("/api/analyze", json=payload).status_code == 422


def test_benchmark_and_ablation_are_served_when_present(client: TestClient):
    for path, key in (("/api/benchmark", "methods"), ("/api/ablation", "stages")):
        response = client.get(path)
        if response.status_code == 404:
            pytest.skip(f"{path} artifact not generated")
        assert key in response.json()


def test_websocket_streams_frames_and_accepts_control(client: TestClient):
    with client.websocket_connect("/api/stream") as socket:
        hello = socket.receive_json()
        assert hello["type"] == "hello"
        assert hello["machine"]["sample_rate_hz"] == DEFAULT_MACHINE.sample_rate_hz

        socket.send_json({"interval_ms": 100, "mode": "outer_race", "severity": 0.95})

        # The first frames may still carry the pre-control fault; keep reading
        # until the injected fault has taken effect.
        for _ in range(8):
            frame = socket.receive_json()
            assert frame["type"] == "frame"
            if frame["fault"]["mode"] == "outer_race":
                assert frame["verdict"]["is_anomaly"] is True
                break
        else:
            pytest.fail("fault injection never reached the stream")


def test_websocket_reports_invalid_control_without_dropping(client: TestClient):
    with client.websocket_connect("/api/stream") as socket:
        socket.receive_json()
        socket.send_json({"severity": 42.0})
        for _ in range(6):
            message = socket.receive_json()
            if message["type"] == "error":
                assert message["detail"]
                return
        pytest.fail("invalid control message was silently accepted")
