"""Smoke tests for the FastAPI app factory."""

from fastapi.testclient import TestClient

from main import app


def test_app_starts() -> None:
    client = TestClient(app)
    resp = client.get("/api/v1/status/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_root_redirects_to_docs() -> None:
    client = TestClient(app)
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert resp.headers["location"] == "/docs"
