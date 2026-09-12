"""Smoke tests for the foundation-only FastAPI shell."""

from __future__ import annotations

from fastapi.testclient import TestClient

from standup_pilot.api.main import app


def test_health_endpoint_is_available_without_external_services():
    response = TestClient(app).get("/healthz")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_foundation_api_does_not_expose_caption_ingress_yet():
    paths = {route.path for route in app.routes}

    assert "/healthz" in paths
    assert "/v1/captions" not in paths
