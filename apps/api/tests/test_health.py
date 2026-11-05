import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient

from jev_rag_api.core.config import Settings
from jev_rag_api.main import create_app


class FakeProbe:
    def __init__(self, up: Any) -> None:
        self.up = up
        self.calls = 0

    async def check_health(self) -> bool:
        self.calls += 1
        return bool(self.up)


@pytest.mark.parametrize(
    "up, status, body",
    [
        (True, 200, {"status": "ready", "dependencies": {"qdrant": "up"}}),
        (False, 503, {"status": "not_ready", "dependencies": {"qdrant": "down"}}),
    ],
)
def test_readiness(settings: Settings, up: Any, status: Any, body: Any) -> None:
    probe = FakeProbe(up)
    with TestClient(create_app(settings, probe)) as client:
        response = client.get("/health/ready")
    assert response.status_code == status
    assert response.json() == body
    assert probe.calls == 1


def test_liveness_and_status_do_not_call_dependencies(settings: Settings) -> None:
    probe = FakeProbe(False)
    with TestClient(create_app(settings, probe)) as client:
        assert client.get("/health/live").json() == {"status": "alive"}
        assert client.get("/api/v1/system/status").json() == {"service": "api", "status": "ok"}
    assert probe.calls == 0


def test_unconfigured_readiness(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        assert client.get("/health/ready").status_code == 503


def test_readiness_timeout(settings: Settings) -> None:
    class SlowProbe:
        async def check_health(self) -> bool:
            await asyncio.sleep(10)
            return True

    settings.qdrant_timeout_seconds = 0.001
    with TestClient(create_app(settings, SlowProbe())) as client:
        assert client.get("/health/ready").status_code == 503
