from typing import Any

import pytest
from fastapi.testclient import TestClient

from jev_rag_api.core.config import Settings
from jev_rag_api.main import create_app


def test_docs_and_schema(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        assert client.get("/docs").status_code == 200
        schema = client.get("/openapi.json").json()
    assert set(schema["paths"]) == {"/health/live", "/health/ready", "/api/v1/system/status"}
    assert "503" in schema["paths"]["/health/ready"]["get"]["responses"]


@pytest.mark.parametrize(
    "origin, allowed",
    [
        ("http://127.0.0.1:3000", True),
        ("http://localhost:3000", False),
        ("https://example.com", False),
    ],
)
def test_cors_preflight(settings: Settings, origin: Any, allowed: Any) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.options(
            "/health/live",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-Request-ID,Content-Type",
            },
        )
    assert response.status_code == (200 if allowed else 400)
    assert ("access-control-allow-origin" in response.headers) == allowed
    assert "x-request-id" in response.headers
    assert "access-control-allow-credentials" not in response.headers


def test_cors_rejects_post(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        assert (
            client.options(
                "/health/live",
                headers={
                    "Origin": "http://127.0.0.1:3000",
                    "Access-Control-Request-Method": "POST",
                },
            ).status_code
            == 400
        )
