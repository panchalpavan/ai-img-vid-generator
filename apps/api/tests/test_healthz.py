"""Smoke test for the /healthz endpoint."""

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_healthz_returns_ok() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "img-vid-generation-api"}
