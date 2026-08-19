"""Transport hardening, asserted rather than assumed.

These are the checks that stop a public deployment from being abused: an
allowlist that actually covers WebSockets, caps that actually cap, and error
responses that do not hand an attacker a free amplifier.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vfactory.api import security

ARTIFACT = Path(__file__).resolve().parents[1] / "artifacts" / "model.json"

pytestmark = pytest.mark.skipif(
    not ARTIFACT.exists(), reason="run scripts/train_and_benchmark.py first"
)


@pytest.fixture
def app_with_origins(monkeypatch):
    """Rebuild the app with a known CORS allowlist."""
    monkeypatch.setenv(security.ENV_ORIGINS, "https://allowed.example")
    module = importlib.import_module("vfactory.api.main")
    importlib.reload(module)
    yield module.app
    monkeypatch.delenv(security.ENV_ORIGINS, raising=False)
    importlib.reload(module)


def test_websocket_rejects_a_foreign_origin(app_with_origins):
    """CORS middleware never sees a handshake, so the route must check it.

    Browsers do not apply the same-origin policy to WebSockets: without this
    check any page on the internet could open a stream against the API.
    """
    # Starlette raises when the handshake is refused; the exact type differs
    # across versions, so the assertion is that it fails at all.
    def connect(client: TestClient) -> None:
        with client.websocket_connect(
            "/api/stream", headers={"Origin": "https://evil.example"}
        ) as socket:
            socket.receive_json()

    with TestClient(app_with_origins) as client, pytest.raises(Exception):  # noqa: B017
        connect(client)


def test_websocket_accepts_an_allowed_origin(app_with_origins):
    with TestClient(app_with_origins) as client, client.websocket_connect(
        "/api/stream", headers={"Origin": "https://allowed.example"}
    ) as socket:
        assert socket.receive_json()["type"] == "hello"


def test_websocket_allows_clients_that_send_no_origin(app_with_origins):
    """Origin is a browser signal; refusing its absence only breaks curl."""
    with TestClient(app_with_origins) as client, client.websocket_connect(
        "/api/stream"
    ) as socket:
        assert socket.receive_json()["type"] == "hello"


def test_origin_allowlist_defaults_to_localhost_only():
    """A deployment that forgets to configure origins must not default to '*'."""
    assert "*" not in security.allowed_origins()
    assert all("localhost" in o or "127.0.0.1" in o for o in security.allowed_origins())


def test_oversized_body_is_refused_before_parsing():
    from vfactory.api.main import app

    with TestClient(app) as client:
        response = client.post(
            "/api/analyze",
            content=b"{}",
            headers={"Content-Type": "application/json", "Content-Length": "99999999"},
        )
        assert response.status_code == 413


def test_validation_errors_do_not_echo_the_request_body():
    """Echoing a 24 000-element array back is a free amplification vector."""
    from vfactory.api.main import app

    with TestClient(app) as client:
        # Too short for the schema, so this goes through the validation handler.
        response = client.post("/api/analyze", json={"samples": [1.0] * 10})
        assert response.status_code == 422
        body = response.json()
        assert "input" not in str(body), "the rejected payload leaked into the error"
        assert all({"loc", "msg", "type"} >= set(item) for item in body["detail"])

        # Long enough to parse but too short to score: a plain message, and
        # still no echo of the caller's array.
        response = client.post("/api/analyze", json={"samples": [1.0] * 100})
        assert response.status_code == 422
        assert isinstance(response.json()["detail"], str)
        assert len(response.content) < 512


def test_rate_limiter_eventually_refuses():
    from vfactory.api import main

    with TestClient(main.app) as client:
        limit = security.rate_limit()
        statuses = {client.get("/api/machine").status_code for _ in range(limit + 5)}
        assert 429 in statuses


def test_healthz_is_never_rate_limited():
    """A liveness probe that trips the rate limiter takes the service down."""
    from vfactory.api.main import app

    with TestClient(app) as client:
        assert all(client.get("/healthz").status_code == 200 for _ in range(50))
