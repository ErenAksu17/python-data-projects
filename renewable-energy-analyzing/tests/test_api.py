"""API behaviour + security posture, via FastAPI's TestClient."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import main  # api/main.py (on path via conftest)


@pytest.fixture(scope="module")
def client() -> TestClient:
    main.load_data()  # ensure processed data is loaded
    return TestClient(main.app)


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_summary_shape(client):
    r = client.get("/api/summary")
    assert r.status_code == 200
    body = r.json()
    assert {"meta", "target", "eu", "insights"} <= body.keys()
    assert 0 <= body["eu"]["latest"]["value"] <= 100


def test_security_headers_present(client):
    r = client.get("/api/summary")
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["x-content-type-options"] == "nosniff"


def test_known_country_ok(client):
    r = client.get("/api/country/AL")
    assert r.status_code == 200
    assert r.json()["geo"] == "AL"


def test_unknown_country_is_404_not_reflected(client):
    r = client.get("/api/country/ZZ")
    assert r.status_code == 404
    # The raw input must not be echoed back.
    assert "ZZ" not in r.text


def test_bad_country_pattern_rejected(client):
    # lowercase / symbols violate the path pattern -> 422 before handler.
    assert client.get("/api/country/al").status_code == 422
    assert client.get("/api/country/A.B").status_code == 422


def test_ranking_limit_validation(client):
    assert client.get("/api/ranking?limit=0").status_code == 422
    assert client.get("/api/ranking?limit=999").status_code == 422
    ok = client.get("/api/ranking?limit=5")
    assert ok.status_code == 200
    assert len(ok.json()["ranking"]) == 5


def test_ranking_sorted_desc(client):
    rows = client.get("/api/ranking?limit=37").json()["ranking"]
    vals = [r["value"] for r in rows]
    assert vals == sorted(vals, reverse=True)
