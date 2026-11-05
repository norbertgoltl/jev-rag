import asyncio
import json
from typing import Any

import httpx
import pytest

from jev_rag_api.core.logging import JsonFormatter
from jev_rag_api.integrations.qdrant.readiness import QdrantReadinessProbe


@pytest.mark.parametrize(
    "status,expected", [(200, True), (201, False), (302, False), (500, False), (503, False)]
)
def test_http_readiness(status: Any, expected: Any) -> None:
    async def scenario() -> Any:
        async with httpx.AsyncClient(
            base_url="http://qdrant/",
            transport=httpx.MockTransport(lambda request: httpx.Response(status)),
        ) as client:
            assert await QdrantReadinessProbe(client).check_health() is expected

    asyncio.run(scenario())


@pytest.mark.parametrize("error", [httpx.ConnectError, httpx.ReadTimeout])
def test_network_failure_and_recovery(error: Any, caplog: pytest.LogCaptureFixture) -> None:
    async def scenario() -> Any:
        attempts = 0

        def handler(request: Any) -> Any:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise error("private-connection-secret", request=request)
            return httpx.Response(200)

        async with httpx.AsyncClient(
            base_url="http://qdrant/", transport=httpx.MockTransport(handler)
        ) as client:
            probe = QdrantReadinessProbe(client)
            assert await probe.check_health() is False
            assert await probe.check_health() is True

    asyncio.run(scenario())
    assert "private-connection-secret" not in caplog.text


def test_failures_are_logged_as_named_events(caplog: pytest.LogCaptureFixture) -> None:
    async def scenario() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503)

        async with httpx.AsyncClient(
            base_url="http://qdrant/", transport=httpx.MockTransport(handler)
        ) as client:
            assert await QdrantReadinessProbe(client).check_health() is False

    with caplog.at_level("WARNING", logger="jev_rag_api"):
        asyncio.run(scenario())
    record = next(item for item in caplog.records if item.getMessage() == "qdrant_not_ready")
    assert json.loads(JsonFormatter().format(record))["event"] == "qdrant_not_ready"
    assert record.status_code == 503  # type: ignore[attr-defined]
