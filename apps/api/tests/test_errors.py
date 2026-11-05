import asyncio
import json
import logging
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from jev_rag_api.application.errors import ServiceUnavailableError
from jev_rag_api.core.logging import JsonFormatter, logger, request_id_context
from jev_rag_api.main import create_app


class Payload(BaseModel):
    count: int


def error_app(settings):
    app = create_app(settings)

    @app.get("/failure")
    async def failure():
        raise RuntimeError("secret-exception-value")

    @app.post("/validation")
    async def validation(payload: Payload):
        return payload

    @app.get("/dependency-failure")
    async def dependency_failure():
        raise ServiceUnavailableError("secret-dependency")

    return app


@pytest.mark.parametrize(
    "method, path, status, code",
    [
        ("GET", "/missing", 404, "NOT_FOUND"),
        ("POST", "/health/live", 405, "METHOD_NOT_ALLOWED"),
        ("POST", "/validation", 422, "VALIDATION_ERROR"),
        ("GET", "/failure", 500, "INTERNAL_ERROR"),
        ("GET", "/dependency-failure", 503, "SERVICE_UNAVAILABLE"),
    ],
)
def test_error_contract(settings, method, path, status, code):
    with TestClient(error_app(settings)) as client:
        response = client.request(
            method,
            path,
            json={"count": "secret-body"},
            headers={
                "X-Request-ID": "test-request",
                "Origin": "http://127.0.0.1:3000",
            },
        )
    body = response.json()
    assert response.status_code == status
    assert body["error"]["code"] == code
    assert body["request_id"] == response.headers["X-Request-ID"] == "test-request"
    assert "details" in body["error"]
    assert "secret" not in response.text
    assert "Traceback" not in response.text
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"
    if status == 405:
        assert "GET" in response.headers["Allow"]


@pytest.mark.parametrize("request_id", ["", "invalid id", "a" * 65])
def test_invalid_request_id_is_replaced(settings, request_id):
    with TestClient(create_app(settings)) as client:
        response = client.get("/health/live", headers={"X-Request-ID": request_id})
    assert UUID(response.headers["X-Request-ID"]).version == 4


def test_parallel_requests_and_logging(settings):
    records = []

    class Capture(logging.Handler):
        def emit(self, record):
            records.append(JsonFormatter().format(record))

    handler = Capture()
    logger.addHandler(handler)
    app = error_app(settings)

    @app.get("/parallel")
    async def parallel():
        await asyncio.sleep(0)
        return {"request_id": request_id_context.get()}

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            responses = await asyncio.gather(
                *[
                    client.get(
                        "/parallel?token=secret-query", headers={"X-Request-ID": f"request-{index}"}
                    )
                    for index in range(8)
                ]
            )
            await client.get("/failure")
        assert request_id_context.get() is None
        for index, response in enumerate(responses):
            assert (
                response.json()["request_id"]
                == response.headers["X-Request-ID"]
                == f"request-{index}"
            )

    try:
        asyncio.run(exercise())
    finally:
        logger.removeHandler(handler)
    assert len(records) == 9
    assert "secret" not in "".join(records)
    decoded = [json.loads(line) for line in records]
    for record in decoded:
        assert {
            "timestamp",
            "level",
            "service",
            "event",
            "request_id",
            "method",
            "path",
            "status_code",
            "duration_ms",
        } <= record.keys()
    assert decoded[-1]["exception_type"] == "RuntimeError"
    assert decoded[-1]["status_code"] == 500
